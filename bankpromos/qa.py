import argparse
import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = "data/bankpromos.db"

SUSPICIOUS_MERCHANTS = {
    "ueno": "bank name used as merchant",
    "sudameris": "bank name used as merchant",
    "itau": "bank name used as merchant",
    "continental": "bank name used as merchant",
    "bnf": "bank name used as merchant",
    "el reintegro del": "fake merchant",
    "un descuento del": "fake merchant",
    "reintegro adicional del": "fake merchant",
    "none": "null merchant",
    "null": "null merchant",
    "nulo": "null merchant",
    "reintegro del": "fake merchant pattern",
    "descuento del": "fake merchant pattern",
    "beneficio del": "fake merchant pattern",
    "40 de reintegro": "fake merchant",
    "contrato único": "fake merchant",
    "proceda": "fake merchant",
    "impuestos": "fake merchant",
}

SUSPICIOUS_TITLES = [
    "presencia del 100%",
    "plazo de acreditaci",
    "corporate",
    "governance",
    "reintegro del 100%",
    "beneficio del 100%",
    "los meses con pagos que tienen un reintegro del",
    "reintegro del 100% no suman",
]

GARBAGE_CATEGORIES = {
    "Impuestos", "Contrato Único", "Proceda", "El Reintegro Del",
    "Un Descuento Del", "40 De Reintegro", "None", "null",
}

GARBAGE_MERCHANTS = {
    "ueno", "sudameris", "itau", "continental", "bnf", "banco",
    "el reintegro del", "un descuento del", "reintegro adicional del",
    "reintegro del", "descuento del", "beneficio del",
    "40 de reintegro", "contrato único", "proceda", "impuestos",
    "none", "null", "nulo", "banco de la nacion",
}


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_promos():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM promotions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fuel():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM fuel_prices").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _is_valid_merchant(m: str) -> bool:
    if not m:
        return False
    ml = m.lower().strip()
    if not ml or ml in ("none", "null", ""):
        return False
    if len(ml) < 2:
        return False
    if any(w in ml for w in GARBAGE_MERCHANTS):
        return False
    if ml.startswith("reintegro") or ml.startswith("descuento"):
        return False
    return True


def analyze_merchants(promos):
    suspicious = {}
    null_count = 0
    general_count = 0
    valid_count = 0
    
    for p in promos:
        merchant = (p.get("merchant_name") or "").lower().strip()
        
        if not merchant or merchant in ("none", "null", ""):
            null_count += 1
        
        for susp, reason in SUSPICIOUS_MERCHANTS.items():
            if susp in merchant:
                suspicious[merchant] = suspicious.get(merchant, {"count": 0, "reason": reason})
                suspicious[merchant]["count"] += 1
                break
        
        if _is_valid_merchant(p.get("merchant_name") or ""):
            valid_count += 1
        
        if p.get("category") == "General" and not p.get("merchant_name"):
            general_count += 1
    
    return {
        "null_merchants": null_count,
        "suspicious": suspicious,
        "general_no_merchant": general_count,
        "valid_merchants": valid_count,
    }


def analyze_caps(promos):
    suspicious = []
    valid = []
    
    for p in promos:
        cap = p.get("cap_amount")
        if cap is None:
            continue
        
        try:
            cap_val = float(str(cap))
            if cap_val < 10000:
                suspicious.append({"merchant": p.get("merchant_name"), "cap": cap_val})
            elif cap_val > 1000 and cap_val < 100000:
                suspicious.append({"merchant": p.get("merchant_name"), "cap": cap_val})
            else:
                valid.append(cap_val)
        except:
            suspicious.append({"merchant": p.get("merchant_name"), "cap": cap})
    
    return {"suspicious": suspicious, "valid_count": len(valid)}


def analyze_titles(promos):
    suspicious = []
    
    for p in promos:
        title = (p.get("title") or "").lower()
        raw = (p.get("raw_text") or "").lower()
        
        for susp in SUSPICIOUS_TITLES:
            if susp in title or susp in raw:
                suspicious.append({
                    "merchant": p.get("merchant_name"),
                    "title": p.get("title", "")[:50],
                    "reason": susp,
                })
                break
    
    return suspicious


