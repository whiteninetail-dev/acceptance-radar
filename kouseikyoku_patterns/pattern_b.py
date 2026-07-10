"""
パターンB: 近畿厚生局など「施設種別ごとにセクション（表）があり、
都道府県が列、掲載日が行、1セル内に新規・変更／失効の両方が
段落（<p>）として縦に並ぶ」構造。

- 医科・歯科・薬局・訪問看護ごとに見出し＋別々の <table class="m-tableFlex"> が
  1ページ内に並ぶ（パターンF の東海北陸と似た「施設種別ごとにセクション」構成）。
- ヘッダ行は都道府県名の列（パターンF/Eの訪問看護ページと同じ「転置」構造）。
- 本文行は掲載日ごとに1行（新規・変更/失効で行が分かれない）で、
  各都道府県のセル内に「1つ目の<p> = 新規・変更、2つ目の<p> = 失効」という
  出現順で並ぶ。PDFが無い場合は「該当なし」とだけ書かれカテゴリラベル自体が
  省略されることがあるため、テキストではなく段落の出現順で判定する。
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_a import convert_japanese_date_to_ymd
from kouseikyoku_patterns.pattern_d import REIWA_KEISAI, _canonical_category
from pdf_facility_type import _normalize_label, _pdf_from_cell

SECTION_KEYWORDS: dict[str, list[str]] = {
    "医科": ["医科"],
    "歯科": ["歯科"],
    "薬局": ["薬局"],
    "訪問看護": ["訪問看護"],
}

# セル内の段落の出現順 -> カテゴリ
CATEGORY_ORDER = ("新規・変更", "辞退・失効")


def _find_section_table(soup: BeautifulSoup, pdf_type: str):
    keywords = SECTION_KEYWORDS.get(pdf_type, [pdf_type])
    for heading in soup.find_all(["h2", "h3"]):
        text = _normalize_label(heading.get_text())
        if any(kw in text for kw in keywords):
            table = heading.find_next("table", class_="m-tableFlex")
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


def get_category_info_pattern_b(
    soup: BeautifulSoup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
    *,
    prefecture: str,
) -> dict | None:
    if not prefecture:
        print("エラー: パターンBには都道府県（prefecture）の指定が必要です。")
        return None

    table = _find_section_table(soup, pdf_type)
    if table is None:
        print(f"エラー: パターンBで「{pdf_type}」のセクションが見つかりませんでした。")
        return None

    col_idx = _prefecture_column_index(table, prefecture)
    if col_idx is None:
        return None

    target_category = _canonical_category(category_name)
    if target_category not in CATEGORY_ORDER:
        return None
    category_index = CATEGORY_ORDER.index(target_category)

    rows = table.find_all("tr")
    for tr in rows[1:]:  # 先頭行はヘッダなのでスキップ
        cells = tr.find_all(["th", "td"])
        if col_idx >= len(cells):
            continue

        date_ymd = None
        match = REIWA_KEISAI.search(_normalize_label(cells[0].get_text()))
        if match:
            date_ymd = convert_japanese_date_to_ymd(match.group(0).replace("掲載", ""))

        # 最初に見つかった本文行 = 最新の掲載日。ここで確定させ、以降の行は見ない。
        target_cell = cells[col_idx]
        paragraphs = target_cell.find_all("p")
        if category_index >= len(paragraphs):
            return None
        href = _pdf_from_cell(paragraphs[category_index], page_url)
        if not href:
            return None
        return {"link": href, "date": date_ymd}
    return None
