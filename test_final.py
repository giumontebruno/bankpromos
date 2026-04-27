import sys
sys.path.insert(0, '.')
from bankpromos.api import app
from fastapi.testclient import TestClient
client = TestClient(app)

r = client.get('/today?limit=10')
data = r.json()
print('GET /today:', r.status_code)
print('Total results:', data.get('total_results', 0))
print()
for i, p in enumerate(data.get('results', [])[:8]):
    print(f'{i+1}. {p.get("display_name")}')
    print(f'   highlight: {p.get("highlight_value")}')
    print(f'   category: {p.get("category")}')
    print(f'   is_category_level: {p.get("is_category_level")}')
    print(f'   display_title: {p.get("display_title")}')
    print(f'   conditions_short: {p.get("conditions_short")}')
    print(f'   quality_label: {p.get("quality_label")}')
    print()

print('Done')