def get_top_categories(promos):
    cats = {}
    for p in promos:
        cat = p.get("category") or "General"
        if cat in GARBAGE_CATEGORIES:
            continue
        cats[cat] = cats.get(cat, 0) + 1
    
    return sorted(cats.items(), key=lambda x: -x[1])


def get_top_banks(promos):
    banks = {}
    for p in promos:
        bank = p.get("bank_id") or "unknown"
        banks[bank] = banks.get(bank, 0) + 1
    
    return sorted(banks.items(), key=lambda x: -x[1])


def get_active_today(promos):
    today = date.today()
    count_by_days = 0
    count_by_dates = 0
    
    day_names = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"}
    today_name = day_names.get(today.weekday(), "")
    
    for p in promos:
        days = p.get("valid_days") or []
        if not days:
            count_by_days += 1
        elif today_name in [d.lower() for d in days]:
            count_by_days += 1
        
        valid_from_str = p.get("valid_from")
        valid_to_str = p.get("valid_to")
        if valid_from_str and valid_to_str:
            try:
                vf = date.fromisoformat(valid_from_str) if isinstance(valid_from_str, str) else valid_from_str
                vt = date.fromisoformat(valid_to_str) if isinstance(valid_to_str, str) else valid_to_str
                if vf <= today <= vt:
                    count_by_dates += 1
            except Exception:
                pass
        elif valid_to_str:
            try:
                vt = date.fromisoformat(valid_to_str) if isinstance(valid_to_str, str) else valid_to_str
                if vt >= today:
                    count_by_dates += 1
            except Exception:
                pass
    
    return count_by_days, count_by_dates


