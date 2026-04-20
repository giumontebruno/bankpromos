import csv
import json
from pathlib import Path
from typing import List

from bankpromos.core.models import PromotionModel


def to_json(promos: List[PromotionModel], fp=None, indent: int = 2) -> str:
    data = [p.model_dump(mode="json") for p in promos]

    if fp:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent, default=str)
        return str(fp)

    return json.dumps(data, ensure_ascii=False, indent=indent, default=str)


def to_csv(promos: List[PromotionModel], fp=None) -> str:
    if not promos:
        return ""

    fieldnames = [
        "bank_id",
        "title",
        "merchant_name",
        "category",
        "benefit_type",
        "discount_percent",
        "installment_count",
        "valid_days",
        "valid_from",
        "valid_to",
        "source_url",
        "result_quality_score",
        "result_quality_label",
        "scraped_at",
    ]

    rows = []
    for p in promos:
        rows.append({
            "bank_id": p.bank_id,
            "title": p.title or "",
            "merchant_name": p.merchant_name or "",
            "category": p.category or "",
            "benefit_type": p.benefit_type or "",
            "discount_percent": str(p.discount_percent) if p.discount_percent else "",
            "installment_count": p.installment_count if p.installment_count else "",
            "valid_days": ",".join(p.valid_days) if p.valid_days else "",
            "valid_from": str(p.valid_from) if p.valid_from else "",
            "valid_to": str(p.valid_to) if p.valid_to else "",
            "source_url": p.source_url,
            "result_quality_score": p.result_quality_score,
            "result_quality_label": p.result_quality_label,
            "scraped_at": p.scraped_at.isoformat() if p.scraped_at else "",
        })

    import io

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    result = output.getvalue()

    if fp:
        Path(fp).write_text(result, encoding="utf-8")
        return str(fp)

    return result


def export_promotions(promos: List[PromotionModel], output_path: str, format_: str = None) -> str:
    if format_ is None:
        format_ = Path(output_path).suffix.lstrip(".")

    if format_ == "json":
        return to_json(promos, output_path)
    elif format_ == "csv":
        return to_csv(promos, output_path)
    else:
        raise ValueError(f"Unsupported format: {format_}")