"""PostgREST write helpers for ingestion (Prefer: return=minimal)."""

from __future__ import annotations

from postgrest import ReturnMethod


def upsert_minimal(db, table: str, row: dict, *, on_conflict: str) -> None:
    db.table(table).upsert(row, on_conflict=on_conflict, returning=ReturnMethod.minimal).execute()


def upsert_minimal_batch(db, table: str, rows: list[dict], *, on_conflict: str) -> None:
    db.table(table).upsert(rows, on_conflict=on_conflict, returning=ReturnMethod.minimal).execute()


def insert_minimal(db, table: str, row: dict) -> None:
    db.table(table).insert(row, returning=ReturnMethod.minimal).execute()


def update_minimal(db, table: str, values: dict, *, column: str, values_in: list) -> None:
    db.table(table).update(values, returning=ReturnMethod.minimal).in_(column, values_in).execute()
