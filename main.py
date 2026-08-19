"""Orquestra o monitoramento: coleta preços via Bright Data, compara com
o histórico salvo e posta no Telegram quando houver queda relevante."""

import logging

from config.settings import DB_PATH, PRICE_DROP_THRESHOLD_PERCENT, load_products
from scraper.amazon import fetch_products
from storage.price_history import PriceHistoryStore
from telegram.affiliate import to_amazon_affiliate_link
from telegram.notifier import send_price_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    products = load_products()
    if not products:
        logger.warning("Nenhum produto cadastrado em config/products.json")
        return

    logger.info("Consultando %d produto(s) no Bright Data...", len(products))
    results = fetch_products([p.url for p in products])
    results_by_url = {r.url: r for r in results}

    store = PriceHistoryStore(DB_PATH)

    for product in products:
        result = results_by_url.get(product.url)
        if result is None or not result.success:
            error = result.error if result else "sem resultado"
            logger.error("Ignorando %s: %s", product.id, error)
            continue

        name = product.name or result.name or product.id
        drop = store.check_price_drop(product.id, result.price, PRICE_DROP_THRESHOLD_PERCENT)

        if drop.is_drop:
            logger.info(
                "Queda de %.1f%% em %s: R$%.2f -> R$%.2f",
                drop.percent, name, drop.previous_price, drop.new_price,
            )
            affiliate_link = to_amazon_affiliate_link(product.url)
            sent = send_price_alert(
                name=name,
                old_price=drop.previous_price,
                new_price=drop.new_price,
                percent=drop.percent,
                affiliate_link=affiliate_link,
                currency=result.currency,
            )
            if not sent:
                logger.error("Falha ao notificar queda de preço de %s", name)
        else:
            logger.info("%s: R$%.2f (sem queda relevante)", name, result.price)

        store.save_price(
            product_id=product.id,
            url=product.url,
            name=name,
            price=result.price,
            currency=result.currency,
            availability=result.availability,
        )


if __name__ == "__main__":
    main()
