import sys
sys.path.insert(0, '.')
from bankpromos.pdf_classifier import get_sources_for_bank
sources = get_sources_for_bank('continental')
print(f'Sources: {len(sources)}')
for s in sources:
    fname = s['filename']
    print(f'  {fname}')