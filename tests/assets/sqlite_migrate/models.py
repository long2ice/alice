from tortoise import Model, fields


class Foo(Model):
    name = fields.CharField(max_length=60, db_index=False)
