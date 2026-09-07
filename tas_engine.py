# ============================================================
# BIST AI - TAS V2
# GENEL TEKNİK ANALİZ MOTORU
#
# Desteklenen:
#   FROTO
#   TOASO
#   TTRAK
#   ve genel olarak Yahoo Finance'ta bulunan BIST hisseleri
#
# TAS ağırlıkları:
#   Fiyat Yapısı / Destek-Direnç   %30
#   MA20 / MA50 / MA200            %25
#   RSI(14)                        %20
#   Hacim / RVOL20                 %15
#   ATR(14)                        %10
# ============================================================


import math
import pandas as pd
import numpy as np
import yfinance as yf


# ============================================================
# TICKER
# ============================================================

def yahoo_ticker(hisse):

    hisse = (
        hisse
        .upper()
        .strip()
    )

    # Kullanıcı zaten .IS girdiyse tekrar ekleme
    if hisse.endswith(".IS"):
        return hisse

    return f"{hisse}.IS"


# ============================================================
# VERİ GETİR
# ============================================================

def fiyat_verisi_getir(
    hisse,
    period="1y"
):

    ticker = yahoo_ticker(
        hisse
    )

    df = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if (
        df is None
        or df.empty
    ):

        # İlk deneme başarısızsa daha uzun dönem
        df = yf.download(
            ticker,
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

    if (
        df is None
        or df.empty
    ):

        raise ValueError(
            f"{hisse} için fiyat verisi bulunamadı."
        )


    # ========================================================
    # MULTIINDEX DÜZELT
    # ========================================================

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = [
            col[0]
            if isinstance(
                col,
                tuple
            )
            else col
            for col in df.columns
        ]


    # ========================================================
    # GEREKLİ KOLONLAR
    # ========================================================

    gerekli = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for col in gerekli:

        if col not in df.columns:

            raise ValueError(
                f"{hisse} fiyat verisinde "
                f"{col} kolonu bulunamadı."
            )


    # Sayısal dönüşüm
    for col in gerekli:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


    df = (
        df
        .dropna(
            subset=[
                "High",
                "Low",
                "Close",
            ]
        )
        .copy()
    )


    if len(df) < 30:

        raise ValueError(
            f"{hisse} için yeterli fiyat geçmişi yok."
        )


    return df


# ============================================================
# RSI
# ============================================================

def rsi_hesapla(
    close,
    period=14
):

    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = (
        -delta.clip(
            upper=0
        )
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = (
        avg_gain
        / avg_loss.replace(
            0,
            np.nan
        )
    )

    rsi = (
        100
        - (
            100
            / (
                1 + rs
            )
        )
    )

    # Hiç kayıp yoksa RSI 100
    rsi = rsi.fillna(
        100
    )

    return rsi


# ============================================================
# ATR
# ============================================================

def atr_hesapla(
    df,
    period=14
):

    previous_close = (
        df["Close"]
        .shift(1)
    )

    tr1 = (
        df["High"]
        - df["Low"]
    )

    tr2 = (
        df["High"]
        - previous_close
    ).abs()

    tr3 = (
        df["Low"]
        - previous_close
    ).abs()

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3,
        ],
        axis=1,
    ).max(
        axis=1
    )

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return atr


# ============================================================
# RSI SKORU
# ============================================================

def rsi_skoru(
    rsi
):

    if rsi is None:
        return 50

    # Güçlü fakat aşırı alım değil
    if 55 <= rsi <= 70:
        return 100

    if 50 <= rsi < 55:
        return 85

    if 40 <= rsi < 50:
        return 65

    if 30 <= rsi < 40:
        return 50

    # Aşırı satım - tepki ihtimali var ama trend zayıf
    if rsi < 30:
        return 40

    # 70-75 hâlâ güçlü
    if 70 < rsi <= 75:
        return 80

    # Aşırı alım
    return 60


# ============================================================
# MA SKORU
# ============================================================

def ma_skoru(
    price,
    ma20,
    ma50,
    ma200
):

    score = 0

    # Fiyat konumu
    if (
        ma20 is not None
        and price > ma20
    ):
        score += 25

    if (
        ma50 is not None
        and price > ma50
    ):
        score += 25

    if (
        ma200 is not None
        and price > ma200
    ):
        score += 25


    # Ortalama sıralaması
    if (
        ma20 is not None
        and ma50 is not None
        and ma200 is not None
        and ma20 > ma50 > ma200
    ):

        score += 25

    elif (
        ma20 is not None
        and ma50 is not None
        and ma20 > ma50
    ):

        score += 15

    elif (
        ma50 is not None
        and ma200 is not None
        and ma50 > ma200
    ):

        score += 10


    return min(
        score,
        100
    )


