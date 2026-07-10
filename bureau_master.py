"""
厚生局マスターデータ（47都道府県）。

地理順（北→南）で PREFECTURE_ENTRIES を並べます。
url が空の県はサイト構造の調査・URL確定が未完了です（enabled=False）。
"""

from __future__ import annotations

from dataclasses import dataclass

from pdf_facility_type import PDF_TYPES_BASIC, PDF_TYPES_WITH_HOME_NURSING

BASE = "https://kouseikyoku.mhlw.go.jp"

# パターンB: 施設種別ごとにセクション、都道府県が列、1セルに新規・変更/失効が縦に並ぶ（近畿）
KIJUN_B_KINKI = f"{BASE}/kinki/gyomu/gyomu/hoken_kikan/kijun_jurijoukyou.html"
# パターンC: 入口ページ → カテゴリ別ページ（北海道）
HUB_C_HOKKAIDO = f"{BASE}/hokkaido/iryo_shido/shisetsukijyun_iryoukikan.html"
# パターンD: 1ページに掲載日ごとの表があり、県別行がカテゴリでグループ化される構造（東北）
KIJUN_D_TOHOKU = f"{BASE}/tohoku/gyomu/gyomu/hoken_kikan/kijun_jurijoukyou.html"
# パターンE: カテゴリ×施設種別ごとに別ページ（四国）。実URLは pattern_e.py 側で解決するため、
# ここでは参考表示用の入口ページを url に入れておく。
HUB_E_SHIKOKU = f"{BASE}/shikoku/gyomu/gyomu/hoken_kikan/shitei/index_00013.html"
# パターンF: 1ページ内に施設種別ごとの表（都道府県が列）が並ぶ構造（東海北陸）
KIJUN_F_TOKAIHOKURIKU = f"{BASE}/tokaihokuriku/newpage_00843.html"
# パターンG: 都道府県ごとにセクション、カテゴリはセル内テキストに埋め込み（中国四国厚生局・中国地方）
# 旧 chugoku/ 配下のURLは廃止され、chugokushikoku/ に統合されている点に注意。
KIJUN_G_CHUGOKU = f"{BASE}/chugokushikoku/chousaka/kijunjuriichiran_shinkihenkou_shikkou_00001.html"

@dataclass(frozen=True)
class PrefectureEntry:
    prefecture: str
    bureau: str
    pattern: str  # "A" | "B" | "C" | "D" | "E" | "F" | "G"
    url: str
    region_slug: str
    pdf_types: tuple[str, ...] = PDF_TYPES_WITH_HOME_NURSING
    enabled: bool = True


def _kanto_juri(office: str) -> str:
    return f"{BASE}/kantoshinetsu/gyomu/bu_ka/{office}/kijun.html"


def _kyushu_juri(office: str) -> str:
    return f"{BASE}/kyushu/gyomu/gyomu/hoken_kikan/juri_{office}.html"


def _entries() -> list[PrefectureEntry]:
    rows: list[PrefectureEntry] = []

    def add(
        pref: str,
        bureau: str,
        pattern: str,
        url: str,
        slug: str,
        *,
        pdf_types: tuple[str, ...] = PDF_TYPES_WITH_HOME_NURSING,
        enabled: bool = True,
    ):
        rows.append(
            PrefectureEntry(
                prefecture=pref,
                bureau=bureau,
                pattern=pattern,
                url=url,
                region_slug=slug,
                pdf_types=pdf_types,
                enabled=enabled,
            )
        )

    # --- 北海道（パターンC: 入口 → カテゴリ別ページ・3種） ---
    add("北海道", "北海道厚生局", "C", HUB_C_HOKKAIDO, "hokkaido", pdf_types=PDF_TYPES_BASIC)

    # --- 東北（パターンD: 1ページ内でカテゴリ別に県ごとの行がグループ化） ---
    for pref in ("青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"):
        add(pref, "東北厚生局", "D", KIJUN_D_TOHOKU, "tohoku")

    # --- 関東信越（県・事務所別ページ） ---
    kanto_map = [
        ("茨城県", "ibaraki"),
        ("栃木県", "tochigi"),
        ("群馬県", "gunma"),
        ("埼玉県", "shido_kansa"),  # 指導監査課（埼玉県管轄）
        ("千葉県", "chiba"),
        ("東京都", "tokyo"),
        ("神奈川県", "kanagawa"),
        ("新潟県", "niigata"),
        ("山梨県", "yamanashi"),
        ("長野県", "nagano"),
    ]
    for pref, office in kanto_map:
        add(pref, "関東信越厚生局", "A", _kanto_juri(office), "kantoshinetsu")

    # --- 東海北陸（パターンF: 都道府県が列、掲載日×カテゴリが行） ---
    # 福井県はこのページの表に列が存在しなかった（要調査と思っていたが、
    # 実際の管轄は近畿厚生局のため東海北陸のページに無いのは正しい。近畿側で対応する）。
    for pref in ("岐阜県", "静岡県", "愛知県", "三重県", "富山県", "石川県"):
        add(pref, "東海北陸厚生局", "F", KIJUN_F_TOKAIHOKURIKU, "tokaihokuriku")

    # --- 近畿（パターンB: 施設種別ごとにセクション、都道府県が列。福井県も管轄はここ） ---
    for pref in ("福井県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"):
        add(pref, "近畿厚生局", "B", KIJUN_B_KINKI, "kinki")

    # --- 中国（パターンG: 都道府県ごとにセクション、カテゴリはセル内テキストに埋め込み） ---
    # 厚生局名は「中国四国厚生局」に統合されているが、地域(region_slug)は従来通り chugoku のまま区別する。
    for pref in ("鳥取県", "島根県", "岡山県", "広島県", "山口県"):
        add(pref, "中国四国厚生局", "G", KIJUN_G_CHUGOKU, "chugoku")

    # --- 四国（パターンE: カテゴリ×施設種別ごとに別ページ） ---
    for pref in ("徳島県", "香川県", "愛媛県", "高知県"):
        add(pref, "四国厚生局", "E", HUB_E_SHIKOKU, "shikoku")

    # --- 九州（事務所別ページ・パターンAと同一スクレイパ） ---
    kyushu_map = [
        ("福岡県", "fukuoka"),
        ("佐賀県", "saga"),
        ("長崎県", "nagasaki"),
        ("熊本県", "kumamoto"),
        ("大分県", "ooita"),
        ("宮崎県", "miyazaki"),
        ("鹿児島県", "kagoshima"),
        ("沖縄県", "okinawa"),
    ]
    for pref, office in kyushu_map:
        add(pref, "九州厚生局", "A", _kyushu_juri(office), "kyushu")

    return rows


PREFECTURE_ENTRIES: list[PrefectureEntry] = _entries()

PREFECTURE_NAMES: list[str] = [e.prefecture for e in PREFECTURE_ENTRIES]

ENTRY_BY_PREFECTURE: dict[str, PrefectureEntry] = {e.prefecture: e for e in PREFECTURE_ENTRIES}


def get_entry(prefecture: str) -> PrefectureEntry | None:
    return ENTRY_BY_PREFECTURE.get(prefecture)
