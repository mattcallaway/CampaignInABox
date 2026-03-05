"""
scripts/loaders/categories.py

Canonical mapping of human-readable jurisdiction data category labels
to filesystem-safe folder names. Single source of truth for all scripts.
"""

# Maps human-readable label -> filesystem folder name
CATEGORY_MAP = {
    "MPREC GeoPackage":          "MPREC_GeoPackage",
    "MPREC GeoJSON":              "MPREC_GeoJSON",
    "MPREC Shapefile":            "MPREC_Shapefile",
    "SRPREC GeoPackage":         "SRPREC_GeoPackage",
    "SRPREC GeoJSON":             "SRPREC_GeoJSON",
    "SRPREC Shapefile":           "SRPREC_Shapefile",
    "SRPREC TO 2020 BLK":        "SRPREC_TO_2020_BLK",
    "RGPREC TO 2020 BLK":        "RGPREC_TO_2020_BLK",
    "2020 BLK TO MPREC":         "2020_BLK_TO_MPREC",
    "RG to RR to SR to SVPREC":  "RG_to_RR_to_SR_to_SVPREC",
    "MPREC to SRPREC":           "MPREC_to_SRPREC",
    "SRPREC to CITY":            "SRPREC_to_CITY",
}

# Reverse mapping: folder name -> human label
FOLDER_TO_LABEL = {v: k for k, v in CATEGORY_MAP.items()}

# Ordered list of all required category folder names
ALL_CATEGORIES = list(CATEGORY_MAP.values())

# Geometry categories (prefer MPREC; fall back to SRPREC)
MPREC_GEOM_CATEGORIES = ["MPREC_GeoJSON", "MPREC_GeoPackage", "MPREC_Shapefile"]
SRPREC_GEOM_CATEGORIES = ["SRPREC_GeoJSON", "SRPREC_GeoPackage", "SRPREC_Shapefile"]

# Crosswalk categories
CROSSWALK_CATEGORIES = [
    "SRPREC_TO_2020_BLK",
    "RGPREC_TO_2020_BLK",
    "2020_BLK_TO_MPREC",
    "RG_to_RR_to_SR_to_SVPREC",
    "MPREC_to_SRPREC",
    "SRPREC_to_CITY",
]

# File extensions recognized per category type
GEOM_EXTENSIONS = {
    "GeoJSON":    [".geojson"],
    "GeoPackage": [".gpkg"],
    "Shapefile":  [".shp"],
}

CROSSWALK_EXTENSIONS = [".csv", ".tsv", ".xlsx", ".xls"]
