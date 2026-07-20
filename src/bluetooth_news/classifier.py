"""Classify articles into tech bucket, vendor (with region), customer, application."""
from __future__ import annotations

import re
from urllib.parse import urlparse

# --- Tech bucket detection ----------------------------------------------
BUCKET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("matter",    re.compile(r"\bmatter(?:\s+1\.\d)?\s+(smart|protocol|spec|casting|over[- ]thread|bridge|device|enabled|certif|ecosystem)|\bmatter\b(?=.*\b(thread|wifi|smart home|bridge|device|spec)\b)", re.I)),
    ("aliro",     re.compile(r"\baliro\b", re.I)),
    ("thread",    re.compile(r"\b(thread (protocol|network|border router|group|stack|1\.\d)|openthread)\b", re.I)),
    ("ieee15_4",  re.compile(r"\b(802\.?15\.?4|ieee[ -]?802\.?15\.?4|zigbee)\b", re.I)),
    ("bluetooth", re.compile(r"\b(bluetooth|ble\b|le audio|auracast|channel sounding|coded phy|bluez|gabeldorsche|nimble|corebluetooth|zephyr (bt|bluetooth)|btstack|gatt\b|a2dp|avrcp|hfp\b|pbap|map profile|hid profile|bap profile|tmap|gmap|hap profile)\b", re.I)),
    ("wifi",      re.compile(r"\b(wi[- ]?fi(?:\s?[678])?|802\.11(ax|be|bn|ah)?|halow|mlo\b)\b", re.I)),
]

BUCKET_LABELS = {
    "wifi":      "Wi-Fi",
    "bluetooth": "Bluetooth",
    "ieee15_4":  "802.15.4 / Zigbee",
    "aliro":     "Aliro",
    "thread":    "Thread",
    "matter":    "Matter",
}


def classify_buckets(text: str, hint: str | None = None) -> list[str]:
    if not text:
        return [hint] if hint else []
    found = [b for b, p in BUCKET_PATTERNS if p.search(text)]
    if hint and hint not in found:
        found.append(hint)
    return found


# --- Standards-body (SDO) news detection --------------------------------
# Articles that originate from an official standards-development organisation
# domain are tagged with the relevant technology family so the News page can
# show spec adoptions / roadmaps / official press releases separate from
# generic coverage. Domain match is authoritative; CSA is an umbrella body so
# its family is resolved from the article text.
STANDARDS_DOMAINS: list[tuple[str, str]] = [
    ("bluetooth.com", "bluetooth"),
    ("bluetooth.org", "bluetooth"),
    ("wi-fi.org", "wifi"),
    ("wifialliance.org", "wifi"),
    ("threadgroup.org", "thread"),
    ("openthread.io", "thread"),
    ("standards.ieee.org", "ieee15_4"),
    ("firaconsortium.org", "aliro"),
    ("csa-iot.org", ""),  # umbrella -> resolve from content
    ("connectivitystandardsalliance.org", ""),
]


