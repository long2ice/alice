from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Generator, Optional, Union

from asyncclick import BadOptionUsage, ClickException, Context
from dictdiffer import diff
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


def get_dict_diff_by_key(
    old_fields: list[dict], new_fields: list[dict], key="through"
) -> Generator[tuple]:
    """
    Compare two list by key instead of by index

    :param old_fields: previous field info list
    :param new_fields: current field info list
    :param key: if two dicts have the same value of this key, action is change; otherwise, is remove/add
    :return: similar to dictdiffer.diff

    Example::

        >>> old = [{'through': 'a'}, {'through': 'b'}, {'through': 'c'}]
        >>> new = [{'through': 'a'}, {'through': 'c'}]  # remove the second element
        >>> list(diff(old, new))
        [('change', [1, 'through'], ('b', 'c')),
         ('remove', '', [(2, {'through': 'c'})])]
        >>> list(get_dict_diff_by_key(old, new))
        [('remove', '', [(0, {'through': 'b'})])]

    """
    length_old, length_new = len(old_fields), len(new_fields)
    if length_old == 0 or length_new == 0 or length_old == length_new == 1:
        yield from diff(old_fields, new_fields)
    else:
        value_index: dict[str, int] = {f[key]: i for i, f in enumerate(new_fields)}
        additions = set(range(length_new))
        for field in old_fields:
            value = field[key]
            if (index := value_index.get(value)) is not None:
                additions.remove(index)
                yield from diff([field], [new_fields[index]])  # change
            else:
                yield from diff([field], [])  # remove
        if additions:
            for index in sorted(additions):
                yield from diff([], [new_fields[index]])  # add
