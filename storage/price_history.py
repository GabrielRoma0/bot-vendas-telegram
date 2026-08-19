"""Histórico de preços em SQLite: salva cada leitura de preço e compara
com a última leitura salva para decidir se houve uma queda relevante."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    url TEXT NOT NULL,
    name TEXT,
    price REAL NOT NULL,
    currency TEXT,
    availability TEXT,
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id
    ON price_history (product_id, checked_at);
"""


@dataclass
class PriceDrop:
    is_drop: bool
    previous_price: float | None
    new_price: float
    percent: float | None


class PriceHistoryStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_last_price(self, product_id: str) -> float | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT price FROM price_history
                   WHERE product_id = ?
                   ORDER BY checked_at DESC LIMIT 1""",
                (product_id,),
            ).fetchone()
        return row[0] if row else None

    def save_price(
        self,
        product_id: str,
        url: str,
        name: str | None,
        price: float,
        currency: str | None,
        availability: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO price_history
                   (product_id, url, name, price, currency, availability, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    url,
                    name,
                    price,
                    currency,
                    availability,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def check_price_drop(
        self, product_id: str, new_price: float, threshold_percent: float
    ) -> PriceDrop:
        previous_price = self.get_last_price(product_id)
        if previous_price is None or previous_price <= 0:
            return PriceDrop(
                is_drop=False, previous_price=previous_price,
                new_price=new_price, percent=None,
            )

        percent = (previous_price - new_price) / previous_price * 100
        is_drop = percent >= threshold_percent
        return PriceDrop(
            is_drop=is_drop, previous_price=previous_price,
            new_price=new_price, percent=percent,
        )
