import contextlib
import os
import sys

from tortoise import Tortoise, generate_schema_for_client
from tortoise.exceptions import DBConnectionError, OperationalError

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


async def drop_db(tortoise_orm) -> None:
    # Placing init outside the try-block(suppress) since it doesn't
    # establish connections to the DB eagerly.
    await Tortoise.init(config=tortoise_orm)
    with contextlib.suppress(DBConnectionError, OperationalError):
        await Tortoise._drop_databases()


async def init_db(tortoise_orm, generate_schemas=True) -> None:
    await drop_db(tortoise_orm)
    await Tortoise.init(config=tortoise_orm, _create_db=True)
    if generate_schemas:
        await generate_schema_for_client(Tortoise.get_connection("default"), safe=True)
