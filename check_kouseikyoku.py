"""
厚生局ウェブサイト 更新チェック・PDF 抽出プログラム
設定は config.ini（または環境変数 AUTOMATION_CONFIG）の [kouseikyoku:プロファイル名] を参照します。
1つの config.ini に複数プロファイルを持たせて、1回の実行で順番にチェックできます。
"""

import os
from datetime import datetime

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
            success, result_text, _created_files = download_and_process_pdf(
                current_info,
                search_terms,
                category,
                download_folder,
                extracted_folder,
                backup_folder,
            )
            all_results_text.append(f"--- {category} ---\n{result_text}")
            if not success:
                # ダウンロード/抽出に失敗した場合は「未処理」のまま残し、
                # 次回実行時に同じ更新を再検知してリトライできるようにする。
                print(f"「{category}」の処理に失敗したため、今回のリンクは保存しません（次回リトライします）。")
                continue
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
    response = requests.get(page_url, headers=DEFAULT_HEADERS, timeout=30)
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


def _show_results_if_any(all_results_text: list[str], *, batch: bool = False) -> None:
    if not all_results_text or batch:
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
    if pattern in ("A", "B", "D", "F", "G"):
        # B・D・F・G も取得方法（1ページ取得してソースを渡す）が A と同じで、
        # ページ内の解析ロジックだけが異なる（get_category_info_for_pattern 側で分岐）。
        return run_process_pattern_a(target)
    if pattern in ("C", "E"):
        # E も取得方法（カテゴリごとに別URLを取りに行く）が C と同じ。
        return run_process_pattern_c(target)
    print(f"エラー: 未対応の pattern です: {pattern}（A / B / C / D / E / F / G を指定してください）")
    return ""


def _write_log(summary: list[tuple[str, str]], started_at: datetime) -> None:
    """実行結果を logs/update_history_YYYYMM.txt に追記する（監査・後追い確認用）。"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"update_history_{started_at.strftime('%Y%m')}.txt")
    lines = [f"[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] === 厚生局チェック実行 ==="]
    for profile, outcome in summary:
        lines.append(f"  ・{profile}: {outcome}")
    lines.append("")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def list_profile_names() -> list[str]:
    """設定ウィザードを起動せず、config.ini にあるプロファイル名だけを返す。"""
    return [t.get("profile", "?") for t in load_targets()]


def run_process(only_profile: str | None = None, *, batch: bool = False) -> bool:
    """厚生局サイトの更新チェック・PDF 取得・ページ抽出まで（メールは別プロジェクト）。
    config.ini 内の全プロファイルを順番にチェックする。1件のプロファイルで
    エラーが起きても、そこだけスキップして残りは続行する。
    only_profile を指定すると、そのプロファイルだけを実行する。
    batch=True の場合、設定不足時のダイアログや結果報告ポップアップを出さない
    （タスクスケジューラ等の無人実行向け）。"""
    targets = ensure_kouseikyoku_config(batch=batch)
    if not targets:
        return False

    if only_profile:
        matched = [t for t in targets if t.get("profile") == only_profile]
        if not matched:
            available = ", ".join(t.get("profile", "?") for t in targets)
            print(f"エラー: プロファイル「{only_profile}」が見つかりません。利用可能: {available}")
            return False
        targets = matched

    started_at = datetime.now()
    print("############################################")
    print(f"# 厚生局チェック開始: {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 対象プロファイル数: {len(targets)}件")
    print("############################################")

    all_results_text: list[str] = []
    any_success = False
    summary: list[tuple[str, str]] = []  # (profile, 結果概要)

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
                summary.append((profile, "更新あり（PDFダウンロード・抽出済み）"))
            else:
                summary.append((profile, "更新なし"))
        except requests.exceptions.RequestException as e:
            print(f"エラー: [{profile}] ページへのアクセスに失敗しました。 {e}")
            summary.append((profile, f"エラー（アクセス失敗: {e}）"))
        except Exception as e:
            print(f"エラー: [{profile}] 予期しないエラーが発生しました。 {e}")
            summary.append((profile, f"エラー（予期しない: {e}）"))

    print("\n############################################")
    print("# チェック結果サマリー")
    print("############################################")
    for profile, outcome in summary:
        print(f"  ・{profile}: {outcome}")
    print("############################################\n")

    _write_log(summary, started_at)
    _show_results_if_any(all_results_text, batch=batch)
    return any_success
