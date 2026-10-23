from sqlalchemy import text

from app.db.session import get_engine


def test_tests_use_test_database():
    with get_engine().connect() as connection:
        name = connection.execute(text("SELECT current_database()")).scalar()
    assert name == "audit_test"