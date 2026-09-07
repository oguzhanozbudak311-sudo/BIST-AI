from financial_data_engine import fss_v2_veri_paketi
from isyatirim_engine import isyatirim_hisse_analizi


# ============================================================
# BIST AI - FSS V3.1.3
# ============================================================
# Ana faktörler değişmedi:
#   Değerleme       %25
#   Kalite          %25
#   Büyüme          %25
#   Finansal Sağlık %25
# Genel panelde FSS %60 + TAS %40 kullanılmaya devam eder.
#
# V3.1 ekleri:
#   1) Sektör-duyarlı değerleme ağırlıkları
#   2) Value-trap risk bayrağı (skoru yapay olarak değiştirmez)
#   3) Net Borç/FAVÖK için KAP tabanlı yıllıklandırılmış FAVÖK
#      yaklaşımı; veri yoksa mevcut implied yönteme güvenli fallback
# ============================================================


def safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return float(a) / float(b)


def degerleme_skoru(prim_iskonto):
    if prim_iskonto is None:
        return None
    if prim_iskonto <= -40: return 100
    if prim_iskonto <= -25: return 90
    if prim_iskonto <= -10: return 75
    if prim_iskonto <= 10: return 60
    if prim_iskonto <= 25: return 40
    if prim_iskonto <= 40: return 20
    return 10


def _norm_text(x):
    return str(x or "").lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")


def sektor_degerleme_profili(sektor):
    """Return valuation weights based on sector economics.

    Weights only redistribute the valuation factor; the valuation factor
    remains 25% of FSS. Unknown sectors use the balanced default.
    """
    s = _norm_text(sektor)
    profile = "Dengeli"
    w = {"fk": .40, "fd_favok": .40, "pddd": .20, "fd_satislar": 0.0}

    if any(k in s for k in ["gayrimenkul", "gmyo", "yatirim ortakligi"]):
        profile = "Varlık ağırlıklı"
        w = {"fk": .25, "fd_favok": .15, "pddd": .60, "fd_satislar": 0.0}
    elif any(k in s for k in ["teknoloji", "yazilim", "bilisim"]):
        profile = "Büyüme/teknoloji"
        w = {"fk": .30, "fd_favok": .35, "pddd": .15, "fd_satislar": .20}
    elif any(k in s for k in ["petrol", "enerji", "elektrik", "madencilik"]):
        profile = "Sermaye yoğun/döngüsel"
        w = {"fk": .30, "fd_favok": .50, "pddd": .20, "fd_satislar": 0.0}
    elif any(k in s for k in ["otomotiv", "havayolu", "ulastirma", "demir", "celik", "metal", "sanayi"]):
        profile = "Sermaye yoğun sanayi"
        w = {"fk": .30, "fd_favok": .50, "pddd": .20, "fd_satislar": 0.0}
    elif any(k in s for k in ["perakende", "gida", "icecek", "telekom", "saglik"]):
        profile = "Operasyon odaklı"
        w = {"fk": .35, "fd_favok": .45, "pddd": .20, "fd_satislar": 0.0}

    return profile, w


def roe_hesapla(net_kar, current_equity, previous_equity):
    if net_kar is None or current_equity is None or previous_equity is None:
        return None
    avg = (current_equity + previous_equity) / 2
    if avg <= 0:
        return None
    return (net_kar * 2) / avg * 100


def roe_skoru(roe):
    if roe is None: return None
    if roe >= 30: return 100
    if roe >= 20: return 85
    if roe >= 15: return 75
    if roe >= 10: return 60
    if roe >= 5: return 40
    if roe > 0: return 25
    return 10


def faaliyet_marji_hesapla(faaliyet_kari, hasilat):
    x = safe_div(faaliyet_kari, hasilat)
    return None if x is None else x * 100


def faaliyet_marji_mutlak_skoru(m):
    if m is None: return None
    if m >= 20: return 100
    if m >= 15: return 90
    if m >= 10: return 80
    if m >= 7.5: return 70
    if m >= 5: return 60
    if m >= 3: return 50
    if m >= 1: return 40
    if m > 0: return 30
    return 10


def marj_trend_skoru(current_margin, comparison_margin):
    if current_margin is None or comparison_margin is None:
        return None
    d = current_margin - comparison_margin
    if d >= 5: return 100
    if d >= 3: return 90
    if d >= 1: return 75
    if d >= 0: return 60
    if d >= -1: return 45
    if d >= -3: return 25
    return 10


