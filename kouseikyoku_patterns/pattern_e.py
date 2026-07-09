"""
パターンE: 四国厚生局など「カテゴリ×施設種別グループごとに別ページ」構造。

- 「新規・変更」「辞退・失効」×「医科等（医科/歯科/薬局）」「訪問看護」の
  組み合わせで、4つの別ページに分かれている（カテゴリは URL 選択で決まり、
  ページ内の表自体にカテゴリ区分は無い）。
- 医科等ページ: 都道府県が行、施設種別が列 → パターンD の表構造と同じなので
  そのヘルパーをそのまま再利用する。
- 訪問看護ページ: 都道府県が列見出しになっている転置構造で、専用の抽出関数を使う。
  また、日付見出しの直後に空の <table class="datatable"> が挟まることがあるため、
  パターンD 側で空テーブルをスキップするようにしてある。
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_d import (
    _canonical_category,
    _date_for_table,
    _iter_prefecture_rows,
    _latest_datatable,
)
from pdf_facility_type import _header_column_index, _normalize_label, _pdf_from_cell
from pdf_processing import DEFAULT_HEADERS

BASE = "https://kouseikyoku.mhlw.go.jp"
SHIKOKU_DIR = f"{BASE}/shikoku/gyomu/gyomu/hoken_kikan/shitei"

# (正規化後カテゴリ, 訪問看護か) -> ページURL
SHIKOKU_CATEGORY_URLS: dict[tuple[str, bool], str] = {
    ("新規・変更", False): f"{SHIKOKU_DIR}/index_00005.html",
    ("辞退・失効", False): f"{SHIKOKU_DIR}/index_00007.html",
    ("新規・変更", True): f"{SHIKOKU_DIR}/index_00009.html",
    ("辞退・失効", True): f"{SHIKOKU_DIR}/index_00010.html",
}


def _resolve_shikoku_url(category_name: str, pdf_type: str) -> str | None:
    category = _canonical_category(category_name)
    is_nursing = pdf_type == "訪問看護"
    return SHIKOKU_CATEGORY_URLS.get((category, is_nursing))


def _pdf_from_prefecture_column(table, prefecture: str, page_url: str) -> str | None:
    """訪問看護ページ用: 都道府県が列見出しになっている表からPDFを抽出する。"""
    target = _normalize_label(prefecture)
    col_idx: int | None = None
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if col_idx is None:
            for idx, cell in enumerate(cells):
                if _normalize_label(cell.get_text()) == target:
                    col_idx = idx
                    break
            continue
        if col_idx < len(cells):
            href = _pdf_from_cell(cells[col_idx], page_url)
            if href:
                return href
    return None


def fetch_category_info_pattern_e(
    hub_url: str,
    category_name: str,
    pdf_type: str = "医科",
    *,
    prefecture: str,
) -> dict | None:
    _ = hub_url  # 四国は組み合わせごとに固定URLが分かれているため、hub_url 自体は未使用
    if not prefecture:
        print("エラー: パターンEには都道府県（prefecture）の指定が必要です。")
        return None

    page_url = _resolve_shikoku_url(category_name, pdf_type)
    if not page_url:
        print(f"エラー: パターンEで未対応のカテゴリ/施設種別です: {category_name} / {pdf_type}")
        return None

    try:
        print(f"  カテゴリページ: {page_url}")
        response = requests.get(page_url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"エラー: ページ取得失敗: {page_url} ({e})")
        return None

    table = _latest_datatable(soup)
    if table is None:
        return None

    if pdf_type == "訪問看護":
        href = _pdf_from_prefecture_column(table, prefecture, page_url)
        if not href:
            return None
        return {"link": href, "date": _date_for_table(table)}

    col_idx = _header_column_index(table, pdf_type)
    if col_idx is None:
        return None

    target_pref = _normalize_label(prefecture)
    for _row_category, pref_name, data_cells in _iter_prefecture_rows(table):
        if pref_name != target_pref:
            continue
        data_idx = col_idx - 1
        if data_idx < 0 or data_idx >= len(data_cells):
            return None
        href = _pdf_from_cell(data_cells[data_idx], page_url)
        if not href:
            return None
        return {"link": href, "date": _date_for_table(table)}
    return None
