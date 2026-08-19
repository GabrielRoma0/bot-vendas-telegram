"""Postagem de alertas de queda de preço no Telegram via Bot API."""

import logging

import requests

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _format_price(price: float, currency: str | None) -> str:
    symbol = "R$" if currency in (None, "BRL") else currency
    return f"{symbol} {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_message(
    name: str,
    old_price: float,
    new_price: float,
    percent: float,
    affiliate_link: str,
    currency: str | None = "BRL",
) -> str:
    return (
        f"🔥 <b>Queda de preço!</b>\n\n"
        f"<b>{name}</b>\n\n"
        f"De: <s>{_format_price(old_price, currency)}</s>\n"
        f"Por: <b>{_format_price(new_price, currency)}</b>\n"
        f"Desconto: <b>{percent:.0f}%</b>\n\n"
        f'<a href="{affiliate_link}">Ver oferta</a>'
    )


def send_price_alert(
    name: str,
    old_price: float,
    new_price: float,
    percent: float,
    affiliate_link: str,
    currency: str | None = "BRL",
) -> bool:
    """Envia o alerta ao canal configurado. Retorna True em caso de sucesso,
    False em caso de falha (loga o erro, não lança exceção)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")
        return False

    message = build_message(name, old_price, new_price, percent, affiliate_link, currency)

    try:
        resp = requests.post(
            API_URL.format(token=TELEGRAM_BOT_TOKEN),
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Falha ao enviar mensagem no Telegram: %s", exc)
        return False
