import sys
from typing import List, Optional

from ddlparse import DdlParse
from tortoise import BaseDBAsyncClient


class InspectDb:
    _table_template = "class {table}(Model):\n"
    _field_template_mapping = {
        "INT": "    {field} = fields.IntField({pk}{unique}{comment})",
        "BIGINT": "    {field} = fields.BigIntField({pk}{unique}{comment})",
        "SMALLINT": "    {field} = fields.IntField({pk}{unique}{comment})",
        "TINYINT": "    {field} = fields.BooleanField({null}{default}{comment})",
        "VARCHAR": "    {field} = fields.CharField({pk}{unique}{length}{null}{default}{comment})",
        "LONGTEXT": "    {field} = fields.TextField({null}{default}{comment})",
        "TEXT": "    {field} = fields.TextField({null}{default}{comment})",
        "DATETIME": "    {field} = fields.DatetimeField({null}{default}{comment})",
        "FLOAT": "    {field} = fields.FloatField({null}{default}{comment})",
    }

    def __init__(self, conn: BaseDBAsyncClient, tables: Optional[List[str]] = None):
        self.conn = conn
        self.tables = tables
        self.DIALECT = conn.schema_generator.DIALECT

    async def show_create_tables(self):
        if self.DIALECT == "mysql":
            if not self.tables:
                sql_tables = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{self.conn.database}';"  # nosec: B608
                ret = await self.conn.execute_query(sql_tables)
                self.tables = map(lambda x: x["TABLE_NAME"], ret[1])
            for table in self.tables:
                sql_show_create_table = f"SHOW CREATE TABLE `{table}`"
                ret = await self.conn.execute_query(sql_show_create_table)
                yield ret[1][0]["Create Table"]
        else:
            raise NotImplementedError("Currently only support MySQL")

    async def inspect(self):
        ddl_list = self.show_create_tables()
        result = "from tortoise import Model, fields\n\n\n"
        tables = []
        async for ddl in ddl_list:
            parser = DdlParse(ddl, DdlParse.DATABASE.mysql)
            table = parser.parse()
            name = table.name.title()
            columns = table.columns
            fields = []
            model = self._table_template.format(table=name)
            for column_name, column in columns.items():
                comment = default = length = unique = null = pk = ""
                if column.primary_key:
                    pk = "pk=True, "
                if column.unique:
                    unique = "unique=True, "
                if column.data_type == "VARCHAR":
                    length = f"max_length={column.length}, "
                if not column.not_null:
                    null = "null=True, "
                if column.default is not None:
                    if column.data_type == "TINYINT":
                        default = f"default={'True' if column.default == '1' else 'False'}, "
                    elif column.data_type == "DATETIME":
                        if "CURRENT_TIMESTAMP" in column.default:
                            if "ON UPDATE CURRENT_TIMESTAMP" in ddl:
                                default = "auto_now_add=True, "
                            else:
                                default = "auto_now=True, "
                    else:
                        if column.default == 'NULL':
                            default = "default=None, "
                        else:
                            default = f"default={column.default}, "

                if column.comment:
                    comment = f"description='{column.comment}', "

                field = self._field_template_mapping[column.data_type].format(
                    field=column_name,
                    pk=pk,
                    unique=unique,
                    length=length,
                    null=null,
                    default=default,
                    comment=comment,
                )
                fields.append(field)
            tables.append(model + "\n".join(fields))
        sys.stdout.write(result + "\n\n\n".join(tables))
