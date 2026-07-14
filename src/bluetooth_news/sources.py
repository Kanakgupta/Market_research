"""Search sources grouped by wireless technology bucket.

Each bucket gets sent to Google News + Bing News RSS. Direct vendor RSS
feeds (when available) feed all buckets and are classified later.
LinkedIn company pages are fetched via RSSHub (configurable via RSSHUB_INSTANCE env var).
X/Twitter timelines are fetched via a nitter instance (configurable via NITTER_INSTANCE env var).
"""
import os
from urllib.parse import quote_plus

# Tab order in the generated site.
BUCKETS: list[tuple[str, str]] = [
    ("wifi",      "Wi-Fi"),
    ("bluetooth", "Bluetooth"),
    ("ieee15_4",  "802.15.4"),
    ("aliro",     "Aliro"),
    ("thread",    "Thread"),
    ("matter",    "Matter"),
]

# Search queries per bucket. Every query becomes one Google + one Bing RSS feed.
QUERIES: dict[str, list[str]] = {
    "wifi": [
        "Wi-Fi 7 chip",
        "Wi-Fi 7 release announcement",
        "Wi-Fi 8 IEEE 802.11bn",
        "Wi-Fi 6E 6 GHz",
        "Wi-Fi MLO multi-link operation",
        "Wi-Fi HaLow 802.11ah",
        "Qualcomm FastConnect Wi-Fi",
        "MediaTek Filogic Wi-Fi",
        "NXP IW612 Wi-Fi",
        "Realtek Wi-Fi chip",
        "Espressif ESP32 Wi-Fi",
        "Broadcom Wi-Fi chip",
    ],
    "bluetooth": [
        # Specs / features
        "Bluetooth LE Audio",
        "Bluetooth Auracast",
        "Bluetooth LE long range coded PHY",
        "Bluetooth low latency connection interval",
        "Bluetooth high data throughput HDT",
        "Bluetooth higher band 6 GHz",
        "Bluetooth channel sounding ranging",
        "Bluetooth ambient light",
        "Bluetooth 6.0 specification",
        # Apple / iOS specific
        "Apple Bluetooth iOS",
        "iPhone Bluetooth tracking",
        "iOS Channel Sounding",
        "Apple CoreBluetooth",
        "Apple HomeKit Bluetooth",
        "AirTag Bluetooth",
        "Apple Watch Bluetooth",
        # Stacks (open source + OEM)
        "Android Bluetooth stack Gabeldorsche",
        "Android Fluoride Bluetooth",
        "BlueZ Bluetooth Linux",
        "Zephyr Bluetooth stack",
        "NimBLE Apache Bluetooth stack",
        "Apple CoreBluetooth iOS",
        "Windows Bluetooth stack WinRT",
        "Mynewt Bluetooth",
        "Bluetooth host controller HCI open source",
        # Profiles
        "Bluetooth GATT profile",
        "Bluetooth HFP hands-free profile",
        "Bluetooth A2DP audio profile",
        "Bluetooth AVRCP profile",
        "Bluetooth HID profile",
        "Bluetooth BAP basic audio profile",
        "Bluetooth TMAP telephony media profile",
        "Bluetooth GMAP gaming audio profile",
        "Bluetooth HAP hearing access profile",
        "Bluetooth PBAP phonebook profile",
        "Bluetooth MAP message access profile",
        # Vendor chips
        "Nordic nRF54 Bluetooth",
        "Silicon Labs EFR32 Bluetooth",
        "TI CC2340 Bluetooth",
        "Qualcomm QCC Bluetooth audio",
        "Espressif ESP32 Bluetooth",
        "Infineon AIROC Bluetooth",
        "STMicro STM32WB Bluetooth",
    ],
    "ieee15_4": [
        "802.15.4 wireless",
        "IEEE 802.15.4 chip",
        "802.15.4 multiprotocol SoC",
        "802.15.4 radio MCU",
        "802.15.4 Thread Zigbee SoC",
        "IEEE 802.15.4 industrial IoT",
    ],
    "aliro": [
        "Aliro digital key",
        "Aliro CSA access",
        "Aliro NFC UWB Bluetooth",
        "Connectivity Standards Alliance Aliro",
        "FiRa digital key UWB",
        "NFC UWB BLE access control",
    ],
    "thread": [
        "Thread protocol IoT",
        "Thread border router",
        "OpenThread",
        "Thread 1.4",
        "Thread Group news",
        "Thread over 802.15.4 smart home",
        "Matter over Thread deployment",
    ],
    "matter": [
        "Matter smart home",
        "Matter 1.4 specification",
        "Matter Casting",
        "Matter Apple Google Amazon",
        "Matter device launch",
        "Matter 1.6",
        "CSA Matter certification",
    ],
}

