import sys
sys.path.insert(0, '.')
from bankpromos.api import app
from fastapi.testclient import TestClient
client = TestClient(app)

r = client.get('/today?limit=2')
data = r.json()
for p in data.get('results', []):
    print('Result:')
    ql = p.get('quality_label')
    su = p.get('source_url')
    print(f'  quality_label: {ql}')
    print(f'  source_url: {su}')
    print()