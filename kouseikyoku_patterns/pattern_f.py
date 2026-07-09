"""
パターンF: 東海北陸厚生局など「1ページ内に施設種別ごとのセクション（表）があり、
各表は都道府県が列、掲載日×カテゴリ（新規・変更／失効）が行」という構造。

- 医科・歯科・薬局・訪問看護ごとに見出し＋別々の <table class="m-table"> が
  1ページ内に並ぶ（バナーでページ内ジャンプするだけで、実際は同一ページ）。
- 各表のヘッダ行は都道府県名の列（パターンE の訪問看護ページと同じ「転置」構造）。
- 本文行は「掲載日セル（rowspan=2）＋新規・変更」行と「失効」行のペアが、
  掲載日の新しい順に並ぶ（パターンD と同様、日付は表内に直接書かれている）。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_a import convert_japanese_date_to_ymd
from kouseikyoku_patterns.pattern_d import _canonical_category
from pdf_facility_type import _normalize_label, _pdf_from_cell

DATE_RE = re.compile(r"令和(\d+)年(\d+)月(\d+)日")

SECTION_KEYWORDS: dict[str, list[str]] = {
    "医科": ["医科"],
    "歯科": ["歯科"],
    "薬局": ["薬局"],
    "訪問看護": ["訪問看護"],
}


def _find_section_table(soup: BeautifulSoup, pdf_type: str):
    keywords = SECTION_KEYWORDS.get(pdf_type, [pdf_type])
    for heading in soup.find_all(["h2", "h3"]):
        text = _normalize_label(heading.get_text())
        if any(kw in text for kw in keywords):
            table = heading.find_next("table", class_="m-table")
            if table:
                return table
    return None


def _prefecture_column_index(table, prefecture: str) -> int | None:
    target = _normalize_label(prefecture)
    header_row = table.find("tr")
    if not header_row:
        return None
    for idx, cell in enumerate(header_row.find_all(["th", "td"])):
        if _normalize_label(cell.get_text()) == target:
            return idx
    return None


def _has_rowspan(cell) -> bool:
    """rowspan="1" は「区切りなし」と同義なので、2以上のときだけ本物のグループ開始とみなす。"""
    value = cell.get("rowspan")
    if not value:
        return False
    try:
        return int(value) > 1
    except ValueError:
        return False


def _iter_date_category_rows(table):
    """
    表の行を (掲載日YYYYMMDD_or_None, カテゴリ, data_cells) の順に返す。
    data_cells はヘッダ行の都道府県列と同じ並びに揃える。
    """
    current_date: str | None = None
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        if _has_rowspan(cells[0]):
            match = DATE_RE.search(_normalize_label(cells[0].get_text()))
            if match:
                current_date = convert_japanese_date_to_ymd(match.group(0))
            if len(cells) < 2:
                continue
            category = _canonical_category(cells[1].get_text())
            data_cells = cells[2:]
        else:
            category = _canonical_category(cells[0].get_text())
            data_cells = cells[1:]
        yield current_date, category, data_cells


def get_category_info_pattern_f(
    soup: BeautifulSoup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
    *,
    prefecture: str,
) -> dict | None:
    if not prefecture:
        print("エラー: パターンFには都道府県（prefecture）の指定が必要です。")
        return None

    table = _find_section_table(soup, pdf_type)
    if table is None:
        print(f"エラー: パターンFで「{pdf_type}」のセクションが見つかりませんでした。")
        return None

    col_idx = _prefecture_column_index(table, prefecture)
    if col_idx is None:
        return None

    target_category = _canonical_category(category_name)
    latest_date: str | None = None

    for row_date, row_category, data_cells in _iter_date_category_rows(table):
        if latest_date is None and row_date is not None:
            latest_date = row_date
        if row_date != latest_date:
            # 最新の掲載日ブロックを通り過ぎたら打ち切る
            break
        if row_category != target_category:
            continue
        data_idx = col_idx - 1
        if data_idx < 0 or data_idx >= len(data_cells):
            return None
        href = _pdf_from_cell(data_cells[data_idx], page_url)
        if not href:
            return None
        return {"link": href, "date": latest_date}
    return None
