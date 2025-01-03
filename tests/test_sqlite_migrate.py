import contextlib
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from aerich.ddl.sqlite import SqliteDDL
from aerich.migrate import Migrate

if sys.version_info >= (3, 11):
    from contextlib import chdir
else:

    class chdir(contextlib.AbstractContextManager):  # Copied from source code of Python3.13
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
    name = fields.CharField(max_length=60, db_index=False)
"""

SETTINGS = """from __future__ import annotations

TORTOISE_ORM = {
    "connections": {"default": "sqlite://db.sqlite3"},
    "apps": {"models": {"models": ["models", "aerich.models"]}},
}
"""

CONFTEST = """from __future__ import annotations

import asyncio
from typing import Generator

import pytest
import pytest_asyncio
from tortoise import Tortoise, connections

import settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    policy = asyncio.get_event_loop_policy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    res._close = res.close  # type:ignore[attr-defined]
    res.close = lambda: None  # type:ignore[method-assign]

    yield res

    res._close()  # type:ignore[attr-defined]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def api(event_loop, request):
    await Tortoise.init(config=settings.TORTOISE_ORM)
    request.addfinalizer(lambda: event_loop.run_until_complete(connections.close_all(discard=True)))
"""

TESTS = """from __future__ import annotations

import uuid

import pytest
from tortoise.exceptions import IntegrityError

from models import Foo


@pytest.mark.asyncio
async def test_allow_duplicate() -> None:
    await Foo.all().delete()
    await Foo.create(name="foo")
    obj = await Foo.create(name="foo")
    assert (await Foo.all().count()) == 2
    await obj.delete()


@pytest.mark.asyncio
async def test_unique_is_true() -> None:
    with pytest.raises(IntegrityError):
        await Foo.create(name="foo")


@pytest.mark.asyncio
async def test_add_unique_field() -> None:
    if not await Foo.filter(age=0).exists():
        await Foo.create(name="0_"+uuid.uuid4().hex, age=0)
    with pytest.raises(IntegrityError):
        await Foo.create(name=uuid.uuid4().hex, age=0)


@pytest.mark.asyncio
async def test_drop_unique_field() -> None:
    name = "1_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    assert (await Foo.filter(name=name).exists())


@pytest.mark.asyncio
async def test_with_age_field() -> None:
    name = "2_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    obj = await Foo.get(name=name)
    assert obj.age == 0


@pytest.mark.asyncio
async def test_without_age_field() -> None:
    name = "3_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    obj = await Foo.get(name=name)
    assert getattr(obj, "age", None) is None


@pytest.mark.asyncio
async def test_m2m_with_custom_through() -> None:
    from models import Group, FooGroup
    name = "4_" + uuid.uuid4().hex
    foo = await Foo.create(name=name)
    group = await Group.create(name=name+"1")
    await FooGroup.all().delete()
    await foo.groups.add(group)
    foo_group = await FooGroup.get(foo=foo, group=group)
    assert not foo_group.is_active


@pytest.mark.asyncio
async def test_add_m2m_field_after_init_db() -> None:
    from models import Group
    name = "5_" + uuid.uuid4().hex
    foo = await Foo.create(name=name)
    group = await Group.create(name=name+"1")
    await foo.groups.add(group)
    assert (await group.users.all().first()) == foo
