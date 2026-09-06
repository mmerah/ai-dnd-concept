from asyncio import create_task

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from aidm.app.mcp import MountedLifespan


def _lifespan() -> MountedLifespan:
    return MountedLifespan(StreamableHTTPSessionManager(app=Server("test"), stateless=True))


async def test_manager_stops_from_a_task_other_than_the_one_that_started_it() -> None:
    lifespan = _lifespan()
    await create_task(lifespan.start())
    assert lifespan.manager._task_group is not None  # pyright: ignore[reportPrivateUsage]
    await create_task(lifespan.stop())
    assert lifespan.manager._task_group is None  # pyright: ignore[reportPrivateUsage]


async def test_stop_before_start_is_a_no_op() -> None:
    await _lifespan().stop()
