import sys
from typing import List, Optional

from ddlparse import DdlParse
from tortoise import BaseDBAsyncClient


class InspectDb:
    _table_template = "class {table}(Model):\n"
    _field_template_mapping = {
        # Numerical type
        "TINYINT": "{field} = fields.BooleanField({null}{default}{comment})",
        "SMALLINT": "{field} = fields.SmallIntField({pk}{unique}{comment})",
        "INT": "{field} = fields.IntField({pk}{unique}{comment})",
        "BIGINT": "{field} = fields.SmallIntField({pk}{unique}{comment})",
        "FLOAT": "{field} = fields.FloatField({null}{default}{comment})",
        "DECIMAL": "{field} = fields.DecimalField({null}{default}{other})",  # 新增
        "DOUBLE": "{field} = fields.FloatField({null}{default}{comment})",  # 新增

        # String type
        "CHAR": "{field} = fields.CharField({pk}{unique}{length}{null}{default}{comment})",  # 新增
        "VARCHAR": "{field} = fields.CharField({pk}{unique}{length}{null}{default}{comment})",
        "LONGTEXT": "{field} = fields.TextField({null}{default}{comment})",
        "TEXT": "{field} = fields.TextField({null}{default}{comment})",

        # Date and time type
        "DATETIME": "{field} = fields.DatetimeField({null}{default}{comment})",
        "TIME": "{field} = fields.TimeDeltaField({null}{default}{comment})"  # 新增
    }
    _text = """
     _____                           _      _ _     
    |_   _|                         | |    | | |    
      | |  _ __  ___ _ __   ___  ___| |_ __| | |__  
      | | | '_ \/ __| '_ \ / _ \/ __| __/ _` | '_ \ 
     _| |_| | | \__ \ |_) |  __/ (__| || (_| | |_) |
    |_____|_| |_|___/ .__/ \___|\___|\__\__,_|_.__/ 
                    | |                             
                    |_|                             \n\n\n"""

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
                sql_show_create_table = f"SHOW CREATE TABLE {table}"
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
                other = {}

                if column.data_type == "VARCHAR":
                    length = f"max_length={column.length}, "
                elif column.data_type == "CHAR":
                    length = f"max_length={column.length}, "
                elif column.data_type == "DECIMAL":
                    other['max_digits'] = column.length
                    other['decimal_places'] = column.scale

                if column.default is not None:
                    if column.data_type == "TINYINT":
                        default = f"default={'True' if column.default == '1' else 'False'}, "
                    elif column.data_type == "DATETIME":
                        if "CURRENT_TIMESTAMP" in column.default:
                            if "ON UPDATE CURRENT_TIMESTAMP" in ddl:
                                default = "auto_now_add=True, "
                            else:
                                default = "auto_now=True, "
                    elif column.default != "NULL":
                        default = f'default={column.default}, '

                if not column.not_null:
                    null = "null=True, "

                if column.primary_key:
                    pk = "pk=True, "

                if column.unique:
                    unique = "unique=True, "

                if column.comment:
                    comment = f"description='{column.comment}', "

                try:
                    field = self._field_template_mapping[column.data_type].format(
                        field=column_name,
                        pk=pk,
                        unique=unique,
                        length=length,
                        null=null,
                        default=default,
                        comment=comment,
                        other=', '.join([f'{parameter}={value}' for parameter, value in other.items()])
                    )
                # Avoid the need to manually create the entire table because a certain data type is not supported
                except KeyError:
                    field = f"{column_name} = The {column.data_type} data type type is not currently supported, please add it manually."
                fields.append(field)
            tables.append(model + "    " + "\n    ".join(fields))
        sys.stdout.write(self._text)
        sys.stdout.write(result + "\n\n\n".join(tables) + '\n\n')
