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


def _pick_match_to_head(m2m_fields: list[dict], field_info: dict) -> list[dict]:
    """
    If there is a element in m2m_fields whose through or name is equal to field_info's
    and this element is not at the first position, put it to the head then return the
    new list, otherwise return the origin list.

    Example::
        >>> m2m_fields = [{'through': 'u1', 'name': 'u1'}, {'throught': 'u2', 'name': 'u2'}]
        >>> _pick_match_to_head(m2m_fields, {'through': 'u2', 'name': 'u2'})
        [{'through': 'u2', 'name': 'u2'}, {'throught': 'u1', 'name': 'u1'}]

    """
    through = field_info["through"]
    name = field_info["name"]
    for index, field in enumerate(m2m_fields):
        if field["through"] == through or field["name"] == name:
            if index != 0:
                m2m_fields = [field, *m2m_fields[:index], *m2m_fields[index + 1 :]]
            break
    return m2m_fields


def reorder_m2m_fields(
    old_m2m_fields: list[dict], new_m2m_fields: list[dict]
) -> tuple[list[dict], list[dict]]:
    """
    Reorder m2m fields to help dictdiffer.diff generate more precise changes
    :param old_m2m_fields: previous m2m field info list
    :param new_m2m_fields: current m2m field info list
    :return: ordered old/new m2m fields
    """
    length_old, length_new = len(old_m2m_fields), len(new_m2m_fields)
    if length_old == length_new == 1:
        # No need to change order if both of them have only one element
        pass
    elif length_old == 1:
        # If any element of new fields match the one in old fields, put it to head
        new_m2m_fields = _pick_match_to_head(new_m2m_fields, old_m2m_fields[0])
    elif length_new == 1:
        old_m2m_fields = _pick_match_to_head(old_m2m_fields, new_m2m_fields[0])
    else:
        old_table_names = [f["through"] for f in old_m2m_fields]
        new_table_names = [f["through"] for f in new_m2m_fields]
        old_field_names = [f["name"] for f in old_m2m_fields]
        new_field_names = [f["name"] for f in new_m2m_fields]
        if old_table_names == new_table_names:
            pass
        elif sorted(old_table_names) == sorted(new_table_names):
            # If table name are the same but order not match,
            # reorder new fields by through to match the order of old.

            # Case like::
            # old_m2m_fields = [
            #     {'through': 'users_group', 'name': 'users',},
            #     {'through': 'admins_group', 'name': 'admins'},
            # ]
            # new_m2m_fields = [
            #     {'through': 'admins_group', 'name': 'admins_new'},
            #     {'through': 'users_group', 'name': 'users_new',},
            # ]
            new_m2m_fields = sorted(
                new_m2m_fields, key=lambda f: old_table_names.index(f["through"])
            )
        elif old_field_names == new_field_names:
            pass
        elif sorted(old_field_names) == sorted(new_field_names):
            # Case like:
            # old_m2m_fields = [
            #     {'name': 'users', 'through': 'users_group'},
            #     {'name': 'admins', 'through': 'admins_group'},
            # ]
            # new_m2m_fields = [
            #     {'name': 'admins', 'through': 'admin_group_map'},
            #     {'name': 'users', 'through': 'user_group_map'},
            # ]
            new_m2m_fields = sorted(new_m2m_fields, key=lambda f: old_field_names.index(f["name"]))
        elif unchanged_table_names := set(old_table_names) & set(new_table_names):
            # If old/new m2m field list have one or some unchanged table names, put them to head of list.

            # Case like::
            # old_m2m_fields = [
            #     {'through': 'users_group', 'name': 'users',},
            #     {'through': 'staffs_group', 'name': 'users',},
            #     {'through': 'admins_group', 'name': 'admins'},
            # ]
            # new_m2m_fields = [
            #     {'through': 'admins_group', 'name': 'admins_new'},
            #     {'through': 'users_group', 'name': 'users_new',},
            # ]
            unchanged = sorted(unchanged_table_names, key=lambda name: old_table_names.index(name))
            ordered_old_tables = unchanged + sorted(
                set(old_table_names) - unchanged_table_names,
                key=lambda name: old_table_names.index(name),
            )
            ordered_new_tables = unchanged + sorted(
                set(new_table_names) - unchanged_table_names,
                key=lambda name: new_table_names.index(name),
            )
            if ordered_old_tables != old_table_names:
                old_m2m_fields = sorted(
                    old_m2m_fields, key=lambda f: ordered_old_tables.index(f["through"])
                )
            if ordered_new_tables != new_table_names:
                new_m2m_fields = sorted(
                    new_m2m_fields, key=lambda f: ordered_new_tables.index(f["through"])
                )
    return old_m2m_fields, new_m2m_fields
