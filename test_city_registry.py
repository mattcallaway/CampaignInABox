import sys
from pathlib import Path

# Ensure 'scripts' is in sys.path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.lib.city_registry import normalize_city_input, load_city_registry

def test_sonoma_cities():
    fips = "097"  # Sonoma County
    
    # 1. Test canonical names
    assert normalize_city_input(fips, "Santa Rosa")["city_slug"] == "santa_rosa"
    assert normalize_city_input(fips, "Petaluma")["city_slug"] == "petaluma"
    
    # 2. Test dirty variants
    dirty_tests = [
        ("City of rohnert park", "rohnert_park"),
        ("SantaRosa", "santa_rosa"),
        (" Sonoma", "sonoma"),
        ("PETALUMA  ", "petaluma"),
        ("sebaSTopol", "sebastopol"),
        ("Town of Windsor", "windsor"),
        ("Healdsburg City", "healdsburg"),
        ("Cotati", "cotati"),
        ("Cloverdale \t", "cloverdale"),
    ]
    
    for input_str, expected_slug in dirty_tests:
        try:
            res = normalize_city_input(fips, input_str)
            assert res["city_slug"] == expected_slug, f"Failed: '{input_str}' -> {res['city_slug']} != {expected_slug}"
            print(f"OK Exact match test passed: '{input_str}' -> {res['city_slug']}")
        except ValueError as e:
            print(f"FAIL Failed to resolve '{input_str}': {e}")
            sys.exit(1)

    # 3. Test failure for unknown cities
    try:
        normalize_city_input(fips, "Gotham")
        print("FAIL Error: 'Gotham' incorrectly resolved.")
        sys.exit(1)
    except ValueError:
        print("OK Correctly rejected 'Gotham'.")
        
    print("\nSUCCESS All Sonoma County city tests passed!")

if __name__ == "__main__":
    test_sonoma_cities()
