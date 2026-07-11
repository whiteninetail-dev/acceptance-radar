"""
厚生局チェックの設定 GUI。

複数プロファイル（施設×施設種別の組み合わせ）を管理できる。
都道府県選択 → マスターデータから bureau / pattern / url を反映し config.ini に保存。
タスクスケジューラへの登録・解除（任意）に対応。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from bureau_master import PREFECTURE_ENTRIES, get_entry
from config_loader import config_path, delete_target, load_targets, save_targets, sync_targets_from_master
from pdf_facility_type import PDF_TYPES_WITH_HOME_NURSING

PROJECT_DIR = Path(__file__).resolve().parent
TASK_NAME = "AcceptanceRadarCheck"
CATEGORIES = ("新規・変更", "辞退")


def register_scheduled_task(start_time: str = "09:00") -> tuple[bool, str]:
    # --batch: 無人実行中に応答されないダイアログが出て処理が固まるのを防ぐ
    python_cmd = f'cd /d "{PROJECT_DIR}" && uv run main.py --batch'
    tr = f'cmd /c "{python_cmd}"'
    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        tr,
        "/SC",
        "DAILY",
        "/ST",
        start_time,
        "/F",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="cp932", errors="replace")
    if result.returncode == 0:
        return True, f"タスク「{TASK_NAME}」を登録（上書き）しました。"
    return False, (result.stderr or result.stdout or "schtasks に失敗しました。").strip()


def unregister_scheduled_task() -> tuple[bool, str]:
    """登録済みの定期実行タスクを解除する。"""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="cp932", errors="replace")
    if result.returncode == 0:
        return True, f"タスク「{TASK_NAME}」の自動実行を解除しました。"
    return False, (result.stderr or result.stdout or "schtasks に失敗しました。").strip()


def scheduled_task_exists() -> bool:
    """定期実行タスクが既に登録されているかを返す（チェックボックスの初期状態に使用）。"""
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="cp932", errors="replace")
    return result.returncode == 0


class SetupApp(tk.Tk):
    def __init__(self, from_main: bool = False):
        super().__init__()
        self.from_main = from_main
        self.title("厚生局チェック 設定（複数プロファイル対応）")
        self.geometry("820x660")
        self.resizable(False, False)

        self.profiles: list[dict] = sync_targets_from_master(load_targets(), write_back=False)
        self.current_profile_name: str | None = None  # None = 新規追加モード

        if from_main:
            ttk.Label(
                self,
                text="設定を保存すると、チェック処理に戻って再開します。",
                foreground="#0066cc",
            ).pack(anchor="w", padx=12, pady=(12, 0))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        # --- 左: プロファイル一覧 ---
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 12))

        ttk.Label(left, text="プロファイル一覧").pack(anchor="w")
        self.profile_listbox = tk.Listbox(left, width=28, height=24, exportselection=False)
        self.profile_listbox.pack(fill="y", expand=True)
        self.profile_listbox.bind("<<ListboxSelect>>", self._on_select_profile)

        list_btns = ttk.Frame(left)
        list_btns.pack(fill="x", pady=(6, 0))
        ttk.Button(list_btns, text="新規追加", command=self._new_profile).pack(side="left")
        ttk.Button(list_btns, text="削除", command=self._delete_profile).pack(side="left", padx=(6, 0))

        # --- 右: 編集フォーム ---
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="プロファイル名（一意な名前。例: 〇〇病院_医科）").pack(anchor="w")
        self.profile_name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.profile_name_var).pack(fill="x", pady=4)

        ttk.Label(right, text="都道府県（北→南）").pack(anchor="w", pady=(8, 0))
        self.pref_var = tk.StringVar()
        names = [e.prefecture for e in PREFECTURE_ENTRIES]
        self.pref_combo = ttk.Combobox(right, textvariable=self.pref_var, values=names, state="readonly")
        self.pref_combo.pack(fill="x", pady=4)
        self.pref_combo.bind("<<ComboboxSelected>>", self._on_prefecture_change)

        info = ttk.LabelFrame(right, text="厚生局マスター（自動反映）")
        info.pack(fill="x", pady=8)
        self.bureau_label = ttk.Label(info, text="厚生局: -")
        self.bureau_label.pack(anchor="w", padx=8, pady=2)
        self.pattern_label = ttk.Label(info, text="パターン: -")
        self.pattern_label.pack(anchor="w", padx=8, pady=2)
        self.url_label = ttk.Label(info, text="URL: -", wraplength=460)
        self.url_label.pack(anchor="w", padx=8, pady=(2, 8))

        ttk.Label(right, text="検索キーワード（病院名など。カンマ区切りでAND指定可）").pack(anchor="w")
        self.keyword_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.keyword_var).pack(fill="x", pady=4)

        pdf_frame = ttk.LabelFrame(right, text="対象 PDF（施設種別）")
        pdf_frame.pack(fill="x", pady=8)
        self.pdf_type_var = tk.StringVar()
        self.pdf_type_combo = ttk.Combobox(
            pdf_frame,
            textvariable=self.pdf_type_var,
            values=list(PDF_TYPES_WITH_HOME_NURSING),
            state="readonly",
        )
        self.pdf_type_combo.pack(fill="x", padx=8, pady=6)
        self.pdf_type_combo.bind("<<ComboboxSelected>>", self._on_pdf_type_change)
        ttk.Label(
            pdf_frame,
            text="同じ施設を複数の施設種別で監視したい場合は、施設種別ごとに別プロファイルを作成してください。",
            font=("", 8),
            wraplength=460,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        cat_frame = ttk.LabelFrame(right, text="対象カテゴリ")
        cat_frame.pack(fill="x", pady=8)
        self.cat_vars: dict[str, tk.BooleanVar] = {}
        for cat in CATEGORIES:
            var = tk.BooleanVar(value=True)
            self.cat_vars[cat] = var
            ttk.Checkbutton(cat_frame, text=cat, variable=var).pack(anchor="w", padx=8)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill="x", pady=12)
        ttk.Button(btn_frame, text="このプロファイルを保存", command=self._save_current_profile).pack(
            side="left", padx=(0, 8)
        )

        task_frame = ttk.LabelFrame(right, text="定期自動実行（タスクスケジューラ・任意）")
        task_frame.pack(fill="x", pady=(4, 0))

        # 既にタスクが登録済みならチェックON、未登録ならOFFで開始する
        self.task_enabled_var = tk.BooleanVar(value=scheduled_task_exists())
        ttk.Checkbutton(
            task_frame,
            text="毎日この時刻に、全プロファイルを自動でチェックする",
            variable=self.task_enabled_var,
        ).pack(anchor="w", padx=8, pady=(6, 0))

        time_row = ttk.Frame(task_frame)
        time_row.pack(fill="x", padx=8, pady=6)
        ttk.Label(time_row, text="実行時刻:").pack(side="left")
        self.task_time_var = tk.StringVar(value="09:00")
        ttk.Entry(time_row, textvariable=self.task_time_var, width=8).pack(side="left", padx=(4, 8))
        ttk.Button(time_row, text="この自動実行の設定を適用", command=self._apply_task_setting).pack(side="left")

        ttk.Label(
            task_frame,
            text="チェックを外して「適用」を押すと、登録済みの自動実行を解除します（登録しない運用も可）。",
            font=("", 8),
            wraplength=460,
        ).pack(anchor="w", padx=8, pady=(0, 6))

        ttk.Button(
            right,
            text="設定を保存して戻る" if from_main else "閉じる",
            command=self._finish,
        ).pack(anchor="w", pady=(8, 0))

        self._refresh_listbox()
        if self.profiles:
            self.profile_listbox.selection_set(0)
            self._load_profile_into_form(self.profiles[0])
        else:
            self._new_profile()

    # --- プロファイル一覧の描画 ---
    def _refresh_listbox(self, select_name: str | None = None) -> None:
        self.profile_listbox.delete(0, "end")
        for p in self.profiles:
            self.profile_listbox.insert("end", p["profile"])
        if select_name:
            for idx, p in enumerate(self.profiles):
                if p["profile"] == select_name:
                    self.profile_listbox.selection_set(idx)
                    break

    def _on_select_profile(self, _event=None) -> None:
        sel = self.profile_listbox.curselection()
        if not sel:
            return
        self._load_profile_into_form(self.profiles[sel[0]])

    def _load_profile_into_form(self, target: dict) -> None:
        self.current_profile_name = target["profile"]
        self.profile_name_var.set(target["profile"])
        pref = target.get("prefecture", "")
        if pref:
            self.pref_combo.set(pref)
        self.keyword_var.set(", ".join(target.get("search_terms", [])))
        self.pdf_type_var.set(target.get("pdf_type", "医科"))
        selected_cats = set(target.get("target_categories", []))
        for cat, var in self.cat_vars.items():
            var.set((not selected_cats) or (cat in selected_cats))
        self._on_prefecture_change()

    def _new_profile(self) -> None:
        self.current_profile_name = None
        self.profile_listbox.selection_clear(0, "end")
        self.profile_name_var.set("")
        if PREFECTURE_ENTRIES:
            self.pref_combo.current(0)
        self.keyword_var.set("")
        for var in self.cat_vars.values():
            var.set(True)
        self._on_prefecture_change()

    def _on_prefecture_change(self, _event=None) -> None:
        entry = get_entry(self.pref_var.get())
        if not entry:
            return
        status = "" if entry.enabled else "（URL未設定・要追加）"
        self.bureau_label.config(text=f"厚生局: {entry.bureau}{status}")
        self.pattern_label.config(text=f"パターン: {entry.pattern}")
        url_show = entry.url if entry.url else "（未設定）"
        self.url_label.config(text=f"URL: {url_show}")

        types = list(entry.pdf_types)
        self.pdf_type_combo["values"] = types
        current = self.pdf_type_var.get()
        if current not in types:
            self.pdf_type_var.set(types[0] if types else "医科")

        self._suggest_profile_name_if_empty()

    def _on_pdf_type_change(self, _event=None) -> None:
        self._suggest_profile_name_if_empty()

    def _suggest_profile_name_if_empty(self) -> None:
        """新規追加モードで、まだ名前を手入力していない場合だけ自動提案する。"""
        if self.current_profile_name is not None:
            return
        if self.profile_name_var.get().strip():
            return
        pref = self.pref_var.get()
        pdf_type = self.pdf_type_var.get()
        if pref and pdf_type:
            self.profile_name_var.set(f"{pref}_{pdf_type}")

    def _delete_profile(self) -> None:
        sel = self.profile_listbox.curselection()
        if not sel:
            messagebox.showinfo("削除", "削除するプロファイルを選択してください。")
            return
        target = self.profiles[sel[0]]
        if not messagebox.askyesno("削除確認", f"プロファイル「{target['profile']}」を削除しますか？"):
            return
        delete_target(target["profile"])
        self.profiles = [p for p in self.profiles if p["profile"] != target["profile"]]
        self._refresh_listbox()
        if self.profiles:
            self.profile_listbox.selection_set(0)
            self._load_profile_into_form(self.profiles[0])
        else:
            self._new_profile()

    def _save_current_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showerror("エラー", "プロファイル名を入力してください。")
            return

        entry = get_entry(self.pref_var.get())
        if not entry:
            messagebox.showerror("エラー", "都道府県を選択してください。")
            return
        if not entry.enabled or not entry.url:
            messagebox.showerror(
                "エラー",
                f"{entry.prefecture} はマスターデータの URL が未設定です。\n"
                "bureau_master.py に URL を追加してから保存してください。",
            )
            return

        keyword = self.keyword_var.get().strip()
        if not keyword:
            messagebox.showerror("エラー", "検索キーワードを入力してください。")
            return
        selected_cats = [c for c, v in self.cat_vars.items() if v.get()]
        if not selected_cats:
            messagebox.showerror("エラー", "対象カテゴリを1つ以上選択してください。")
            return

        pdf_type = self.pdf_type_var.get().strip()
        if pdf_type not in entry.pdf_types:
            messagebox.showerror("エラー", f"{entry.prefecture} で選べる施設種別: {', '.join(entry.pdf_types)}")
            return

        # 名前を変更した場合は、旧プロファイルを削除してから新しい名前で保存し直す
        renaming_from = None
        if self.current_profile_name and self.current_profile_name != name:
            renaming_from = self.current_profile_name

        if any(p["profile"] == name for p in self.profiles) and self.current_profile_name != name:
            messagebox.showerror("エラー", f"プロファイル名「{name}」は既に使われています。")
            return

        if renaming_from:
            delete_target(renaming_from)
            self.profiles = [p for p in self.profiles if p["profile"] != renaming_from]

        new_target = {
            "profile": name,
            "prefecture": entry.prefecture,
            "bureau": entry.bureau,
            "pattern": entry.pattern,
            "url": entry.url,
            "search_terms": [k.strip() for k in keyword.split(",") if k.strip()],
            "target_categories": selected_cats,
            "pdf_type": pdf_type,
            "download_folder": "Downloaded_PDFs",
            "extracted_folder": "Extracted_Pages",
            "backup_folder": "",
        }

        self.profiles = [p for p in self.profiles if p["profile"] != name] + [new_target]
        save_targets(self.profiles)
        self.current_profile_name = name
        self._refresh_listbox(select_name=name)
        messagebox.showinfo("保存完了", f"プロファイル「{name}」を保存しました。\n{config_path()}")

    def _apply_task_setting(self) -> None:
        if self.task_enabled_var.get():
            # チェックON → 登録（既存があれば上書き）
            start_time = self.task_time_var.get().strip()
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", start_time):
                messagebox.showerror("エラー", "実行時刻は HH:MM（24時間表記）で入力してください。例: 09:00 / 21:30")
                return
            ok, msg = register_scheduled_task(start_time)
            if ok:
                messagebox.showinfo("自動実行の設定", f"{msg}\n実行時刻: 毎日 {start_time}")
            else:
                messagebox.showerror("自動実行の設定", msg)
        else:
            # チェックOFF → 解除。元々登録が無い場合は「解除済み」扱いにする
            if not scheduled_task_exists():
                messagebox.showinfo("自動実行の設定", "自動実行は登録されていません（登録しない運用のままです）。")
                return
            ok, msg = unregister_scheduled_task()
            if ok:
                messagebox.showinfo("自動実行の設定", msg)
            else:
                messagebox.showerror("自動実行の設定", msg)

    def _finish(self) -> None:
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="厚生局チェックの設定 GUI")
    parser.add_argument(
        "--from-main",
        action="store_true",
        help="main.py から起動された場合（保存後に自動で閉じて処理を再開）",
    )
    args = parser.parse_args()
    app = SetupApp(from_main=args.from_main)
    app.mainloop()


if __name__ == "__main__":
    main()
