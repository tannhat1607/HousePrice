from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


ML_COLUMNS = [
    "area_m2",
    "bedrooms",
    "floors",
    "frontage_m",
    "road_width_m",
    "district",
    "price_million_vnd",
    "address",
]

USA_FORMAT_COLUMNS = [
    "Avg. Area Income",
    "Avg. Area House Age",
    "Avg. Area Number of Rooms",
    "Avg. Area Number of Bedrooms",
    "Area Population",
    "Price",
    "Address",
]


DISTRICT_CODES = {
    "Hai Chau": 1,
    "Thanh Khe": 2,
    "Son Tra": 3,
    "Ngu Hanh Son": 4,
    "Lien Chieu": 5,
    "Cam Le": 6,
    "Hoa Vang": 7,
    "Hoang Sa": 8,
}


def district_from_text(value: str) -> str:
    text = strip_accents(value).lower().replace("-", " ")
    districts = {
        "hai chau": "Hai Chau",
        "thanh khe": "Thanh Khe",
        "son tra": "Son Tra",
        "ngu hanh son": "Ngu Hanh Son",
        "lien chieu": "Lien Chieu",
        "cam le": "Cam Le",
        "hoa vang": "Hoa Vang",
        "hoang sa": "Hoang Sa",
    }
    for key, district in districts.items():
        if key in text:
            return district
    return ""


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def number_from_text(value: object, patterns: tuple[str, ...]) -> float | None:
    text = strip_accents(str(value or "")).lower()
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def coalesce_numeric(series: pd.Series, fallback: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.fillna(fallback)


def build_clean_ml_dataset(source_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(source_path)

    df = pd.DataFrame()
    df["area_m2"] = pd.to_numeric(raw["area_m2"], errors="coerce")
    df["bedrooms"] = pd.to_numeric(raw["bedrooms"], errors="coerce")
    df["floors"] = pd.to_numeric(raw["floors"], errors="coerce")
    df["frontage_m"] = pd.to_numeric(raw["frontage_m"], errors="coerce")
    df["road_width_m"] = pd.to_numeric(raw["road_width_m"], errors="coerce")
    district_source = raw["district"].fillna("").astype(str)
    fallback_text = (
        raw.get("url", pd.Series([""] * len(raw))).fillna("").astype(str)
        + " "
        + raw["title"].fillna("").astype(str)
        + " "
        + raw["description"].fillna("").astype(str)
    )
    fallback_district = fallback_text.apply(district_from_text)
    df["district"] = district_source.where(district_source.str.strip().ne(""), fallback_district)
    df["price_million_vnd"] = pd.to_numeric(raw["price_million_vnd"], errors="coerce")

    title = raw["title"].fillna("").astype(str)
    address = raw["address"].fillna("").astype(str)

    extracted_bedrooms = title.apply(lambda value: number_from_text(value, (r"(\d+(?:[.,]\d+)?)\s*pn", r"(\d+(?:[.,]\d+)?)\s*phong ngu")))
    extracted_floors = title.apply(lambda value: number_from_text(value, (r"(\d+(?:[.,]\d+)?)\s*tang", r"(\d+(?:[.,]\d+)?)\s*tầng")))
    extracted_frontage = title.apply(lambda value: number_from_text(value, (r"ngang\s*(\d+(?:[.,]\d+)?)", r"mt\s*(\d+(?:[.,]\d+)?)m")))
    extracted_road = title.apply(lambda value: number_from_text(value, (r"duong\s*(\d+(?:[.,]\d+)?)", r"duong\s*(\d+(?:[.,]\d+)?)m", r"(\d+(?:[.,]\d+)?)m\s*duong")))

    df["bedrooms"] = coalesce_numeric(df["bedrooms"], extracted_bedrooms)
    df["floors"] = coalesce_numeric(df["floors"], extracted_floors)
    df["frontage_m"] = coalesce_numeric(df["frontage_m"], extracted_frontage)
    df["road_width_m"] = coalesce_numeric(df["road_width_m"], extracted_road)

    df["bedrooms"] = df["bedrooms"].fillna(df["bedrooms"].median()).round(0)
    df["floors"] = df["floors"].fillna(df["floors"].median()).round(0)
    df["frontage_m"] = df["frontage_m"].fillna(df["frontage_m"].median())
    df["road_width_m"] = df["road_width_m"].fillna(df["road_width_m"].median())

    # Keep only district-level location. Listing titles/addresses are noisy and
    # often break when opened in spreadsheet apps with the wrong encoding.
    df["address"] = df["district"]

    df = df[ML_COLUMNS]
    df = df.dropna(subset=["area_m2", "price_million_vnd"])
    df = df[df["price_million_vnd"] > 0]
    df = df[df["area_m2"] > 0]
    if "url" in raw.columns:
        df["_url"] = raw["url"].fillna("").astype(str)
        df = df.drop_duplicates(subset=["_url"])
        df = df.drop(columns=["_url"])
    else:
        df = df.drop_duplicates(subset=["address", "area_m2", "price_million_vnd"])
    return df.reset_index(drop=True)


def build_usa_compatible_dataset(clean: pd.DataFrame) -> pd.DataFrame:
    compatible = pd.DataFrame()

    # These names are kept only so the current Django app accepts the CSV.
    # Units are Da Nang-specific: price is million VND, not USD.
    compatible["Avg. Area Income"] = clean["area_m2"]
    compatible["Avg. Area House Age"] = clean["floors"]
    compatible["Avg. Area Number of Rooms"] = clean["bedrooms"] + 2
    compatible["Avg. Area Number of Bedrooms"] = clean["bedrooms"]
    compatible["Area Population"] = clean["district"].map(DISTRICT_CODES).fillna(0)
    compatible["Price"] = clean["price_million_vnd"]
    compatible["Address"] = clean["address"]
    return compatible[USA_FORMAT_COLUMNS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ML-ready Da Nang housing CSV files from scraped listings.")
    parser.add_argument("--input", default="data/danang_real_estate.csv")
    parser.add_argument("--ml-output", default="data/danang_housing_ml.csv")
    parser.add_argument("--usa-output", default="data/danang_housing_usa_format.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.input)
    ml_output = Path(args.ml_output)
    usa_output = Path(args.usa_output)

    clean = build_clean_ml_dataset(source_path)
    compatible = build_usa_compatible_dataset(clean)

    ml_output.parent.mkdir(parents=True, exist_ok=True)
    usa_output.parent.mkdir(parents=True, exist_ok=True)

    clean.to_csv(ml_output, index=False, encoding="utf-8")
    compatible.to_csv(usa_output, index=False, encoding="utf-8")

    print(f"Saved {len(clean)} rows to {ml_output}")
    print(f"Saved {len(compatible)} rows to {usa_output}")
    print(clean.head().to_string(index=False))


if __name__ == "__main__":
    main()
