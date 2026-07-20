"""Hand-crafted application/market-research content for the Applications page.

Static, editorial content (not news-driven). For each end-application we track:
  - a short block diagram (system layers) plus a "zoom" into the wireless radios used
  - a 15-year market-size trend (5y history + 10y forecast) rendered as an inline SVG
  - which wireless features are mandatory / good-to-have / future-looking
  - which silicon vendors are positioned to win the wireless content in that device

Market figures are directional estimates synthesized from public secondary research
(Grand View Research, Fortune Business Insights, MarketsandMarkets, IDC, Counterpoint,
ABI Research and similar syndicated reports) as of 2024-2025. They are meant to guide
product-marketing prioritization, not to be quoted as audited figures -- see the
disclaimer rendered on the page itself.
"""
from __future__ import annotations


def _num(v: float) -> str:
    return f"{v:.1f}" if v < 10 else f"{v:.0f}"


def market_svg(history: list[tuple[int, float]], forecast: list[tuple[int, float]]) -> str:
    """Render a small, dependency-free line chart: solid history + dashed forecast."""
    pts = history + forecast
    n = len(pts)
    w, h = 660, 210
    pad_l, pad_r, pad_t, pad_b = 46, 16, 16, 26
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    vmax = max(v for _, v in pts) * 1.15 or 1.0

    def x(i: int) -> float:
        return pad_l + plot_w * i / (n - 1)

    def y(v: float) -> float:
        return pad_t + plot_h - (plot_h * v / vmax)

    hist_line = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(history))
    fc_start = len(history) - 1
    fc_line = " ".join(f"{x(fc_start + i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(forecast))

    grid, ylabels = [], []
    for k in range(5):
        gy = pad_t + plot_h - (plot_h * k / 4)
        gval = vmax * k / 4
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        ylabels.append(f'<text x="{pad_l - 6}" y="{gy + 3:.1f}" text-anchor="end" font-size="9" fill="#64748b">{_num(gval)}</text>')

    xlabels = []
    for i, (yr, _) in enumerate(pts):
        if i % 2 == 0 or i == n - 1:
            xlabels.append(f'<text x="{x(i):.1f}" y="{h - 6}" text-anchor="middle" font-size="9" fill="#64748b">{yr}</text>')

    hist_dots = " ".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.6" fill="#0284c7"/>' for i, (_, v) in enumerate(history))
    fc_dots = " ".join(f'<circle cx="{x(fc_start + i):.1f}" cy="{y(v):.1f}" r="2.6" fill="#94a3b8"/>' for i, (_, v) in enumerate(forecast) if i > 0)
    today_x = x(fc_start)

    return (
        f'<svg viewBox="0 0 {w} {h}" class="mkt-svg" role="img" aria-label="Market size trend">'
        + "".join(grid)
        + f'<line x1="{today_x:.1f}" y1="{pad_t}" x2="{today_x:.1f}" y2="{pad_t + plot_h}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,3"/>'
        + f'<text x="{today_x:.1f}" y="{pad_t - 4}" text-anchor="middle" font-size="9" font-weight="700" fill="#b45309">now</text>'
        + f'<polyline points="{hist_line}" fill="none" stroke="#0284c7" stroke-width="2.2"/>'
        + f'<polyline points="{fc_line}" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-dasharray="5,4"/>'
        + hist_dots + fc_dots
        + "".join(ylabels) + "".join(xlabels)
        + "</svg>"
    )


def _cagr(v0: float, v1: float, years: int) -> str:
    rate = (v1 / v0) ** (1 / years) - 1
    return f"{rate * 100:.0f}%"


def _app(slug, label, category, tagline, overview, diagram, radios, unit, history, forecast, features, vendors):
    hist_first, hist_last = history[0][1], history[-1][1]
    fc_last = forecast[-1][1]
    return {
        "slug": slug, "label": label, "category": category, "tagline": tagline, "overview": overview,
        "diagram": diagram, "radios": radios, "unit": unit,
        "size_now": f"{_num(hist_last)}", "size_now_year": history[-1][0],
        "size_future": f"{_num(fc_last)}", "size_future_year": forecast[-1][0],
        "cagr_hist": _cagr(hist_first, hist_last, history[-1][0] - history[0][0]),
        "cagr_fwd": _cagr(hist_last, fc_last, forecast[-1][0] - history[-1][0]),
        "chart": market_svg(history, forecast),
        "features": features, "vendors": vendors,
    }


APP_CATEGORIES = [
    "Wearables & XR",
    "Smart Home & Security",
    "Audio & Entertainment",
    "Robotics",
    "Networking Infrastructure",
    "Automotive",
]


APPLICATIONS: list[dict] = [
    _app(
        "smartwatch", "Smart Watch", "Wearables & XR",
        "The anchor wearable: phone-companion notifications, health sensing, payments and (increasingly) standalone cellular.",
        "Smart watches pair a low-power always-on display and health sensor suite with a phone-companion "
        "app model. BLE carries the bulk of the traffic (notifications, health sync, LE Audio to earbuds); "
        "Wi-Fi and an optional eSIM/LTE modem let premium tiers work untethered from the phone. NFC adds "
        "tap-to-pay, and GNSS adds standalone workout tracking without the phone in-pocket.",
        [
            {"name": "Watch UI / Health Apps", "sub": "Watch face, notifications, workout & health apps, on-device voice assistant", "k": "c1"},
            {"name": "SoC + RTOS", "sub": "Ultra-low-power MCU/AP, sensor hub (HR, SpO2, accelerometer), always-on display controller", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Combo radio die (see zoom below) handling phone sync, standalone data, ranging and payments", "k": "c3"},
            {"name": "Sensors, Battery & Haptics", "sub": "PPG/ECG sensors, haptic motor, multi-day Li-poly cell, wireless charging coil", "k": "c4"},
        ],
        [
            {"name": "Bluetooth LE (+ LE Audio)", "role": "Primary phone-companion link; streams notifications/health data and pairs to LE Audio earbuds."},
            {"name": "Wi-Fi (STA)", "role": "Backup/parallel data path when phone is out of range but a known Wi-Fi AP is in reach; OTA updates."},
            {"name": "NFC", "role": "Contactless payment (Google/Samsung/Apple Pay) and quick pairing."},
            {"name": "GNSS", "role": "Standalone location for run/ride tracking without the phone."},
            {"name": "eSIM LTE/5G (premium tier)", "role": "Untethered calls, streaming and messaging on cellular-capable models."},
        ],
        "US$ Billion",
        [(2020, 18), (2021, 24), (2022, 28), (2023, 32), (2024, 38)],
        [(2025, 45), (2026, 53), (2027, 62), (2028, 72), (2029, 83), (2030, 96), (2031, 110), (2032, 126), (2033, 144), (2034, 164)],
        {
            "mandatory": [
                {"f": "Bluetooth LE 5.2+ / LE Audio", "w": "Table-stakes phone sync plus LC3 codec for LE Audio earbuds and Auracast."},
                {"f": "NFC (ISO 14443)", "w": "Contactless payment is now an expected flagship feature, not a differentiator."},
                {"f": "Coexistence (BLE+Wi-Fi+GNSS on one die)", "w": "Board space and battery are the binding constraints; combo silicon is required."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6 low-power mode (TWT)", "w": "Faster OTA/app sync without materially hurting multi-day battery life."},
                {"f": "UWB ranging", "w": "Precision item-finding and secure unlock use cases some flagships already ship."},
                {"f": "eSIM / RedCap 5G", "w": "Standalone connectivity tier commands a subscription and higher ASP."},
            ],
            "future": [
                {"f": "Satellite SOS (non-terrestrial NR)", "w": "Emergency messaging off-grid, following the smartphone satellite trend."},
                {"f": "Channel Sounding (BT 6.x)", "w": "Secure distance-bound unlock/handoff without a dedicated UWB radio."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon Wear / W5+ Gen 1", "note": "Leads Wear OS reference platforms; strongest at cellular-capable flagship watches."},
            {"company": "Apple (in-house)", "chip": "S-series SiP", "note": "Vertically integrated SiP; sets the bar for combo-radio + sensor-hub power efficiency."},
            {"company": "Infineon AIROC", "chip": "CYW20xxx combo", "note": "BLE/Wi-Fi combo silicon widely used across Android/Samsung and fitness-wearable tiers."},
            {"company": "Nordic Semiconductor", "chip": "nRF54 / nRF52 series", "note": "Dominant in low-cost fitness bands and entry smartwatches on BLE-only designs."},
            {"company": "MediaTek", "chip": "MT2xxx wearable SoC", "note": "Value-tier Android watches, strong in China/India OEM designs."},
            {"company": "Broadcom", "chip": "BCM4xxx combo", "note": "Long-standing combo-chip supplier inside premium smartwatch platforms."},
        ],
    ),
    _app(
        "smartglasses", "Smart Glasses", "Wearables & XR",
        "Camera- and audio-first glasses (Ray-Ban Meta style) — the lightweight, all-day sibling of AR headsets.",
        "Smart glasses prioritize weight and battery life over compute, so most intelligence (voice assistant, "
        "photo/video processing) happens on the paired phone or in the cloud. The glasses themselves are "
        "essentially a BLE+Wi-Fi accessory with a camera, open-ear speakers and mic array; heavier optical "
        "waveguide/AR variants add a dedicated display and start converging with the AR/VR/MR category.",
        [
            {"name": "Capture & Audio UX", "sub": "Camera capture, open-ear audio, voice-assistant wake word, LED privacy indicator", "k": "c1"},
            {"name": "Companion-App Compute", "sub": "Most AI/vision processing offloaded to the paired phone app or cloud", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "BLE control link + Wi-Fi Direct high-bandwidth media offload (see zoom)", "k": "c3"},
            {"name": "Optics, Battery & Frame", "sub": "Camera module, small day-long battery in the temple, optional waveguide display", "k": "c4"},
        ],
        [
            {"name": "Bluetooth LE", "role": "Low-power control channel: pairing, settings, voice-assistant trigger, telemetry."},
            {"name": "Wi-Fi Direct / Aware", "role": "High-bandwidth burst offload of photos/video clips to the phone without cloud round-trip."},
            {"name": "LE Audio / Auracast", "role": "Open-ear audio streaming and, on some models, broadcast audio reception."},
        ],
        "US$ Billion",
        [(2020, 1.2), (2021, 1.6), (2022, 2.1), (2023, 2.8), (2024, 3.8)],
        [(2025, 5.2), (2026, 7.0), (2027, 9.3), (2028, 12.2), (2029, 15.8), (2030, 20.2), (2031, 25.5), (2032, 31.8), (2033, 39.2), (2034, 47.8)],
        {
            "mandatory": [
                {"f": "Bluetooth LE 5.x", "w": "Baseline control link for pairing and low-rate telemetry with minimal power draw."},
                {"f": "Wi-Fi Direct (P2P)", "w": "Media-sized transfers (photo/video) are impractical over BLE alone."},
                {"f": "LE Audio (LC3)", "w": "Efficient, higher-quality open-ear audio inside a very small power budget."},
            ],
            "good_to_have": [
                {"f": "Auracast receive", "w": "Tune into public broadcast audio (venues, kiosks) without pairing."},
                {"f": "Wi-Fi 6E offload", "w": "Faster cloud sync for AI features (live translation, visual search) when near an AP."},
            ],
            "future": [
                {"f": "On-glasses RedCap 5G", "w": "Cloud-AI features without depending on the phone's tether."},
                {"f": "UWB for spatial anchoring", "w": "Precise device-to-device handoff as glasses gain waveguide displays."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon AR1 Gen 1", "note": "Reference SoC behind Ray-Ban Meta and most camera-glasses designs."},
            {"company": "Nordic Semiconductor", "chip": "nRF53 series", "note": "Dual-core BLE MCU commonly used for the low-power control/audio path."},
            {"company": "Infineon AIROC", "chip": "CYW20xxx combo", "note": "BLE+Wi-Fi combo for designs needing Wi-Fi Direct offload in one die."},
            {"company": "Synaptics", "chip": "Astra SL18xx", "note": "Edge-AI + connectivity combo pitched specifically at AI glasses."},
            {"company": "Espressif", "chip": "ESP32-C6", "note": "Low-cost Wi-Fi 6 + BLE combo used in smaller-brand smart glasses."},
        ],
    ),
    _app(
        "arvrmr", "AR/VR/MR Headset", "Wearables & XR",
        "Standalone mixed-reality headsets — the highest wireless-bandwidth wearable, bridging to 6 GHz Wi-Fi and cellular XR.",
        "Standalone MR headsets (Quest, Vision Pro-class) run full compute onboard but still lean on wireless "
        "for controller tracking, PC/console streaming (Wi-Fi 6E/7), and companion accessories. Low-latency, "
        "high-throughput links matter more here than in any other wearable category, making 6 GHz Wi-Fi and "
        "UWB/BLE-based controller tracking first-class requirements rather than nice-to-haves.",
        [
            {"name": "Immersive UX", "sub": "Passthrough/AR overlay, hand & eye tracking UI, spatial app runtime", "k": "c1"},
            {"name": "Onboard SoC + GPU", "sub": "High-performance AP with dedicated vision/AI accelerators for SLAM and passthrough", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Multi-radio combo: Wi-Fi 6E/7, BLE for controllers, UWB/optical for tracking (zoom below)", "k": "c3"},
            {"name": "Optics, Sensors & Battery", "sub": "Pancake lenses, IMU/eye/hand cameras, hot-swappable battery pack", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi 6E/7 (6 GHz)", "role": "Wireless PC/console streaming (Air Link-class) needs uncongested, high-throughput spectrum."},
            {"name": "Bluetooth LE", "role": "Controller pairing, haptics link, low-rate accessory telemetry."},
            {"name": "UWB / IR / optical tracking", "role": "Sub-cm controller and boundary tracking latency that BLE alone can't guarantee."},
        ],
        "US$ Billion",
        [(2020, 12), (2021, 18), (2022, 22), (2023, 26), (2024, 32)],
        [(2025, 40), (2026, 50), (2027, 63), (2028, 79), (2029, 98), (2030, 121), (2031, 148), (2032, 179), (2033, 214), (2034, 254)],
        {
            "mandatory": [
                {"f": "Wi-Fi 6E (6 GHz)", "w": "Only realistic band for stutter-free wireless PC-streamed VR given 2.4/5 GHz congestion."},
                {"f": "Bluetooth LE 5.x", "w": "Controller and accessory pairing baseline across every platform."},
                {"f": "Low-latency proprietary 2.4 GHz link (controllers)", "w": "Sub-5ms controller polling still often uses a proprietary link, not BLE, for competitive titles."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 7 (MLO)", "w": "Multi-link operation further cuts streaming latency/jitter for premium tethered-free PCVR."},
                {"f": "UWB precision tracking", "w": "Improves boundary and multi-headset co-location tracking accuracy."},
            ],
            "future": [
                {"f": "On-device 5G RedCap/mmWave", "w": "Untethered cloud-rendered AR/VR without a home Wi-Fi dependency."},
                {"f": "60 GHz WiGig short-hop", "w": "Multi-gigabit local streaming for uncompressed passthrough/AR video."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon XR2 Gen 2", "note": "Reference silicon behind Quest 3/3S and most Android-based standalone headsets."},
            {"company": "Apple (in-house)", "chip": "R1 co-processor + M-series", "note": "Dedicated R1 chip purely for low-latency sensor/wireless I/O in Vision Pro."},
            {"company": "Broadcom", "chip": "BCM4389/6 combo", "note": "Wi-Fi 6E/7 + BLE combo used in premium headset reference designs."},
            {"company": "MediaTek", "chip": "XR SoC platforms", "note": "Positioned for value/mid-tier standalone headsets, especially in China."},
            {"company": "Qorvo", "chip": "UWB + Wi-Fi FEM", "note": "RF front-end and UWB ranging components for precision controller tracking."},
        ],
    ),

    _app(
        "doorlock", "Video Doorbell / Smart Door Lock", "Smart Home & Security",
        "The entry point of the smart home — Matter's flagship use case, bridging Wi-Fi video with Thread-based locks.",
        "Video doorbells need sustained Wi-Fi bandwidth for streaming and cloud clips, while smart locks "
        "prioritize ultra-low-power mesh (Thread/Zigbee) for instant, battery-friendly response. Matter over "
        "Thread has become the interoperability layer of choice for locks, while doorbells remain mostly "
        "Wi-Fi-only due to their higher power/bandwidth needs and mains or high-capacity battery power.",
        [
            {"name": "App & Notifications", "sub": "Live view, motion/person alerts, remote lock/unlock, guest access codes", "k": "c1"},
            {"name": "Edge Compute", "sub": "On-device person/package detection, local video buffer, secure element for keys", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi for video doorbells; Thread/Zigbee/BLE for locks (zoom below)", "k": "c3"},
            {"name": "Actuator, Camera & Battery", "sub": "Motor/deadbolt or camera+IR, battery or mains power, tamper sensor", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (2.4/5 GHz)", "role": "Video doorbell streaming and cloud upload; needs sustained throughput."},
            {"name": "Thread (802.15.4)", "role": "Low-power mesh for battery locks; Matter's preferred transport for locks/sensors."},
            {"name": "Bluetooth LE", "role": "Commissioning (in-app QR pairing), local proximity unlock, out-of-band setup."},
            {"name": "Zigbee (legacy installs)", "role": "Still shipped for backward compatibility with existing hub ecosystems."},
        ],
        "US$ Billion",
        [(2020, 3.2), (2021, 4.0), (2022, 4.9), (2023, 5.9), (2024, 7.1)],
        [(2025, 8.5), (2026, 10.1), (2027, 11.9), (2028, 13.9), (2029, 16.2), (2030, 18.7), (2031, 21.5), (2032, 24.6), (2033, 28.0), (2034, 31.7)],
        {
            "mandatory": [
                {"f": "Matter over Thread (locks)", "w": "Cross-ecosystem support (Apple Home/Google Home/Alexa) is now a purchase-decision checkbox."},
                {"f": "Wi-Fi 4/5 dual-band (doorbells)", "w": "Reliable streaming from garages/porches at the edge of home Wi-Fi coverage."},
                {"f": "BLE commissioning", "w": "Standard QR/BLE onboarding flow expected by every major smart-home app."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6 (doorbells)", "w": "Better performance in dense multi-device homes, longer battery for battery-powered doorbells."},
                {"f": "Thread Border Router built-in (hub)", "w": "Extends Thread mesh coverage without an extra dedicated hub."},
            ],
            "future": [
                {"f": "UWB fine-ranging unlock", "w": "Walk-up-and-unlock without touching phone or key, similar to automotive digital keys."},
                {"f": "Wi-Fi HaLow for wide-yard sensors", "w": "Sub-GHz Wi-Fi extends range to gate/driveway sensors far from the router."},
            ],
        },
        [
            {"company": "Nordic Semiconductor", "chip": "nRF52840 (Thread+BLE)", "note": "Leading Thread SoC choice for Matter-certified smart locks."},
            {"company": "Silicon Labs", "chip": "MG24 (Thread/Zigbee/BLE)", "note": "Multiprotocol SoC widely used by lock and sensor OEMs for Matter certification."},
            {"company": "Qualcomm", "chip": "QCC/IPQ Wi-Fi platforms", "note": "Wi-Fi camera SoCs powering many video-doorbell reference designs."},
            {"company": "Infineon AIROC", "chip": "CYW43xxx Wi-Fi", "note": "Wi-Fi module supplier across mainstream video doorbell OEMs."},
            {"company": "Espressif", "chip": "ESP32-C6 (Wi-Fi 6 + 802.15.4)", "note": "Cost-effective combo silicon increasingly used in value-tier locks/doorbells."},
        ],
    ),
    _app(
        "securityhub", "Security Hub", "Smart Home & Security",
        "The whole-home security brain — a multi-radio bridge tying sensors, cameras and locks into one monitored system.",
        "A security hub's job is being the most reliable radio in the house: it typically runs Wi-Fi/Ethernet "
        "backhaul to the cloud plus a Zigbee/Z-Wave/Thread radio to talk to dozens of battery sensors, and a "
        "cellular backup so an intruder cutting the internet doesn't disable monitoring. This makes hubs the "
        "most radio-dense device in the smart home.",
        [
            {"name": "Monitoring App & Rules", "sub": "Arm/disarm, event timeline, professional-monitoring integration, automations", "k": "c1"},
            {"name": "Hub Compute", "sub": "Local rules engine, event buffering during outages, secure credential storage", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi/Ethernet backhaul + Zigbee/Z-Wave/Thread mesh + cellular backup (zoom below)", "k": "c3"},
            {"name": "Siren, Battery Backup & I/O", "sub": "Onboard siren, backup battery, wired panel/keypad interfaces", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi / Ethernet", "role": "Primary backhaul to the monitoring cloud and mobile app."},
            {"name": "Zigbee / Z-Wave", "role": "Mesh to legacy door/window/motion sensors — still the largest installed base."},
            {"name": "Thread (Matter Border Router)", "role": "Newer sensors and locks increasingly ship Matter/Thread instead of Zigbee."},
            {"name": "Cellular (LTE-M/CAT-1)", "role": "Backup uplink so cutting the home internet/power doesn't disable monitoring."},
            {"name": "Bluetooth LE", "role": "Keypad/fob pairing and installer commissioning."},
        ],
        "US$ Billion",
        [(2020, 4.5), (2021, 5.3), (2022, 6.1), (2023, 7.0), (2024, 8.1)],
        [(2025, 9.3), (2026, 10.7), (2027, 12.2), (2028, 13.9), (2029, 15.8), (2030, 17.9), (2031, 20.2), (2032, 22.7), (2033, 25.4), (2034, 28.4)],
        {
            "mandatory": [
                {"f": "Zigbee 3.0 mesh", "w": "Largest installed base of legacy sensors that a new hub still must support."},
                {"f": "Cellular backup (LTE-M/CAT-1)", "w": "Table-stakes for any professionally-monitored security offering."},
                {"f": "Wi-Fi dual-band backhaul", "w": "Primary uplink for events, live video and app control."},
            ],
            "good_to_have": [
                {"f": "Thread Border Router + Matter", "w": "Future-proofs the hub as sensor/lock OEMs migrate away from proprietary Zigbee profiles."},
                {"f": "Z-Wave Long Range", "w": "Extends mesh reach in large homes/multi-building properties for the installed Z-Wave base."},
            ],
            "future": [
                {"f": "Wi-Fi HaLow sub-GHz", "w": "Longer range, lower power sensors covering garages, sheds and perimeters."},
                {"f": "Satellite IoT backup", "w": "Monitoring continuity even when both cellular and Wi-Fi backhaul fail."},
            ],
        },
        [
            {"company": "Silicon Labs", "chip": "EFR32 multiprotocol (Zigbee/Thread/BLE)", "note": "Dominant multiprotocol SoC in professional and DIY security-hub designs."},
            {"company": "Qualcomm", "chip": "IPQ/QCA Wi-Fi + cellular modules", "note": "Wi-Fi and LTE-M modules used in premium/professionally-monitored hubs."},
            {"company": "NXP Semiconductors", "chip": "JN51xx / K32W (Zigbee/Thread)", "note": "Long-standing supplier to security panel OEMs for mesh radios."},
            {"company": "u-blox", "chip": "LTE-M/NB-IoT modules", "note": "Cellular-backup module supplier across alarm-panel and hub OEMs."},
            {"company": "Texas Instruments", "chip": "CC13xx/CC26xx multiprotocol", "note": "Sub-GHz + 2.4 GHz combo used by several panel and sensor makers."},
        ],
    ),
    _app(
        "thermostat", "Smart Thermostat", "Smart Home & Security",
        "The energy-savings poster child — Wi-Fi first, with Matter/Thread adoption accelerating for whole-home HVAC control.",
        "Thermostats are mains-powered (thermostats tap the HVAC transformer), so unlike battery sensors they "
        "default to Wi-Fi for direct cloud connectivity, energy-utility demand-response programs and voice "
        "assistant integration. Matter-over-Wi-Fi and Matter-over-Thread variants are both shipping as OEMs "
        "chase multi-ecosystem certification (Apple Home, Google Home, Amazon Alexa, SmartThings).",
        [
            {"name": "Schedules & Energy App", "sub": "Learning schedules, geofencing, utility demand-response, energy reports", "k": "c1"},
            {"name": "HVAC Control Logic", "sub": "Relay control for heat/cool/fan stages, occupancy & temperature sensing", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi primary, with Thread/Matter for multi-vendor sensor ecosystems (zoom below)", "k": "c3"},
            {"name": "Display, Sensors & Power", "sub": "Color touch display, humidity/occupancy sensors, C-wire or battery-buffered power", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (2.4 GHz)", "role": "Primary and often only radio: cloud connectivity, app control, firmware updates."},
            {"name": "Thread", "role": "Growing option for Matter certification and talking to satellite temperature sensors."},
            {"name": "Bluetooth LE", "role": "In-app setup/commissioning before Wi-Fi credentials are provisioned."},
        ],
        "US$ Billion",
        [(2020, 2.6), (2021, 3.1), (2022, 3.6), (2023, 4.1), (2024, 4.8)],
        [(2025, 5.5), (2026, 6.3), (2027, 7.2), (2028, 8.2), (2029, 9.3), (2030, 10.5), (2031, 11.9), (2032, 13.4), (2033, 15.1), (2034, 17.0)],
        {
            "mandatory": [
                {"f": "Wi-Fi 4/5 (2.4 GHz)", "w": "Universal requirement: every mainstream thermostat is Wi-Fi first for cloud/app control."},
                {"f": "BLE commissioning", "w": "Standard onboarding flow before Wi-Fi credentials are handed over."},
                {"f": "Matter over Wi-Fi", "w": "Multi-ecosystem certification is now a shelf-placement requirement at major retailers."},
            ],
            "good_to_have": [
                {"f": "Thread (satellite sensors)", "w": "Low-power link to remote room-temperature sensors without extra Wi-Fi APs."},
                {"f": "Wi-Fi 6 (low-power mode)", "w": "Better coexistence in dense-device homes without hurting standby power."},
            ],
            "future": [
                {"f": "Wi-Fi HaLow for whole-house sensors", "w": "Sub-GHz reach for basements/detached rooms beyond normal Wi-Fi coverage."},
                {"f": "Grid-aware demand-response signaling", "w": "Direct utility-to-device signaling for real-time grid/carbon-aware setpoints."},
            ],
        },
        [
            {"company": "Infineon AIROC", "chip": "CYW43xxx Wi-Fi", "note": "Widely used Wi-Fi module across leading connected-thermostat brands."},
            {"company": "Espressif", "chip": "ESP32 series", "note": "Popular low-cost Wi-Fi+BLE SoC for value-tier and white-label thermostats."},
            {"company": "Silicon Labs", "chip": "EFR32MG (Thread)", "note": "Thread radio supplier for thermostats adding Matter/satellite-sensor support."},
            {"company": "Qualcomm", "chip": "QCA4xxx Wi-Fi", "note": "Wi-Fi SoC supplier to several premium thermostat and HVAC-control OEMs."},
            {"company": "NXP Semiconductors", "chip": "88W Wi-Fi + Thread combo", "note": "Combo silicon positioned for next-gen Matter-over-Thread thermostats."},
        ],
    ),
    _app(
        "ipcamera", "IP Camera", "Smart Home & Security",
        "Consumer and prosumer network cameras — the highest sustained-throughput radio load in the smart home.",
        "IP cameras stream continuous or motion-triggered video, so Wi-Fi throughput and range dominate the "
        "wireless requirements list; PoE remains common in prosumer/commercial installs. Local (on-device or "
        "hub-based) AI person/vehicle detection is shifting compute to the edge to cut cloud bandwidth and "
        "improve response latency.",
        [
            {"name": "Live View & Alerts App", "sub": "Live stream, event clips, person/vehicle/package AI alerts, two-way audio", "k": "c1"},
            {"name": "Vision Compute", "sub": "On-device NPU for person/object detection, local video buffering (SD/NVR)", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi dual-band primary; PoE Ethernet for prosumer/commercial (zoom below)", "k": "c3"},
            {"name": "Sensor, IR & Power", "sub": "Image sensor, IR/color-night-vision LEDs, PoE or battery + solar panel option", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (dual-band)", "role": "Sustained video upload; 5 GHz preferred where range allows for less 2.4 GHz congestion."},
            {"name": "Ethernet / PoE", "role": "Prosumer and commercial installs prefer wired power+data reliability over Wi-Fi."},
            {"name": "Bluetooth LE", "role": "Setup/commissioning and firmware pairing before Wi-Fi is configured."},
            {"name": "Cellular (battery/solar cams)", "role": "Off-grid battery cameras without a nearby router use LTE-M/CAT-1 backhaul."},
        ],
        "US$ Billion",
        [(2020, 6.8), (2021, 8.0), (2022, 9.2), (2023, 10.6), (2024, 12.2)],
        [(2025, 14.0), (2026, 16.0), (2027, 18.3), (2028, 20.9), (2029, 23.8), (2030, 27.1), (2031, 30.8), (2032, 35.0), (2033, 39.7), (2034, 45.0)],
        {
            "mandatory": [
                {"f": "Wi-Fi 5 dual-band", "w": "Baseline throughput/range needed for reliable HD/QHD continuous or event streaming."},
                {"f": "BLE/Wi-Fi commissioning", "w": "Standard app-guided setup flow expected across every consumer camera brand."},
                {"f": "WPA3", "w": "Camera feeds are a high-value target; WPA3 is now a baseline security requirement."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6/6E", "w": "Better performance in multi-camera households and denser urban RF environments."},
                {"f": "PoE (prosumer/commercial)", "w": "Eliminates battery/Wi-Fi reliability concerns for fixed installations."},
            ],
            "future": [
                {"f": "Wi-Fi HaLow (long-range, low-power)", "w": "Perimeter/driveway/barn cameras far outside normal Wi-Fi and on battery+solar."},
                {"f": "On-camera RedCap 5G", "w": "Backhaul-independent cameras for construction sites and temporary installs."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "QCS/IPQ camera platforms", "note": "Wi-Fi + vision SoC combination widely used across premium IP-camera brands."},
            {"company": "Realtek", "chip": "RTL819x Wi-Fi", "note": "Cost-optimized Wi-Fi SoC supplier for mainstream/value camera OEMs."},
            {"company": "Ambarella", "chip": "CV-series vision SoC", "note": "Leading vision/AI processor paired with third-party Wi-Fi modules."},
            {"company": "Infineon AIROC", "chip": "CYW43xxx Wi-Fi", "note": "Wi-Fi module supplier across several battery and mains-powered camera lines."},
            {"company": "u-blox", "chip": "LTE-M modules", "note": "Cellular backhaul for off-grid solar/battery security cameras."},
        ],
    ),

    _app(
        "speaker", "Portable Speaker", "Audio & Entertainment",
        "The default Bluetooth-audio device — party speakers to pocket speakers, increasingly with Wi-Fi multiroom.",
        "Portable speakers are overwhelmingly Bluetooth Classic (A2DP) devices today, with LE Audio migration "
        "underway for battery efficiency and multi-speaker broadcast (Auracast party mode). Premium multiroom "
        "speakers add Wi-Fi for higher-fidelity streaming and whole-home group playback alongside Bluetooth "
        "for simple, router-free pairing.",
        [
            {"name": "Playback UX", "sub": "EQ, party-mode pairing, voice-assistant wake word, companion app control", "k": "c1"},
            {"name": "Audio DSP", "sub": "Codec decode, active EQ, multi-driver crossover, battery/thermal management", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Bluetooth Classic/LE primary; Wi-Fi on multiroom-capable models (zoom below)", "k": "c3"},
            {"name": "Drivers, Battery & Enclosure", "sub": "Passive radiators, rugged/waterproof housing, multi-hour rechargeable battery", "k": "c4"},
        ],
        [
            {"name": "Bluetooth Classic (A2DP)", "role": "Dominant streaming path today: simple, router-free, universal phone support."},
            {"name": "Bluetooth LE Audio / Auracast", "role": "Emerging: lower power, multi-speaker broadcast \"party mode\" without pairing each unit."},
            {"name": "Wi-Fi (multiroom models)", "role": "Higher-fidelity streaming and synchronized whole-home group playback."},
        ],
        "US$ Billion",
        [(2020, 8.5), (2021, 9.8), (2022, 11.0), (2023, 12.4), (2024, 14.0)],
        [(2025, 15.7), (2026, 17.6), (2027, 19.7), (2028, 22.0), (2029, 24.5), (2030, 27.3), (2031, 30.3), (2032, 33.6), (2033, 37.2), (2034, 41.1)],
        {
            "mandatory": [
                {"f": "Bluetooth Classic A2DP", "w": "Still the universal, zero-setup streaming path every phone supports."},
                {"f": "Bluetooth 5.x (BLE control)", "w": "App-based EQ/firmware control channel alongside the audio streaming link."},
            ],
            "good_to_have": [
                {"f": "LE Audio / Auracast", "w": "Lower power draw and broadcast \"stereo/party pairing\" across many units at once."},
                {"f": "Wi-Fi multiroom (AirPlay/Chromecast/proprietary)", "w": "Whole-home synchronized playback and hi-res streaming beyond Bluetooth's bitrate."},
            ],
            "future": [
                {"f": "Auracast as default broadcast mode", "w": "Instant multi-speaker sync without manual pairing as Auracast device support matures."},
                {"f": "Wi-Fi 6 low-power audio profiles", "w": "Better coexistence for Wi-Fi speakers living alongside dense home mesh networks."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "QCC Bluetooth audio SoC", "note": "Leading Bluetooth audio SoC family across mainstream and premium portable speakers."},
            {"company": "Infineon AIROC", "chip": "Bluetooth Audio combo", "note": "Bluetooth Classic/LE Audio SoCs used broadly across the portable-speaker market."},
            {"company": "Realtek", "chip": "RTL87xx Bluetooth audio", "note": "Cost-competitive Bluetooth audio SoC common in value-tier speakers."},
            {"company": "MediaTek", "chip": "MT2xxx/Airoha audio platforms", "note": "Bluetooth audio SoCs (via Airoha) widely used in Asia-based speaker OEMs."},
            {"company": "Qualcomm/Sonos-style", "chip": "Wi-Fi + BT combo", "note": "Combo silicon for multiroom speakers that need both Wi-Fi streaming and BT fallback."},
        ],
    ),
    _app(
        "soundbar", "Wireless Soundbar", "Audio & Entertainment",
        "TV-companion audio — wireless subwoofer/rear-channel links plus Wi-Fi streaming and Bluetooth casting.",
        "Soundbars use a proprietary low-latency 2.4/5 GHz link to their wireless subwoofer and rear satellite "
        "speakers (a use case Bluetooth's latency profile doesn't comfortably serve), while offering Bluetooth "
        "for phone casting and Wi-Fi for AirPlay/Chromecast and multiroom grouping with other speakers in the "
        "same ecosystem.",
        [
            {"name": "Home-Theater UX", "sub": "Dialogue enhancement, surround virtualization, companion app EQ, voice-assistant mic", "k": "c1"},
            {"name": "Audio Processing", "sub": "Multi-channel DSP, HDMI-ARC/eARC audio return, Dolby Atmos/DTS:X decode", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Proprietary wireless sub/rears + Wi-Fi streaming + Bluetooth casting (zoom below)", "k": "c3"},
            {"name": "Drivers, Sub & Power", "sub": "Multi-driver bar array, wireless powered subwoofer, mains power", "k": "c4"},
        ],
        [
            {"name": "Proprietary 2.4/5 GHz link", "role": "Ultra-low-latency wireless subwoofer/rear-satellite audio that Bluetooth can't match."},
            {"name": "Wi-Fi", "role": "AirPlay/Chromecast casting and multiroom grouping with other speakers in the home."},
            {"name": "Bluetooth Classic", "role": "Direct phone/tablet casting without joining the home Wi-Fi network."},
        ],
        "US$ Billion",
        [(2020, 4.2), (2021, 4.9), (2022, 5.6), (2023, 6.4), (2024, 7.3)],
        [(2025, 8.2), (2026, 9.2), (2027, 10.3), (2028, 11.5), (2029, 12.8), (2030, 14.2), (2031, 15.7), (2032, 17.4), (2033, 19.2), (2034, 21.2)],
        {
            "mandatory": [
                {"f": "Proprietary low-latency wireless sub/rear link", "w": "Sub-audio sync latency requirements Bluetooth's codec/link layer isn't built for."},
                {"f": "Bluetooth Classic (casting)", "w": "Expected fallback for direct phone streaming without Wi-Fi setup."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi (AirPlay 2 / Chromecast built-in)", "w": "Multiroom grouping and higher-fidelity streaming beyond Bluetooth bitrate limits."},
                {"f": "Wi-Fi 6", "w": "More reliable multiroom sync in homes with many competing 2.4/5 GHz devices."},
            ],
            "future": [
                {"f": "LE Audio for TV-to-soundbar link", "w": "Standardizing the TV-audio handoff instead of each brand's proprietary protocol."},
                {"f": "Auracast broadcast to personal earbuds", "w": "Private TV listening broadcast directly to Auracast-capable headphones."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "QCC Bluetooth + Wi-Fi combo", "note": "Common combo platform for soundbar casting and multiroom features."},
            {"company": "MediaTek", "chip": "Home-theater audio SoC", "note": "Audio-processing SoC family used across many mainstream soundbar OEMs."},
            {"company": "Infineon AIROC", "chip": "CYW combo (Wi-Fi+BT)", "note": "Wi-Fi/Bluetooth combo silicon supplier for multiroom-capable soundbars."},
            {"company": "Texas Instruments", "chip": "Proprietary sub/rear RF + amp ICs", "note": "RF and amplifier ICs behind many proprietary wireless-subwoofer links."},
        ],
    ),
    _app(
        "streamingstick", "Streaming Media Stick", "Audio & Entertainment",
        "The Fire TV Stick/Chromecast/Roku category — Wi-Fi for 4K streaming, Bluetooth for the remote and audio.",
        "A maturing category: growth has slowed as smart TVs increasingly embed the same streaming OS directly, "
        "shrinking the standalone-dongle opportunity. Wireless requirements are dominated by Wi-Fi throughput "
        "for 4K/HDR streaming and Bluetooth LE for the remote control and headphone-jack-free private "
        "listening mode.",
        [
            {"name": "Streaming OS & Apps", "sub": "App store, voice search, universal search across streaming services", "k": "c1"},
            {"name": "Media SoC", "sub": "4K/HDR video decode, app processor, local storage for app caching", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi for video streaming, BLE for remote and private-listening headphones (zoom below)", "k": "c3"},
            {"name": "Remote, HDMI & Power", "sub": "BLE/IR remote, HDMI output, USB/mains power adapter", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (dual-band)", "role": "Primary link for 4K/HDR video streaming; 5 GHz strongly preferred for bandwidth/latency."},
            {"name": "Bluetooth LE", "role": "Remote-control pairing and private-listening audio to Bluetooth headphones."},
            {"name": "Bluetooth Classic (some models)", "role": "Direct game-controller or headphone pairing for casual gaming apps."},
        ],
        "US$ Billion",
        [(2020, 5.5), (2021, 6.5), (2022, 7.3), (2023, 8.0), (2024, 8.6)],
        [(2025, 9.2), (2026, 9.8), (2027, 10.4), (2028, 11.0), (2029, 11.6), (2030, 12.2), (2031, 12.8), (2032, 13.4), (2033, 14.0), (2034, 14.6)],
        {
            "mandatory": [
                {"f": "Wi-Fi 5 dual-band", "w": "Minimum bar for reliable 4K/HDR streaming without buffering in typical homes."},
                {"f": "Bluetooth LE (remote)", "w": "Standard low-power remote-control link across every major streaming-stick brand."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6", "w": "Better performance in dense multi-device households streaming 4K on several TVs at once."},
                {"f": "LE Audio private listening", "w": "Lower-latency, lower-power headphone streaming directly from the stick."},
            ],
            "future": [
                {"f": "Wi-Fi 7 (low-latency multi-link)", "w": "Headroom for 8K and cloud-gaming style low-latency streaming use cases."},
                {"f": "Matter smart-home hub role", "w": "Repurposing the always-on stick as a Thread border router for the home."},
            ],
        },
        [
            {"company": "Amlogic", "chip": "S9xx media SoC", "note": "Widely used media-streaming SoC platform across multiple stick/box OEMs."},
            {"company": "MediaTek", "chip": "MT8695/streaming SoC", "note": "Media SoC and Wi-Fi combo supplier for several streaming-device brands."},
            {"company": "Broadcom", "chip": "BCM Wi-Fi+BT combo", "note": "Combo connectivity silicon inside several flagship streaming-stick designs."},
            {"company": "Realtek", "chip": "RTD1xxx media SoC", "note": "Cost-optimized streaming SoC for value-tier sticks and smart-TV dongles."},
        ],
    ),
    _app(
        "audiobox", "Kids' Audio Box (Yoto-style)", "Audio & Entertainment",
        "Screen-free kids' audio players — Wi-Fi for library sync, Bluetooth/NFC for card-based, tactile content triggering.",
        "The screen-free kids-audio category (Yoto and similar) is built around physical cards/pebbles that "
        "trigger playback, so NFC/RFID tap detection is as important as the streaming radio. Wi-Fi handles "
        "content library sync and parental-control app connectivity, while Bluetooth remains a fallback for "
        "headphone/speaker pairing.",
        [
            {"name": "Kid-Safe Playback UX", "sub": "Card/pebble tap-to-play, screen-free pixel display, parental controls app", "k": "c1"},
            {"name": "Content Compute", "sub": "Local content cache, daily podcast/radio download scheduler, volume limiter", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "NFC/RFID card reader + Wi-Fi library sync + BLE setup (zoom below)", "k": "c3"},
            {"name": "Speaker, Battery & Enclosure", "sub": "Kid-durable housing, rechargeable battery, built-in speaker/headphone jack", "k": "c4"},
        ],
        [
            {"name": "NFC / RFID", "role": "Physical card or pebble tap-to-play is the core interaction model of the category."},
            {"name": "Wi-Fi", "role": "Content library sync, daily downloadable audio, parental-control app connectivity."},
            {"name": "Bluetooth LE / Classic", "role": "Initial app-based setup and, on some models, external speaker/headphone pairing."},
        ],
        "US$ Billion",
        [(2020, 0.18), (2021, 0.24), (2022, 0.32), (2023, 0.41), (2024, 0.52)],
        [(2025, 0.64), (2026, 0.78), (2027, 0.94), (2028, 1.12), (2029, 1.33), (2030, 1.56), (2031, 1.82), (2032, 2.10), (2033, 2.42), (2034, 2.76)],
        {
            "mandatory": [
                {"f": "NFC/RFID card reader", "w": "The physical tap-to-play interaction is the category's core differentiator vs. app-based players."},
                {"f": "Wi-Fi (2.4 GHz)", "w": "Content sync and parental-control connectivity; most models skip 5 GHz to save cost/power."},
            ],
            "good_to_have": [
                {"f": "Bluetooth LE (setup + audio out)", "w": "Simple app onboarding and optional external speaker/headphone pairing."},
                {"f": "Offline content caching over Wi-Fi", "w": "Reduces reliance on constant connectivity for car trips and travel."},
            ],
            "future": [
                {"f": "Matter/Thread parental-control integration", "w": "Tie screen-time and audio limits into the broader smart-home ecosystem."},
                {"f": "Wi-Fi 6 low-power mode", "w": "Longer battery life for all-day, always-connected use by young children."},
            ],
        },
        [
            {"company": "NXP Semiconductors", "chip": "NFC reader ICs (PN7xx)", "note": "Widely used NFC/RFID front-end for card- and pebble-based audio players."},
            {"company": "Espressif", "chip": "ESP32 (Wi-Fi+BLE)", "note": "Cost-effective combo SoC common across smaller kids-audio hardware makers."},
            {"company": "Nordic Semiconductor", "chip": "nRF52 series", "note": "BLE SoC used for setup/companion-app connectivity in several designs."},
        ],
    ),
    _app(
        "dsr", "Satellite / Set-Top Receiver (DSR)", "Audio & Entertainment",
        "Digital satellite/set-top receivers — a shrinking but still meaningful base with Wi-Fi/Bluetooth for app and remote control.",
        "Traditional satellite/cable set-top receivers are in structural decline as cord-cutting accelerates, "
        "but the installed base still requires Wi-Fi for companion-app control, whole-home client boxes, and "
        "streaming-app integration, plus Bluetooth LE for modern voice remotes replacing legacy IR.",
        [
            {"name": "Guide & App UX", "sub": "Program guide, DVR management, streaming-app integration, voice remote search", "k": "c1"},
            {"name": "Tuner & Media SoC", "sub": "Satellite/cable tuner, video decode, DVR storage controller", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi for whole-home client boxes and apps; BLE for the voice remote (zoom below)", "k": "c3"},
            {"name": "Dish/Cable Front-End & Power", "sub": "LNB/tuner front-end, HDMI output, mains power", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (dual-band)", "role": "Whole-home client-box video distribution and streaming-app connectivity."},
            {"name": "Bluetooth LE", "role": "Modern voice remotes replacing legacy IR remotes."},
            {"name": "MoCA (coax networking, adjunct)", "role": "Common wired alternative/complement to Wi-Fi for whole-home video distribution."},
        ],
        "US$ Billion",
        [(2020, 14.0), (2021, 13.5), (2022, 13.0), (2023, 12.6), (2024, 12.1)],
        [(2025, 11.7), (2026, 11.3), (2027, 11.0), (2028, 10.7), (2029, 10.4), (2030, 10.1), (2031, 9.8), (2032, 9.6), (2033, 9.3), (2034, 9.1)],
        {
            "mandatory": [
                {"f": "Wi-Fi dual-band", "w": "Required for whole-home client boxes and any streaming-app integration on the main receiver."},
                {"f": "Bluetooth LE (voice remote)", "w": "Now the standard remote-control link, replacing IR line-of-sight limitations."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6", "w": "Better multi-client-box performance as more households run 3+ TVs off one receiver."},
                {"f": "MoCA 2.5 coax backhaul", "w": "More reliable whole-home distribution than Wi-Fi in RF-noisy or large homes."},
            ],
            "future": [
                {"f": "Hybrid satellite+broadband streaming stack", "w": "Bolt-on streaming-app hub to slow subscriber erosion from pure OTT competitors."},
                {"f": "Matter smart-home hub repurposing", "w": "Using the always-on box as a Thread border router to extend its usefulness."},
            ],
        },
        [
            {"company": "Broadcom", "chip": "BCM7xxx set-top SoC", "note": "Long-standing set-top/satellite-receiver SoC and Wi-Fi combo supplier."},
            {"company": "MaxLinear", "chip": "Satellite tuner + MoCA", "note": "Tuner and MoCA/coax-networking silicon for satellite/cable receiver platforms."},
            {"company": "Realtek", "chip": "RTD/Wi-Fi combo", "note": "Wi-Fi module supplier for whole-home client-box connectivity."},
        ],
    ),

    _app(
        "domesticrobot", "Domestic Robot", "Robotics",
        "Robot vacuums, mops and lawn mowers — Wi-Fi for app control/mapping, with UWB/precision-nav sensors emerging.",
        "Domestic robots (robovacs, robomops, robomowers) rely on Wi-Fi for remote start, map sharing and "
        "firmware updates, while onboard LiDAR/camera SLAM handles navigation rather than a dedicated wireless "
        "positioning radio. Multi-robot and dock-to-robot coordination is a growing use case for low-latency "
        "local links as households add multiple units.",
        [
            {"name": "Cleaning App & Maps", "sub": "Room maps, no-go zones, scheduling, voice-assistant integration", "k": "c1"},
            {"name": "Navigation Compute", "sub": "LiDAR/vSLAM processor, obstacle-avoidance AI, motor control", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi primary control/app link; BLE for setup and dock communication (zoom below)", "k": "c3"},
            {"name": "Motors, Dock & Battery", "sub": "Drive motors, self-empty/self-wash dock, high-capacity battery pack", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (2.4 GHz)", "role": "Primary app control, map upload/sync, scheduling and remote-start link."},
            {"name": "Bluetooth LE", "role": "Initial setup/commissioning and short-range dock/robot pairing."},
            {"name": "UWB (emerging)", "role": "Precision multi-robot or robot-to-furniture positioning beyond camera/LiDAR SLAM."},
        ],
        "US$ Billion",
        [(2020, 5.0), (2021, 6.2), (2022, 7.3), (2023, 8.6), (2024, 10.1)],
        [(2025, 11.8), (2026, 13.8), (2027, 16.0), (2028, 18.6), (2029, 21.5), (2030, 24.8), (2031, 28.5), (2032, 32.6), (2033, 37.2), (2034, 42.3)],
        {
            "mandatory": [
                {"f": "Wi-Fi 4 (2.4 GHz)", "w": "Baseline for app control, scheduling and remote start across every mainstream robovac."},
                {"f": "Bluetooth LE commissioning", "w": "Standard setup flow before Wi-Fi credentials are provisioned."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6 (dual-band)", "w": "Faster map uploads and better coexistence in crowded smart-home 2.4 GHz bands."},
                {"f": "Matter smart-home integration", "w": "Cross-ecosystem scheduling and status alongside other Matter devices."},
            ],
            "future": [
                {"f": "UWB multi-robot coordination", "w": "Precision positioning for multi-unit fleets (vacuum + mop + mower) working together."},
                {"f": "5G/RedCap connectivity (commercial robots)", "w": "Untethered operation across large commercial floor plans beyond Wi-Fi coverage."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Robotics RB-series SoC", "note": "Vision/AI + Wi-Fi platform positioned for premium navigation-heavy robovacs."},
            {"company": "Espressif", "chip": "ESP32 (Wi-Fi+BLE)", "note": "Dominant low-cost combo SoC across the majority of value and mid-tier robovacs."},
            {"company": "Infineon AIROC", "chip": "CYW43xxx Wi-Fi", "note": "Wi-Fi module supplier to several premium robotic-vacuum brands."},
            {"company": "Realtek", "chip": "RTL8xxx Wi-Fi", "note": "Cost-competitive Wi-Fi SoC widely used across Chinese ODM robovac platforms."},
        ],
    ),
    _app(
        "industrialrobot", "Industrial Robot", "Robotics",
        "Factory-floor arms and AGVs/AMVs — private 5G and Wi-Fi 6/6E driving the shift away from tethered fieldbus cabling.",
        "Industrial robots and mobile AGVs/AMRs are the leading edge of the private-5G and Wi-Fi 6E push in "
        "manufacturing, replacing drag-chains and slip-rings with wireless for mobility and reconfigurability. "
        "Deterministic, low-latency wireless (TSN over Wi-Fi 6/6E, private 5G URLLC) is now a real requirement "
        "for motion-control loops, not just monitoring/telemetry.",
        [
            {"name": "MES/Fleet Management", "sub": "Production scheduling, fleet routing (AGV/AMR), digital-twin monitoring", "k": "c1"},
            {"name": "Robot Controller", "sub": "Real-time motion control, safety PLC, on-arm vision/force sensing", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Private 5G/Wi-Fi 6E for mobility + wired TSN Ethernet for fixed arms (zoom below)", "k": "c3"},
            {"name": "Actuators, Safety & Power", "sub": "Servo motors/grippers, safety-rated e-stop, battery (mobile) or mains power (fixed)", "k": "c4"},
        ],
        [
            {"name": "Private 5G (URLLC)", "role": "Deterministic, low-latency wireless replacing cabling for mobile robots and reconfigurable cells."},
            {"name": "Wi-Fi 6/6E (TSN-aware)", "role": "Cost-effective deterministic wireless for AGV/AMR fleets in most factory deployments today."},
            {"name": "Bluetooth LE", "role": "Handheld teach-pendant pairing, asset tags, technician diagnostic tools."},
            {"name": "UWB", "role": "Centimeter-accurate AGV/AMR indoor positioning where GPS is unavailable."},
        ],
        "US$ Billion",
        [(2020, 16), (2021, 19), (2022, 21), (2023, 23), (2024, 26)],
        [(2025, 29), (2026, 33), (2027, 37), (2028, 42), (2029, 47), (2030, 53), (2031, 60), (2032, 67), (2033, 76), (2034, 85)],
        {
            "mandatory": [
                {"f": "Wi-Fi 6/6E (deterministic QoS)", "w": "Current mainstream wireless backbone for AGV/AMR fleets and factory monitoring."},
                {"f": "Bluetooth LE (tools/tags)", "w": "Teach-pendant, asset-tag and diagnostic-tool connectivity baseline."},
            ],
            "good_to_have": [
                {"f": "Private 5G (URLLC)", "w": "Deterministic latency/reliability for motion-critical wireless control loops at scale."},
                {"f": "UWB positioning", "w": "Precise indoor localization for AMR fleets and safety zoning around moving robots."},
            ],
            "future": [
                {"f": "Wi-Fi 7 (TSN + multi-link)", "w": "Wireless replacement for the last tethered motion-control cabling on fixed arms."},
                {"f": "5G-Advanced RedCap sensors", "w": "Battery-friendly wireless sensor swarms across large industrial sites."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "FSM private-5G platforms", "note": "Reference private-5G radio platforms positioned for factory AGV/AMR deployments."},
            {"company": "Siemens/Nokia-class infra", "chip": "Private 5G RAN + Wi-Fi 6E APs", "note": "Infrastructure vendors partnering with chipmakers for industrial wireless rollouts."},
            {"company": "Infineon AIROC", "chip": "Industrial Wi-Fi 6/BLE combo", "note": "Ruggedized combo connectivity for factory-floor robot and sensor modules."},
            {"company": "u-blox", "chip": "UWB + Wi-Fi/BLE modules", "note": "Positioning and connectivity modules used across AMR/AGV fleet vendors."},
        ],
    ),
    _app(
        "humanoid", "Humanoid Robot", "Robotics",
        "The newest, fastest-growing category — dense onboard sensor fusion demands the highest-bandwidth, lowest-latency wireless stack of any consumer/industrial device.",
        "Humanoid robots combine industrial-grade mobility with consumer-adjacent deployment (homes, warehouses, "
        "retail), needing simultaneous high-bandwidth video/lidar telemetry, low-latency teleoperation links, "
        "and dense onboard sensor buses. This is currently the highest-growth, most speculative category on "
        "this page, with valuations driven heavily by future potential rather than current shipment volume.",
        [
            {"name": "Task & Teleop UX", "sub": "Autonomous task planning, remote-teleoperation console, fleet dashboard", "k": "c1"},
            {"name": "Onboard AI Compute", "sub": "Multimodal foundation model inference, real-time motion/balance control", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Wi-Fi 6E/7 telemetry + 5G/private-5G teleop link + UWB/BLE sensor mesh (zoom below)", "k": "c3"},
            {"name": "Actuators, Battery & Safety", "sub": "Dexterous hands/legs, high-density battery pack, safety e-stop and geofencing", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi 6E/7", "role": "High-bandwidth camera/LiDAR telemetry and model-update streaming while docked or roaming."},
            {"name": "Private 5G / RedCap", "role": "Low-latency remote-teleoperation and fleet coordination beyond a single Wi-Fi cell."},
            {"name": "UWB", "role": "Precise robot-to-robot and robot-to-charging-dock positioning in shared spaces."},
            {"name": "Bluetooth LE", "role": "Onboard sensor/actuator bus links and technician diagnostic tools."},
        ],
        "US$ Billion",
        [(2020, 1.2), (2021, 1.5), (2022, 1.9), (2023, 2.4), (2024, 3.2)],
        [(2025, 4.6), (2026, 6.8), (2027, 9.9), (2028, 14.2), (2029, 20.0), (2030, 27.7), (2031, 37.5), (2032, 49.9), (2033, 65.2), (2034, 83.9)],
        {
            "mandatory": [
                {"f": "Wi-Fi 6E (dual/tri-band)", "w": "Sustained high-bandwidth sensor telemetry and over-the-air model updates."},
                {"f": "Bluetooth LE (sensor bus/tools)", "w": "Low-power links for distributed onboard sensors and field diagnostics."},
            ],
            "good_to_have": [
                {"f": "Private 5G/RedCap teleop link", "w": "Reliable low-latency remote operation across a warehouse or campus, not just one Wi-Fi cell."},
                {"f": "UWB fleet positioning", "w": "Safe multi-robot coordination and precision docking/charging in shared human spaces."},
            ],
            "future": [
                {"f": "Wi-Fi 7 multi-link teleoperation", "w": "Near-zero-jitter video/haptic feedback for high-fidelity remote teleoperation."},
                {"f": "Satellite/5G-A backhaul", "w": "Connectivity continuity for humanoid fleets operating outside dense-Wi-Fi facilities."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Robotics RB6/Snapdragon platforms", "note": "AI + connectivity reference platform positioned for humanoid and mobile-robot OEMs."},
            {"company": "NVIDIA", "chip": "Jetson Thor + partner Wi-Fi/5G modules", "note": "Dominant onboard AI compute partner; relies on third-party silicon for wireless connectivity."},
            {"company": "Infineon AIROC", "chip": "Industrial Wi-Fi 6E/BLE combo", "note": "Positioned for ruggedized humanoid sensor-bus and telemetry connectivity."},
            {"company": "u-blox", "chip": "UWB + 5G modules", "note": "Positioning and cellular module supplier for early humanoid fleet pilots."},
        ],
    ),

    _app(
        "meshrouter", "Mesh Router (Wi-Fi/BT/802.15.4)", "Networking Infrastructure",
        "The connective tissue of the smart home — whole-home Wi-Fi mesh plus a built-in Thread/Zigbee/Matter border router.",
        "Modern mesh Wi-Fi systems have become the default smart-home hub by adding a Thread border router and "
        "Bluetooth LE radio alongside their core Wi-Fi mesh backhaul, letting one box provide both internet "
        "connectivity and the low-power mesh backbone for Matter-certified sensors and locks.",
        [
            {"name": "Home Network App", "sub": "Network topology, parental controls, guest Wi-Fi, Matter/Thread device management", "k": "c1"},
            {"name": "Router/Mesh Compute", "sub": "Wi-Fi mesh routing (802.11s/proprietary), QoS engine, Thread border-router stack", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Tri-band Wi-Fi mesh backhaul + Thread/Zigbee border router + BLE (zoom below)", "k": "c3"},
            {"name": "WAN, Antennas & Power", "sub": "Cable/fiber/5G WAN uplink, multi-antenna array, mains power with battery-backup option", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi 6/6E/7 (tri-band mesh)", "role": "Dedicated backhaul band plus client bands for whole-home coverage without speed loss."},
            {"name": "Thread (802.15.4)", "role": "Built-in Matter border router extending low-power mesh to sensors, locks and bulbs."},
            {"name": "Zigbee (select models)", "role": "Legacy mesh support for existing non-Matter Zigbee device ecosystems."},
            {"name": "Bluetooth LE", "role": "Node commissioning and Matter/BLE device onboarding handoff to Wi-Fi/Thread."},
        ],
        "US$ Billion",
        [(2020, 2.0), (2021, 2.6), (2022, 3.2), (2023, 3.9), (2024, 4.7)],
        [(2025, 5.6), (2026, 6.6), (2027, 7.7), (2028, 9.0), (2029, 10.4), (2030, 12.0), (2031, 13.7), (2032, 15.6), (2033, 17.7), (2034, 20.0)],
        {
            "mandatory": [
                {"f": "Wi-Fi 6 tri-band mesh", "w": "Dedicated backhaul band is now the baseline expectation for premium mesh systems."},
                {"f": "Thread border router + Matter", "w": "Table-stakes differentiator versus legacy single-purpose Wi-Fi routers."},
                {"f": "Bluetooth LE onboarding", "w": "Standard commissioning flow for both the router nodes and Matter accessories."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi 6E/7 (6 GHz)", "w": "Interference-free backhaul and client bands in dense multi-AP, multi-device homes."},
                {"f": "Zigbee bridging", "w": "Backward compatibility for households with an existing non-Matter Zigbee device base."},
            ],
            "future": [
                {"f": "Wi-Fi HaLow gateway role", "w": "Extending whole-property coverage to long-range, low-power outdoor sensors."},
                {"f": "Built-in 5G/satellite WAN failover", "w": "Uplink resiliency as mesh systems become the single point of home connectivity."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Networking Pro Wi-Fi 7 platform", "note": "Reference chipset behind most premium tri-band mesh Wi-Fi systems."},
            {"company": "Broadcom", "chip": "BCM Wi-Fi 6E/7 SoC", "note": "Leading Wi-Fi SoC supplier for flagship mesh-router platforms."},
            {"company": "MediaTek", "chip": "Filogic Wi-Fi 6E/7", "note": "Fast-growing Wi-Fi SoC platform across value and mid-tier mesh systems."},
            {"company": "Silicon Labs", "chip": "EFR32 (Thread border router)", "note": "Thread/Zigbee radio supplier embedded inside many mesh-router SKUs."},
            {"company": "NXP Semiconductors", "chip": "88W Wi-Fi + 802.15.4 combo", "note": "Combo silicon positioned for integrated Wi-Fi+Thread mesh-router designs."},
        ],
    ),

    _app(
        "rse", "Rear Seat Entertainment", "Automotive",
        "In-cabin passenger displays and audio — Bluetooth/Wi-Fi streaming plus wireless headphone and device-mirroring links.",
        "Rear-seat entertainment systems stream content to passenger displays and support Bluetooth headphone "
        "pairing and device screen-mirroring, increasingly over an in-vehicle Wi-Fi hotspot fed by the head "
        "unit's cellular modem. Multi-zone audio (different audio per seat) is a growing premium differentiator "
        "relying on LE Audio's multi-stream capability.",
        [
            {"name": "Passenger UX", "sub": "Per-seat displays, streaming apps, device mirroring, multi-zone audio control", "k": "c1"},
            {"name": "Media Compute", "sub": "Video decode SoC, app processor for streaming apps, content caching", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "In-vehicle Wi-Fi hotspot + Bluetooth headphone/mirroring links (zoom below)", "k": "c3"},
            {"name": "Displays, Speakers & Power", "sub": "Seatback/overhead displays, per-zone speakers, vehicle 12V power", "k": "c4"},
        ],
        [
            {"name": "Wi-Fi (in-vehicle hotspot)", "role": "Streaming content and device-mirroring backhaul fed by the head unit's cellular modem."},
            {"name": "Bluetooth Classic/LE Audio", "role": "Wireless headphone pairing; LE Audio multi-stream enables different audio per passenger."},
            {"name": "NFC", "role": "Tap-to-mirror or tap-to-pair for a passenger's phone/tablet."},
        ],
        "US$ Billion",
        [(2020, 1.8), (2021, 2.1), (2022, 2.4), (2023, 2.7), (2024, 3.1)],
        [(2025, 3.5), (2026, 4.0), (2027, 4.5), (2028, 5.1), (2029, 5.8), (2030, 6.5), (2031, 7.3), (2032, 8.2), (2033, 9.2), (2034, 10.3)],
        {
            "mandatory": [
                {"f": "Bluetooth Classic (A2DP headphones)", "w": "Baseline wireless headphone pairing expected in every rear-seat entertainment package."},
                {"f": "Wi-Fi in-vehicle hotspot", "w": "Streaming-app and device-mirroring connectivity for passenger displays."},
            ],
            "good_to_have": [
                {"f": "LE Audio multi-stream", "w": "Distinct audio per passenger/zone from one broadcast source without extra hardware."},
                {"f": "NFC tap-to-pair/mirror", "w": "Faster, simpler passenger onboarding than manual Bluetooth pairing menus."},
            ],
            "future": [
                {"f": "Auracast per-seat broadcast", "w": "Any passenger's own headphones can tune into their seat's audio feed instantly."},
                {"f": "5G-fed edge streaming cache", "w": "Reduces buffering by pre-caching content via the vehicle's cellular connection."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon Cockpit platform", "note": "Cockpit SoC family increasingly bundling rear-seat display and connectivity IP."},
            {"company": "NXP Semiconductors", "chip": "Bluetooth/Wi-Fi automotive combo", "note": "Automotive-grade combo connectivity widely used in cabin infotainment modules."},
            {"company": "Infineon AIROC", "chip": "Automotive combo (Wi-Fi/BLE)", "note": "Automotive-qualified Wi-Fi/BLE combo positioned for in-cabin entertainment modules."},
            {"company": "Texas Instruments", "chip": "Automotive Bluetooth/Wi-Fi", "note": "Connectivity IC supplier across several rear-seat entertainment Tier-1 designs."},
        ],
    ),
    _app(
        "headunit", "Head Unit (Infotainment)", "Automotive",
        "The car's central cockpit computer — Wi-Fi/Bluetooth for phone projection, plus cellular and V2X for connected-car services.",
        "The head unit is the most radio-dense automotive application: Bluetooth for hands-free calling and "
        "phone-audio, Wi-Fi for CarPlay/Android Auto wireless projection and hotspot, embedded cellular for "
        "connected services (OTA updates, telematics, eCall), and growing V2X/UWB support for digital-key and "
        "vehicle-to-infrastructure use cases.",
        [
            {"name": "Cockpit UX", "sub": "Navigation, phone projection (CarPlay/Android Auto), voice assistant, cluster integration", "k": "c1"},
            {"name": "Cockpit Domain Controller", "sub": "Multi-display SoC, OTA update manager, telematics control unit (TCU)", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Bluetooth + Wi-Fi + embedded cellular + UWB/V2X (zoom below)", "k": "c3"},
            {"name": "Antennas, Displays & Power", "sub": "Shark-fin antenna module, multi-display cluster/center-stack, 12V/48V vehicle power", "k": "c4"},
        ],
        [
            {"name": "Bluetooth Classic/LE", "role": "Hands-free calling, phone-audio streaming, and digital-key BLE ranging."},
            {"name": "Wi-Fi (dual/tri-band)", "role": "Wireless CarPlay/Android Auto projection and in-vehicle hotspot for passengers."},
            {"name": "Embedded cellular (4G/5G)", "role": "OTA software updates, telematics, eCall, connected-navigation and streaming."},
            {"name": "UWB", "role": "Secure, relay-attack-resistant digital-key ranging for passive entry/start."},
            {"name": "C-V2X (emerging)", "role": "Direct vehicle-to-vehicle/infrastructure safety and traffic-signal messaging."},
        ],
        "US$ Billion",
        [(2020, 22), (2021, 25), (2022, 27), (2023, 30), (2024, 33)],
        [(2025, 37), (2026, 41), (2027, 45), (2028, 50), (2029, 55), (2030, 61), (2031, 67), (2032, 74), (2033, 81), (2034, 89)],
        {
            "mandatory": [
                {"f": "Bluetooth 5.x (hands-free + audio)", "w": "Regulatory and consumer-expectation baseline for hands-free calling worldwide."},
                {"f": "Wi-Fi (wireless CarPlay/Android Auto)", "w": "Now a mainstream buyer expectation across most trim levels, not just premium."},
                {"f": "Embedded cellular (telematics/eCall)", "w": "Regulatory requirement in several regions (e.g., EU eCall) plus OTA update dependency."},
            ],
            "good_to_have": [
                {"f": "UWB digital key", "w": "Premium anti-relay-attack passive entry, differentiating against legacy BLE-only keyless entry."},
                {"f": "Wi-Fi 6E in-cabin hotspot", "w": "Higher-throughput passenger connectivity, especially with rear-seat entertainment onboard."},
            ],
            "future": [
                {"f": "C-V2X / 5G-Advanced sidelink", "w": "Direct vehicle-to-vehicle/infrastructure safety messaging as regulatory mandates mature."},
                {"f": "Satellite connectivity fallback", "w": "Connected-service continuity in cellular dead zones for safety and navigation features."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon Digital Chassis (Cockpit + TCU)", "note": "Leading integrated cockpit + connectivity platform across many global OEMs."},
            {"company": "NXP Semiconductors", "chip": "S32 + automotive UWB/BLE", "note": "Strong automotive UWB digital-key and multi-radio connectivity positioning."},
            {"company": "Infineon AIROC", "chip": "AURIX + automotive RF/UWB", "note": "Automotive-grade microcontrollers and RF front-end IP for connectivity modules."},
            {"company": "Renesas", "chip": "R-Car cockpit SoC", "note": "Cockpit domain-controller SoC family used by multiple Tier-1 infotainment suppliers."},
            {"company": "Texas Instruments", "chip": "Automotive Bluetooth/Wi-Fi/UWB", "note": "Broad automotive connectivity IC portfolio spanning BT, Wi-Fi and UWB ranging."},
        ],
    ),
    _app(
        "twowheeler", "2-Wheeler Head Unit", "Automotive",
        "Connected motorcycle/scooter dashboards — a smaller, cost- and power-constrained cousin of the car head unit.",
        "Two-wheeler head units bring car-style connectivity (navigation, phone notifications, call handling) "
        "to motorcycles and scooters under tighter cost, power and ruggedization constraints, so Bluetooth for "
        "helmet-intercom/phone pairing and low-cost Wi-Fi/cellular for navigation and OTA updates dominate the "
        "radio bill of materials.",
        [
            {"name": "Rider UX", "sub": "Turn-by-turn nav, call/notification display, helmet-intercom integration", "k": "c1"},
            {"name": "Dash Compute", "sub": "Ruggedized low-power display SoC, GNSS nav engine, vibration-hardened design", "k": "c2"},
            {"name": "Connectivity Subsystem", "sub": "Bluetooth for phone/helmet + optional Wi-Fi/cellular for nav/OTA (zoom below)", "k": "c3"},
            {"name": "Display, GNSS & Power", "sub": "Sunlight-readable display, GNSS antenna, 12V motorcycle battery with regulator", "k": "c4"},
        ],
        [
            {"name": "Bluetooth Classic/LE", "role": "Phone pairing for calls/notifications and helmet-intercom communication."},
            {"name": "GNSS", "role": "Turn-by-turn navigation, core to nearly every connected 2-wheeler dash."},
            {"name": "Wi-Fi (setup/OTA, select models)", "role": "Firmware updates and initial app-based configuration where fitted."},
            {"name": "Embedded cellular (premium models)", "role": "Connected navigation, theft-tracking and telematics on higher-end motorcycles."},
        ],
        "US$ Billion",
        [(2020, 0.60), (2021, 0.75), (2022, 0.92), (2023, 1.12), (2024, 1.36)],
        [(2025, 1.64), (2026, 1.97), (2027, 2.36), (2028, 2.81), (2029, 3.34), (2030, 3.95), (2031, 4.65), (2032, 5.46), (2033, 6.39), (2034, 7.46)],
        {
            "mandatory": [
                {"f": "Bluetooth Classic/LE (phone + intercom)", "w": "Core rider use case: calls, notifications and helmet-intercom pairing."},
                {"f": "GNSS", "w": "Turn-by-turn navigation is now the primary reason riders buy a connected dash."},
            ],
            "good_to_have": [
                {"f": "Wi-Fi (setup/OTA)", "w": "Simplifies configuration and firmware updates versus cellular-only or USB-only updates."},
                {"f": "Theft-alert BLE beacon", "w": "Low-cost proximity/tamper alert leveraging the existing BLE radio."},
            ],
            "future": [
                {"f": "Embedded cellular telematics", "w": "Connected navigation and stolen-vehicle tracking as cost of cellular modules keeps falling."},
                {"f": "C-V2X hazard/blind-spot alerts", "w": "Motorcycle-specific safety use case as V2X infrastructure rolls out for cars first."},
            ],
        },
        [
            {"company": "Qualcomm", "chip": "Snapdragon Wear/automotive-lite platforms", "note": "Repurposed wearable/automotive-lite SoCs positioned for cost-sensitive 2-wheeler dashes."},
            {"company": "Nordic Semiconductor", "chip": "nRF52/53 (BLE)", "note": "Low-cost BLE SoC widely used for phone/intercom pairing in 2-wheeler dashboards."},
            {"company": "u-blox", "chip": "GNSS + cellular modules", "note": "GNSS and cellular module supplier for navigation and telematics features."},
            {"company": "MediaTek", "chip": "Automotive-lite Wi-Fi/BT SoC", "note": "Cost-optimized connectivity SoC positioned for mass-market scooter/motorcycle OEMs."},
        ],
    ),
]
