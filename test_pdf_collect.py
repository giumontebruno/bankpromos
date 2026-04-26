import sys
sys.path.insert(0, '.')
from bankpromos.storage import init_db, clear_promotions, save_promotions
init_db('data/bankpromos.db')
clear_promotions('data/bankpromos.db')

from bankpromos.collectors.ueno import UenoCollector
from bankpromos.collectors.sudameris import SudamerisCollector
from bankpromos.collectors.continental import ContinentalCollector
from bankpromos.pipeline.runner import _to_legacy

all_models = []
for cls, name in [
    (UenoCollector, 'ueno'),
    (SudamerisCollector, 'sudameris'),
    (ContinentalCollector, 'continental'),
]:
    c = cls()
    try:
        sources = c.discover_sources()
        raw = c.collect(sources)
        print(f'{name}: {len(raw)} raw promos')
        caps = [p for p in raw if p.cap_amount]
        dates = [p for p in raw if p.valid_from]
        print(f'  caps={len(caps)}, dates={len(dates)}')
        for cap_p in caps[:3]:
            print(f'    cap example: {cap_p.title[:40]}: {cap_p.cap_amount}')
        for p in raw:
            all_models.append(_to_legacy(p))
    except Exception as e:
        print(f'{name}: ERROR {e}')
        import traceback
        traceback.print_exc()

print(f'\nTotal: {len(all_models)} models')
save_promotions(all_models, 'data/bankpromos.db')

import sqlite3
conn = sqlite3.connect('data/bankpromos.db')
caps_q = "select count(*) from promotions where cap_amount is not null"
dates_q = "select count(*) from promotions where valid_from is not null"
print(f'DB caps: {conn.execute(caps_q).fetchone()[0]}')
print(f'DB dates: {conn.execute(dates_q).fetchone()[0]}')
print(f'DB total: {conn.execute("select count(*) from promotions").fetchone()[0]}')