"""Portable durable outbox for the Brain client.

Stdlib-only transactional SQLite outbox used to durably enqueue uploads and
event/proposal enrichment jobs without coupling to server, Pydantic, or any
other dependency. The contract is intentionally narrow:

* ``enqueue(kind, payload, *, id, version)`` persists a job locally and
  returns the assigned identifier.
* ``claim_ready`` / ``record_success`` / ``record_failure`` advance the job
  lifecycle while preserving ``(id, version)`` identity so server-side
  idempotency keys stay stable across retries.
* ``run_once`` drives a single batch through an injectable transport, with
  bounded exponential backoff and jitter.
* ``backup_snapshot`` / ``open_snapshot`` produce a consistent read-only
  copy via SQLite's online backup API.
* Enrichment jobs live in a separate table so upload state is independent
  from enrichment state.

The outbox is designed for a single local disk. It does **not** provide
machine-loss resilience; an approved independent backup destination is
required before production resilience can be claimed.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OutboxError(Exception):
    """Base error for outbox operations."""


class DuplicateJobError(OutboxError):
    """Raised when an explicit id is already present in the outbox."""


class StaleJobError(OutboxError):
    """Raised when a record cannot advance because its version is stale."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    version: int
    payload: dict[str, Any]
    attempts: int
    state: str
    next_attempt_at: float
    lease_owner: str | None
    lease_expires_at: float | None
    last_error: str | None
    last_response: dict[str, Any] | None
    acknowledged_version: int | None


