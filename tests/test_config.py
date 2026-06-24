from alembic.config import Config
from app.core import config


def test_secret_file_precedence(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("HERMES_API_KEY", "from-env")
    monkeypatch.setenv("HERMES_API_KEY_FILE", str(secret_file))
    assert config._secret("HERMES_API_KEY") == "from-file"


def test_alembic_config_value_escapes_percent_interpolation():
    raw_url = "mysql+pymysql://user:p%40ss@host/db?ssl_ca=/mnt/certs%2Fca.pem"
    alembic_config = Config()

    alembic_config.set_main_option(
        "sqlalchemy.url",
        config.escape_configparser_value(raw_url),
    )

    assert alembic_config.get_main_option("sqlalchemy.url") == raw_url
