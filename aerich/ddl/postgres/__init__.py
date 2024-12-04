from typing import Type, cast

from tortoise import Model
from tortoise.backends.asyncpg.schema_generator import AsyncpgSchemaGenerator

from aerich.ddl import BaseDDL


class PostgresDDL(BaseDDL):
    schema_generator_cls = AsyncpgSchemaGenerator
    DIALECT = AsyncpgSchemaGenerator.DIALECT
    _ADD_INDEX_TEMPLATE = 'CREATE {unique}INDEX "{index_name}" ON "{table_name}" ({column_names})'
    _DROP_INDEX_TEMPLATE = 'DROP INDEX "{index_name}"'
    _ALTER_NULL_TEMPLATE = 'ALTER TABLE "{table_name}" ALTER COLUMN "{column}" {set_drop} NOT NULL'
    _MODIFY_COLUMN_TEMPLATE = (
        'ALTER TABLE "{table_name}" ALTER COLUMN "{column}" TYPE {datatype}{using}'
    )
    _SET_COMMENT_TEMPLATE = 'COMMENT ON COLUMN "{table_name}"."{column}" IS {comment}'
    _DROP_FK_TEMPLATE = 'ALTER TABLE "{table_name}" DROP CONSTRAINT "{fk_name}"'

    def alter_column_null(self, model: "Type[Model]", field_describe: dict) -> str:
        db_table = model._meta.db_table
        return self._ALTER_NULL_TEMPLATE.format(
            table_name=db_table,
            column=field_describe.get("db_column"),
            set_drop="DROP" if field_describe.get("nullable") else "SET",
        )

    def modify_column(self, model: "Type[Model]", field_describe: dict, is_pk: bool = False) -> str:
        db_table = model._meta.db_table
        db_field_types = cast(dict, field_describe.get("db_field_types"))
        db_column = field_describe.get("db_column")
        datatype = db_field_types.get(self.DIALECT) or db_field_types.get("")
        return self._MODIFY_COLUMN_TEMPLATE.format(
            table_name=db_table,
            column=db_column,
            datatype=datatype,
            using=f' USING "{db_column}"::{datatype}',
        )

    def set_comment(self, model: "Type[Model]", field_describe: dict) -> str:
        db_table = model._meta.db_table
        return self._SET_COMMENT_TEMPLATE.format(
            table_name=db_table,
            column=field_describe.get("db_column") or field_describe.get("raw_field"),
            comment=(
                "'{}'".format(field_describe.get("description"))
                if field_describe.get("description")
                else "NULL"
            ),
        )
