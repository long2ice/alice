import os
import shlex
import subprocess
import sys
from pathlib import Path

from aerich.ddl.sqlite import SqliteDDL
from aerich.migrate import Migrate

if sys.version_info >= (3, 11):
    from contextlib import chdir
else:
    from contextlib import AbstractContextManager

    class chdir(AbstractContextManager):  # Copied from source code of Python3.13
        """Non thread-safe context manager to change the current working directory."""

        def __init__(self, path):
            self.path = path
            self._old_cwd = []

        def __enter__(self):
            self._old_cwd.append(os.getcwd())
            os.chdir(self.path)

        def __exit__(self, *excinfo):
            os.chdir(self._old_cwd.pop())


MODELS = """from __future__ import annotations

from tortoise import Model, fields


class Foo(Model):
    name = fields.CharField(max_length=20, index=False, unique=False)
"""

SETTINGS = """from __future__ import annotations

TORTOISE_ORM = {
    "connections": {"default": "sqlite://db.sqlite3"},
    "apps": {"models": {"models": ["models", "aerich.models"]}},
}
"""


def test_sqlite_migrate(tmp_path: Path) -> None:
    if not isinstance(Migrate.ddl, SqliteDDL):
        return
    with chdir(tmp_path):
        models_py = tmp_path / "models.py"
        settings_py = tmp_path / "settings.py"
        models_py.write_text(MODELS)
        settings_py.write_text(SETTINGS)
        subprocess.run(shlex.split("aerich init -t settings.TORTOISE_ORM"))
        subprocess.run(shlex.split("aerich init-db"))
        models_py.write_text(MODELS.replace("index=False", "index=True"))
        r = subprocess.run(shlex.split("aerich migrate"))
        assert r.returncode == 0
        r = subprocess.run(shlex.split("aerich upgrade"))
        assert r.returncode == 0
        models_py.write_text(MODELS.replace("index=False, unique=False", "index=True, unique=True"))
        r = subprocess.run(shlex.split("aerich migrate"))
        assert r.returncode == 0
        r = subprocess.run(shlex.split("aerich upgrade"))
        assert r.returncode == 0
