"""Hand-curated market map of Bluetooth stacks (BT Stack page).

Static, editorial content (not news-driven). The goal is a *complete* market map of
Bluetooth host/controller stacks that ship in real products worldwide -- commercial
(licensed / vendor) stacks, open-source stacks, and OS-native stacks -- plus, for each
stack, an honest read on:

  - which Bluetooth Core spec version it tracks and how far behind the latest spec it is
  - which link-layer / host features it supports (LE Audio, Channel Sounding, etc.)
  - which profiles are supported vs. not supported
  - what is missing compared to the latest Bluetooth specification
  - qualification / certification posture (QDID / Declaration IDs are assigned per
    release -- we link to the Bluetooth SIG Qualification listing to verify, rather
    than hard-coding numbers that change every release)

Two shared glossaries (FEATURE_GLOSSARY, PROFILE_GLOSSARY) hold a one-line
"what problem it solves / why you care" brief for every feature and profile so the
page can make each chip clickable. Each stack only references glossary keys, so the
briefs stay consistent across the whole page.

Latest reference spec on this page: Bluetooth Core Specification 6.1 (2025), with 6.0
(Channel Sounding) as the headline recent feature wave. Update LATEST_SPEC below when a
newer core spec ships.
"""
from __future__ import annotations

LATEST_SPEC = "Bluetooth Core 6.1 (2025)"

# ---------------------------------------------------------------------------
# FEATURE GLOSSARY  -- key -> {name, tag, brief}
#   tag: "LE" | "Classic" | "Audio" | "Both"  (used only for a small colored pill)
#   brief: what problem it solves + why you care (kept to 1-2 sentences)
# ---------------------------------------------------------------------------
FEATURE_GLOSSARY: dict[str, dict] = {
    # --- Radio / PHY ---
    "le_1m_phy": {"name": "LE 1M PHY", "tag": "LE",
        "brief": "The original 1 Mbit/s Bluetooth Low Energy radio. It is the baseline every LE device must support for interoperability -- if a stack has this, any phone can at least connect to it."},
    "le_2m_phy": {"name": "LE 2M PHY", "tag": "LE",
        "brief": "A 2 Mbit/s LE radio (Bluetooth 5.0) that doubles throughput and shortens on-air time. You care because faster transfers mean lower energy per byte and longer battery life for firmware updates and sensor bursts."},
    "le_coded_phy": {"name": "LE Coded PHY (Long Range)", "tag": "LE",
        "brief": "Forward-error-corrected LE radio (Bluetooth 5.0) that trades data rate for up to ~4x range. It solves 'the device drops out across the house / factory floor' without adding a repeater."},
    "br_edr": {"name": "BR/EDR (Classic)", "tag": "Classic",
        "brief": "Classic Bluetooth for streaming audio, serial links and legacy accessories. You still need it for headsets, car kits and any pre-LE-Audio product that must work with today's phones."},
    "edr": {"name": "Enhanced Data Rate (EDR)", "tag": "Classic",
        "brief": "2-3 Mbit/s Classic Bluetooth modulation for higher throughput audio/data. It is what makes A2DP music streaming and file transfer usable over Classic."},

    # --- Advertising / connection topology ---
    "adv_extensions": {"name": "LE Advertising Extensions", "tag": "LE",
        "brief": "Bluetooth 5.0 extended advertising: bigger payloads, secondary channels and chaining. It solves crowded-2.4GHz reliability and lets beacons/broadcasters send far more data without a connection."},
    "periodic_adv": {"name": "Periodic Advertising", "tag": "LE",
        "brief": "Deterministic, schedulable broadcasts many receivers can lock onto at once. This underpins one-to-many use cases like Auracast and time-synced sensor networks."},
    "past": {"name": "Periodic Adv. Sync Transfer (PAST)", "tag": "LE",
        "brief": "Lets one device hand a periodic-advertising sync to another so the receiver skips the slow scan/lock step. It makes joining a broadcast (e.g. an Auracast stream) fast and low-power."},
    "pawr": {"name": "Periodic Adv. with Responses (PAwR)", "tag": "LE",
        "brief": "Bidirectional periodic advertising (Bluetooth 5.4) where broadcast subscribers can reply in assigned slots. It enables huge one-to-many device networks -- e.g. electronic shelf labels -- with acknowledgements."},
    "adv_coding_selection": {"name": "Advertising Coding Selection", "tag": "LE",
        "brief": "Bluetooth 5.4 control over the Coded PHY coding scheme (S=2 vs S=8) used for advertising. It lets you tune the range-vs-rate trade-off per broadcast instead of accepting a fixed default."},
    "decision_based_adv": {"name": "Decision-Based Adv. Filtering", "tag": "LE",
        "brief": "Bluetooth 6.0 feature letting a scanner decide which extended advertisements to process using a decision field, before full decode. It cuts scanner power and CPU in dense advertising environments."},
    "monitoring_advertisers": {"name": "Monitoring Advertisers", "tag": "LE",
        "brief": "Bluetooth 6.0 mechanism to get notified when specific advertisers come/go in range without constantly scanning. It is the basis for low-power presence/proximity apps."},

    # --- Connection quality-of-service ---
    "connection_subrating": {"name": "Connection Subrating", "tag": "LE",
        "brief": "Bluetooth 5.3 lets a link switch quickly between a fast and a slow duty cycle. It keeps a keyboard/controller responsive when active but ultra-low-power when idle, without dropping the connection."},
    "le_power_control": {"name": "LE Power Control (LEPC)", "tag": "LE",
        "brief": "Bluetooth 5.2 dynamic TX power adjustment based on measured link quality. It saves battery and reduces interference by never transmitting louder than needed."},
    "data_length_ext": {"name": "LE Data Length Extension", "tag": "LE",
        "brief": "Bigger link-layer packets (up to 251 bytes). Fewer packets per payload means higher throughput and lower energy -- important for OTA firmware updates and sensor logs."},
    "channel_selection_2": {"name": "Channel Selection Algorithm #2", "tag": "LE",
        "brief": "An improved adaptive-frequency-hopping algorithm for LE. It improves coexistence and robustness in noisy 2.4 GHz environments (offices, factories)."},
    "afh": {"name": "Adaptive Frequency Hopping (AFH)", "tag": "Both",
        "brief": "Avoids channels polluted by Wi-Fi/microwaves by hopping around them. It is why Bluetooth keeps working next to a busy Wi-Fi access point."},

    # --- Security / privacy ---
    "le_secure_connections": {"name": "LE Secure Connections", "tag": "LE",
        "brief": "ECDH (P-256) pairing that defends against passive eavesdropping and MITM. You care because regulators and platform stores increasingly require it for any product handling personal data."},
    "sc_classic": {"name": "Secure Connections (Classic)", "tag": "Classic",
        "brief": "Brings the stronger LE-Secure-Connections crypto to Classic BR/EDR pairing. It is the modern, non-legacy pairing path for headsets and car kits."},
    "le_privacy": {"name": "LE Privacy (RPA)", "tag": "LE",
        "brief": "Resolvable Private Addresses rotate the device's MAC so it can't be tracked by third parties. Essential for wearables and anything a person carries in public."},
    "encrypted_adv_data": {"name": "Encrypted Advertising Data", "tag": "LE",
        "brief": "Bluetooth 5.4 lets advertising payloads be encrypted to trusted peers. It stops passive sniffers from reading beacon data (e.g. sensor readings) that used to be broadcast in the clear."},

    # --- ATT / GATT transport ---
    "gatt": {"name": "GATT / ATT", "tag": "LE",
        "brief": "The attribute database every LE service is built on. Without a GATT engine a stack can't expose or consume any standard LE profile."},
    "gatt_caching": {"name": "GATT Caching (Robust Caching)", "tag": "LE",
        "brief": "Lets a client remember a server's attribute layout across connections. It removes the slow service-discovery step on every reconnect, so wearables re-sync with a phone almost instantly."},
    "eatt": {"name": "Enhanced ATT (EATT)", "tag": "LE",
        "brief": "Bluetooth 5.2 concurrent, multiplexed ATT bearers. It stops one slow operation from blocking others, which is what makes LE Audio's many parallel controls feel responsive."},
    "l2cap_coc": {"name": "L2CAP CoC (Credit-Based Flow)", "tag": "LE",
        "brief": "Connection-oriented L2CAP channels for streaming arbitrary data over LE with flow control. It is how you move bulk data (files, IP packets) efficiently without abusing GATT notifications."},

    # --- Isochronous / LE Audio plumbing ---
    "le_iso": {"name": "Isochronous Channels (CIS/BIS)", "tag": "Audio",
        "brief": "Bluetooth 5.2 time-synchronized data streams -- connected (CIS) and broadcast (BIS). They are the transport layer that makes LE Audio and true-wireless earbud sync possible."},
    "lc3": {"name": "LC3 Codec", "tag": "Audio",
        "brief": "The mandatory LE Audio codec: better quality than SBC at half the bitrate. It means longer earbud battery life and more simultaneous streams for the same airtime."},
    "le_audio_core": {"name": "LE Audio (core support)", "tag": "Audio",
        "brief": "The full LE Audio feature set (ISO + LC3 + audio profiles). It is the platform for hearing aids, Auracast broadcast audio and next-gen earbuds -- the industry's replacement for Classic A2DP/HFP."},
    "auracast": {"name": "Auracast Broadcast Audio", "tag": "Audio",
        "brief": "One transmitter, unlimited receivers -- public broadcast audio (airports, TVs, assistive listening). It solves 'share audio to a crowd' and accessibility mandates for hearing access."},

    # --- Bluetooth 6.0 headline ---
    "channel_sounding": {"name": "Channel Sounding", "tag": "LE",
        "brief": "Bluetooth 6.0 secure distance measurement using phase-based ranging. It brings accurate, spoof-resistant 'how far away is it' to digital keys, find-my tags and access control -- a direct answer to UWB."},

    # --- Mesh ---
    "mesh": {"name": "Bluetooth Mesh", "tag": "LE",
        "brief": "Many-to-many networking over LE advertising for building-scale lighting and sensor control. It solves whole-building coverage without every node being in phone range."},

    # --- Controller / transport plumbing ---
    "hci_transport": {"name": "HCI Transport (UART/USB/SDIO)", "tag": "Both",
        "brief": "The standard host-controller interface so a host stack can drive many different radio chips. It is what lets an OS stack (BlueZ, Windows) work across vendors."},
    "controller_only": {"name": "Link-Layer / Controller", "tag": "Both",
        "brief": "The lower half of the stack (radio scheduling, encryption, HCI). A product needs a controller paired with a host stack -- some vendors ship both, some only one half."},
    "host_only": {"name": "Host Stack (upper layers)", "tag": "Both",
        "brief": "The upper half (L2CAP, ATT/GATT, SMP, profiles) that runs over any qualified controller via HCI. Useful when you want to reuse silicon from multiple radio vendors."},
}

