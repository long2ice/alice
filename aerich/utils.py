from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Optional, Union

from asyncclick import BadOptionUsage, ClickException, Context
from tortoise import BaseDBAsyncClient, Tortoise


def add_src_path(path: str) -> str:
    """
    add a folder to the paths, so we can import from there
    :param path: path to add
    :return: absolute path
    """
    if not os.path.isabs(path):
        # use the absolute path, otherwise some other things (e.g. __file__) won't work properly
        path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise ClickException(f"Specified source folder does not exist: {path}")
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def get_app_connection_name(config, app_name: str) -> str:
    """
    get connection name
    :param config:
    :param app_name:
    :return:
    """
    app = config.get("apps").get(app_name)
    if app:
        return app.get("default_connection", "default")
    raise BadOptionUsage(
        option_name="--app",
        message=f'Can\'t get app named "{app_name}"',
    )


def get_app_connection(config, app) -> BaseDBAsyncClient:
    """
    get connection name
    :param config:
    :param app:
    :return:
    """
    return Tortoise.get_connection(get_app_connection_name(config, app))


def get_tortoise_config(ctx: Context, tortoise_orm: str) -> dict:
    """
    get tortoise config from module
    :param ctx:
    :param tortoise_orm:
    :return:
    """
    splits = tortoise_orm.split(".")
    config_path = ".".join(splits[:-1])
    tortoise_config = splits[-1]

    try:
        config_module = importlib.import_module(config_path)
    except ModuleNotFoundError as e:
        raise ClickException(f"Error while importing configuration module: {e}") from None

    config = getattr(config_module, tortoise_config, None)
    if not config:
        raise BadOptionUsage(
            option_name="--config",
            message=f'Can\'t get "{tortoise_config}" from module "{config_module}"',
            ctx=ctx,
        )
    return config


def get_models_describe(app: str) -> Dict:
    """
    get app models describe
    :param app:
    :return:
    """
    ret = {}
    for model in Tortoise.apps[app].values():
        describe = model.describe()
        ret[describe.get("name")] = describe
    return ret


def is_default_function(string: str) -> Optional[re.Match]:
    return re.match(r"^<function.+>$", str(string or ""))


def import_py_file(file: Union[str, Path]) -> ModuleType:
    module_name, file_ext = os.path.splitext(os.path.split(file)[-1])
    spec = importlib.util.spec_from_file_location(module_name, file)
    module = importlib.util.module_from_spec(spec)  # type:ignore[arg-type]
    spec.loader.exec_module(module)  # type:ignore[union-attr]
    return module


def reorder_m2m_fields(old_m2m_fields: list[dict], new_m2m_fields: list[dict]) -> None:
    """
    Reorder m2m fields to help dictdiffer.diff generate more precise changes
    :param old_m2m_fields: previous m2m field info list
    :param new_m2m_fields: current m2m field info list
    :return:
    """
    old_table_names: list[str] = [f["through"] for f in old_m2m_fields]
    new_table_names: list[str] = [f["through"] for f in new_m2m_fields]
    if old_table_names == new_table_names:
        return
    if sorted(old_table_names) == sorted(new_table_names):
        new_m2m_fields.sort(key=lambda field: old_table_names.index(field["through"]))
        return
    old_field_names: list[str] = [f["name"] for f in old_m2m_fields]
    new_field_names: list[str] = [f["name"] for f in new_m2m_fields]
    if old_field_names == new_field_names:
        return
    if sorted(old_field_names) == sorted(new_field_names):
        new_m2m_fields.sort(key=lambda field: old_field_names.index(field["name"]))
        return
    if unchanged_tables := set(old_table_names) & set(new_table_names):
        unchanged = sorted(unchanged_tables)
        ordered_old_tables = unchanged + sorted(set(old_table_names) - unchanged_tables)
        ordered_new_tables = unchanged + sorted(set(new_table_names) - unchanged_tables)
        if ordered_old_tables != old_table_names:
            old_m2m_fields.sort(key=lambda field: ordered_old_tables.index(field["through"]))
        if ordered_new_tables != new_table_names:
            new_m2m_fields.sort(key=lambda field: ordered_new_tables.index(field["through"]))
