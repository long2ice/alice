import asyncio
import os
import sys
from configparser import ConfigParser
from functools import wraps
from pathlib import Path
from typing import List

import click
from click import Context, UsageError
from tortoise import Tortoise, generate_schema_for_client
from tortoise.exceptions import OperationalError
from tortoise.transactions import in_transaction
from tortoise.utils import get_schema_sql

from aerich.inspectdb import InspectDb
from aerich.migrate import Migrate
from aerich.utils import (
    get_app_connection,
    get_app_connection_name,
    get_models_describe,
    get_tortoise_config,
    get_version_content_from_file,
    write_version_file,
)

from . import __version__
from .enums import Color
from .models import Aerich

parser = ConfigParser()


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()

        # Close db connections at the end of all all but the cli group function
        try:
            loop.run_until_complete(f(*args, **kwargs))
        finally:
            if f.__name__ != "cli":
                loop.run_until_complete(Tortoise.close_connections())

    return wrapper


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.option(
    "-c",
    "--config",
    default="aerich.ini",
    show_default=True,
    help="Config file.",
)
@click.option("--app", required=False, help="Tortoise-ORM app name.")
@click.option(
    "-n",
    "--name",
    default="aerich",
    show_default=True,
    help="Name of section in .ini file to use for aerich config.",
)
@click.pass_context
@coro
async def cli(ctx: Context, config, app, name):
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config
    ctx.obj["name"] = name

    invoked_subcommand = ctx.invoked_subcommand
    if invoked_subcommand != "init":
        if not Path(config).exists():
            raise UsageError("You must exec init first", ctx=ctx)
        parser.read(config)

        location = parser[name]["location"]
        tortoise_orm = parser[name]["tortoise_orm"]

        tortoise_config = get_tortoise_config(ctx, tortoise_orm)
        app = app or list(tortoise_config.get("apps").keys())[0]
        ctx.obj["config"] = tortoise_config
        ctx.obj["location"] = location
        ctx.obj["app"] = app
        Migrate.app = app
        if invoked_subcommand != "init-db":
            if not Path(location, app).exists():
                raise UsageError("You must exec init-db first", ctx=ctx)
            await Migrate.init(tortoise_config, app, location)


@cli.command(help="Generate migrate changes file.")
@click.option("--name", default="update", show_default=True, help="Migrate name.")
@click.pass_context
@coro
async def migrate(ctx: Context, name):
    ret = await Migrate.migrate(name)
    if not ret:
        return click.secho("No changes detected", fg=Color.yellow)
    click.secho(f"Success migrate {ret}", fg=Color.green)


@cli.command(help="Upgrade to specified version.")
@click.pass_context
@coro
async def upgrade(ctx: Context):
    config = ctx.obj["config"]
    app = ctx.obj["app"]
    migrated = False
    for version_file in Migrate.get_all_version_files():
        try:
            exists = await Aerich.exists(version=version_file, app=app)
        except OperationalError:
            exists = False
        if not exists:
            async with in_transaction(get_app_connection_name(config, app)) as conn:
                file_path = Path(Migrate.migrate_location, version_file)
                content = get_version_content_from_file(file_path)
                upgrade_query_list = content.get("upgrade")
                for upgrade_query in upgrade_query_list:
                    await conn.execute_script(upgrade_query)
                await Aerich.create(
                    version=version_file,
                    app=app,
                    content=get_models_describe(app),
                )
            click.secho(f"Success upgrade {version_file}", fg=Color.green)
            migrated = True
    if not migrated:
        click.secho("No upgrade items found", fg=Color.yellow)