# ---------------------------------------------------------------------------
# PROFILE GLOSSARY  -- key -> {name, tag, brief}
#   tag: "Classic" | "LE" | "Audio"
# ---------------------------------------------------------------------------
PROFILE_GLOSSARY: dict[str, dict] = {
    # --- Foundational ---
    "gap": {"name": "GAP", "tag": "LE",
        "brief": "Generic Access Profile -- defines discovery, connection and roles. Every Bluetooth device implements it; it is the 'how do two devices find and talk to each other' baseline."},
    "gatt_profile": {"name": "GATT (generic)", "tag": "LE",
        "brief": "The framework all LE data profiles are built on. If a stack supports GATT you can layer any custom or standard LE service on top."},

    # --- Classic audio / telephony ---
    "a2dp": {"name": "A2DP", "tag": "Classic",
        "brief": "Advanced Audio Distribution -- stereo music streaming to headphones/speakers. It is the profile behind virtually every Classic Bluetooth speaker and earbud today."},
    "avrcp": {"name": "AVRCP", "tag": "Classic",
        "brief": "Audio/Video Remote Control -- play/pause/skip/volume and track metadata. It is why your car or earbuds can control the phone's music app."},
    "hfp": {"name": "HFP", "tag": "Classic",
        "brief": "Hands-Free Profile -- phone calls through a car kit or headset, including call control and (wideband) speech. Mandatory for any calling headset or automotive infotainment."},
    "hsp": {"name": "HSP", "tag": "Classic",
        "brief": "Headset Profile -- the older, simpler mono call/audio profile. Mostly legacy, kept for backward compatibility with old accessories."},

    # --- Classic data ---
    "spp": {"name": "SPP", "tag": "Classic",
        "brief": "Serial Port Profile -- a virtual RS-232 cable over Bluetooth. It is the workhorse for industrial gear, payment terminals and DIY projects that just need a data pipe."},
    "pbap": {"name": "PBAP", "tag": "Classic",
        "brief": "Phone Book Access -- syncs contacts/call history to a car or headset. It is why your caller ID and address book show up on the car screen."},
    "map": {"name": "MAP", "tag": "Classic",
        "brief": "Message Access Profile -- pushes texts/notifications to a car or wearable. It powers 'read my messages' in automotive infotainment."},
    "pan": {"name": "PAN / BNEP", "tag": "Classic",
        "brief": "Personal Area Networking -- Ethernet-over-Bluetooth for tethering/IP. Niche today but still used for gateway and legacy tethering scenarios."},
    "opp": {"name": "OPP", "tag": "Classic",
        "brief": "Object Push -- the classic 'beam a file/contact' transfer. Largely superseded by Wi-Fi/cloud sharing but still specified for interoperability."},
    "dip": {"name": "DIP", "tag": "Classic",
        "brief": "Device ID Profile -- advertises vendor/product IDs so the peer can identify the device. It lets phones apply device-specific quirks and show proper names."},

    # --- HID ---
    "hid": {"name": "HID (Classic)", "tag": "Classic",
        "brief": "Human Interface Device over Classic -- keyboards, mice, controllers. Still used by many game controllers and older peripherals."},
    "hogp": {"name": "HOGP (HID over GATT)", "tag": "LE",
        "brief": "HID over LE -- low-power keyboards, mice, styluses and controllers. It is why a modern LE keyboard lasts months on a coin cell yet stays responsive."},

    # --- LE health / sensor profiles ---
    "hrp": {"name": "Heart Rate (HRP)", "tag": "LE",
        "brief": "Standard heart-rate service so any app can read any compliant chest strap or watch. Interoperability means users aren't locked to one vendor's app."},
    "htp": {"name": "Health Thermometer (HTP)", "tag": "LE",
        "brief": "Standard body-temperature service. Lets medical/consumer thermometers report to any compliant phone app."},
    "blp": {"name": "Blood Pressure (BLP)", "tag": "LE",
        "brief": "Standard blood-pressure-monitor service. Chosen by regulated health devices that need vendor-neutral phone integration."},
    "glp": {"name": "Glucose (GLP)", "tag": "LE",
        "brief": "Standard glucose-meter service, including stored readings. Important for connected diabetes-care devices."},
    "bas": {"name": "Battery (BAS)", "tag": "LE",
        "brief": "Standard battery-level service. Nearly every LE device exposes it so phones can show the accessory's battery in the OS UI."},
    "dis": {"name": "Device Information (DIS)", "tag": "LE",
        "brief": "Model, firmware and serial number service. Used by companion apps and DFU flows to know exactly what they're talking to."},
    "esp": {"name": "Environmental Sensing (ESP)", "tag": "LE",
        "brief": "Standard temperature/humidity/pressure sensor service. Lets smart-home hubs read any compliant sensor without custom code."},
    "cscp": {"name": "Cycling Speed & Cadence (CSCP)", "tag": "LE",
        "brief": "Standard bike speed/cadence service. Used by cycling sensors so any fitness app (Strava, Garmin, Wahoo) can read them."},
    "rscp": {"name": "Running Speed & Cadence (RSCP)", "tag": "LE",
        "brief": "Standard running foot-pod service. Same interoperability story as cycling, for run-tracking accessories."},
    "cpp": {"name": "Cycling Power (CPP)", "tag": "LE",
        "brief": "Standard bike power-meter service. Core data source for serious cycling training platforms."},

    # --- LE proximity / time / find ---
    "pxp": {"name": "Proximity (PXP)", "tag": "LE",
        "brief": "Alerts when two devices move apart (link-loss/immediate alert). Basis of 'leave-behind' warnings and simple anti-loss tags."},
    "fmp": {"name": "Find Me (FMP)", "tag": "LE",
        "brief": "Makes a lost accessory beep from a button on the phone. The classic 'ring my earbud case' feature."},
    "ias": {"name": "Immediate Alert (IAS)", "tag": "LE",
        "brief": "The building block used by Proximity/Find-Me to trigger an alert level. Small but required by those anti-loss features."},
    "cts": {"name": "Current Time (CTS)", "tag": "LE",
        "brief": "Syncs date/time from a phone to a watch/sensor. It keeps accessory timestamps correct without a UI on the device."},
    "ans": {"name": "Alert Notification (ANS)", "tag": "LE",
        "brief": "Pushes caller/message alert counts to a simple wearable. An LE-native alternative to Apple's proprietary ANCS."},

    # --- LE transport / networking ---
    "ots": {"name": "Object Transfer (OTS)", "tag": "LE",
        "brief": "Standard way to move files/objects over LE. Used for firmware images, log downloads and camera stills without a custom protocol."},
    "ipsp": {"name": "IPSP (IPv6 over BLE)", "tag": "LE",
        "brief": "Carries IPv6 (6LoWPAN) over LE for IP-native sensors. Niche, but relevant to some Thread-adjacent and edge deployments."},

    # --- LE Audio profile stack ---
    "bap": {"name": "BAP (Basic Audio)", "tag": "Audio",
        "brief": "Basic Audio Profile -- the foundation of LE Audio: stream setup, codec config, unicast + broadcast. Nothing in LE Audio works without it."},
    "cap": {"name": "CAP (Common Audio)", "tag": "Audio",
        "brief": "Common Audio Profile -- the coordination layer that makes left+right earbuds and multi-device audio behave as one. It is what turns raw BAP streams into a coherent product."},
    "csip": {"name": "CSIP (Coordinated Sets)", "tag": "Audio",
        "brief": "Coordinated Set Identification -- groups the two earbuds (or stereo speakers) so they pair/act together. Solves 'why did only one bud connect'."},
    "vcp": {"name": "VCP (Volume Control)", "tag": "Audio",
        "brief": "Standard LE Audio volume control across a coordinated set. One volume change hits both earbuds in sync."},
    "micp": {"name": "MICP (Microphone Control)", "tag": "Audio",
        "brief": "Standard LE Audio mic mute/gain control. Needed for LE Audio headsets used on calls."},
    "mcp": {"name": "MCP/MCS (Media Control)", "tag": "Audio",
        "brief": "Media Control Profile -- LE Audio's play/pause/skip/metadata (the LE-Audio successor to AVRCP). Lets earbuds drive the phone's player."},
    "ccp": {"name": "CCP/TBS (Call Control)", "tag": "Audio",
        "brief": "Call Control Profile -- answer/reject/hold over LE Audio (the successor to HFP call control). Required for LE-Audio calling headsets."},
    "tmap": {"name": "TMAP (Telephony & Media)", "tag": "Audio",
        "brief": "Telephony and Media Audio Profile -- the top-level profile phones/earbuds actually advertise for mainstream LE Audio (music + calls). Interop shorthand for 'a normal LE Audio headset'."},
    "hap": {"name": "HAP (Hearing Access)", "tag": "Audio",
        "brief": "Hearing Access Profile -- LE Audio for hearing aids (presets, binaural coordination). Directly tied to accessibility regulation and the reason LE Audio exists."},
    "pbp": {"name": "PBP (Public Broadcast)", "tag": "Audio",
        "brief": "Public Broadcast Profile -- the Auracast rules for public broadcast audio (naming, quality tiers). Ensures a TV's broadcast is discoverable by any receiver."},
    "gmap": {"name": "GMAP (Gaming Audio)", "tag": "Audio",
        "brief": "Gaming Audio Profile -- low-latency bidirectional LE Audio for game headsets. Targets the latency-sensitive gaming market Classic couldn't serve well."},
    "asha": {"name": "ASHA (Android Hearing Aid)", "tag": "Audio",
        "brief": "Google's pre-LE-Audio hearing-aid streaming protocol over LE. Still shipping widely on Android hearing aids until LE Audio/HAP fully takes over."},
}


