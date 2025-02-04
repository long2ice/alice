from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from aerich.ddl.sqlite import SqliteDDL
from aerich.migrate import Migrate
from tests._utils import chdir, copy_files


def run_shell(command: str, capture_output=True, **kw) -> str:
    r = subprocess.run(shlex.split(command), capture_output=capture_output)
    if r.returncode != 0 and r.stderr:
        return r.stderr.decode()
    if not r.stdout:
        return ""
    return r.stdout.decode()


@pytest.fixture
def new_aerich_project(tmp_path: Path):
    test_dir = Path(__file__).parent
    asset_dir = test_dir / "assets" / "fake"
    settings_py = asset_dir / "settings.py"
    _tests_py = asset_dir / "_tests.py"
    db_py = asset_dir / "db.py"
    models_py = test_dir / "models.py"
    models_second_py = test_dir / "models_second.py"
    copy_files(settings_py, _tests_py, models_py, models_second_py, db_py, target_dir=tmp_path)
    dst_dir = tmp_path / "tests"
    dst_dir.mkdir()
    dst_dir.joinpath("__init__.py").touch()
    copy_files(test_dir / "_utils.py", test_dir / "indexes.py", target_dir=dst_dir)
    if should_remove := str(tmp_path) not in sys.path:
        sys.path.append(str(tmp_path))
    with chdir(tmp_path):
        run_shell("python db.py create", capture_output=False)
        try:
            yield
        finally:
            if not os.getenv("AERICH_DONT_DROP_FAKE_DB"):
                run_shell("python db.py drop", capture_output=False)
            if should_remove:
                sys.path.remove(str(tmp_path))


def _append_field(*files: str, name="field_1") -> None:
    for file in files:
        p = Path(file)
        field = f"    {name} = fields.IntField(default=0)"
        with p.open("a") as f:
            f.write(os.linesep + field)


def test_fake(new_aerich_project):
    if (ddl := getattr(Migrate, "ddl", None)) and isinstance(ddl, SqliteDDL):
        # TODO: go ahead if sqlite alter-column supported
        return
    output = run_shell("aerich init -t settings.TORTOISE_ORM")
    assert "Success" in output
    output = run_shell("aerich init-db")
    assert "Success" in output
    output = run_shell("aerich --app models_second init-db")
    assert "Success" in output
    output = run_shell("pytest _tests.py::test_init_db")
    assert "error" not in output.lower()
    _append_field("models.py", "models_second.py")
    output = run_shell("aerich migrate")
    assert "Success" in output
    output = run_shell("aerich --app models_second migrate")
    assert "Success" in output
    output = run_shell("aerich upgrade --fake")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second upgrade --fake")
    assert "FAKED" in output
    output = run_shell("pytest _tests.py::test_fake_field_1")
    assert "error" not in output.lower()
    _append_field("models.py", "models_second.py", name="field_2")
    output = run_shell("aerich migrate")
    assert "Success" in output
    output = run_shell("aerich --app models_second migrate")
    assert "Success" in output
    output = run_shell("aerich heads")
    assert "_update.py" in output
    output = run_shell("aerich upgrade --fake")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second upgrade --fake")
    assert "FAKED" in output
    output = run_shell("pytest _tests.py::test_fake_field_2")
    assert "error" not in output.lower()
    output = run_shell("aerich heads")
    assert "No available heads." in output
    output = run_shell("aerich --app models_second heads")
    assert "No available heads." in output
    _append_field("models.py", "models_second.py", name="field_3")
    run_shell("aerich migrate", capture_output=False)
    run_shell("aerich --app models_second migrate", capture_output=False)
    run_shell("aerich upgrade --fake", capture_output=False)
    run_shell("aerich --app models_second upgrade --fake", capture_output=False)
    output = run_shell("aerich downgrade --fake -v 2 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second downgrade --fake -v 2 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich heads")
    assert "No available heads." not in output
    assert not re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
    output = run_shell("aerich --app models_second heads")
    assert "No available heads." not in output
    assert not re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
    output = run_shell("aerich downgrade --fake -v 1 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second downgrade --fake -v 1 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich heads")
    assert "No available heads." not in output
    assert re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
    output = run_shell("aerich --app models_second heads")
    assert "No available heads." not in output
    assert re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
    output = run_shell("aerich upgrade --fake")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second upgrade --fake")
    assert "FAKED" in output
    output = run_shell("aerich heads")
    assert "No available heads." in output
    output = run_shell("aerich --app models_second heads")
    assert "No available heads." in output
    output = run_shell("aerich downgrade --fake -v 1 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich --app models_second downgrade --fake -v 1 --yes", input="y\n")
    assert "FAKED" in output
    output = run_shell("aerich heads")
    assert "No available heads." not in output
    assert re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
    output = run_shell("aerich --app models_second heads")
    assert "No available heads." not in output
    assert re.search(r"1_\d+_update\.py", output)
    assert re.search(r"2_\d+_update\.py", output)
