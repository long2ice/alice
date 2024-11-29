import hashlib
import importlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, Type, Union, cast

import asyncclick as click
from dictdiffer import diff
from tortoise import BaseDBAsyncClient, Model, Tortoise
from tortoise.exceptions import OperationalError
from tortoise.indexes import Index

from aerich.ddl import BaseDDL
from aerich.models import MAX_VERSION_LENGTH, Aerich
from aerich.utils import get_app_connection, get_models_describe, is_default_function

MIGRATE_TEMPLATE = """from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return \"\"\"
        {upgrade_sql}\"\"\"


async def downgrade(db: BaseDBAsyncClient) -> str:
    return \"\"\"
        {downgrade_sql}\"\"\"
"""


class Migrate:
    upgrade_operators: List[str] = []
    downgrade_operators: List[str] = []
    _upgrade_fk_m2m_index_operators: List[str] = []
    _downgrade_fk_m2m_index_operators: List[str] = []
    _upgrade_m2m: List[str] = []
    _downgrade_m2m: List[str] = []
    _aerich = Aerich.__name__
    _rename_old: List[str] = []
    _rename_new: List[str] = []

    ddl: BaseDDL
    ddl_class: Type[BaseDDL]
    _last_version_content: Optional[dict] = None
    app: str
    migrate_location: Path
    dialect: str
    _db_version: Optional[str] = None

    @staticmethod
    def get_field_by_name(name: str, fields: List[dict]) -> dict:
        return next(filter(lambda x: x.get("name") == name, fields))

    @classmethod
    def get_all_version_files(cls) -> List[str]:
        return sorted(
            filter(lambda x: x.endswith("py"), os.listdir(cls.migrate_location)),
            key=lambda x: int(x.split("_")[0]),
        )

    @classmethod
    def _get_model(cls, model: str) -> Type[Model]:
        return Tortoise.apps[cls.app][model]

    @classmethod
    async def get_last_version(cls) -> Optional[Aerich]:
        try:
            return await Aerich.filter(app=cls.app).first()
        except OperationalError:
            return None

    @classmethod
    async def _get_db_version(cls, connection: BaseDBAsyncClient) -> None:
        if cls.dialect == "mysql":
            sql = "select version() as version"
            ret = await connection.execute_query(sql)
            cls._db_version = ret[1][0].get("version")

    @classmethod
    async def load_ddl_class(cls) -> Type[BaseDDL]:
        ddl_dialect_module = importlib.import_module(f"aerich.ddl.{cls.dialect}")
        return getattr(ddl_dialect_module, f"{cls.dialect.capitalize()}DDL")

    @classmethod
    async def init(cls, config: dict, app: str, location: str) -> None:
        await Tortoise.init(config=config)
        last_version = await cls.get_last_version()
        cls.app = app
        cls.migrate_location = Path(location, app)
        if last_version:
            cls._last_version_content = cast(dict, last_version.content)

        connection = get_app_connection(config, app)
        cls.dialect = connection.schema_generator.DIALECT
        cls.ddl_class = await cls.load_ddl_class()
        cls.ddl = cls.ddl_class(connection)
        await cls._get_db_version(connection)

    @classmethod
    async def _get_last_version_num(cls) -> Optional[int]:
        last_version = await cls.get_last_version()
        if not last_version:
            return None
        version = last_version.version
        return int(version.split("_", 1)[0])

    @classmethod
    async def generate_version(cls, name=None) -> str:
        now = datetime.now().strftime("%Y%m%d%H%M%S").replace("/", "")
        last_version_num = await cls._get_last_version_num()
        if last_version_num is None:
            return f"0_{now}_init.py"
        version = f"{last_version_num + 1}_{now}_{name}.py"
        if len(version) > MAX_VERSION_LENGTH:
            raise ValueError(f"Version name exceeds maximum length ({MAX_VERSION_LENGTH})")
        return version

    @classmethod
    async def _generate_diff_py(cls, name) -> str:
        version = await cls.generate_version(name)
        # delete if same version exists
        for version_file in cls.get_all_version_files():
            if version_file.startswith(version.split("_")[0]):
                os.unlink(Path(cls.migrate_location, version_file))

        content = cls._get_diff_file_content()
        Path(cls.migrate_location, version).write_text(content, encoding="utf-8")
        return version

    @classmethod
    async def migrate(cls, name: str, empty: bool) -> str:
        """
        diff old models and new models to generate diff content
        :param name: str name for migration
        :param empty: bool if True generates empty migration
        :return:
        """
        if empty:
            return await cls._generate_diff_py(name)
        new_version_content = get_models_describe(cls.app)
        last_version = cast(dict, cls._last_version_content)
        cls.diff_models(last_version, new_version_content)
        cls.diff_models(new_version_content, last_version, False)

        cls._merge_operators()

        if not cls.upgrade_operators:
            return ""

        return await cls._generate_diff_py(name)

    @classmethod
    def _get_diff_file_content(cls) -> str:
        """
        builds content for diff file from template
        """

        def join_lines(lines: List[str]) -> str:
            if not lines:
                return ""
            return ";\n        ".join(lines) + ";"

        return MIGRATE_TEMPLATE.format(
            upgrade_sql=join_lines(cls.upgrade_operators),
            downgrade_sql=join_lines(cls.downgrade_operators),
        )

    @classmethod
    def _add_operator(cls, operator: str, upgrade=True, fk_m2m_index=False) -> None:
        """
        add operator,differentiate fk because fk is order limit
        :param operator:
        :param upgrade:
        :param fk_m2m_index:
        :return:
        """
        operator = operator.rstrip(";")
        if upgrade:
            if fk_m2m_index:
                cls._upgrade_fk_m2m_index_operators.append(operator)
            else:
                cls.upgrade_operators.append(operator)
        else:
            if fk_m2m_index:
                cls._downgrade_fk_m2m_index_operators.append(operator)
            else:
                cls.downgrade_operators.append(operator)

    @classmethod
    def _handle_indexes(cls, model: Type[Model], indexes: List[Union[Tuple[str], Index]]) -> list:
        ret: list = []

        def index_hash(self) -> str:
            h = hashlib.new("MD5", usedforsecurity=False)  # type:ignore[call-arg]
            h.update(
                self.index_name(cls.ddl.schema_generator, model).encode()
                + self.__class__.__name__.encode()
            )
            return h.hexdigest()

        for index in indexes:
            if isinstance(index, Index):
                index.__hash__ = index_hash  # type:ignore[method-assign,assignment]
            ret.append(index)
        return ret

    @classmethod
    def _get_indexes(cls, model, model_describe: dict) -> Set[Union[Index, Tuple[str, ...]]]:
        indexes: Set[Union[Index, Tuple[str, ...]]] = set()
        for x in cls._handle_indexes(model, model_describe.get("indexes", [])):
            if isinstance(x, Index):
                indexes.add(x)
            else:
                indexes.add(cast(Tuple[str, ...], tuple(x)))
        return indexes

    @classmethod
    def diff_models(
        cls, old_models: Dict[str, dict], new_models: Dict[str, dict], upgrade=True
    ) -> None:
        """
        diff models and add operators
        :param old_models:
        :param new_models:
        :param upgrade:
        :return:
        """
        _aerich = f"{cls.app}.{cls._aerich}"
        old_models.pop(_aerich, None)
        new_models.pop(_aerich, None)

        for new_model_str, new_model_describe in new_models.items():
            model = cls._get_model(new_model_describe["name"].split(".")[1])

            if new_model_str not in old_models:
                if upgrade:
                    cls._add_operator(cls.add_model(model), upgrade)
                else:
                    # we can't find origin model when downgrade, so skip
                    pass
            else:
                old_model_describe = cast(dict, old_models.get(new_model_str))
                # rename table
                new_table = cast(str, new_model_describe.get("table"))
                old_table = cast(str, old_model_describe.get("table"))
                if new_table != old_table:
                    cls._add_operator(cls.rename_table(model, old_table, new_table), upgrade)
                old_unique_together = set(
                    map(
                        lambda x: tuple(x),
                        cast(List[Iterable[str]], old_model_describe.get("unique_together")),
                    )
                )
                new_unique_together = set(
                    map(
                        lambda x: tuple(x),
                        cast(List[Iterable[str]], new_model_describe.get("unique_together")),
                    )
                )
                old_indexes = cls._get_indexes(model, old_model_describe)
                new_indexes = cls._get_indexes(model, new_model_describe)
                old_pk_field = old_model_describe.get("pk_field")
                new_pk_field = new_model_describe.get("pk_field")
                # pk field
                changes = diff(old_pk_field, new_pk_field)
                for action, option, change in changes:
                    # current only support rename pk
                    if action == "change" and option == "name":
                        cls._add_operator(cls._rename_field(model, *change), upgrade)
                # m2m fields
                old_m2m_fields = cast(List[dict], old_model_describe.get("m2m_fields"))
                new_m2m_fields = cast(List[dict], new_model_describe.get("m2m_fields"))
                for action, option, change in diff(old_m2m_fields, new_m2m_fields):
                    if change[0][0] == "db_constraint":
                        continue
                    new_value = change[0][1]
                    if isinstance(new_value, str):
                        for new_m2m_field in new_m2m_fields:
                            if new_m2m_field["name"] == new_value:
                                table = cast(str, new_m2m_field.get("through"))
                                break
                    else:
                        table = new_value.get("through")
                    if action == "add":
                        add = False
                        if upgrade and table not in cls._upgrade_m2m:
                            cls._upgrade_m2m.append(table)
                            add = True
                        elif not upgrade and table not in cls._downgrade_m2m:
                            cls._downgrade_m2m.append(table)
                            add = True
                        if add:
                            ref_desc = cast(dict, new_models.get(new_value.get("model_name")))
                            cls._add_operator(
                                cls.create_m2m(model, new_value, ref_desc),
                                upgrade,
                                fk_m2m_index=True,
                            )
                    elif action == "remove":
                        add = False
                        if upgrade and table not in cls._upgrade_m2m:
                            cls._upgrade_m2m.append(table)
                            add = True
                        elif not upgrade and table not in cls._downgrade_m2m:
                            cls._downgrade_m2m.append(table)
                            add = True
                        if add:
                            cls._add_operator(cls.drop_m2m(table), upgrade, True)
                # add unique_together
                for index in new_unique_together.difference(old_unique_together):
                    cls._add_operator(cls._add_index(model, index, True), upgrade, True)
                # remove unique_together
                for index in old_unique_together.difference(new_unique_together):
                    cls._add_operator(cls._drop_index(model, index, True), upgrade, True)
                # add indexes
                for idx in new_indexes.difference(old_indexes):
                    cls._add_operator(cls._add_index(model, idx, False), upgrade, True)
                # remove indexes
                for idx in old_indexes.difference(new_indexes):
                    cls._add_operator(cls._drop_index(model, idx, False), upgrade, True)
                old_data_fields = list(
                    filter(
                        lambda x: x.get("db_field_types") is not None,
                        cast(List[dict], old_model_describe.get("data_fields")),
                    )
                )
                new_data_fields = list(
                    filter(
                        lambda x: x.get("db_field_types") is not None,
                        cast(List[dict], new_model_describe.get("data_fields")),
                    )
                )

                old_data_fields_name = cast(List[str], [i.get("name") for i in old_data_fields])
                new_data_fields_name = cast(List[str], [i.get("name") for i in new_data_fields])

                # add fields or rename fields
                for new_data_field_name in set(new_data_fields_name).difference(
                    set(old_data_fields_name)
                ):
                    new_data_field = cls.get_field_by_name(new_data_field_name, new_data_fields)
                    is_rename = False
                    for old_data_field in old_data_fields:
                        changes = list(diff(old_data_field, new_data_field))
                        old_data_field_name = cast(str, old_data_field.get("name"))
                        if len(changes) == 2:
                            # rename field
                            if (
                                changes[0]
                                == (
                                    "change",
                                    "name",
                                    (old_data_field_name, new_data_field_name),
                                )
                                and changes[1]
                                == (
                                    "change",
                                    "db_column",
                                    (
                                        old_data_field.get("db_column"),
                                        new_data_field.get("db_column"),
                                    ),
                                )
                                and old_data_field_name not in new_data_fields_name
                            ):
                                if upgrade:
                                    is_rename = click.prompt(
                                        f"Rename {old_data_field_name} to {new_data_field_name}?",
                                        default=True,
                                        type=bool,
                                        show_choices=True,
                                    )
                                else:
                                    is_rename = old_data_field_name in cls._rename_new
                                if is_rename:
                                    cls._rename_new.append(new_data_field_name)
                                    cls._rename_old.append(old_data_field_name)
                                    # only MySQL8+ has rename syntax
                                    if (
                                        cls.dialect == "mysql"
                                        and cls._db_version
                                        and cls._db_version.startswith("5.")
                                    ):
                                        cls._add_operator(
                                            cls._change_field(
                                                model, old_data_field, new_data_field
                                            ),
                                            upgrade,
                                        )
                                    else:
                                        cls._add_operator(
                                            cls._rename_field(model, *changes[1][2]),
                                            upgrade,
                                        )
                    if not is_rename:
                        cls._add_operator(
                            cls._add_field(
                                model,
                                new_data_field,
                            ),
                            upgrade,
                        )
                        if new_data_field["indexed"]:
                            cls._add_operator(
                                cls._add_index(
                                    model, (new_data_field["db_column"],), new_data_field["unique"]
                                ),
                                upgrade,
                                True,
                            )
                # remove fields
                for old_data_field_name in set(old_data_fields_name).difference(
                    set(new_data_fields_name)
                ):
                    # don't remove field if is renamed
                    if (upgrade and old_data_field_name in cls._rename_old) or (
                        not upgrade and old_data_field_name in cls._rename_new
                    ):
                        continue
                    old_data_field = cls.get_field_by_name(old_data_field_name, old_data_fields)
                    db_column = cast(str, old_data_field["db_column"])
                    cls._add_operator(
                        cls._remove_field(model, db_column),
                        upgrade,
                    )
                    if old_data_field["indexed"]:
                        is_unique_field = old_data_field.get("unique")
                        cls._add_operator(
                            cls._drop_index(model, {db_column}, is_unique_field),
                            upgrade,
                            True,
                        )

                old_fk_fields = cast(List[dict], old_model_describe.get("fk_fields"))
                new_fk_fields = cast(List[dict], new_model_describe.get("fk_fields"))

                old_fk_fields_name: List[str] = [i.get("name", "") for i in old_fk_fields]
                new_fk_fields_name: List[str] = [i.get("name", "") for i in new_fk_fields]

                # add fk
                for new_fk_field_name in set(new_fk_fields_name).difference(
                    set(old_fk_fields_name)
                ):
                    fk_field = cls.get_field_by_name(new_fk_field_name, new_fk_fields)
                    if fk_field.get("db_constraint"):
                        ref_describe = cast(dict, new_models[fk_field["python_type"]])
                        cls._add_operator(
                            cls._add_fk(model, fk_field, ref_describe),
                            upgrade,
                            fk_m2m_index=True,
                        )
                # drop fk
                for old_fk_field_name in set(old_fk_fields_name).difference(
                    set(new_fk_fields_name)
                ):
                    old_fk_field = cls.get_field_by_name(
                        old_fk_field_name, cast(List[dict], old_fk_fields)
                    )
                    if old_fk_field.get("db_constraint"):
                        ref_describe = cast(dict, old_models[old_fk_field["python_type"]])
                        cls._add_operator(
                            cls._drop_fk(model, old_fk_field, ref_describe),
                            upgrade,
                            fk_m2m_index=True,
                        )
                # change fields
                for field_name in set(new_data_fields_name).intersection(set(old_data_fields_name)):
                    old_data_field = cls.get_field_by_name(field_name, old_data_fields)
                    new_data_field = cls.get_field_by_name(field_name, new_data_fields)
                    changes = diff(old_data_field, new_data_field)
                    modified = False
                    for change in changes:
                        _, option, old_new = change
                        if option == "indexed":
                            # change index
                            if old_new[0] is False and old_new[1] is True:
                                unique = new_data_field.get("unique")
                                cls._add_operator(
                                    cls._add_index(model, (field_name,), unique), upgrade, True
                                )
                            else:
                                unique = old_data_field.get("unique")
                                cls._add_operator(
                                    cls._drop_index(model, (field_name,), unique), upgrade, True
                                )
                        elif option == "db_field_types.":
                            if new_data_field.get("field_type") == "DecimalField":
                                # modify column
                                cls._add_operator(
                                    cls._modify_field(model, new_data_field),
                                    upgrade,
                                )
                            else:
                                continue
                        elif option == "default":
                            if not (
                                is_default_function(old_new[0]) or is_default_function(old_new[1])
                            ):
                                # change column default
                                cls._add_operator(
                                    cls._alter_default(model, new_data_field), upgrade
                                )
                        elif option == "unique":
                            # because indexed include it
                            continue
                        elif option == "nullable":
                            # change nullable
                            cls._add_operator(cls._alter_null(model, new_data_field), upgrade)
                        elif option == "description":
                            # change comment
                            cls._add_operator(cls._set_comment(model, new_data_field), upgrade)
                        else:
                            if modified:
                                continue
                            # modify column
                            cls._add_operator(
                                cls._modify_field(model, new_data_field),
                                upgrade,
                            )
                            modified = True

        for old_model in old_models.keys() - new_models.keys():
            cls._add_operator(cls.drop_model(old_models[old_model]["table"]), upgrade)

    @classmethod
    def rename_table(cls, model: Type[Model], old_table_name: str, new_table_name: str) -> str:
        return cls.ddl.rename_table(model, old_table_name, new_table_name)

    @classmethod
    def add_model(cls, model: Type[Model]) -> str:
        return cls.ddl.create_table(model)

    @classmethod
    def drop_model(cls, table_name: str) -> str:
        return cls.ddl.drop_table(table_name)

    @classmethod
    def create_m2m(
        cls, model: Type[Model], field_describe: dict, reference_table_describe: dict
    ) -> str:
        return cls.ddl.create_m2m(model, field_describe, reference_table_describe)

    @classmethod
    def drop_m2m(cls, table_name: str) -> str:
        return cls.ddl.drop_m2m(table_name)

    @classmethod
    def _resolve_fk_fields_name(cls, model: Type[Model], fields_name: Iterable[str]) -> List[str]:
        ret = []
        for field_name in fields_name:
            try:
                field = model._meta.fields_map[field_name]
            except KeyError:
                # field dropped or to be add
                pass
            else:
                if field.source_field:
                    field_name = field.source_field
                elif field_name in model._meta.fk_fields:
                    field_name += "_id"
            ret.append(field_name)
        return ret

    @classmethod
    def _drop_index(
        cls, model: Type[Model], fields_name: Union[Iterable[str], Index], unique=False
    ) -> str:
        if isinstance(fields_name, Index):
            return cls.ddl.drop_index_by_name(
                model, fields_name.index_name(cls.ddl.schema_generator, model)
            )
        field_names = cls._resolve_fk_fields_name(model, fields_name)
        return cls.ddl.drop_index(model, field_names, unique)

    @classmethod
    def _add_index(
        cls, model: Type[Model], fields_name: Union[Iterable[str], Index], unique=False
    ) -> str:
        if isinstance(fields_name, Index):
            return fields_name.get_sql(cls.ddl.schema_generator, model, False)
        field_names = cls._resolve_fk_fields_name(model, fields_name)
        return cls.ddl.add_index(model, field_names, unique)

    @classmethod
    def _add_field(cls, model: Type[Model], field_describe: dict, is_pk: bool = False) -> str:
        return cls.ddl.add_column(model, field_describe, is_pk)

    @classmethod
    def _alter_default(cls, model: Type[Model], field_describe: dict) -> str:
        return cls.ddl.alter_column_default(model, field_describe)

    @classmethod
    def _alter_null(cls, model: Type[Model], field_describe: dict) -> str:
        return cls.ddl.alter_column_null(model, field_describe)

    @classmethod
    def _set_comment(cls, model: Type[Model], field_describe: dict) -> str:
        return cls.ddl.set_comment(model, field_describe)

    @classmethod
    def _modify_field(cls, model: Type[Model], field_describe: dict) -> str:
        return cls.ddl.modify_column(model, field_describe)

    @classmethod
    def _drop_fk(
        cls, model: Type[Model], field_describe: dict, reference_table_describe: dict
    ) -> str:
        return cls.ddl.drop_fk(model, field_describe, reference_table_describe)

    @classmethod
    def _remove_field(cls, model: Type[Model], column_name: str) -> str:
        return cls.ddl.drop_column(model, column_name)

    @classmethod
    def _rename_field(cls, model: Type[Model], old_field_name: str, new_field_name: str) -> str:
        return cls.ddl.rename_column(model, old_field_name, new_field_name)

    @classmethod
    def _change_field(
        cls, model: Type[Model], old_field_describe: dict, new_field_describe: dict
    ) -> str:
        db_field_types = cast(dict, new_field_describe.get("db_field_types"))
        return cls.ddl.change_column(
            model,
            cast(str, old_field_describe.get("db_column")),
            cast(str, new_field_describe.get("db_column")),
            cast(str, db_field_types.get(cls.dialect) or db_field_types.get("")),
        )

    @classmethod
    def _add_fk(
        cls, model: Type[Model], field_describe: dict, reference_table_describe: dict
    ) -> str:
        """
        add fk
        :param model:
        :param field_describe:
        :param reference_table_describe:
        :return:
        """
        return cls.ddl.add_fk(model, field_describe, reference_table_describe)

    @classmethod
    def _merge_operators(cls) -> None:
        """
        fk/m2m/index must be last when add,first when drop
        :return:
        """
        for _upgrade_fk_m2m_operator in cls._upgrade_fk_m2m_index_operators:
            if "ADD" in _upgrade_fk_m2m_operator or "CREATE" in _upgrade_fk_m2m_operator:
                cls.upgrade_operators.append(_upgrade_fk_m2m_operator)
            else:
                cls.upgrade_operators.insert(0, _upgrade_fk_m2m_operator)

        for _downgrade_fk_m2m_operator in cls._downgrade_fk_m2m_index_operators:
            if "ADD" in _downgrade_fk_m2m_operator or "CREATE" in _downgrade_fk_m2m_operator:
                cls.downgrade_operators.append(_downgrade_fk_m2m_operator)
            else:
                cls.downgrade_operators.insert(0, _downgrade_fk_m2m_operator)
