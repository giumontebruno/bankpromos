from bankpromos.pdf_classifier import get_sources_for_bank

for bank in ['ueno', 'sudameris', 'continental']:
    s = get_sources_for_bank(bank)
    print(f'{bank}: {len(s)} sources')
    for x in s[:3]:
        print(f'  {x["filename"][:50]}: cat={x.get("category_hint")}, merch={x.get("merchant_hint")}')