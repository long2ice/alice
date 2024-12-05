checkfiles = aerich/ tests/ conftest.py
black_opts = -l 100 -t py38
py_warn = PYTHONDEVMODE=1
MYSQL_HOST ?= "127.0.0.1"
MYSQL_PORT ?= 3306
MYSQL_PASS ?= "123456"
POSTGRES_HOST ?= "127.0.0.1"
POSTGRES_PORT ?= 5432
POSTGRES_PASS ?= "123456"

up:
	@poetry update

deps:
	@poetry install -E asyncpg -E asyncmy

_style:
	@isort -src $(checkfiles)
	@black $(black_opts) $(checkfiles)
style: deps _style

_check:
	@black --check $(black_opts) $(checkfiles) || (echo "Please run 'make style' to auto-fix style issues" && false)
	@ruff check $(checkfiles)
	@mypy $(checkfiles)
ifneq ($(shell python -c 'import sys;is_py38=sys.version_info<(3,9);rc=int(is_py38);sys.exit(rc)'),)
	# Run bandit with Python3.9+, as the `usedforsecurity=...` parameter of `hashlib.new` is only added from Python 3.9 onwards.
	@bandit -r aerich
endif
check: deps _check

test: deps
	$(py_warn) TEST_DB=sqlite://:memory: py.test

test_sqlite:
	$(py_warn) TEST_DB=sqlite://:memory: py.test

test_mysql:
	$(py_warn) TEST_DB="mysql://root:$(MYSQL_PASS)@$(MYSQL_HOST):$(MYSQL_PORT)/test_\{\}" pytest -vv -s

test_postgres:
	$(py_warn) TEST_DB="postgres://postgres:$(POSTGRES_PASS)@$(POSTGRES_HOST):$(POSTGRES_PORT)/test_\{\}" pytest -vv -s

_testall: test_sqlite test_postgres test_mysql
testall: deps _testall

build: deps
	@poetry build

ci: check _testall
