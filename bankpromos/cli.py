import argparse
import sys
from datetime import datetime
from pathlib import Path

from bankpromos import list_scrapers
from bankpromos.cache import get_cache_status
from bankpromos.config import config
from bankpromos.data_service import (
    collect_all_data,
    get_fuel_data,
    get_promotions_data,
)
from bankpromos.exporter import export_promotions
from bankpromos.fuel_prices import normalize_emblem, normalize_fuel_type
from bankpromos.fuel_query import find_best_fuel_promotions
from bankpromos.query_engine import query_promotions
from bankpromos.run_all import run_scraper

SUPPORTED_BANKS = ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]
DEFAULT_DB = "bankpromos.db"
LOCAL_DEFAULT_DB = "data/bankpromos.db"


def main():
    parser = argparse.ArgumentParser(prog="bankpromos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available banks")

    collect_parser = subparsers.add_parser("collect", help="Collect and cache all data")
    collect_parser.add_argument("--all", action="store_true", help="Collect from all banks")
    collect_parser.add_argument("--bank", help="Specific bank to collect")
    collect_parser.add_argument("--force", action="store_true", help="Force refresh cache")
    collect_parser.add_argument("--fuel", action="store_true", help="Collect fuel prices only")
    collect_parser.add_argument("--db", default=DEFAULT_DB, help="Database path")
    collect_parser.add_argument(
        "--parser-mode",
        choices=["classic", "ai", "auto"],
        default="classic",
        help="PDF parser mode (default: classic)",
    )

    run_parser = subparsers.add_parser("run", help="Run scraper(s) without saving to cache")
    run_parser.add_argument("--bank", help="Bank ID to scrape")
    run_parser.add_argument("--all", action="store_true", help="Run all banks")
    run_parser.add_argument("--output", "-o", help="Output file path")
    run_parser.add_argument("--format", choices=["json", "csv"], help="Output format")
    run_parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    query_parser = subparsers.add_parser("query", help="Query promotions (uses cache)")
    query_parser.add_argument("query", nargs="*", help="Search query")
    query_parser.add_argument("--all", action="store_true", help="Scrape all banks first")
    query_parser.add_argument("--bank", help="Specific bank to query")
    query_parser.add_argument("--limit", type=int, default=10, help="Max results")
    query_parser.add_argument("--force", action="store_true", help="Force cache refresh")
    query_parser.add_argument("--db", default=DEFAULT_DB, help="Database path")

    fuel_parser = subparsers.add_parser("fuel", help="Query fuel promotions (uses cache)")
    fuel_parser.add_argument("query", nargs="*", help="Fuel query (e.g., 'mejor nafta 95')")
    fuel_parser.add_argument("--all", action="store_true", help="Scrape all banks first")
    fuel_parser.add_argument("--emblem", help="Filter by emblem (shell, copetrol, etc.)")
    fuel_parser.add_argument("--fuel-type", help="Filter by fuel type (nafta_95, diesel, etc.)")
    fuel_parser.add_argument("--limit", type=int, default=10, help="Max results")
    fuel_parser.add_argument("--force", action="store_true", help="Force cache refresh")
    fuel_parser.add_argument("--db", default=DEFAULT_DB, help="Database path")

    cache_parser = subparsers.add_parser("cache", help="Show cache status")
    cache_parser.add_argument("--db", default=DEFAULT_DB, help="Database path")

    pdf_parser = subparsers.add_parser("pdf-debug", help="Debug PDF extraction")
    pdf_parser.add_argument("file", nargs="?", help="Specific PDF file in data/pdfs/")

    qa_parser = subparsers.add_parser("qa", help="QA database")
    qa_parser.add_argument("--export", action="store_true", help="Export QA report CSV")
    qa_parser.add_argument("--today", action="store_true", help="Show today's top promos")

    args = parser.parse_args()

    if args.command == "list":
        banks = list_scrapers()
        print("Available banks:")
        for b in banks:
            print(f"  - {b}")
        return

    if args.command == "collect":
        force = args.force
        db_path = args.db if args.db != DEFAULT_DB else LOCAL_DEFAULT_DB
        parser_mode = getattr(args, "parser_mode", "classic")
        
        print(f"[DB] Using: {db_path}")

        if args.fuel:
            print("Collecting fuel prices...")
            prices = get_fuel_data(force_refresh=force, db_path=db_path)
            print(f"Collected {len(prices)} fuel prices")
            return

        if args.all:
            from bankpromos.pipeline import run_all_collections, print_results
            from bankpromos.storage import load_promotions, load_fuel_prices
            import os
            print(f"Running all collectors (parser: {parser_mode})...")
            results = run_all_collections(db_path=db_path, debug=False, parser_mode=parser_mode, clear_first=force)
            print_results(results)
            
            if os.path.exists(db_path):
                total_promos = len(load_promotions(db_path))
                total_fuel = len(load_fuel_prices(db_path))
                print(f"[DB] Total promotions in {db_path}: {total_promos}")
                print(f"[DB] Total fuel prices in {db_path}: {total_fuel}")
            return

        if args.bank:
            from bankpromos.pipeline import run_bank_collection
            from bankpromos.pipeline.runner import CollectionResult

            result: CollectionResult = run_bank_collection(
                args.bank,
                db_path=db_path,
                debug=True,
                parser_mode=parser_mode,
            )
            print(f"  Parser mode: {result.parser_mode}")
            if result.parser_used != result.parser_mode:
                print(f"  Parser used: {result.parser_used}")
            print(f"  Sources: {result.sources_found}")
            print(f"  Collected: {result.promos_collected}")
            print(f"  Normalized: {result.promos_normalized}")
            print(f"  Deduped: {result.promos_deduped}")
            print(f"  Saved: {result.promos_saved}")
            if result.errors:
                for e in result.errors:
                    print(f"  Error: {e}")
            return

        result = collect_all_data(force_refresh=force, db_path=db_path)
        print(f"Collected {result['promotions_count']} promotions")
        print(f"Collected {result['fuel_prices_count']} fuel prices")
        print(f"Promotions updated: {result['promos_updated']}")
        print(f"Fuel updated: {result['fuel_updated']}")
        
        if "source_counts" in result:
            print("Source breakdown:")
            for src, count in result["source_counts"].items():
                print(f"  {src}: {count}")
        return

    if args.command == "cache":
        status = get_cache_status(args.db)
        print("Cache Status:")
        print(f"  Promotions fresh: {status['promotions_fresh']}")
        print(f"  Fuel fresh: {status['fuel_fresh']}")
        print(f"  Promotions age (hours): {status['promotions_age_hours']:.1f}")
        print(f"  Fuel age (hours): {status['fuel_age_hours']:.1f}")
        print(f"  Last update: {status['promotions_updated_at']}")
        return

    if args.command == "pdf-debug":
        from bankpromos.pdf_debug import main as pdf_main
        pdf_main()
        return

    if args.command == "qa":
        import bankpromos.qa as qa_module
        from argparse import Namespace
        qa_args = Namespace(
            export=getattr(args, 'export', False),
            today=getattr(args, 'today', False),
        )
        qa_module.main(qa_args)
        return

    if args.command == "run":
        if not args.bank and not args.all:
            print("Error: specify --bank or --all", file=sys.stderr)
            sys.exit(1)

        if args.all:
            from bankpromos.run_all import run_all_scrapers

            promos, errors = run_all_scrapers(debug_mode=args.debug)
            if errors:
                print(f"\nErrors encountered:")
                for bid, err in errors.items():
                    print(f"  {bid}: {err}")
        else:
            if args.bank not in SUPPORTED_BANKS:
                print(f"Error: Unknown bank: {args.bank}. Available: {SUPPORTED_BANKS}", file=sys.stderr)
                sys.exit(1)
            promos, error = run_scraper(args.bank, debug_mode=args.debug)
            if error:
                print(f"Error: {error}", file=sys.stderr)
                sys.exit(1)

        print(f"\nScraped {len(promos)} promotions")

        if args.output:
            export_promotions(promos, args.output, args.format)
            print(f"Exported to {args.output}")
        else:
            for p in promos[:5]:
                pct = p.discount_percent or p.installment_count or ""
                print(f"  - {p.title}: {pct} @ {p.merchant_name}")
            if len(promos) > 5:
                print(f"  ... and {len(promos) - 5} more")
        return

    if args.command == "query":
        query_str = " ".join(args.query) if args.query else ""
        db_path = args.db

        print(f"Loading promotions (cache: {'fresh' if not args.force else 'refreshed'})...")
        promos = get_promotions_data(force_refresh=args.force, db_path=db_path)
        print(f"Loaded {len(promos)} promotions")

        if args.all:
            print("Scraping fresh data...")
            from bankpromos.run_all import run_all_scrapers, run_scraper

            all_promos = []
            for bank_id in SUPPORTED_BANKS:
                try:
                    p, err = run_scraper(bank_id, debug_mode=False)
                    if not err and p:
                        all_promos.extend(p)
                except Exception:
                    continue

            if all_promos:
                from bankpromos.data_service import _process_promotions

                promos = _process_promotions(all_promos)
                print(f"Processed {len(promos)} promotions")
        elif args.bank:
            promos, error = run_scraper(args.bank, debug_mode=False)
            if error:
                print(f"Error: {error}", file=sys.stderr)
                sys.exit(1)

        results = query_promotions(promos, query_str)

        if args.limit:
            results = results[:args.limit]

        print(f"\n{len(results)} results for: '{query_str}'")

        if results:
            for p in results:
                bank_display = p.bank_id.replace("py_", "").upper()
                merchant = p.merchant_name or p.title or "N/A"
                benefit = f"{int(p.discount_percent)}%" if p.discount_percent else (f"{p.installment_count} cuotas" if p.installment_count else p.benefit_type or "-")
                days = ", ".join(p.valid_days) if p.valid_days else "todos"
                category = p.category or "General"
                print(f"  [{bank_display}] {merchant} | {benefit} | {days} | {category}")
        else:
            print("  No results found")
        return

    if args.command == "fuel":
        query_str = " ".join(args.query) if args.query else ""
        db_path = args.db

        print(f"Loading data...")
        promos = get_promotions_data(force_refresh=args.force, db_path=db_path)

        fuel_type = args.fuel_type or normalize_fuel_type(query_str) or "nafta_95"
        emblem = args.emblem or normalize_emblem(query_str)

        if not fuel_type:
            fuel_type = "nafta_95"

        fuel_prices = get_fuel_data(force_refresh=args.force, db_path=db_path)

        matches = find_best_fuel_promotions(promos, fuel_prices, fuel_type, emblem)

        if args.limit:
            matches = matches[:args.limit]

        print(f"\n{'='*70}")
        print(f"MEJOR PRECIO - Combustible ({fuel_type.replace('_', ' ').upper()})")
        print(f"{'='*70}")
        print(f"{'Rank':<5} {'Banco':<8} {'Estacion':<12} {'Tipo':<6} {'Base':>6} {'Desc':>6} {'Final':>8} {'Dias':<12}")
        print(f"{'-'*70}")

        if matches:
            for i, m in enumerate(matches, 1):
                bank = m["bank_id"].replace("py_", "").upper()
                emb = m["emblem"].upper()
                ft = m["fuel_type"].replace("nafta_", "").replace("_", " ")
                base = m["base_price"]
                disc = m["discount_percent"]
                final = m["estimated_final_price"]
                days = ",".join(m["valid_days"]) if m["valid_days"] else "todos"
                disc_str = f"{int(disc)}%" if disc else "-"
                print(f"{i:<5} {bank:<8} {emb:<12} {ft:<6} {float(base):>6,.0f} {disc_str:>6} {float(final):>8,.0f} {days:<12}")
        else:
            print("  No se encontraron promociones de combustible")

        print(f"{'='*70}")


if __name__ == "__main__":
    main()