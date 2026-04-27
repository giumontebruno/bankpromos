#!/usr/bin/env python3
"""
Deploy verification script for Bank Promos PY.
Validates Railway deployment matches expected version.
"""

import sys
import time
import requests

EXPECTED_VERSION = "v2-clean-pipeline"
API_BASE = "https://bankpromos-production.up.railway.app"
MAX_RETRIES = 3
RETRY_DELAY = 20


def check_version():
    """Check if API version matches expected."""
    try:
        resp = requests.get(f"{API_BASE}/build-info", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        version = data.get("app_version")
        promotions = data.get("promotions_count", 0)
        
        print(f"  app_version: {version}")
        print(f"  promotions_count: {promotions}")
        
        return version == EXPECTED_VERSION
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_today_version():
    """Check if /today returns version."""
    try:
        resp = requests.get(f"{API_BASE}/today?limit=1", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        version = data.get("version")
        total = data.get("total_results", 0)
        
        print(f"  /today version: {version}")
        print(f"  /today total_results: {total}")
        
        return version == EXPECTED_VERSION
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print(f"=== Bank Promos Deploy Verification ===")
    print(f"Expected version: {EXPECTED_VERSION}")
    print(f"API base: {API_BASE}")
    print()
    
    all_ok = True
    
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt}/{MAX_RETRIES}...")
        
        if check_version() and check_today_version():
            print(f"\n[SUCCESS] All versions match {EXPECTED_VERSION}")
            return 0
        
        if attempt < MAX_RETRIES:
            print(f"  Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
    
    print(f"\n[FAILED] Version mismatch after {MAX_RETRIES} attempts")
    print(f"\nTo force redeploy, run:")
    print(f"  git commit --allow-empty -m 'force redeploy'")
    print(f"  git push origin main")
    return 1


if __name__ == "__main__":
    sys.exit(main())