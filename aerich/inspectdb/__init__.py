from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypedDict

from pydantic import BaseModel
from tortoise import BaseDBAsyncClient


class ColumnInfoDict(TypedDict):
    name: str
    pk: str
    index: str
    null: str
    default: str
    length: str
    comment: str


FieldMapDict = Dict[str, Callable[..., str]]


class Column(BaseModel):
    name: str
    data_type: str
    null: bool
    default: Any
    comment: Optional[str] = None
    pk: bool
    unique: bool
    index: bool
    length: Optional[int] = None
    extra: Optional[str] = None
    decimal_places: Optional[int] = None
    max_digits: Optional[int] = None

    def translate(self) -> ColumnInfoDict:
        comment = default = length = index = null = pk = ""
        if self.pk:
            pk = "pk=True, "
        else:
            if self.unique:
                index = "unique=True, "
            else:
                if self.index:
                    index = "index=True, "
        if self.data_type in ("varchar", "VARCHAR"):
            length = f"max_length={self.length}, "
        elif self.data_type in ("decimal", "numeric"):
            length_parts = []
            if self.max_digits:
                length_parts.append(f"max_digits={self.max_digits}")
            if self.decimal_places:
                length_parts.append(f"decimal_places={self.decimal_places}")
            if length_parts:
                length = ", ".join(length_parts) + ", "
        if self.null:
            null = "null=True, "
        if self.default is not None:
            if self.data_type in ("tinyint", "INT"):
                default = f"default={'True' if self.default == '1' else 'False'}, "
            elif self.data_type == "bool":
                default = f"default={'True' if self.default == 'true' else 'False'}, "
            elif self.data_type in ("datetime", "timestamptz", "TIMESTAMP"):
                if "CURRENT_TIMESTAMP" == self.default:
                    if "DEFAULT_GENERATED on update CURRENT_TIMESTAMP" == self.extra:
                        default = "auto_now=True, "
                    else:
                        default = "auto_now_add=True, "
            else:
                if "::" in self.default:
                    default = f"default={self.default.split('::')[0]}, "
                elif self.default.endswith("()"):
                    default = ""
                elif self.default == "":
                    default = 'default=""'
                else:
                    default = f"default={self.default}, "

        if self.comment:
            comment = f"description='{self.comment}', "
        return {
            "name": self.name,
            "pk": pk,
            "index": index,
            "null": null,
            "default": default,
            "length": length,
            "comment": comment,
        }


class Inspect:
    _table_template = "class {table}(Model):\n"

    def __init__(self, conn: BaseDBAsyncClient, tables: list[str] | None = None) -> None:
        self.conn = conn
        try:
            self.database = conn.database  # type:ignore[attr-defined]
        except AttributeError:
            pass
        self.tables = tables

    @property
    def field_map(self) -> FieldMapDict:
        raise NotImplementedError

    async def inspect(self) -> str:
        if not self.tables:
            self.tables = await self.get_all_tables()
        result = "from tortoise import Model, fields\n\n\n"
        tables = []
        for table in self.tables:
            columns = await self.get_columns(table)
            fields = []
            model = self._table_template.format(table=table.title().replace("_", ""))
            for column in columns:
                field = self.field_map[column.data_type](**column.translate())
                fields.append("    " + field)
            tables.append(model + "\n".join(fields))
        return result + "\n\n\n".join(tables)

    async def get_columns(self, table: str) -> list[Column]:
        raise NotImplementedError

    async def get_all_tables(self) -> list[str]:
        raise NotImplementedError

    @classmethod
    def decimal_field(cls, **kwargs) -> str:
        return "{name} = fields.DecimalField({pk}{index}{length}{null}{default}{comment})".format(
            **kwargs
        )

    @classmethod
    def time_field(cls, **kwargs) -> str:
        return "{name} = fields.TimeField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def date_field(cls, **kwargs) -> str:
        return "{name} = fields.DateField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def float_field(cls, **kwargs) -> str:
        return "{name} = fields.FloatField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def datetime_field(cls, **kwargs) -> str:
        return "{name} = fields.DatetimeField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def text_field(cls, **kwargs) -> str:
        return "{name} = fields.TextField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def char_field(cls, **kwargs) -> str:
        return "{name} = fields.CharField({pk}{index}{length}{null}{default}{comment})".format(
            **kwargs
        )

    @classmethod
    def int_field(cls, **kwargs) -> str:
        return "{name} = fields.IntField({pk}{index}{comment})".format(**kwargs)

    @classmethod
    def smallint_field(cls, **kwargs) -> str:
        return "{name} = fields.SmallIntField({pk}{index}{comment})".format(**kwargs)

    @classmethod
    def bigint_field(cls, **kwargs) -> str:
        return "{name} = fields.BigIntField({pk}{index}{default}{comment})".format(**kwargs)

    @classmethod
    def bool_field(cls, **kwargs) -> str:
        return "{name} = fields.BooleanField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def uuid_field(cls, **kwargs) -> str:
        return "{name} = fields.UUIDField({pk}{index}{default}{comment})".format(**kwargs)

    @classmethod
    def json_field(cls, **kwargs) -> str:
        return "{name} = fields.JSONField({null}{default}{comment})".format(**kwargs)

    @classmethod
    def binary_field(cls, **kwargs) -> str:
        return "{name} = fields.BinaryField({null}{default}{comment})".format(**kwargs)
