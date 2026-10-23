import os
import tempfile

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values

base_url = os.environ.get("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
assert base_url, "DATABASE_URL is not set"
test_url = base_url.rsplit("/", 1)[0] + "/audit_test"

os.environ["DATABASE_URL"] = test_url
os.environ["TEMP_UPLOAD_DIR"] = tempfile.mkdtemp(prefix="finaudit_test_")

command.upgrade(Config("alembic.ini"), "head")