from system.settings import Session
from contextlib import contextmanager

__all__ = ["session_scope"]


@contextmanager
def _session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def session_scope():
    #  Split the function into 2 parts so that it can be patched when running tests
    return _session_scope()
