import datetime
from enum import IntEnum

from tortoise import Model, fields
from tortoise.indexes import Index

from tests.indexes import CustomIndex


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
    username = fields.CharField(max_length=20)
    password = fields.CharField(max_length=200)
    last_login = fields.DatetimeField(description="Last Login", default=datetime.datetime.now)
    is_active = fields.BooleanField(default=True, description="Is Active")
    is_superuser = fields.BooleanField(default=False, description="Is SuperUser")
    avatar = fields.CharField(max_length=200, default="")
    intro = fields.TextField(default="")
    longitude = fields.DecimalField(max_digits=12, decimal_places=9)

    class Meta:
        indexes = [Index(fields=("username", "is_active")), CustomIndex(fields=("is_superuser",))]


class Email(Model):
    email = fields.CharField(max_length=200)
    is_primary = fields.BooleanField(default=False)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", db_constraint=False
    )


class Category(Model):
    slug = fields.CharField(max_length=200)
    name = fields.CharField(max_length=200)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", description="User"
    )
    title = fields.CharField(max_length=20, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        indexes = [Index(fields=("slug",))]


class Product(Model):
    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField("models.Category")
    uid = fields.IntField(source_field="uuid", unique=True)
    name = fields.CharField(max_length=50)
    view_num = fields.IntField(description="View Num")
    sort = fields.IntField()
    is_review = fields.BooleanField(description="Is Reviewed")
    type: int = fields.IntEnumField(
        ProductType, description="Product Type", source_field="type_db_alias"
    )
    image = fields.CharField(max_length=200)
    body = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    is_delete = fields.BooleanField(default=False)


class Config(Model):
    category: fields.ManyToManyRelation[Category] = fields.ManyToManyField("models.Category")
    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category", through="config_category_map", related_name="config_set"
    )
    name = fields.CharField(max_length=100, unique=True)
    label = fields.CharField(max_length=200)
    key = fields.CharField(max_length=20)
    value: dict = fields.JSONField()
    status: Status = fields.IntEnumField(Status, default=Status.on)

    class Meta:
        table = "configs"