def classify_standard(url: str, text: str, buckets: list[str] | None = None) -> str:
    """Return the standards technology family (wifi/bluetooth/ieee15_4/aliro/
    thread/matter) when an article comes from an official standards body,
    else ''."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    low = (text or "").lower()
    for domain, fam in STANDARDS_DOMAINS:
        if host == domain or host.endswith("." + domain):
            if fam:
                return fam
            # CSA umbrella: pick the most specific family from the content.
            if "aliro" in low:
                return "aliro"
            if "thread" in low:
                return "thread"
            if "zigbee" in low or "802.15.4" in low or "15.4" in low:
                return "ieee15_4"
            return "matter"
    return ""


# --- Chip / wireless vendor detection (with region) ---------------------
# Region tags: "americas", "europe", "asia"
VENDORS: list[tuple[str, str, re.Pattern]] = [
    # ---- Americas ----
    ("Qualcomm",     "americas", re.compile(r"\b(qualcomm|qcc[\d]{3,4}|qca[\d]{3,4}|snapdragon( sound)?|fastconnect( ?\d{3,4})?|wcn[\d]{3,4}|ar[\d]{3,4})\b", re.I)),
    ("Broadcom",     "americas", re.compile(r"\b(broadcom|bcm[\d]{3,5}|bcm43[\d]{2,3})\b", re.I)),
    ("TI",           "americas", re.compile(r"\b(texas instruments|\bti\b cc?\d|cc26[\d]{2}|cc23[\d]{2}|cc27[\d]{2}|cc13[\d]{2}|cc33[\d]{2}|cc26x[\d]|simplelink)\b", re.I)),
    ("Silicon Labs", "americas", re.compile(r"\b(silicon ?labs|silabs|efr32(mg|bg|fg|xg|zg)?[\d]{2,3}?|bgm\d|mgm\d|siwx?\d{3,4}|series ?[23])\b", re.I)),
    ("Marvell",      "americas", re.compile(r"\bmarvell( technology)?\b", re.I)),
    ("Microchip",    "americas", re.compile(r"\b(microchip( technology)?|atmel|at\s?bm\d|sam[a-z]\d{2}|wfi32|rn41|rn42|wbz351|pic32cx)\b", re.I)),
    ("Synaptics",    "americas", re.compile(r"\b(synaptics|veros|sybridge|syn4\d{4}|syn43\d{3})\b", re.I)),
    ("Apple",        "americas", re.compile(r"\b(apple silicon|h[12]\s?chip|w\d\s?chip|u[12]\s?chip)\b", re.I)),
    ("Lattice",      "americas", re.compile(r"\b(lattice semi(conductor)?)\b", re.I)),
    ("Onsemi",       "americas", re.compile(r"\b(onsemi|on semiconductor|rsl10)\b", re.I)),
    ("Skyworks",     "americas", re.compile(r"\b(skyworks( solutions)?)\b", re.I)),
    ("Qorvo",        "americas", re.compile(r"\b(qorvo|qpg6\d{3}|qpg7\d{3})\b", re.I)),
    ("Atmosic",      "americas", re.compile(r"\b(atmosic|atm3\d{3}|atm4\d{3})\b", re.I)),
    ("InPlay",       "americas", re.compile(r"\b(inplay (inc|ip\d)|in[a-z]?\d{3,4} ble)\b", re.I)),
    # ---- Europe ----
    ("Nordic",       "europe",   re.compile(r"\b(nordic semi(conductor)?|nrf-?5[234]\d{0,3}|nrf-?7\d{3}|nrf-?91\d{2}|nrf-?54[lh]\d+)\b", re.I)),
    ("NXP",          "europe",   re.compile(r"\b(nxp( semiconductors)?|kw\d{2}|iw\d{3}|jn5\d{3}|rw61[\d]?|mcx[a-z]?\d|mcxw\d|qn90\d{2})\b", re.I)),
    ("Infineon",     "europe",   re.compile(r"\b(infineon|airoc|cyw[\d]{4,5}|psoc \d|psoc[\d ]?6|cypress|merus)\b", re.I)),
    ("STMicro",      "europe",   re.compile(r"\b(stmicro(electronics)?|\bst micro\b|stm32wb[a]?\d{0,3}|bluenrg(-[\w\d]+)?|stm32u\d|stm32l\d)\b", re.I)),
    ("Dialog",       "europe",   re.compile(r"\b(dialog semi(conductor)?)\b", re.I)),
    ("u-blox",       "europe",   re.compile(r"\b(u-?blox|nina-?b\d|nora-?b\d|anna-?b\d)\b", re.I)),
    ("Bosch",        "europe",   re.compile(r"\b(bosch sensortec|bcm150|bme[\d]{3}|bma[\d]{3})\b", re.I)),
    ("Sequans",      "europe",   re.compile(r"\b(sequans|monarch|calliope)\b", re.I)),
    # ---- Asia: China ----
    ("MediaTek",     "asia",     re.compile(r"\b(mediatek|filogic ?\d{2,3}|mt[\d]{3,4}|mt76\d{2}|mt78\d{2}|mt27\d{2}|mt259\d|dimensity)\b", re.I)),
    ("Realtek",      "asia",     re.compile(r"\b(realtek|rtl8\d{3}[a-z]{0,3}|rtl87\d{2}|rtl88\d{2}|rtl89\d{2})\b", re.I)),
    ("Espressif",    "asia",     re.compile(r"\b(espressif|esp32(-[a-z\d]+)?|esp-?h\d|esp-?c\d|esp-?s\d|esp-?p\d|esp8266)\b", re.I)),
    ("Telink",       "asia",     re.compile(r"\b(telink|tlsr\d{4}|tlsr8\d{3}|tlsr9\d{3})\b", re.I)),
    ("Bouffalo Lab", "asia",     re.compile(r"\b(bouffalo|bl60\d|bl61\d|bl70\d|bl80\d|bl61[68]|bl616|bl618|bl808)\b", re.I)),
    ("Beken",        "asia",     re.compile(r"\b(beken|bk72\d{2}|bk32\d{2}|bk78\d{2})\b", re.I)),
    ("Goodix",       "asia",     re.compile(r"\b(goodix|gr551|gr552|gr5526|gr5\d{3})\b", re.I)),
    ("Actions Semi", "asia",     re.compile(r"\b(actions semi|atsv\d|ats29\d|ats30\d|ats31\d)\b", re.I)),
    ("Bestechnic",   "asia",     re.compile(r"\b(bestechnic|bes2\d{3}|bes2700|bes2800)\b", re.I)),
    ("HiSilicon",    "asia",     re.compile(r"\b(hisilicon|kirin|hi36\d{2}|hi11\d{2}|hi[\d]{4} chip)\b", re.I)),
    ("UNISOC",       "asia",     re.compile(r"\b(unisoc|spreadtrum|tiger t\d{3}|uwc\d{4}|ums\d{4})\b", re.I)),
    ("Phyplus",      "asia",     re.compile(r"\b(phyplus|phy62\d{2})\b", re.I)),
    ("Chipsea",      "asia",     re.compile(r"\b(chipsea|chipsen|csb6\d{3}|csb7\d{3})\b", re.I)),
    ("WCH",          "asia",     re.compile(r"\b(wch ?ic|ch579|ch583|ch592|ch32v\d{3})\b", re.I)),
    ("Ingenic",      "asia",     re.compile(r"\b(ingenic|x1000|x2000)\b", re.I)),
    # ---- Asia: Japan / Korea / Taiwan ----
    ("Renesas",      "asia",     re.compile(r"\b(renesas( electronics)?|da14\d{3}|da16\d{3}|smartbond|ra4w\d|ra2|ra6e\d)\b", re.I)),
    ("Sony Semi",    "asia",     re.compile(r"\b(sony semi(conductor)?|altair semi|alt125\d|spresense)\b", re.I)),
    ("Toshiba",      "asia",     re.compile(r"\b(toshiba electronic|tc35\d{3}|tc3567|tz1\d{3})\b", re.I)),
    ("Rohm",         "asia",     re.compile(r"\b(rohm semi(conductor)?|lapis semi)\b", re.I)),
    ("Murata",       "asia",     re.compile(r"\b(murata( manufacturing)?|type[- ]?[12][a-z]{2,3} module)\b", re.I)),
    ("Samsung LSI",  "asia",     re.compile(r"\b(samsung (lsi|system lsi|exynos)|exynos connect|exynos w\d{3}|exynos auto)\b", re.I)),
    ("LG Innotek",   "asia",     re.compile(r"\blg innotek\b", re.I)),
    ("Airoha",       "asia",     re.compile(r"\b(airoha|ab15\d{2}|ab16\d{2})\b", re.I)),
]

REGION_LABELS = {"americas": "Americas", "europe": "European", "asia": "Asian"}

# --- Customers / OEMs ---------------------------------------------------
CUSTOMERS: list[tuple[str, re.Pattern]] = [
    # Big tech / ecosystem owners
    ("Google",     re.compile(r"\b(google|alphabet|nest (cam|hub|thermostat|doorbell|wifi|audio|mini|protect)|fitbit|pixel (watch|buds|tablet|phone)?|chromecast|google home|google tv)\b", re.I)),
    ("Amazon",     re.compile(r"\b(amazon|alexa|amazon alexa|echo (dot|show|studio|hub|pop|spot|frames|auto|plus|buds)?|echo\b|fire tv( stick| cube| omni| soundbar)?|fire (tablet|max|hd|stick)|kindle( scribe| paperwhite)?|ring (camera|doorbell|alarm|cam|stick up|spotlight|floodlight|intercom|chime)|blink (camera|doorbell|mini|outdoor|video|sync module)|eero (pro|6e|6|max|7)?|astro robot|project kuiper|sidewalk)\b", re.I)),
    ("Apple",      re.compile(r"\b(apple|iphone|ipad|airpods( pro| max)?|apple watch|homepod( mini)?|homekit|airtag|vision pro|apple tv|beats (studio|fit|solo|pill|x|flex))\b", re.I)),
    ("Microsoft",  re.compile(r"\b(microsoft|surface(?!\s+pro\s+ai)|xbox|hololens)\b", re.I)),
    ("Meta",       re.compile(r"\b(meta\b|facebook|oculus|ray[- ]ban meta|quest \d|meta quest|orion glasses)\b", re.I)),
    ("Samsung",    re.compile(r"\b(samsung|galaxy (buds|watch|ring|fit|s\d|z fold|z flip|tab)?|smartthings|tizen|harman|jbl (flip|charge|xtreme|go|pulse|clip|partybox|tour|live|tune)|akg)\b", re.I)),
    ("Sony",       re.compile(r"\b(sony|playstation|ps5|wh-?1000|wf-?1000|wh-?ch|linkbuds|inzone|srs-x[bp]?\d*|bravia|ult (wear|tower|field))\b", re.I)),
    ("Bose",       re.compile(r"\b(bose|quietcomfort|soundlink|smart soundbar|bose frames|bose ultra)\b", re.I)),
    ("Sonos",      re.compile(r"\b(sonos|sonos (one|move|roam|arc|beam|ray|era|sub|ace))\b", re.I)),
    ("LG",         re.compile(r"\b(lg electronics|lg thinq|lg oled|lg xboom|tone free|lg gram|lg styler)\b", re.I)),
    ("Xiaomi",     re.compile(r"\b(xiaomi|redmi|poco|mi band|mi smart|mi home)\b", re.I)),
    ("Huawei",     re.compile(r"\b(huawei|honor (band|magic|watch)|huawei freebuds|huawei sound)\b", re.I)),
    # Audio specialists / speaker brands
    ("Sennheiser", re.compile(r"\b(sennheiser|momentum (true|sport|wireless))\b", re.I)),
    ("Bang & Olufsen", re.compile(r"\b(bang ?\& ?olufsen|b&o\b|beoplay|beosound|beolab)\b", re.I)),
    ("Marshall",   re.compile(r"\bmarshall (acton|stanmore|woburn|emberton|willen|kilburn|tufton|major|minor|monitor|motif|middleton)\b", re.I)),
    ("Ultimate Ears", re.compile(r"\b(ultimate ears|ue (boom|megaboom|wonderboom|hyperboom|epicboom|drops))\b", re.I)),
    ("Klipsch",    re.compile(r"\bklipsch\b", re.I)),
    ("Polk Audio", re.compile(r"\bpolk (audio|magnifi|signa|react|atrium)\b", re.I)),
    ("Yamaha",     re.compile(r"\byamaha (musiccast|sound bar|wx|trueX|ysp|yas)\b", re.I)),
    ("Denon",      re.compile(r"\b(denon|home \d{3}|heos)\b", re.I)),
    ("Harman Kardon", re.compile(r"\bharman kardon\b", re.I)),
    # Smart home / camera / security
    ("Arlo",       re.compile(r"\barlo\b", re.I)),
    ("Eve",        re.compile(r"\beve (energy|motion|systems|home|weather|water guard|door)\b", re.I)),
    ("Aqara",      re.compile(r"\baqara\b", re.I)),
    ("Tuya",       re.compile(r"\btuya\b", re.I)),
    ("Philips Hue",re.compile(r"\bphilips hue|signify\b", re.I)),
    ("IKEA",       re.compile(r"\b(ikea|dirigera|tradfri)\b", re.I)),
    ("SwitchBot",  re.compile(r"\bswitchbot\b", re.I)),
    ("Eufy/Anker", re.compile(r"\b(eufy|anker|soundcore)\b", re.I)),
    # Home security specialists
    ("SimpliSafe", re.compile(r"\bsimplisafe\b", re.I)),
    ("Wyze",       re.compile(r"\bwyze (cam|bulb|plug|lock|sense|thermostat|doorbell|watch)?\b", re.I)),
    ("Ecobee",     re.compile(r"\becobee\b", re.I)),
    ("Resideo",    re.compile(r"\b(resideo|honeywell home|honeywell t\d)\b", re.I)),
    ("ADT",        re.compile(r"\badt (security|cam|smart home|self setup)\b", re.I)),
    ("Reolink",    re.compile(r"\breolink\b", re.I)),
    ("Lorex",      re.compile(r"\blorex\b", re.I)),
    ("Swann",      re.compile(r"\bswann (security|cam)\b", re.I)),
    ("Vivint",     re.compile(r"\bvivint\b", re.I)),
    # Wearable / health
    ("Garmin",     re.compile(r"\bgarmin\b", re.I)),
    ("Whoop",      re.compile(r"\bwhoop\b", re.I)),
    ("Oura",       re.compile(r"\boura\b", re.I)),
    ("GoPro",      re.compile(r"\bgopro\b", re.I)),
    ("Motorola",   re.compile(r"\b(motorola|moto (g|e|edge|razr|tag|buds|watch)|lenovo (yoga|thinkpad|tab|smart))\b", re.I)),
    # Automotive
    ("Tesla",      re.compile(r"\btesla\b", re.I)),
    ("BMW",        re.compile(r"\bbmw\b", re.I)),
    ("Mercedes",   re.compile(r"\b(mercedes|daimler)\b", re.I)),
    ("Volkswagen", re.compile(r"\b(volkswagen|vw\b|audi|porsche)\b", re.I)),
    ("Toyota",     re.compile(r"\b(toyota|lexus)\b", re.I)),
    ("HKMC",       re.compile(r"\b(hyundai|kia|genesis motor|hkmc)\b", re.I)),
    ("Ford",       re.compile(r"\bford motor|ford f-?150\b", re.I)),
    ("GM",         re.compile(r"\b(general motors|gm motors|cadillac|chevrolet|chevy bolt)\b", re.I)),
    ("Stellantis", re.compile(r"\b(stellantis|jeep|chrysler|dodge|ram trucks)\b", re.I)),
]

# --- Applications -------------------------------------------------------
APPLICATIONS: list[tuple[str, re.Pattern]] = [
    ("Smart Home",     re.compile(r"\b(smart home|smart lighting|smart lock|smart plug|smart thermostat|home automation)\b", re.I)),
    ("Industrial",     re.compile(r"\b(industrial iot|iiot|industry 4\.0|factory|plc\b|opc[- ]?ua|scada|predictive maintenance|machine vision|edge gateway)\b", re.I)),
    ("Automotive",     re.compile(r"\b(car|vehicle|auto(motive)?|infotainment|carplay|android auto|digital key|adas|ev\b|tpms)\b", re.I)),
    ("Wearable",       re.compile(r"\b(wearable|smartwatch|fitness tracker|fitness band|smart ring)\b", re.I)),
    ("AR / VR / XR",   re.compile(r"\b(ar/vr|augmented reality|virtual reality|mixed reality|\bxr\b|metaverse|spatial computing|vision pro|quest \d|hololens)\b", re.I)),
    ("Smart Glasses",  re.compile(r"\b(smart glasses|ar glasses|ray[- ]ban meta|north focals|orion glasses|nuance audio|even realities|brilliant labs)\b", re.I)),
    ("Audio / Speaker",re.compile(r"\b(speaker|soundbar|earbud|airpods|headphone|home audio|hearable|wireless audio|hi-?fi)\b", re.I)),
    ("Healthcare",     re.compile(r"\b(medical|healthcare|hospital|patient monitoring|cgm|glucose|insulin|hearing aid|telehealth)\b", re.I)),
    ("Asset Tracking", re.compile(r"\b(asset tracking|tracker tag|airtag|fleet|logistics|cold chain|rtls)\b", re.I)),
    ("Retail",         re.compile(r"\b(retail|electronic shelf label|esl\b|point of sale|pos\b|beacon)\b", re.I)),
    ("Energy/Utility", re.compile(r"\b(smart meter|utility|grid|solar|ev charger|charging station|energy management)\b", re.I)),
    ("Smart City",     re.compile(r"\b(smart city|street light|parking sensor|traffic sensor|public transit)\b", re.I)),
    ("Agriculture",    re.compile(r"\b(precision (agri|farming)|smart farm|livestock monitoring)\b", re.I)),
    ("Robotics",       re.compile(r"\b(robot|cobot|amr\b|agv\b|drone)\b", re.I)),
]


def detect_vendor(text: str) -> tuple[str, str] | tuple[None, None]:
    if not text:
        return (None, None)
    for name, region, pat in VENDORS:
        if pat.search(text):
            return name, region
    return (None, None)


def detect_customer(text: str) -> str | None:
    if not text:
        return None
    # Prioritize explicit Apple signals so mixed-source summaries that mention
    # generic terms like "Google" don't incorrectly steal Apple-tagged stories.
    if re.search(r"\b(apple|iphone|ipad|ios\s?\d+|airpods|apple watch|airtag|homekit|corebluetooth)\b", text, re.I):
        return "Apple"
    for name, pat in CUSTOMERS:
        if pat.search(text):
            return name
    return None


def detect_application(text: str) -> str | None:
    if not text:
        return None
    for name, pat in APPLICATIONS:
        if pat.search(text):
            return name
    return None


def vendors_by_region() -> list[tuple[str, list[str]]]:
    out: dict[str, list[str]] = {"americas": [], "europe": [], "asia": []}
    for name, region, _ in VENDORS:
        out[region].append(name)
    return [("americas", out["americas"]), ("europe", out["europe"]), ("asia", out["asia"])]


def all_customers() -> list[str]:
    return [n for n, _ in CUSTOMERS]


def all_applications() -> list[str]:
    return [n for n, _ in APPLICATIONS]