@dataclass(frozen=True)
class TransportResult:
    state: str  # "ok" | "retry" | "conflict" | "dropped_response_unknown"
    acknowledged_version: int | None = None
    response: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Outbox
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id                   TEXT PRIMARY KEY,
    kind                 TEXT NOT NULL,
    version              INTEGER NOT NULL,
    payload_json         TEXT NOT NULL,
    state                TEXT NOT NULL,
    attempts             INTEGER NOT NULL DEFAULT 0,
    next_attempt_at      REAL NOT NULL,
    lease_owner          TEXT,
    lease_expires_at     REAL,
    last_error           TEXT,
    last_response_json   TEXT,
    acknowledged_version INTEGER,
    canonical_digest     TEXT,
    created_at           REAL NOT NULL,
    updated_at           REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_due
    ON jobs (state, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_jobs_kind_state
    ON jobs (kind, state);

CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id                   TEXT PRIMARY KEY,
    kind                 TEXT NOT NULL,
    payload_json         TEXT NOT NULL,
    state                TEXT NOT NULL DEFAULT 'pending',
    attempts             INTEGER NOT NULL DEFAULT 0,
    next_attempt_at      REAL NOT NULL,
    last_error           TEXT,
    created_at           REAL NOT NULL,
    updated_at           REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enrich_due
    ON enrichment_jobs (state, next_attempt_at);
"""


def _now_default() -> float:
    return time.time()


def _set_owner_only_mode(path: Path) -> None:
    """Restrict permissions to the owner where the platform supports it.

    POSIX: chmod 0o600 on the SQLite file and the containing directory.
    Windows: ACL tightening is platform-incompatible from pure stdlib, so
    we rely on the user's profile-directory ACLs and document the gap.
    """
    if os.name != "posix":
        return
    try:
        if path.exists():
            os.chmod(path, 0o600)
        parent = path.parent
        if parent.exists():
            current = parent.stat().st_mode & 0o777
            if current & 0o077:
                os.chmod(parent, current & 0o700)
    except OSError:
        # Best-effort only; never block outbox creation on permission fixes.
        pass


class Outbox:
    """SQLite-backed durable outbox.

    Instances are safe to use from a single thread. Concurrent workers must
    each open their own ``Outbox`` against the same path; SQLite's write
    serialization arbitrates claims. The lease table guarantees that only
    one worker owns a given job at a time.
    """

    def __init__(self, path: os.PathLike[str] | str | Path,
                 *, clock: Callable[[], float] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or _now_default
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path),
            isolation_level=None,  # autocommit; we manage txns explicitly
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key,value) VALUES(?,?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        # Restrict permissions *after* SQLite finalizes the file so the
        # final mode is preserved (SQLite may reset bits during creation).
        _set_owner_only_mode(self.path)

    # -- helpers ----------------------------------------------------------

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def _begin(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def _commit(self) -> None:
        self._conn.execute("COMMIT")

    def _rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            kind=row["kind"],
            version=row["version"],
            payload=json.loads(row["payload_json"]),
            attempts=row["attempts"],
            state=row["state"],
            next_attempt_at=row["next_attempt_at"],
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            last_error=row["last_error"],
            last_response=(json.loads(row["last_response_json"])
                            if row["last_response_json"] else None),
            acknowledged_version=row["acknowledged_version"],
        )

    # -- enqueue ----------------------------------------------------------

    def enqueue(self, kind: str, payload: dict[str, Any], *,
                id: str | None = None, version: int = 1) -> str:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        if version < 1:
            raise ValueError("version must be >= 1")
        if id is not None and not id:
            raise ValueError("id must be a non-empty string")
        job_id = id or str(uuid.uuid4())
        now = self._clock()
        try:
            self._begin()
            self._conn.execute(
                "INSERT INTO jobs("
                "id, kind, version, payload_json, state, attempts,"
                "next_attempt_at, created_at, updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, kind, version, json.dumps(payload, sort_keys=True,
                                                    ensure_ascii=False),
                 "pending", 0, now, now, now),
            )
            self._commit()
        except sqlite3.IntegrityError as exc:
            self._rollback()
            raise DuplicateJobError(
                f"job id already exists: {job_id}"
            ) from exc
        return job_id

    def enqueue_enrichment(self, kind: str, payload: dict[str, Any],
                            *, id: str | None = None) -> str:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        job_id = id or str(uuid.uuid4())
        now = self._clock()
        try:
            self._begin()
            self._conn.execute(
                "INSERT INTO enrichment_jobs("
                "id, kind, payload_json, state, attempts,"
                "next_attempt_at, created_at, updated_at"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (job_id, kind,
                 json.dumps(payload, sort_keys=True, ensure_ascii=False),
                 "pending", 0, now, now, now),
            )
            self._commit()
        except sqlite3.IntegrityError as exc:
            self._rollback()
            raise DuplicateJobError(
                f"enrichment job id already exists: {job_id}"
            ) from exc
        return job_id

    # -- claim ------------------------------------------------------------

    def claim_ready(self, *, clock: Callable[[], float] | None = None,
                    owner: str, lease_seconds: int,
                    limit: int = 50) -> list[Job]:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if not owner:
            raise ValueError("owner must be non-empty")
        now = (clock or self._clock)()
        lease_until = now + lease_seconds
        claimed: list[Job] = []
        self._begin()
        try:
            rows = self._conn.execute(
                "SELECT * FROM jobs "
                "WHERE state='pending' AND next_attempt_at <= ? "
                "  AND (lease_owner IS NULL OR lease_expires_at <= ?) "
                "ORDER BY next_attempt_at ASC LIMIT ?",
                (now, now, limit),
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    "UPDATE jobs SET lease_owner=?, lease_expires_at=?,"
                    " updated_at=? WHERE id=? AND state='pending'",
                    (owner, lease_until, now, row["id"]),
                )
                # Re-read the row after update to capture lease fields.
                updated = self._conn.execute(
                    "SELECT * FROM jobs WHERE id=?", (row["id"],),
                ).fetchone()
                if updated is not None:
                    claimed.append(self._row_to_job(updated))
            self._commit()
        except Exception:
            self._rollback()
            raise
        return claimed

    # -- completion / failure --------------------------------------------

    def record_success(self, job_id: str, *, acknowledged_version: int,
                       response: dict[str, Any] | None,
                       now: float | None = None) -> None:
        ts = now if now is not None else self._clock()
        self._begin()
        try:
            row = self._conn.execute(
                "SELECT version FROM jobs WHERE id=?", (job_id,),
            ).fetchone()
            if row is None:
                self._rollback()
                raise OutboxError(f"unknown job id: {job_id}")
            # Exact acknowledgement: bools and missing/future versions
            # must not silently complete a persisted upload.
            if type(acknowledged_version) is not int or acknowledged_version != row["version"]:
                raise StaleJobError("exact-version-ack-required")
            self._conn.execute(
                "UPDATE jobs SET state='completed',"
                " acknowledged_version=?,"
                " last_response_json=?,"
                " last_error=NULL,"
                " lease_owner=NULL, lease_expires_at=NULL,"
                " updated_at=? WHERE id=?",
                (acknowledged_version,
                 json.dumps(response, sort_keys=True,
                            ensure_ascii=False) if response else None,
                 ts, job_id),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise

    def record_failure(self, job_id: str, *, error: str,
                        response: dict[str, Any] | None,
                        backoff_base: float, backoff_cap: float,
                        jitter: float, now: float | None = None) -> None:
        ts = now if now is not None else self._clock()
        if backoff_base <= 0 or backoff_cap < backoff_base:
            raise ValueError("backoff must satisfy 0 < base <= cap")
        if jitter < 0:
            raise ValueError("jitter must be >= 0")
        self._begin()
        try:
            row = self._conn.execute(
                "SELECT attempts FROM jobs WHERE id=?", (job_id,),
            ).fetchone()
            if row is None:
                self._rollback()
                raise OutboxError(f"unknown job id: {job_id}")
            attempts = row["attempts"] + 1
            backoff = self._backoff(attempts, backoff_base, backoff_cap,
                                     jitter, ts)
            self._conn.execute(
                "UPDATE jobs SET state='pending',"
                " attempts=?, next_attempt_at=?,"
                " last_error=?, last_response_json=?,"
                " lease_owner=NULL, lease_expires_at=NULL,"
                " updated_at=? WHERE id=?",
                (attempts, backoff, error,
                 json.dumps(response, sort_keys=True,
                            ensure_ascii=False) if response else None,
                 ts, job_id),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise

    def record_conflict(self, job_id: str, *, error: str,
                         response: dict[str, Any] | None,
                         now: float | None = None) -> None:
        ts = now if now is not None else self._clock()
        self._begin()
        try:
            self._conn.execute(
                "UPDATE jobs SET state='conflict',"
                " last_error=?, last_response_json=?,"
                " lease_owner=NULL, lease_expires_at=NULL,"
                " updated_at=? WHERE id=?",
                (error,
                 json.dumps(response, sort_keys=True,
                            ensure_ascii=False) if response else None,
                 ts, job_id),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise

    # -- run loop ---------------------------------------------------------

    def run_once(self, transport: Callable[[Job], TransportResult], *,
                 clock: Callable[[], float] | None = None,
                 owner: str, lease_seconds: int,
                 backoff_base: float = 2.0,
                 backoff_cap: float = 60.0,
                 jitter: float = 0.5,
                 limit: int = 25) -> dict[str, int]:
        """Process one batch of due jobs through ``transport``.

        Returns a counts dict with keys: claimed, completed, retried,
        conflicts, dropped_unknown.
        """
        now_fn = clock or self._clock
        claimed = self.claim_ready(clock=now_fn, owner=owner,
                                    lease_seconds=lease_seconds, limit=limit)
        completed = retried = conflicts = dropped = 0
        for job in claimed:
            try:
                result = transport(job)
            except Exception as exc:  # noqa: BLE001
                # Transport raised BEFORE send: nothing was sent, do not
                # count an attempt; release the lease so another worker
                # (or this one next round) can retry.
                self._begin()
                try:
                    self._conn.execute(
                        "UPDATE jobs SET lease_owner=NULL,"
                        " lease_expires_at=NULL,"
                        " last_error=?, updated_at=? WHERE id=?",
                        (f"transport-raised: {exc}", now_fn(), job.id),
                    )
                    self._commit()
                except Exception:
                    self._rollback()
                continue
            if result.state == "ok":
                try:
                    self.record_success(
                        job.id,
                        acknowledged_version=result.acknowledged_version
                            if result.acknowledged_version is not None
                            else job.version,
                        response=result.response,
                        now=now_fn(),
                    )
                    completed += 1
                except StaleJobError:
                    # Server already has a newer version; treat as conflict
                    # and stop retrying this id+version.
                    self.record_conflict(
                        job.id,
                        error="stale-version",
                        response=result.response,
                        now=now_fn(),
                    )
                    conflicts += 1
            elif result.state == "conflict":
                self.record_conflict(
                    job.id, error=result.error or "conflict",
                    response=result.response, now=now_fn(),
                )
                conflicts += 1
            elif result.state == "dropped_response_unknown":
                # Persist a separate held state: elapsed time and process
                # restart must never turn an ambiguous send into a retry.
                # Exact authorized server readback is required to resolve it.
                self._begin()
                try:
                    self._conn.execute(
                        "UPDATE jobs SET state='unknown', last_error=?,"
                        " last_response_json=?,"
                        " lease_owner=NULL, lease_expires_at=NULL,"
                        " updated_at=? WHERE id=?",
                        (result.error or "dropped-response-unknown",
                         json.dumps(result.response, sort_keys=True,
                                    ensure_ascii=False)
                            if result.response else None,
                         now_fn(), job.id),
                    )
                    self._commit()
                except Exception:
                    self._rollback()
                dropped += 1
            else:  # "retry" or anything else
                self.record_failure(
                    job.id, error=result.error or "retry",
                    response=result.response,
                    backoff_base=backoff_base, backoff_cap=backoff_cap,
                    jitter=jitter, now=now_fn(),
                )
                retried += 1
        return {
            "claimed": len(claimed),
            "completed": completed,
            "retried": retried,
            "conflicts": conflicts,
            "dropped_unknown": dropped,
        }

    # -- queries ----------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE id=?", (job_id,),
        ).fetchone()
        return self._row_to_job(row) if row else None

    def pending(self, *, kind: str | None = None) -> list[str]:
        if kind is None:
            rows = self._conn.execute(
                "SELECT id FROM jobs WHERE state='pending' ORDER BY id",
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM jobs WHERE state='pending' AND kind=? ORDER BY id",
                (kind,),
            ).fetchall()
        return [r["id"] for r in rows]

    def completed(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM jobs WHERE state='completed' ORDER BY id",
        ).fetchall()
        return [r["id"] for r in rows]

    def pending_enrichment(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM enrichment_jobs WHERE state='pending' ORDER BY id",
        ).fetchall()
        return [r["id"] for r in rows]

    def stats(self) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state",
        ).fetchall()
        by_state = {r["state"]: r["n"] for r in rows}
        total = sum(by_state.values())
        pending_ids = self.pending()
        return {"by_state": by_state, "total": total,
                "pending_ids": pending_ids}

    def inspect_unknown(self, job_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT id, kind, version, attempts, state, last_error,"
            " last_response_json, acknowledged_version, next_attempt_at"
            " FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise OutboxError(f"unknown job id: {job_id}")
        return {
            "id": row["id"],
            "kind": row["kind"],
            "version": row["version"],
            "attempts": row["attempts"],
            "state": row["state"],
            "last_error": row["last_error"],
            "last_response": (json.loads(row["last_response_json"])
                                if row["last_response_json"] else None),
            "acknowledged_version": row["acknowledged_version"],
            "next_attempt_at": row["next_attempt_at"],
        }

    def reconcile_unknown(self, job_id: str, lookup: Callable[..., Any]) -> str:
        """Resolve ambiguity through an injected authenticated exact-version read.

        The transport adapter, not a submitted payload, establishes authorization.
        Unavailable, unauthorized and mismatched replies never permit resending.
        This method does not upload or replay the original operation.
        """
        import hashlib
        job = self.get(job_id)
        if job is None:
            raise OutboxError("unknown job")
        if job.state != "unknown":
            return job.state
        try:
            evidence = lookup(job.kind, job.id, job.version)
        except Exception:
            return "unknown"
        if not isinstance(evidence, dict) or evidence.get("authorized") is not True:
            return "unknown"
        if evidence.get("id") != job.id or type(evidence.get("version")) is not int or evidence["version"] != job.version:
            return "unknown"
        digest = job.last_response.get("client_digest") if isinstance(job.last_response, dict) else None
        if not digest:
            digest = hashlib.sha256(json.dumps(job.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        status = evidence.get("status")
        if status == "accepted" and evidence.get("digest") == digest:
            state = "completed"
        elif status == "absent":
            state = "pending"
        else:
            return "unknown"
        self._begin()
        try:
            self._conn.execute(
                "UPDATE jobs SET state=?, acknowledged_version=?, last_error=NULL, updated_at=? "
                "WHERE id=? AND version=? AND state='unknown' AND payload_json=?",
                (state, job.version if state == "completed" else None, self._clock(), job.id, job.version,
                 json.dumps(job.payload, sort_keys=True, ensure_ascii=False)),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self.get(job_id).state

    # -- snapshot ---------------------------------------------------------

    def backup_snapshot(self, dest_path: os.PathLike[str] | str | Path
                         ) -> None:
        """Copy the outbox to ``dest_path`` using SQLite's backup API.

        Safe to call while writers are active; the destination is a
        transactionally consistent point-in-time snapshot.
        """
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                with sqlite3.connect(str(dest)) as dst:
                    self._conn.backup(dst)
            except sqlite3.OperationalError:
                # Fallback for very old SQLite: serialized copy inside a txn.
                self._conn.execute("BEGIN")
                try:
                    with sqlite3.connect(str(dest)) as dst:
                        dst.executescript(_SCHEMA)
                        for tbl in ("jobs", "enrichment_jobs",
                                     "schema_meta"):
                            rows = self._conn.execute(
                                f"SELECT * FROM {tbl}",
                            ).fetchall()
                            cols = [d[0] for d in self._conn.execute(
                                f"SELECT * FROM {tbl} LIMIT 0").description]
                            placeholders = ",".join(["?"] * len(cols))
                            dst.executemany(
                                f"INSERT OR REPLACE INTO {tbl}"
                                f" VALUES({placeholders})",
                                [tuple(r[c] for c in cols) for r in rows],
                            )
                    self._conn.execute("COMMIT")
                except Exception:
                    self._conn.execute("ROLLBACK")
                    raise

    @classmethod
    def open_snapshot(cls, path: os.PathLike[str] | str | Path
                       ) -> "Outbox":
        """Open a snapshot as a read-only outbox.

        The snapshot is opened in read-only mode; attempts to enqueue or
        claim will raise ``sqlite3.OperationalError``.
        """
        instance = cls.__new__(cls)
        instance.path = Path(path)
        instance._clock = _now_default
        instance._lock = threading.RLock()
        uri = f"file:{instance.path}?mode=ro"
        instance._conn = sqlite3.connect(
            uri, uri=True,
            isolation_level=None,
            check_same_thread=False,
            timeout=30.0,
        )
        instance._conn.row_factory = sqlite3.Row
        instance._conn.executescript(_SCHEMA)
        return instance

    # -- internals --------------------------------------------------------

    @staticmethod
    def _backoff(attempts: int, base: float, cap: float, jitter: float,
                  now: float) -> float:
        # Exponential: base * 2^(attempts-1), clamped to cap.
        delay = min(cap, base * (2 ** max(0, attempts - 1)))
        if jitter > 0:
            import random
            # Symmetric jitter in [-jitter, +jitter] seconds.
            delta = (random.random() * 2.0 - 1.0) * jitter
            delay = max(0.0, delay + delta)
        return now + delay

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.ProgrammingError:
                pass


__all__ = [
    "Outbox",
    "Job",
    "TransportResult",
    "OutboxError",
    "DuplicateJobError",
    "StaleJobError",
    "SCHEMA_VERSION",
]
