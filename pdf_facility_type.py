"""施設種別（医科・歯科・薬局・訪問看護）と PDF リンクの対応。"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# config.ini / setup で使う表示名
PDF_TYPES_BASIC = ("医科", "歯科", "薬局")
PDF_TYPES_WITH_HOME_NURSING = ("医科", "歯科", "薬局", "訪問看護")

# 表ヘッダ・リンク文言の照合（九州は「指定訪問看護事業所」等）
HEADER_KEYWORDS: dict[str, list[str]] = {
    "医科": ["医科"],
    "歯科": ["歯科"],
    "薬局": ["薬局"],
    "訪問看護": ["訪問看護", "指定訪問看護", "訪看"],
}

ANCHOR_KEYWORDS: dict[str, list[str]] = {
    "医科": ["医科"],
    "歯科": ["歯科"],
    "薬局": ["薬局"],
    "訪問看護": ["指定訪問看護", "訪問看護"],
}


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _is_pdf_anchor(anchor) -> bool:
    href = anchor.get("href", "")
    text = anchor.get_text()
    return bool(
        href.lower().endswith(".pdf")
        or re.search(r"/\d{6,}\.pdf", href, re.I)
        or "pdf" in text.lower()
        or "PDF" in text
    )


def _match_keywords(text: str, pdf_type: str) -> bool:
    norm = _normalize_label(text)
    # 「医科（歯科併設含む）」のような注記内の語で誤マッチしないよう、
    # 丸括弧より前の部分を優先的に照合対象にする（括弧を除くと空になる場合は全文で照合）。
    main_part = re.split(r"[（(]", norm)[0] or norm
    for kw in HEADER_KEYWORDS.get(pdf_type, [pdf_type]):
        if _normalize_label(kw) in main_part:
            return True
    return False


def _header_column_index(table, pdf_type: str) -> int | None:
    """関東信越など: ヘッダ行の「医科」「歯科」列インデックス。"""
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        for idx, cell in enumerate(cells):
            if _match_keywords(cell.get_text(), pdf_type):
                return idx
    return None


def _pdf_from_cell(cell, page_url: str) -> str | None:
    if not cell:
        return None
    text = cell.get_text()
    if "該当なし" in text or "該当無し" in text:
        return None
    for anchor in cell.find_all("a", href=True):
        if _is_pdf_anchor(anchor):
            return urljoin(page_url, anchor["href"])
    return None


def pdf_href_in_category_row(
    row,
    page_url: str,
    pdf_type: str,
    *,
    column_index: int | None = None,
) -> str | None:
    """カテゴリ行から施設種別に応じた PDF URL を取得。"""
    cells = row.find_all(["th", "td"])
    if column_index is not None and column_index < len(cells):
        href = _pdf_from_cell(cells[column_index], page_url)
        if href:
            return href

    # 九州など: リンク文言で照合（指定訪問看護事業所）
    for anchor in row.find_all("a", href=True):
        if not _is_pdf_anchor(anchor):
            continue
        if _match_keywords(anchor.get_text(), pdf_type):
            return urljoin(page_url, anchor["href"])
    return None


def pdf_href_from_table_with_headers(
    table,
    category_cell,
    page_url: str,
    pdf_type: str,
) -> str | None:
    row = category_cell.find_parent("tr")
    if not row:
        return None
    col_idx = _header_column_index(table, pdf_type)
    return pdf_href_in_category_row(row, page_url, pdf_type, column_index=col_idx)


def pdf_href_from_column_header_table(
    table,
    page_url: str,
    pdf_type: str,
) -> str | None:
    """北海道など: 先頭データ行の「医科|歯科|薬局」表。"""
    col_idx = _header_column_index(table, pdf_type)
    if col_idx is None:
        return None
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) <= col_idx:
            continue
        if any(_match_keywords(c.get_text(), pdf_type) for c in cells):
            continue
        href = _pdf_from_cell(cells[col_idx], page_url)
        if href:
            return href
    return None
