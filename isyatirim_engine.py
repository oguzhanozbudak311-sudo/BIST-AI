import re
import numbers
from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = (
    "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/"
    "Sayfalar/Temel-Degerler-Ve-Oranlar.aspx"
)
COMPANY_CARD_URL = (
    "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/"
    "Sayfalar/sirket-karti.aspx?hisse={hisse}"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    trans = str.maketrans({
        "İ":"i","I":"i","ı":"i","Ş":"s","ş":"s","Ğ":"g","ğ":"g",
        "Ü":"u","ü":"u","Ö":"o","ö":"o","Ç":"c","ç":"c",
    })
    return re.sub(r"\s+", " ", text.translate(trans).lower()).strip()


def tr_float(value):
    if value is None:
        return None
    if isinstance(value, numbers.Number):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return float(value)
    text = str(value).strip()
    if text == "" or text == "-" or text.upper() == "A/D" or text.lower() == "nan":
        return None
    text = text.replace("\xa0", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def flatten_column(column):
    if isinstance(column, tuple):
        return " ".join(str(x).strip() for x in column if str(x).strip() and str(x).lower() != "nan")
    return str(column).strip()


def find_column(columns, candidates):
    for col in columns:
        n = normalize_text(col)
        for c in candidates:
            if normalize_text(c) in n:
                return col
    return None


@lru_cache(maxsize=256)
def get_html(url):
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def read_tables(html):
    return pd.read_html(StringIO(html), decimal=",", thousands=".")


def find_summary_table(tables):
    for t in tables:
        t = t.copy()
        t.columns = [flatten_column(x) for x in t.columns]
        if find_column(t.columns, ["Kod"]) is not None and find_column(t.columns, ["Sektör", "Sektor"]) is not None:
            return t
    return None


def find_ratio_table(tables):
    for t in tables:
        t = t.copy()
        t.columns = [flatten_column(x) for x in t.columns]
        if (
            find_column(t.columns, ["Kod"]) is not None
            and find_column(t.columns, ["F/K"]) is not None
            and find_column(t.columns, ["FD/FAVÖK", "FD/FAVOK"]) is not None
            and find_column(t.columns, ["PD/DD"]) is not None
        ):
            return t
    return None


def find_stock_row(table, hisse):
    kod_col = find_column(table.columns, ["Kod"])
    if kod_col is None:
        return None
    kodlar = table[kod_col].astype(str).str.upper().str.strip()
    rows = table[kodlar == hisse.upper().strip()]
    return None if rows.empty else rows.iloc[0]


@lru_cache(maxsize=1)
def ana_sayfa_verileri():
    html = get_html(BASE_URL)
    tables = read_tables(html)
    summary = find_summary_table(tables)
    if summary is None:
        raise ValueError("İş Yatırım ana sektör tablosu bulunamadı.")
    return {"html": html, "summary": summary}


@lru_cache(maxsize=256)
def hisse_meta_getir(hisse):
    hisse = hisse.upper().strip()
    summary = ana_sayfa_verileri()["summary"]
    row = find_stock_row(summary, hisse)
    if row is None:
        raise ValueError(f"{hisse} İş Yatırım ana sektör tablosunda bulunamadı.")
    sektor_col = find_column(summary.columns, ["Sektör", "Sektor"])
    ad_col = find_column(summary.columns, ["Hisse Adı", "Hisse Adi"])
    return {
        "hisse": hisse,
        "hisse_adi": str(row[ad_col]).strip() if ad_col is not None else hisse,
        "sektor": str(row[sektor_col]).strip(),
    }


@lru_cache(maxsize=256)
def sirket_oranlari_getir(hisse):
    hisse = hisse.upper().strip()
    html = get_html(COMPANY_CARD_URL.format(hisse=hisse))
    table = find_ratio_table(read_tables(html))
    if table is None:
        raise ValueError(f"{hisse} şirket kartında gerçekleşen oran tablosu bulunamadı.")
    row = find_stock_row(table, hisse)
    if row is None:
        raise ValueError(f"{hisse} şirket kartındaki oran tablosunda bulunamadı.")
    def val(cands):
        c = find_column(table.columns, cands)
        return tr_float(row[c]) if c is not None else None
    return {
        "fk": val(["F/K"]),
        "fd_favok": val(["FD/FAVÖK", "FD/FAVOK"]),
        "fd_satislar": val(["FD/Satışlar", "FD/Satislar"]),
        "pddd": val(["PD/DD"]),
        "kapanis": val(["Kapanış", "Kapanis"]),
        "son_donem": str(row[find_column(table.columns, ["Son Dönem", "Son Donem"])]) if find_column(table.columns, ["Son Dönem", "Son Donem"]) is not None else "",
    }


@lru_cache(maxsize=1)
def sektor_option_map_getir():
    soup = BeautifulSoup(ana_sayfa_verileri()["html"], "html.parser")
    result = {}
    for option in soup.find_all("option"):
        text = option.get_text(" ", strip=True)
        value = str(option.get("value") or "").strip()
        if not text or not value:
            continue
        m = re.search(r"(?:sektor=)?(\d{4})", value, flags=re.IGNORECASE)
        if m:
            result[normalize_text(text)] = {"name": text, "code": m.group(1)}
    return result


def sektor_kodu_getir(sektor_adi):
    options = sektor_option_map_getir()
    target = normalize_text(sektor_adi)
    if target in options:
        return options[target]
    for key, value in options.items():
        if target in key or key in target:
            return value
    raise ValueError(f"İş Yatırım sektör kodu bulunamadı: {sektor_adi}")


def parse_sector_average(html):
    text = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    patterns = {
        "fk": r"F/K\s*:\s*([0-9.,]+|A/D)",
        "fd_favok": r"FD/FAVÖK\s*:\s*([0-9.,]+|A/D)",
        "fd_satislar": r"FD/Satışlar\s*:\s*([0-9.,]+|A/D)",
        "pddd": r"PD/DD\s*:\s*([0-9.,]+|A/D)",
    }
    out = {}
    for k, p in patterns.items():
        m = re.search(p, text, flags=re.IGNORECASE)
        v = tr_float(m.group(1)) if m else None
        out[k] = None if v is not None and v <= 0 else v
    return out


def prim_iskonto_hesapla(sirket, sektor):
    if sirket is None or sektor is None or sektor <= 0:
        return None
    return (sirket / sektor - 1) * 100


@lru_cache(maxsize=256)
def isyatirim_hisse_analizi(hisse):
    hisse = hisse.upper().strip()
    meta = hisse_meta_getir(hisse)
    company = sirket_oranlari_getir(hisse)
    sektor_info = sektor_kodu_getir(meta["sektor"])
    sektor_url = BASE_URL + "?sektor=" + sektor_info["code"]
    sector = parse_sector_average(get_html(sektor_url))
    discount = {k: prim_iskonto_hesapla(company.get(k), sector.get(k)) for k in ("fk", "fd_favok", "fd_satislar", "pddd")}
    return {
        "hisse": hisse,
        "hisse_adi": meta["hisse_adi"],
        "sektor": meta["sektor"],
        "sektor_kodu": sektor_info["code"],
        "sektor_url": sektor_url,
        "company": company,
        "sector": sector,
        "prim_iskonto": discount,
    }


if __name__ == "__main__":
    for h in ["FROTO", "TOASO", "TTRAK", "TUPRS"]:
        try:
            x = isyatirim_hisse_analizi(h)
            print(h, x["sektor"], x["company"], x["sector"], x["prim_iskonto"])
        except Exception as e:
            print(h, type(e).__name__, e)
