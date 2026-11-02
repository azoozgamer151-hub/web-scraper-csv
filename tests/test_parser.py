from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scraper  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def test_parse_price():
    assert scraper.parse_price("£51.77") == (51.77, "£")
    assert scraper.parse_price("Â£1,234.50") == (1234.50, "£")


def test_parse_listing():
    books, nxt = scraper.parse_listing((FIX / "listing.html").read_text(), "https://books.toscrape.com/")
    assert len(books) == 2
    b = books[0]
    assert b.title == "A Light in the Attic"           # full title from the title attribute, not the truncated text
    assert b.price == 51.77 and b.rating == 3 and b.in_stock
    assert b.url == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert books[1].rating == 1 and not books[1].in_stock
    assert nxt == "https://books.toscrape.com/catalogue/page-2.html"


def test_parse_details():
    b = scraper.Book("A Light in the Attic", 51.77, "£", 3, True, "u")
    scraper.parse_details((FIX / "detail.html").read_text(), b)
    assert b.category == "Poetry" and b.stock_count == 22 and b.upc == "a897fe39b1053632"


def test_outputs(tmp_path):
    books = [scraper.Book("A", 10.0, "£", 5, True, "u1"), scraper.Book("B", 20.0, "£", 2, False, "u2")]
    scraper.write_csv(books, tmp_path / "out.csv")
    lines = (tmp_path / "out.csv").read_text().splitlines()
    assert lines[0].startswith("title,price,currency,rating")
    assert len(lines) == 3
    assert "2 books" in scraper.summarize(books)
