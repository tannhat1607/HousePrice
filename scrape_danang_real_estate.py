from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


LOG = logging.getLogger("danang-real-estate-scraper")

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


@dataclass(frozen=True)
class Source:
    name: str
    list_url: str
    page_url: Callable[[str, int], str]
    base_url: str
    list_link_selectors: tuple[str, ...]
    detail_link_filter: Callable[[str], bool]


def alonhadat_page_url(list_url: str, page: int) -> str:
    if page <= 1:
        return list_url
    if list_url.endswith(".html"):
        return list_url.replace(".html", f"/trang-{page}.html")
    return f"{list_url.rstrip('/')}/trang-{page}"


def batdongsan_page_url(list_url: str, page: int) -> str:
    if page <= 1:
        return list_url
    return f"{list_url}/p{page}"


SOURCES = {
    "alonhadat": Source(
        name="alonhadat",
        list_url="https://alonhadat.com.vn/can-ban-nha-dat/da-nang",
        page_url=alonhadat_page_url,
        base_url="https://alonhadat.com.vn",
        list_link_selectors=(
            ".content-item h3 a[href]",
            ".search-content .item a.title[href]",
            ".ct_title a[href]",
            ".item .title a[href]",
            "a[href*='.html']",
        ),
        detail_link_filter=lambda href: href.startswith("/") and re.search(r"-\d+\.html$", href) is not None,
    ),
    "alonhadat_land": Source(
        name="alonhadat_land",
        list_url="https://alonhadat.com.vn/can-ban-dat/da-nang",
        page_url=alonhadat_page_url,
        base_url="https://alonhadat.com.vn",
        list_link_selectors=(
            ".content-item h3 a[href]",
            ".search-content .item a.title[href]",
            ".ct_title a[href]",
            ".item .title a[href]",
            "a[href*='.html']",
        ),
        detail_link_filter=lambda href: href.startswith("/") and re.search(r"-\d+\.html$", href) is not None,
    ),
    "batdongsan": Source(
        name="batdongsan",
        list_url="https://batdongsan.com.vn/nha-dat-ban-tp-da-nang",
        page_url=batdongsan_page_url,
        base_url="https://batdongsan.com.vn",
        list_link_selectors=(
            "a.js__product-link-for-product-id[href]",
            "a.js__card-title[href]",
            "a[href*='-pr'][href]",
        ),
        detail_link_filter=lambda href: ("-pr" in href) and href.startswith("/"),
    ),
}


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


def parse_int(value: str | None) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_price_million(value: str | None) -> float | None:
    if not value:
        return None
    raw = strip_accents(value).lower()
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


def is_price_per_m2(value: str | None) -> bool:
    raw = strip_accents(value or "").lower().replace(" ", "")
    has_area_unit = "/m2" in raw or "/m\u00b2" in raw
    return has_area_unit and "trieu" in raw


def first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = compact_text(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def all_texts(soup: BeautifulSoup, selector: str) -> list[str]:
    return [compact_text(node.get_text(" ", strip=True)) for node in soup.select(selector)]


def field_from_pairs(pairs: dict[str, str], *keys: str) -> str:
    normalized_keys = [strip_accents(key).lower() for key in keys]
    for label, value in pairs.items():
        normalized_label = strip_accents(label).lower()
        if any(key in normalized_label for key in normalized_keys):
            return value
    return ""


def regex_value(text: str, patterns: tuple[str, ...]) -> str:
    plain = strip_accents(text)
    for pattern in patterns:
        match = re.search(pattern, plain, re.IGNORECASE)
        if match:
            return compact_text(match.group(1))
    return ""


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
            "Connection": "keep-alive",
        }
    )
    return session


