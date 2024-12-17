import datetime
import uuid
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
    password = fields.CharField(max_length=100)
    last_login = fields.DatetimeField(description="Last Login", default=datetime.datetime.now)
    is_active = fields.BooleanField(default=True, description="Is Active")
    is_superuser = fields.BooleanField(default=False, description="Is SuperUser")
    intro = fields.TextField(default="")
    longitude = fields.DecimalField(max_digits=10, decimal_places=8)

    products: fields.ManyToManyRelation["Product"]


class Email(Model):
    email_id = fields.IntField(primary_key=True)
    email = fields.CharField(max_length=200, db_index=True)
    is_primary = fields.BooleanField(default=False)
    address = fields.CharField(max_length=200)
    users: fields.ManyToManyRelation[User] = fields.ManyToManyField("models.User")


def default_name():
    return uuid.uuid4()


class Category(Model):
    slug = fields.CharField(max_length=100)
    name = fields.CharField(max_length=200, null=True, default=default_name)
    owner: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", description="User"
    )
    title = fields.CharField(max_length=20, unique=False)
    created_at = fields.DatetimeField(auto_now_add=True)


class Product(Model):
    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category", null=False
    )
    users: fields.ManyToManyRelation[User] = fields.ManyToManyField(
        "models.User", related_name="products"
    )
    name = fields.CharField(max_length=50)
    view_num = fields.IntField(description="View Num", default=0)
    sort = fields.IntField()
    is_reviewed = fields.BooleanField(description="Is Reviewed")
    type = fields.IntEnumField(
        ProductType, description="Product Type", source_field="type_db_alias"
    )
    pic = fields.CharField(max_length=200)
    body = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = (("name", "type"),)
        indexes = (("name", "type"),)


class Config(Model):
    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category", through="config_category_map", related_name="category_set"
    )
    label = fields.CharField(max_length=200)
    key = fields.CharField(max_length=20)
    value: dict = fields.JSONField()
    status: Status = fields.IntEnumField(Status)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", description="User"
    )


class NewModel(Model):
    name = fields.CharField(max_length=50)
