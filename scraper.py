#!/usr/bin/env python3
"""
web-scraper-csv: scrape a product catalogue into clean CSV / Excel files.

Demo target: https://books.toscrape.com (a sandbox site built for scraping practice).

Examples:
  python3 scraper.py                       # all 50 pages -> books.csv + books.xlsx
  python3 scraper.py --pages 3             # first 3 pages only
  python3 scraper.py --details             # also open every product page (category, stock count, UPC)
  python3 scraper.py --min-rating 4 --max-price 20 -o cheap_good_books
"""
import argparse
import csv
import logging
import re
import sys
import time
from dataclasses import dataclass, asdict, fields
from typing import Iterator, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
log = logging.getLogger("scraper")


@dataclass
class Book:
    title: str
    price: float
    currency: str
    rating: int
    in_stock: bool
    url: str
    category: str = ""
    stock_count: Optional[int] = None
    upc: str = ""


# ---------------- HTTP ----------------
class Fetcher:
    """requests.Session with polite delay and retries (exponential backoff)."""

    def __init__(self, delay: float = 0.5, retries: int = 3, timeout: int = 20):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (portfolio scraper; contact via GitHub)"
        self.delay, self.retries, self.timeout = delay, retries, timeout

    def get(self, url: str) -> str:
        for attempt in range(1, self.retries + 1):
            try:
                r = self.s.get(url, timeout=self.timeout)
                r.raise_for_status()
                r.encoding = "utf-8"
                time.sleep(self.delay)
                return r.text
            except requests.RequestException as e:
                wait = 2 ** attempt
                log.warning("attempt %d/%d failed for %s (%s), retrying in %ds", attempt, self.retries, url, e, wait)
                time.sleep(wait)
        raise RuntimeError(f"giving up on {url}")


# ---------------- parsing (pure functions, unit-tested) ----------------
def parse_price(text: str):
    m = re.search(r"([^\d\s.,]*)\s*([\d.,]+)", text.strip())
    if not m:
        raise ValueError(f"no price in {text!r}")
    return float(m.group(2).replace(",", "")), (m.group(1) or "").replace("Â", "")


def parse_listing(html: str, page_url: str):
    """Returns (books on this page, absolute url of next page or None)."""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        price, cur = parse_price(card.select_one("p.price_color").get_text())
        rating_cls = [c for c in card.select_one("p.star-rating")["class"] if c != "star-rating"]
        books.append(Book(
            title=link["title"].strip(),
            price=price,
            currency=cur,
            rating=RATINGS.get(rating_cls[0], 0) if rating_cls else 0,
            in_stock="in stock" in card.select_one("p.availability").get_text().lower(),
            url=urljoin(page_url, link["href"]),
        ))
    nxt = soup.select_one("li.next a")
    return books, (urljoin(page_url, nxt["href"]) if nxt else None)


def parse_details(html: str, book: Book) -> Book:
    soup = BeautifulSoup(html, "html.parser")
    crumbs = soup.select("ul.breadcrumb li a")
    if len(crumbs) >= 3:
        book.category = crumbs[2].get_text(strip=True)
    table = {row.th.get_text(strip=True): row.td.get_text(strip=True) for row in soup.select("table tr") if row.th and row.td}
    book.upc = table.get("UPC", "")
    m = re.search(r"\((\d+) available\)", table.get("Availability", ""))
    book.stock_count = int(m.group(1)) if m else None
    return book


# ---------------- crawl ----------------
def crawl(fetcher: Fetcher, start_url: str, max_pages: int, details: bool) -> Iterator[Book]:
    url, page = start_url, 0
    while url and page < max_pages:
        page += 1
        books, url = parse_listing(fetcher.get(url), url)
        log.info("page %d: %d books", page, len(books))
        for b in books:
            if details:
                try:
                    parse_details(fetcher.get(b.url), b)
                except Exception as e:  # one bad product page shouldn't kill the run
                    log.warning("details failed for %s: %s", b.url, e)
            yield b


# ---------------- output ----------------
def write_csv(books: List[Book], path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(Book)])
        w.writeheader()
        for b in books:
            w.writerow(asdict(b))


def write_xlsx(books: List[Book], path: str):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        log.warning("openpyxl not installed, skipping Excel output")
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "books"
    cols = [fl.name for fl in fields(Book)]
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
    for b in books:
        ws.append([getattr(b, c) for c in cols])
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    for col, width in zip("ABCDEFGHI", (50, 9, 9, 7, 9, 60, 18, 12, 18)):
        ws.column_dimensions[col].width = width
    wb.save(path)
    return True


def summarize(books: List[Book]) -> str:
    if not books:
        return "no books"
    prices = [b.price for b in books]
    by_rating = {r: sum(1 for b in books if b.rating == r) for r in range(1, 6)}
    return (f"{len(books)} books | price min {min(prices):.2f} / avg {sum(prices)/len(prices):.2f} / "
            f"max {max(prices):.2f} | ratings {by_rating}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=BASE_URL, help="start page")
    ap.add_argument("--pages", type=int, default=50, help="max listing pages to crawl")
    ap.add_argument("--details", action="store_true", help="open each product page for extra fields")
    ap.add_argument("--min-rating", type=int, default=0)
    ap.add_argument("--max-price", type=float, default=None)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests (be polite)")
    ap.add_argument("-o", "--output", default="books", help="output file name without extension")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    books = [b for b in crawl(Fetcher(delay=args.delay), args.url, args.pages, args.details)
             if b.rating >= args.min_rating and (args.max_price is None or b.price <= args.max_price)]
    books.sort(key=lambda b: (-b.rating, b.price))
    write_csv(books, f"{args.output}.csv")
    xlsx = write_xlsx(books, f"{args.output}.xlsx")
    log.info("saved %s.csv%s", args.output, f" and {args.output}.xlsx" if xlsx else "")
    print(summarize(books))
    return 0


if __name__ == "__main__":
    sys.exit(main())
