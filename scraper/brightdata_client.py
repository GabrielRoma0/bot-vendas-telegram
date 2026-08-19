"""Cliente HTTP para a Web Scraper API (dataset API) do Bright Data.

Fluxo: dispara uma coleta (trigger) com uma lista de URLs, espera o
snapshot ficar pronto (poll) e baixa o resultado estruturado (snapshot).

Docs: https://docs.brightdata.com/scraping-automation/web-scraper-api
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.brightdata.com/datasets/v3"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 180

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


class BrightDataError(Exception):
    pass


class BrightDataClient:
    def __init__(self, api_token: str, dataset_id: str):
        if not api_token:
            raise BrightDataError("BRIGHTDATA_API_TOKEN não configurado")
        if not dataset_id:
            raise BrightDataError("BRIGHTDATA_AMAZON_DATASET_ID não configurado")
        self.api_token = api_token
        self.dataset_id = dataset_id
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise BrightDataError(f"{exc} — resposta: {resp.text[:500]}") from exc

    def _request(self, method: str, url: str, timeout: float, **kwargs) -> requests.Response:
        """Faz uma requisição HTTP com retry exponencial para falhas
        transitórias (erro de rede ou HTTP 5xx). Erros 4xx (ex: token
        inválido, request malformado) não são retentados — tentar de
        novo não resolve, e só atrasaria a falha."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "Falha de rede em %s %s (tentativa %d/%d): %s",
                    method, url, attempt, MAX_RETRIES, exc,
                )
            else:
                if resp.status_code < 500:
                    self._raise_for_status(resp)
                    return resp
                last_error = BrightDataError(
                    f"HTTP {resp.status_code} — resposta: {resp.text[:500]}"
                )
                logger.warning(
                    "Erro %d do Bright Data em %s %s (tentativa %d/%d)",
                    resp.status_code, method, url, attempt, MAX_RETRIES,
                )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        raise BrightDataError(
            f"Falha em {method} {url} após {MAX_RETRIES} tentativas: {last_error}"
        ) from last_error

    def trigger_collection(self, urls: list[str]) -> str:
        """Dispara a coleta para uma lista de URLs e retorna o snapshot_id."""
        resp = self._request(
            "POST", f"{BASE_URL}/trigger",
            timeout=30,
            params={"dataset_id": self.dataset_id, "include_errors": "true"},
            json=[{"url": url} for url in urls],
        )
        data = resp.json()
        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            raise BrightDataError(f"Resposta sem snapshot_id: {data}")
        return snapshot_id

    def wait_for_snapshot(self, snapshot_id: str) -> None:
        """Aguarda o snapshot ficar pronto (status 'ready')."""
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            resp = self._request("GET", f"{BASE_URL}/progress/{snapshot_id}", timeout=30)
            status = resp.json().get("status")
            if status == "ready":
                return
            if status == "failed":
                raise BrightDataError(f"Snapshot {snapshot_id} falhou")
            time.sleep(POLL_INTERVAL_SECONDS)
        raise BrightDataError(f"Timeout esperando snapshot {snapshot_id}")

    def get_snapshot_data(self, snapshot_id: str) -> list[dict]:
        resp = self._request(
            "GET", f"{BASE_URL}/snapshot/{snapshot_id}",
            timeout=60,
            params={"format": "json"},
        )
        data = resp.json()
        return data if isinstance(data, list) else [data]

    def fetch(self, urls: list[str]) -> list[dict]:
        """Executa o fluxo completo: trigger -> poll -> download."""
        snapshot_id = self.trigger_collection(urls)
        self.wait_for_snapshot(snapshot_id)
        return self.get_snapshot_data(snapshot_id)
