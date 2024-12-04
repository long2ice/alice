import os
from pathlib import Path
from typing import Dict, List, cast

import asyncclick as click
import tomlkit
from asyncclick import Context, UsageError
from tomlkit.exceptions import NonExistentKey

from aerich import Command
from aerich.enums import Color
from aerich.exceptions import DowngradeError
from aerich.utils import add_src_path, get_tortoise_config
from aerich.version import __version__

CONFIG_DEFAULT_VALUES = {
    "src_folder": ".",
}


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.option(
    "-c",
    "--config",
    default="pyproject.toml",
    show_default=True,
    help="Config file.",
)
@click.option("--app", required=False, help="Tortoise-ORM app name.")
@click.pass_context
async def cli(ctx: Context, config, app) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config

    invoked_subcommand = ctx.invoked_subcommand
    if invoked_subcommand != "init":
        config_path = Path(config)
        if not config_path.exists():
            raise UsageError(
                "You need to run `aerich init` first to create the config file.", ctx=ctx
            )
        content = config_path.read_text()
        doc: dict = tomlkit.parse(content)
        try:
            tool = cast(Dict[str, str], doc["tool"]["aerich"])
            location = tool["location"]
            tortoise_orm = tool["tortoise_orm"]
            src_folder = tool.get("src_folder", CONFIG_DEFAULT_VALUES["src_folder"])
        except NonExistentKey:
            raise UsageError("You need run `aerich init` again when upgrading to aerich 0.6.0+.")
        add_src_path(src_folder)
        tortoise_config = get_tortoise_config(ctx, tortoise_orm)
        if not app:
            apps_config = cast(dict, tortoise_config.get("apps"))
            app = list(apps_config.keys())[0]
        command = Command(tortoise_config=tortoise_config, app=app, location=location)
        ctx.obj["command"] = command
        if invoked_subcommand != "init-db":
            if not Path(location, app).exists():
                raise UsageError(
                    "You need to run `aerich init-db` first to initialize the database.", ctx=ctx
                )
            await command.init()


@cli.command(help="Generate a migration file for the current state of the models.")
@click.option("--name", default="update", show_default=True, help="Migration name.")
@click.option("--empty", default=False, is_flag=True, help="Generate an empty migration file.")
@click.pass_context
async def migrate(ctx: Context, name, empty) -> None:
    command = ctx.obj["command"]
    ret = await command.migrate(name, empty)
    if not ret:
        return click.secho("No changes detected", fg=Color.yellow)
    click.secho(f"Success creating migration file {ret}", fg=Color.green)


@cli.command(help="Upgrade to specified migration version.")
@click.option(
    "--in-transaction",
    "-i",
    default=True,
    type=bool,
    help="Make migrations in a single transaction or not. Can be helpful for large migrations or creating concurrent indexes.",
)
@click.pass_context
async def upgrade(ctx: Context, in_transaction: bool) -> None:
    command = ctx.obj["command"]
    migrated = await command.upgrade(run_in_transaction=in_transaction)
    if not migrated:
        click.secho("No upgrade items found", fg=Color.yellow)
    else:
        for version_file in migrated:
            click.secho(f"Success upgrading to {version_file}", fg=Color.green)


@cli.command(help="Downgrade to specified version.")
@click.option(
    "-v",
    "--version",
    default=-1,
    type=int,
    show_default=False,
    help="Specified version, default to last migration.",
)
@click.option(
    "-d",
    "--delete",
    is_flag=True,
    default=False,
    show_default=True,
    help="Also delete the migration files.",
)
@click.pass_context
@click.confirmation_option(
    prompt="Downgrade is dangerous: you might lose your data! Are you sure?",
)
async def downgrade(ctx: Context, version: int, delete: bool) -> None:
    command = ctx.obj["command"]
    try:
        files = await command.downgrade(version, delete)
    except DowngradeError as e:
        return click.secho(str(e), fg=Color.yellow)
    for file in files:
        click.secho(f"Success downgrading to {file}", fg=Color.green)


@cli.command(help="Show currently available heads (unapplied migrations).")
@click.pass_context
async def heads(ctx: Context) -> None:
    command = ctx.obj["command"]
    head_list = await command.heads()
    if not head_list:
        return click.secho("No available heads.", fg=Color.green)
    for version in head_list:
        click.secho(version, fg=Color.green)


@cli.command(help="List all migrations.")
@click.pass_context
async def history(ctx: Context) -> None:
    command = ctx.obj["command"]
    versions = await command.history()
    if not versions:
        return click.secho("No migrations created yet.", fg=Color.green)
    for version in versions:
        click.secho(version, fg=Color.green)


@cli.command(help="Initialize aerich config and create migrations folder.")
@click.option(
    "-t",
    "--tortoise-orm",
    required=True,
    help="Tortoise-ORM config dict location, like `settings.TORTOISE_ORM`.",
)
@click.option(
    "--location",
    default="./migrations",
    show_default=True,
    help="Migrations folder.",
)
@click.option(
    "-s",
    "--src_folder",
    default=CONFIG_DEFAULT_VALUES["src_folder"],
    show_default=False,
    help="Folder of the source, relative to the project root.",
)
@click.pass_context
async def init(ctx: Context, tortoise_orm, location, src_folder) -> None:
    config_file = ctx.obj["config_file"]

    if os.path.isabs(src_folder):
        src_folder = os.path.relpath(os.getcwd(), src_folder)
    # Add ./ so it's clear that this is relative path
    if not src_folder.startswith("./"):
        src_folder = "./" + src_folder

    # check that we can find the configuration, if not we can fail before the config file gets created
    add_src_path(src_folder)
    get_tortoise_config(ctx, tortoise_orm)
    config_path = Path(config_file)
    if config_path.exists():
        content = config_path.read_text()
    else:
        content = "[tool.aerich]"
    doc: dict = tomlkit.parse(content)
    table = tomlkit.table()
    table["tortoise_orm"] = tortoise_orm
    table["location"] = location
    table["src_folder"] = src_folder
    doc["tool"]["aerich"] = table

    config_path.write_text(tomlkit.dumps(doc))

    Path(location).mkdir(parents=True, exist_ok=True)

    click.secho(f"Success creating migrations folder {location}", fg=Color.green)
    click.secho(f"Success writing aerich config to {config_file}", fg=Color.green)


@cli.command(help="Generate schema and generate app migration folder.")
@click.option(
    "-s",
    "--safe",
    type=bool,
    is_flag=True,
    default=True,
    help="Create tables only when they do not already exist.",
    show_default=True,
)
@click.pass_context
async def init_db(ctx: Context, safe: bool) -> None:
    command = ctx.obj["command"]
    app = command.app
    dirname = Path(command.location, app)
    try:
        await command.init_db(safe)
        click.secho(f"Success creating app migration folder {dirname}", fg=Color.green)
        click.secho(f'Success generating initial migration file for app "{app}"', fg=Color.green)
    except FileExistsError:
        return click.secho(
            f"App {app} is already initialized. Delete {dirname} and try again.", fg=Color.yellow
        )


@cli.command(help="Prints the current database tables to stdout as Tortoise-ORM models.")
@click.option(
    "-t",
    "--table",
    help="Which tables to inspect.",
    multiple=True,
    required=False,
)
@click.pass_context
async def inspectdb(ctx: Context, table: List[str]) -> None:
    command = ctx.obj["command"]
    ret = await command.inspectdb(table)
    click.secho(ret)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
