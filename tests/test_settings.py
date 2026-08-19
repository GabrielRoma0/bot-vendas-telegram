"""Testes de config/settings.py, com foco no bug de regressão em que
PRICE_DROP_THRESHOLD_PERCENT chegava como string vazia (não ausente) via
`vars.X` do GitHub Actions quando a Repository Variable não é cadastrada,
e o default do getenv() nunca era aplicado."""

import importlib

import pytest


@pytest.fixture
def reload_settings(monkeypatch):
    """Recarrega config.settings após alterar variáveis de ambiente,
    sem deixar o .env local (se existir) interferir no resultado."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)

    def _reload():
        import config.settings as settings

        return importlib.reload(settings)

    return _reload


def test_threshold_defaults_to_15_when_env_var_absent(monkeypatch, reload_settings):
    monkeypatch.delenv("PRICE_DROP_THRESHOLD_PERCENT", raising=False)

    settings = reload_settings()

    assert settings.PRICE_DROP_THRESHOLD_PERCENT == 15.0


def test_threshold_defaults_to_15_when_env_var_is_empty_string(monkeypatch, reload_settings):
    # Regressão: vars.PRICE_DROP_THRESHOLD_PERCENT no GitHub Actions resolve
    # para "" (não ausente) quando a Repository Variable não é cadastrada.
    monkeypatch.setenv("PRICE_DROP_THRESHOLD_PERCENT", "")

    settings = reload_settings()

    assert settings.PRICE_DROP_THRESHOLD_PERCENT == 15.0


def test_threshold_respects_explicit_value(monkeypatch, reload_settings):
    monkeypatch.setenv("PRICE_DROP_THRESHOLD_PERCENT", "10")

    settings = reload_settings()

    assert settings.PRICE_DROP_THRESHOLD_PERCENT == 10.0


def test_load_products_reads_products_json(reload_settings):
    settings = reload_settings()

    products = settings.load_products()

    assert len(products) >= 1
    assert all(p.id and p.url for p in products)
