import os
import pdfplumber
import csv
from datetime import datetime

# --- ▼▼▼ 設定項目 ▼▼▼ ---

# 読み込むPDFファイルが保存されているフォルダ
EXTRACTED_FOLDER = "Extracted_Pages"

# CSVファイルの保存先フォルダ
CSV_OUTPUT_FOLDER = "CSV_Output"

# --- ▲▲▲ 設定はここまで ▲▲▲ ---

def find_latest_file(folder_path):
    """指定されたフォルダの中から、最も新しく更新されたファイルを探して返す"""
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.pdf')]
    if not files:
        return None
    # ファイルの更新日時が最も新しいものを返す
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def clean_cell_text(text):
    """セルのテキストから不要な改行を取り除き、整形する"""
    if text is None:
        return ""
    # 改行を半角スペースに置き換えて、前後の余白を削除
    return text.replace('\n', ' ').strip()

def main():
    """メインの処理"""
    print(f"--- PDFからCSVへの変換処理を開始します ---")

    # 1. 処理対象の最新PDFファイルを探す
    latest_pdf_path = find_latest_file(EXTRACTED_FOLDER)

    if not latest_pdf_path:
        print(f"エラー: 「{EXTRACTED_FOLDER}」フォルダに処理対象のPDFファイルが見つかりません。")
        return

    print(f"処理対象ファイル: {latest_pdf_path}")

    # 2. PDFからテーブルデータを抽出
    all_table_data = []
    with pdfplumber.open(latest_pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"{i+1}ページ目を読み込んでいます...")
            # ページから全てのテーブルを抽出
            tables = page.extract_tables()
            for table in tables:
                # テーブルの各行をループ
                for row in table:
                    # 各セルのテキストをお掃除して、新しい行として追加
                    cleaned_row = [clean_cell_text(cell) for cell in row]
                    all_table_data.append(cleaned_row)
    
    if not all_table_data:
        print("エラー: PDFからテーブルデータを抽出できませんでした。")
        return
        
    print("テーブルの抽出が完了しました。")

    # 3. 抽出したデータをCSVファイルに書き出す
    os.makedirs(CSV_OUTPUT_FOLDER, exist_ok=True) # 保存先フォルダがなければ作成
    
    # 日付をファイル名に含めて、いつのデータかわかるようにする
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv_path = os.path.join(CSV_OUTPUT_FOLDER, f"output_{timestamp}.csv")

    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(all_table_data)
        
        print(f"【成功】CSVファイルを「{output_csv_path}」に保存しました。")

    except Exception as e:
        print(f"エラー: CSVファイルの書き込み中に問題が発生しました。 {e}")

    print("--- 処理を終了します ---")


if __name__ == "__main__":
    main()