import pytest
from pydantic import ValidationError

from app.core.config import PROJECT_ROOT, Settings
from app.main import app


def test_settings_load_values_from_project_env_example() -> None:
    settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.database_url == "sqlite:///./qualbot.db"
    assert str(settings.frontend_api_base_url).rstrip("/") == "http://localhost:8000/api/v1"
    assert [str(origin).rstrip("/") for origin in settings.cors_origins] == [
        "http://localhost:5173"
    ]
    assert app.openapi_url == f"{settings.api_prefix}/openapi.json"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("QUALBOT_ENV", "staging"),
        ("QUALBOT_API_PREFIX", "api/v1"),
        ("QUALBOT_DATABASE_URL", "mysql://db.example/qualbot"),
        ("QUALBOT_CORS_ORIGINS", "not-a-url"),
    ],
)
def test_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_accept_comma_separated_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUALBOT_CORS_ORIGINS", "https://example.com, http://localhost:5173")

    settings = Settings(_env_file=None)

    assert [str(origin).rstrip("/") for origin in settings.cors_origins] == [
        "https://example.com",
        "http://localhost:5173",
    ]
