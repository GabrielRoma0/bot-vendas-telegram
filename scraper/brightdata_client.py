"""Cliente HTTP para a Web Scraper API (dataset API) do Bright Data.

Fluxo: dispara uma coleta (trigger) com uma lista de URLs, espera o
snapshot ficar pronto (poll) e baixa o resultado estruturado (snapshot).

Docs: https://docs.brightdata.com/scraping-automation/web-scraper-api
"""

import time

import requests

BASE_URL = "https://api.brightdata.com/datasets/v3"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 180


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

    def trigger_collection(self, urls: list[str]) -> str:
        """Dispara a coleta para uma lista de URLs e retorna o snapshot_id."""
        resp = self._session.post(
            f"{BASE_URL}/trigger",
            params={"dataset_id": self.dataset_id, "include_errors": "true"},
            json=[{"url": url} for url in urls],
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            raise BrightDataError(f"Resposta sem snapshot_id: {data}")
        return snapshot_id

    def wait_for_snapshot(self, snapshot_id: str) -> None:
        """Aguarda o snapshot ficar pronto (status 'ready')."""
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            resp = self._session.get(f"{BASE_URL}/progress/{snapshot_id}", timeout=30)
            resp.raise_for_status()
            status = resp.json().get("status")
            if status == "ready":
                return
            if status == "failed":
                raise BrightDataError(f"Snapshot {snapshot_id} falhou")
            time.sleep(POLL_INTERVAL_SECONDS)
        raise BrightDataError(f"Timeout esperando snapshot {snapshot_id}")

    def get_snapshot_data(self, snapshot_id: str) -> list[dict]:
        resp = self._session.get(
            f"{BASE_URL}/snapshot/{snapshot_id}",
            params={"format": "json"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [data]

    def fetch(self, urls: list[str]) -> list[dict]:
        """Executa o fluxo completo: trigger -> poll -> download."""
        snapshot_id = self.trigger_collection(urls)
        self.wait_for_snapshot(snapshot_id)
        return self.get_snapshot_data(snapshot_id)
