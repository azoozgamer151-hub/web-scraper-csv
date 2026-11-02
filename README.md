# web-scraper-csv: catalogue scraper to CSV + Excel

Scrapes every product from a paginated catalogue and exports clean, sorted data to **CSV** and **Excel**.
Demo target: [books.toscrape.com](https://books.toscrape.com), a sandbox site made for scraping practice.

**Real run (all 50 pages):** `1000 books | price min 10.00 / avg 35.07 / max 59.99 | ratings {1: 226, 2: 196, 3: 203, 4: 179, 5: 196}`

Output: [`sample/books.csv`](sample/books.csv) · [`sample/books.xlsx`](sample/books.xlsx) (bold header, filters, frozen top row)

## What it does
- Follows pagination automatically until the last page
- Extracts title, price, currency, star rating, stock status and product URL
- `--details` opens every product page for category, exact stock count and UPC
- Filters (`--min-rating`, `--max-price`) and sorts best-rated / cheapest first
- Polite by default: delay between requests, retries with exponential backoff, clear logs
- Parsing is separated into pure functions with unit tests (HTML fixtures, no network needed)

## Usage
```bash
pip install -r requirements.txt
python3 scraper.py                                   # everything -> books.csv + books.xlsx
python3 scraper.py --pages 3                         # quick run
python3 scraper.py --details                         # + category, stock count, UPC
python3 scraper.py --min-rating 4 --max-price 20 -o deals
```

## Tests
```bash
python3 -m pytest -q
```

## Adapting it to another site
Only `parse_listing()` and `parse_details()` change (CSS selectors). Fetching, retries,
pagination, filtering and the CSV/Excel export stay the same. Always check the site's
terms and robots.txt, and keep the delay reasonable.

## License
MIT
