import pandas as pd
import streamlit as st

from fss_v3_engine import fss_v3_hesapla
from tas_engine import tas_hesapla
from universe import HISSELER, evren_kontrolu

st.set_page_config(page_title="BİST AI- Oğuzhan Özbudak", page_icon="📊", layout="wide")

evren_kontrolu()

def para(v):
    if v is None: return "-"
    if abs(v) >= 1_000_000_000: return f"{v/1_000_000_000:,.2f} mlr TL"
    if abs(v) >= 1_000_000: return f"{v/1_000_000:,.2f} mn TL"
    return f"{v:,.0f} TL"


def pct(v): return "-" if v is None else f"%{v:.2f}"
def xx(v): return "-" if v is None else f"{v:.2f}x"
def score(v): return "-" if v is None else f"{v:.1f}"


def score_color(v):
    """Kullanıcının skor renk eşikleri: <40 kırmızı, 40-70 sarı, >70 yeşil."""
    if v is None:
        return "#FAFAFA"
    if v < 40:
        return "#ff4b4b"
    if v <= 70:
        return "#f2c94c"
    return "#21c55d"


def score_metric(label, value):
    display = "-" if value is None else f"{value:.1f}/100"
    color = score_color(value)
    st.markdown(
        f"""
        <div class="score-metric">
            <div class="score-metric-label">{label}</div>
            <div class="score-metric-value" style="color:{color};">{display}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    .score-metric { margin-bottom: 0.25rem; }
    .score-metric-label {
        font-size: 0.95rem;
        font-weight: 600;
        line-height: 1.3;
        margin-bottom: 0.35rem;
    }
    .score-metric-value {
        font-size: 2.5rem;
        font-weight: 400;
        line-height: 1.2;
        white-space: nowrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def nd_favok_source_label(src):
    if src == "kap_yilliklandirilmis_favok_yaklasimi":
        return "KAP faaliyet kârı + amortisman/itfa üzerinden yıllıklandırılmış FAVÖK yaklaşımı"
    return "İş Yatırım FD/FAVÖK ve PD/DD çarpanlarından türetilen fallback yaklaşımı"


st.title("📊 BİST AI- Oğuzhan Özbudak")
st.caption("KAP otomatik finansal rapor + İş Yatırım sektör değerleme + teknik analiz")

hisse = st.sidebar.selectbox("Hisse", HISSELER, index=HISSELER.index("TUPRS"))
st.sidebar.caption("Genel skor: %60 FSS + %40 TAS")
st.sidebar.success("50 Hisselik evren aktif.")

if st.button(f"🚀 {hisse} Analizini Çalıştır", use_container_width=True):
    try:
        with st.spinner("KAP, İş Yatırım ve teknik veriler hazırlanıyor..."):
            fss = fss_v3_hesapla(hisse)
            tas = tas_hesapla(hisse)

        fss_score = fss.get("FSS_V3")
        tas_score = tas.get("TAS")
        genel = None if fss_score is None or tas_score is None else fss_score * .60 + tas_score * .40

        c1,c2,c3,c4 = st.columns(4)
        with c1:
            score_metric("GENEL SKOR", genel)
        with c2:
            score_metric("Finansal Sağlık Skoru", fss_score)
        with c3:
            score_metric("Teknik Analiz Skoru", tas_score)
        c4.metric("Son Fiyat", "-" if tas.get("Price") is None else f"{tas['Price']:.2f} TL")

        st.subheader("FSS Ana Faktörler")
        f1,f2,f3,f4 = st.columns(4)
        f1.metric("Değerleme", score(fss.get("valuation_score")))
        f2.metric("Kalite", score(fss.get("quality_score")))
        f3.metric("Büyüme", score(fss.get("growth_score")))
        f4.metric("Finansal Sağlık", score(fss.get("financial_health_score")))
        st.caption(f"FSS etiketi: {fss.get('etiket')} | Veri tamamlanma: %{fss.get('tamamlanma',0):.0f}")
        if not fss.get("score_usable", True):
            raw = fss.get("FSS_V3_RAW")
            reason = fss.get("score_gate_reason")
            if reason == "stale_financials":
                st.error("⛔ FSS güvenlik kapısı aktif: Finansal rapor güncel değil. Ham FSS yalnızca inceleme amaçlıdır; Genel Skor hesabına dahil edilmedi.")
            else:
                st.error("⛔ FSS güvenlik kapısı aktif: Kritik KAP satır/ölçek anomalisi tespit edildi. Finansal skor ve Genel Skor geçersiz sayıldı.")
            if raw is not None:
                st.caption(f"Ham FSS (karar skoruna dahil edilmez): {raw:.1f}/100")
        if fss.get("valuation_coverage", 100) < 100:
            st.info(f"Değerleme veri kapsamı: %{fss.get('valuation_coverage',0):.0f}. Eksik çarpanlar nedeniyle değerleme skoru güvenlik tavanına tabi.")
        for issue in fss.get("kap", {}).get("data_quality_issues", []):
            st.warning("⚠️ Veri kalite kontrolü: " + issue)
        if fss.get("kap", {}).get("stale_fallback"):
            st.warning("⚠️ Cari yıl finansal raporu bulunamadı; en güncel kullanılabilir KAP raporu gösteriliyor. Dönem etiketi ve veri tarihi mutlaka kontrol edilmeli.")

        risk = fss.get("value_trap_risk")
        if risk == "Yüksek":
            st.error(f"⚠️ Value-trap riski: YÜKSEK — {fss.get('value_trap_note')}")
        elif risk == "Orta":
            st.warning(f"⚠️ Value-trap riski: ORTA — {fss.get('value_trap_note')}")

        st.subheader("Değerleme – İş Yatırım sektör karşılaştırması")
        st.caption(
            f"Sektör profili: {fss.get('valuation_profile')} | "
            f"Ağırlıklar: F/K %{fss['valuation_weights']['fk']*100:.0f}, "
            f"FD/FAVÖK %{fss['valuation_weights']['fd_favok']*100:.0f}, "
            f"PD/DD %{fss['valuation_weights']['pddd']*100:.0f}, "
            f"FD/Satış %{fss['valuation_weights']['fd_satislar']*100:.0f}"
        )
        rows = [
            ["F/K", xx(fss.get("fk")), xx(fss.get("sector_fk")), pct(fss.get("fk_discount")), score(fss.get("fk_score"))],
            ["FD/FAVÖK", xx(fss.get("fd_favok")), xx(fss.get("sector_fd_favok")), pct(fss.get("fd_favok_discount")), score(fss.get("fd_favok_score"))],
            ["PD/DD", xx(fss.get("pddd")), xx(fss.get("sector_pddd")), pct(fss.get("pddd_discount")), score(fss.get("pddd_score"))],
        ]
        if fss["valuation_weights"].get("fd_satislar", 0) > 0:
            rows.append(["FD/Satış", xx(fss.get("fd_satislar")), xx(fss.get("sector_fd_satislar")), pct(fss.get("fd_satislar_discount")), score(fss.get("fd_satislar_score"))])
        st.dataframe(pd.DataFrame(rows, columns=["Metrik","Şirket","Sektör","Prim/İskonto","Skor"]), width="stretch", hide_index=True)

        kap = fss["kap"]
        cur = kap["current"]
        comp = kap["comparison"]
        prev = kap["previous_same"]

        st.subheader("KAP finansalları")
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("Hasılat", para(cur.get("hasilat")))
        k2.metric("Net Kâr", para(cur.get("net_kar")))
        k3.metric("Faaliyet Kârı", para(cur.get("faaliyet_kari")))
        k4.metric("Özkaynak", para(cur.get("ozkaynak")))

        st.caption(
            f"Cari KAP: {kap.get('current_year')} {kap.get('current_period')} / Bildirim {kap.get('bildirim_id')} | "
            "Akış karşılaştırmaları cari raporun kendi karşılaştırmalı sütunundan alınır; ikinci TÜFE düzeltmesi uygulanmaz."
        )

        growth_df = pd.DataFrame([
            ["Hasılat", para(cur.get("hasilat")), para(comp.get("hasilat")), pct(fss.get("hasilat_degisim")), score(fss.get("hasilat_degisim_score"))],
            ["Faaliyet Kârı", para(cur.get("faaliyet_kari")), para(comp.get("faaliyet_kari")), "-", score(fss.get("faaliyet_buyume_score"))],
            ["Net Kâr", para(cur.get("net_kar")), para(comp.get("net_kar")), "-", score(fss.get("net_kar_buyume_score"))],
        ], columns=["Metrik","Cari","Karşılaştırmalı","Değişim","Skor"])
        st.dataframe(growth_df, width="stretch", hide_index=True)

        q1,q2,q3,q4 = st.columns(4)
        q1.metric("ROE (H1 yıllıklandırılmış)", pct(fss.get("roe")))
        q2.metric("Faaliyet Marjı", pct(fss.get("faaliyet_marji")))
        q3.metric("Net Borç / Özkaynak", xx(fss.get("net_borc_ozkaynak")))
        q4.metric("Net Borç / FAVÖK", xx(fss.get("net_borc_favok")))
        st.caption("Net Borç/FAVÖK kaynağı: " + nd_favok_source_label(fss.get("net_borc_favok_source")))

        with st.expander("Borç ve FAVÖK detayı"):
            debt_df = pd.DataFrame([
                ["Nakit", para(cur.get("nakit"))],
                ["Kısa vadeli borçlanmalar", para(cur.get("kv_borc"))],
                ["UV borcun kısa kısmı", para(cur.get("uv_kisa"))],
                ["Uzun vadeli borçlanmalar", para(cur.get("uv_borc"))],
                ["Finansal borç", para(kap.get("finansal_borc"))],
                ["Net borç", para(kap.get("net_borc"))],
                ["Amortisman/itfa (KAP, varsa)", para(cur.get("amortisman_itfa"))],
                ["Önceki aynı dönem özkaynak", para((prev or {}).get("ozkaynak"))],
            ], columns=["Kalem","Değer"])
            st.dataframe(debt_df, width="stretch", hide_index=True)

        st.subheader("Teknik analiz – TAS V2")
        t1,t2,t3,t4,t5 = st.columns(5)
        t1.metric("TAS", f"{tas_score:.1f}/100")
        t2.metric("Destek", "-" if tas.get("Destek") is None else f"{tas['Destek']:.2f} TL")
        t3.metric("Direnç", "-" if tas.get("Direnc") is None else f"{tas['Direnc']:.2f} TL")
        t4.metric("RSI(14)", "-" if tas.get("RSI14") is None else f"{tas['RSI14']:.1f}")
        t5.metric("Risk/Reward", "-" if tas.get("RiskReward") is None else f"{tas['RiskReward']:.2f}")
        rr = tas.get("RiskReward")
        if rr is not None and rr < 0.25 and tas_score >= 65:
            st.warning("⚠️ TAS yüksek olsa da fiyat mevcut dirence çok yakın; Risk/Reward çok düşük.")
        elif rr is not None and rr >= 5 and tas_score < 55:
            st.info("ℹ️ Risk/Reward yüksek, ancak TAS zayıf. Destek yakınlığı tek başına teknik teyit değildir.")

        with st.expander("Teknik detay"):
            td = pd.DataFrame([
                ["MA20", tas.get("MA20")], ["MA50", tas.get("MA50")], ["MA200", tas.get("MA200")],
                ["RSI14", tas.get("RSI14")], ["RVOL20", tas.get("RVOL20")], ["NATR14", tas.get("NATR14")],
                ["Trend", tas.get("Trend")],
            ], columns=["Gösterge","Değer"])
            st.dataframe(td, width="stretch", hide_index=True)

        if fss.get("score_usable", True):
            st.success("✅ KAP + İş Yatırım + FSS V3.1.3 + TAS V2 zinciri tamamlandı.")
        else:
            st.info("ℹ️ Veri zinciri tamamlandı; ancak FSS güvenlik kapısı nedeniyle Genel Skor üretilmedi.")
        st.caption("Bu panel karar destek aracıdır; otomatik al/sat sistemi değildir.")

    except Exception as e:
        st.error(f"Analiz sırasında hata oluştu: {type(e).__name__}: {e}")