# ============================================================
# HACİM SKORU
# ============================================================

def hacim_skoru(
    rvol
):

    if rvol is None:
        return 50

    if rvol >= 2.0:
        return 100

    if rvol >= 1.50:
        return 90

    if rvol >= 1.20:
        return 80

    if rvol >= 1.00:
        return 70

    if rvol >= 0.80:
        return 60

    if rvol >= 0.60:
        return 50

    return 40


# ============================================================
# ATR SKORU
# ============================================================

def atr_skoru(
    natr
):

    if natr is None:
        return 50

    # Dengeli volatilite
    if 1.5 <= natr <= 3.5:
        return 100

    if 1.0 <= natr < 1.5:
        return 90

    if 3.5 < natr <= 5.0:
        return 85

    if 0.5 <= natr < 1.0:
        return 75

    if 5.0 < natr <= 7.0:
        return 65

    if natr > 7.0:
        return 45

    return 60


# ============================================================
# DESTEK / DİRENÇ
# ============================================================

def destek_direnc_hesapla(
    df,
    lookback=60
):

    work = (
        df.tail(
            lookback
        )
        .copy()
    )

    current = float(
        work["Close"]
        .iloc[-1]
    )


    # ========================================================
    # PIVOT LOW / HIGH
    # ========================================================

    lows = work["Low"]

    highs = work["High"]


    pivot_low = (
        (lows < lows.shift(1))
        & (lows <= lows.shift(2))
        & (lows < lows.shift(-1))
        & (lows <= lows.shift(-2))
    )


    pivot_high = (
        (highs > highs.shift(1))
        & (highs >= highs.shift(2))
        & (highs > highs.shift(-1))
        & (highs >= highs.shift(-2))
    )


    supports = (
        lows[
            pivot_low
        ]
        .dropna()
        .tolist()
    )

    resistances = (
        highs[
            pivot_high
        ]
        .dropna()
        .tolist()
    )


    supports = [
        float(x)
        for x in supports
        if float(x) < current
    ]


    resistances = [
        float(x)
        for x in resistances
        if float(x) > current
    ]


    # ========================================================
    # DESTEK
    # ========================================================

    if supports:

        support = max(
            supports
        )

    else:

        support = float(
            work["Low"]
            .tail(20)
            .min()
        )


    # ========================================================
    # DİRENÇ
    # ========================================================

    if resistances:

        resistance = min(
            resistances
        )

    else:

        resistance = float(
            work["High"]
            .tail(20)
            .max()
        )


    return (
        support,
        resistance
    )


# ============================================================
# TREND
# ============================================================

def trend_hesapla(
    df
):

    work = (
        df
        .tail(60)
        .copy()
    )

    first_half = (
        work.iloc[
            :30
        ]
    )

    second_half = (
        work.iloc[
            -30:
        ]
    )


    high_old = float(
        first_half[
            "High"
        ].max()
    )

    high_new = float(
        second_half[
            "High"
        ].max()
    )

    low_old = float(
        first_half[
            "Low"
        ].min()
    )

    low_new = float(
        second_half[
            "Low"
        ].min()
    )


    if (
        high_new > high_old
        and low_new > low_old
    ):

        return (
            "Higher High + Higher Low",
            100
        )


    if (
        high_new < high_old
        and low_new < low_old
    ):

        return (
            "Lower High + Lower Low",
            20
        )


    if (
        high_new > high_old
        or low_new > low_old
    ):

        return (
            "Kısmi Pozitif",
            70
        )


    return (
        "Yatay / Kararsız",
        50
    )


# ============================================================
# FİYAT YAPISI SKORU
# ============================================================

