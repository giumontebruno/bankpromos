import sys
sys.path.insert(0, '.')
from bankpromos.storage import load_promotions
from bankpromos.ui_output import to_ui_promo

promos = load_promotions('data/bankpromos.db')
print('Total:', len(promos))

if promos:
    p = promos[0]
    print('Source promo:')
    print('  result_quality_label:', repr(p.result_quality_label))
    print('  source_url:', repr(p.source_url))
    print()
    
    d = {
        'bank_id': p.bank_id,
        'title': p.title,
        'merchant_name': p.merchant_name,
        'category': p.category,
        'benefit_type': p.benefit_type,
        'discount_percent': str(p.discount_percent) if p.discount_percent else None,
        'installment_count': p.installment_count,
        'valid_days': p.valid_days,
        'cap_amount': str(p.cap_amount) if p.cap_amount else None,
        'valid_from': p.valid_from.isoformat() if p.valid_from else None,
        'valid_to': p.valid_to.isoformat() if p.valid_to else None,
        'conditions_text': p.conditions_text,
        'payment_method': p.payment_method,
        'emblem': p.emblem,
        'source_url': p.source_url,
        'raw_text': p.raw_text,
        'result_quality_score': p.result_quality_score,
        'result_quality_label': p.result_quality_label,
        'raw_data': p.raw_data,
    }
    
    ui = to_ui_promo(d)
    if ui:
        print('UI promo:')
        print('  quality_label:', repr(ui.get('quality_label')))
    else:
        print('UI returned None')