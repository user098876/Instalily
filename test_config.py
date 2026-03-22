from app.config import Settings


def test_cors_origins_supports_comma_separated_values():
    settings = Settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_supports_json_array_values():
    settings = Settings(cors_origins='["http://localhost:5173", "http://127.0.0.1:5173"]')

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_database_url_normalizes_legacy_postgres_scheme():
    settings = Settings(database_url="postgresql://postgres:postgres@localhost:5433/instalily")

    assert settings.database_url == "postgresql+psycopg://postgres:postgres@localhost:5433/instalily"
