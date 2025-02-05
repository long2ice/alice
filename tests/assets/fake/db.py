import asyncclick as click
from settings import TORTOISE_ORM

from tests._utils import drop_db, init_db


@click.group()
def cli(): ...


@cli.command()
async def create():
    await init_db(TORTOISE_ORM, False)
    click.echo(f"Success to create databases for {TORTOISE_ORM['connections']}")


@cli.command()
async def drop():
    await drop_db(TORTOISE_ORM)
    click.echo(f"Dropped databases for {TORTOISE_ORM['connections']}")


def main():
    cli()


if __name__ == "__main__":
    main()
