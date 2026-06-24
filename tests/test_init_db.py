from app.init_db import init_db


def test_init_db_compatibility_hook_is_noop():
    assert init_db() is None