def get_soup(session: requests.Session, url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=25)
            if "xac-thuc-nguoi-dung" in response.url or "khong phai robot" in strip_accents(response.text).lower():
                LOG.warning("Anti-bot verification required: %s", response.url)
                return None
            if response.status_code == 200 and response.text:
                return BeautifulSoup(response.text, "html.parser")
            LOG.warning("HTTP %s on %s", response.status_code, url)
        except requests.RequestException as exc:
            LOG.warning("Request failed on attempt %s/%s: %s", attempt, retries, exc)
        time.sleep(random.uniform(2.5, 5.0))
    return None


def collect_links(session: requests.Session, source: Source, pages: int, delay: tuple[float, float]) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for page in range(1, pages + 1):
        url = source.page_url(source.list_url, page)
        LOG.info("[%s] list page %s: %s", source.name, page, url)
        soup = get_soup(session, url)
        if not soup:
            LOG.warning("Skip list page %s because it could not be loaded", page)
            continue

        page_links: list[str] = []
        for selector in source.list_link_selectors:
            for node in soup.select(selector):
                href = node.get("href") or ""
                if not source.detail_link_filter(href):
                    continue
                full_url = urljoin(source.base_url, href.split("#")[0])
                if full_url not in seen:
                    seen.add(full_url)
                    page_links.append(full_url)
                    links.append(full_url)

        LOG.info("Found %s new links on page %s", len(page_links), page)
        if page > 1 and not page_links:
            LOG.info("No links found; stopping pagination for %s", source.name)
            break
        time.sleep(random.uniform(*delay))

    return links


def detail_pairs(soup: BeautifulSoup) -> dict[str, str]:
    pairs: dict[str, str] = {}

    for row in soup.select("tr, li, .re__pr-specs-content-item, .re__pr-short-description-item, .spec-item"):
        texts = [compact_text(text) for text in row.stripped_strings]
        texts = [text for text in texts if text]
        if len(texts) >= 2:
            label = texts[0].rstrip(":")
            value = texts[-1]
            if label and value and label != value:
                pairs[label] = value

    labels = all_texts(soup, "dt, th, label, .property-label")
    values = all_texts(soup, "dd, td, .property-value")
    for label, value in zip(labels, values):
        if label and value:
            pairs[label.rstrip(":")] = value

    return pairs


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


