"""config.ini（共有パス可）から複数の [kouseikyoku:プロファイル名] を読み込む。

旧形式（単一の [kouseikyoku] セクション）は自動的に1件のプロファイルとして
扱われ、次回保存時に新形式（[kouseikyoku:プロファイル名]）へ移行される。
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from bureau_master import get_entry

PROFILE_PREFIX = "kouseikyoku:"
LEGACY_SECTION = "kouseikyoku"

DEFAULT_DOWNLOAD_FOLDER = "Downloaded_PDFs"
DEFAULT_EXTRACTED_FOLDER = "Extracted_Pages"

CONFIG_HEADER_COMMENT = """\
; 【厚生局チェック 設定ファイル】
; このファイルは setup.py（GUI）から自動生成されます。手動で編集することもできます。
;
; [kouseikyoku:プロファイル名] の形式で、施設×施設種別の組み合わせを何件でも登録できます。
; プロファイル名は自由に付けられます（例: 〇〇病院_医科）。
;
; 各プロファイルの項目:
;   prefecture       = 都道府県名（例: 埼玉県）
;   bureau            = 厚生局名（prefecture から自動反映。通常は編集不要）
;   pattern           = サイト構造パターン（同上、自動反映）
;   url               = 対象厚生局ページ（同上、自動反映）
;   pdf_type          = 医科 / 歯科 / 薬局 / 訪問看護
;   target_categories = 新規・変更, 辞退（カンマ区切りで複数指定可）
;   search_terms      = 検索キーワード（施設名など。カンマ区切りでAND指定）
;   download_folder   = ダウンロード先フォルダ（通常は変更不要）
;   extracted_folder  = 抽出PDF保存先フォルダ（通常は変更不要）
;   backup_folder     = バックアップ先フォルダ（任意）
;
; 共有パスを使う場合は環境変数 AUTOMATION_CONFIG にこのファイルのフルパスを設定してください。
; 作り直す場合は、このファイルを削除して setup.py（または main.py）を起動し直すのが簡単です。

