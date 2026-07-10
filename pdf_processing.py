"""PDF ダウンロードとキーワード該当ページの抽出（厚生局共通）。"""

from __future__ import annotations

import io
import os
import shutil

import pdfplumber
import requests
from pypdf import PdfReader, PdfWriter

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
}


def download_and_process_pdf(
    pdf_info,
    search_terms,
    category_name,
    download_folder,
    extracted_folder,
    backup_folder,
):
    """PDFをダウンロードして該当ページを抽出する。
    戻り値は (success, message, created_files)。success が False の場合、
    呼び出し側は「更新チェック済み」の記録を書き換えず、次回リトライできるようにする。"""
    pdf_url = pdf_info["link"]
    publication_date = pdf_info["date"] if pdf_info["date"] else "NODATE"
    created_files = []
    try:
        print(f"PDFをダウンロードしています: {pdf_url}")
        response = requests.get(pdf_url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        pdf_content = response.content
        os.makedirs(download_folder, exist_ok=True)
        pdf_filename = os.path.basename(pdf_url)
        new_full_filename = f"{category_name}_{publication_date}_{pdf_filename}"
        full_pdf_path = os.path.join(download_folder, new_full_filename)
        with open(full_pdf_path, "wb") as f:
            f.write(pdf_content)
        message = f"【ダウンロード完了】\nフルPDFを「{full_pdf_path}」に保存しました。\n"
        created_files.append(full_pdf_path)
        if backup_folder and os.path.isdir(backup_folder):
            shutil.copy2(full_pdf_path, backup_folder)
            message += f"→ バックアップを「{backup_folder}」に作成しました。\n\n"
        else:
            message += "\n"
        found_pages = []
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            initial_found_pages = []
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                page_found = False
                for table in tables:
                    for row in table:
                        row_text = "".join(cell if cell is not None else "" for cell in row)
                        cleaned_row_text = (
                            row_text.replace("\n", "").replace(" ", "").replace("　", "")
                        )
                        cleaned_search_terms = [
                            term.replace(" ", "").replace("　", "") for term in search_terms
                        ]
                        if all(term in cleaned_row_text for term in cleaned_search_terms):
                            initial_found_pages.append(i)
                            page_found = True
                            break
                    if page_found:
                        break
            if initial_found_pages:
                all_target_pages = set(initial_found_pages)
                last_checked_page = max(initial_found_pages)
                for i in range(last_checked_page + 1, len(pdf.pages)):
                    page = pdf.pages[i]
                    tables = page.extract_tables()
                    if tables and tables[0] and len(tables[0]) > 1:
                        first_data_row = tables[0][1]
                        if (
                            len(first_data_row) > 1
                            and (first_data_row[1] is None or first_data_row[1].strip() == "")
                            and (first_data_row[0] is None or first_data_row[0].strip() == "")
                        ):
                            all_target_pages.add(i)
                        else:
                            break
                    else:
                        break
                found_pages = sorted(list(all_target_pages))
        if found_pages:
            hospital_name_str = "_".join(search_terms)
            os.makedirs(extracted_folder, exist_ok=True)
            new_extracted_filename = (
                f"{category_name}_{publication_date}_抜粋_{hospital_name_str}_{pdf_filename}"
            )
            extracted_pdf_path = os.path.join(extracted_folder, new_extracted_filename)
            pdf_reader = PdfReader(io.BytesIO(pdf_content))
            pdf_writer = PdfWriter()
            for page_num in found_pages:
                pdf_writer.add_page(pdf_reader.pages[page_num])
            with open(extracted_pdf_path, "wb") as f:
                pdf_writer.write(f)
            message += f"【ページ抽出完了】\n該当ページを「{extracted_pdf_path}」に保存しました。\n"
            created_files.append(extracted_pdf_path)
            if backup_folder and os.path.isdir(backup_folder):
                shutil.copy2(extracted_pdf_path, backup_folder)
                message += f"→ バックアップを「{backup_folder}」に作成しました。"
        else:
            message += (
                f"【見つかりませんでした】\nPDF内に「{'_'.join(search_terms)}」の記載はありませんでした。"
            )
        return True, message, created_files
    except Exception as e:
        error_message = f"エラー: PDFの処理中に問題が発生しました。\n{e}"
        print(error_message)
        return False, error_message, []