@cli.command(help="Downgrade to specified version.")
@click.option(
    "-v",
    "--version",
    default=-1,
    type=int,
    show_default=True,
    help="Specified version, default to last.",
)
@click.option(
    "-d",
    "--delete",
    is_flag=True,
    default=False,
    show_default=True,
    help="Delete version files at the same time.",
)
@click.pass_context
@click.confirmation_option(
    prompt="Downgrade is dangerous, which maybe lose your data, are you sure?",
)
@coro
async def downgrade(ctx: Context, version: int, delete: bool):
    app = ctx.obj["app"]
    config = ctx.obj["config"]
    if version == -1:
        specified_version = await Migrate.get_last_version()
    else:
        specified_version = await Aerich.filter(app=app, version__startswith=f"{version}_").first()
    if not specified_version:
        return click.secho("No specified version found", fg=Color.yellow)
    if version == -1:
        versions = [specified_version]
    else:
        versions = await Aerich.filter(app=app, pk__gte=specified_version.pk)
    for version in versions:
        file = version.version
        async with in_transaction(get_app_connection_name(config, app)) as conn:
            file_path = Path(Migrate.migrate_location, file)
            content = get_version_content_from_file(file_path)
            downgrade_query_list = content.get("downgrade")
            if not downgrade_query_list:
                click.secho("No downgrade items found", fg=Color.yellow)
                return
            for downgrade_query in downgrade_query_list:
                await conn.execute_query(downgrade_query)
            await version.delete()
            if delete:
                os.unlink(file_path)
            click.secho(f"Success downgrade {file}", fg=Color.green)


@cli.command(help="Show current available heads in migrate location.")
@click.pass_context
@coro
async def heads(ctx: Context):
    app = ctx.obj["app"]
    versions = Migrate.get_all_version_files()
    is_heads = False
    for version in versions:
        if not await Aerich.exists(version=version, app=app):
            click.secho(version, fg=Color.green)
            is_heads = True
    if not is_heads:
        click.secho("No available heads,try migrate first", fg=Color.green)


@cli.command(help="List all migrate items.")
@click.pass_context
@coro
async def history(ctx: Context):
    versions = Migrate.get_all_version_files()
    for version in versions:
        click.secho(version, fg=Color.green)
    if not versions:
        click.secho("No history,try migrate", fg=Color.green)


@cli.command(help="Init config file and generate root migrate location.")
@click.option(
    "-t",
    "--tortoise-orm",
    required=True,
    help="Tortoise-ORM config module dict variable, like settings.TORTOISE_ORM.",
)
@click.option(
    "--location",
    default="./migrations",
    show_default=True,
    help="Migrate store location.",
)
@click.pass_context
@coro
async def init(
    ctx: Context,
    tortoise_orm,
    location,
):
    config_file = ctx.obj["config_file"]
    name = ctx.obj["name"]
    if Path(config_file).exists():
        return click.secho("You have inited", fg=Color.yellow)

    parser.add_section(name)
    parser.set(name, "tortoise_orm", tortoise_orm)
    parser.set(name, "location", location)

    with open(config_file, "w", encoding="utf-8") as f:
        parser.write(f)

    Path(location).mkdir(parents=True, exist_ok=True)

    click.secho(f"Success create migrate location {location}", fg=Color.green)
    click.secho(f"Success generate config file {config_file}", fg=Color.green)


@cli.command(help="Generate schema and generate app migrate location.")
@click.option(
    "--safe",
    type=bool,
    default=True,
    help="When set to true, creates the table only when it does not already exist.",
    show_default=True,
)
@click.pass_context
@coro
async def init_db(ctx: Context, safe):
    config = ctx.obj["config"]
    location = ctx.obj["location"]
    app = ctx.obj["app"]

    dirname = Path(location, app)
    try:
        dirname.mkdir(parents=True)
        click.secho(f"Success create app migrate location {dirname}", fg=Color.green)
    except FileExistsError:
        return click.secho(
            f"Inited {app} already, or delete {dirname} and try again.", fg=Color.yellow
        )

    await Tortoise.init(config=config)
    connection = get_app_connection(config, app)
    await generate_schema_for_client(connection, safe)

    schema = get_schema_sql(connection, safe)

    version = await Migrate.generate_version()
    await Aerich.create(
        version=version,
        app=app,
        content=get_models_describe(app),
    )
    content = {
        "upgrade": [schema],
    }
    write_version_file(Path(dirname, version), content)
    click.secho(f'Success generate schema for app "{app}"', fg=Color.green)


@cli.command(help="Introspects the database tables to standard output as TortoiseORM model.")
@click.option(
    "-t",
    "--table",
    help="Which tables to inspect.",
    multiple=True,
    required=False,
)
@click.pass_context
@coro
async def inspectdb(ctx: Context, table: List[str]):
    config = ctx.obj["config"]
    app = ctx.obj["app"]
    connection = get_app_connection(config, app)

    inspect = InspectDb(connection, table)
    await inspect.inspect()


def main():
    sys.path.insert(0, ".")
    cli()


if __name__ == "__main__":
    main()
