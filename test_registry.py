import sys
from scripts.lib.county_registry import load_county_registry, normalize_county_input

def test_registry():
    reg = load_county_registry()
    counties = reg.get_all()
    
    # 1. Check count
    assert len(counties) == 58, f"Expected 58 counties, got {len(counties)}"
    
    # 2. Check a few normalization cases
    cases = [
        ("Sonoma", "Sonoma", "097"),
        ("sonoma county", "Sonoma", "097"),
        ("097", "Sonoma", "097"),
        ("c097", "Sonoma", "097"),
        ("l.a.", "Los Angeles", "037"),
        ("SF", "San Francisco", "075"),
        ("County of San Francisco", "San Francisco", "075"),
    ]
    
    for input_val, expected_name, expected_fips in cases:
        try:
            record = normalize_county_input(input_val)
            assert record["county_name"] == expected_name, f"Expected {expected_name} for '{input_val}', got {record['county_name']}"
            assert record["county_fips"] == expected_fips, f"Expected {expected_fips} for '{input_val}', got {record['county_fips']}"
        except ValueError as e:
            print(f"Failed to normalize {input_val}: {e}")
            sys.exit(1)
            
    print("All registry tests passed successfully!")

if __name__ == "__main__":
    test_registry()