def faaliyet_marji_skoru(current_margin, comparison_margin):
    absolute = faaliyet_marji_mutlak_skoru(current_margin)
    trend = marj_trend_skoru(current_margin, comparison_margin)
    if absolute is None: return None
    if trend is None: return absolute
    return absolute * .70 + trend * .30


def karsilastirmali_degisim(current, comparison):
    """Current report vs its own TMS29-consistent comparative column."""
    if current is None or comparison is None or comparison <= 0:
        return None
    return (current / comparison - 1) * 100


def buyume_skoru(g):
    if g is None: return None
    if g >= 30: return 100
    if g >= 20: return 90
    if g >= 10: return 80
    if g >= 5: return 70
    if g >= 0: return 60
    if g >= -5: return 50
    if g >= -10: return 40
    if g >= -20: return 25
    return 10


def kar_degisim_skoru(current, comparison):
    if current is None or comparison is None:
        return None
    if comparison < 0 < current: return 90
    if comparison > 0 > current: return 10
    if comparison < 0 and current < 0:
        old_loss, new_loss = abs(comparison), abs(current)
        if old_loss == 0: return 10
        improvement = (old_loss - new_loss) / old_loss * 100
        if improvement >= 50: return 85
        if improvement >= 20: return 70
        if improvement >= 0: return 55
        if improvement >= -25: return 30
        return 10
    return buyume_skoru(karsilastirmali_degisim(current, comparison))


def net_borc_ozkaynak_skoru(r):
    if r is None: return None
    if r < 0: return 100
    if r < .25: return 90
    if r < .50: return 80
    if r < .75: return 65
    if r < 1.00: return 50
    if r < 1.50: return 30
    return 10


def implied_net_borc_favok_hesapla(net_borc, equity, pddd, fd_favok):
    if None in (net_borc, equity, pddd, fd_favok): return None
    if equity <= 0 or pddd <= 0 or fd_favok <= 0: return None
    market_cap = equity * pddd
    ev = market_cap + net_borc
    if ev <= 0: return None
    implied_ebitda = ev / fd_favok
    return None if implied_ebitda <= 0 else net_borc / implied_ebitda


def _annualization_factor(period_text):
    p = _norm_text(period_text)
    if "3 ayl" in p: return 4.0
    if "6 ayl" in p: return 2.0
    if "9 ayl" in p: return 4.0 / 3.0
    if "yillik" in p or "12 ayl" in p: return 1.0
    return None


def kap_net_borc_favok_hesapla(net_borc, current, current_period):
    """KAP-based annualized EBITDA proxy.

    EBITDA proxy = operating profit + abs(depreciation/amortization).
    The cumulative period is annualized according to 3M/6M/9M/12M.
    This is used only when KAP provides a usable depreciation/amortization line.
    """
    if net_borc is None:
        return None
    op = current.get("faaliyet_kari")
    da = current.get("amortisman_itfa")
    factor = _annualization_factor(current_period)
    if op is None or da is None or factor is None:
        return None
    ebitda_period = float(op) + abs(float(da))
    if ebitda_period <= 0:
        return None
    annualized = ebitda_period * factor
    return None if annualized <= 0 else float(net_borc) / annualized


def net_borc_favok_skoru(r):
    if r is None: return None
    if r < 0: return 100
    if r < 1: return 90
    if r < 2: return 75
    if r < 3: return 55
    if r < 4: return 30
    return 10


def factor_score(items):
    num = den = 0.0
    for s, w in items:
        if s is None or w <= 0:
            continue
        num += s * w
        den += w
    return None if den == 0 else num / den


def _completion(items):
    total = sum(w for _, w in items)
    if total <= 0: return 0.0
    return sum(w for s, w in items if s is not None) / total * 100


def value_trap_degerlendir(valuation_score, quality_score, growth_score):
    if valuation_score is None:
        return "Yok", None
    if valuation_score >= 80 and quality_score is not None and growth_score is not None:
        if quality_score < 30 and growth_score < 30:
            return "Yüksek", "Ucuz değerleme; ancak kalite ve büyüme aynı anda çok zayıf."
        if quality_score < 40 or growth_score < 30:
            return "Orta", "Ucuz değerleme; ancak kalite veya büyümede belirgin bozulma var."
    return "Yok", None


