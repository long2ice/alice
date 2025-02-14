from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
import pytest_asyncio
import settings
from tortoise import Tortoise, connections


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    policy = asyncio.get_event_loop_policy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    res._close = res.close  # type:ignore[attr-defined]
    res.close = lambda: None  # type:ignore[method-assign]

    yield res

    res._close()  # type:ignore[attr-defined]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def api(event_loop, request):
    await Tortoise.init(config=settings.TORTOISE_ORM)
    request.addfinalizer(lambda: event_loop.run_until_complete(connections.close_all(discard=True)))
