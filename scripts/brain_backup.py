#!/usr/bin/env python3
"""Encrypted SQLite backups; destinations are configured by the operator."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SOURCES = tuple(Path(p) for p in os.environ.get("BRAIN_BACKUP_SOURCES", "hermes.sqlite3").split(os.pathsep))
KEY_FILE = Path(os.environ.get("BRAIN_BACKUP_KEY_FILE", "~/.config/brain/backup.key")).expanduser()
REMOTE = os.environ.get("BRAIN_BACKUP_REMOTE", "")
REMOTE_DIR = os.environ.get("BRAIN_BACKUP_REMOTE_DIR", "backups/brain")


def _key() -> bytes:
    raw = KEY_FILE.read_bytes()
    if len(raw) != 32:
        raise RuntimeError("brain-backup-key must contain exactly 32 bytes")
    return raw


def _keystream(key: bytes, nonce: bytes):
    counter = 0
    while True:
        block = hmac.new(key, b"brain-backup-v1\0" + nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        yield block
        counter += 1


def encrypt(source: Path, destination: Path, key: bytes) -> dict[str, object]:
    nonce = os.urandom(16)
    plain_hash = hashlib.sha256()
    cipher_hash = hashlib.sha256()
    mac = hmac.new(key, b"brain-backup-v1\0" + nonce, hashlib.sha256)
    size = 0
    stream = _keystream(key, nonce)
    with source.open("rb") as src, destination.open("wb") as dst:
        dst.write(b"BRNBK1\0" + nonce)
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            plain_hash.update(chunk)
            cipher = bytearray()
            offset = 0
            while offset < len(chunk):
                block = next(stream)
                take = min(len(block), len(chunk) - offset)
                cipher.extend(a ^ b for a, b in zip(chunk[offset:offset + take], block[:take]))
                offset += take
            mac.update(cipher)
            cipher_hash.update(cipher)
            dst.write(cipher)
        dst.write(mac.digest())
    return {
        "plain_size": size,
        "plain_sha256": plain_hash.hexdigest(),
        "cipher_sha256": cipher_hash.hexdigest(),
    }


def decrypt(source: Path, destination: Path, key: bytes) -> None:
    raw = source.read_bytes()
    if not raw.startswith(b"BRNBK1\0") or len(raw) < 55:
        raise RuntimeError("invalid encrypted backup")
    nonce = raw[7:23]
    cipher = raw[23:-32]
    expected = raw[-32:]
    mac = hmac.new(key, b"brain-backup-v1\0" + nonce, hashlib.sha256)
    mac.update(cipher)
    if not hmac.compare_digest(mac.digest(), expected):
        raise RuntimeError("backup authentication failed")
    stream = _keystream(key, nonce)
    plain = bytearray()
    offset = 0
    while offset < len(cipher):
        block = next(stream)
        take = min(len(block), len(cipher) - offset)
        plain.extend(a ^ b for a, b in zip(cipher[offset:offset + take], block[:take]))
        offset += take
    destination.write_bytes(plain)


def sqlite_snapshot(source: Path, destination: Path) -> None:
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def run_backup() -> dict[str, object]:
    key = _key()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not REMOTE:
        raise RuntimeError("BRAIN_BACKUP_REMOTE is required")
    uploaded = []
    with tempfile.TemporaryDirectory(prefix="brain-backup-") as tmp_raw:
        tmp = Path(tmp_raw)
        for source in SOURCES:
            if not source.exists():
                continue
            snapshot = tmp / source.name
            sqlite_snapshot(source, snapshot)
            encrypted = tmp / f"{source.name}.{stamp}.brnbk"
            metadata = encrypt(snapshot, encrypted, key)
            remote_file = f"{REMOTE_DIR}/{encrypted.name}"
            subprocess.run(["ssh", REMOTE, "mkdir", "-p", REMOTE_DIR], check=True)
            subprocess.run(["rsync", "-a", "--chmod=F600", str(encrypted), f"{REMOTE}:{remote_file}"], check=True)
            remote_sha = subprocess.check_output(["ssh", REMOTE, "sha256sum", remote_file], text=True).split()[0]
            local_sha = hashlib.sha256(encrypted.read_bytes()).hexdigest()
            if remote_sha != local_sha:
                raise RuntimeError("remote backup checksum mismatch")
            uploaded.append({"source": str(source), "remote": remote_file, **metadata, "encrypted_sha256": local_sha})
    manifest = {"schema": 1, "created_at": datetime.now(timezone.utc).isoformat(), "files": uploaded}
    manifest_path = Path(tempfile.mkstemp(prefix="brain-backup-manifest-", suffix=".json")[1])
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        subprocess.run(["rsync", "-a", "--chmod=F600", str(manifest_path), f"{REMOTE}:{REMOTE_DIR}/manifest-{stamp}.json"], check=True)
    finally:
        manifest_path.unlink(missing_ok=True)
    subprocess.run(["ssh", REMOTE, "bash", "-lc", f"'cd {REMOTE_DIR} && ls -1t *.brnbk 2>/dev/null | tail -n +15 | xargs -r rm -f'"], check=True)
    return manifest


def verify_restore(encrypted: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="brain-restore-") as tmp:
        restored = Path(tmp) / "restored.sqlite3"
        decrypt(encrypted, restored, _key())
        conn = sqlite3.connect(restored)
        try:
            check = conn.execute("PRAGMA quick_check").fetchone()[0]
            tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        finally:
            conn.close()
        return {"quick_check": check, "tables": tables, "size": restored.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run")
    verify = sub.add_parser("verify")
    verify.add_argument("file")
    args = parser.parse_args()
    result = run_backup() if args.command == "run" else verify_restore(Path(args.file))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