"""


def config_path() -> Path:
    env = os.environ.get("AUTOMATION_CONFIG", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent / "config.ini"


def _read_config() -> configparser.ConfigParser:
    path = config_path()
    if not path.is_file():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    return cp


def _split_csv(sec: configparser.SectionProxy, key: str) -> list[str]:
    raw = sec.get(key, fallback="").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_target(profile: str, sec: configparser.SectionProxy) -> dict:
    pattern_raw = sec.get("pattern", fallback="A").strip().upper() or "A"
    return {
        "profile": profile,
        "prefecture": sec.get("prefecture", fallback="").strip(),
        "bureau": sec.get("bureau", fallback="").strip(),
        "pattern": pattern_raw,
        "url": sec.get("url", fallback="").strip(),
        "target_categories": _split_csv(sec, "target_categories"),
        "search_terms": _split_csv(sec, "search_terms"),
        "download_folder": sec.get("download_folder", fallback=DEFAULT_DOWNLOAD_FOLDER).strip()
        or DEFAULT_DOWNLOAD_FOLDER,
        "extracted_folder": sec.get("extracted_folder", fallback=DEFAULT_EXTRACTED_FOLDER).strip()
        or DEFAULT_EXTRACTED_FOLDER,
        "backup_folder": sec.get("backup_folder", fallback="").strip(),
        "pdf_type": sec.get("pdf_type", fallback="医科").strip() or "医科",
    }


def _legacy_profile_name(sec: configparser.SectionProxy) -> str:
    prefecture = sec.get("prefecture", fallback="").strip()
    pdf_type = sec.get("pdf_type", fallback="医科").strip() or "医科"
    return f"{prefecture}_{pdf_type}" if prefecture else "既存設定"


def load_targets() -> list[dict]:
    """config.ini 内の全プロファイルを読み込む。ファイルが無ければ空リストを返す
    （setup.py を初回起動する場合など、まだ config.ini が存在しないケースがあるため）。"""
    try:
        cp = _read_config()
    except FileNotFoundError:
        return []
    targets: list[dict] = []

    for section in cp.sections():
        if section.startswith(PROFILE_PREFIX):
            name = section[len(PROFILE_PREFIX):].strip() or section
            targets.append(_parse_target(name, cp[section]))

    if not targets and LEGACY_SECTION in cp:
        sec = cp[LEGACY_SECTION]
        targets.append(_parse_target(_legacy_profile_name(sec), sec))

    return targets


def save_targets(targets: list[dict]) -> None:
    """指定したプロファイル一覧を新形式（[kouseikyoku:名前]）で書き出す。

    渡されなかった既存プロファイルはそのまま残す。旧形式の [kouseikyoku] は
    新形式へ統合済みとして削除する。
    """
    path = config_path()
    cp = configparser.ConfigParser()
    if path.is_file():
        cp.read(path, encoding="utf-8")

    if LEGACY_SECTION in cp:
        cp.remove_section(LEGACY_SECTION)

    for target in targets:
        section = f"{PROFILE_PREFIX}{target['profile']}"
        if not cp.has_section(section):
            cp.add_section(section)
        sec = cp[section]
        sec["prefecture"] = target.get("prefecture", "")
        sec["bureau"] = target.get("bureau", "")
        sec["pattern"] = target.get("pattern", "")
        sec["url"] = target.get("url", "")
        sec["search_terms"] = ", ".join(target.get("search_terms", []))
        sec["target_categories"] = ", ".join(target.get("target_categories", []))
        sec["pdf_type"] = target.get("pdf_type", "医科")
        sec.setdefault("download_folder", DEFAULT_DOWNLOAD_FOLDER)
        sec.setdefault("extracted_folder", DEFAULT_EXTRACTED_FOLDER)
        sec.setdefault("backup_folder", "")

    with open(path, "w", encoding="utf-8") as f:
        f.write(CONFIG_HEADER_COMMENT)
        cp.write(f)


def delete_target(profile: str) -> None:
    path = config_path()
    if not path.is_file():
        return
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    section = f"{PROFILE_PREFIX}{profile}"
    if cp.has_section(section):
        cp.remove_section(section)
        with open(path, "w", encoding="utf-8") as f:
            f.write(CONFIG_HEADER_COMMENT)
            cp.write(f)


def sync_targets_from_master(targets: list[dict], *, write_back: bool = True) -> list[dict]:
    """各プロファイルの prefecture から、マスターデータの url/bureau/pattern に揃える。"""
    updated: list[dict] = []
    changed = False
    for target in targets:
        prefecture = target.get("prefecture", "")
        if not prefecture:
            updated.append(target)
            continue
        entry = get_entry(prefecture)
        if not entry or not entry.enabled or not entry.url:
            updated.append(target)
            continue
        new_target = dict(target)
        for key, master_val in (("url", entry.url), ("bureau", entry.bureau), ("pattern", entry.pattern)):
            if new_target.get(key) != master_val:
                new_target[key] = master_val
                changed = True
        updated.append(new_target)

    if changed and write_back:
        print("【設定補正】プロファイルの一部をマスターデータに合わせて更新しました。")
        save_targets(updated)

    return updated


def validate_targets() -> tuple[bool, str]:
    """設定がチェック実行可能か検証する。"""
    targets = load_targets()

    if not targets:
        return False, f"有効なプロファイルが1件もありません（設定ファイルが無いか空です）: {config_path()}"

    for target in targets:
        profile = target.get("profile", "?")
        if not target.get("prefecture"):
            return False, f"[{profile}] prefecture（都道府県）が未設定です。"
        if not target.get("url"):
            return False, f"[{profile}] url が未設定です。"
        if not target.get("search_terms"):
            return False, f"[{profile}] search_terms が未設定です。"
        if not target.get("target_categories"):
            return False, f"[{profile}] target_categories が未設定です。"
        if not target.get("pdf_type"):
            return False, f"[{profile}] pdf_type が未設定です。"
    return True, ""
