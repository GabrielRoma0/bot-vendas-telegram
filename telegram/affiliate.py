"""Conversão de links de produto em links de afiliado."""

from urllib.parse import urlparse, urlunparse

from config.settings import AMAZON_AFFILIATE_TAG


def to_amazon_affiliate_link(url: str, tag: str = AMAZON_AFFILIATE_TAG) -> str:
    """Adiciona (ou substitui) o parâmetro `tag` de afiliado da Amazon.

    Se nenhuma tag estiver configurada, retorna a URL original sem
    modificação — melhor postar sem afiliado do que quebrar o link.
    """
    if not tag:
        return url

    parsed = urlparse(url)
    query = f"tag={tag}"
    return urlunparse(parsed._replace(query=query))
