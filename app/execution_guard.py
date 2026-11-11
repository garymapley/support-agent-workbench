from contextlib import contextmanager
from threading import Lock


class ThreadBusyError(RuntimeError):
    pass


_registry_lock = Lock()
_thread_locks: dict[str, Lock] = {}


@contextmanager
def guard_thread(thread_id: str):
    """阻止同一 Agent thread 被两个请求同时推进。"""

    with _registry_lock:
        thread_lock = _thread_locks.setdefault(thread_id, Lock())
    if not thread_lock.acquire(blocking=False):
        raise ThreadBusyError(f"Agent thread {thread_id} 正在运行")
    try:
        yield
    finally:
        thread_lock.release()
        with _registry_lock:
            if not thread_lock.locked():
                _thread_locks.pop(thread_id, None)
