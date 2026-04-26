import logging
from typing import Dict, List, Optional

from bankpromos.collectors.base import BaseCollector, CollectorResult, Promotion, Source

from bankpromos.collectors.ueno import UenoCollector, collect_ueno
from bankpromos.collectors.continental import ContinentalCollector, collect_continental
from bankpromos.collectors.sudameris import SudamerisCollector, collect_sudameris
from bankpromos.collectors.itau import ItauCollector, collect_itau
from bankpromos.collectors.bnf import BnfCollector, collect_bnf

logger = logging.getLogger(__name__)

COLLECTOR_REGISTRY: Dict[str, type[BaseCollector]] = {
    "ueno": UenoCollector,
    "py_ueno": UenoCollector,
    "continental": ContinentalCollector,
    "py_continental": ContinentalCollector,
    "sudameris": SudamerisCollector,
    "py_sudameris": SudamerisCollector,
    "itau": ItauCollector,
    "py_itau": ItauCollector,
    "bnf": BnfCollector,
    "py_bnf": BnfCollector,
}

COLLECT_FUNCTIONS: Dict[str, callable] = {
    "ueno": collect_ueno,
    "py_ueno": collect_ueno,
    "continental": collect_continental,
    "py_continental": collect_continental,
    "sudameris": collect_sudameris,
    "py_sudameris": collect_sudameris,
    "itau": collect_itau,
    "py_itau": collect_itau,
    "bnf": collect_bnf,
    "py_bnf": collect_bnf,
}


def get_collector(bank_id: str) -> Optional[BaseCollector]:
    bank_id = bank_id.lower().replace("py_", "")
    collector_class = COLLECTOR_REGISTRY.get(bank_id)
    if collector_class:
        return collector_class()
    return None


def collect_bank(bank_id: str) -> CollectorResult:
    collect_fn = COLLECT_FUNCTIONS.get(bank_id.lower())
    if collect_fn:
        return collect_fn()
    
    collector = get_collector(bank_id)
    if collector:
        sources = collector.discover_sources()
        promos = collector.collect(sources)
        return CollectorResult(
            bank_id=collector.bank_id,
            sources_discovered=sources,
            sources_parsed=len(sources),
            promotions_found=len(promos),
        )
    
    return CollectorResult(
        bank_id=bank_id,
        errors=[f"No collector found for {bank_id}"],
    )


def list_collectors() -> List[str]:
    return sorted(set(k.replace("py_", "") for k in COLLECTOR_REGISTRY.keys()))


def register_collector(bank_id: str, collector_class: type[BaseCollector]) -> None:
    COLLECTOR_REGISTRY[bank_id] = collector_class
    logger.info(f"Registered collector: {bank_id}")