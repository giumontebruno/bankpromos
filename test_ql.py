import sys
sys.path.insert(0, '.')

promo_dict = {
    'bank_id': 'py_itau',
    'title': 'Supermercado Stock - 15% de descuento',
    'merchant_name': 'Stock',
    'category': 'Supermercados',
    'benefit_type': 'descuento',
    'discount_percent': '15',
    'installment_count': None,
    'valid_days': ['sabado', 'domingo'],
    'cap_amount': None,
    'valid_from': None,
    'valid_to': None,
    'conditions_text': None,
    'payment_method': None,
    'emblem': None,
    'source_url': 'https://www.itau.com.py/beneficios',
    'raw_text': None,
    'result_quality_score': 1.3,
    'result_quality_label': 'CURATED',
    'raw_data': {'curated': True},
}

print('Input promo_dict:')
print(f"  result_quality_label: {promo_dict.get('result_quality_label')}")
print(f"  source_url: {promo_dict.get('source_url')}")

from bankpromos.ui_output import to_ui_promo, _infer_quality_label

q = _infer_quality_label(promo_dict)
print(f'_infer_quality_label result: {q}')

ui = to_ui_promo(promo_dict)
if ui:
    print(f'to_ui_promo quality_label: {ui.get("quality_label")}')
else:
    print('to_ui_promo returned None')