from enum import Enum
from typing import Any, List, Type, cast

from tortoise import BaseDBAsyncClient, Model
from tortoise.backends.base.schema_generator import BaseSchemaGenerator

from aerich.utils import is_default_function


class BaseDDL:
    schema_generator_cls: Type[BaseSchemaGenerator] = BaseSchemaGenerator
    DIALECT = "sql"
    _DROP_TABLE_TEMPLATE = 'DROP TABLE IF EXISTS "{table_name}"'
    _ADD_COLUMN_TEMPLATE = 'ALTER TABLE "{table_name}" ADD {column}'
    _DROP_COLUMN_TEMPLATE = 'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}"'
    _ALTER_DEFAULT_TEMPLATE = 'ALTER TABLE "{table_name}" ALTER COLUMN "{column}" {default}'
    _RENAME_COLUMN_TEMPLATE = (
        'ALTER TABLE "{table_name}" RENAME COLUMN "{old_column_name}" TO "{new_column_name}"'
    )
    _ADD_INDEX_TEMPLATE = (
        'ALTER TABLE "{table_name}" ADD {unique}INDEX "{index_name}" ({column_names})'
    )
    _DROP_INDEX_TEMPLATE = 'ALTER TABLE "{table_name}" DROP INDEX "{index_name}"'
    _ADD_FK_TEMPLATE = 'ALTER TABLE "{table_name}" ADD CONSTRAINT "{fk_name}" FOREIGN KEY ("{db_column}") REFERENCES "{table}" ("{field}") ON DELETE {on_delete}'
    _DROP_FK_TEMPLATE = 'ALTER TABLE "{table_name}" DROP FOREIGN KEY "{fk_name}"'
    _M2M_TABLE_TEMPLATE = (
        'CREATE TABLE "{table_name}" (\n'
        '    "{backward_key}" {backward_type} NOT NULL REFERENCES "{backward_table}" ("{backward_field}") ON DELETE CASCADE,\n'
        '    "{forward_key}" {forward_type} NOT NULL REFERENCES "{forward_table}" ("{forward_field}") ON DELETE {on_delete}\n'
        "){extra}{comment}"
    )
    _MODIFY_COLUMN_TEMPLATE = 'ALTER TABLE "{table_name}" MODIFY COLUMN {column}'
    _CHANGE_COLUMN_TEMPLATE = (
        'ALTER TABLE "{table_name}" CHANGE {old_column_name} {new_column_name} {new_column_type}'
    )
    _RENAME_TABLE_TEMPLATE = 'ALTER TABLE "{old_table_name}" RENAME TO "{new_table_name}"'

    def __init__(self, client: "BaseDBAsyncClient") -> None:
        self.client = client
        self.schema_generator = self.schema_generator_cls(client)

    def create_table(self, model: "Type[Model]") -> str:
        return self.schema_generator._get_table_sql(model, True)["table_creation_string"].rstrip(
            ";"
        )

    def drop_table(self, table_name: str) -> str:
        return self._DROP_TABLE_TEMPLATE.format(table_name=table_name)

    def create_m2m(
        self, model: "Type[Model]", field_describe: dict, reference_table_describe: dict
    ) -> str:
        through = cast(str, field_describe.get("through"))
        description = field_describe.get("description")
        pk_field = cast(dict, reference_table_describe.get("pk_field"))
        reference_id = pk_field.get("db_column")
        db_field_types = cast(dict, pk_field.get("db_field_types"))
        return self._M2M_TABLE_TEMPLATE.format(
            table_name=through,
            backward_table=model._meta.db_table,
            forward_table=reference_table_describe.get("table"),
            backward_field=model._meta.db_pk_column,
            forward_field=reference_id,
            backward_key=field_describe.get("backward_key"),
            backward_type=model._meta.pk.get_for_dialect(self.DIALECT, "SQL_TYPE"),
            forward_key=field_describe.get("forward_key"),
            forward_type=db_field_types.get(self.DIALECT) or db_field_types.get(""),
            on_delete=field_describe.get("on_delete"),
            extra=self.schema_generator._table_generate_extra(table=through),
            comment=(
                self.schema_generator._table_comment_generator(table=through, comment=description)
                if description
                else ""
            ),
        )

    def drop_m2m(self, table_name: str) -> str:
        return self._DROP_TABLE_TEMPLATE.format(table_name=table_name)

    def _get_default(self, model: "Type[Model]", field_describe: dict) -> Any:
        db_table = model._meta.db_table
        default = field_describe.get("default")
        if isinstance(default, Enum):
            default = default.value
        db_column = cast(str, field_describe.get("db_column"))
        auto_now_add = field_describe.get("auto_now_add", False)
        auto_now = field_describe.get("auto_now", False)
        if default is not None or auto_now_add:
            if field_describe.get("field_type") in [
                "UUIDField",
                "TextField",
                "JSONField",
            ] or is_default_function(default):
                default = ""
            else:
                try:
                    default = self.schema_generator._column_default_generator(
                        db_table,
                        db_column,
                        self.schema_generator._escape_default_value(default),
                        auto_now_add,
                        auto_now,
                    )
                except NotImplementedError:
                    default = ""
        else:
            default = None
        return default

    def add_column(self, model: "Type[Model]", field_describe: dict, is_pk: bool = False) -> str:
        return self._add_or_modify_column(model, field_describe, is_pk)

    def _add_or_modify_column(self, model, field_describe: dict, is_pk: bool, modify=False) -> str:
        db_table = model._meta.db_table
        description = field_describe.get("description")
        db_column = cast(str, field_describe.get("db_column"))
        db_field_types = cast(dict, field_describe.get("db_field_types"))
        default = self._get_default(model, field_describe)
        if default is None:
            default = ""
        if modify:
            unique = ""
            template = self._MODIFY_COLUMN_TEMPLATE
        else:
            unique = "UNIQUE" if field_describe.get("unique") else ""
            template = self._ADD_COLUMN_TEMPLATE
        return template.format(
            table_name=db_table,
            column=self.schema_generator._create_string(
                db_column=db_column,
                field_type=db_field_types.get(self.DIALECT, db_field_types.get("")),
                nullable="NOT NULL" if not field_describe.get("nullable") else "",
                unique=unique,
                comment=(
                    self.schema_generator._column_comment_generator(
                        table=db_table,
                        column=db_column,
                        comment=description,
                    )
                    if description
                    else ""
                ),
                is_primary_key=is_pk,
                default=default,
            ),
        )

    def drop_column(self, model: "Type[Model]", column_name: str) -> str:
        return self._DROP_COLUMN_TEMPLATE.format(
            table_name=model._meta.db_table, column_name=column_name
        )

    def modify_column(self, model: "Type[Model]", field_describe: dict, is_pk: bool = False) -> str:
        return self._add_or_modify_column(model, field_describe, is_pk, modify=True)

    def rename_column(
        self, model: "Type[Model]", old_column_name: str, new_column_name: str
    ) -> str:
        return self._RENAME_COLUMN_TEMPLATE.format(
            table_name=model._meta.db_table,
            old_column_name=old_column_name,
            new_column_name=new_column_name,
        )

    def change_column(
        self, model: "Type[Model]", old_column_name: str, new_column_name: str, new_column_type: str
    ) -> str:
        return self._CHANGE_COLUMN_TEMPLATE.format(
            table_name=model._meta.db_table,
            old_column_name=old_column_name,
            new_column_name=new_column_name,
            new_column_type=new_column_type,
        )

    def add_index(self, model: "Type[Model]", field_names: List[str], unique=False) -> str:
        return self._ADD_INDEX_TEMPLATE.format(
            unique="UNIQUE " if unique else "",
            index_name=self.schema_generator._generate_index_name(
                "idx" if not unique else "uid", model, field_names
            ),
            table_name=model._meta.db_table,
            column_names=", ".join(self.schema_generator.quote(f) for f in field_names),
        )

    def drop_index(self, model: "Type[Model]", field_names: List[str], unique=False) -> str:
        return self._DROP_INDEX_TEMPLATE.format(
            index_name=self.schema_generator._generate_index_name(
                "idx" if not unique else "uid", model, field_names
            ),
            table_name=model._meta.db_table,
        )

    def drop_index_by_name(self, model: "Type[Model]", index_name: str) -> str:
        return self._DROP_INDEX_TEMPLATE.format(
            index_name=index_name,
            table_name=model._meta.db_table,
        )

    def _generate_fk_name(
        self, db_table, field_describe: dict, reference_table_describe: dict
    ) -> str:
        """Generate fk name"""
        db_column = cast(str, field_describe.get("raw_field"))
        pk_field = cast(dict, reference_table_describe.get("pk_field"))
        to_field = cast(str, pk_field.get("db_column"))
        to_table = cast(str, reference_table_describe.get("table"))
        return self.schema_generator._generate_fk_name(
            from_table=db_table,
            from_field=db_column,
            to_table=to_table,
            to_field=to_field,
        )

    def add_fk(
        self, model: "Type[Model]", field_describe: dict, reference_table_describe: dict
    ) -> str:
        db_table = model._meta.db_table

        db_column = field_describe.get("raw_field")
        pk_field = cast(dict, reference_table_describe.get("pk_field"))
        reference_id = pk_field.get("db_column")
        return self._ADD_FK_TEMPLATE.format(
            table_name=db_table,
            fk_name=self._generate_fk_name(db_table, field_describe, reference_table_describe),
            db_column=db_column,
            table=reference_table_describe.get("table"),
            field=reference_id,
            on_delete=field_describe.get("on_delete"),
        )

    def drop_fk(
        self, model: "Type[Model]", field_describe: dict, reference_table_describe: dict
    ) -> str:
        db_table = model._meta.db_table
        fk_name = self._generate_fk_name(db_table, field_describe, reference_table_describe)
        return self._DROP_FK_TEMPLATE.format(table_name=db_table, fk_name=fk_name)

    def alter_column_default(self, model: "Type[Model]", field_describe: dict) -> str:
        db_table = model._meta.db_table
        default = self._get_default(model, field_describe)
        return self._ALTER_DEFAULT_TEMPLATE.format(
            table_name=db_table,
            column=field_describe.get("db_column"),
            default="SET" + default if default is not None else "DROP DEFAULT",
        )

    def alter_column_null(self, model: "Type[Model]", field_describe: dict) -> str:
        return self.modify_column(model, field_describe)

    def set_comment(self, model: "Type[Model]", field_describe: dict) -> str:
        return self.modify_column(model, field_describe)

    def rename_table(self, model: "Type[Model]", old_table_name: str, new_table_name: str) -> str:
        db_table = model._meta.db_table
        return self._RENAME_TABLE_TEMPLATE.format(
            table_name=db_table, old_table_name=old_table_name, new_table_name=new_table_name
        )
