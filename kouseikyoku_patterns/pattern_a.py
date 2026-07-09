"""
パターンA: 関東信越・中国・九州（事務所ページ）など。

カテゴリ行は th または td。施設種別は表ヘッダ列または
リンク文言（指定訪問看護事業所）で特定する。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pdf_facility_type import pdf_href_from_table_with_headers, pdf_href_in_category_row

REIWA_DATE = re.compile(r"令和(\d+)年(\d+)月(\d+)日")


def convert_japanese_date_to_ymd(jp_date_str: str) -> str | None:
    match = REIWA_DATE.search(jp_date_str)
    if not match:
        return None
    reiwa_year, month, day = map(int, match.groups())
    year = 2018 + reiwa_year
    return f"{year}{month:02d}{day:02d}"


def extract_publication_date_ymd(table) -> str | None:
    """表より前の全文結合テキストから、直前に近い和暦日付を取得。"""
    if table is None:
        return None
    parts: list[str] = []
    for text_node in table.find_all_previous(string=True):
        parent = text_node.parent
        if parent and parent.name in ("script", "style"):
            continue
        parts.append(str(text_node))
    combined = "".join(reversed(parts))
    matches = list(REIWA_DATE.finditer(combined))
    if not matches:
        return None
    return convert_japanese_date_to_ymd(matches[-1].group(0))


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _find_category_cell(soup: BeautifulSoup, category_name: str):
    norm_category = _normalize_label(category_name)
    for cell in soup.find_all(["th", "td"]):
        if norm_category in _normalize_label(cell.get_text()):
            return cell
    return None


def _pdf_href_for_category(
    cell,
    page_url: str,
    pdf_type: str,
) -> str | None:
    table = cell.find_parent("table")
    row = cell.find_parent("tr")
    if table:
        href = pdf_href_from_table_with_headers(table, cell, page_url, pdf_type)
        if href:
            return href
    if row:
        return pdf_href_in_category_row(row, page_url, pdf_type)
    next_td = cell.find_next_sibling("td")
    if next_td:
        from pdf_facility_type import _pdf_from_cell

        return _pdf_from_cell(next_td, page_url)
    return None


def get_category_info(
    soup: BeautifulSoup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
) -> dict | None:
    try:
        cell = _find_category_cell(soup, category_name)
        if not cell:
            return None
        absolute_link = _pdf_href_for_category(cell, page_url, pdf_type)
        if not absolute_link:
            print(f"「{category_name}」の {pdf_type} PDF が見つかりませんでした。")
            return None
        table = cell.find_parent("table")
        date_str_ymd = extract_publication_date_ymd(table)
        return {"link": absolute_link, "date": date_str_ymd}
    except Exception as e:
        print(f"エラー: 「{category_name}」の情報取得中にエラーが発生しました。 {e}")
        return None
