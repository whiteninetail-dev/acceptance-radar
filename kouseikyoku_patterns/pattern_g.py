"""
パターンG: 中国四国厚生局（中国地方）など「都道府県ごとにセクション（表）があり、
各表は施設種別が列、掲載日×カテゴリが行だが、カテゴリはデータセル内のリンク文言
（例:「新規・変更［72KB］」「失効 [該当なし]」）に埋め込まれている」構造。

- 都道府県ごとの見出し（h2, 例:「鳥取県」）＋その直後の <table class="datatable"> が
  ページ内に複数（県の数だけ）並ぶ。
- 表のヘッダ行は 医科/歯科/薬局/訪看 の列。
- 本文行は「掲載日セル（rowspan=2, 'R8.7.6掲載' 形式の和暦略記）＋施設種別ごとのセル」の
  ペアが掲載日の新しい順に並ぶ。1件目の行だけ先頭に日付セルが付き、2件目（失効側）は
  施設種別セルのみで列数が1少ない。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_d import _canonical_category
from pdf_facility_type import _header_column_index, _normalize_label, _pdf_from_cell

REIWA_ABBR = re.compile(r"R(\d+)\.(\d+)\.(\d+)")

CATEGORY_LABELS = ("新規・変更", "失効", "辞退")


def _date_from_abbr(text: str) -> str | None:
    match = REIWA_ABBR.search(_normalize_label(text))
    if not match:
        return None
    reiwa_year, month, day = (int(v) for v in match.groups())
    year = 2018 + reiwa_year
    return f"{year}{month:02d}{day:02d}"


def _cell_category(cell) -> str | None:
    text = _normalize_label(cell.get_text())
    for label in CATEGORY_LABELS:
        if text.startswith(_canonical_category(label)) or text.startswith(label):
            return _canonical_category(label)
    return None


def _find_prefecture_table(soup: BeautifulSoup, prefecture: str):
    target = _normalize_label(prefecture)
    for heading in soup.find_all(["h2", "h3"]):
        if _normalize_label(heading.get_text()) == target:
            table = heading.find_next("table")
            if table:
                return table
    return None


def get_category_info_pattern_g(
    soup: BeautifulSoup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
    *,
    prefecture: str,
) -> dict | None:
    if not prefecture:
        print("エラー: パターンGには都道府県（prefecture）の指定が必要です。")
        return None

    table = _find_prefecture_table(soup, prefecture)
    if table is None:
        print(f"エラー: パターンGで「{prefecture}」のセクションが見つかりませんでした。")
        return None

    col_idx = _header_column_index(table, pdf_type)
    if col_idx is None:
        return None

    rows = table.find_all("tr")
    if not rows:
        return None
    header_cell_count = len(rows[0].find_all(["th", "td"]))

    target_category = _canonical_category(category_name)
    latest_date: str | None = None
    current_date: str | None = None

    for tr in rows[1:]:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        if len(cells) == header_cell_count:
            # 掲載日セル付きの行（各掲載日ブロックの1行目）
            found_date = _date_from_abbr(cells[0].get_text())
            if found_date:
                current_date = found_date
            data_cells = cells[1:]
        else:
            data_cells = cells

        if latest_date is None and current_date is not None:
            latest_date = current_date
        if current_date != latest_date:
            # 最新の掲載日ブロックを通り過ぎたら打ち切る
            break

        data_idx = col_idx - 1
        if data_idx < 0 or data_idx >= len(data_cells):
            continue
        cell = data_cells[data_idx]
        if _cell_category(cell) != target_category:
            continue
        href = _pdf_from_cell(cell, page_url)
        if not href:
            return None
        return {"link": href, "date": latest_date}
    return None
