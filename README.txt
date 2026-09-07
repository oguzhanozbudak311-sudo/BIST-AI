BIST AI - FINAL 50 / FSS V3.1.1 + TAS V2

Kurulum:
  pip install -r requirements.txt

Calistirma:
  streamlit run app.py

Ana mantik:
  Genel Skor = %60 FSS + %40 TAS
  FSS = Degerleme + Kalite + Buyume + Finansal Saglik
  TAS = fiyat yapisi + hareketli ortalamalar + RSI + hacim + ATR

50 hisse universe.py icindedir.

V3.1.1 guvenlik duzeltmeleri:
- Eksik degerleme carpanlarinda skor sisirmeyi engelleyen kapsam/tavan sistemi.
- Onceki ayni donem KAP raporu yoksa karsilastirmali sutunla devam.
- Cari yil raporu yoksa stale fallback + acik veri tarihi uyarisi.
- KAP satir/olcek anomalileri icin veri kalite uyarilari.
- TAS/Risk-Reward celiskilerinde ek teknik uyarilar.

Onemli:
Bu panel karar destek aracidir. KAP/Is Yatirim/Yahoo gibi canli kaynaklardaki format degisiklikleri veri kalitesini etkileyebilir. Panel supheli veriyi uyarir; kullanici kritik hisselerde kaynak kontrolu yapmalidir.
