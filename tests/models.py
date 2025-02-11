from __future__ import annotations

import datetime
import uuid
from enum import IntEnum

from tortoise import Model, fields
from tortoise.contrib.mysql.indexes import FullTextIndex
from tortoise.contrib.postgres.indexes import HashIndex
from tortoise.indexes import Index

from tests._utils import Dialect
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
    username = fields.CharField(max_length=20, unique=True)
    password = fields.CharField(max_length=100)
    last_login = fields.DatetimeField(description="Last Login", default=datetime.datetime.now)
    is_active = fields.BooleanField(default=True, description="Is Active")
    is_superuser = fields.BooleanField(default=False, description="Is SuperUser")
    intro = fields.TextField(default="")
    longitude = fields.DecimalField(max_digits=10, decimal_places=8)

    products: fields.ManyToManyRelation["Product"]

    class Meta:
        # reverse indexes elements
        indexes = [CustomIndex(fields=("is_superuser",)), Index(fields=("username", "is_active"))]


class Email(Model):
    email_id = fields.IntField(primary_key=True)
    email = fields.CharField(max_length=200, db_index=True)
    is_primary = fields.BooleanField(default=False)
    address = fields.CharField(max_length=200)
    users: fields.ManyToManyRelation[User] = fields.ManyToManyField("models.User")
    config: fields.OneToOneRelation["Config"] = fields.OneToOneField("models.Config")


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

    class Meta:
        if Dialect.is_postgres():
            indexes = [HashIndex(fields=("slug",))]
        elif Dialect.is_mysql():
            indexes = [FullTextIndex(fields=("slug",))]  # type:ignore
        else:
            indexes = [Index(fields=("slug",))]  # type:ignore


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
    type: int = fields.IntEnumField(
        ProductType, description="Product Type", source_field="type_db_alias"
    )
    pic = fields.CharField(max_length=200)
    body = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    is_deleted = fields.BooleanField(default=False)

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

    email: fields.OneToOneRelation["Email"]


class NewModel(Model):
    name = fields.CharField(max_length=50)
