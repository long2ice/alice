from typing import TYPE_CHECKING, List, Type

from tortoise.backends.mysql.schema_generator import MySQLSchemaGenerator

from aerich.ddl import BaseDDL

if TYPE_CHECKING:
    from tortoise import Model  # noqa:F401


class MysqlDDL(BaseDDL):
    schema_generator_cls = MySQLSchemaGenerator
    DIALECT = MySQLSchemaGenerator.DIALECT
    _DROP_TABLE_TEMPLATE = "DROP TABLE IF EXISTS `{table_name}`"
    _ADD_COLUMN_TEMPLATE = "ALTER TABLE `{table_name}` ADD {column}"
    _ALTER_DEFAULT_TEMPLATE = "ALTER TABLE `{table_name}` ALTER COLUMN `{column}` {default}"
    _CHANGE_COLUMN_TEMPLATE = (
        "ALTER TABLE `{table_name}` CHANGE {old_column_name} {new_column_name} {new_column_type}"
    )
    _DROP_COLUMN_TEMPLATE = "ALTER TABLE `{table_name}` DROP COLUMN `{column_name}`"
    _RENAME_COLUMN_TEMPLATE = (
        "ALTER TABLE `{table_name}` RENAME COLUMN `{old_column_name}` TO `{new_column_name}`"
    )
    _ADD_INDEX_TEMPLATE = (
        "ALTER TABLE `{table_name}` ADD {unique}INDEX `{index_name}` ({column_names})"
    )
    _DROP_INDEX_TEMPLATE = "ALTER TABLE `{table_name}` DROP INDEX `{index_name}`"
    _ADD_FK_TEMPLATE = "ALTER TABLE `{table_name}` ADD CONSTRAINT `{fk_name}` FOREIGN KEY (`{db_column}`) REFERENCES `{table}` (`{field}`) ON DELETE {on_delete}"
    _DROP_FK_TEMPLATE = "ALTER TABLE `{table_name}` DROP FOREIGN KEY `{fk_name}`"
    _M2M_TABLE_TEMPLATE = (
        "CREATE TABLE `{table_name}` (\n"
        "    `{backward_key}` {backward_type} NOT NULL REFERENCES `{backward_table}` (`{backward_field}`) ON DELETE CASCADE,\n"
        "    `{forward_key}` {forward_type} NOT NULL REFERENCES `{forward_table}` (`{forward_field}`) ON DELETE CASCADE\n"
        "){extra}{comment}"
    )
    _MODIFY_COLUMN_TEMPLATE = "ALTER TABLE `{table_name}` MODIFY COLUMN {column}"
    _RENAME_TABLE_TEMPLATE = "ALTER TABLE `{old_table_name}` RENAME TO `{new_table_name}`"

    def _index_name(self, unique: bool, model: "Type[Model]", field_names: List[str]) -> str:
        if unique:
            if len(field_names) == 1:
                # Example: `email = CharField(max_length=50, unique=True)`
                # Generate schema: `"email" VARCHAR(10) NOT NULL UNIQUE`
                # Unique index key is the same as field name: `email`
                return field_names[0]
            index_prefix = "uid"
        else:
            index_prefix = "idx"
        return self.schema_generator._generate_index_name(index_prefix, model, field_names)

    def add_index(self, model: "Type[Model]", field_names: List[str], unique=False) -> str:
        return self._ADD_INDEX_TEMPLATE.format(
            unique="UNIQUE " if unique else "",
            index_name=self._index_name(unique, model, field_names),
            table_name=model._meta.db_table,
            column_names=", ".join(self.schema_generator.quote(f) for f in field_names),
        )

    def drop_index(self, model: "Type[Model]", field_names: List[str], unique=False) -> str:
        return self._DROP_INDEX_TEMPLATE.format(
            index_name=self._index_name(unique, model, field_names),
            table_name=model._meta.db_table,
        )
