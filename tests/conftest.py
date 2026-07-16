import pytest

from router.server import cache


@pytest.fixture(autouse=True)
def _clear_router_cache():
    """Each test gets a fresh cache — the router module holds a single
    process-wide cache instance, and many tests reuse the same
    'best:<category>' payload with different mocked dispatcher behaviour."""
    cache.clear()
    yield
    cache.clear()