# Direct vendor feeds — they are tagged as "general" and routed by classifier.
RSS_FEEDS: list[dict] = [
    {"name": "Bluetooth SIG Blog",    "url": "https://www.bluetooth.com/blog/feed/"},
    {"name": "Bluetooth SIG News",    "url": "https://www.bluetooth.com/news/feed/"},
    {"name": "CSA / Matter (Zigbee)", "url": "https://csa-iot.org/feed/"},
    {"name": "ZDNet",                 "url": "https://www.zdnet.com/news/rss.xml"},
    {"name": "The Verge",             "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Ars Technica",          "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "TechCrunch",            "url": "https://techcrunch.com/feed/"},
    {"name": "IEEE Spectrum",         "url": "https://spectrum.ieee.org/rss"},
    {"name": "EE Times",              "url": "https://www.eetimes.com/feed/"},
    {"name": "9to5Google",            "url": "https://9to5google.com/feed/"},
    {"name": "9to5Mac",               "url": "https://9to5mac.com/feed/"},
    {"name": "CNX Software",          "url": "https://www.cnx-software.com/feed/"},
    {"name": "The Register",          "url": "https://www.theregister.com/headlines.atom"},
]

# Critical articles that must always be included (bypass relevance filter).
# Fetched directly via trafilatura to ensure capture despite potential filter misses.
FEATURED_ARTICLES: list[str] = [
    "https://www.zdnet.com/article/iphone-enhanced-bluetooth-tracking-with-ios-27-theres-a-catch/",
]

# Per-vendor focused queries. Cast a wide net so each competitor surfaces
# at least some hits. Every entry => Google + Bing RSS feeds (bucket=None,
# classifier sorts later).
VENDOR_QUERIES: list[str] = [
    # Major OEMs / Consumers
    "Apple wireless Bluetooth iOS",
    "Apple HomeKit smart home",
    "Google Nest Bluetooth Matter",
    "Amazon Alexa wireless IoT",
    # Americas
    "Qualcomm wireless chip",
    "Broadcom Wi-Fi Bluetooth",
    "Texas Instruments SimpleLink wireless",
    "Silicon Labs wireless SoC",
    "Microchip wireless MCU",
    "Synaptics Veros wireless",
    "Marvell wireless connectivity",
    "Onsemi RSL10 Bluetooth",
    "Skyworks wireless connectivity",
    "Qorvo wireless IoT",
    "Atmosic Bluetooth energy harvesting",
    # Europe
    "Nordic Semiconductor nRF54",
    "NXP wireless connectivity",
    "Infineon AIROC wireless",
    "STMicroelectronics STM32WB Bluetooth",
    "u-blox wireless module",
    "Bosch Sensortec",
    "Sequans cellular IoT",
    # China
    "MediaTek Filogic wireless",
    "Realtek Wi-Fi Bluetooth",
    "Espressif ESP32",
    "Telink Bluetooth SoC",
    "Bouffalo Lab BL616",
    "Beken Bluetooth",
    "Goodix wireless GR5",
    "Actions Semi Bluetooth audio",
    "Bestechnic BES2700 Bluetooth",
    "HiSilicon Kirin wireless",
    "UNISOC wireless",
    "Phyplus Bluetooth",
    "WCH wireless RISC-V",
    # Japan / Korea / Taiwan
    "Renesas Dialog DA14695 Bluetooth",
    "Sony Spresense wireless",
    "Toshiba TC3567 Bluetooth",
    "Rohm Lapis wireless",
    "Murata wireless module",
    "Samsung Exynos Connect wireless",
    "LG Innotek wireless module",
    "Airoha AB1568 Bluetooth audio",
]

# Site-restricted queries against vendor newsrooms / IR pages.
# Catches press releases that mainstream outlets don't index.
VENDOR_PRESS_SITES: list[str] = [
    "site:nordicsemi.com",
    "site:nxp.com news",
    "site:infineon.com press",
    "site:qualcomm.com news",
    "site:ti.com news",
    "site:silabs.com news",
    "site:st.com press",
    "site:renesas.com news",
    "site:synaptics.com press",
    "site:microchip.com news",
    "site:espressif.com news",
    "site:mediatek.com news",
    "site:realtek.com news",
    "site:u-blox.com news",
    "site:onsemi.com news",
    "site:bouffalolab.com news",
    "site:airoha.com news",
    "site:atmosic.com news",
    "site:goodix.com news",
    "site:telink-semi.com news",
    "site:hisilicon.com news",
    "site:rohm.com news",
    "site:murata.com news",
    "site:semiconductor.samsung.com news",
]

# Trade press + reviewer queries — broad coverage the news bots index.
TRADE_PRESS_QUERIES: list[str] = [
    # Wireless / IoT trade
    "site:eetimes.com wireless",
    "site:edn.com wireless connectivity",
    "site:electronicsweekly.com wireless",
    "site:embedded.com wireless",
    "site:semiengineering.com wireless",
    "site:eenewseurope.com wireless",
    "site:newelectronics.co.uk wireless",
    "site:eeworldonline.com wireless",
    "site:electronicproducts.com wireless",
    "site:digitimes.com wireless chip",
    # Tech publications covering consumer Bluetooth/wireless
    "site:zdnet.com bluetooth ios iphone",
    "site:cnet.com bluetooth ios homekit",
    "site:techcrunch.com bluetooth wireless",
    "site:macrumors.com ios bluetooth",
    "site:macworld.com bluetooth homekit",
    "site:anandtech.com wireless chip",
    "site:wired.com smart home iot",
    "site:gsmarena.com bluetooth",
    "site:phonearena.com bluetooth wireless",
    # Consumer / reviewer trade
    "site:theverge.com smart home bluetooth",
    "site:9to5mac.com homekit matter bluetooth",
    "site:9to5google.com matter google home",
    "site:appleinsider.com bluetooth ios",
    "site:androidauthority.com bluetooth wifi",
    "site:liliputing.com wireless chip",
    "site:notebookcheck.net wifi 7 bluetooth",
    "site:tomshardware.com wifi 7 bluetooth",
    "site:wccftech.com wifi 7",
    "site:cnx-software.com wireless soc",
    "site:hackster.io wireless soc",
    "site:theregister.com wireless iot",
    # PR distribution
    "site:prnewswire.com wireless chip bluetooth",
    "site:businesswire.com wireless chip",
    "site:globenewswire.com wireless chip",
]


# ---------------------------------------------------------------------------
# Social handles for competitor LinkedIn company pages and X timelines.
# LinkedIn feeds require a running RSSHub instance (default: rsshub.app).
# X feeds require a running nitter instance (default: nitter.privacydev.net).
# Override via env vars:  RSSHUB_INSTANCE  /  NITTER_INSTANCE
# ---------------------------------------------------------------------------
SOCIAL_HANDLES: list[dict] = [
    # (vendor label for display, linkedin_slug, x_handle or None)
    {"vendor": "Apple",        "linkedin": "apple",                   "x": "Apple"},
    {"vendor": "Google",       "linkedin": "google",                  "x": "Google"},
    {"vendor": "Amazon",       "linkedin": "amazon-com",              "x": "amazon"},
    {"vendor": "Infineon",     "linkedin": "infineon-technologies",   "x": "Infineon"},
    {"vendor": "Nordic",       "linkedin": "nordicsemi",              "x": "NordicSemi"},
    {"vendor": "NXP",          "linkedin": "nxp-semiconductors",      "x": "NXPSemi"},
    {"vendor": "Qualcomm",     "linkedin": "qualcomm",                "x": "Qualcomm"},
    {"vendor": "Silicon Labs", "linkedin": "silicon-laboratories",    "x": "SiliconLabs"},
    {"vendor": "TI",           "linkedin": "texas-instruments",       "x": "TXInstruments"},
    {"vendor": "MediaTek",     "linkedin": "mediatek-inc",            "x": "MediaTek"},
    {"vendor": "Espressif",    "linkedin": "espressif-systems",       "x": "EspressifSystem"},
    {"vendor": "STMicro",      "linkedin": "stmicroelectronics",      "x": "ST_World"},
    {"vendor": "Renesas",      "linkedin": "renesas-electronics",     "x": "RenesasElec"},
    {"vendor": "Synaptics",    "linkedin": "synaptics-incorporated",  "x": "Synaptics"},
    {"vendor": "Broadcom",     "linkedin": "broadcom",                "x": "Broadcom"},
    {"vendor": "u-blox",       "linkedin": "u-blox",                  "x": "ublox"},
    {"vendor": "Microchip",    "linkedin": "microchip-technology",    "x": "MicrochipTech"},
    {"vendor": "Murata",       "linkedin": "murata-manufacturing",    "x": "MurataGlobal"},
    {"vendor": "Onsemi",       "linkedin": "onsemi",                  "x": "onsemi"},
    {"vendor": "Telink",       "linkedin": "telink-semiconductor",    "x": "telink_semi"},
    {"vendor": "Atmosic",      "linkedin": "atmosic-technologies",    "x": "AtmosicTech"},
    {"vendor": "Airoha",       "linkedin": "airoha-technology",       "x": None},
    {"vendor": "Bouffalo Lab", "linkedin": "bouffalo-lab",            "x": None},
]


def google_news_rss(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


def bing_news_rss(query: str) -> str:
    return f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss"


def rsshub_linkedin_rss(slug: str) -> str:
    """Return a RSSHub RSS URL for a LinkedIn company page.

    RSSHub scrapes LinkedIn company posts and exposes them as RSS.
    Default public instance: rsshub.app  — override with RSSHUB_INSTANCE env var.
    Self-host: https://docs.rsshub.app/deploy/
    """
    instance = os.environ.get("RSSHUB_INSTANCE", "https://rsshub.app").rstrip("/")
    return f"{instance}/linkedin/company/{slug}"


def nitter_rss(handle: str) -> str:
    """Return a nitter RSS URL for an X/Twitter user timeline.

    nitter is an open-source Twitter front-end that exposes RSS feeds.
    Default public instance: nitter.privacydev.net — override with NITTER_INSTANCE env var.
    Self-host: https://github.com/zedeus/nitter
    """
    instance = os.environ.get("NITTER_INSTANCE", "https://nitter.privacydev.net").rstrip("/")
    return f"{instance}/{handle}/rss"


def all_feed_urls() -> list[dict]:
    """Return list of {name, url, bucket} entries for every feed to fetch."""
    feeds: list[dict] = []
    for f in RSS_FEEDS:
        feeds.append({**f, "bucket": None})  # bucket inferred by classifier
    for bucket, queries in QUERIES.items():
        for q in queries:
            feeds.append({"name": f"Google: {q}", "url": google_news_rss(q), "bucket": bucket})
            feeds.append({"name": f"Bing: {q}",   "url": bing_news_rss(q),   "bucket": bucket})
    for q in VENDOR_QUERIES:
        feeds.append({"name": f"Google: {q}", "url": google_news_rss(q), "bucket": None})
        feeds.append({"name": f"Bing: {q}",   "url": bing_news_rss(q),   "bucket": None})
    for q in VENDOR_PRESS_SITES:
        feeds.append({"name": f"Google: {q}", "url": google_news_rss(q), "bucket": None})
    for q in TRADE_PRESS_QUERIES:
        feeds.append({"name": f"Google: {q}", "url": google_news_rss(q), "bucket": None})
        feeds.append({"name": f"Bing: {q}",   "url": bing_news_rss(q),   "bucket": None})
    # LinkedIn company pages (via RSSHub) and X timelines (via nitter)
    for h in SOCIAL_HANDLES:
        vendor = h["vendor"]
        feeds.append({
            "name": f"LinkedIn: {vendor}",
            "url": rsshub_linkedin_rss(h["linkedin"]),
            "bucket": None,
        })
        if h.get("x"):
            feeds.append({
                "name": f"X: {vendor}",
                "url": nitter_rss(h["x"]),
                "bucket": None,
            })
    return feeds
