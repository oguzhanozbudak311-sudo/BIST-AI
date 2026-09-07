"""BIST AI FINAL - OFFLINE SELF TEST

Internet gerektirmez. 50 hissenin tamaminda:
- evren/ticker kontrolu
- FSS V3.1 veri semasi ve sektor profili
- value-trap mantigi
- TAS V2 hesap motoru (sentetik OHLCV ile)
- moduller arasi temel sozlesmeler
kontrol edilir.

Canli KAP / Is Yatirim / Yahoo cevaplari bu testin kapsami disindadir.
"""
from __future__ import annotations

import math
import sys
import types
import numpy as np
import pandas as pd

# Offline ortamda yfinance kurulu olmasa bile TAS motorunu sentetik veriyle test edebilmek icin.
if "yfinance" not in sys.modules:
    fake_yf = types.ModuleType("yfinance")
    fake_yf.download = lambda *args, **kwargs: pd.DataFrame()
    sys.modules["yfinance"] = fake_yf

from universe import HISSELER, SEKTOR_TEST_HINT, evren_kontrolu
from fss_v3_engine import fss_v3_hesapla
import tas_engine


def synthetic_kap(i: int):
    # Degisik sirket profilleri uret: buyuyen, daralan, zarar eden, net nakitli.
    base = 10_000_000_000 + i * 300_000_000
    comp_sales = base
    growth = [-0.30, -0.12, 0.05, 0.18, 0.45][i % 5]
    sales = comp_sales * (1 + growth)

    comp_op_margin = [0.04, 0.08, 0.12][i % 3]
    cur_op_margin = [0.02, 0.06, 0.11, 0.16][i % 4]
    comp_op = comp_sales * comp_op_margin
    op = sales * cur_op_margin

    comp_np = comp_sales * [0.02, 0.04, 0.07][i % 3]
    npv = sales * [0.015, 0.035, 0.06][i % 3]
    if i % 11 == 0:
        npv = -abs(npv)
    if i % 13 == 0:
        op = -abs(op)

    equity_prev = base * 0.55
    equity = equity_prev * (1 + [0.02, 0.12, 0.25][i % 3])
    cash = base * [0.05, 0.15, 0.35][i % 3]
    kv = base * [0.08, 0.18][i % 2]
    uv_short = base * 0.04
    uv = base * [0.10, 0.25][i % 2]
    debt = kv + uv_short + uv
    net_debt = debt - cash

    return {
        "hisse": HISSELER[i],
        "current_year": 2026,
        "current_period": "6 Aylık",
        "bildirim_id": 1_600_000 + i,
        "comparison_source": "current_report_comparative",
        "current": {
            "hasilat": sales,
            "net_kar": npv,
            "faaliyet_kari": op,
            "ozkaynak": equity,
            "nakit": cash,
            "kv_borc": kv,
            "uv_kisa": uv_short,
            "uv_borc": uv,
            "amortisman_itfa": abs(op) * 0.35 + base * 0.005,
        },
        "comparison": {
            "hasilat": comp_sales,
            "net_kar": comp_np,
            "faaliyet_kari": comp_op,
        },
        "previous_same": {"ozkaynak": equity_prev},
        "finansal_borc": debt,
        "net_borc": net_debt,
    }


def synthetic_is(i: int):
    # Iskontolu/primli senaryolari donustur.
    sector = {"fk": 12.0, "fd_favok": 9.0, "fd_satislar": 1.5, "pddd": 2.0}
    mult = [0.55, 0.80, 1.00, 1.25, 1.70][i % 5]
    company = {k: v * mult for k, v in sector.items()}
    discount = {k: (company[k] / sector[k] - 1) * 100 for k in sector}
    return {
        "hisse": HISSELER[i],
        "hisse_adi": HISSELER[i],
        "sektor": SEKTOR_TEST_HINT[HISSELER[i]],
        "company": company,
        "sector": sector,
        "prim_iskonto": discount,
    }


def synthetic_ohlcv(n=420):
    # Deterministik, trend + salinim; tum teknik hesaplar icin yeterli tarihce.
    x = np.arange(n, dtype=float)
    close = 100 + 0.08 * x + 5 * np.sin(x / 17.0)
    open_ = close * (1 + 0.002 * np.sin(x / 5.0))
    high = np.maximum(open_, close) + 1.2 + 0.2 * np.sin(x / 9.0)
    low = np.minimum(open_, close) - 1.2 - 0.2 * np.cos(x / 11.0)
    vol = 1_000_000 + (x % 30) * 20_000
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open":open_, "High":high, "Low":low, "Close":close, "Volume":vol}, index=idx)


def main():
    evren_kontrolu()
    assert set(SEKTOR_TEST_HINT) == set(HISSELER)

    fss_results = []
    for i, h in enumerate(HISSELER):
        out = fss_v3_hesapla(h, kap_data=synthetic_kap(i), is_data=synthetic_is(i))
        s = out.get("FSS_V3")
        assert s is not None and 0 <= s <= 100, (h, s)
        assert out.get("valuation_profile"), h
        assert out.get("value_trap_risk") in {"Yok", "Orta", "Yüksek"}, h
        fss_results.append((h, s))

    old_fetch = tas_engine.fiyat_verisi_getir
    try:
        tas_engine.fiyat_verisi_getir = lambda hisse, period="2y": synthetic_ohlcv()
        for h in HISSELER:
            out = tas_engine.tas_hesapla(h)
            s = out.get("TAS")
            assert s is not None and 0 <= s <= 100, (h, s)
            assert out.get("Ticker") == f"{h}.IS", (h, out.get("Ticker"))
    finally:
        tas_engine.fiyat_verisi_getir = old_fetch

    print("=" * 72)
    print("BIST AI FINAL OFFLINE SELF TEST: BASARILI")
    print(f"Hisse evreni : {len(HISSELER)}/50")
    print(f"FSS V3.1     : {len(fss_results)}/50")
    print(f"TAS V2       : {len(HISSELER)}/50")
    print("Syntax/compile testi ayrica paket olusturulurken uygulanir.")
    print("=" * 72)


if __name__ == "__main__":
    main()