def fiyat_yapisi_skoru(
    price,
    support,
    resistance,
    trend_score
):

    # ========================================================
    # RISK / REWARD
    # ========================================================

    downside = (
        price
        - support
    )

    upside = (
        resistance
        - price
    )


    if (
        downside > 0
        and upside > 0
    ):

        rr = (
            upside
            / downside
        )

    else:

        rr = None


    # ========================================================
    # RR SKOR
    # ========================================================

    if rr is None:
        rr_score = 50

    elif rr >= 3:
        rr_score = 100

    elif rr >= 2:
        rr_score = 85

    elif rr >= 1.5:
        rr_score = 70

    elif rr >= 1:
        rr_score = 50

    elif rr >= 0.5:
        rr_score = 30

    else:
        rr_score = 10


    # ========================================================
    # BREAKOUT SKOR
    # ========================================================

    if price > resistance:

        breakout_score = 100

    elif (
        resistance > 0
        and price
        >= resistance * 0.98
    ):

        breakout_score = 75

    else:

        breakout_score = 50


    # ========================================================
    # FİYAT YAPISI
    # ========================================================

    score = (
        trend_score * 0.50
        + rr_score * 0.30
        + breakout_score * 0.20
    )


    return (
        round(
            score,
            1
        ),
        rr,
        rr_score,
        breakout_score,
    )


# ============================================================
# ANA TAS MOTORU
# ============================================================

