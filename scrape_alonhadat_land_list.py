from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


LOG = logging.getLogger("alonhadat-land-list")
BASE_URL = "https://alonhadat.com.vn"
LIST_URL = "https://alonhadat.com.vn/can-ban-dat/da-nang"

OUTPUT_COLUMNS = [
    "source",
    "title",
    "price_million_vnd",
    "price_raw",
    "price_per_m2_million",
    "area_m2",
    "bedrooms",
    "floors",
    "frontage_m",
    "road_width_m",
    "direction",
    "property_type",
    "legal_status",
    "district",
    "address",
    "description",
    "url",
    "scraped_at",
]


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", value.replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_price_million(value: str | None) -> float | None:
    raw = strip_accents(value or "").lower()
    if any(token in raw for token in ("thoa thuan", "lien he")):
        return None
    number = parse_number(raw)
    if number is None:
        return None
    if "ty" in raw:
        return round(number * 1000, 2)
    if "trieu" in raw:
        return round(number, 2)
    return None


def district_from_text(value: str) -> str:
    plain = strip_accents(value).lower()
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
        if key in plain:
            return district
    return ""


def page_url(page: int) -> str:
    if page <= 1:
        return LIST_URL
    return f"{LIST_URL}/trang-{page}"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        }
    )
    return session


def get_soup(session: requests.Session, url: str) -> BeautifulSoup | None:
    response = session.get(url, timeout=25)
    plain = strip_accents(response.text).lower()
    if "xac-thuc-nguoi-dung" in response.url or "khong phai robot" in plain:
        LOG.warning("Anti-bot verification required: %s", response.url)
        return None
    if response.status_code != 200:
        LOG.warning("HTTP %s on %s", response.status_code, url)
        return None
    return BeautifulSoup(response.text, "html.parser")


def text_one(node, selector: str) -> str:
    found = node.select_one(selector)
    return compact_text(found.get_text(" ", strip=True)) if found else ""


def parse_card(article) -> dict[str, object] | None:
    link = article.select_one("a[href]")
    href = link.get("href", "") if link else ""
    if not re.search(r"-\d+\.html$", href):
        return None

    title = text_one(article, ".property-title") or compact_text(link.get_text(" ", strip=True))
    description = text_one(article, ".brief")
    land_text = strip_accents(" ".join([title, description])).lower()
    land_keywords = ("dat", "lo ", "lo dat", "nen", "block", "quy dat", "tich san")
    house_keywords = ("nha ", "can ho", "apartment", "biet thu", "toa can ho", "khach san")
    if not any(keyword in land_text for keyword in land_keywords):
        return None
    if any(keyword in land_text for keyword in house_keywords) and "dat" not in land_text:
        return None
    price_raw = text_one(article, ".price")
    area_raw = text_one(article, ".area")
    old_address = text_one(article, ".old-address")
    new_address = text_one(article, ".new-address")
    address = old_address or new_address

    road_width = parse_number(text_one(article, ".street-width"))
    floors = parse_number(text_one(article, ".floors"))
    bedrooms = parse_number(text_one(article, ".bedroom"))
    area_m2 = parse_number(area_raw)
    price_million = parse_price_million(price_raw)
    district = district_from_text(" ".join([address, title, description]))

    frontage = parse_number(
        re.search(r"ngang\s*([\d,.]+)", strip_accents(" ".join([title, description])).lower()).group(1)
        if re.search(r"ngang\s*([\d,.]+)", strip_accents(" ".join([title, description])).lower())
        else ""
    )

    if not price_million or not area_m2:
        return None

    return {
        "source": "alonhadat_land_list",
        "title": title,
        "price_million_vnd": price_million,
        "price_raw": price_raw,
        "price_per_m2_million": round(price_million / area_m2, 2),
        "area_m2": area_m2,
        "bedrooms": bedrooms,
        "floors": floors,
        "frontage_m": frontage,
        "road_width_m": road_width,
        "direction": "",
        "property_type": "land",
        "legal_status": "",
        "district": district,
        "address": district,
        "description": description[:1000],
        "url": urljoin(BASE_URL, href),
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_existing_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row["url"] for row in csv.DictReader(file) if row.get("url")}


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Da Nang land listings from Alonhadat list pages only.")
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--output", default="data/danang_land_raw.csv")
    parser.add_argument("--min-delay", type=float, default=10.0)
    parser.add_argument("--max-delay", type=float, default=20.0)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    output = Path(args.output)
    if args.fresh and output.exists():
        output.unlink()

    session = make_session()
    existing_urls = load_existing_urls(output)
    saved = 0

    for page in range(1, args.pages + 1):
        url = page_url(page)
        LOG.info("List page %s: %s", page, url)
        soup = get_soup(session, url)
        if soup is None:
            LOG.warning("Stopping because the site did not return a normal list page.")
            break

        rows = []
        for article in soup.select("article.property-item"):
            row = parse_card(article)
            if row and row["url"] not in existing_urls:
                existing_urls.add(str(row["url"]))
                rows.append(row)

        append_rows(output, rows)
        saved += len(rows)
        LOG.info("Saved %s new rows from page %s", len(rows), page)

        if not rows:
            break
        time.sleep(random.uniform(args.min_delay, args.max_delay))

    LOG.info("Done. Saved %s new rows to %s", saved, output)


if __name__ == "__main__":
    main()
