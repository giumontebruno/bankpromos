"""
Ejemplo de uso del módulo pdf_ai_parser para extraer promociones desde PDFs usando visión AI.

Este módulo es opcional y puede usarse como alternativa o complemento al parser tradicional.
"""
import argparse
import json
import sys
from pathlib import Path

from bankpromos.pdf_ai_parser import (
    analyze_pdf_and_convert,
    analyze_pdf_url_and_convert,
    analyze_pdf_with_vision,
)


def main():
    parser = argparse.ArgumentParser(description="Extraer promociones de PDFs usando AI")
    parser.add_argument("pdf", help="Ruta o URL del PDF a analizar")
    parser.add_argument("--bank-id", default="ueno", help="ID del banco (default: ueno)")
    parser.add_argument("--model", default="gpt-4o", help="Modelo de OpenAI (default: gpt-4o)")
    parser.add_argument("--output", "-o", help="Archivo de salida JSON")
    parser.add_argument("--raw", action="store_true", help="Mostrar respuesta raw del AI")
    args = parser.parse_args()

    pdf_source = args.pdf

    print(f"Analizando: {pdf_source}")
    print(f"Banco: {args.bank_id}, Modelo: {args.model}")

    is_url = pdf_source.startswith("http://") or pdf_source.startswith("https://")

    if args.raw:
        if is_url:
            results = analyze_pdf_with_vision(pdf_source, args.bank_id, args.model)
        else:
            results = analyze_pdf_with_vision(pdf_source, args.bank_id, args.model)
        
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if is_url:
        promos = analyze_pdf_url_and_convert(pdf_source, args.bank_id, args.model)
    else:
        promos = analyze_pdf_and_convert(pdf_source, args.bank_id, pdf_source, args.model)

    print(f"\nExtraídas {len(promos)} promociones:")

    for i, p in enumerate(promos, 1):
        print(f"\n{i}. {p.title}")
        print(f"   Comercio: {p.merchant_name}")
        print(f"   Categoría: {p.category}")
        print(f"   Descuento: {p.discount_percent}%")
        if p.installment_count:
            print(f"   Cuotas: {p.installment_count}")
        if p.cap_amount:
            print(f"   Tope: Gs. {p.cap_amount:,}")
        if p.valid_days:
            print(f"   Días: {p.valid_days}")

    if args.output:
        data = [p.model_dump(mode="json") for p in promos]
        Path(args.output).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nGuardado en: {args.output}")


if __name__ == "__main__":
    main()