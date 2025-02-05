import uuid

import pytest
from models import Foo
from tortoise.exceptions import IntegrityError


@pytest.mark.asyncio
async def test_allow_duplicate() -> None:
    await Foo.all().delete()
    await Foo.create(name="foo")
    obj = await Foo.create(name="foo")
    assert (await Foo.all().count()) == 2
    await obj.delete()


@pytest.mark.asyncio
async def test_unique_is_true() -> None:
    with pytest.raises(IntegrityError):
        await Foo.create(name="foo")


@pytest.mark.asyncio
async def test_add_unique_field() -> None:
    if not await Foo.filter(age=0).exists():
        await Foo.create(name="0_" + uuid.uuid4().hex, age=0)
    with pytest.raises(IntegrityError):
        await Foo.create(name=uuid.uuid4().hex, age=0)


@pytest.mark.asyncio
async def test_drop_unique_field() -> None:
    name = "1_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    assert await Foo.filter(name=name).exists()


@pytest.mark.asyncio
async def test_with_age_field() -> None:
    name = "2_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    obj = await Foo.get(name=name)
    assert obj.age == 0


@pytest.mark.asyncio
async def test_without_age_field() -> None:
    name = "3_" + uuid.uuid4().hex
    await Foo.create(name=name, age=0)
    obj = await Foo.get(name=name)
    assert getattr(obj, "age", None) is None


@pytest.mark.asyncio
async def test_m2m_with_custom_through() -> None:
    from models import FooGroup, Group

    name = "4_" + uuid.uuid4().hex
    foo = await Foo.create(name=name)
    group = await Group.create(name=name + "1")
    await FooGroup.all().delete()
    await foo.groups.add(group)
    foo_group = await FooGroup.get(foo=foo, group=group)
    assert not foo_group.is_active


@pytest.mark.asyncio
async def test_add_m2m_field_after_init_db() -> None:
    from models import Group

    name = "5_" + uuid.uuid4().hex
    foo = await Foo.create(name=name)
    group = await Group.create(name=name + "1")
    await foo.groups.add(group)
    assert (await group.users.all().first()) == foo
