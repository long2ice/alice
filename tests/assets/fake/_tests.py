import pytest
from models import NewModel
from models_second import Config
from settings import TORTOISE_ORM
from tortoise import Tortoise
from tortoise.exceptions import OperationalError


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def init_connections():
    await Tortoise.init(TORTOISE_ORM)
    try:
        yield
    finally:
        await Tortoise.close_connections()


@pytest.mark.anyio
async def test_init_db():
    m1 = await NewModel.filter(name="")
    assert isinstance(m1, list)
    m2 = await Config.filter(key="")
    assert isinstance(m2, list)
    await NewModel.create(name="")
    await Config.create(key="", label="", value={})


@pytest.mark.anyio
async def test_fake_field_1():
    assert "field_1" in NewModel._meta.fields_map
    assert "field_1" in Config._meta.fields_map
    with pytest.raises(OperationalError):
        await NewModel.create(name="", field_1=1)
    with pytest.raises(OperationalError):
        await Config.create(key="", label="", value={}, field_1=1)

    obj1 = NewModel(name="", field_1=1)
    with pytest.raises(OperationalError):
        await obj1.save()
    obj1 = NewModel(name="")
    with pytest.raises(OperationalError):
        await obj1.save()
    with pytest.raises(OperationalError):
        obj1 = await NewModel.first()
    obj1 = await NewModel.all().first().values("id", "name")
    assert obj1 and obj1["id"]

    obj2 = Config(key="", label="", value={}, field_1=1)
    with pytest.raises(OperationalError):
        await obj2.save()
    obj2 = Config(key="", label="", value={})
    with pytest.raises(OperationalError):
        await obj2.save()
    with pytest.raises(OperationalError):
        obj2 = await Config.first()
    obj2 = await Config.all().first().values("id", "key")
    assert obj2 and obj2["id"]


@pytest.mark.anyio
async def test_fake_field_2():
    assert "field_2" in NewModel._meta.fields_map
    assert "field_2" in Config._meta.fields_map
    with pytest.raises(OperationalError):
        await NewModel.create(name="")
    with pytest.raises(OperationalError):
        await Config.create(key="", label="", value={})
