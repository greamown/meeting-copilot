"""Small test-only async wrapper used when the optional aiosqlite wheel is unavailable."""
import sqlite3
from typing import Any

DatabaseError = sqlite3.DatabaseError
Error = sqlite3.Error
IntegrityError = sqlite3.IntegrityError
NotSupportedError = sqlite3.NotSupportedError
OperationalError = sqlite3.OperationalError
ProgrammingError = sqlite3.ProgrammingError
sqlite_version = sqlite3.sqlite_version
sqlite_version_info = sqlite3.sqlite_version_info


class _TransactionQueue:
    def put_nowait(self, item: tuple[Any, Any]) -> None:
        future, function = item
        try: future.set_result(function())
        except Exception as exc: future.set_exception(exc)


class Cursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None: self._cursor = cursor
    @property
    def description(self): return self._cursor.description
    @property
    def lastrowid(self): return self._cursor.lastrowid
    @property
    def rowcount(self): return self._cursor.rowcount
    async def execute(self, operation: str, parameters: Any = None) -> "Cursor":
        self._cursor.execute(operation, () if parameters is None else parameters); return self
    async def executemany(self, operation: str, parameters: Any) -> "Cursor":
        self._cursor.executemany(operation, parameters); return self
    async def fetchone(self): return self._cursor.fetchone()
    async def fetchmany(self, size: int | None = None): return self._cursor.fetchmany(size or 1)
    async def fetchall(self): return self._cursor.fetchall()
    async def close(self) -> None: self._cursor.close()


class Connection:
    daemon = True
    def __init__(self, database: str, **kwargs: Any) -> None:
        kwargs["check_same_thread"] = False; self._conn = sqlite3.connect(database, **kwargs); self._tx = _TransactionQueue()
    def __await__(self):
        async def ready(): return self
        return ready().__await__()
    @property
    def isolation_level(self): return self._conn.isolation_level
    async def cursor(self) -> Cursor: return Cursor(self._conn.cursor())
    async def execute(self, operation: str, parameters: Any = None) -> Cursor:
        cursor = Cursor(self._conn.cursor()); return await cursor.execute(operation, parameters)
    async def create_function(self, *args: Any, **kwargs: Any) -> None: self._conn.create_function(*args, **kwargs)
    async def rollback(self) -> None: self._conn.rollback()
    async def commit(self) -> None: self._conn.commit()
    async def close(self) -> None: self._conn.close()


def connect(database: str, **kwargs: Any) -> Connection: return Connection(database, **kwargs)