def fss_v3_hesapla(hisse, kap_data=None, is_data=None):
    hisse = hisse.upper().strip()
    kap = kap_data if kap_data is not None else fss_v2_veri_paketi(hisse)
    isd = is_data if is_data is not None else isyatirim_hisse_analizi(hisse)

    current = kap["current"]
    comparison = kap.get("comparison") or kap.get("previous_same", {})
    previous_same = kap.get("previous_same", {})
    company = isd["company"]
    sector = isd["sector"]
    discount = isd["prim_iskonto"]

    # ---- Valuation, sector-sensitive weights ----
    fk_score = degerleme_skoru(discount.get("fk"))
    fd_favok_score = degerleme_skoru(discount.get("fd_favok"))
    pddd_score = degerleme_skoru(discount.get("pddd"))
    fd_satislar_score = degerleme_skoru(discount.get("fd_satislar"))
    valuation_profile, vw = sektor_degerleme_profili(isd.get("sektor"))
    valuation_items = [
        (fk_score, vw["fk"]),
        (fd_favok_score, vw["fd_favok"]),
        (pddd_score, vw["pddd"]),
        (fd_satislar_score, vw["fd_satislar"]),
    ]
    valuation_score_raw = factor_score(valuation_items)
    valuation_weight_total = sum(w for _, w in valuation_items if w > 0)
    valuation_weight_available = sum(w for sc, w in valuation_items if w > 0 and sc is not None)
    valuation_coverage = 0.0 if valuation_weight_total <= 0 else valuation_weight_available / valuation_weight_total
    valuation_score = valuation_score_raw
    # Eksik çarpanların kalan ağırlıkları otomatik 100'e taşımasını engelle.
    if valuation_score is not None:
        if valuation_coverage < .50:
            valuation_score = min(valuation_score, 60.0)
        elif valuation_coverage < .75:
            valuation_score = min(valuation_score, 80.0)
        elif valuation_coverage < 1.0:
            valuation_score = min(valuation_score, 90.0)

    # ---- Quality ----
    previous_equity = previous_same.get("ozkaynak")
    roe = roe_hesapla(current.get("net_kar"), current.get("ozkaynak"), previous_equity)
    roe_score = roe_skoru(roe)
    current_margin = faaliyet_marji_hesapla(current.get("faaliyet_kari"), current.get("hasilat"))
    comparison_margin = faaliyet_marji_hesapla(comparison.get("faaliyet_kari"), comparison.get("hasilat"))
    margin_score = faaliyet_marji_skoru(current_margin, comparison_margin)
    quality_score = factor_score([(roe_score, .15), (margin_score, .10)])

    # ---- Growth ----
    sales_change = karsilastirmali_degisim(current.get("hasilat"), comparison.get("hasilat"))
    sales_score = buyume_skoru(sales_change)
    op_score = kar_degisim_skoru(current.get("faaliyet_kari"), comparison.get("faaliyet_kari"))
    np_score = kar_degisim_skoru(current.get("net_kar"), comparison.get("net_kar"))
    growth_score = factor_score([(sales_score, .08), (op_score, .09), (np_score, .08)])

    # ---- Financial health ----
    net_debt = kap.get("net_borc")
    equity = current.get("ozkaynak")
    nde = safe_div(net_debt, equity)
    nde_score = net_borc_ozkaynak_skoru(nde)

    nd_favok = kap_net_borc_favok_hesapla(net_debt, current, kap.get("current_period"))
    nd_favok_source = "kap_yilliklandirilmis_favok_yaklasimi"
    if nd_favok is None:
        nd_favok = implied_net_borc_favok_hesapla(net_debt, equity, company.get("pddd"), company.get("fd_favok"))
        nd_favok_source = "is_yatirim_implied_fallback"
    nd_favok_score = net_borc_favok_skoru(nd_favok)
    health_score = factor_score([(nd_favok_score, .15), (nde_score, .10)])

    mains = [(valuation_score, .25), (quality_score, .25), (growth_score, .25), (health_score, .25)]
    fss_raw = factor_score(mains)
    completion = _completion(mains)

    # ---- Financial-data safety gate ----
    # Kritik parser/olcek anomalisi veya eski finansal rapor varsa FSS'yi
    # guncel karar skoruna sokma. Ham skor tani/inceleme amaciyla korunur.
    data_quality_severity = kap.get("data_quality_severity", "ok")
    data_quality_flags = list(kap.get("data_quality_flags") or [])
    stale_fallback = bool(kap.get("stale_fallback"))
    # Kalite ana faktörü hesaplanamıyorsa temel finansal veri seti karar skoru
    # üretmek için yeterli değildir. Özellikle faaliyet kârı / net kâr satırları
    # eksik olduğunda %75 tamamlanmış bir FSS'yi "Güçlü" gibi göstermek yanıltıcı
    # olabilir. Ham skor inceleme amacıyla korunur, karar skoru kapatılır.
    critical_factor_missing = quality_score is None

    score_usable = (
        not stale_fallback
        and data_quality_severity != "critical"
        and not critical_factor_missing
    )
    gate_reason = None
    if stale_fallback:
        gate_reason = "stale_financials"
    elif data_quality_severity == "critical":
        gate_reason = "critical_financial_data_quality"
    elif critical_factor_missing:
        gate_reason = "critical_quality_factor_missing"

    fss = fss_raw if score_usable else None

    if not score_usable and gate_reason == "stale_financials":
        label = "Eski Veri"
    elif not score_usable:
        label = "Veri Güvenilmez"
    elif fss is None: label = "Eksik"
    elif fss >= 80: label = "Çok Güçlü"
    elif fss >= 70: label = "Güçlü"
    elif fss >= 60: label = "Pozitif"
    elif fss >= 50: label = "Nötr"
    elif fss >= 40: label = "Zayıf"
    else: label = "Çok Zayıf"

    if score_usable:
        value_trap, value_trap_note = value_trap_degerlendir(valuation_score, quality_score, growth_score)
    else:
        value_trap, value_trap_note = "Yok", None

    return {
        "hisse": hisse,
        "sektor": isd.get("sektor"),
        "FSS_V3": None if fss is None else round(fss, 2),
        "FSS_V3_RAW": None if fss_raw is None else round(fss_raw, 2),
        "FSS_VERSION": "3.1.3",
        "score_usable": score_usable,
        "score_gate_reason": gate_reason,
        "data_quality_severity": data_quality_severity,
        "data_quality_flags": data_quality_flags,
        "etiket": label,
        "tamamlanma": round(completion, 2),
        "comparison_source": kap.get("comparison_source"),
        "valuation_score": valuation_score,
        "valuation_score_raw": valuation_score_raw,
        "valuation_coverage": round(valuation_coverage * 100, 1),
        "quality_score": quality_score,
        "growth_score": growth_score,
        "financial_health_score": health_score,
        "valuation_profile": valuation_profile,
        "valuation_weights": vw,
        "value_trap_risk": value_trap,
        "value_trap_note": value_trap_note,
        "fk": company.get("fk"), "sector_fk": sector.get("fk"), "fk_discount": discount.get("fk"), "fk_score": fk_score,
        "fd_favok": company.get("fd_favok"), "sector_fd_favok": sector.get("fd_favok"), "fd_favok_discount": discount.get("fd_favok"), "fd_favok_score": fd_favok_score,
        "pddd": company.get("pddd"), "sector_pddd": sector.get("pddd"), "pddd_discount": discount.get("pddd"), "pddd_score": pddd_score,
        "fd_satislar": company.get("fd_satislar"), "sector_fd_satislar": sector.get("fd_satislar"), "fd_satislar_discount": discount.get("fd_satislar"), "fd_satislar_score": fd_satislar_score,
        "roe": roe, "roe_score": roe_score,
        "faaliyet_marji": current_margin, "karsilastirma_faaliyet_marji": comparison_margin, "faaliyet_marji_score": margin_score,
        "hasilat_degisim": sales_change, "hasilat_degisim_score": sales_score,
        "faaliyet_buyume_score": op_score, "net_kar_buyume_score": np_score,
        "net_borc": net_debt, "net_borc_ozkaynak": nde, "net_borc_ozkaynak_score": nde_score,
        "net_borc_favok": nd_favok, "net_borc_favok_source": nd_favok_source, "net_borc_favok_score": nd_favok_score,
        # backward compatibility
        "implied_net_borc_favok": nd_favok,
        "kap": kap,
        "isyatirim": isd,
    }


if __name__ == "__main__":
    for h in ["FROTO", "TOASO", "TTRAK", "TUPRS"]:
        try:
            x = fss_v3_hesapla(h)
            print(h, x["FSS_V3"], x["etiket"], x["valuation_score"], x["quality_score"], x["growth_score"], x["financial_health_score"], x["value_trap_risk"], x["net_borc_favok_source"])
        except Exception as e:
            print(h, type(e).__name__, e)