def tas_hesapla(
    hisse
):

    hisse = (
        hisse
        .upper()
        .strip()
    )


    # ========================================================
    # VERİ
    # ========================================================

    df = fiyat_verisi_getir(
        hisse,
        period="2y"
    )


    # ========================================================
    # İNDİKATÖRLER
    # ========================================================

    df["MA20"] = (
        df["Close"]
        .rolling(20)
        .mean()
    )

    df["MA50"] = (
        df["Close"]
        .rolling(50)
        .mean()
    )

    df["MA200"] = (
        df["Close"]
        .rolling(200)
        .mean()
    )

    df["RSI14"] = (
        rsi_hesapla(
            df["Close"],
            14
        )
    )

    df["ATR14"] = (
        atr_hesapla(
            df,
            14
        )
    )

    df["VOL20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
    )


    # ========================================================
    # SON SATIR
    # ========================================================

    last = (
        df.iloc[-1]
    )

    price = float(
        last["Close"]
    )


    ma20 = (
        float(
            last["MA20"]
        )
        if pd.notna(
            last["MA20"]
        )
        else None
    )

    ma50 = (
        float(
            last["MA50"]
        )
        if pd.notna(
            last["MA50"]
        )
        else None
    )

    ma200 = (
        float(
            last["MA200"]
        )
        if pd.notna(
            last["MA200"]
        )
        else None
    )

    rsi14 = (
        float(
            last["RSI14"]
        )
        if pd.notna(
            last["RSI14"]
        )
        else None
    )

    atr14 = (
        float(
            last["ATR14"]
        )
        if pd.notna(
            last["ATR14"]
        )
        else None
    )


    # ========================================================
    # RVOL20
    # ========================================================

    current_volume = float(
        last["Volume"]
    )

    avg_volume = (
        float(
            last["VOL20"]
        )
        if pd.notna(
            last["VOL20"]
        )
        else None
    )


    if (
        avg_volume is not None
        and avg_volume > 0
    ):

        rvol20 = (
            current_volume
            / avg_volume
        )

    else:

        rvol20 = None


    # ========================================================
    # NATR
    # ========================================================

    if (
        atr14 is not None
        and price > 0
    ):

        natr14 = (
            atr14
            / price
            * 100
        )

    else:

        natr14 = None


    # ========================================================
    # DESTEK / DİRENÇ
    # ========================================================

    support, resistance = (
        destek_direnc_hesapla(
            df
        )
    )


    # ========================================================
    # TREND
    # ========================================================

    trend_text, trend_score = (
        trend_hesapla(
            df
        )
    )


    # ========================================================
    # FİYAT YAPISI
    # ========================================================

    (
        price_structure_score,
        rr,
        rr_score,
        breakout_score,
    ) = fiyat_yapisi_skoru(
        price,
        support,
        resistance,
        trend_score,
    )


    # ========================================================
    # ALT SKORLAR
    # ========================================================

    ma_score = (
        ma_skoru(
            price,
            ma20,
            ma50,
            ma200,
        )
    )

    rsi_score = (
        rsi_skoru(
            rsi14
        )
    )

    volume_score = (
        hacim_skoru(
            rvol20
        )
    )

    atr_score = (
        atr_skoru(
            natr14
        )
    )


    # ========================================================
    # TAS
    # ========================================================

    tas = (
        price_structure_score * 0.30
        + ma_score * 0.25
        + rsi_score * 0.20
        + volume_score * 0.15
        + atr_score * 0.10
    )


    tas = round(
        tas,
        1
    )


    # ========================================================
    # GÜNLÜK DEĞİŞİM
    # ========================================================

    if len(df) >= 2:

        previous_close = float(
            df["Close"]
            .iloc[-2]
        )

        daily_change = (
            (
                price
                / previous_close
            )
            - 1
        ) * 100

    else:

        daily_change = None


    # ========================================================
    # RETURN
    #
    # Eski app.py ile uyumluluk için mevcut anahtar isimlerini
    # koruyoruz.
    # ========================================================

    return {

        "Hisse":
            hisse,

        "Ticker":
            yahoo_ticker(
                hisse
            ),

        "Price":
            round(
                price,
                2
            ),

        "TAS":
            tas,

        "TAS_V1":
            tas,

        "Score":
            tas,


        # ====================================================
        # ANA PANEL
        # ====================================================

        "Destek":
            round(
                support,
                2
            ),

        "Direnc":
            round(
                resistance,
                2
            ),

        "RSIScore":
            rsi_score,


        # ====================================================
        # ALT SKOR
        # ====================================================

        "PriceStructureScore":
            price_structure_score,

        "MAScore":
            ma_score,

        "RSIScore":
            rsi_score,

        "VolumeScore":
            volume_score,

        "ATRScore":
            atr_score,


        # ====================================================
        # DETAY
        # ====================================================

        "MA20":
            (
                round(
                    ma20,
                    2
                )
                if ma20 is not None
                else None
            ),

        "MA50":
            (
                round(
                    ma50,
                    2
                )
                if ma50 is not None
                else None
            ),

        "MA200":
            (
                round(
                    ma200,
                    2
                )
                if ma200 is not None
                else None
            ),

        "RSI14":
            (
                round(
                    rsi14,
                    2
                )
                if rsi14 is not None
                else None
            ),

        "ATR14":
            (
                round(
                    atr14,
                    4
                )
                if atr14 is not None
                else None
            ),

        "NATR14":
            (
                round(
                    natr14,
                    2
                )
                if natr14 is not None
                else None
            ),

        "RVOL20":
            (
                round(
                    rvol20,
                    2
                )
                if rvol20 is not None
                else None
            ),

        "GunlukDegisim":
            (
                round(
                    daily_change,
                    2
                )
                if daily_change is not None
                else None
            ),


        # ====================================================
        # DESTEK / DİRENÇ DETAY
        # ====================================================

        "Trend":
            trend_text,

        "TrendScore":
            trend_score,

        "RiskReward":
            (
                round(
                    rr,
                    2
                )
                if rr is not None
                else None
            ),

        "RRScore":
            rr_score,

        "BreakoutScore":
            breakout_score,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 80)
    print(
        "BIST AI - TAS V2 MULTI STOCK"
    )
    print("=" * 80)

    for hisse in [
        "FROTO",
        "TOASO",
        "TTRAK",
    ]:

        print()
        print(
            "-" * 80
        )

        try:

            sonuc = (
                tas_hesapla(
                    hisse
                )
            )

            print(
                "Hisse:",
                hisse
            )

            print(
                "Ticker:",
                sonuc[
                    "Ticker"
                ]
            )

            print(
                "Fiyat:",
                sonuc[
                    "Price"
                ]
            )

            print(
                "TAS:",
                sonuc[
                    "TAS"
                ]
            )

            print(
                "Destek:",
                sonuc[
                    "Destek"
                ]
            )

            print(
                "Direnç:",
                sonuc[
                    "Direnc"
                ]
            )

            print(
                "RSI14:",
                sonuc[
                    "RSI14"
                ]
            )

            print(
                "RSI Skoru:",
                sonuc[
                    "RSIScore"
                ]
            )

            print(
                "MA Skoru:",
                sonuc[
                    "MAScore"
                ]
            )

            print(
                "RVOL20:",
                sonuc[
                    "RVOL20"
                ]
            )

            print(
                "NATR14:",
                sonuc[
                    "NATR14"
                ]
            )

            print(
                "Trend:",
                sonuc[
                    "Trend"
                ]
            )

            print(
                "Risk/Reward:",
                sonuc[
                    "RiskReward"
                ]
            )

            print(
                "✅ TAS OK"
            )

        except Exception as e:

            print(
                f"❌ {hisse} HATA:"
            )

            print(
                type(e).__name__,
                str(e)
            )

    print()
    print("=" * 80)
    print(
        "TAS V2 TESTİ TAMAMLANDI"
    )
    print("=" * 80)