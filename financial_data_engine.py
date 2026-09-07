import re
import time
import numbers
import unicodedata
from datetime import date
from functools import lru_cache

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kap.org.tr"
MEMBER_FILTER_URL = BASE_URL + "/tr/api/member/filter/{ticker}"
DISCLOSURE_QUERY_URL = BASE_URL + "/tr/api/disclosure/members/byCriteria"
DISCLOSURE_DETAIL_URL = BASE_URL + "/tr/api/notification/attachment-detail/{disclosure_index}"
DISCLOSURE_PAGE_URL = BASE_URL + "/tr/Bildirim/{disclosure_index}"
WARMUP_URL = BASE_URL + "/tr/bildirim-sorgu"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": WARMUP_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
_WARMED_UP = False


def kap_warmup():
    global _WARMED_UP
    if _WARMED_UP:
        return
    try:
        SESSION.get(WARMUP_URL, timeout=20)
    except Exception:
        pass
    _WARMED_UP = True


def http_get(url, timeout=30, retries=3, referer=None):
    kap_warmup()
    last_error = None
    headers = {"Referer": referer} if referer else {}
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            return r
        except Exception as e:
            last_error = e
            time.sleep(0.7 * (attempt + 1))
    raise last_error


def http_post_json(url, payload, timeout=40, retries=3):
    kap_warmup()
    last_error = None
    for attempt in range(retries):
        try:
            r = SESSION.post(
                url,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json", "Referer": WARMUP_URL},
            )
            r.raise_for_status()
            return r
        except Exception as e:
            last_error = e
            time.sleep(0.7 * (attempt + 1))
    raise last_error


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    translation = str.maketrans({
        "İ": "I", "ı": "i", "Ş": "S", "ş": "s", "Ğ": "G", "ğ": "g",
        "Ü": "U", "ü": "u", "Ö": "O", "ö": "o", "Ç": "C", "ç": "c",
    })
    text = text.translate(translation)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, numbers.Number):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in {"-", "A/D", "N/A", "NAN"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace("\xa0", "").replace(" ", "").replace("TL", "").replace("TRY", "").replace("%", "")
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        number = float(text)
        return -number if negative else number
    except Exception:
        return None


@lru_cache(maxsize=512)
def kap_company_meta(ticker):
    ticker = ticker.upper().strip()
    r = http_get(MEMBER_FILTER_URL.format(ticker=ticker))
    data = r.json()
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{ticker} KAP şirket kaydı bulunamadı.")
        selected = next((x for x in data if ticker in str(x).upper()), data[0])
        data = selected
    if not isinstance(data, dict):
        raise ValueError(f"{ticker} şirket meta verisi okunamadı.")
    oid = data.get("mkkMemberOid") or data.get("kapMemberOid")
    if not oid:
        raise ValueError(f"{ticker} KAP OID bulunamadı.")
    return {
        "ticker": ticker,
        "oid": oid,
        "title": data.get("title") or data.get("kapMemberTitle") or ticker,
        "company_code": data.get("companyCode"),
        "permalink": data.get("permaLink"),
    }


@lru_cache(maxsize=1024)
def kap_reports_for_year(ticker, year):
    ticker = ticker.upper().strip()
    year = int(year)
    meta = kap_company_meta(ticker)
    payload = {
        "fromDate": f"{year}-01-01",
        "toDate": f"{year}-12-31",
        "memberType": "IGS",
        "mkkMemberOidList": [meta["oid"]],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": "FR",
        "subjectList": [],
        "isLate": "",
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "marketOid": "",
        "index": "",
        "bdkReview": "",
        "bdkMemberOidList": [],
        "year": "",
        "term": "",
        "ruleType": "",
        "period": "",
        "fromSrc": False,
        "srcCategory": "",
        "disclosureIndexList": [],
    }
    data = http_post_json(DISCLOSURE_QUERY_URL, payload).json()
    if not isinstance(data, list):
        raise ValueError(f"{ticker} {year} KAP rapor listesi okunamadı.")
    return data


def is_real_financial_report(item):
    if not isinstance(item, dict):
        return False
    return (
        str(item.get("disclosureClass") or "").upper() == "FR"
        and normalize_text(item.get("subject")) == "finansal rapor"
    )


def normalize_rule_type(value):
    text = normalize_text(value)
    if "3 aylik" in text:
        return "3 Aylık"
    if "6 aylik" in text:
        return "6 Aylık"
    if "9 aylik" in text:
        return "9 Aylık"
    if "yillik" in text or "12 aylik" in text:
        return "Yıllık"
    return str(value or "").strip()


PERIOD_PRIORITY = {"3 Aylık": 1, "6 Aylık": 2, "9 Aylık": 3, "Yıllık": 4}


def select_current_and_previous_report(ticker):
    """Cari raporu bul; yoksa en fazla 3 yil geriye giderek stale fallback kullan.

    Stale rapor skorlamada ayrica guvenlik kapisina tabidir. Buradaki amac
    analizi tamamen cokertmeden en son bilinen finansali gosterebilmektir.
    """
    ticker = ticker.upper().strip()
    today_year = date.today().year

    def _valid_reports(year):
        raw = kap_reports_for_year(ticker, year)
        out = []
        for item in raw:
            if not is_real_financial_report(item):
                continue
            try:
                report_year = int(item.get("year"))
            except Exception:
                continue
            if report_year != year:
                continue
            rule = normalize_rule_type(item.get("ruleType"))
            if rule not in PERIOD_PRIORITY:
                continue
            out.append({**item, "_year": report_year, "_rule_type": rule})
        out.sort(
            key=lambda x: (PERIOD_PRIORITY.get(x["_rule_type"], 0), int(x.get("disclosureIndex") or 0)),
            reverse=True,
        )
        return out

    current_report = None
    for year in range(today_year, today_year - 4, -1):
        reports = _valid_reports(year)
        if reports:
            current_report = reports[0]
            if year != today_year:
                current_report = {**current_report, "_stale_fallback": True}
            break
    if current_report is None:
        raise ValueError(f"{ticker} icin kullanilabilir finansal rapor bulunamadi.")

    target_rule = current_report["_rule_type"]
    previous_target_year = int(current_report["_year"]) - 1
    previous_candidates = [
        x for x in _valid_reports(previous_target_year)
        if x["_rule_type"] == target_rule
    ]
    previous_report = previous_candidates[0] if previous_candidates else None
    return current_report, previous_report


@lru_cache(maxsize=2048)
def kap_disclosure_detail(disclosure_index):
    disclosure_index = int(disclosure_index)
    url = DISCLOSURE_DETAIL_URL.format(disclosure_index=disclosure_index)
    referer = DISCLOSURE_PAGE_URL.format(disclosure_index=disclosure_index)
    data = http_get(url, referer=referer).json()
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{disclosure_index} KAP detayı boş.")
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError(f"{disclosure_index} KAP detayı okunamadı.")
    return data


def disclosure_body_html(disclosure_index):
    detail = kap_disclosure_detail(disclosure_index)
    bodies = detail.get("disclosureBody") or []
    if isinstance(bodies, str):
        bodies = [bodies]
    html = "\n".join(str(x) for x in bodies if x)
    if not html.strip():
        raise ValueError(f"{disclosure_index} finansal tablo HTML boş.")
    return html


def detect_scale(html):
    """KAP finansal tablolarındaki sunum para birimi çarpanını algılar.

    KAP aynı bilgiyi farklı şirket/şablonlarda ``1.000 TL``, ``1000TL``,
    ``1.000.000 TL``, ``1000000TL`` veya ``Milyon TL`` biçiminde
    gösterebiliyor. Büyük çarpanı önce kontrol etmek gerekir; aksi halde
    ``1.000.000 TL`` ifadesi yanlışlıkla 1.000 TL gibi yorumlanabilir.
    """
    text = normalize_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    compact = re.sub(r"\s+", "", text)

    if (
        "1.000.000tl" in compact
        or "1000000tl" in compact
        or "milyontl" in compact
        or "1milyontl" in compact
    ):
        return 1_000_000

    if (
        "1.000tl" in compact
        or "1000tl" in compact
        or "bintl" in compact
    ):
        return 1000

    return 1


def html_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        cells = [x for x in cells if x]
        if cells:
            rows.append(cells)
    return rows


def parse_financial_number(value):
    """KAP finansal tablo hücresindeki parasal sayıyı ayrıştırır.

    Genel ``parse_number`` fonksiyonundan bilinçli olarak ayrıdır. KAP
    finansal tablolarında nokta çoğunlukla binlik ayırıcıdır; örneğin
    ``585.069`` = 585069 ve ``-96.377`` = -96377. Bunları ondalık olarak
    okumak THYAO ve AKCNS gibi şirketlerde 1.000 kat ölçek hatasına yol
    açıyordu. Bu yardımcı yalnızca finansal tablo metrik satırlarında
    kullanılır, dolayısıyla oran/ondalık verilerin genel parser davranışını
    değiştirmez.
    """
    if value is None:
        return None
    if isinstance(value, numbers.Number):
        return float(value)

    text = str(value).strip()
    if not text or text.upper() in {"-", "A/D", "N/A", "NAN"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    text = (
        text.replace("\xa0", "")
        .replace(" ", "")
        .replace("TL", "")
        .replace("TRY", "")
        .replace("%", "")
    )

    sign = -1.0 if text.startswith("-") else 1.0
    unsigned = text[1:] if text.startswith(('-', '+')) else text

    # Türkçe/İngilizce binlik grupları: 13.672.003 / 585.069 / 96.377
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", unsigned):
        number = float(unsigned.replace(".", ""))
        return -number if negative else sign * number

    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", unsigned):
        number = float(unsigned.replace(",", ""))
        return -number if negative else sign * number

    # Hem nokta hem virgül varsa mevcut TR biçimi: 1.234,56
    if "." in unsigned and "," in unsigned:
        normalized = unsigned.replace(".", "").replace(",", ".")
    elif "," in unsigned:
        normalized = unsigned.replace(",", ".")
    else:
        normalized = unsigned

    try:
        number = float(normalized)
        number *= sign
        return -abs(number) if negative else number
    except Exception:
        return None


def numeric_values_from_cell(text):
    text = str(text).strip()
    if not text:
        return []
    whole = parse_financial_number(text)
    if whole is not None:
        return [whole]
    pieces = re.findall(r"-?\(?\d[\d.,]*\)?", text)
    return [x for x in (parse_financial_number(p) for p in pieces) if x is not None]


def financial_values_from_row(row, label_index=0, scale=1):
    """Etiket hücresinden sonraki cari/karşılaştırmalı dönem tutarlarını çıkarır.

    KAP şablonlarında etiket bazen ilk hücrede, bazen taxonomy/role
    hücrelerinden sonra gelir. Değerleri doğrudan etiketin sağından okumak,
    THYAO'daki ``21`` gibi dipnot numaralarının cari dönem değeri sanılmasını
    önler.
    """
    if not row:
        return []

    cells = row[label_index + 1:]
    cell_values = [numeric_values_from_cell(cell) for cell in cells]

    # Boş hücreleri korumak yerine yalnızca sayısal hücreleri sırayla al.
    nonempty = [vals for vals in cell_values if vals]
    if not nonempty:
        return []

    # Etiketten hemen sonraki hücre çoğu raporda dipnot referansıdır.
    # Tek, küçük, tam sayı ve arkasında en az iki sayısal dönem hücresi varsa at.
    first = nonempty[0]
    if (
        len(first) == 1
        and abs(first[0]) <= 99
        and float(first[0]).is_integer()
        and len(nonempty) >= 3
    ):
        nonempty = nonempty[1:]

    values = []
    for vals in nonempty:
        values.extend(vals)

    return values


METRIC_RULES = {
    "hasilat": {
        "aliases": ["Hasılat", "Hasilat", "Satış Gelirleri", "Satis Gelirleri", "Net Satışlar", "Net Satislar"],
        "excludes": [],
    },
    "net_kar_ana": {
        "aliases": ["Ana Ortaklık Payları", "Ana Ortaklik Paylari", "Dönem Kârının (Zararının) Dağılımı, Ana Ortaklık Payları", "Donem Karinin (Zararinin) Dagilimi, Ana Ortaklik Paylari"],
        "excludes": [],
    },
    "net_kar": {
        "aliases": ["Net Dönem Kârı (Zararı)", "Net Donem Kari (Zarari)", "Dönem Kârı (Zararı)", "Donem Kari (Zarari)"],
        "excludes": ["Ana Ortaklık Payları", "Ana Ortaklik Paylari"],
    },
    "faaliyet_kari": {
        "aliases": ["Esas Faaliyet Kârı (Zararı)", "Esas Faaliyet Kari (Zarari)", "Faaliyet Kârı (Zararı)", "Faaliyet Kari (Zarari)"],
        "excludes": ["Finansman", "Vergi Öncesi"],
    },
    "nakit": {
        "aliases": ["Nakit ve Nakit Benzerleri", "Nakit ve Nakit Benzeri"],
        "excludes": ["Nakit Akış", "Nakit Akis"],
    },
    "ozkaynak_ana": {
        "aliases": ["Ana Ortaklığa Ait Özkaynaklar", "Ana Ortakliga Ait Ozkaynaklar"],
        "excludes": [],
    },
    "ozkaynak_toplam": {
        "aliases": ["Toplam Özkaynaklar", "Toplam Ozkaynaklar"],
        "excludes": ["Ana Ortaklığa", "Ana Ortakliga"],
    },
    "kv_borc": {
        "aliases": ["Kısa Vadeli Borçlanmalar", "Kisa Vadeli Borclanmalar", "Kısa Vadeli Finansal Borçlar", "Kisa Vadeli Finansal Borclar"],
        "excludes": ["Uzun Vadeli Borçlanmaların Kısa Vadeli Kısımları", "Uzun Vadeli Borclanmalarin Kisa Vadeli Kisimlari", "Uzun Vadeli Finansal Borçların Kısa Vadeli Kısımları", "Uzun Vadeli Finansal Borclarin Kisa Vadeli Kisimlari"],
    },
    "uv_kisa": {
        "aliases": ["Uzun Vadeli Borçlanmaların Kısa Vadeli Kısımları", "Uzun Vadeli Borclanmalarin Kisa Vadeli Kisimlari", "Uzun Vadeli Finansal Borçların Kısa Vadeli Kısımları", "Uzun Vadeli Finansal Borclarin Kisa Vadeli Kisimlari"],
        "excludes": [],
    },
    "uv_borc": {
        "aliases": ["Uzun Vadeli Borçlanmalar", "Uzun Vadeli Borclanmalar", "Uzun Vadeli Finansal Borçlar", "Uzun Vadeli Finansal Borclar"],
        "excludes": ["Kısa Vadeli Kısımları", "Kisa Vadeli Kisimlari"],
    },
    "amortisman_itfa": {
        "aliases": [
            "Amortisman ve İtfa Giderleri", "Amortisman ve Itfa Giderleri",
            "Amortisman ve İtfa Payları", "Amortisman ve Itfa Paylari",
            "Amortisman, İtfa ve Tükenme Payları", "Amortisman, Itfa ve Tukenme Paylari",
            "Amortisman Giderleri", "Amortisman Gideri"
        ],
        "excludes": ["Satış", "Satis", "Elden Çıkarma", "Elden Cikarma"],
    },
    "brut_kar": {
        "aliases": ["Brüt Kâr (Zarar)", "Brut Kar (Zarar)", "Brüt Kâr", "Brut Kar"],
        "excludes": [],
    },
}


def row_match_score(row, aliases, excludes):
    if not row:
        return None
    label = normalize_text(" ".join(row[:3]))
    for excluded in excludes:
        if normalize_text(excluded) in label:
            return None
    best = None
    for index, alias in enumerate(aliases):
        a = normalize_text(alias)
        if a not in label:
            continue
        score = 1000 - index * 20
        if label == a:
            score += 300
        elif label.endswith(a):
            score += 150
        elif label.startswith(a):
            score += 120
        score -= min(max(0, len(label) - len(a)), 200) * 0.2
        best = score if best is None or score > best else best
    return best


def find_metric_values(rows, metric_key, scale=1):
    rule = METRIC_RULES[metric_key]
    candidates = []
    aliases_norm = [normalize_text(a) for a in rule["aliases"]]

    for row in rows:
        score = row_match_score(row, rule["aliases"], rule["excludes"])
        if score is None:
            continue

        # Gerçek metrik etiketinin hangi hücrede olduğunu bul; değerleri onun
        # sağından oku. Bu taxonomy/role ve dipnot hücrelerini veri alanından
        # ayırır.
        label_index = 0
        for i, cell in enumerate(row[:4]):
            c = normalize_text(cell)
            if any(a in c for a in aliases_norm):
                label_index = i
                break

        vals = financial_values_from_row(row, label_index=label_index, scale=scale)
        if vals:
            candidates.append((score, vals, row))

    if not candidates:
        return []
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _scaled(value, scale):
    return None if value is None else float(value) * scale


@lru_cache(maxsize=2048)
def parse_financial_report(disclosure_index):
    html = disclosure_body_html(int(disclosure_index))
    scale = detect_scale(html)
    rows = html_rows(html)
    if not rows:
        raise ValueError(f"{disclosure_index} finansal satırlar bulunamadı.")

    def values(key):
        return find_metric_values(rows, key, scale)

    def first(key):
        vals = values(key)
        return _scaled(vals[0], scale) if vals else None

    def second(key):
        vals = values(key)
        return _scaled(vals[1], scale) if len(vals) >= 2 else None

    current = {
        "hasilat": first("hasilat"),
        "net_kar": first("net_kar_ana") or first("net_kar"),
        "faaliyet_kari": first("faaliyet_kari"),
        "nakit": first("nakit"),
        "ozkaynak": first("ozkaynak_ana") or first("ozkaynak_toplam"),
        "kv_borc": first("kv_borc"),
        "uv_kisa": first("uv_kisa"),
        "uv_borc": first("uv_borc"),
        "brut_kar": first("brut_kar"),
        "amortisman_itfa": first("amortisman_itfa"),
        "sunum_carpani": scale,
        "bildirim_id": int(disclosure_index),
    }

    # Same-report comparison columns are the correct basis for flow growth under TMS 29.
    comparison = {
        "hasilat": second("hasilat"),
        "net_kar": second("net_kar_ana") or second("net_kar"),
        "faaliyet_kari": second("faaliyet_kari"),
        "brut_kar": second("brut_kar"),
        "amortisman_itfa": second("amortisman_itfa"),
    }
    return {"current": current, "comparison": comparison}


def finansal_borc_hesapla(data):
    vals = [data.get("kv_borc"), data.get("uv_kisa"), data.get("uv_borc")]
    clean = [x for x in vals if x is not None]
    return sum(clean) if clean else None


def net_borc_hesapla(finansal_borc, nakit):
    if finansal_borc is None:
        return None
    return finansal_borc - (nakit or 0)


def kritik_veriler_tam_mi(current, comparison, previous_same):
    critical = [
        current.get("hasilat"), current.get("net_kar"), current.get("faaliyet_kari"), current.get("ozkaynak"),
        comparison.get("hasilat"), comparison.get("net_kar"), comparison.get("faaliyet_kari"),
        previous_same.get("ozkaynak"),
    ]
    return all(x is not None for x in critical)


@lru_cache(maxsize=512)
def fss_v2_veri_paketi(hisse):
    """Backward-compatible data package used by FSS V3.

    current: current-period figures from current report.
    comparison: same-report comparative flow figures (TMS 29-consistent basis).
    previous_same: prior year's same-period report; used mainly for balance-sheet/equity reference.
    """
    hisse = hisse.upper().strip()
    meta = kap_company_meta(hisse)
    current_report, previous_report = select_current_and_previous_report(hisse)
    current_id = int(current_report["disclosureIndex"])
    previous_id = int(previous_report["disclosureIndex"]) if previous_report is not None else None

    parsed_current = parse_financial_report(current_id)
    current = parsed_current["current"]
    comparison = parsed_current["comparison"]
    if previous_id is not None:
        parsed_previous = parse_financial_report(previous_id)
        previous_same = parsed_previous["current"]
    else:
        previous_same = {}

    finansal_borc = finansal_borc_hesapla(current)
    net_borc = net_borc_hesapla(finansal_borc, current.get("nakit"))

    # If same-report comparative flow extraction is unavailable, use previous report as fallback.
    comparison_source = "current_report_comparative"
    for key in ("hasilat", "net_kar", "faaliyet_kari", "brut_kar", "amortisman_itfa"):
        if comparison.get(key) is None:
            comparison[key] = previous_same.get(key)
            comparison_source = "mixed_with_previous_report_fallback"

    data_quality_issues = veri_kalite_kontrolu(current, comparison, previous_same)
    data_quality_severity, data_quality_flags = veri_kalite_seviyesi(data_quality_issues)

    return {
        "hisse": hisse,
        "guid": meta["oid"],
        "company_name": meta["title"],
        "bildirim_id": current_id,
        "previous_bildirim_id": previous_id,
        "current_year": current_report["_year"],
        "current_period": current_report["_rule_type"],
        "previous_year": previous_report["_year"] if previous_report is not None else None,
        "previous_period": previous_report["_rule_type"] if previous_report is not None else None,
        "current": current,
        "comparison": comparison,
        "comparison_source": comparison_source,
        "previous_same": previous_same,
        "finansal_borc": finansal_borc,
        "net_borc": net_borc,
        "kritik_veriler_tam": kritik_veriler_tam_mi(current, comparison, previous_same),
        "stale_fallback": bool(current_report.get("_stale_fallback")),
        "data_quality_issues": data_quality_issues,
        "data_quality_severity": data_quality_severity,
        "data_quality_flags": data_quality_flags,
    }



def veri_kalite_kontrolu(current, comparison, previous_same):
    """Conservative sanity checks. Never fabricates a financial value.

    Suspicious values remain visible, but FSS/app can warn the user instead of
    silently treating a parser anomaly as a valid economic signal.
    """
    issues = []
    rev = current.get("hasilat")
    eq = current.get("ozkaynak")
    op = current.get("faaliyet_kari")
    np = current.get("net_kar")
    if rev is not None and rev > 0:
        if abs(rev) < 1_000_000:
            issues.append("Hasılat olağandışı düşük; KAP satır/ölçek eşleşmesi kontrol edilmeli.")
        for name, val in (("Faaliyet kârı", op), ("Net kâr", np)):
            if val is not None and abs(rev) >= 1_000_000_000 and 0 < abs(val) < abs(rev) * 0.0001:
                issues.append(f"{name} hasılata göre olağandışı küçük; KAP satır/ölçek eşleşmesi kontrol edilmeli.")
    if eq is not None and abs(eq) < 10_000_000:
        issues.append("Özkaynak olağandışı düşük; KAP ölçek eşleşmesi kontrol edilmeli.")
    if not previous_same.get("ozkaynak"):
        issues.append("Önceki aynı dönem özkaynak bulunamadı; ROE eksik hesaplanabilir.")
    return issues

def veri_kalite_seviyesi(issues):
    """Return (severity, critical_flags) for score gating."""
    issues = list(issues or [])
    critical_flags = []
    for issue in issues:
        t = normalize_text(issue)
        if "hasilat olagandisi dusuk" in t:
            critical_flags.append("revenue_scale")
        if "faaliyet kari hasilata gore olagandisi kucuk" in t:
            critical_flags.append("operating_profit_scale")
        if "net kar hasilata gore olagandisi kucuk" in t:
            critical_flags.append("net_profit_scale")
        if "ozkaynak olagandisi dusuk" in t:
            critical_flags.append("equity_scale")
    severity = "critical" if critical_flags else ("warning" if issues else "ok")
    return severity, critical_flags


# Compatibility aliases for older modules, if any.
rapor_ozeti = fss_v2_veri_paketi


if __name__ == "__main__":
    TEST_HISSELERI = ["FROTO", "TOASO", "TTRAK", "TUPRS"]
    for hisse in TEST_HISSELERI:
        print("\n" + "=" * 90)
        print(hisse)
        try:
            d = fss_v2_veri_paketi(hisse)
            print("Cari:", d["bildirim_id"], d["current_year"], d["current_period"])
            print("Önceki:", d["previous_bildirim_id"], d["previous_year"], d["previous_period"])
            print("Hasılat:", d["current"].get("hasilat"))
            print("Karşılaştırmalı hasılat:", d["comparison"].get("hasilat"))
            print("Net kâr:", d["current"].get("net_kar"))
            print("Karşılaştırmalı net kâr:", d["comparison"].get("net_kar"))
            print("Faaliyet kârı:", d["current"].get("faaliyet_kari"))
            print("Karşılaştırmalı faaliyet kârı:", d["comparison"].get("faaliyet_kari"))
            print("Finansal borç:", d["finansal_borc"])
            print("Net borç:", d["net_borc"])
            print("Kaynak:", d["comparison_source"])
            print("Kritik veri tam:", d["kritik_veriler_tam"])
        except Exception as e:
            print(type(e).__name__, e)
