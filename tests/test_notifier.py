"""Testes de telegram/notifier.py. requests.post é substituído por um
fake — nenhuma chamada de rede real é feita, nenhuma mensagem real é
postada no Telegram."""

import requests

from telegram import notifier


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def test_format_price_uses_brl_pt_br_format():
    assert notifier._format_price(1234.5, "BRL") == "R$ 1.234,50"
    assert notifier._format_price(49.9, None) == "R$ 49,90"


def test_build_message_contains_key_fields():
    message = notifier.build_message(
        name="Echo Dot",
        old_price=400.0,
        new_price=329.0,
        percent=17.75,
        affiliate_link="https://www.amazon.com.br/dp/B09B8VGCR8?tag=meutag-20",
    )

    assert "Echo Dot" in message
    assert "R$ 400,00" in message
    assert "R$ 329,00" in message
    assert "18%" in message  # 17.75 arredondado
    assert "meutag-20" in message


def test_send_price_alert_success(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "-1001234567890")

    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(200)

    monkeypatch.setattr(notifier.requests, "post", fake_post)

    sent = notifier.send_price_alert(
        name="Echo Dot",
        old_price=400.0,
        new_price=329.0,
        percent=17.75,
        affiliate_link="https://www.amazon.com.br/dp/B09B8VGCR8",
    )

    assert sent is True
    assert captured["url"] == "https://api.telegram.org/botfake-token/sendMessage"
    assert captured["json"]["chat_id"] == "-1001234567890"
    assert captured["json"]["parse_mode"] == "HTML"
    assert "Echo Dot" in captured["json"]["text"]


def test_send_price_alert_without_credentials_does_not_call_telegram(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "")

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("requests.post não deveria ser chamado sem credenciais")

    monkeypatch.setattr(notifier.requests, "post", _unexpected)

    sent = notifier.send_price_alert(
        name="Echo Dot", old_price=400.0, new_price=329.0,
        percent=17.75, affiliate_link="https://example.com",
    )

    assert sent is False


def test_send_price_alert_network_error_returns_false_without_raising(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "-1001234567890")

    def fake_post(*_args, **_kwargs):
        raise requests.ConnectionError("falha de rede simulada")

    monkeypatch.setattr(notifier.requests, "post", fake_post)

    sent = notifier.send_price_alert(
        name="Echo Dot", old_price=400.0, new_price=329.0,
        percent=17.75, affiliate_link="https://example.com",
    )

    assert sent is False


def test_send_price_alert_http_error_returns_false_without_raising(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "-1001234567890")
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **kw: FakeResponse(401))

    sent = notifier.send_price_alert(
        name="Echo Dot", old_price=400.0, new_price=329.0,
        percent=17.75, affiliate_link="https://example.com",
    )

    assert sent is False
