from app.main import app


def test_application_metadata_is_available() -> None:
    openapi = app.openapi()

    assert openapi["info"]["title"] == "QualBot API"
    assert openapi["info"]["version"] == "0.1.0"