def _stack(slug, name, vendor, category, license, spec, tagline, overview,
           certification, features, profiles_supported, profiles_not,
           missing_vs_spec, best_fit, links=None):
    return {
        "slug": slug, "name": name, "vendor": vendor, "category": category,
        "license": license, "spec": spec, "tagline": tagline, "overview": overview,
        "certification": certification, "features": features,
        "profiles_supported": profiles_supported, "profiles_not": profiles_not,
        "missing_vs_spec": missing_vs_spec, "best_fit": best_fit,
        "links": links or [],
    }


# A verify link for qualification data (never hard-code QDIDs -- they change per release)
_QUAL_SEARCH = "https://qualification.bluetooth.com/ListingType/Product"

# ---------------------------------------------------------------------------
# STACK CATALOG  -- grouped by category for the left panel
# ---------------------------------------------------------------------------
STACK_CATEGORIES = [
    "Silicon-Vendor Stacks (commercial)",
    "Independent / Licensable Stacks",
    "Open-Source Stacks",
    "OS-Native Stacks",
]

BT_STACKS = [
    # =====================================================================
    # Silicon-vendor commercial stacks
    # =====================================================================
    _stack(
        "infineon-airoc", "Infineon AIROC Bluetooth Stack", "Infineon AIROC",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (vendor SDK)", "Bluetooth 5.4 / LE Audio",
        "Vendor-integrated dual-mode stack tuned to Infineon AIROC silicon.",
        "Full dual-mode (BR/EDR + LE) host+controller shipped as part of the Infineon AIROC ModusToolbox SDK. "
        "Tightly co-designed with the radio for low-power tuning, qualified per release, with vendor lifecycle "
        "support and LE Audio on the newest parts. It is a turnkey, time-to-market choice inside the Infineon AIROC ecosystem.",
        {"status": "Qualified", "note": "QDID assigned per silicon/SDK release; verify current listings on the Bluetooth SIG Qualification site.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "connection_subrating",
         "data_length_ext", "afh", "mesh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "hid", "hogp", "bas", "dis",
         "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap", "pbp"],
        ["channel_sounding", "hap", "gmap", "pawr"],
        ["Channel Sounding (BT 6.0) availability is silicon-dependent -- confirm on the specific AIROC part before committing a ranging feature.",
         "Newest LE Audio profiles (HAP hearing-aid, GMAP gaming) trail the platform profiles on some parts.",
         "Not portable to third-party silicon -- there is no cross-vendor abstraction layer."],
        "Commercial products that want qualification, low-power tuning and long-term vendor support inside the Infineon AIROC ecosystem.",
        [{"label": "ModusToolbox / AIROC", "url": "https://www.infineon.com/cms/en/design-support/tools/sdk/modustoolbox-software/"}],
    ),
    _stack(
        "nordic-softdevice", "Nordic SoftDevice / nRF Connect SDK", "Nordic Semiconductor",
        "Silicon-Vendor Stacks (commercial)", "Proprietary SoftDevice + Zephyr-based SDK", "Bluetooth 5.4 / LE Audio",
        "Precompiled LE stack ('SoftDevice') plus a Zephyr-based SDK; the default for many BLE products.",
        "Nordic ships two paths: the classic binary SoftDevice controller (S1xx) and the newer nRF Connect SDK "
        "built on Zephyr with Nordic's SoftDevice Controller. LE-only (no Classic), extremely well documented, huge "
        "developer base, and among the earliest to ship LE Audio and Channel Sounding on nRF54 parts.",
        {"status": "Qualified", "note": "SoftDevice / SDK releases carry Bluetooth QDIDs per version; verify the exact listing for your SDK.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past", "pawr",
         "le_secure_connections", "le_privacy", "encrypted_adv_data", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "channel_sounding", "le_power_control",
         "connection_subrating", "data_length_ext", "channel_selection_2", "afh", "mesh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "rscp", "cpp",
         "pxp", "fmp", "ias", "cts", "ans", "ots", "bap", "cap", "csip", "vcp", "micp", "mcp", "ccp", "tmap", "hap"],
        ["a2dp", "avrcp", "hfp", "hsp", "spp", "hid", "pbap", "map"],
        ["No Classic BR/EDR at all -- cannot do legacy A2DP/HFP headsets or SPP serial links.",
         "Classic-only accessories (car kits, legacy game controllers) need a different chip/stack."],
        "LE-only products (wearables, sensors, LE Audio, digital keys) that want mature tooling and early access to new LE features.",
        [{"label": "nRF Connect SDK", "url": "https://www.nordicsemi.com/Products/Development-software/nRF-Connect-SDK"}],
    ),
    _stack(
        "silabs-bt", "Silicon Labs Bluetooth Stack", "Silicon Labs",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (Simplicity/Gecko SDK)", "Bluetooth 5.4 / LE Audio",
        "LE + mesh stack for EFR32 wireless SoCs, strong in mesh and multiprotocol.",
        "Silicon Labs' Bluetooth stack (Gecko/Simplicity SDK) targets EFR32 SoCs and modules. LE-focused with a "
        "well-regarded Bluetooth Mesh implementation and multiprotocol (concurrent Bluetooth + Zigbee/Thread/Matter). "
        "LE Audio and Channel Sounding are supported on the newer Series 2/xG24-class parts.",
        {"status": "Qualified", "note": "SDK releases carry per-version QDIDs; verify the current Simplicity SDK listing.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "channel_sounding", "le_power_control",
         "connection_subrating", "data_length_ext", "afh", "mesh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "cpp", "pxp", "fmp",
         "cts", "ots", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["a2dp", "avrcp", "hfp", "spp", "hid", "pbap", "map", "hap"],
        ["LE-only -- no Classic BR/EDR, so no legacy audio/serial accessories.",
         "Strongest fit is mesh/multiprotocol; audio-product profile coverage is narrower than audio-specialist stacks."],
        "Smart-home / building products needing Bluetooth mesh and concurrent Zigbee/Thread/Matter on one chip.",
        [{"label": "Simplicity SDK", "url": "https://www.silabs.com/developers/simplicity-sdk"}],
    ),
    _stack(
        "ti-blestack", "Texas Instruments BLE-Stack / SimpleLink", "Texas Instruments",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (SimpleLink SDK)", "Bluetooth 5.4",
        "LE stack for SimpleLink CC13xx/CC23xx/CC27xx wireless MCUs.",
        "TI's BLE-Stack ships in the SimpleLink SDK for CC26xx/CC13xx and newer CC23xx/CC27xx MCUs. LE-only, known "
        "for very low power and multiprotocol (BLE + 802.15.4/Thread/Matter). Newer CC27xx parts add Channel Sounding.",
        {"status": "Qualified", "note": "SimpleLink SDK releases carry per-version QDIDs; verify the current listing.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "le_privacy", "gatt", "gatt_caching", "l2cap_coc", "channel_sounding",
         "le_power_control", "data_length_ext", "afh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "cpp", "pxp", "fmp", "cts"],
        ["a2dp", "avrcp", "hfp", "spp", "hid", "bap", "cap", "tmap", "hap", "mesh"],
        ["LE-only and not an LE Audio audio stack -- no BAP/CAP audio profiles out of the box.",
         "No Classic BR/EDR for legacy audio/serial.",
         "Bluetooth Mesh is not a core focus of the TI stack."],
        "Ultra-low-power LE sensor/medical/industrial nodes, often alongside Thread/Matter on the same SoC.",
        [{"label": "SimpleLink SDK", "url": "https://www.ti.com/tool/SIMPLELINK-LOWPOWER-SDK"}],
    ),
    _stack(
        "nxp-ble", "NXP Bluetooth LE / Wireless Stack", "NXP Semiconductors",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (MCUXpresso SDK)", "Bluetooth 5.4 / LE Audio",
        "Dual-mode/LE stacks across KW, RW and i.MX wireless families.",
        "NXP provides LE and dual-mode Bluetooth across several families -- KW3x/KW4x connectivity MCUs, the RW61x "
        "tri-radio parts, and Linux/BlueZ-based stacks on i.MX application processors. LE Audio is supported on newer "
        "connectivity silicon; Classic audio is available on the Wi-Fi/BT combo and applications-processor side.",
        {"status": "Qualified", "note": "Per-family, per-release QDIDs; verify listings for the specific NXP part/SDK.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "data_length_ext", "afh",
         "mesh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "spp", "hid", "hogp", "bas", "dis", "hrp",
         "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["channel_sounding", "hap", "gmap", "pawr"],
        ["Feature coverage varies a lot by family -- a KW connectivity MCU, an RW61x combo and an i.MX+BlueZ host are three different capability sets.",
         "Channel Sounding availability is part-dependent; confirm on the target silicon."],
        "Broad portfolios that mix MCU connectivity, Wi-Fi/BT combos and Linux gateways under one vendor.",
        [{"label": "MCUXpresso SDK", "url": "https://www.nxp.com/design/software/development-software/mcuxpresso-software-and-tools-/mcuxpresso-software-development-kit-sdk:MCUXpresso-SDK"}],
    ),
    _stack(
        "st-stm32wb", "STMicroelectronics STM32Cube WB / WBA", "STMicroelectronics",
        "Silicon-Vendor Stacks (commercial)", "Open middleware + proprietary BT stack", "Bluetooth 5.4 / LE Audio",
        "LE stack for STM32WB/WBA wireless MCUs; open Cube middleware over a proprietary link layer.",
        "ST's STM32Cube WB (Cortex-M0+ radio coprocessor) and newer WBA (single-core) wireless MCUs ship an LE stack "
        "under open STM32Cube middleware with a proprietary controller. Popular for cost-sensitive LE plus concurrent "
        "802.15.4/Thread/Matter/Zigbee; WBA adds LE Audio.",
        {"status": "Qualified", "note": "STM32WB/WBA releases carry per-version QDIDs; verify the current listing.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "data_length_ext", "afh",
         "mesh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "cpp", "pxp", "fmp",
         "cts", "ans", "ots", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["a2dp", "avrcp", "hfp", "spp", "hid", "channel_sounding", "hap"],
        ["LE-only -- no Classic BR/EDR audio/serial.",
         "Channel Sounding not part of the current WB/WBA feature set.",
         "LE Audio is WBA-family; the older WB line does not have it."],
        "Cost-sensitive LE + mesh + Thread/Matter designs already standardized on STM32/STM32Cube.",
        [{"label": "STM32CubeWBA", "url": "https://www.st.com/en/embedded-software/stm32cubewba.html"}],
    ),
    _stack(
        "espressif-bt", "Espressif ESP-IDF Bluetooth (Bluedroid / NimBLE)", "Espressif",
        "Silicon-Vendor Stacks (commercial)", "Apache-2.0 SDK (bundles Bluedroid & NimBLE)", "Bluetooth 5.4 / LE Audio (ESP32-C5/C6 class)",
        "ESP32 SDK offering both a Classic+LE host (Bluedroid) and an LE-only host (NimBLE).",
        "Espressif's ESP-IDF ships two selectable Bluetooth hosts: Bluedroid (dual-mode, Classic + LE) and Apache "
        "NimBLE (LE-only, smaller). Massive maker/OEM adoption thanks to low cost and Wi-Fi coexistence. Classic audio "
        "(A2DP/HFP) exists on original ESP32; newer C-series parts are LE-only with LE Audio arriving on the newest silicon.",
        {"status": "Qualified", "note": "Espressif publishes Bluetooth QDIDs per chip/IDF release; verify the target part.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "le_power_control", "data_length_ext", "afh", "mesh",
         "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "spp", "hid", "hogp", "bas", "dis", "hrp", "esp"],
        ["bap", "cap", "tmap", "hap", "channel_sounding", "pbap", "map"],
        ["Classic audio (A2DP/HFP) is only on the original ESP32; the popular C3/C6 parts are LE-only.",
         "LE Audio profile stack (BAP/CAP/TMAP) is still maturing and part-dependent.",
         "No Channel Sounding."],
        "Cost-driven IoT and maker products that want Wi-Fi + Bluetooth on one cheap SoC.",
        [{"label": "ESP-IDF Bluetooth", "url": "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/bluetooth.html"}],
    ),
    _stack(
        "qualcomm-bt", "Qualcomm Bluetooth Stack (QCC / Snapdragon Sound)", "Qualcomm",
        "Silicon-Vendor Stacks (commercial)", "Proprietary", "Bluetooth 5.4 / LE Audio",
        "Dual-mode stack across QCC audio SoCs and Snapdragon platforms; strong in premium audio.",
        "Qualcomm's Bluetooth stack spans QCC-series earbud/headset SoCs and Snapdragon mobile/compute platforms. "
        "It is a premium-audio leader (aptX family, Snapdragon Sound, early LE Audio + Auracast) with deep phone-side "
        "integration on Android devices using Snapdragon.",
        {"status": "Qualified", "note": "Per-platform QDIDs; verify the specific QCC/Snapdragon listing.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "eatt", "l2cap_coc", "le_iso", "lc3",
         "le_audio_core", "auracast", "le_power_control", "connection_subrating", "afh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "hid", "hogp", "bas", "dis",
         "bap", "cap", "csip", "vcp", "micp", "mcp", "ccp", "tmap", "gmap"],
        ["hap", "channel_sounding", "pawr"],
        ["Closed ecosystem -- best value comes when both endpoints are Qualcomm (Snapdragon Sound).",
         "aptX advantages depend on the phone side also being Qualcomm."],
        "Premium true-wireless earbuds/headsets and Android flagships prioritizing audio quality and latency.",
        [{"label": "Snapdragon Sound", "url": "https://www.qualcomm.com/products/features/snapdragon-sound"}],
    ),
    _stack(
        "realtek-bt", "Realtek Bluetooth Stack", "Realtek",
        "Silicon-Vendor Stacks (commercial)", "Proprietary", "Bluetooth 5.3 / LE Audio (newer parts)",
        "High-volume dual-mode stack in combo Wi-Fi/BT chips and audio SoCs.",
        "Realtek's Bluetooth stack ships in enormous volume inside its Wi-Fi/BT combo chips (PCs, TVs, IoT) and "
        "dedicated audio SoCs. Dual-mode with Classic audio; LE Audio is arriving on newer parts. Chosen mainly on "
        "cost and combo integration rather than leading-edge feature timing.",
        {"status": "Qualified", "note": "Per-part QDIDs; verify the specific Realtek chip listing.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "eatt", "l2cap_coc", "le_iso", "lc3",
         "le_audio_core", "le_power_control", "afh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "hid", "hogp", "bas", "dis", "bap", "cap", "tmap"],
        ["channel_sounding", "hap", "gmap", "pawr"],
        ["Newest LE features (Channel Sounding, latest LE Audio profiles) typically lag the market leaders.",
         "Documentation and direct developer support are lighter than the top-tier vendors."],
        "High-volume, cost-sensitive PC/TV/combo and mainstream audio designs.",
        [{"label": "Realtek Bluetooth", "url": "https://www.realtek.com/"}],
    ),
    _stack(
        "microchip-blusdk", "Microchip BluSDK / Harmony Bluetooth", "Microchip",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (Harmony/BluSDK)", "Bluetooth 5.x",
        "LE and dual-mode stacks across Microchip/Atmel wireless parts.",
        "Microchip offers Bluetooth via BluSDK and MPLAB Harmony across its wireless MCUs and modules (including the "
        "former Atmel and legacy WBZ/PIC32CX-BZ families). Coverage is solid for mainstream LE (and Classic on combo "
        "parts) but tends to trail the leaders on the newest LE Audio and BT 6.0 features.",
        {"status": "Qualified", "note": "Per-part/per-SDK QDIDs; verify the specific Microchip listing.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "l2cap_coc", "le_power_control",
         "data_length_ext", "afh", "mesh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "spp", "hid", "hogp", "bas", "dis", "hrp", "esp"],
        ["bap", "cap", "tmap", "hap", "le_audio_core", "channel_sounding"],
        ["LE Audio and Channel Sounding are generally not available across the current mainstream parts.",
         "Feature timing trails Nordic/TI/Silicon Labs on new LE additions."],
        "Existing Microchip/PIC/AVR designs adding mainstream LE connectivity within one toolchain.",
        [{"label": "MPLAB Harmony", "url": "https://www.microchip.com/en-us/tools-resources/develop/mplab-harmony"}],
    ),
    _stack(
        "renesas-smartbond", "Renesas / Dialog SmartBond SDK", "Renesas (Dialog)",
        "Silicon-Vendor Stacks (commercial)", "Proprietary (SmartBond SDK)", "Bluetooth 5.3 / LE Audio (DA1470x class)",
        "Ultra-low-power LE stack for the DA145xx/DA1469x/DA1470x SmartBond parts.",
        "The SmartBond SDK from Renesas (via Dialog) targets famously low-power LE SoCs used heavily in wearables, "
        "styluses, remotes and beacons. LE-only, strong power numbers; newer DA1470x-class parts add LE Audio.",
        {"status": "Qualified", "note": "Per-part/per-SDK QDIDs; verify the specific SmartBond listing.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "le_privacy", "gatt", "gatt_caching", "l2cap_coc", "le_iso", "lc3",
         "le_audio_core", "le_power_control", "data_length_ext", "afh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "cpp", "pxp", "fmp", "cts", "bap", "cap", "tmap"],
        ["a2dp", "avrcp", "hfp", "spp", "hid", "channel_sounding", "hap", "mesh"],
        ["LE-only -- no Classic BR/EDR.",
         "No Channel Sounding in the current mainstream parts.",
         "Bluetooth Mesh is not the platform's focus."],
        "Battery-critical wearables, active styluses, remotes and beacons where microamps decide the design.",
        [{"label": "SmartBond SDK", "url": "https://www.renesas.com/en/products/wireless-connectivity/bluetooth-low-energy"}],
    ),

    # =====================================================================
    # Independent / licensable stacks
    # =====================================================================
    _stack(
        "opensynergy-bluesdk", "OpenSynergy Blue SDK", "OpenSynergy",
        "Independent / Licensable Stacks", "Commercial license (source)", "Bluetooth 5.x dual-mode",
        "Portable, silicon-independent dual-mode stack widely licensed in automotive.",
        "Blue SDK is a highly portable, OS- and chip-independent dual-mode Bluetooth stack licensed as source. It is a "
        "long-standing choice for automotive infotainment and embedded systems that need the full Classic profile set "
        "(HFP/PBAP/MAP/A2DP/AVRCP) plus LE, running on the customer's own silicon and RTOS/Linux. OpenSynergy pairs it "
        "with profile packages and a qualification program.",
        {"status": "Qualified (licensable)", "note": "OpenSynergy provides Bluetooth qualification support; listings are per integrated product. Verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "le_power_control", "data_length_ext", "afh", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "map", "opp", "pan", "dip",
         "hid", "hogp", "bas", "dis", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["channel_sounding", "hap", "gmap", "mesh"],
        ["It is a host stack -- you bring a qualified controller/radio; it does not include silicon.",
         "Bluetooth Mesh is not its focus.",
         "Channel Sounding depends on the chosen controller's capability."],
        "Automotive and embedded OEMs needing a portable, fully-profiled dual-mode stack on their own silicon and OS.",
        [{"label": "OpenSynergy Blue SDK", "url": "https://www.opensynergy.com/blue-sdk/"}],
    ),
    _stack(
        "ethermind", "Mindtree EtherMind Bluetooth Stack", "Mindtree / LTTS",
        "Independent / Licensable Stacks", "Commercial license (source)", "Bluetooth 5.x dual-mode / LE Audio",
        "One of the most-licensed embedded Bluetooth stacks; the IP behind many vendor SDKs.",
        "EtherMind is a widely-licensed, portable dual-mode host (and controller) stack that has been embedded, "
        "sometimes under other names, inside numerous silicon-vendor SDKs. Full Classic + LE profile coverage, LE Audio, "
        "and a mature qualification pedigree. If you have used several different vendors' BLE SDKs, you may have used "
        "EtherMind without knowing it.",
        {"status": "Qualified (licensable)", "note": "Qualification support provided; listings appear under integrator products. Verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "data_length_ext", "afh", "mesh",
         "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "map", "hid", "hogp",
         "bas", "dis", "hrp", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap", "hap"],
        ["channel_sounding", "gmap"],
        ["Delivered as licensable IP -- you integrate it onto your silicon/OS rather than buying a chip.",
         "Channel Sounding availability depends on the paired controller."],
        "Silicon vendors and OEMs that want a proven, fully-featured stack to embed and re-brand.",
        [{"label": "LTTS EtherMind", "url": "https://www.ltts.com/"}],
    ),
    _stack(
        "searan", "Searan / SEARAN Bluetooth Stack", "SEARAN",
        "Independent / Licensable Stacks", "Commercial license (source)", "Bluetooth 5.x dual-mode",
        "Portable dual-mode source stack for custom embedded and automotive integrations.",
        "SEARAN provides a portable dual-mode Bluetooth stack and profiles licensed as source for teams building on "
        "their own silicon/OS. Positioned similarly to Blue SDK/EtherMind for embedded and automotive, with an emphasis "
        "on customization and integration services.",
        {"status": "Qualified (licensable)", "note": "Qualification support for integrated products; verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "l2cap_coc", "le_power_control",
         "data_length_ext", "afh", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "spp", "pbap", "map", "hid", "hogp", "bas", "dis"],
        ["bap", "cap", "tmap", "hap", "le_audio_core", "channel_sounding", "mesh"],
        ["Host stack IP -- you supply the qualified radio/controller.",
         "LE Audio and Channel Sounding depend on the specific licensed configuration and controller.",
         "Smaller ecosystem than the largest licensable stacks."],
        "Custom embedded/automotive products wanting a tailorable source stack plus integration help.",
        [{"label": "SEARAN", "url": "https://www.searan.com/"}],
    ),
    _stack(
        "alpwise", "Alpwise Bluetooth LE Stack", "Alpwise",
        "Independent / Licensable Stacks", "Commercial license (source/IP)", "Bluetooth 5.x LE",
        "Licensable LE stack IP for SoC vendors and constrained designs.",
        "Alpwise licenses Bluetooth LE stack and controller IP aimed at semiconductor makers and constrained embedded "
        "designs. It is an ingredient technology -- integrated into chips and modules rather than sold as an end product.",
        {"status": "Qualified (licensable IP)", "note": "Qualification handled at the integrator level; verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "le_secure_connections",
         "le_privacy", "gatt", "l2cap_coc", "le_power_control", "data_length_ext", "afh", "controller_only", "host_only"],
        ["gap", "gatt_profile", "hogp", "hrp", "bas", "dis", "esp", "pxp", "fmp"],
        ["a2dp", "hfp", "spp", "bap", "cap", "tmap", "hap", "le_audio_core", "channel_sounding", "mesh"],
        ["LE-only IP -- no Classic BR/EDR.",
         "LE Audio / Channel Sounding depend on the licensed configuration.",
         "Not an off-the-shelf product; it is IP for integrators."],
        "Chip/module vendors needing licensable LE IP to embed into their own silicon.",
        [{"label": "Alpwise", "url": "https://www.alpwise.com/"}],
    ),

    # =====================================================================
    # Open-source stacks
    # =====================================================================
    _stack(
        "zephyr-bt", "Zephyr Bluetooth Host", "Zephyr Project (Linux Foundation)",
        "Open-Source Stacks", "Apache-2.0 (open source)", "Bluetooth 5.4 / 6.0 features landing",
        "Portable open-source host+controller used across many MCU vendors.",
        "Zephyr's Bluetooth subsystem is a full, portable open-source stack (host + optional controller) that runs on "
        "dozens of MCUs. It is the upstream basis for several vendor SDKs (notably Nordic's nRF Connect SDK) and moves "
        "fast on new features -- LE Audio, and Channel Sounding support is landing. Trade-off: you own the integration, "
        "qualification and maintenance.",
        {"status": "Qualifiable", "note": "Open source ships as source; you qualify your product build. Nordic and others publish qualified builds derived from Zephyr.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past", "pawr",
         "le_secure_connections", "le_privacy", "encrypted_adv_data", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "channel_sounding", "le_power_control",
         "connection_subrating", "data_length_ext", "channel_selection_2", "afh", "mesh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "hogp", "hrp", "htp", "bas", "dis", "esp", "cscp", "rscp", "cpp",
         "pxp", "fmp", "ias", "cts", "ans", "ots", "ipsp", "bap", "cap", "csip", "vcp", "micp", "mcp", "ccp", "tmap", "hap"],
        ["a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "map", "hid"],
        ["No Classic BR/EDR profiles -- LE-only (no A2DP/HFP/SPP).",
         "You own qualification, integration and long-term maintenance; there is no single-vendor SLA.",
         "Newest features are 'landing' -- maturity varies by driver/SoC."],
        "Teams wanting cross-vendor firmware reuse, deep customization and no per-unit license fee.",
        [{"label": "Zephyr Bluetooth", "url": "https://docs.zephyrproject.org/latest/connectivity/bluetooth/index.html"}],
    ),
    _stack(
        "bluez", "BlueZ", "BlueZ / Linux",
        "Open-Source Stacks", "GPL/LGPL (open source)", "Bluetooth 5.x dual-mode",
        "The official Linux Bluetooth stack -- dual-mode, host-side, ubiquitous on Linux.",
        "BlueZ is the default Bluetooth stack on Linux, running on top of any HCI controller. Full dual-mode with a "
        "broad Classic + LE profile set and D-Bus APIs. It is everywhere Linux is -- gateways, edge computers, "
        "infotainment, robots -- but it is a Linux-host stack, not an RTOS/MCU stack.",
        {"status": "Qualifiable", "note": "Product qualification is done at the integrated-product level; many shipping Linux devices carry their own listings.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "data_length_ext", "afh", "mesh",
         "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "map", "pan", "opp", "dip",
         "hid", "hogp", "bas", "dis", "hrp", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["channel_sounding", "hap", "gmap"],
        ["Needs a Linux-class host -- not for tiny MCU-only endpoints.",
         "LE Audio support is comparatively recent and evolving.",
         "No Channel Sounding support yet."],
        "Linux gateways, edge computers and infotainment where Linux is already the system baseline.",
        [{"label": "BlueZ", "url": "https://www.bluez.org/"}],
    ),
    _stack(
        "nimble", "Apache NimBLE (Mynewt)", "Apache Software Foundation",
        "Open-Source Stacks", "Apache-2.0 (open source)", "Bluetooth 5.x LE",
        "Compact open-source LE host (and controller) for constrained MCUs.",
        "Apache NimBLE is a small-footprint, open-source LE host with an optional controller, part of Apache Mynewt "
        "and bundled by Espressif's ESP-IDF and others. It is a favorite for memory-constrained LE endpoints where "
        "size and a permissive license matter.",
        {"status": "Qualifiable", "note": "Qualification at the product level; several shipping products use NimBLE. Verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "le_privacy", "gatt", "gatt_caching", "l2cap_coc", "le_power_control",
         "data_length_ext", "afh", "mesh", "controller_only", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "hogp", "hrp", "bas", "dis", "esp", "pxp", "fmp", "cts", "ots"],
        ["a2dp", "hfp", "spp", "bap", "cap", "tmap", "hap", "le_audio_core", "channel_sounding"],
        ["LE-only -- no Classic BR/EDR.",
         "No LE Audio profile stack (no BAP/CAP).",
         "No Channel Sounding; you own qualification and maintenance."],
        "Ultra-low-resource LE endpoints wanting a compact, permissively-licensed host.",
        [{"label": "Apache NimBLE", "url": "https://mynewt.apache.org/latest/network/index.html"}],
    ),
    _stack(
        "btstack", "BTstack (BlueKitchen)", "BlueKitchen",
        "Open-Source Stacks", "Dual license (free non-commercial / commercial)", "Bluetooth 5.x dual-mode",
        "Clean, portable dual-mode stack popular for custom firmware and prototyping.",
        "BTstack from BlueKitchen is a highly portable dual-mode stack with a clean architecture, free for "
        "non-commercial use and commercially licensed for products. It supports a surprising breadth of Classic + LE "
        "profiles for its size and runs on everything from tiny MCUs to Raspberry Pi Pico, making it a go-to for "
        "custom and research firmware.",
        {"status": "Qualifiable / licensable", "note": "Commercial products license BTstack and qualify per product; BlueKitchen supports qualification. Verify via the SIG site.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "l2cap_coc", "le_iso", "lc3",
         "le_audio_core", "le_power_control", "data_length_ext", "afh", "mesh", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "hid", "hogp", "bas", "dis",
         "hrp", "bap", "cap", "tmap"],
        ["channel_sounding", "hap", "gmap", "map"],
        ["Requires stronger in-house Bluetooth expertise to productionize.",
         "Smaller ecosystem than mainstream vendor stacks.",
         "No Channel Sounding."],
        "Engineering-led products and research needing a tailorable, portable stack across many hosts.",
        [{"label": "BTstack", "url": "https://github.com/bluekitchen/btstack"}],
    ),
    _stack(
        "bumble", "Google Bumble", "Google",
        "Open-Source Stacks", "Apache-2.0 (open source)", "Bluetooth 5.x dual-mode (host)",
        "Python-based dual-mode host stack for testing, tooling and prototyping.",
        "Bumble is Google's open-source, Python-based Bluetooth host stack. It is aimed at testing, virtualization, "
        "automation and prototyping rather than shipping in firmware -- it can drive real controllers over HCI or run "
        "fully virtual, which makes it valuable for building test harnesses and reproducing interop issues.",
        {"status": "Not a product stack", "note": "A development/test tool, not intended for qualified end products.", "verify": "https://github.com/google/bumble"},
        ["br_edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "le_privacy", "gatt", "l2cap_coc", "le_iso", "lc3", "afh", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "spp", "hid", "hogp", "bas", "dis"],
        ["hap", "channel_sounding", "mesh"],
        ["Intended for testing/tooling, not for shipping in production firmware.",
         "Runs in Python -- not for constrained embedded targets."],
        "Engineers building Bluetooth test automation, virtual peers and interop-debug harnesses.",
        [{"label": "Bumble", "url": "https://github.com/google/bumble"}],
    ),

    # =====================================================================
    # OS-native stacks
    # =====================================================================
    _stack(
        "android-bt", "Android Bluetooth Stack (Fluoride / Gabeldorsche)", "Google / AOSP",
        "OS-Native Stacks", "AOSP (open source, platform)", "Bluetooth 5.x dual-mode / LE Audio",
        "The stack on billions of Android phones -- dual-mode with LE Audio and ASHA.",
        "Android's Bluetooth stack (historically Fluoride/'Bluedroid', modernizing toward Gabeldorsche) is deeply "
        "integrated with the Android framework and ships on billions of devices. Dual-mode, with LE Audio and the "
        "Google-specific ASHA hearing-aid protocol. As a phone-side stack it defines what accessories must interoperate with.",
        {"status": "Qualified (per device)", "note": "Each Android handset carries its own qualification; the stack is validated as part of the device.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "auracast", "le_power_control", "afh", "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pbap", "map", "pan", "opp", "dip",
         "hid", "hogp", "bas", "dis", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap", "asha"],
        ["hap", "channel_sounding", "gmap"],
        ["It is a phone/tablet OS stack -- not a drop-in RTOS stack for MCU peripherals.",
         "Feature availability varies by handset OEM and Android version.",
         "No standardized Channel Sounding exposure yet across devices."],
        "Phone-side reference for accessory makers -- what your product must interoperate with on Android.",
        [{"label": "AOSP Bluetooth", "url": "https://source.android.com/docs/core/connect/bluetooth"}],
    ),
    _stack(
        "apple-corebluetooth", "Apple CoreBluetooth (iOS / macOS)", "Apple",
        "OS-Native Stacks", "Proprietary (platform)", "Bluetooth 5.x dual-mode / LE Audio",
        "Apple's platform stack behind iPhone/iPad/Mac; defines the Apple accessory experience.",
        "Apple's Bluetooth stack, exposed to developers via CoreBluetooth (LE) and higher-level frameworks, ships on "
        "all iPhones/iPads/Macs. Dual-mode with proprietary extensions (ANCS notifications, AirPods pairing, Find My, "
        "and its own LE Audio rollout). For accessory makers it is the other must-interoperate-with phone platform.",
        {"status": "Qualified (per device)", "note": "Each Apple device is qualified as a product; the stack is validated within the device.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv", "past",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "gatt_caching", "eatt", "l2cap_coc",
         "le_iso", "lc3", "le_audio_core", "le_power_control", "afh", "host_only"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "pbap", "map", "hid", "hogp", "bas", "dis",
         "ans", "cts", "bap", "cap", "csip", "vcp", "mcp", "ccp", "tmap"],
        ["spp", "hap", "channel_sounding", "gmap"],
        ["Classic SPP is not exposed to third parties (Apple uses MFi/iAP or LE instead).",
         "Many capabilities are gated behind Apple frameworks (ANCS, Find My, MFi) rather than raw Bluetooth APIs.",
         "No third-party Channel Sounding exposure."],
        "Phone-side reference for accessory makers -- what your product must interoperate with on iOS/macOS.",
        [{"label": "CoreBluetooth", "url": "https://developer.apple.com/documentation/corebluetooth"}],
    ),
    _stack(
        "windows-bt", "Windows Bluetooth Stack (Microsoft / WinRT)", "Microsoft",
        "OS-Native Stacks", "Proprietary (platform)", "Bluetooth 5.x dual-mode",
        "The Windows platform stack, exposed via WinRT/UWP APIs on PCs.",
        "Microsoft's in-box Bluetooth stack drives Windows PCs over standard HCI controllers, exposed through WinRT "
        "APIs (GATT client/server, RFCOMM, advertising). Dual-mode with broad Classic accessory support; LE Audio "
        "support is progressing in newer Windows releases. It is the PC-side interoperability target.",
        {"status": "Qualified (per device/OS)", "note": "PCs and the OS stack are validated at the product/platform level.", "verify": _QUAL_SEARCH},
        ["br_edr", "edr", "le_1m_phy", "le_2m_phy", "le_coded_phy", "adv_extensions", "periodic_adv",
         "le_secure_connections", "sc_classic", "le_privacy", "gatt", "l2cap_coc", "le_audio_core", "afh",
         "host_only", "hci_transport"],
        ["gap", "gatt_profile", "a2dp", "avrcp", "hfp", "hsp", "spp", "pan", "opp", "hid", "hogp", "bas", "dis"],
        ["pbap", "map", "hap", "channel_sounding", "auracast", "gmap"],
        ["LE Audio / Auracast support is still maturing in Windows.",
         "Some profiles (PBAP/MAP) are not first-class in the platform APIs.",
         "No Channel Sounding exposure."],
        "PC-side reference for accessory makers and any product that must pair cleanly with Windows.",
        [{"label": "Windows Bluetooth (WinRT)", "url": "https://learn.microsoft.com/en-us/windows/uwp/devices-sensors/bluetooth"}],
    ),
]
