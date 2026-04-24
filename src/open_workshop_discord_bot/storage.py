from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class DailyBucket:
    requests_count: int
    files_sent_count: int
    direct_links_count: int
    mod_not_found_count: int
    failed_requests_count: int


@dataclass(frozen=True, slots=True)
class StatisticsSnapshot:
    total_requests: int
    total_files_sent: int
    total_direct_links: int
    total_mod_not_found: int
    total_failed_requests: int
    statistics_days: int
    since_date: str | None
    today: DailyBucket
    last_7_days: DailyBucket


class StatisticsStorage:
    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def record_download_outcome(self, outcome: str) -> None:
        await asyncio.to_thread(self._record_download_outcome_sync, outcome, _today_iso())

    async def fetch_statistics(self) -> StatisticsSnapshot:
        return await asyncio.to_thread(self._fetch_statistics_sync, _today_iso())

    def _initialize_sync(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_download_stats (
                    stat_date TEXT PRIMARY KEY,
                    requests_count INTEGER NOT NULL DEFAULT 0,
                    files_sent_count INTEGER NOT NULL DEFAULT 0,
                    direct_links_count INTEGER NOT NULL DEFAULT 0,
                    mod_not_found_count INTEGER NOT NULL DEFAULT 0,
                    failed_requests_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _record_download_outcome_sync(self, outcome: str, stat_date: str) -> None:
        column = _outcome_column(outcome)
        files_sent_count = 1 if column == "files_sent_count" else 0
        direct_links_count = 1 if column == "direct_links_count" else 0
        mod_not_found_count = 1 if column == "mod_not_found_count" else 0
        failed_requests_count = 1 if column == "failed_requests_count" else 0
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_download_stats (
                    stat_date,
                    requests_count,
                    files_sent_count,
                    direct_links_count,
                    mod_not_found_count,
                    failed_requests_count
                )
                VALUES (?, 1, ?, ?, ?, ?)
                ON CONFLICT(stat_date) DO UPDATE SET
                    requests_count = requests_count + 1,
                    files_sent_count = files_sent_count + CASE WHEN ? = 'files_sent_count' THEN 1 ELSE 0 END,
                    direct_links_count = direct_links_count + CASE WHEN ? = 'direct_links_count' THEN 1 ELSE 0 END,
                    mod_not_found_count = mod_not_found_count + CASE WHEN ? = 'mod_not_found_count' THEN 1 ELSE 0 END,
                    failed_requests_count = failed_requests_count + CASE WHEN ? = 'failed_requests_count' THEN 1 ELSE 0 END
                """,
                (
                    stat_date,
                    files_sent_count,
                    direct_links_count,
                    mod_not_found_count,
                    failed_requests_count,
                    column,
                    column,
                    column,
                    column,
                ),
            )

    def _fetch_statistics_sync(self, today_iso: str) -> StatisticsSnapshot:
        with self._connect() as connection:
            totals_row = connection.execute(
                """
                SELECT
                    COALESCE(SUM(requests_count), 0),
                    COALESCE(SUM(files_sent_count), 0),
                    COALESCE(SUM(direct_links_count), 0),
                    COALESCE(SUM(mod_not_found_count), 0),
                    COALESCE(SUM(failed_requests_count), 0),
                    COUNT(*),
                    MIN(stat_date)
                FROM daily_download_stats
                """
            ).fetchone()
            today_row = connection.execute(
                """
                SELECT
                    requests_count,
                    files_sent_count,
                    direct_links_count,
                    mod_not_found_count,
                    failed_requests_count
                FROM daily_download_stats
                WHERE stat_date = ?
                """,
                (today_iso,),
            ).fetchone()
            last_7_days_row = connection.execute(
                """
                SELECT
                    COALESCE(SUM(requests_count), 0),
                    COALESCE(SUM(files_sent_count), 0),
                    COALESCE(SUM(direct_links_count), 0),
                    COALESCE(SUM(mod_not_found_count), 0),
                    COALESCE(SUM(failed_requests_count), 0)
                FROM daily_download_stats
                WHERE stat_date BETWEEN date(?, '-6 day') AND date(?)
                """,
                (today_iso, today_iso),
            ).fetchone()

        assert totals_row is not None
        return StatisticsSnapshot(
            total_requests=int(totals_row[0]),
            total_files_sent=int(totals_row[1]),
            total_direct_links=int(totals_row[2]),
            total_mod_not_found=int(totals_row[3]),
            total_failed_requests=int(totals_row[4]),
            statistics_days=int(totals_row[5]),
            since_date=str(totals_row[6]) if totals_row[6] is not None else None,
            today=_bucket_from_row(today_row),
            last_7_days=_bucket_from_row(last_7_days_row),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _bucket_from_row(row: tuple[object, ...] | None) -> DailyBucket:
    if row is None:
        return DailyBucket(0, 0, 0, 0, 0)
    return DailyBucket(*(int(value) for value in row))


def _outcome_column(outcome: str) -> str:
    mapping = {
        "file_sent": "files_sent_count",
        "direct_link_sent": "direct_links_count",
        "mod_not_found": "mod_not_found_count",
        "failed_request": "failed_requests_count",
    }
    try:
        return mapping[outcome]
    except KeyError as exc:
        raise ValueError(f"Unsupported statistics outcome: {outcome!r}") from exc


def _today_iso() -> str:
    return datetime.now().astimezone().date().isoformat()
