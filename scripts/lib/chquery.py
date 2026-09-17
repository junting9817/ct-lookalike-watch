"""Read and write the `ct` database inside the NSM lab's ClickHouse container (CLAUDE.md C2).

Everything goes through `docker exec … clickhouse-client`, so no credentials live in this repository and no port is
exposed. Writes are allowed here — unlike `~/HP`, this project owns its database — but only into `ct`.
"""
import json
import os
import shutil
import subprocess

CONTAINER = os.environ.get("CT_CH_CONTAINER", "nsm-clickhouse")
DATABASE = os.environ.get("CT_CH_DATABASE", "ct")


class QueryError(Exception):
    """ClickHouse is unreachable, or the statement failed."""


def _run(arguments: list[str], stdin_text: str | None = None) -> str:
    if shutil.which("docker") is None:
        raise QueryError("docker is not installed")
    command = ["docker", "exec", "-i", CONTAINER, "clickhouse-client", "--database", DATABASE] + arguments
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300,
                                input=stdin_text if stdin_text is not None else "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QueryError(f"could not run clickhouse-client: {exc}") from None
    if result.returncode != 0:
        # clickhouse-client echoes the statement after an error, so pick the exception line rather than the last one
        lines = [line.strip() for line in (result.stderr or "").splitlines() if line.strip()]
        detail = next((line for line in lines if "Exception" in line), lines[0] if lines else "")
        raise QueryError(detail or f"clickhouse-client exited {result.returncode}")
    return result.stdout


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a SELECT and return its rows as dicts."""
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        raise QueryError("query() runs SELECT statements; use insert() to write")
    arguments = ["--format", "JSONEachRow"]
    for name, value in (params or {}).items():
        arguments.append(f"--param_{name}={value}")
    arguments += ["--query", sql]
    return [json.loads(line) for line in _run(arguments).splitlines() if line.strip()]


def scalar(sql: str, params: dict | None = None):
    rows = query(sql, params)
    return next(iter(rows[0].values())) if rows else None


def optimize(table: str) -> None:
    """Merge a ReplacingMergeTree now, so the stored rows match the logical ones.

    Without this the table keeps every re-inserted copy until ClickHouse decides to merge, and `count()` disagrees
    with `uniqExact(domain)` — true but confusing, and it makes "re-running changes nothing" hard to demonstrate.
    These tables are thousands of rows, so the merge is immediate.
    """
    if not all(part.isidentifier() for part in table.split(".")):
        raise QueryError(f"{table!r} is not a table name")
    _run(["--query", f"OPTIMIZE TABLE {table} FINAL"])


def insert(table: str, rows: list[dict]) -> int:
    """Insert rows as JSONEachRow. Returns how many were sent."""
    if not rows:
        return 0
    if not all(part.isidentifier() for part in table.split(".")):
        raise QueryError(f"{table!r} is not a table name")
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    _run(["--query", f"INSERT INTO {table} FORMAT JSONEachRow"], payload)
    return len(rows)
