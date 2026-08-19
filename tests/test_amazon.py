"""Testes de scraper/amazon.py. O BrightDataClient real (que fala HTTP
com o Bright Data) é substituído por um fake — esses testes cobrem só o
mapeamento de registros e o tratamento de falha, não a integração real."""

import pytest

from scraper import amazon
from scraper.brightdata_client import BrightDataError

URL = "https://www.amazon.com.br/dp/B09B8VGCR8"


class FakeClient:
    """Substitui BrightDataClient: retorna registros fixos ou lança
    BrightDataError, sem nenhuma chamada de rede."""

    def __init__(self, records=None, error=None):
        self._records = records or []
        self._error = error

    def __call__(self, *_args, **_kwargs):
        return self

    def fetch(self, _urls):
        if self._error:
            raise self._error
        return self._records


def test_successful_extraction_maps_fields(monkeypatch):
    monkeypatch.setattr(
        amazon,
        "BrightDataClient",
        FakeClient(records=[{
            "input": {"url": URL},
            "title": "Echo Dot (5ª Geração) Preto",
            "final_price": 329,
            "currency": "BRL",
            "availability": "Em estoque",
            "error": None,
        }]),
    )

    [result] = amazon.fetch_products([URL])

    assert result.success is True
    assert result.name == "Echo Dot (5ª Geração) Preto"
    assert result.price == 329.0
    assert result.currency == "BRL"
    assert result.availability == "Em estoque"


def test_record_matched_by_nested_input_url_not_top_level_url(monkeypatch):
    # Regressão: o Bright Data retorna a URL de origem em `input.url`; o
    # campo `url` de topo só é preenchido quando a extração dá certo, e
    # em páginas com erro (ex: 404) vem None — casar só por `url` faz o
    # produto nunca ser encontrado.
    monkeypatch.setattr(
        amazon,
        "BrightDataClient",
        FakeClient(records=[{
            "url": None,
            "input": {"url": URL},
            "error": "The navigation resulted in a dead page (404 status code)",
        }]),
    )

    [result] = amazon.fetch_products([URL])

    assert result.success is False
    assert "404" in result.error


def test_missing_price_field_is_a_failure(monkeypatch):
    monkeypatch.setattr(
        amazon,
        "BrightDataClient",
        FakeClient(records=[{
            "input": {"url": URL},
            "title": "Produto sem preço",
        }]),
    )

    [result] = amazon.fetch_products([URL])

    assert result.success is False
    assert result.price is None


def test_non_numeric_price_is_a_failure(monkeypatch):
    monkeypatch.setattr(
        amazon,
        "BrightDataClient",
        FakeClient(records=[{
            "input": {"url": URL},
            "title": "Produto com preço inválido",
            "final_price": "indisponível",
        }]),
    )

    [result] = amazon.fetch_products([URL])

    assert result.success is False
    assert "inválido" in result.error or "indisponível" in result.error


def test_brightdata_error_fails_every_url_without_raising(monkeypatch):
    monkeypatch.setattr(
        amazon, "BrightDataClient", FakeClient(error=BrightDataError("token inválido"))
    )

    results = amazon.fetch_products([URL, "https://www.amazon.com.br/dp/OUTRO123"])

    assert len(results) == 2
    assert all(r.success is False for r in results)
    assert all("token inválido" in r.error for r in results)


def test_url_missing_from_response_is_a_failure(monkeypatch):
    monkeypatch.setattr(amazon, "BrightDataClient", FakeClient(records=[]))

    [result] = amazon.fetch_products([URL])

    assert result.success is False
    assert "Sem retorno" in result.error


def test_empty_url_list_returns_empty_without_calling_client(monkeypatch):
    def _unexpected(*_args, **_kwargs):
        raise AssertionError("BrightDataClient não deveria ser chamado sem URLs")

    monkeypatch.setattr(amazon, "BrightDataClient", _unexpected)

    assert amazon.fetch_products([]) == []


@pytest.mark.parametrize("error_field", ["error", "error_code"])
def test_record_level_error_field_is_a_failure(monkeypatch, error_field):
    monkeypatch.setattr(
        amazon,
        "BrightDataClient",
        FakeClient(records=[{"input": {"url": URL}, error_field: "algum erro"}]),
    )

    [result] = amazon.fetch_products([URL])

    assert result.success is False
    assert result.error == "algum erro"
