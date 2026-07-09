"""
パターンD: 東北厚生局など「1ページに掲載日ごとの表があり、
各表の中でカテゴリ（新規・変更／失効等）ごとに都道府県別の行がグループ化」される構造。

- ページには掲載日の新しい順に <table class="datatable"> が並ぶ。最初（先頭）の表が最新。
- 各表内は「カテゴリ見出しセル（rowspan 付き th）→ 都道府県ごとの行」という構成。
- 列（医科・歯科・薬局・訪問看護）は表ヘッダ行から判定する。
- カテゴリの呼び方はサイトによって「辞退」「失効」など揺れがあるため、
  CATEGORY_SYNONYMS で同義語として扱う。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_a import convert_japanese_date_to_ymd
from pdf_facility_type import _header_column_index, _normalize_label, _pdf_from_cell

REIWA_KEISAI = re.compile(r"令和(\d+)年(\d+)月(\d+)日掲載")

# サイトによってカテゴリの呼称が異なるため、同じ意味の言葉を1つにまとめる
CATEGORY_SYNONYMS: dict[str, str] = {
    "新規・変更": "新規・変更",
    "辞退": "辞退・失効",
    "失効": "辞退・失効",
}


def _canonical_category(label: str) -> str:
    # サイトによっては「新規・変更」の中点が半角カタカナ中点(U+FF65)で
    # 書かれていることがあるため、正規の中点(U+30FB)に統一してから照合する。
    norm = _normalize_label(label).replace("･", "・")
    return CATEGORY_SYNONYMS.get(norm, norm)


def _date_for_table(table) -> str | None:
    for tag in table.find_all_previous(["p", "h2", "h3", "h4"]):
        text = tag.get_text()
        match = REIWA_KEISAI.search(text)
        if match:
            return convert_japanese_date_to_ymd(match.group(0).replace("掲載", ""))
    return None


def _latest_datatable(soup: BeautifulSoup):
    """
    「掲載日」見出しに紐づく最新の表を返す。
    - ページ上部には掲載日と無関係な datatable クラスの表（お知らせ等）が
      紛れ込むことがあるため、直前に「令和X年Y月Z日掲載」見出しを持つ表だけを対象にする。
    - サイトによっては、その見出し直後に中身が空の datatable（tbody だけで
      行が無い）が挟まることがあるため、実際に行を持つ表まで読み飛ばす。
    """
    for table in soup.find_all("table"):
        classes = table.get("class") or []
        if "datatable" not in classes:
            continue
        if not table.find("tr"):
            continue
        if _date_for_table(table) is not None:
            return table
    return None


def _iter_prefecture_rows(table):
    """
    表の行を (category_or_None, 都道府県名, data_cells) の順に返す。
    data_cells はヘッダ行の医科/歯科/薬局/訪問看護列と同じ並びに揃える
    （カテゴリ見出しセルや都道府県セルは含まない）。
    """
    current_category: str | None = None
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        if cells[0].has_attr("rowspan"):
            current_category = _canonical_category(cells[0].get_text())
            if len(cells) < 2:
                continue
            pref_name = _normalize_label(cells[1].get_text())
            data_cells = cells[2:]
        else:
            pref_name = _normalize_label(cells[0].get_text())
            data_cells = cells[1:]
        if not pref_name:
            continue
        yield current_category, pref_name, data_cells


def get_category_info_pattern_d(
    soup: BeautifulSoup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
    *,
    prefecture: str,
) -> dict | None:
    if not prefecture:
        print("エラー: パターンDには都道府県（prefecture）の指定が必要です。")
        return None

    table = _latest_datatable(soup)
    if table is None:
        return None

    col_idx = _header_column_index(table, pdf_type)
    if col_idx is None:
        return None

    target_category = _canonical_category(category_name)
    target_pref = _normalize_label(prefecture)

    for row_category, pref_name, data_cells in _iter_prefecture_rows(table):
        if pref_name != target_pref:
            continue
        if row_category is not None and row_category != target_category:
            continue
        data_idx = col_idx - 1
        if data_idx < 0 or data_idx >= len(data_cells):
            return None
        href = _pdf_from_cell(data_cells[data_idx], page_url)
        if not href:
            return None
        return {"link": href, "date": _date_for_table(table)}
    return None
