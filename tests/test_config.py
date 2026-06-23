from app.core import config


def test_secret_file_precedence(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("HERMES_API_KEY", "from-env")
    monkeypatch.setenv("HERMES_API_KEY_FILE", str(secret_file))
    assert config._secret("HERMES_API_KEY") == "from-file"
