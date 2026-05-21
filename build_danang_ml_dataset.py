from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


OUTPUT_COLUMNS = [
    "property_type",
    "area_m2",
    "frontage_m",
    "road_width_m",
    "district",
    "district_code",
    "price_million_vnd",
    "price_per_m2_million",
    "source",
    "url",
]

DISTRICT_CODES = {
    "Hai Chau": 1,
    "Thanh Khe": 2,
    "Son Tra": 3,
    "Ngu Hanh Son": 4,
    "Lien Chieu": 5,
    "Cam Le": 6,
    "Hoa Vang": 7,
}

MIN_PRICE_PER_M2_BY_DISTRICT = {
    "Hai Chau": 20,
    "Thanh Khe": 15,
    "Son Tra": 20,
    "Ngu Hanh Son": 10,
    "Lien Chieu": 8,
    "Cam Le": 8,
    "Hoa Vang": 1,
}

NON_DANANG_PATTERNS = (
    r"\bquang nam\b",
    r"\bdai loc\b",
    r"\bai nghia\b",
    r"\bduy xuyen\b",
    r"\bnam giang\b",
    r"\bdai hiep\b",
    r"\bdien ban\b",
)

def strip_accents(value: object) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def normalize_text_key(value: object) -> str:
    text = strip_accents(value).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\bes\d+\b", " ", text)
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    skip_words = {
        "ban",
        "can",
        "gap",
        "chinh",
        "chu",
        "gia",
        "tot",
        "dep",
        "lo",
        "dat",
        "nen",
        "quan",
        "huyen",
        "hai",
        "chau",
        "thanh",
        "khe",
        "son",
        "tra",
        "ngu",
        "hanh",
        "lien",
        "chieu",
        "cam",
        "le",
        "hoa",
        "vang",
        "dt",
        "tl",
        "ty",
        "tytl",
    }
    words = [word for word in text.split() if word not in skip_words]
    return " ".join(words[:18])


def parse_number(value: object) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", str(value or "").replace(" ", ""))
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def is_price_per_m2(value: object) -> bool:
    text = strip_accents(value).lower().replace(" ", "")
    return ("/m2" in text or "/m²" in text) and ("trieu" in text or "tr" in text)


def number_from_text(value: object, patterns: tuple[str, ...]) -> float | None:
    text = strip_accents(value).lower()
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def district_from_text(value: object) -> str:
    text = strip_accents(value).lower().replace("-", " ")
    for key, district in {
        "hai chau": "Hai Chau",
        "thanh khe": "Thanh Khe",
        "son tra": "Son Tra",
        "ngu hanh son": "Ngu Hanh Son",
        "lien chieu": "Lien Chieu",
        "cam le": "Cam Le",
        "hoa vang": "Hoa Vang",
    }.items():
        if key in text:
            return district
    return ""


def is_outside_danang(value: object) -> bool:
    text = strip_accents(value).lower().replace("-", " ")
    return any(re.search(pattern, text) for pattern in NON_DANANG_PATTERNS)


def infer_property_type(title: object, description: object, current_type: object) -> str:
    # Uu tien title vi description cua cac trang thuong co nhieu chu boilerplate
    # nhu "nha dat", de gay nham lan giua tin dat va tin nha.
    text = strip_accents(f"{title} {current_type}").lower()

    house_patterns = (
        r"\bnha\b",
        r"\bcan ho\b",
        r"\btoa can ho\b",
        r"\bbiet thu\b",
        r"\bvilla\b",
        r"\bkhach san\b",
        r"\bday tro\b",
        r"\bphong tro\b",
        r"\bnha pho\b",
    )
    land_patterns = (
        r"\bdat\b",
        r"\blo dat\b",
        r"\blo\b",
        r"\bnen\b",
        r"\bdat nen\b",
        r"\bblock\b",
        r"\bquy dat\b",
    )

    # Tin "dat tang nha" van xem la dat vi gia tri chinh thuong la lo dat.
    if re.search(r"\bdat\b.*\btang\b.*\bnha\b", text):
        return "land"
    if any(re.search(pattern, text) for pattern in house_patterns):
        return "house"
    if any(re.search(pattern, text) for pattern in land_patterns):
        return "land"
    return "land"


