"""Recover already captured context from local durable outboxes.

Default is a read-only audit. --apply appends new event revisions only when
both the event identity and original client digest match a server receipt.
It preserves the original event revisions and every outbox receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .event_store import EventStore, SensitiveRejectedError, StaticPrincipalAdapter
from .proposal_protocol_v2 import EventCapture


def backfill(db_path: Path, outboxes: list[Path], *, apply: bool = False) -> dict[str, int]:
    counts = dict(candidates=0, applied=0, already_present=0, unmatched=0, invalid=0, sensitive=0)
    stores: dict[tuple[str, str, str], EventStore] = {}
    server = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    server.row_factory = sqlite3.Row
    columns = {r[1] for r in server.execute("PRAGMA table_info(source_events)")}
    select_columns = "*" if "capture" in columns else "*, '{}' AS capture"
    try:
        for path in outboxes:
            local = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                for (raw,) in local.execute("SELECT payload_json FROM jobs WHERE kind='execution'"):
                    try:
                        payload = json.loads(raw)
                        capture = payload.get("capture")
                        if not capture:
                            continue
                        context = EventCapture.model_validate(capture).model_dump(exclude_unset=True)
                        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                                          ensure_ascii=False, allow_nan=False).encode()).hexdigest()
                    except (TypeError, ValueError, ValidationError):
                        counts["invalid"] += 1
                        continue
                    row = server.execute(f"SELECT {select_columns} FROM source_events WHERE id=? ORDER BY version DESC LIMIT 1", (payload.get("id"),)).fetchone()
                    if row is None or row["client_digest"] != digest or row["principal_project"] != payload.get("project_id"):
                        counts["unmatched"] += 1
                        continue
                    if row["capture"] != "{}":
                        counts["already_present"] += 1
                        continue
                    counts["candidates"] += 1
                    if not apply:
                        continue
                    scope = (row["principal_actor"], row["principal_workspace"], row["principal_project"])
                    store = stores.get(scope)
                    if store is None:
                        store = EventStore(db_path, principal=StaticPrincipalAdapter(actor=scope[0], workspace=scope[1], project=scope[2]))
                        stores[scope] = store
                    try:
                        result = store.record_event(
                            id=row["id"], project_id=row["project_id"], agent_id=row["agent_id"],
                            occurred_at=datetime.fromisoformat(row["occurred_at"]),
                            action=row["action"], result=row["result"], source_refs=json.loads(row["source_refs"]),
                            origin=row["origin"], classification=row["classification"],
                            client_digest=digest, capture=context, expected_version=row["version"],
                        )
                        counts["applied"] += result["status"] == "recorded"
                    except SensitiveRejectedError:
                        counts["sensitive"] += 1
            finally:
                local.close()
    finally:
        server.close()
        for store in stores.values():
            store.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(backfill(args.db, args.outbox, apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
