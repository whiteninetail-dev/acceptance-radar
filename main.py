import argparse
import sys

from check_kouseikyoku import list_profile_names, run_process


def _pick_profile_interactively() -> str | None:
    names = list_profile_names()
    if not names:
        print("エラー: プロファイルが1件もありません。setup.py で作成してください。")
        return None
    print("\n実行するプロファイルを選んでください。")
    for i, name in enumerate(names, start=1):
        print(f"  {i}: {name}")
    print("  0: 全プロファイルをまとめて実行")
    choice = input("番号を入力: ").strip()
    if choice == "0":
        return ""  # 全件実行の合図（呼び出し側で None として扱う）
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        return names[int(choice) - 1]
    print("エラー: 無効な番号です。")
    return None


def main():
    parser = argparse.ArgumentParser(description="厚生局チェックツール")
    parser.add_argument(
        "--profile",
        "-p",
        metavar="NAME",
        help="指定したプロファイル名だけを実行する（省略時は全プロファイルを実行）",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="登録されているプロファイル名の一覧を表示して終了する",
    )
    parser.add_argument(
        "--pick",
        "-i",
        action="store_true",
        help="対話形式でプロファイルを選んで実行する",
    )
    args = parser.parse_args()

    if args.list:
        for name in list_profile_names():
            print(name)
        return

    only_profile = args.profile
    if args.pick:
        picked = _pick_profile_interactively()
        if picked is None:
            sys.exit(1)
        only_profile = picked or None

    if not run_process(only_profile=only_profile):
        sys.exit(1)


if __name__ == "__main__":
    main()