def export_qa_report(promos, output_path="data/qa_promotions_report.csv"):
    rows = []
    
    for p in promos:
        merchant = (p.get("merchant_name") or "").lower().strip()
        title = (p.get("title") or "").lower().strip()
        raw = (p.get("raw_text") or "")[:200]
        
        suspicious = []
        
        if not merchant or merchant in ("none", "null", ""):
            suspicious.append("null_merchant")
        
        for susp, reason in SUSPICIOUS_MERCHANTS.items():
            if susp in merchant:
                suspicious.append(reason)
        
        for susp in SUSPICIOUS_TITLES:
            if susp in title or susp in raw:
                suspicious.append(f"title:{susp}")
        
        cap = p.get("cap_amount")
        if cap:
            try:
                if float(str(cap)) < 10000:
                    suspicious.append("low_cap")
            except:
                suspicious.append("invalid_cap")
        
        if p.get("category") == "General" and not p.get("merchant_name"):
            suspicious.append("general_no_merchant")
        
        rows.append({
            "bank_id": p.get("bank_id"),
            "merchant_name": p.get("merchant_name"),
            "category": p.get("category"),
            "title": p.get("title"),
            "discount_percent": p.get("discount_percent"),
            "installment_count": p.get("installment_count"),
            "cap_amount": p.get("cap_amount"),
            "valid_days": p.get("valid_days"),
            "valid_from": p.get("valid_from"),
            "valid_to": p.get("valid_to"),
            "source_url": p.get("source_url"),
            "result_quality_label": p.get("result_quality_label"),
            "raw_text_preview": raw[:100],
            "suspicious_reason": "; ".join(suspicious) if suspicious else "",
        })
    
    if not rows:
        return False
    
    fieldnames = list(rows[0].keys())
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return True


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="QA database")
        parser.add_argument("--export", action="store_true", help="Export QA report CSV")
        parser.add_argument("--today", action="store_true", help="Show todays top promos")
        args = parser.parse_args()
    
    if not Path(DB_PATH).exists():
        print(f"DB not found: {DB_PATH}")
        return
    
    promos = get_promos()
    fuel = get_fuel()
    
    print(f"\n{'='*60}")
    print("QA REPORT")
    print(f"{'='*60}")
    print(f"Total promotions: {len(promos)}")
    print(f"Total fuel prices: {len(fuel)}")
    
    print(f"\n--- By Bank ---")
    for bank, count in get_top_banks(promos):
        print(f"  {bank}: {count}")
    
    print(f"\n--- By Category ---")
    for cat, count in get_top_categories(promos):
        print(f"  {cat}: {count}")
    
    merch_analysis = analyze_merchants(promos)
    print(f"\n--- Merchant Issues ---")
    print(f"  Null merchants: {merch_analysis['null_merchants']}")
    print(f"  Valid merchants: {merch_analysis['valid_merchants']}")
    print(f"  General no merchant: {merch_analysis['general_no_merchant']}")
    if merch_analysis['suspicious']:
        print(f"  Suspicious merchants:")
        for m, data in list(merch_analysis['suspicious'].items())[:5]:
            print(f"    - {m[:30]}: {data['count']} ({data['reason']})")
    
    cap_analysis = analyze_caps(promos)
    print(f"\n--- Cap Issues ---")
    print(f"  Valid caps: {cap_analysis['valid_count']}")
    if cap_analysis['suspicious'][:5]:
        print(f"  Suspicious caps:")
        for c in cap_analysis['suspicious'][:5]:
            print(f"    - {str(c['merchant'] or '')[:20]}: {c['cap']}")
    
    title_analysis = analyze_titles(promos)
    print(f"\n--- Title Issues ---")
    print(f"  Suspicious titles: {len(title_analysis)}")
    if title_analysis[:3]:
        for t in title_analysis[:3]:
            print(f"    - {t['title'][:40]}")
    
    active_days, active_dates = get_active_today(promos)
    print(f"\n--- Today ---")
    print(f"  Active (no day restriction): {active_days}")
    print(f"  Active (date range includes today): {active_dates}")
    
    records_with_from = sum(1 for p in promos if p.get("valid_from"))
    records_with_to = sum(1 for p in promos if p.get("valid_to"))
    print(f"\n--- Date Ranges ---")
    print(f"  Records with valid_from: {records_with_from}")
    print(f"  Records with valid_to: {records_with_to}")
    if records_with_from > 0:
        print(f"  Sample date ranges:")
        shown = 0
        for p in promos:
            if p.get("valid_from") and p.get("valid_to"):
                print(f"    {p.get('title', '')[:40]}: {p.get('valid_from')} -> {p.get('valid_to')}")
                shown += 1
                if shown >= 5:
                    break
    
    if args.export:
        output_path = "data/qa_promotions_report.csv"
        if export_qa_report(promos, output_path):
            print(f"\n[EXPORTED] {output_path}")
    
    if getattr(args, 'today', False):
        print(f"\n{'='*60}")
        print("TOP TODAY")
        print(f"{'='*60}")
        
        valid_fuel = [f for f in fuel if f.get("discount_percent") and f.get("emblem")]
        fuel_sorted = sorted(valid_fuel, key=lambda x: float(x.get("discount_percent") or 0), reverse=True)
        print(f"\nTop Fuel ({len(fuel_sorted)} with discount):")
        for f in fuel_sorted[:5]:
            print(f"  {f.get('emblem')}: {f.get('discount_percent')}% on {f.get('fuel_type')}")
        if not fuel_sorted:
            print("  (no fuel prices with valid discounts)")
        
        cat_promos = {}
        for p in promos:
            cat = p.get("category") or "General"
            if cat in GARBAGE_CATEGORIES or cat == "General":
                continue
            if not _is_valid_merchant(p.get("merchant_name") or ""):
                continue
            if cat not in cat_promos:
                cat_promos[cat] = []
            cat_promos[cat].append(p)
        
        for cat in ["Combustible", "Supermercados", "Gastronomía", "Tecnología", "Indumentaria"]:
            if cat in cat_promos:
                subset = sorted(cat_promos[cat], key=lambda x: float(x.get("discount_percent") or 0), reverse=True)
                print(f"\nTop {cat} ({len(subset)}):")
                for p in subset[:3]:
                    m = p.get("merchant_name") or "-"
                    d = p.get("discount_percent") or "-"
                    i = p.get("installment_count")
                    benefit = f"{d}%" if d else (f"{i} cuotas" if i else "-")
                    print(f"  {str(m)[:25]}: {benefit}")


if __name__ == "__main__":
    main()