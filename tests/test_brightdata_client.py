"""Testes de scraper/brightdata_client.py, focados no retry exponencial
para falhas transitórias (erro de rede, HTTP 5xx) e no não-retry de
erros 4xx (falha do request em si — tentar de novo não ajuda). A
requests.Session real é substituída por um fake — nenhuma chamada de
rede é feita."""

import requests
import pytest

from scraper.brightdata_client import MAX_RETRIES, BrightDataClient, BrightDataError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


class FakeSession:
    """Retorna respostas/exceções de uma fila, uma por chamada de
    .request(), na ordem em que foram enfileiradas."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("scraper.brightdata_client.time.sleep", lambda *_: None)
    return BrightDataClient(api_token="fake-token", dataset_id="gd_fake")


def _with_responses(client, responses):
    fake_session = FakeSession(responses)
    client._session = fake_session
    return fake_session


def test_trigger_succeeds_on_first_try(client):
    session = _with_responses(client, [FakeResponse(200, {"snapshot_id": "s1"})])

    assert client.trigger_collection(["https://example.com/p1"]) == "s1"
    assert session.calls == 1


def test_network_error_is_retried_then_succeeds(client):
    session = _with_responses(client, [
        requests.ConnectionError("falha de rede simulada"),
        FakeResponse(200, {"snapshot_id": "s1"}),
    ])

    assert client.trigger_collection(["https://example.com/p1"]) == "s1"
    assert session.calls == 2


def test_5xx_is_retried_then_succeeds(client):
    session = _with_responses(client, [
        FakeResponse(503, text="service unavailable"),
        FakeResponse(200, {"snapshot_id": "s1"}),
    ])

    assert client.trigger_collection(["https://example.com/p1"]) == "s1"
    assert session.calls == 2


def test_4xx_fails_immediately_without_retry(client):
    session = _with_responses(client, [FakeResponse(400, text="bad request")])

    with pytest.raises(BrightDataError):
        client.trigger_collection(["https://example.com/p1"])

    assert session.calls == 1


def test_exhausts_retries_and_raises_brightdata_error(client):
    session = _with_responses(client, [FakeResponse(503, text="down")] * MAX_RETRIES)

    with pytest.raises(BrightDataError):
        client.trigger_collection(["https://example.com/p1"])

    assert session.calls == MAX_RETRIES


def test_missing_snapshot_id_raises_without_retry(client):
    session = _with_responses(client, [FakeResponse(200, {"unexpected": "shape"})])

    with pytest.raises(BrightDataError):
        client.trigger_collection(["https://example.com/p1"])

    assert session.calls == 1


def test_wait_for_snapshot_returns_when_ready(client):
    session = _with_responses(client, [
        FakeResponse(200, {"status": "running"}),
        FakeResponse(200, {"status": "ready"}),
    ])

    client.wait_for_snapshot("snap1")

    assert session.calls == 2


def test_wait_for_snapshot_raises_on_failed_status(client):
    _with_responses(client, [FakeResponse(200, {"status": "failed"})])

    with pytest.raises(BrightDataError):
        client.wait_for_snapshot("snap1")


def test_get_snapshot_data_returns_list_as_is(client):
    _with_responses(client, [FakeResponse(200, [{"a": 1}, {"a": 2}])])

    assert client.get_snapshot_data("snap1") == [{"a": 1}, {"a": 2}]


def test_get_snapshot_data_wraps_single_dict_in_list(client):
    _with_responses(client, [FakeResponse(200, {"a": 1})])

    assert client.get_snapshot_data("snap1") == [{"a": 1}]
