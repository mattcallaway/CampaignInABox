import sys
import os
sys.path.insert(0, os.path.abspath("."))
from scripts.lib.naming import normalize_county, normalize_contest_slug, normalize_precinct_id, generate_contest_id

print("County:", normalize_county("sonoma "))
print("County:", normalize_county("s.f."))
print("Slug:", normalize_contest_slug("My Contest! 2024 @ General_"))
print("Precinct1:", normalize_precinct_id("  123.0  ", pad_to=7))
print("Precinct2:", normalize_precinct_id("AB.12  ", pad_to=7))
print("Contest ID:", generate_contest_id("2024", "CA", "sonoma", "my_contest_2024_general"))