"""


def run_aerich(cmd: str) -> None:
    with contextlib.suppress(subprocess.TimeoutExpired):
        if not cmd.startswith("aerich"):
            cmd = "aerich " + cmd
        subprocess.run(shlex.split(cmd), timeout=2)


def run_shell(cmd: str) -> subprocess.CompletedProcess:
    envs = dict(os.environ, PYTHONPATH=".")
    return subprocess.run(shlex.split(cmd), env=envs)


def test_sqlite_migrate(tmp_path: Path) -> None:
    if (ddl := getattr(Migrate, "ddl", None)) and not isinstance(ddl, SqliteDDL):
        return
    with chdir(tmp_path):
        models_py = Path("models.py")
        settings_py = Path("settings.py")
        test_py = Path("_test.py")
        models_py.write_text(MODELS)
        settings_py.write_text(SETTINGS)
        test_py.write_text(TESTS)
        Path("conftest.py").write_text(CONFTEST)
        if (db_file := Path("db.sqlite3")).exists():
            db_file.unlink()
        run_aerich("aerich init -t settings.TORTOISE_ORM")
        config_file = Path("pyproject.toml")
        modify_time = config_file.stat().st_mtime
        run_aerich("aerich init-db")
        run_aerich("aerich init -t settings.TORTOISE_ORM")
        assert modify_time == config_file.stat().st_mtime
        r = run_shell("pytest _test.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add index
        models_py.write_text(MODELS.replace("index=False", "index=True"))
        run_aerich("aerich migrate")  # migrations/models/1_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _test.py::test_allow_duplicate")
        assert r.returncode == 0
        # Drop index
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/2_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _test.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add unique index
        models_py.write_text(MODELS.replace("index=False", "index=True, unique=True"))
        run_aerich("aerich migrate")  # migrations/models/3_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _test.py::test_unique_is_true")
        assert r.returncode == 0
        # Drop unique index
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/4_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _test.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add field with unique=True
        with models_py.open("a") as f:
            f.write("    age = fields.IntField(unique=True, default=0)")
        run_aerich("aerich migrate")  # migrations/models/5_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _test.py::test_add_unique_field")
        assert r.returncode == 0
        # Drop unique field
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/6_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _test.py::test_drop_unique_field")
        assert r.returncode == 0

        # Initial with indexed field and then drop it
        migrations_dir = Path("migrations/models")
        shutil.rmtree(migrations_dir)
        db_file.unlink()
        models_py.write_text(MODELS + "    age = fields.IntField(db_index=True)")
        run_aerich("aerich init -t settings.TORTOISE_ORM")
        run_aerich("aerich init-db")
        migration_file = list(migrations_dir.glob("0_*.py"))[0]
        assert "CREATE INDEX" in migration_file.read_text()
        r = run_shell("pytest _test.py::test_with_age_field")
        assert r.returncode == 0
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")
        run_aerich("aerich upgrade")
        migration_file_1 = list(migrations_dir.glob("1_*.py"))[0]
        assert "DROP INDEX" in migration_file_1.read_text()
        r = run_shell("pytest _test.py::test_without_age_field")
        assert r.returncode == 0

        # Generate migration file in emptry directory
        db_file.unlink()
        run_aerich("aerich init-db")
        assert not db_file.exists()
        for p in migrations_dir.glob("*"):
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        run_aerich("aerich init-db")
        assert db_file.exists()

        # init without '[tool]' section in pyproject.toml
        config_file = Path("pyproject.toml")
        config_file.write_text('[project]\nname = "project"')
        run_aerich("init -t settings.TORTOISE_ORM")
        assert "[tool.aerich]" in config_file.read_text()

        # add m2m with custom model for through
        new = """
    groups = fields.ManyToManyField("models.Group", through="foo_group")

class Group(Model):
    name = fields.CharField(max_length=60)

class FooGroup(Model):
    foo = fields.ForeignKeyField("models.Foo")
    group = fields.ForeignKeyField("models.Group")
    is_active = fields.BooleanField(default=False)

    class Meta:
        table = "foo_group"
        """
        models_py.write_text(MODELS + new)
        run_aerich("aerich migrate")
        run_aerich("aerich upgrade")
        migration_file_1 = list(migrations_dir.glob("1_*.py"))[0]
        assert "foo_group" in migration_file_1.read_text()
        r = run_shell("pytest _test.py::test_m2m_with_custom_through")
        assert r.returncode == 0

        # add m2m field after init-db
        new = """
    groups = fields.ManyToManyField("models.Group", through="foo_group", related_name="users")

class Group(Model):
    name = fields.CharField(max_length=60)
        """
        if db_file.exists():
            db_file.unlink()
        if migrations_dir.exists():
            shutil.rmtree(migrations_dir)
        models_py.write_text(MODELS)
        run_aerich("aerich init-db")
        models_py.write_text(MODELS + new)
        run_aerich("aerich migrate")
        run_aerich("aerich upgrade")
        migration_file_1 = list(migrations_dir.glob("1_*.py"))[0]
        assert "foo_group" in migration_file_1.read_text()
        r = run_shell("pytest _test.py::test_add_m2m_field_after_init_db")
        assert r.returncode == 0
