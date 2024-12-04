from aerich.utils import import_py_file


def test_import_py_file() -> None:
    m = import_py_file("aerich/utils.py")
    assert getattr(m, "import_py_file")
