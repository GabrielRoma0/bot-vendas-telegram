"""Coleta preços de produtos da Amazon usando o Bright Data como fonte
principal. Cada URL que falhar na extração é logada e ignorada — uma
falha isolada não deve interromper o restante da execução.
"""

import logging
from dataclasses import dataclass

from config.settings import BRIGHTDATA_AMAZON_DATASET_ID, BRIGHTDATA_API_TOKEN
from scraper.brightdata_client import BrightDataClient, BrightDataError

logger = logging.getLogger(__name__)


@dataclass
class ProductResult:
    url: str
    name: str | None
    price: float | None
    currency: str | None
    availability: str | None
    success: bool
    error: str | None = None


def _parse_record(url: str, record: dict) -> ProductResult:
    """Mapeia um registro bruto do dataset Amazon do Bright Data para
    ProductResult. Os nomes de campo seguem o schema do dataset "Amazon
    Products" do Bright Data; ajuste aqui se o schema mudar."""
    error = record.get("error") or record.get("error_code")
    if error:
        return ProductResult(
            url=url, name=None, price=None, currency=None,
            availability=None, success=False, error=str(error),
        )

    name = record.get("title") or record.get("name")
    price = record.get("final_price") or record.get("price")
    currency = record.get("currency")
    availability = record.get("availability") or record.get("in_stock")

    if price is None:
        return ProductResult(
            url=url, name=name, price=None, currency=currency,
            availability=availability, success=False,
            error="Preço não encontrado no registro retornado",
        )

    try:
        price = float(price)
    except (TypeError, ValueError):
        return ProductResult(
            url=url, name=name, price=None, currency=currency,
            availability=availability, success=False,
            error=f"Preço em formato inesperado: {price!r}",
        )

    return ProductResult(
        url=url, name=name, price=price, currency=currency,
        availability=availability, success=True,
    )


def fetch_products(urls: list[str]) -> list[ProductResult]:
    """Busca preço/nome/disponibilidade para uma lista de URLs de produto
    da Amazon via Bright Data. Nunca lança exceção por falha de um produto
    individual — erros viram ProductResult(success=False) e são logados."""
    if not urls:
        return []

    try:
        client = BrightDataClient(BRIGHTDATA_API_TOKEN, BRIGHTDATA_AMAZON_DATASET_ID)
        records = client.fetch(urls)
    except BrightDataError as exc:
        logger.error("Falha ao consultar Bright Data: %s", exc)
        return [
            ProductResult(
                url=url, name=None, price=None, currency=None,
                availability=None, success=False, error=str(exc),
            )
            for url in urls
        ]

    records_by_url = {record.get("url", ""): record for record in records}

    results = []
    for url in urls:
        record = records_by_url.get(url)
        if record is None:
            logger.error("Bright Data não retornou dados para %s", url)
            results.append(
                ProductResult(
                    url=url, name=None, price=None, currency=None,
                    availability=None, success=False,
                    error="Sem retorno do Bright Data para esta URL",
                )
            )
            continue

        result = _parse_record(url, record)
        if not result.success:
            logger.error("Falha ao extrair dados de %s: %s", url, result.error)
        results.append(result)

    return results
