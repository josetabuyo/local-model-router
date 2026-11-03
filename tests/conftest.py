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


def pytest_configure(config):
    config.addinivalue_line("markers", "default_order: run with the real JEV_PROVIDER_ORDER default instead of the pinned d3-era order")
