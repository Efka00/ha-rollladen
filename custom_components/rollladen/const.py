"""Konstanten der Integration Rollladen."""

DOMAIN = "rollladen"

# Rollläden in den Optionen der Anlage: {rollladen_id: {...Einstellungen}}
CONF_ROLLLAEDEN = "rolllaeden"

# ---- Anlage (Optionen des Config-Eintrags) ---------------------------
CONF_LUX_SENSOR = "lux_sensor"
CONF_ANWESENHEIT = "anwesenheit"
CONF_TEMPERATUR = "temperatur"
CONF_BESCHATTUNG_POS = "beschattung_pos"
CONF_MIN_ELEVATION = "min_elevation"
CONF_MIN_TEMP = "min_temp"
CONF_SONNIG = "sonnig_lux"
CONF_BEWOELKT = "bewoelkt_lux"
CONF_WARTEZEIT = "beschattung_wartezeit"
CONF_LUX_MITTEL = "lux_mittel"
CONF_FROST_POS = "frost_pos"
CONF_FROST_HYSTERESE = "frost_hysterese"
CONF_FROST_STUNDEN = "frost_stunden"
CONF_NIEDERSCHLAG = "niederschlag"
CONF_FEUCHTE = "feuchte"
CONF_FEUCHTE_SCHWELLE = "feuchte_schwelle"
CONF_WETTER = "wetter"
CONF_NOTIFY = "notify_dienst"

ANLAGE_DEFAULTS = {
    CONF_BESCHATTUNG_POS: 40,
    CONF_MIN_ELEVATION: 20,
    CONF_MIN_TEMP: 18,
    CONF_SONNIG: 30000,
    CONF_BEWOELKT: 15000,
    CONF_WARTEZEIT: 10,        # Minuten
    CONF_LUX_MITTEL: 5,        # Minuten, 0 = letzter Wert
    CONF_FROST_POS: 10,
    CONF_FROST_HYSTERESE: 1.0,
    CONF_FROST_STUNDEN: 24,
    CONF_FEUCHTE_SCHWELLE: 90,
}

# ---- Rollladen (Einstellungen aus dem Dialog) -------------------------
CONF_NAME = "name"
CONF_COVER = "cover"
CONF_TASTER = "taster"
CONF_TASTER_KURZ = "taster_kurz"
CONF_TASTER_LANG = "taster_lang"
CONF_GRIFF = "griff"
CONF_TUER = "tuer"
CONF_GEKIPPT_POS = "gekippt_pos"
CONF_GRIFF_OFFEN_POS = "griff_offen_pos"
CONF_AZIMUT_VON = "azimut_von"
CONF_AZIMUT_BIS = "azimut_bis"
CONF_SPERRE_MIN = "sperre_minuten"
CONF_BLOCK_MORGEN = "block_morgen_minuten"
CONF_BLOCK_ABEND = "block_abend_minuten"
CONF_FROSTSCHUTZ = "frostschutz"

ROLLLADEN_DEFAULTS = {
    CONF_TASTER_KURZ: "press_short",
    CONF_TASTER_LANG: "press_long",
    CONF_TUER: False,
    CONF_GEKIPPT_POS: 25,
    CONF_GRIFF_OFFEN_POS: 80,
    CONF_SPERRE_MIN: 120,
    CONF_BLOCK_MORGEN: 60,
    CONF_BLOCK_ABEND: 60,
    CONF_FROSTSCHUTZ: True,
}

# Anlagenwerte, die über Entities verstellt werden (gespeichert).
ANLAGE_SPEICHER_DEFAULTS = {
    "automatik": False,        # startet bei Neuinstallation AUS
    "beschattung": False,
    "frostschutz": False,
    "lux_hoch": 700.0,
    "lux_runter": 600.0,
    "frost_schwelle": 1.5,
}

# Zykluszeit und Startverzögerung in Sekunden (fest).
ZYKLUS_SEKUNDEN = 60
# Fällt der Helligkeitssensor länger aus, gilt „kein Wert“ (Ersatz: Astro).
LUX_AUSFALL_SEKUNDEN = 900
START_VERZOEGERUNG = 10

# Abstand zwischen zwei Automatik-Fahrten in Sekunden, damit nicht alle
# Motoren gleichzeitig anlaufen (Bus, Anlaufstrom). Taster fahren sofort.
FAHR_ABSTAND = 1.5

# Optionen, die auf Entities verweisen (Umbenennen folgen, Fehlende melden).
ENTITY_KEYS_ANLAGE = (CONF_LUX_SENSOR, CONF_ANWESENHEIT, CONF_TEMPERATUR,
                      CONF_NIEDERSCHLAG, CONF_FEUCHTE, CONF_WETTER)
ENTITY_KEYS_ROLLLADEN = (CONF_COVER, CONF_GRIFF, CONF_TASTER)
