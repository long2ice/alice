import datetime
from enum import IntEnum

from tortoise import Model, fields


class ProductType(IntEnum):
    article = 1
    page = 2


class PermissionAction(IntEnum):
    create = 1
    delete = 2
    update = 3
    read = 4


class Status(IntEnum):
    on = 1
    off = 0


class User(Model):
    username = fields.CharField(max_length=20, unique=True)
    password = fields.CharField(max_length=200)
    last_login = fields.DatetimeField(description="Last Login", default=datetime.datetime.now)
    is_active = fields.BooleanField(default=True, description="Is Active")
    is_superuser = fields.BooleanField(default=False, description="Is SuperUser")
    avatar = fields.CharField(max_length=200, default="")
    intro = fields.TextField(default="")


class Email(Model):
    email = fields.CharField(max_length=200)
    is_primary = fields.BooleanField(default=False)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models_second.User", db_constraint=False
    )


class Category(Model):
    slug = fields.CharField(max_length=200)
    name = fields.CharField(max_length=200)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models_second.User", description="User"
    )
    created_at = fields.DatetimeField(auto_now_add=True)


class Product(Model):
    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models_second.Category"
    )
    name = fields.CharField(max_length=50)
    view_num = fields.IntField(description="View Num")
    sort = fields.IntField()
    is_reviewed = fields.BooleanField(description="Is Reviewed")
    type: int = fields.IntEnumField(
        ProductType, description="Product Type", source_field="type_db_alias"
    )
    image = fields.CharField(max_length=200)
    body = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)


class Config(Model):
    label = fields.CharField(max_length=200)
    key = fields.CharField(max_length=20)
    value: dict = fields.JSONField()
    status: Status = fields.IntEnumField(Status, default=Status.on)
