"""Canli dogrulanmis 4 hisse icin FSS V3.1 regresyon testi.

Bu test 2026-09-05 tarihinde panelde gorulen dogrulanmis finansal/oran girdilerini
fixture olarak kullanir. Ag erisimi gerekmez; skor motorunda sonraki degisikliklerin
beklenmeyen sonuc uretmesini yakalamak icindir.
"""
from fss_v3_engine import fss_v3_hesapla


def kap(cur, comp, prev_eq, net_debt):
    return {
        "current_period": "6 Aylık",
        "current": cur,
        "comparison": comp,
        "previous_same": {"ozkaynak": prev_eq},
        "net_borc": net_debt,
    }


def isd(sektor, company, sector):
    d = {}
    for k in ("fk", "fd_favok", "pddd", "fd_satislar"):
        a, b = company.get(k), sector.get(k)
        d[k] = None if a is None or b in (None, 0) else (a / b - 1) * 100
    return {"sektor": sektor, "company": company, "sector": sector, "prim_iskonto": d}


FIX = {
    "FROTO": (
        kap(
            {"hasilat":427.07e9,"net_kar":10.34e9,"faaliyet_kari":11.65e9,"ozkaynak":179.19e9,"amortisman_itfa":None},
            {"hasilat":482.67e9,"net_kar":17.16e9,"faaliyet_kari":26.72e9},
            140.46e9, 111.98e9,
        ),
        isd("Otomotiv", {"fk":7.40,"fd_favok":5.40,"pddd":1.50,"fd_satislar":None}, {"fk":10.71,"fd_favok":10.56,"pddd":2.01,"fd_satislar":None}),
        57.8,
    ),
    "TOASO": (
        kap(
            {"hasilat":201.80e9,"net_kar":6.29e9,"faaliyet_kari":2.88e9,"ozkaynak":65.74e9,"amortisman_itfa":None},
            {"hasilat":125.63e9,"net_kar":2.12e9,"faaliyet_kari":1.08e9},
            48.24e9, 59.36e9,
        ),
        isd("Otomotiv", {"fk":4.30,"fd_favok":5.20,"pddd":1.40,"fd_satislar":None}, {"fk":10.71,"fd_favok":10.56,"pddd":2.01,"fd_satislar":None}),
        80.1,
    ),
    "TTRAK": (
        kap(
            {"hasilat":23.68e9,"net_kar":-669.15e6,"faaliyet_kari":-1.07e9,"ozkaynak":18.98e9,"amortisman_itfa":None},
            {"hasilat":34.32e9,"net_kar":778.08e6,"faaliyet_kari":2.60e9},
            15.16e9, 9.86e9,
        ),
        isd("Otomotiv", {"fk":7.70,"fd_favok":4.70,"pddd":1.90,"fd_satislar":None}, {"fk":10.71,"fd_favok":10.56,"pddd":2.01,"fd_satislar":None}),
        45.0,
    ),
    "TUPRS": (
        kap(
            {"hasilat":662.79e9,"net_kar":49.85e9,"faaliyet_kari":59.03e9,"ozkaynak":456.14e9,"amortisman_itfa":None},
            {"hasilat":464.12e9,"net_kar":11.87e9,"faaliyet_kari":18.16e9},
            306.64e9, -127.64e9,
        ),
        isd("Petrol", {"fk":21.50,"fd_favok":7.70,"pddd":1.70,"fd_satislar":None}, {"fk":10.16,"fd_favok":6.12,"pddd":1.59,"fd_satislar":None}),
        76.6,
    ),
}


def main():
    for h, (k, i, expected) in FIX.items():
        out = fss_v3_hesapla(h, kap_data=k, is_data=i)
        got = round(out["FSS_V3"], 1)
        assert abs(got - expected) <= 0.2, (h, got, expected)
        if h == "TTRAK":
            assert out["value_trap_risk"] == "Yüksek", out["value_trap_risk"]
        if h == "FROTO":
            assert out["value_trap_risk"] == "Orta", out["value_trap_risk"]
        if h in ("TOASO", "TUPRS"):
            assert out["value_trap_risk"] == "Yok", out["value_trap_risk"]
        print(f"{h}: {got:.1f} OK | value-trap={out['value_trap_risk']}")
    print("4/4 canli-dogrulanmis FSS regresyon testi BASARILI")


if __name__ == "__main__":
    main()


def safety_gate_tests():
    base_is = isd("Sanayi", {"fk":10.0,"fd_favok":8.0,"pddd":1.5,"fd_satislar":None}, {"fk":12.0,"fd_favok":9.0,"pddd":2.0,"fd_satislar":None})

    # THYAO tipi: hasılat/dipnot numarasi olcek hatasi kritik sayilmali.
    thyao_kap = kap(
        {"hasilat":21.0,"net_kar":19.0,"faaliyet_kari":-5.0,"ozkaynak":1.02e6,"amortisman_itfa":None},
        {"hasilat":585.0,"net_kar":25.0,"faaliyet_kari":25.0},
        1.0e6, 0.0,
    )
    thyao_kap.update({"data_quality_severity":"critical","data_quality_flags":["revenue_scale","equity_scale"]})
    out = fss_v3_hesapla("THYAO", kap_data=thyao_kap, is_data=base_is)
    assert out["FSS_V3"] is None and out["score_gate_reason"] == "critical_financial_data_quality"

    # AKCNS tipi: kâr satirlari hasılata gore imkansiz derecede kucuk.
    akcns_kap = kap(
        {"hasilat":13.67e9,"net_kar":-96377.0,"faaliyet_kari":-362003.0,"ozkaynak":28.53e9,"amortisman_itfa":None},
        {"hasilat":13.03e9,"net_kar":91806.0,"faaliyet_kari":69115.0},
        27e9, -0.3e9,
    )
    akcns_kap.update({"data_quality_severity":"critical","data_quality_flags":["operating_profit_scale","net_profit_scale"]})
    out = fss_v3_hesapla("AKCNS", kap_data=akcns_kap, is_data=base_is)
    assert out["FSS_V3"] is None and out["FSS_V3_RAW"] is not None

    # KAYSE tipi: eski finansal veri ham skorlanabilir ama Genel FSS olarak kullanilamaz.
    kayse_kap = kap(
        {"hasilat":29.90e9,"net_kar":-883.05e6,"faaliyet_kari":1.07e9,"ozkaynak":37.09e9,"amortisman_itfa":None},
        {"hasilat":25.20e9,"net_kar":272.67e6,"faaliyet_kari":388.91e6},
        None, 8.5e9,
    )
    kayse_kap.update({"stale_fallback":True,"current_year":2024,"data_quality_severity":"warning","data_quality_flags":[]})
    out = fss_v3_hesapla("KAYSE", kap_data=kayse_kap, is_data=base_is)
    assert out["FSS_V3"] is None and out["score_gate_reason"] == "stale_financials" and out["FSS_V3_RAW"] is not None

    print("THYAO/AKCNS/KAYSE safety-gate testleri BASARILI")


if __name__ == "__main__":
    safety_gate_tests()
