import contextlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from aerich.ddl.sqlite import SqliteDDL
from aerich.migrate import Migrate
from tests._utils import chdir, copy_files


def run_aerich(cmd: str) -> None:
    with contextlib.suppress(subprocess.TimeoutExpired):
        if not cmd.startswith("aerich") and not cmd.startswith("poetry"):
            cmd = "aerich " + cmd
        subprocess.run(shlex.split(cmd), timeout=2)


def run_shell(cmd: str) -> subprocess.CompletedProcess:
    envs = dict(os.environ, PYTHONPATH=".")
    return subprocess.run(shlex.split(cmd), env=envs)


def test_sqlite_migrate(tmp_path: Path) -> None:
    if (ddl := getattr(Migrate, "ddl", None)) and not isinstance(ddl, SqliteDDL):
        return
    test_dir = Path(__file__).parent
    asset_dir = test_dir / "assets" / "sqlite_migrate"
    with chdir(tmp_path):
        files = ("models.py", "settings.py", "_tests.py")
        copy_files(*(asset_dir / f for f in files), target_dir=Path())
        models_py, settings_py, test_py = (Path(f) for f in files)
        copy_files(asset_dir / "conftest_.py", target_dir=Path("conftest.py"))
        if (db_file := Path("db.sqlite3")).exists():
            db_file.unlink()
        MODELS = models_py.read_text("utf-8")
        run_aerich("aerich init -t settings.TORTOISE_ORM")
        config_file = Path("pyproject.toml")
        modify_time = config_file.stat().st_mtime
        run_aerich("aerich init-db")
        run_aerich("aerich init -t settings.TORTOISE_ORM")
        assert modify_time == config_file.stat().st_mtime
        r = run_shell("pytest _tests.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add index
        models_py.write_text(MODELS.replace("index=False", "index=True"))
        run_aerich("aerich migrate")  # migrations/models/1_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _tests.py::test_allow_duplicate")
        assert r.returncode == 0
        # Drop index
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/2_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _tests.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add unique index
        models_py.write_text(MODELS.replace("index=False", "index=True, unique=True"))
        run_aerich("aerich migrate")  # migrations/models/3_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _tests.py::test_unique_is_true")
        assert r.returncode == 0
        # Drop unique index
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/4_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _tests.py::test_allow_duplicate")
        assert r.returncode == 0
        # Add field with unique=True
        with models_py.open("a") as f:
            f.write("    age = fields.IntField(unique=True, default=0)")
        run_aerich("aerich migrate")  # migrations/models/5_
        run_aerich("aerich upgrade")
        r = run_shell("pytest _tests.py::test_add_unique_field")
        assert r.returncode == 0
        # Drop unique field
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")  # migrations/models/6_
        run_aerich("aerich upgrade")
        r = run_shell("pytest -s _tests.py::test_drop_unique_field")
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
        r = run_shell("pytest _tests.py::test_with_age_field")
        assert r.returncode == 0
        models_py.write_text(MODELS)
        run_aerich("aerich migrate")
        run_aerich("aerich upgrade")
        migration_file_1 = list(migrations_dir.glob("1_*.py"))[0]
        assert "DROP INDEX" in migration_file_1.read_text()
        r = run_shell("pytest _tests.py::test_without_age_field")
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
        r = run_shell("pytest _tests.py::test_m2m_with_custom_through")
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
        r = run_shell("pytest _tests.py::test_add_m2m_field_after_init_db")
        assert r.returncode == 0
