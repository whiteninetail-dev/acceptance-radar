"""
パターンC: 北海道厚生局など。

入口ページ（hub）からカテゴリ別ページへ1階層下がり、
各ページ先頭の掲載分（最新）の PDF（医科列）を取得する。

掲載は毎月1日・15日頃 → チェック推奨: 2日・16日（休日なら翌営業日）
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from kouseikyoku_patterns.pattern_a import convert_japanese_date_to_ymd
from pdf_facility_type import pdf_href_from_column_header_table
from pdf_processing import DEFAULT_HEADERS

CATEGORY_PAGE = {
    "新規・変更": "shisetsukijyun_jyuri_iryoukikan.html",
    "辞退": "shisetsukijyun_jitai_iryoukikan.html",
}

REIWA_KEISAI = re.compile(r"令和(\d+)年(\d+)月(\d+)日掲載")

CHECK_SCHEDULE_NOTE = (
    "【パターンC】掲載は毎月1日・15日頃。"
    "チェック推奨日: 2日・16日（土日祝・年始等の場合は翌営業日）"
)


def category_page_url(hub_url: str, category_name: str) -> str | None:
    suffix = CATEGORY_PAGE.get(category_name)
    if not suffix:
        return None
    base = hub_url.rstrip("/").rsplit("/", 1)[0] + "/"
    return urljoin(base, suffix)


def _date_from_table_section(table) -> str | None:
    for tag in table.find_all_previous(["p", "h2", "h3", "h4"]):
        text = tag.get_text()
        match = REIWA_KEISAI.search(text)
        if match:
            return convert_japanese_date_to_ymd(match.group(0).replace("掲載", ""))
        plain = re.search(r"令和(\d+)年(\d+)月(\d+)日", text)
        if plain and "掲載" in text:
            return convert_japanese_date_to_ymd(plain.group(0))
    return None


def get_latest_pdf_info(soup: BeautifulSoup, page_url: str, pdf_type: str = "医科") -> dict | None:
    """カテゴリページ先頭（最新掲載）の指定施設種別 PDF を返す。"""
    for table in soup.find_all("table"):
        href = pdf_href_from_column_header_table(table, page_url, pdf_type)
        if href:
            return {
                "link": href,
                "date": _date_from_table_section(table),
            }
    return None


def fetch_category_info_pattern_c(
    hub_url: str, category_name: str, pdf_type: str = "医科"
) -> dict | None:
    cat_url = category_page_url(hub_url, category_name)
    if not cat_url:
        print(f"エラー: パターンCで未対応のカテゴリです: {category_name}")
        return None
    try:
        print(f"  カテゴリページ: {cat_url}")
        response = requests.get(cat_url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        info = get_latest_pdf_info(soup, cat_url, pdf_type)
        if not info:
            print(f"「{category_name}」の {pdf_type} PDF が見つかりませんでした。")
        return info
    except requests.RequestException as e:
        print(f"エラー: 「{category_name}」ページ取得失敗: {e}")
        return None


def get_category_info_pattern_c(
    soup, category_name: str, page_url: str, pdf_type: str = "医科"
) -> dict | None:
    """hub ページの soup からカテゴリ URL を解決して取得（互換用）。"""
    _ = soup
    return fetch_category_info_pattern_c(page_url, category_name, pdf_type)
