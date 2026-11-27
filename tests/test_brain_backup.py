"""Tests for the encrypted Brain backup format and restore checks."""
import importlib.util
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("brain_backup", ROOT / "scripts" / "brain_backup.py")
assert spec and spec.loader
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_encrypt_decrypt_authenticated_roundtrip(tmp_path):
    key = os.urandom(32)
    source = tmp_path / "source.bin"
    encrypted = tmp_path / "source.brnbk"
    restored = tmp_path / "restored.bin"
    source.write_bytes(os.urandom(200_000))
    metadata = backup.encrypt(source, encrypted, key)
    backup.decrypt(encrypted, restored, key)
    assert restored.read_bytes() == source.read_bytes()
    assert metadata["plain_size"] == source.stat().st_size


def test_tampered_backup_is_rejected(tmp_path):
    key = os.urandom(32)
    source = tmp_path / "source.bin"
    encrypted = tmp_path / "source.brnbk"
    restored = tmp_path / "restored.bin"
    source.write_bytes(b"sqlite data")
    backup.encrypt(source, encrypted, key)
    damaged = bytearray(encrypted.read_bytes())
    damaged[30] ^= 1
    encrypted.write_bytes(damaged)
    try:
        backup.decrypt(encrypted, restored, key)
    except RuntimeError as exc:
        assert "authentication failed" in str(exc)
    else:
        raise AssertionError("tampered backup was accepted")


def test_sqlite_snapshot_and_restore_quick_check(tmp_path, monkeypatch):
    source = tmp_path / "db.sqlite3"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO items(value) VALUES('kept')")
    conn.commit(); conn.close()
    snapshot = tmp_path / "snapshot.sqlite3"
    encrypted = tmp_path / "snapshot.brnbk"
    key_path = tmp_path / "key"
    key_path.write_bytes(os.urandom(32))
    monkeypatch.setattr(backup, "KEY_FILE", key_path)
    backup.sqlite_snapshot(source, snapshot)
    backup.encrypt(snapshot, encrypted, key_path.read_bytes())
    result = backup.verify_restore(encrypted)
    assert result["quick_check"] == "ok"
    assert result["tables"] == 1


def test_binary_key_preserves_boundary_whitespace(tmp_path, monkeypatch):
    key = b' \t\n\r\v\f' + bytes(range(20, 40)) + b'\f\v\r\n\t '
    assert len(key) == 32
    key_path = tmp_path / 'key'
    key_path.write_bytes(key)
    monkeypatch.setattr(backup, 'KEY_FILE', key_path)
    assert backup._key() == key
    source = tmp_path / 'plain'
    source.write_bytes(b'boundary whitespace regression')
    backup.encrypt(source, tmp_path / 'encrypted', backup._key())
    backup.decrypt(tmp_path / 'encrypted', tmp_path / 'restored', backup._key())
    assert (tmp_path / 'restored').read_bytes() == source.read_bytes()


def test_binary_key_rejects_wrong_length(tmp_path, monkeypatch):
    import pytest
    key_path = tmp_path / 'key'
    monkeypatch.setattr(backup, 'KEY_FILE', key_path)
    for size in (31, 33):
        key_path.write_bytes(b'x' * size)
        with pytest.raises(RuntimeError, match='exactly 32 bytes'):
            backup._key()