def parse_detail(session: requests.Session, source: Source, url: str) -> dict[str, object] | None:
    soup = get_soup(session, url)
    if not soup:
        return None

    body_text = compact_text(soup.get_text(" ", strip=True))
    pairs = detail_pairs(soup)

    title = first_text(
        soup,
        (
            "h1.re__pr-title",
            "h1.title",
            "h1.property-title",
            "h1",
            ".re__card-title",
        ),
    )
    price_raw = first_text(
        soup,
        (
            ".re__pr-short-description-pr-price",
            ".js__pr-price",
            ".price strong",
            ".ct-price span",
            ".moreinfor .price",
            "[class*='price']",
        ),
    ) or regex_value(body_text, (r"(\d+(?:[.,]\d+)?\s*(?:ty|trieu)(?:/\s*m2)?)",))
    area_raw = first_text(
        soup,
        (
            ".re__pr-short-description-pr-area",
            ".acreage strong",
            ".ct-dt-dientich span",
            ".moreinfor .acreage",
            "[class*='area']",
        ),
    ) or regex_value(body_text, (r"(\d+(?:[.,]\d+)?\s*(?:m2|m\\u00b2))",))

    address = first_text(
        soup,
        (
            ".re__pr-short-description-item-value",
            ".re__pr-address span",
            ".address span",
            ".full-address",
            "[class*='address']",
        ),
    )
    description = first_text(
        soup,
        (
            ".re__detail-content",
            ".re__section-body",
            ".detail-content",
            ".description",
            "[class*='description']",
        ),
    )

    breadcrumb = " ".join(all_texts(soup, ".re__breadcrumb a, .breadcrumb a, nav a"))
    district = district_from_text(" ".join([address, breadcrumb, title, url]))

    bedrooms = (
        parse_int(field_from_pairs(pairs, "phong ngu", "so phong"))
        or parse_int(regex_value(body_text, (r"(\d+)\s*phong ngu",)))
    )
    floors = (
        parse_int(field_from_pairs(pairs, "so tang", "tang"))
        or parse_int(regex_value(body_text, (r"(\d+)\s*tang",)))
    )

    frontage = field_from_pairs(pairs, "mat tien", "ngang")
    road_width = field_from_pairs(pairs, "duong vao", "duong truoc nha", "rong duong")
    direction = field_from_pairs(pairs, "huong nha", "huong")
    property_type = field_from_pairs(pairs, "loai hinh", "loai bds", "loai nha dat", "loai")
    legal_status = field_from_pairs(pairs, "phap ly", "giay to")

    parsed_price = parse_price_million(price_raw)
    area_m2 = parse_number(area_raw)
    if parsed_price and area_m2 and is_price_per_m2(price_raw):
        price_million = round(parsed_price * area_m2, 2)
        price_per_m2 = parsed_price
    else:
        price_million = parsed_price
        price_per_m2 = round(price_million / area_m2, 2) if price_million and area_m2 else None

    if not any((title, price_raw, area_raw, address)):
        return None

    return {
        "source": source.name,
        "title": title,
        "price_million_vnd": price_million,
        "price_raw": price_raw,
        "price_per_m2_million": price_per_m2,
        "area_m2": area_m2,
        "bedrooms": bedrooms,
        "floors": floors,
        "frontage_m": parse_number(frontage),
        "road_width_m": parse_number(road_width),
        "direction": direction,
        "property_type": property_type,
        "legal_status": legal_status,
        "district": district,
        "address": address,
        "description": description[:1000],
        "url": url,
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
    with path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Da Nang real-estate listings for house-price ML data.")
    parser.add_argument("--source", choices=sorted(SOURCES), default="alonhadat")
    parser.add_argument("--pages", type=int, default=5, help="Number of list pages to crawl.")
    parser.add_argument("--output", default="data/danang_real_estate.csv")
    parser.add_argument("--min-delay", type=float, default=2.0)
    parser.add_argument("--max-delay", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=0, help="Max detail listings to scrape. 0 means no limit.")
    parser.add_argument("--fresh", action="store_true", help="Overwrite the output CSV instead of resuming.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.pages < 1:
        raise SystemExit("--pages must be >= 1")
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("Invalid delay range")

    source = SOURCES[args.source]
    output_path = Path(args.output)
    if args.fresh and output_path.exists():
        output_path.unlink()

    session = make_session()
    existing_urls = load_existing_urls(output_path)

    LOG.info("Source: %s", source.name)
    LOG.info("Output: %s", output_path)
    LOG.info("Resume mode: %s existing URLs", len(existing_urls))

    links = collect_links(session, source, args.pages, (args.min_delay, args.max_delay))
    links = [link for link in links if link not in existing_urls]
    if args.limit > 0:
        links = links[: args.limit]

    LOG.info("Scraping %s detail pages", len(links))
    buffer: list[dict[str, object]] = []
    saved = 0

    for index, url in enumerate(links, start=1):
        LOG.info("[%s/%s] %s", index, len(links), url)
        row = parse_detail(session, source, url)
        if row:
            buffer.append(row)
            LOG.info("OK: %s | %s | %s m2", row["title"], row["price_raw"], row["area_m2"])
        else:
            LOG.warning("No usable data: %s", url)

        if len(buffer) >= 10:
            append_rows(output_path, buffer)
            saved += len(buffer)
            buffer.clear()
            LOG.info("Saved %s rows so far", saved)

        time.sleep(random.uniform(args.min_delay, args.max_delay))

    append_rows(output_path, buffer)
    saved += len(buffer)
    LOG.info("Done. Saved %s new rows to %s", saved, output_path)


if __name__ == "__main__":
    main()
