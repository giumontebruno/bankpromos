import sys
sys.path.insert(0, '.')
from bankpromos.storage import load_promotions

promos = load_promotions('data/bankpromos.db')
print(f'Total: {len(promos)}')
for p in promos[:2]:
    print(f'  bank_id: {p.bank_id}')
    print(f'  result_quality_label: {p.result_quality_label}')
    su = p.source_url or ""
    print(f'  source_url: {su[:40]}')
    rd = str(p.raw_data or "")
    print(f'  raw_data: {rd[:50]}')
    print()