# BIST AI - 50 HISSE EVRENI
# Tek kaynak: panel, test ve gelecekteki toplu taramalar bu listeyi kullanir.

HISSELER = [
    "TUPRS", "THYAO", "SISE", "AEFES", "ASELS", "ASTOR", "BIMAS", "EKGYO", "ENKAI", "FROTO",
    "HEKTS", "MGROS", "PETKM", "PGSUS", "SASA", "TAVHL", "TCELL", "TTKOM", "TOASO", "TTRAK",
    "TRALT", "ULKER", "ARDYZ", "BRSAN", "DOAS", "ENJSA", "ALARK", "KAYSE", "BRYAT", "TABGD",
    "SOKM", "EUPWR", "TCKRC", "ATATP", "ARCLK", "KCAER", "KORDS", "AKSA", "KONTR", "MPARK",
    "LILAK", "LKMNH", "AKCNS", "ALFAS", "BIGCH", "DOFRB", "GWIND", "INDES", "KBORU", "MAVI",
]

# Offline back-testte sektor-duyarli degerleme profillerini zorlamak icin yaklasik sektor etiketleri.
# Canli program bu alani kullanmaz; canli sektor bilgisi Is Yatirim'dan gelir.
SEKTOR_TEST_HINT = {
    "TUPRS": "Petrol", "THYAO": "Ulastirma", "SISE": "Sanayi", "AEFES": "Icecek",
    "ASELS": "Teknoloji", "ASTOR": "Elektrik", "BIMAS": "Perakende", "EKGYO": "Gayrimenkul",
    "ENKAI": "Sanayi", "FROTO": "Otomotiv", "HEKTS": "Sanayi", "MGROS": "Perakende",
    "PETKM": "Petrol", "PGSUS": "Ulastirma", "SASA": "Sanayi", "TAVHL": "Ulastirma",
    "TCELL": "Telekom", "TTKOM": "Telekom", "TOASO": "Otomotiv", "TTRAK": "Otomotiv",
    "TRALT": "Madencilik", "ULKER": "Gida", "ARDYZ": "Yazilim", "BRSAN": "Metal",
    "DOAS": "Otomotiv", "ENJSA": "Enerji", "ALARK": "Enerji", "KAYSE": "Gida",
    "BRYAT": "Sanayi", "TABGD": "Gida", "SOKM": "Perakende", "EUPWR": "Elektrik",
    "TCKRC": "Sanayi", "ATATP": "Bilisim", "ARCLK": "Sanayi", "KCAER": "Metal",
    "KORDS": "Sanayi", "AKSA": "Sanayi", "KONTR": "Teknoloji", "MPARK": "Saglik",
    "LILAK": "Sanayi", "LKMNH": "Saglik", "AKCNS": "Sanayi", "ALFAS": "Enerji",
    "BIGCH": "Gida", "DOFRB": "Gida", "GWIND": "Enerji", "INDES": "Bilisim",
    "KBORU": "Sanayi", "MAVI": "Perakende",
}


def evren_kontrolu():
    if len(HISSELER) != 50:
        raise AssertionError(f"Hisse evreni 50 olmali, mevcut: {len(HISSELER)}")
    if len(set(HISSELER)) != len(HISSELER):
        raise AssertionError("Hisse evreninde tekrar eden kod var.")
    for h in HISSELER:
        if h != h.upper() or not h.isalnum():
            raise AssertionError(f"Gecersiz hisse kodu: {h}")
    return True
