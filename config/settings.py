"""Carrega configuração do projeto a partir de variáveis de ambiente e do
arquivo config/products.json."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = BASE_DIR / "config" / "products.json"
DB_PATH = BASE_DIR / "data" / "price_history.db"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

BRIGHTDATA_API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN", "")
BRIGHTDATA_AMAZON_DATASET_ID = os.getenv("BRIGHTDATA_AMAZON_DATASET_ID", "")

AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")

# `os.getenv(..., "15")` não cobre o caso da var existir mas vazia (ex: uma
# `vars.X` do GitHub Actions não cadastrada resolve para string vazia, não
# para ausente) — por isso o fallback é aplicado com `or` em vez de default.
PRICE_DROP_THRESHOLD_PERCENT = float(os.getenv("PRICE_DROP_THRESHOLD_PERCENT") or "15")


@dataclass(frozen=True)
class Product:
    id: str
    url: str
    name: str | None = None


def load_products() -> list[Product]:
    with open(PRODUCTS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return [Product(id=item["id"], url=item["url"], name=item.get("name")) for item in raw]
