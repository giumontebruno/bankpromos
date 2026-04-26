import logging
from typing import Dict, List

from bankpromos.storage import init_db, save_promotions, clear_promotions

logger = logging.getLogger(__name__)


def write_to_db(
    promos: List,
    db_path: str = "bankpromos.db",
    clear_first: bool = False,
) -> Dict[str, int]:
    if not promos:
        return {"written": 0, "db_path": db_path}
    
    try:
        init_db(db_path)
        
        if clear_first:
            clear_promotions(db_path)
            logger.info(f"Cleared existing promos from {db_path}")
        
        save_promotions(list(promos), db_path)
        logger.info(f"Wrote {len(promos)} promos to {db_path}")
        return {"written": len(promos), "db_path": db_path}
    except Exception as e:
        logger.error(f"Write error: {e}")
        return {"written": 0, "db_path": db_path, "error": str(e)}