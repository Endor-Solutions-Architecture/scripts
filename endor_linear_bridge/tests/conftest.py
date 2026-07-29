import pytest

from endor_linear_bridge.models import build_engine, build_session_factory, create_all


@pytest.fixture
def session_factory(tmp_path):
    """A real SQLite database on disk -- exercises the same driver as production."""
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_all(engine)
    return build_session_factory(engine)


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s
