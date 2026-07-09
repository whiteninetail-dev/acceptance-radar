"""config.ini が無い・不完全なときに setup.py へ誘導し、保存後に処理を再開する。"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config_loader import config_path, load_targets, sync_targets_from_master, validate_targets

PROJECT_DIR = Path(__file__).resolve().parent
RESUME_TIMEOUT_MS = 10_000


def _ask_yes_no(title: str, message: str) -> bool:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    answer = messagebox.askyesno(title, message)
    root.destroy()
    return answer


def _show_info(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo(title, message)
    root.destroy()


def _confirm_resume_after_setup(targets: list[dict]) -> bool:
    """
    設定完了を通知し、チェック再開の確認を行う。
    応答がなければ RESUME_TIMEOUT_MS 後に自動で再開（はい）する。
    """
    root = tk.Tk()
    root.title("厚生局チェック — 設定完了")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    result = {"answer": True}
    seconds = RESUME_TIMEOUT_MS // 1000

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=f"設定ができました（{len(targets)}件のプロファイル）。", font=("", 11, "bold")).pack(
        anchor="w"
    )

    detail_lines = [f"保存先: {config_path()}"]
    for target in targets:
        detail_lines.append(
            f"・{target.get('profile', '?')}（{target.get('prefecture', '?')} / {target.get('pdf_type', '?')}）"
        )

    ttk.Label(frame, text="\n".join(detail_lines), justify="left").pack(anchor="w", pady=(8, 12))

    countdown_var = tk.StringVar(
        value=f"チェック処理を再開しますか？（{seconds}秒で自動的に再開します）"
    )
    ttk.Label(frame, textvariable=countdown_var, wraplength=360).pack(anchor="w", pady=(0, 12))

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(anchor="e")

    def finish(answer: bool) -> None:
        result["answer"] = answer
        if root.winfo_exists():
            root.destroy()

    yes_btn = ttk.Button(btn_frame, text="はい（再開）", command=lambda: finish(True))
    yes_btn.pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="いいえ", command=lambda: finish(False)).pack(side="left")

    remaining = {"sec": seconds}

    def tick() -> None:
        if not root.winfo_exists():
            return
        remaining["sec"] -= 1
        if remaining["sec"] <= 0:
            finish(True)
            return
        countdown_var.set(
            f"チェック処理を再開しますか？（{remaining['sec']}秒で自動的に再開します）"
        )
        root.after(1000, tick)

    root.after(1000, tick)
    root.after(RESUME_TIMEOUT_MS, lambda: finish(True))
    root.protocol("WM_DELETE_WINDOW", lambda: finish(False))
    yes_btn.focus_set()
    root.mainloop()
    return result["answer"]


def _run_setup_from_main() -> None:
    setup_script = PROJECT_DIR / "setup.py"
    subprocess.run(
        [sys.executable, str(setup_script), "--from-main"],
        cwd=PROJECT_DIR,
        check=False,
    )


def prompt_and_run_setup(reason: str) -> bool:
    """
    設定不足を通知し、setup.py 起動を確認する。
    保存後に設定が有効なら True。
    """
    msg = (
        "設定ファイルが利用できません。\n\n"
        f"{reason}\n\n"
        "設定画面（setup.py）を開いて作成しますか？"
    )
    if not _ask_yes_no("厚生局チェック — 設定が必要です", msg):
        _show_info("終了", "設定がないため処理を中断しました。")
        return False

    print("設定画面を開きます...")
    _run_setup_from_main()

    ok, err = validate_targets()
    if ok:
        return True

    _show_info(
        "設定未完成",
        "設定がまだ完了していません。\n\n"
        f"{err}\n\n"
        "次回、設定画面で「設定を保存」してから再度実行してください。",
    )
    return False


def ensure_kouseikyoku_config() -> list[dict] | None:
    """設定（全プロファイル）を読み込む。不足時は setup へ誘導し、保存後に再読み込みする。"""
    ok, err = validate_targets()
    if ok:
        return sync_targets_from_master(load_targets())

    print(f"エラー: {err}")
    if not prompt_and_run_setup(err):
        return None

    targets = sync_targets_from_master(load_targets())
    print(f"設定を読み込みました（{config_path()}）。{len(targets)}件のプロファイル。")

    if not _confirm_resume_after_setup(targets):
        print("チェック処理の再開をキャンセルしました。")
        return None

    print("チェック処理を再開します。")
    return targets
