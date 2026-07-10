"""厚生局サイト構造パターン別の HTML 解析。"""

from kouseikyoku_patterns.pattern_a import get_category_info
from kouseikyoku_patterns.pattern_b import get_category_info_pattern_b
from kouseikyoku_patterns.pattern_c import fetch_category_info_pattern_c, get_category_info_pattern_c
from kouseikyoku_patterns.pattern_d import get_category_info_pattern_d
from kouseikyoku_patterns.pattern_e import fetch_category_info_pattern_e
from kouseikyoku_patterns.pattern_f import get_category_info_pattern_f
from kouseikyoku_patterns.pattern_g import get_category_info_pattern_g

__all__ = [
    "get_category_info",
    "get_category_info_for_pattern",
    "fetch_category_info_for_pattern",
]


def get_category_info_for_pattern(
    pattern: str,
    soup,
    category_name: str,
    page_url: str,
    pdf_type: str = "医科",
    prefecture: str = "",
):
    p = (pattern or "A").strip().upper()
    if p == "A":
        return get_category_info(soup, category_name, page_url, pdf_type)
    if p == "B":
        return get_category_info_pattern_b(
            soup, category_name, page_url, pdf_type, prefecture=prefecture
        )
    if p == "C":
        return get_category_info_pattern_c(soup, category_name, page_url, pdf_type)
    if p == "D":
        return get_category_info_pattern_d(
            soup, category_name, page_url, pdf_type, prefecture=prefecture
        )
    if p == "F":
        return get_category_info_pattern_f(
            soup, category_name, page_url, pdf_type, prefecture=prefecture
        )
    if p == "G":
        return get_category_info_pattern_g(
            soup, category_name, page_url, pdf_type, prefecture=prefecture
        )
    raise ValueError(f"未対応の pattern です: {pattern}")


def fetch_category_info_for_pattern(
    pattern: str,
    category_name: str,
    page_url: str,
    soup=None,
    pdf_type: str = "医科",
    prefecture: str = "",
):
    """カテゴリごとに別 URL へ取りに行くパターン（C・E 等）向け。"""
    p = (pattern or "A").strip().upper()
    if p == "C":
        return fetch_category_info_pattern_c(page_url, category_name, pdf_type)
    if p == "E":
        return fetch_category_info_pattern_e(page_url, category_name, pdf_type, prefecture=prefecture)
    return get_category_info_for_pattern(p, soup, category_name, page_url, pdf_type, prefecture)
