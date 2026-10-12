import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_database_url_is_required_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_url_can_be_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_url = "postgresql+psycopg://test:test@localhost:5432/test"
    monkeypatch.setenv("DATABASE_URL", expected_url)

    assert Settings(_env_file=None).database_url == expected_url


def test_application_settings_fail_with_clear_message_when_url_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        get_settings()

    get_settings.cache_clear()
