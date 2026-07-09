"""
厚生局ウェブサイト 更新チェック・PDF 抽出プログラム
設定は config.ini（または環境変数 AUTOMATION_CONFIG）の [kouseikyoku:プロファイル名] を参照します。
1つの config.ini に複数プロファイルを持たせて、1回の実行で順番にチェックできます。
"""

import os

import requests
import tkinter as tk
from bs4 import BeautifulSoup
from tkinter import messagebox

from config_loader import load_targets
from config_setup_flow import ensure_kouseikyoku_config
from kouseikyoku_patterns import fetch_category_info_for_pattern, get_category_info_for_pattern
from kouseikyoku_patterns.pattern_c import CHECK_SCHEDULE_NOTE
from pdf_processing import DEFAULT_HEADERS, download_and_process_pdf


def run_check_loop(cfg: dict, soup: BeautifulSoup | None, page_url: str) -> list[str]:
    """カテゴリごとの更新チェック・PDF 処理。pattern に応じた HTML 解析を使用。
    出力先（ダウンロード/抜粋/更新チェック記録）はプロファイル名で分けて、
    他のプロファイルと混ざらないようにする。"""
    pattern = cfg.get("pattern", "A")
    pdf_type = cfg.get("pdf_type", "医科")
    prefecture = cfg.get("prefecture", "")
    profile = cfg.get("profile", "default")
    per_category_fetch = pattern.upper() in ("C", "E")
    target_categories = cfg["target_categories"]
    search_terms = cfg["search_terms"]
    download_folder = os.path.join(cfg["download_folder"], profile)
    extracted_folder = os.path.join(cfg["extracted_folder"], profile)
    backup_folder_base = cfg["backup_folder"]
    backup_folder = os.path.join(backup_folder_base, profile) if backup_folder_base else ""

    all_results_text = []
    state_folder = os.path.join("state", profile)
    for category in target_categories:
        print(f"\n--- カテゴリ「{category}」のチェックを開始（{pdf_type}） ---")
        if per_category_fetch:
            current_info = fetch_category_info_for_pattern(
                pattern, category, page_url, pdf_type=pdf_type, prefecture=prefecture
            )
        else:
            current_info = get_category_info_for_pattern(
                pattern, soup, category, page_url, pdf_type=pdf_type, prefecture=prefecture
            )
        if not current_info:
            print(f"「{category}」のPDF情報が見つかりませんでした。")
            continue
        current_link = current_info["link"]
        os.makedirs(state_folder, exist_ok=True)
        previous_link_file = os.path.join(state_folder, f"{category}.txt")
        previous_link = ""
        if os.path.exists(previous_link_file):
            with open(previous_link_file, encoding="utf-8") as f:
                previous_link = f.read().strip()
        if current_link != previous_link:
            print(f"【結果】★★ 更新がありました！ ★★ ({category})")
            result_text, _created_files = download_and_process_pdf(
                current_info,
                search_terms,
                category,
                download_folder,
                extracted_folder,
                backup_folder,
            )
            all_results_text.append(f"--- {category} ---\n{result_text}")
        else:
            print(f"【結果】更新はありませんでした。 ({category})")
        with open(previous_link_file, "w", encoding="utf-8") as f:
            f.write(current_link)
        print(f"今回のリンクを「{previous_link_file}」に保存しました。")
    return all_results_text


def run_process_pattern_a(cfg: dict) -> str:
    page_url = cfg["url"]
    pattern_label = cfg.get("pattern", "A").upper()
    print(f"[パターン{pattern_label}] ページにアクセスしています: {page_url}")
    response = requests.get(page_url, headers=DEFAULT_HEADERS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    all_results_text = run_check_loop(cfg, soup, page_url)
    return "\n\n".join(all_results_text)


def run_process_pattern_c(cfg: dict) -> str:
    pattern_label = cfg.get("pattern", "C").upper()
    page_url = cfg["url"]
    print(f"[パターン{pattern_label}] 入口ページ: {page_url}")
    if pattern_label == "C":
        print(CHECK_SCHEDULE_NOTE)
    all_results_text = run_check_loop(cfg, None, page_url)
    return "\n\n".join(all_results_text)


def _show_results_if_any(all_results_text: list[str]) -> None:
    if not all_results_text:
        return
    final_message = "\n\n".join(all_results_text)
    root = tk.Tk()
    root.withdraw()
    root.after(60000, root.destroy)
    try:
        messagebox.showinfo("厚生局チェック 結果報告", final_message)
        root.destroy()
    except tk.TclError:
        pass


def _run_one_target(target: dict) -> str:
    """1プロファイル分の処理を実行し、結果テキスト（更新が無ければ空文字）を返す。"""
    pattern = target.get("pattern", "A").upper()
    if pattern in ("A", "D", "F", "G", "H"):
        # D・F・G・H も取得方法（1ページ取得してソースを渡す）が A と同じで、
        # ページ内の解析ロジックだけが異なる（get_category_info_for_pattern 側で分岐）。
        return run_process_pattern_a(target)
    if pattern in ("C", "E"):
        # E も取得方法（カテゴリごとに別URLを取りに行く）が C と同じ。
        return run_process_pattern_c(target)
    print(f"エラー: 未対応の pattern です: {pattern}（A / C / D / E / F / G / H を指定してください）")
    return ""


def list_profile_names() -> list[str]:
    """設定ウィザードを起動せず、config.ini にあるプロファイル名だけを返す。"""
    try:
        return [t.get("profile", "?") for t in load_targets()]
    except FileNotFoundError:
        return []


def run_process(only_profile: str | None = None) -> bool:
    """厚生局サイトの更新チェック・PDF 取得・ページ抽出まで（メールは別プロジェクト）。
    config.ini 内の全プロファイルを順番にチェックする。1件のプロファイルで
    エラーが起きても、そこだけスキップして残りは続行する。
    only_profile を指定すると、そのプロファイルだけを実行する。"""
    targets = ensure_kouseikyoku_config()
    if not targets:
        return False

    if only_profile:
        matched = [t for t in targets if t.get("profile") == only_profile]
        if not matched:
            available = ", ".join(t.get("profile", "?") for t in targets)
            print(f"エラー: プロファイル「{only_profile}」が見つかりません。利用可能: {available}")
            return False
        targets = matched

    all_results_text: list[str] = []
    any_success = False

    for target in targets:
        profile = target.get("profile", "?")
        prefecture = target.get("prefecture", "")
        bureau = target.get("bureau", "")
        pattern = target.get("pattern", "A").upper()

        print(f"\n======== プロファイル「{profile}」 ========")
        if prefecture:
            print(
                f"対象: {prefecture} / 厚生局: {bureau} / パターン: {pattern} "
                f"/ 施設種別: {target.get('pdf_type', '医科')}"
            )
        elif bureau:
            print(f"厚生局: {bureau} / パターン: {pattern}")

        try:
            result_text = _run_one_target(target)
            any_success = True
            if result_text:
                all_results_text.append(f"■ {profile}\n{result_text}")
        except requests.exceptions.RequestException as e:
            print(f"エラー: [{profile}] ページへのアクセスに失敗しました。 {e}")
        except Exception as e:
            print(f"エラー: [{profile}] 予期しないエラーが発生しました。 {e}")

    _show_results_if_any(all_results_text)
    return any_success