def coalesce_numeric(series: pd.Series, fallback: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.fillna(fallback)


def build_dataset(source_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(source_path)
    title = raw["title"].fillna("")
    description = raw["description"].fillna("")
    url = raw.get("url", pd.Series([""] * len(raw))).fillna("")

    df = pd.DataFrame()
    df["title_key"] = title.apply(normalize_text_key)
    df["property_type"] = [
        infer_property_type(t, d, p)
        for t, d, p in zip(title, description, raw.get("property_type", ""))
    ]
    df = df[df["property_type"].eq("land")].copy()

    df["area_m2"] = pd.to_numeric(raw["area_m2"], errors="coerce")
    df["frontage_m"] = pd.to_numeric(raw["frontage_m"], errors="coerce")
    df["road_width_m"] = pd.to_numeric(raw["road_width_m"], errors="coerce")

    df["price_million_vnd"] = pd.to_numeric(raw["price_million_vnd"], errors="coerce")
    df["price_per_m2_million"] = pd.to_numeric(raw["price_per_m2_million"], errors="coerce")
    price_raw = raw.get("price_raw", pd.Series([""] * len(raw))).fillna("")

    text_for_fallback = url.astype(str) + " " + title.astype(str) + " " + description.astype(str)
    outside_danang = text_for_fallback.loc[df.index].apply(is_outside_danang)
    df = df[~outside_danang].copy()
    title = title.loc[df.index]
    description = description.loc[df.index]
    url = url.loc[df.index]
    price_raw = price_raw.loc[df.index]
    text_for_fallback = text_for_fallback.loc[df.index]

    district_source = raw["district"].fillna("").astype(str)
    district_source = district_source.loc[df.index]
    district_fallback = text_for_fallback.apply(district_from_text)
    df["district"] = district_source.where(district_source.str.strip().ne(""), district_fallback)
    df["district_code"] = df["district"].map(DISTRICT_CODES)

    df["frontage_m"] = coalesce_numeric(
        df["frontage_m"],
        title.apply(lambda value: number_from_text(value, (r"ngang\s*(\d+(?:[.,]\d+)?)", r"(\d+(?:[.,]\d+)?)\s*x\s*\d"))),
    )
    df["road_width_m"] = coalesce_numeric(
        df["road_width_m"],
        title.apply(lambda value: number_from_text(value, (r"duong\s*(\d+(?:[.,]\d+)?)", r"duong\s*(\d+(?:[.,]\d+)?)m"))),
    )
    df["frontage_m"] = df["frontage_m"].fillna(df["frontage_m"].median())
    df["road_width_m"] = df["road_width_m"].fillna(df["road_width_m"].median())

    df["source"] = raw["source"].fillna("")
    df["url"] = url

    df = df.dropna(subset=[
        "area_m2",
        "district_code",
        "price_million_vnd",
    ])
    df = df[
        (df["area_m2"].between(20, 5000))
        & (df["price_million_vnd"].between(100, 200000))
        & (df["frontage_m"].between(0, 100))
        & (df["road_width_m"].between(0, 100))
    ].copy()

    df["price_per_m2_million"] = (
        df["price_per_m2_million"]
        .fillna((df["price_million_vnd"] / df["area_m2"]).round(2))
    )

    price_per_m2_mask = price_raw.apply(is_price_per_m2)
    price_per_m2_from_raw = price_raw.apply(parse_number)
    df.loc[price_per_m2_mask, "price_per_m2_million"] = price_per_m2_from_raw[price_per_m2_mask]
    df.loc[price_per_m2_mask, "price_million_vnd"] = (
        df.loc[price_per_m2_mask, "price_per_m2_million"]
        * df.loc[price_per_m2_mask, "area_m2"]
    ).round(2)

    df = df[
        df["price_per_m2_million"].between(1, 350)
        & df["price_million_vnd"].between(100, 200000)
    ].copy()

    district_bounds = df.groupby("district")["price_per_m2_million"].transform(
        lambda values: values.quantile(0.75) + 2.5 * (values.quantile(0.75) - values.quantile(0.25))
    )
    district_floor = df.groupby("district")["price_per_m2_million"].transform(
        lambda values: max(values.quantile(0.25) - 2.5 * (values.quantile(0.75) - values.quantile(0.25)), 1)
    )
    df = df[
        (df["price_per_m2_million"] >= district_floor)
        & (df["price_per_m2_million"] <= district_bounds)
    ].copy()
    min_price_by_district = df["district"].map(MIN_PRICE_PER_M2_BY_DISTRICT).fillna(1)
    df = df[df["price_per_m2_million"] >= min_price_by_district].copy()

    df = df.drop_duplicates(subset=["url"])

    numeric_dedupe_columns = [
        "area_m2",
        "frontage_m",
        "road_width_m",
        "price_million_vnd",
    ]
    for column in numeric_dedupe_columns:
        df[f"{column}_key"] = pd.to_numeric(df[column], errors="coerce").round(1)
    df["area_m2_fuzzy_key"] = (pd.to_numeric(df["area_m2"], errors="coerce") / 5).round(0)
    df["price_million_fuzzy_key"] = (pd.to_numeric(df["price_million_vnd"], errors="coerce") / 500).round(0)

    exact_keys = [
        "property_type",
        "district",
        "area_m2_key",
        "frontage_m_key",
        "road_width_m_key",
        "price_million_vnd_key",
    ]
    df = df.drop_duplicates(subset=exact_keys)

    title_keys = [
        "title_key",
        "district",
        "area_m2_key",
        "price_million_vnd_key",
    ]
    df = df.drop_duplicates(subset=title_keys)

    fuzzy_title_keys = [
        "title_key",
        "district",
        "area_m2_fuzzy_key",
        "price_million_fuzzy_key",
    ]
    df = df.drop_duplicates(subset=fuzzy_title_keys)

    return df[OUTPUT_COLUMNS].reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one clean Da Nang land dataset for land price prediction.")
    parser.add_argument("--input", default="data/danang_land_raw.csv")
    parser.add_argument("--output", default="data/danang_land_dataset.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    dataset = build_dataset(Path(args.input))

    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output, index=False, encoding="utf-8")

    print(f"Saved {len(dataset)} rows to {output}")
    print(dataset["property_type"].value_counts().to_string())
    print(dataset.head().to_string(index=False))


if __name__ == "__main__":
    main()
