from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import main as db
from app.internal import was
from app.internal.migration import LEGACY_BACKUP_SUFFIX, backup_legacy_file


class FailingSession:
    def __init__(self):
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def add(self, record):
        pass

    def commit(self):
        raise IntegrityError("statement", {}, RuntimeError("migration failed"))

    def rollback(self):
        self.rolled_back = True


def test_backup_legacy_file_preserves_original(tmp_path):
    source_path = tmp_path / "user_config.json"
    source_path.write_text('{"original": true}')

    backup_path = backup_legacy_file(source_path)

    assert backup_path == Path(f"{source_path}{LEGACY_BACKUP_SUFFIX}")
    assert backup_path.read_text() == source_path.read_text()


def test_backup_legacy_file_does_not_overwrite_existing_backup(tmp_path):
    source_path = tmp_path / "user_config.json"
    source_path.write_text('{"original": true}')
    backup_path = backup_legacy_file(source_path)
    source_path.write_text('{"updated": true}')

    assert backup_legacy_file(source_path) is None
    assert backup_path.read_text() == '{"original": true}'


def test_backup_legacy_file_ignores_missing_source(tmp_path):
    assert backup_legacy_file(tmp_path / "missing.json") is None


def test_get_devices_does_not_create_missing_legacy_file(tmp_path, monkeypatch):
    source_path = tmp_path / "user_client_config.json"
    monkeypatch.setattr(was, "STORAGE_USER_CLIENT_CONFIG", str(source_path))

    assert was.get_devices() == []
    assert source_path.exists() is False


def test_get_devices_rejects_invalid_legacy_file(tmp_path, monkeypatch):
    source_path = tmp_path / "user_client_config.json"
    source_path.write_text("{}")
    monkeypatch.setattr(was, "STORAGE_USER_CLIENT_CONFIG", str(source_path))

    with pytest.raises(ValueError, match="is not a list"):
        was.get_devices()


@pytest.mark.parametrize(
    ("migrate", "content"),
    [
        (db.migrate_user_config, {"aec": True}),
        (
            db.migrate_user_nvs,
            {
                "WAS": {"URL": "http://was.example/ws"},
                "WIFI": {"PSK": "secret", "SSID": "willow"},
            },
        ),
        (
            db.migrate_user_client_config,
            [{"label": "Kitchen", "mac_addr": "00:11:22:33:44:55"}],
        ),
    ],
)
def test_failed_database_migration_is_reported(monkeypatch, migrate, content):
    session = FailingSession()
    monkeypatch.setattr(db, "Session", lambda engine: session)

    with pytest.raises(IntegrityError):
        migrate(content)

    assert session.rolled_back is True
