import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Type

from tortoise import Tortoise, generate_schema_for_client
from tortoise.exceptions import OperationalError
from tortoise.transactions import in_transaction
from tortoise.utils import get_schema_sql

from aerich.exceptions import DowngradeError
from aerich.inspectdb.mysql import InspectMySQL
from aerich.inspectdb.postgres import InspectPostgres
from aerich.inspectdb.sqlite import InspectSQLite
from aerich.migrate import MIGRATE_TEMPLATE, Migrate
from aerich.models import Aerich
from aerich.utils import (
    get_app_connection,
    get_app_connection_name,
    get_models_describe,
    import_py_file,
)

if TYPE_CHECKING:
    from aerich.inspectdb import Inspect  # noqa:F401


class Command:
    def __init__(
        self,
        tortoise_config: dict,
        app: str = "models",
        location: str = "./migrations",
    ) -> None:
        self.tortoise_config = tortoise_config
        self.app = app
        self.location = location
        Migrate.app = app

    async def init(self) -> None:
        await Migrate.init(self.tortoise_config, self.app, self.location)

    async def _upgrade(self, conn, version_file) -> None:
        file_path = Path(Migrate.migrate_location, version_file)
        m = import_py_file(file_path)
        upgrade = getattr(m, "upgrade")
        await conn.execute_script(await upgrade(conn))
        await Aerich.create(
            version=version_file,
            app=self.app,
            content=get_models_describe(self.app),
        )

    async def upgrade(self, run_in_transaction: bool = True) -> List[str]:
        migrated = []
        for version_file in Migrate.get_all_version_files():
            try:
                exists = await Aerich.exists(version=version_file, app=self.app)
            except OperationalError:
                exists = False
            if not exists:
                app_conn_name = get_app_connection_name(self.tortoise_config, self.app)
                if run_in_transaction:
                    async with in_transaction(app_conn_name) as conn:
                        await self._upgrade(conn, version_file)
                else:
                    app_conn = get_app_connection(self.tortoise_config, self.app)
                    await self._upgrade(app_conn, version_file)
                migrated.append(version_file)
        return migrated

    async def downgrade(self, version: int, delete: bool) -> List[str]:
        ret: List[str] = []
        if version == -1:
            specified_version = await Migrate.get_last_version()
        else:
            specified_version = await Aerich.filter(
                app=self.app, version__startswith=f"{version}_"
            ).first()
        if not specified_version:
            raise DowngradeError("No specified version found")
        if version == -1:
            versions = [specified_version]
        else:
            versions = await Aerich.filter(app=self.app, pk__gte=specified_version.pk)
        for version_obj in versions:
            file = version_obj.version
            async with in_transaction(
                get_app_connection_name(self.tortoise_config, self.app)
            ) as conn:
                file_path = Path(Migrate.migrate_location, file)
                m = import_py_file(file_path)
                downgrade = getattr(m, "downgrade")
                downgrade_sql = await downgrade(conn)
                if not downgrade_sql.strip():
                    raise DowngradeError("No downgrade items found")
                await conn.execute_script(downgrade_sql)
                await version_obj.delete()
                if delete:
                    os.unlink(file_path)
                ret.append(file)
        return ret

    async def heads(self) -> List[str]:
        ret = []
        versions = Migrate.get_all_version_files()
        for version in versions:
            if not await Aerich.exists(version=version, app=self.app):
                ret.append(version)
        return ret

    async def history(self) -> List[str]:
        versions = Migrate.get_all_version_files()
        return [version for version in versions]

    async def inspectdb(self, tables: Optional[List[str]] = None) -> str:
        connection = get_app_connection(self.tortoise_config, self.app)
        dialect = connection.schema_generator.DIALECT
        if dialect == "mysql":
            cls: Type["Inspect"] = InspectMySQL
        elif dialect == "postgres":
            cls = InspectPostgres
        elif dialect == "sqlite":
            cls = InspectSQLite
        else:
            raise NotImplementedError(f"{dialect} is not supported")
        inspect = cls(connection, tables)
        return await inspect.inspect()

    async def migrate(self, name: str = "update", empty: bool = False) -> str:
        return await Migrate.migrate(name, empty)

    async def init_db(self, safe: bool) -> None:
        location = self.location
        app = self.app
        dirname = Path(location, app)
        dirname.mkdir(parents=True)

        await Tortoise.init(config=self.tortoise_config)
        connection = get_app_connection(self.tortoise_config, app)
        await generate_schema_for_client(connection, safe)

        schema = get_schema_sql(connection, safe)

        version = await Migrate.generate_version()
        await Aerich.create(
            version=version,
            app=app,
            content=get_models_describe(app),
        )
        version_file = Path(dirname, version)
        content = MIGRATE_TEMPLATE.format(upgrade_sql=schema, downgrade_sql="")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(content)
