from typing import Optional, Type

from bankpromos.scrapers.base_public import BasePublicScraper

_SCRAPERS: dict[str, Type[BasePublicScraper]] = {}


def register_scraper(bank_id: str):
    def decorator(cls: Type[BasePublicScraper]):
        _SCRAPERS[bank_id] = cls
        return cls
    return decorator


def get_scraper(bank_id: str, **kwargs) -> BasePublicScraper:
    if bank_id not in _SCRAPERS:
        available = ", ".join(_SCRAPERS.keys())
        raise ValueError(f"Unknown bank: {bank_id}. Available: {available}")
    return _SCRAPERS[bank_id](**kwargs)


def list_scrapers() -> list[str]:
    return sorted(_SCRAPERS.keys())


from bankpromos.scrapers.py import (
    py_sudameris,
    py_ueno,
    py_itau,
    py_continental,
    py_bnf,
)