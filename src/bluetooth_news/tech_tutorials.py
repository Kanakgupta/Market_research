"""Hand-crafted technical tutorials for the Wireless Technology learning page.

This content is intentionally static and editorial (not news-driven). It exists
to teach anyone new to a wireless technology -- including application developers --
how each stack is layered, what each layer does, how the core procedures work,
and what an app/device developer actually programs against.

Version/spec numbers shown on the page are merged in at render time from
data/standards.json (single source of truth, kept verified there). This file
covers the timeless architecture/concepts that don't change release to release.
"""
from __future__ import annotations

TECH_TUTORIALS: list[dict] = [
    {
        "slug": "bluetooth",
        "label": "Zephyr Bluetooth",
        "spec_family": "bluetooth",
        "tagline": "The Zephyr RTOS's in-tree Bluetooth Low Energy Host + Controller stack -- the open-source reference implementation many silicon vendors and product companies build their Bluetooth firmware on.",
        "overview": (
            "Zephyr is a Linux-Foundation-governed, Apache-2.0 real-time OS that ships a complete Bluetooth Low "
            "Energy stack -- Host, Controller, and the HCI glue between them -- written from scratch in-tree "
            "(not a BlueZ port), plus a growing set of Classic Bluetooth (BR/EDR) Host profiles (SDP, L2CAP, "
            "RFCOMM, A2DP, AVRCP, HFP, GOEP/OBEX, BIP). It is Bluetooth v5.3 compliant, portable to every CPU "
            "architecture Zephyr supports, highly configurable down to a 16 KB-RAM footprint for Bluetooth Mesh, "
            "and ships with a Bluetooth SIG pre-qualified Host listing that product companies can reference to "
            "cut their own qualification cost and effort."
        ),
        "architecture": [
            {"tag": "APP", "name": "Application", "function": "Your Zephyr app: calls bt_enable() to bring up the stack, registers GATT services with BT_GATT_SERVICE_DEFINE, and starts advertising/scanning/connecting -- built with the same west/CMake application flow as any other Zephyr app."},
            {"tag": "HOST", "name": "Bluetooth Host (subsys/bluetooth/host)", "function": "GAP, GATT, ATT, SMP (pairing/bonding) and L2CAP for LE, plus SDP/RFCOMM/A2DP/AVRCP/HFP for Classic -- this is where HCI command/event handling and connection tracking live."},
            {"tag": "HCI", "name": "Host Controller Interface", "function": "The Bluetooth-standard wire protocol between Host and Controller (commands, events, ACL/ISO data). Zephyr carries it over UART (3-wire/5-wire), SPI, USB, or IPC (shared memory on multi-core SoCs)."},
            {"tag": "CTLR", "name": "Bluetooth Controller (subsys/bluetooth/controller)", "function": "Zephyr's own software Link Layer (LL_SW): connection scheduling via the Ticker, advertising/scanning, channel-hopping, encryption, and the LLCP control-procedure state machines -- runs natively on Nordic nRF52x/nRF53x radios today."},
            {"tag": "HAL", "name": "Hardware Abstraction Layer / Radio", "function": "Vendor-specific glue to the 2.4 GHz radio peripheral and supporting blocks (timers, RNG, AES-CCM/ECB crypto, address-resolution accelerator) -- swapped per SoC; this is the layer a new chip port has to implement."},
        ],
        "block_diagram": {
            "caption": "Zephyr can produce three different Bluetooth build types from the same source tree: Combined (Host+Controller on one chip -- the classic single-chip SoC image), Host-only (talks HCI out to an external Controller chip over UART/SPI/USB/IPC), and Controller-only (exposes Zephyr's own Controller over HCI to any external Host, including Linux BlueZ). Choosing a build type is a Kconfig decision (CONFIG_BT, CONFIG_BT_HCI, CONFIG_BT_HCI_RAW), not a code rewrite.",
            "blocks": [
                {"name": "Application & GATT Services", "sub": "bt_enable() | BT_GATT_SERVICE_DEFINE | advertising / scanning APIs", "kind": "upper", "iface": "Zephyr Bluetooth API (zephyr/bluetooth/*.h)"},
                {"name": "Bluetooth Host", "sub": "GAP | GATT | ATT | SMP | L2CAP | Mesh | Classic profiles", "kind": "mac", "iface": "HCI (UART / SPI / USB / IPC)"},
                {"name": "Bluetooth Controller", "sub": "Link Layer (LL_SW) | Ticker scheduler | LLCP procedures", "kind": "phy", "iface": "radio HAL"},
                {"name": "Physical Radio", "sub": "Nordic nRF52x / nRF53x native, or any HCI-compliant external Controller chip", "kind": "medium"},
            ],
        },
        "core_concepts": [
            {"term": "Build types: Combined / Host-only / Controller-only", "definition": "Combined puts Host+Controller in one firmware image (single-chip SoC); Host-only runs the app+Host and drives an external Controller chip over HCI; Controller-only turns a Zephyr board into an HCI radio (hci_uart, hci_usb, hci_spi) for any external Host, Zephyr or otherwise."},
            {"term": "Single-chip vs. dual-chip configuration", "definition": "Single-chip = one MCU running Host, Controller and app together. Dual-chip = a Host processor (which can even be Linux/BlueZ) paired over HCI with a separate Controller IC -- HCI is what makes any Host/Controller vendor combination interoperable."},
            {"term": "Bluetooth Mesh", "definition": "Relay, Friend Node, Low-Power Node (LPN) and GATT Proxy roles, both provisioning bearers (PB-ADV & PB-GATT), and the Foundation Models -- fits devices with as little as 16 KB RAM."},
            {"term": "LE Audio stack", "definition": "Built on Isochronous Channels: BAP (Basic Audio Profile), CAP (Common Audio Profile), TMAP (Telephone & Media Audio), HAP (Hearing Access Profile) and PBP (Public Broadcast, i.e. Auracast-style) all ship as separate, composable API modules."},
            {"term": "SIG qualification via PTS / AutoPTS", "definition": "The Host stack is tested against the Bluetooth SIG's Profile Tuning Suite (PTS), automated with the open-source AutoPTS tool; an ICS file (PICS) declares exactly which features are claimed for qualification."},
            {"term": "Simulated hardware (native_sim, QEMU, BabbleSim)", "definition": "native_sim runs the Host as a plain Linux executable against a real or virtual external Controller; nrf52_bsim / nrf5340bsim use BabbleSim to simulate the radio environment itself so multi-device Bluetooth scenarios run entirely on a CI server, no boards required."},
        ],
        "how_it_works": [
            {"title": "1. Pick a build type", "detail": "Decide Combined, Host-only, or Controller-only via Kconfig (CONFIG_BT, CONFIG_BT_HCI, CONFIG_BT_HCI_RAW) and, for dual-chip setups, which physical HCI transport (UART/SPI/USB/IPC) connects the two chips."},
            {"title": "2. Initialize the stack", "detail": "The app calls bt_enable(), optionally with a completion callback since init can be asynchronous while the Controller and any persisted settings load."},
            {"title": "3. Advertise or scan (GAP)", "detail": "A Peripheral calls bt_le_adv_start() with advertising + scan-response data; a Central calls bt_le_scan_start() to discover it -- exactly the GAP Broadcaster/Observer/Peripheral/Central roles from the Bluetooth spec."},
            {"title": "4. Connect & discover GATT", "detail": "On connection, the app registers/enumerates GATT services (BT_GATT_SERVICE_DEFINE on the Server side, bt_gatt_discover() on the Client side) to exchange Characteristics."},
            {"title": "5. Pair & bond (SMP, optional)", "detail": "Legacy or LE Secure Connections pairing negotiates a Long-Term Key; Zephyr's settings subsystem persists bonds to flash so reconnects skip re-pairing."},
            {"title": "6. Exchange data", "detail": "Reads/writes/notifications flow over ATT/L2CAP; this is the day-to-day interface most Zephyr Bluetooth application code is written against."},
            {"title": "7. Extend into Mesh or LE Audio (optional)", "detail": "The same Controller/HCI foundation carries Bluetooth Mesh provisioning/relay traffic or LE Audio Isochronous Channels (BAP/CAP/TMAP/HAP) depending on which subsystem the app enables."},
            {"title": "8. Qualify the product", "detail": "Run PTS/AutoPTS against the claimed ICS features, or inherit coverage from Zephyr's own pre-qualified Host listing, before submitting an End Product Listing to the Bluetooth SIG."},
        ],
        "developer_view": [
            {"title": "Core API entry points", "detail": "bt_enable() to start the stack, bt_le_adv_start() / bt_le_scan_start() for GAP roles, BT_GATT_SERVICE_DEFINE + bt_gatt_notify()/bt_gatt_read()/bt_gatt_write() for GATT -- all declared in the public headers under include/zephyr/bluetooth/."},
            {"title": "Kconfig & devicetree wiring", "detail": "CONFIG_BT enables the subsystem; CONFIG_BT_HCI plus the zephyr,bt-hci devicetree chosen node selects which Controller (local radio or external HCI transport) the Host talks to; CONFIG_BT_HCI_RAW builds a Controller-only image."},
            {"title": "Samples as the fastest way to learn", "detail": "samples/bluetooth/ ships 60+ ready-to-build examples: Peripheral, Central, Mesh, the whole LE Audio (BAP/CAP/TMAP/HAP/PBP) family, Classic A2DP/HFP, and the hci_uart/hci_usb/hci_spi Controller bridges -- clone one and modify it rather than starting from scratch."},
            {"title": "Hardware setups for development", "detail": "Embedded (flash a real board), Host-on-Linux with an external Controller (QEMU or native_sim + a physical/virtual Controller, Linux-only), or fully-simulated nRF5x via BabbleSim (nrf52_bsim / nrf5340bsim) -- pick based on what hardware you have on hand."},
            {"title": "Debugging tools", "detail": "HCI snoop logging captures Host<->Controller traffic even with no physical transport (feed it to Wireshark/btmon); the interactive Bluetooth shell (`bt` commands) exercises GAP/GATT/Mesh without writing app code; nRF Sniffer captures over-the-air packets."},
        ],
        "hardware_support": [
            {"name": "Nordic Semiconductor nRF52x / nRF53x", "detail": "The only silicon with a native, in-tree Zephyr Controller (Link Layer) today -- documented hardware requirements include the RADIO, RTC, PPI/DPPI, timers, AAR, ECB and CCM crypto blocks. This is the combination most Bluetooth SIG conformance testing runs against."},
            {"name": "Any Bluetooth-HCI-compliant external Controller", "detail": "Host-only builds talk standard HCI over UART/SPI/USB/IPC to any qualified Controller chip -- the whole point of the Host/Controller split is that a Zephyr Host (or Linux BlueZ) can pair with silicon Zephyr doesn't natively drive."},
            {"name": "nRF5340 (dual-core) & similar multi-core SoCs", "detail": "The network core runs a Controller-only HCI-IPC image while the application core runs the Host + app, connected via the IPC subsystem -- two separate Zephyr builds flashed to the same chip."},
            {"name": "Simulation targets (no hardware required)", "detail": "native_sim builds the Host as a native Linux executable; nrf52_bsim / nrf5340bsim use BabbleSim to simulate the nRF5x radio and modem so full multi-device Bluetooth scenarios can run in CI."},
        ],
        "hardware_note": "Caveat: Zephyr's huge Supported Boards list (docs.zephyrproject.org/latest/boards) is not the same as \"chips with a native Combined Bluetooth build.\" Most non-Nordic boards run Zephyr as a Bluetooth Host paired with a separate external Controller chip, rather than Zephyr owning both Host and Controller on that silicon.",
        "missing_features": [
            {"title": "No native Classic (BR/EDR) Controller / Link Layer", "detail": "Zephyr's own Controller implementation is LE-only. Classic Bluetooth (A2DP, AVRCP, HFP, etc.) always requires pairing the Zephyr Host with an external BR/EDR-capable Controller chip -- there is no in-tree Classic radio/Link-Layer."},
            {"title": "Classic profiles sit outside the regular qualification cycle", "detail": "The project's own qualification page states conformance tests run \"on all layers (Controller and Host, except BT Classic)\" -- Classic Host profiles are functional and growing (A2DP, AVRCP, HFP, GOEP, BIP samples all exist) but aren't part of the routine PTS/AutoPTS test sweep the LE stack gets."},
            {"title": "In-tree Controller silicon support is narrow", "detail": "Only Nordic nRF52x/nRF53x get a native, in-tree Link Layer implementation; every other radio vendor needs its own out-of-tree Controller port or an external HCI-connected Controller chip to get a full Combined build."},
            {"title": "Known third-party Controller interop quirks", "detail": "Documented flow-control issues: some Qualcomm Controllers reject Zephyr's default Host-to-Controller flow-control parameters, and some Realtek Controllers send no data back to the Host -- both require manually setting CONFIG_BT_HCI_ACL_FLOW_CONTROL=n as a workaround."},
            {"title": "Dual-chip Linux dev setups are Linux-only", "detail": "Running the Host on QEMU/native_sim against an external Controller, and the BabbleSim-based nrf52_bsim/nrf5340bsim simulators, are documented as GNU/Linux-only -- not available on Windows or macOS development hosts."},
            {"title": "LE Audio / Isochronous Channels are still fast-moving", "detail": "BAP/CAP/TMAP/HAP/PBP and Channel Sounding are real and shipping in samples, but treat them as \"supported but evolving\": Kconfig options, APIs and sample structure have changed materially release to release."},
        ],
        "code_example": {
            "title": "Minimal Bluetooth LE beacon (Eddystone-URL)",
            "filename": "main.c",
            "source_url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-dev.html#bluetooth-application-example",
            "code": (
                "/* Set Advertisement data (Eddystone-URL spec) */\n"
                "static const struct bt_data ad[] = {\n"
                "\tBT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_NO_BREDR),\n"
                "\tBT_DATA_BYTES(BT_DATA_UUID16_ALL, 0xaa, 0xfe),\n"
                "\tBT_DATA_BYTES(BT_DATA_SVC_DATA16,\n"
                "\t\t      0xaa, 0xfe,       /* Eddystone UUID */\n"
                "\t\t      0x10,             /* Eddystone-URL frame type */\n"
                "\t\t      0x00,             /* Calibrated Tx power at 0m */\n"
                "\t\t      0x00,             /* URL Scheme http://www. */\n"
                "\t\t      'z','e','p','h','y','r','p','r','o','j','e','c','t',\n"
                "\t\t      0x08)             /* .org */\n"
                "};\n\n"
                "/* Set Scan Response data */\n"
                "static const struct bt_data sd[] = {\n"
                "\tBT_DATA(BT_DATA_NAME_COMPLETE, DEVICE_NAME, DEVICE_NAME_LEN),\n"
                "};\n\n"
                "static void bt_ready(int err)\n"
                "{\n"
                "\tbt_addr_le_t addr = {0};\n"
                "\tsize_t count = 1;\n\n"
                "\tif (err) {\n"
                "\t\tprintk(\"Bluetooth init failed (err %d)\\n\", err);\n"
                "\t\treturn;\n"
                "\t}\n"
                "\tprintk(\"Bluetooth initialized\\n\");\n\n"
                "\t/* Start advertising */\n"
                "\terr = bt_le_adv_start(BT_LE_ADV_NCONN_IDENTITY, ad, ARRAY_SIZE(ad),\n"
                "\t\t\t      sd, ARRAY_SIZE(sd));\n"
                "\tif (err) {\n"
                "\t\tprintk(\"Advertising failed to start (err %d)\\n\", err);\n"
                "\t\treturn;\n"
                "\t}\n\n"
                "\tbt_id_get(&addr, &count);\n"
                "\tprintk(\"Beacon started, advertising as %s\\n\", bt_addr_le_str(&addr));\n"
                "}\n\n"
                "int main(void)\n"
                "{\n"
                "\tint err;\n\n"
                "\tprintk(\"Starting Beacon Demo\\n\");\n\n"
                "\t/* Initialize the Bluetooth Subsystem */\n"
                "\terr = bt_enable(bt_ready);\n"
                "\tif (err) {\n"
                "\t\tprintk(\"Bluetooth init failed (err %d)\\n\", err);\n"
                "\t}\n"
                "\treturn 0;\n"
                "}"
            ),
            "note": "The two APIs every Zephyr Bluetooth app starts from: bt_enable() to bring up the stack (Host + Controller, whichever build type you chose) and bt_le_adv_start() to broadcast as a GAP Broadcaster. 60+ more complete samples (Peripheral, Central, Mesh, LE Audio, Classic) live in samples/bluetooth/ in the Zephyr source tree.",
        },
        "use_cases": [
            "Wearables & hearables (LE Audio hearing aids)", "Cellular-to-BLE sensor gateways", "Bluetooth Mesh lighting & building automation",
            "Smart locks & digital keys", "Asset & livestock trackers", "Multi-device Bluetooth hubs / dongles", "HID peripherals (keyboards, mice, remotes)",
        ],
        "companies_note": "Real, publicly documented products shipping on the Zephyr Bluetooth stack (source: zephyrproject.org's own showcase, linked per row) -- a representative sample, not an exhaustive list.",
        "companies": [
            {"company": "Ezurio (formerly Laird Connectivity)", "product": "Sentrius\u2122 MG100 Gateway", "feature": "Bluetooth 5 to LTE-M/NB-IoT cellular gateway", "url": "https://www.zephyrproject.org/portfolio/sentrius-mg100-gateway/"},
            {"company": "Ezurio (formerly Laird Connectivity)", "product": "Sentrius\u2122 BT610 I/O Sensor", "feature": "Battery-powered BLE sensor-to-cloud node", "url": "https://www.zephyrproject.org/portfolio/sentrius/"},
            {"company": "Demant / Oticon", "product": "Oticon More\u2122 hearing aid", "feature": "Rechargeable hearing aid using Bluetooth LE connectivity", "url": "https://www.zephyrproject.org/portfolio/oticon-more/"},
            {"company": "Bauer NE", "product": "Bauer NE Bluetooth Smart Lock", "feature": "Keyless BLE entry for RV doors", "url": "https://www.zephyrproject.org/portfolio/bauer-ne/"},
            {"company": "Seeed Studio", "product": "Wio Terminal", "feature": "Bluetooth + Wi-Fi ARM development board", "url": "https://www.zephyrproject.org/portfolio/wio-terminal/"},
            {"company": "Seeed Studio", "product": "SenseCAP T1000-S", "feature": "GNSS / Wi-Fi / Bluetooth LoRaWAN asset tracker", "url": "https://www.zephyrproject.org/portfolio/sensecap-t1000-s-lorawan-tracker/"},
            {"company": "(showcased on zephyrproject.org)", "product": "splitR\u2122", "feature": "Bluetooth receiver/transmitter hub connecting multiple BLE devices simultaneously", "url": "https://www.zephyrproject.org/portfolio/splitr/"},
        ],
        "resources": [
            {"label": "Zephyr Project Introduction", "url": "https://docs.zephyrproject.org/latest/introduction/index.html"},
            {"label": "Bluetooth section home", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/index.html"},
            {"label": "Supported features", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/features.html"},
            {"label": "Qualification (PTS / AutoPTS / QDID)", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-qual.html"},
            {"label": "Stack Architecture (Host/Controller/HCI, build types)", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-arch.html"},
            {"label": "LE Host", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-le-host.html"},
            {"label": "LE Audio Stack architecture", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/api/audio/bluetooth-le-audio-arch.html"},
            {"label": "LE Controller (Link Layer) architecture", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-ctlr-arch.html"},
            {"label": "Application Development guide", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-dev.html"},
            {"label": "API reference index (GAP, GATT, Mesh, Audio, Classic profiles)", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/api/index.html"},
            {"label": "Tools (HCI tracing, sniffing)", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-tools.html"},
            {"label": "Bluetooth shell reference", "url": "https://docs.zephyrproject.org/latest/services/connectivity/bluetooth/bluetooth-shell.html"},
            {"label": "All Bluetooth samples (60+ examples)", "url": "https://docs.zephyrproject.org/latest/samples/bluetooth/bluetooth.html"},
            {"label": "Doxygen API index", "url": "https://docs.zephyrproject.org/latest/doxygen/html/index.html"},
            {"label": "Zephyr Project members", "url": "https://www.zephyrproject.org/members/"},
            {"label": "Products running Zephyr (showcase)", "url": "https://www.zephyrproject.org/products-running-zephyr/"},
        ],
    },
    {
        "slug": "ieee15_4",
        "label": "802.15.4",
        "spec_family": "802.15.4 / thread / matter",
        "tagline": "The low-rate PHY+MAC foundation for Zigbee and Thread; understand this first, then upper layers become much easier.",
        "overview": (
            "IEEE 802.15.4 is the LR-WPAN base standard that defines only two layers: PHY and MAC. "
            "PHY defines channels/modulation/data rates; MAC defines framing, channel access, reliability, "
            "and optional link-layer security. It intentionally does not define end-to-end routing or app "
            "semantics. Zigbee and Thread both reuse the same 802.15.4 radio but build different network "
            "and application ecosystems on top. If you are new: learn MAC behavior first (beacons, CSMA-CA, "
            "ack/retry, association, and security fields), then map how Zigbee and Thread consume those services."
        ),
        "architecture": [
            {"tag": "APP", "name": "Application behavior (not in 802.15.4)", "function": "Zigbee apps use ZCL clusters/commands; Thread apps are IP apps (often CoAP, Matter over IPv6). 802.15.4 does not define app payload meaning."},
            {"tag": "NWK", "name": "Network/routing (not in 802.15.4)", "function": "Zigbee adds its own NWK+APS stack. Thread uses 6LoWPAN+IPv6+MLE. Both consume the same MAC primitives and frame transport below."},
            {"tag": "MAC", "name": "802.15.4 MAC (this is the key layer)", "function": "Creates and parses MAC frames, controls channel access (CSMA-CA), supports association/disassociation, acknowledgment/retry, beacon/superframe timing, addressing, and optional AES-CCM* frame protection."},
            {"tag": "PHY", "name": "802.15.4 PHY", "function": "Transmits symbols on selected channels and reports clear-channel energy/CCA to MAC. Common profile: 2.4 GHz O-QPSK DSSS at 250 kbps with 16 channels (11-26)."},
        ],
        "block_diagram": {
            "caption": "IEEE 802.15.4 defines the two bottom layers and exposes them to upper stacks through Service Access Points (SAPs). The management plane crosses the *-LME-SAP interfaces (MLME, PLME); the data plane crosses the data SAPs (MCPS-SAP data, PD-SAP data). This is the same block-and-interface style used by protocol standards -- learn the SAPs and the layer boundaries become clear.",
            "blocks": [
                {"name": "Upper Layers (Network + Application)", "sub": "Zigbee NWK/APS/ZCL  OR  Thread 6LoWPAN / IPv6 -- not part of 802.15.4", "kind": "upper", "mgmt": "MLME-SAP", "data": "MCPS-SAP"},
                {"name": "MAC Sublayer", "sub": "MLME (management entity)  |  MCPS (common part / data service)", "kind": "mac", "mgmt": "PLME-SAP", "data": "PD-SAP"},
                {"name": "PHY Layer", "sub": "PLME (management entity)  |  PD (data service)", "kind": "phy", "data": "RF signals"},
                {"name": "Physical Radio Medium", "sub": "2.4 GHz O-QPSK DSSS (ch 11-26) | sub-GHz PHYs (868 / 915 MHz) | SUN PHYs", "kind": "medium"},
            ],
        },
        "layer_details": [
            {
                "title": "APP: Payload semantics live above 802.15.4",
                "detail": "An 802.15.4 Data frame only carries bytes. Meaning is provided by upper stacks: Zigbee APS/ZCL messages, Thread 6LoWPAN-compressed IPv6 packets, or Matter interaction-model traffic running over Thread/Wi-Fi.",
                "points": ["No app model in base spec", "Protocol-independent payload", "Interoperability defined above MAC"],
            },
            {
                "title": "NWK: Routing and topology are stack-defined",
                "detail": "802.15.4 can deliver a frame one hop. Multi-hop routing, address assignment policy, route repair, and service discovery are solved by Zigbee or Thread. This separation is why one radio can host multiple upper protocols.",
                "points": ["One-hop MAC transport", "Mesh behavior above MAC", "Zigbee NWK vs Thread IPv6 mesh"],
            },
            {
                "title": "MAC Deep Dive: framing, reliability, and medium access",
                "detail": "MAC defines frame types (Beacon, Data, ACK, MAC Command), frame-control bits (ack request, security enabled, PAN-ID compression, frame pending), sequence numbers, address fields, and FCS. For access, devices run slotted or unslotted CSMA-CA based on mode. Reliability is built with immediate ACKs and retry limits. Management commands cover association, disassociation, orphan notification, and data request for sleepy children.",
                "points": ["Frame control and addressing", "ACK + retry behavior", "Association/disassociation", "CSMA-CA", "Beacon/superframe", "Indirect data + frame pending", "MAC command set"],
            },
            {
                "title": "PHY Deep Dive: channels and CCA feedback",
                "detail": "PHY handles modulation/spreading, symbol timing, and channel selection. It offers key primitives to MAC: transmit, receive, energy detect, and clear-channel assessment. MAC uses CCA results during CSMA-CA backoff loops before transmission.",
                "points": ["2.4 GHz channels 11-26", "O-QPSK DSSS (common)", "ED/CCA primitives", "CCA mode selection", "Sub-GHz variants"],
            },
        ],
        "core_concepts": [
            {"term": "PAN & PAN Coordinator", "definition": "A Personal Area Network is identified by a PAN ID; the PAN Coordinator is the device that starts the network and picks the operating channel."},
            {"term": "FFD vs. RFD", "definition": "A Full Function Device can route and act as a coordinator; a Reduced Function Device is a simple end node (e.g. a battery sensor) that only talks to its parent."},
            {"term": "Beacon-enabled vs. non-beacon", "definition": "Beacon-enabled PANs use superframes timed by periodic beacons. Non-beacon mode is asynchronous and typically used by Thread; devices contend with unslotted CSMA-CA when data exists."},
            {"term": "Superframe (BO/SO)", "definition": "Beacon mode organizes time into Beacon Interval and active Superframe Duration. The active period contains CAP (contention access) and optional CFP with GTS allocations (up to 7 in classic mode)."},
            {"term": "CSMA-CA", "definition": "Before transmit, a node waits random backoff slots, performs CCA, and transmits only when channel is idle. On busy channel it increases backoff state and retries according to configured limits."},
            {"term": "MAC frame anatomy", "definition": "Typical MPDU fields: Frame Control, Sequence Number, Address fields (PAN ID + short/extended addresses), Auxiliary Security Header (if enabled), payload, then FCS."},
            {"term": "Acknowledgment and retransmission", "definition": "A sender can request ACK. If ACK is not received in time, MAC retries transmission up to configured limits. This provides link reliability without requiring upper-layer retries for every hop."},
            {"term": "Addressing", "definition": "Devices can use a globally-unique 64-bit extended address (like a MAC address) or a short 16-bit address assigned after joining a PAN, to keep frame headers small."},
            {"term": "MAC security", "definition": "802.15.4 supports AES-CCM* with frame counters and security control fields to provide integrity, replay protection, and optional confidentiality at link layer."},
            {"term": "CCA failure budget", "definition": "High CCA busy counts indicate contention/interference. Rising CCA failures usually predict retransmission storms and battery drain before app-level errors appear."},
            {"term": "Retry/latency tradeoff", "definition": "Higher retry limits improve delivery probability but increase worst-case latency and airtime. Control loops and battery products should tune retries differently."},
        ],
        "how_it_works": [
            {"title": "1. PAN formation", "detail": "A coordinator scans for a quiet channel, picks a PAN ID, and starts the network -- it becomes the root that other devices join."},
            {"title": "2. Beacon timing or asynchronous mode", "detail": "Beacon-enabled networks advertise superframe timing; non-beacon networks skip periodic beacons and rely on contention access plus parent/child polling patterns for sleepy nodes."},
            {"title": "3. Discovery and association", "detail": "A new node scans channels, evaluates beacons/energy, chooses a parent/coordinator, then exchanges MAC command frames to associate and optionally receive a short address."},
            {"title": "4. Channel access with CSMA-CA", "detail": "The sender enters backoff, runs CCA, and transmits only on idle medium. In beacon mode this is slotted CSMA-CA aligned to superframe slots; otherwise unslotted."},
            {"title": "5. Per-hop reliability", "detail": "Data frame may request ACK. Receiver sends ACK quickly after successful FCS/sequence validation. Missing ACK triggers retry and potential channel-contention repeat."},
            {"title": "6. Sleepy-device exchange", "detail": "Battery end devices can poll parent for pending data using MAC command frames. Parent indicates pending status and delivers queued frames when child wakes."},
            {"title": "7. Security processing", "detail": "If security is enabled, transmitter adds auxiliary security header and frame counter; receiver validates counter/freshness and integrity before accepting payload."},
            {"title": "8. Handoff to upper protocol", "detail": "After MAC accepts payload, bytes are passed to Zigbee NWK/APS or Thread 6LoWPAN/IPv6. At that point routing, sessions, and app semantics are owned above 802.15.4."},
            {"title": "9. Performance tuning cycle", "detail": "Deployments are tuned by observing ED scans, CCA busy rate, ACK loss, retry counts, and parent-poll intervals, then adjusting channel plan and MAC parameters to stabilize latency and battery life."},
        ],
        "developer_view": [
            {"title": "What app developers touch vs. stack developers", "detail": "Raw MAC APIs are MLME/MCPS primitives used by stack implementers. Product teams usually consume Zigbee SDK APIs or OpenThread APIs because those expose discoverable network/app abstractions."},
            {"title": "When raw MAC knowledge still matters", "detail": "Even if you use Zigbee/Thread APIs, MAC behavior affects your product: channel plan, parent-child polling cadence, ACK/retry tuning, and coexistence with Wi-Fi/BLE strongly influence battery life and reliability."},
            {"title": "Debugging strategy", "detail": "Start at MAC: verify channel occupancy/CCA failures, retry counters, and ACK success. Then move up to NWK/IPv6 routing. This layered approach prevents app-level blame for radio-level loss.",},
            {"title": "Portable implementation mindset", "detail": "Keep app logic above protocol-specific abstractions (ZCL clusters or CoAP resources). Avoid chipset-specific assumptions in payload formats or security policy so migration across silicon families is easier."},
            {"title": "Field telemetry that matters", "detail": "Track per-node CCA busy rate, MAC retry histograms, parent change events, and average poll interval. These indicators correlate directly with user-visible reliability and battery complaints."},
        ],
        "use_cases": [
            "Zigbee smart bulbs, switches, meters, and sensors",
            "Thread and Matter-over-Thread smart-home endpoints",
            "Battery-operated mesh sensors with parent-child polling",
            "Industrial and building automation low-rate control meshes",
            "Sub-GHz long-range telemetry in applicable regional profiles",
        ],
        "resources": [
            {"label": "IEEE 802.15.4 standard (IEEE-SA)", "url": "https://standards.ieee.org/ieee/802.15.4/7029/"},
            {"label": "IEEE 802.15 Working Group (public documents)", "url": "https://www.ieee802.org/15/"},
            {"label": "6LoWPAN over IEEE 802.15.4 -- RFC 4944", "url": "https://www.rfc-editor.org/rfc/rfc4944"},
            {"label": "See the Zigbee and Thread tabs for the stacks built on top", "url": "#"},
        ],
    },
    {
        "slug": "wifi",
        "label": "Wi-Fi",
        "spec_family": "wi-fi",
        "tagline": "Full IP-networking wireless LAN -- higher power and throughput than BLE/802.15.4, used when a device needs real internet bandwidth.",
        "overview": (
            "Wi-Fi (the IEEE 802.11 family, certified by the Wi-Fi Alliance) is a wireless LAN "
            "technology that -- unlike Bluetooth LE or 802.15.4 -- carries a full, standard IP stack. "
            "A Wi-Fi radio is effectively the link layer under ordinary TCP/IP networking, which is why "
            "Wi-Fi devices can run any internet protocol (HTTP, MQTT, CoAP) without a technology-specific "
            "application model. The tradeoff versus BLE/802.15.4 is power: Wi-Fi radios are far more "
            "capable but consume much more energy, which is why battery-IoT designs often pair Wi-Fi "
            "with Bluetooth for provisioning and use features like Target Wake Time to save power."
        ),
        "architecture": [
            {"tag": "APP", "name": "Application layer", "function": "Ordinary IP applications -- HTTP, MQTT, CoAP, or any custom protocol. Wi-Fi does not define its own application model; it just delivers IP packets."},
            {"tag": "TCP/IP", "name": "Network / Transport (TCP/IP stack)", "function": "Standard IPv4/IPv6 addressing and routing, with TCP or UDP transport -- the same stack used on Ethernet, just carried over a radio link."},
            {"tag": "MAC", "name": "MAC layer (802.11)", "function": "CSMA/CA channel access, management/control/data frame types, the authentication & association state machine, WPA2/WPA3 security handshakes, QoS (WMM), power-save modes, and -- new in Wi-Fi 7 -- Multi-Link Operation (MLO) letting one device use several bands/links at once."},
            {"tag": "PHY", "name": "Physical layer (802.11a/b/g/n/ac/ax/be)", "function": "OFDM/OFDMA modulation across 2.4/5/6 GHz bands with channel widths from 20 MHz up to 320 MHz (Wi-Fi 7), MIMO/MU-MIMO spatial streams, plus Wi-Fi HaLow (802.11ah) -- a sub-1 GHz, long-range, low-power PHY variant built for IoT rather than high throughput."},
        ],
        "core_concepts": [
            {"term": "SSID / BSSID / AP vs. Station", "definition": "The SSID is the human-readable network name; the BSSID is the AP radio's MAC address. An Access Point (AP) serves multiple client Stations (STAs)."},
            {"term": "WPA2/WPA3 & SAE", "definition": "WPA2 uses a Pre-Shared Key with a 4-Way Handshake; WPA3 replaces the PSK exchange with SAE (Simultaneous Authentication of Equals), which resists offline dictionary attacks."},
            {"term": "OFDMA / MU-MIMO", "definition": "Techniques (from Wi-Fi 6 onward) that let an AP serve multiple clients' data in the same time-frequency resource, dramatically improving efficiency in dense environments."},
            {"term": "MLO (Multi-Link Operation)", "definition": "New in Wi-Fi 7: a single device can transmit/receive across multiple bands (e.g. 5 GHz + 6 GHz) simultaneously for higher throughput and lower latency."},
            {"term": "Target Wake Time (TWT)", "definition": "Lets a battery-powered Wi-Fi device negotiate a schedule with the AP so it can sleep between agreed wake windows -- the key power-saving feature for Wi-Fi IoT devices."},
            {"term": "Roaming (802.11k/v/r)", "definition": "Assist protocols that help a station moving between APs (e.g. in a mesh) hand off quickly with minimal reassociation delay."},
        ],
        "how_it_works": [
            {"title": "1. Scanning", "detail": "A station passively listens for Beacon frames or actively sends Probe Requests to discover nearby APs and their capabilities."},
            {"title": "2. Authentication", "detail": "Open System authentication (essentially a formality) or WPA3's SAE handshake establishes initial cryptographic trust before association."},
            {"title": "3. Association", "detail": "The station formally joins the AP's Basic Service Set (BSS), negotiating supported data rates and capabilities -- including setting up multiple simultaneous links if using Wi-Fi 7 MLO."},
            {"title": "4. 4-Way Handshake (WPA2/3)", "detail": "Derives a per-session Pairwise Transient Key from the Pairwise Master Key to encrypt unicast traffic, plus a Group Temporal Key for broadcast/multicast traffic."},
            {"title": "5. Data transfer", "detail": "The MAC layer contends for the channel via CSMA/CA (or uses scheduled OFDMA/MU-MIMO access in modern Wi-Fi) while IP packets are encapsulated into 802.11 data frames."},
            {"title": "6. Power management", "detail": "IoT-class devices negotiate Target Wake Time windows (or use legacy PS-Poll) so the radio can sleep between scheduled transmissions instead of staying fully powered."},
            {"title": "7. Roaming", "detail": "802.11k/v/r let a moving station discover and hand off to a better AP quickly, minimizing the reassociation gap."},
        ],
        "developer_view": [
            {"title": "You mostly use normal networking APIs", "detail": "Because Wi-Fi presents a standard IP link, application code uses ordinary BSD sockets or protocol client libraries (MQTT, HTTP, CoAP) -- the Wi-Fi-specific work (scanning, association, security) is handled by the OS or driver beneath you."},
            {"title": "Platform / driver layer", "detail": "Linux uses wpa_supplicant; Android/iOS have native Wi-Fi stacks; embedded designs use a vendor Wi-Fi Host Driver (e.g. Espressif ESP-IDF's Wi-Fi driver, Infineon AIROC WHD) that exposes scan/connect/provision APIs to your firmware."},
            {"title": "Provisioning headless devices", "detail": "Since a Wi-Fi IoT device has no keyboard, typical flows are SoftAP + captive portal (device becomes a temporary AP for setup) or BLE-assisted provisioning (as used by Matter) to hand over Wi-Fi credentials securely."},
            {"title": "Power-aware design", "detail": "If you're building a battery Wi-Fi product, design around Target Wake Time and minimize how often the radio has to wake and re-associate -- this is usually the single biggest power lever available."},
        ],
        "use_cases": [
            "Home & mesh routers", "Smart cameras & video doorbells", "Matter-over-Wi-Fi smart home devices",
            "Industrial wireless backhaul", "Wi-Fi HaLow long-range sensor & agriculture IoT",
        ],
        "resources": [
            {"label": "Wi-Fi Alliance -- Wi-Fi CERTIFIED 7", "url": "https://www.wi-fi.org/discover-wi-fi/wi-fi-certified-7"},
            {"label": "IEEE 802.11 standards family", "url": "https://www.ieee802.org/11/"},
        ],
    },
    {
        "slug": "thread",
        "label": "Thread",
        "spec_family": "802.15.4 / thread / matter",
        "tagline": "An IPv6 mesh network built on 802.15.4 radios -- the low-power backbone most Matter smart-home devices run on.",
        "overview": (
            "Thread is a mesh networking protocol -- standardized by the Thread Group -- that gives every "
            "device on the mesh a real, routable IPv6 address, unlike Zigbee's proprietary networking "
            "layer. It reuses the IEEE 802.15.4 radio (2.4 GHz) but replaces Zigbee's NWK layer with "
            "6LoWPAN + IPv6 mesh routing, so any standard IP or CoAP application can run over it. Thread "
            "is the low-power mesh transport most Matter devices use under the hood."
        ),
        "architecture": [
            {"tag": "APP", "name": "Application layer", "function": "Any IP application protocol -- most commonly CoAP for device control, or Matter's data model layered directly on top of Thread's IPv6 transport (see the Matter tab)."},
            {"tag": "NWK", "name": "Thread networking layer", "function": "6LoWPAN header compression/fragmentation of IPv6 over 802.15.4, Mesh Link Establishment (MLE) for topology/routing, Network Data distribution (prefixes, DNS/services), and the Border Router function that bridges the mesh to Wi-Fi/Ethernet and the internet."},
            {"tag": "MAC/PHY", "name": "IEEE 802.15.4 MAC/PHY", "function": "The same radio layer used by Zigbee (2.4 GHz, CSMA-CA channel access) -- Thread's innovation is entirely in the networking layer above it, not the radio itself."},
        ],
        "block_diagram": {
            "caption": "Thread keeps the 802.15.4 MAC/PHY but replaces proprietary networking with a standards-based IPv6 stack: 6LoWPAN adapts IPv6 to the small 802.15.4 frame, MLE builds and heals the mesh, and applications talk plain UDP/CoAP (or Matter) on top. Because every node has a real IPv6 address, ordinary IP tooling works end-to-end.",
            "blocks": [
                {"name": "Application", "sub": "CoAP / UDP apps | Matter data model over IPv6", "kind": "upper", "iface": "UDP sockets / CoAP"},
                {"name": "IPv6 + Transport", "sub": "IPv6 | ICMPv6 | UDP | DTLS (commissioning security)", "kind": "nwk", "iface": "IPv6 datagrams"},
                {"name": "Mesh routing + Adaptation", "sub": "MLE mesh link establishment | Network Data | 6LoWPAN header compression & fragmentation", "kind": "mac", "iface": "MCPS / MLME (SAPs)"},
                {"name": "IEEE 802.15.4 MAC", "sub": "CSMA-CA | ACK / retry | AES-CCM* link security", "kind": "phy", "iface": "PD / PLME"},
                {"name": "IEEE 802.15.4 PHY + Radio", "sub": "2.4 GHz O-QPSK DSSS | channels 11-26", "kind": "medium"},
            ],
        },
        "layer_details": [
            {
                "title": "APP: standard IP applications",
                "detail": "Because a Thread node is a full IPv6 host, application code is ordinary networking code -- CoAP or UDP sockets, or a Matter session. No proprietary application framework is imposed by Thread itself.",
                "points": ["CoAP / UDP", "Matter over Thread", "Standard IP tooling"],
            },
            {
                "title": "NWK: 6LoWPAN + IPv6 + MLE",
                "detail": "6LoWPAN compresses and fragments IPv6 to fit 802.15.4 frames. IPv6/ICMPv6/UDP provide addressing and transport. Mesh Link Establishment (MLE) discovers neighbors, builds routing tables, and keeps the mesh self-healing. Network Data distributes prefixes and services.",
                "points": ["6LoWPAN adaptation", "IPv6 / UDP", "MLE mesh routing", "RLOC / ML-EID addressing", "Network Data"],
            },
            {
                "title": "MAC/PHY: reused 802.15.4 radio",
                "detail": "Thread does not modify the radio -- it consumes the same 802.15.4 MAC (CSMA-CA, ACK/retry, AES-CCM* link security) and PHY (2.4 GHz O-QPSK) described on the 802.15.4 tab.",
                "points": ["802.15.4 MAC", "802.15.4 PHY", "Battery-friendly radio"],
            },
        ],
        "core_concepts": [
            {"term": "Leader", "definition": "An elected router responsible for network-wide configuration (like assigning router IDs); if it goes offline, another eligible router is elected automatically."},
            {"term": "Router / REED / End Device", "definition": "Routers forward mesh traffic and can have children; a Router-Eligible End Device (REED) can be promoted to a Router if the mesh needs more routing capacity; simple End Devices only talk to their parent."},
            {"term": "Border Router", "definition": "Bridges the Thread mesh to the home's IP network (Wi-Fi/Ethernet) and the internet, advertises the mesh's routable IPv6 prefix, and proxies mDNS/DNS-SD so devices are discoverable from outside the mesh."},
            {"term": "Commissioning", "definition": "The secure process of adding a new device to the mesh -- a Commissioner (often a phone app) and a Joiner exchange credentials (via DTLS) so the Joiner can obtain the network key."},
            {"term": "Mesh Link Establishment (MLE)", "definition": "The protocol routers use to discover neighbors, build routing tables, and keep the mesh self-healing if a router drops out."},
        ],
        "how_it_works": [
            {"title": "1. Network formation", "detail": "A Leader is elected among capable routers; the network's channel, PAN ID, and network key are established for the mesh."},
            {"title": "2. Commissioning", "detail": "A new device (Joiner) is securely admitted using a DTLS-based exchange with a Commissioner -- typically brokered through the Border Router -- and receives the network key."},
            {"title": "3. Attaching", "detail": "The joined device attaches to a suitable parent Router, becoming a Router, REED, or End Device, and is assigned a 16-bit Routing Locator (RLOC) plus a full IPv6 address."},
            {"title": "4. Routing", "detail": "Devices route IPv6 packets hop-by-hop using MLE-derived routing tables; if a router fails, the mesh recalculates routes and self-heals without manual intervention."},
            {"title": "5. Border routing & discovery", "detail": "The Border Router advertises an Off-Mesh Routable (OMR) prefix to the home network and relays traffic between Thread and Wi-Fi/Ethernet/the internet, including proxying mDNS service discovery."},
            {"title": "6. Application data", "detail": "CoAP/UDP messages -- or a Matter application session -- ride over the IPv6 transport exactly like they would on any other IP network."},
        ],
        "developer_view": [
            {"title": "OpenThread", "detail": "The open-source Thread stack (originally from Google/Nest) implements the full networking layer and exposes a C API for network management; it's used inside the Nordic, Silicon Labs, NXP, and TI SDKs rather than being reimplemented per vendor."},
            {"title": "Plain IP APIs above OpenThread", "detail": "Because a Thread device is just an IPv6 host, you can use standard CoAP client/server libraries directly for custom device control instead of building a Zigbee-style proprietary protocol."},
            {"title": "Matter as the common application layer", "detail": "Most product teams don't write raw CoAP against Thread directly -- they build on Matter's data model (Clusters/Attributes/Commands), which already runs over Thread's IPv6 transport. See the Matter tab."},
            {"title": "Border Router reference implementation", "detail": "OpenThread Border Router (OTBR) is the standard reference implementation, commonly run on a Raspberry Pi or embedded into smart speakers/hubs (Apple TV, Google Nest Hub, Amazon Echo, etc.)."},
        ],
        "thread_in_depth": [
            {
                "title": "Why Thread uses IPv6 instead of a proprietary mesh",
                "detail": "Giving every node a routable IPv6 address means Thread reuses decades of proven IP protocols (UDP, CoAP, DTLS, mDNS) instead of reinventing them. A phone or cloud service can address a Thread device the same way it addresses any internet host, through the Border Router -- this is the core reason modern smart-home standards chose Thread.",
            },
            {
                "title": "Device roles and mesh resilience",
                "detail": "Routers form the always-on mesh backbone and forward traffic. A Router-Eligible End Device (REED) can be promoted to Router when the mesh needs more capacity. Minimal/Sleepy End Devices (MED/SED) only talk to a parent Router and sleep to save battery. One Leader coordinates network-wide configuration; if it drops, another Router is elected automatically -- there is no single point of failure.",
            },
            {
                "title": "Addressing model (RLOC, ML-EID, GUA)",
                "detail": "Each node has a Routing Locator (RLOC) that reflects its position in the mesh and changes as topology changes, plus a stable Mesh-Local EID (ML-EID) for identity within the mesh. When a Border Router advertises an Off-Mesh-Routable prefix, nodes also gain a Global Unicast Address reachable from outside the mesh.",
            },
            {
                "title": "Commissioning (secure joining)",
                "detail": "A new device (Joiner) is admitted through a DTLS-secured handshake with a Commissioner -- typically a phone app brokered via the Border Router. The Joiner proves knowledge of a pre-shared commissioning credential, then receives the network credentials so it can attach to a parent and route traffic.",
            },
            {
                "title": "Border Router: bridging to the internet",
                "detail": "The Thread Border Router connects the low-power mesh to Wi-Fi/Ethernet, advertises routable prefixes, and proxies mDNS/DNS-SD so mesh devices are discoverable from the home network. Matter-over-Thread depends on this bridge for controllers (phones, hubs) to reach devices.",
            },
            {
                "title": "OpenThread as the reference stack",
                "detail": "OpenThread is the open-source implementation of the full Thread networking layer and role/state machines. It is integrated into the SDKs of most silicon vendors rather than reimplemented per chip, so behavior is consistent across hardware and certification is simpler.",
            },
            {
                "title": "Capability profile for product teams",
                "detail": "Thread's key capability is IP-native low-power mesh: every node is addressable with standard network tooling, Border Routers can be redundant, and Matter rides naturally on top. This makes Thread highly suitable for future-proof smart-home products that need deep ecosystem interoperability.",
            },
            {
                "title": "Operational levers that move outcomes",
                "detail": "Most field issues are driven by Border Router placement/quality, parent selection stability for sleepy nodes, and 2.4 GHz coexistence planning. Instrumenting attach time, parent switches, and route churn is more valuable than app-only telemetry.",
            },
        ],
        "use_cases": [
            "Matter-over-Thread smart home devices (locks, sensors, bulbs)", "Always-on low-power mesh sensor networks",
            "Devices needing IP-routability without a Wi-Fi radio's power cost",
        ],
        "resources": [
            {"label": "Thread Group", "url": "https://www.threadgroup.org/"},
            {"label": "OpenThread (open-source stack)", "url": "https://openthread.io/"},
        ],
    },
    {
        "slug": "matter",
        "label": "Matter",
        "spec_family": "802.15.4 / thread / matter",
        "tagline": "The application-layer smart-home standard -- runs over Thread, Wi-Fi, or Ethernet, using BLE only to get a device onto the network.",
        "overview": (
            "Matter (from the Connectivity Standards Alliance) is not a radio technology -- it's an "
            "application-layer standard that defines a common data model so smart-home devices from "
            "different manufacturers interoperate regardless of which network they run on (Thread, "
            "Wi-Fi, or Ethernet). Bluetooth LE is used only during the initial commissioning handshake; "
            "after that, all operational traffic runs over IP. This is the single most important thing "
            "to understand about Matter's architecture -- it deliberately reuses Thread and Wi-Fi rather "
            "than inventing a new radio layer."
        ),
        "architecture": [
            {"tag": "DM", "name": "Application / Data Model", "function": "Devices are modeled as Device Types (e.g. On/Off Light, Door Lock, Thermostat) composed of Clusters (e.g. On/Off, Level Control, Door Lock), each exposing Attributes (state), Commands (actions), and Events -- conceptually the IP-native equivalent of BLE's GATT Services/Characteristics."},
            {"tag": "IM", "name": "Interaction Model", "function": "Defines how a Controller Reads/Writes Attributes, Invokes Commands, and Subscribes to Attribute/Event reports over an established session -- this is the API surface every Matter controller and device implementation uses."},
            {"tag": "SEC", "name": "Security / Fabric layer", "function": "A Fabric is a set of mutually-trusted nodes with a shared root of trust. Commissioning uses PASE (password-based) for the initial secure session, then issues each device a Node Operational Certificate for ongoing CASE (certificate-based) sessions."},
            {"tag": "TRANS", "name": "Transport", "function": "Matter messages travel over UDP via a lightweight message-framing layer across whatever IP network is available -- Bluetooth LE is used ONLY for commissioning, never for normal operation."},
            {"tag": "NET", "name": "Network layer", "function": "Matter does not define its own radio or mesh -- it rides on Thread's IPv6 mesh or on Wi-Fi/Ethernet IP connectivity, reusing whichever transport the device already has."},
        ],
        "core_concepts": [
            {"term": "Fabric", "definition": "A logical smart-home network of mutually-trusted Nodes sharing a root Certificate Authority; a device can belong to multiple Fabrics at once (Multi-Admin) so it works simultaneously with, e.g., Apple Home and Google Home."},
            {"term": "Node / Endpoint / Cluster", "definition": "A physical device is a Node; a Node exposes one or more Endpoints (e.g. a power strip might expose 4 outlet endpoints); each Endpoint implements Clusters that define its actual behavior."},
            {"term": "Commissioner / Commissionee", "definition": "The Commissioner is the controller app doing the onboarding (e.g. a phone); the Commissionee is the new, uncommissioned device being set up."},
            {"term": "PASE vs. CASE", "definition": "PASE (Password Authenticated Session Establishment, via SPAKE2+) is used once, over BLE, purely to bootstrap the device onto the network; CASE (Certificate Authenticated Session Establishment) secures all subsequent normal operation over IP."},
            {"term": "Multi-Admin / Joint Fabric", "definition": "Multi-Admin lets several ecosystems control one device on one Fabric; Joint Fabric (introduced in Matter 1.6) extends this to formally share devices and structure across multiple independent Fabrics."},
        ],
        "how_it_works": [
            {"title": "1. Discovery", "detail": "The Commissioner (a phone app) discovers the uncommissioned device via Bluetooth LE advertising (or a Wi-Fi SoftAP fallback) after scanning its setup QR code / manual pairing code."},
            {"title": "2. PASE over BLE", "detail": "A temporary secure session is established over Bluetooth LE using the device's setup passcode via a SPAKE2+ key exchange -- this session exists purely to bootstrap the device, and is never used again afterward."},
            {"title": "3. Network provisioning", "detail": "Over that secure PASE session, the Commissioner sends the device its Wi-Fi credentials, or a Thread network dataset, letting the device join the real IP network."},
            {"title": "4. Operational credentials", "detail": "The Commissioner issues the device a Node Operational Certificate (NOC) signed by the Fabric's root CA, formally admitting it to the Fabric."},
            {"title": "5. CASE sessions take over", "detail": "From this point forward, the device and any other Fabric member (hubs, controllers) establish CASE sessions -- mutual certificate-based authentication over IP. Bluetooth is not used again."},
            {"title": "6. Interaction", "detail": "Controllers Read or Subscribe to Cluster Attributes (e.g. current on/off state) and Invoke Commands (e.g. \"Toggle\") to operate the device; subscriptions let multiple ecosystems stay in sync in real time (Multi-Admin)."},
        ],
        "developer_view": [
            {"title": "connectedhomeip SDK", "detail": "The open-source Matter SDK provides the data model, standard Cluster implementations, and the full commissioning flow; silicon vendors (NXP, Silicon Labs, Espressif, Nordic, Infineon) ship SDKs built directly on top of it."},
            {"title": "Building a device", "detail": "Device developers implement standard Device Types/Clusters from the Matter Device Library so any certified controller works out of the box -- the real engineering effort is usually the sensor/actuator driver underneath, not the network protocol."},
            {"title": "Building a controller/app", "detail": "Controller developers use a Matter controller SDK (or CHIP Tool for testing) to commission and operate devices purely through the standardized Cluster model -- no device-specific integration code needed, unlike pre-Matter smart-home APIs."},
            {"title": "Testing tools", "detail": "CHIP Tool (command-line controller) and the Matter Test Harness are the standard ways to commission and exercise a device during development before certification."},
        ],
        "use_cases": [
            "Smart lights, plugs, locks & thermostats", "Sensors that must work across Apple Home, Google Home, Alexa & SmartThings simultaneously",
            "Multi-vendor smart-home ecosystems requiring true interoperability",
        ],
        "resources": [
            {"label": "CSA -- Matter specification hub", "url": "https://csa-iot.org/all-solutions/matter/"},
            {"label": "connectedhomeip (Matter SDK, open source)", "url": "https://github.com/project-chip/connectedhomeip"},
            {"label": "Matter developer handbook", "url": "https://handbook.buildwithmatter.com/"},
        ],
    },
    {
        "slug": "aliro",
        "label": "Aliro",
        "spec_family": "uwb",
        "tagline": "A CSA standard for interoperable digital keys -- so one phone credential unlocks doors from many different lock brands.",
        "overview": (
            "Aliro (from the Connectivity Standards Alliance) standardizes digital-key access control -- "
            "letting a phone or wearable act as a key for doors (hotels, residences, offices, cars) using "
            "a common credential format across NFC, Bluetooth LE, and optionally UWB. Before Aliro, each "
            "lock brand needed its own proprietary app; Aliro's goal is that any certified wallet works "
            "with any certified reader, the same way EMV made contactless payment cards interoperable "
            "across banks and terminals."
        ),
        "architecture": [
            {"tag": "APP", "name": "Application layer", "function": "The use-case logic -- hotel check-in, residential lock management, or car access -- implemented by the wallet app or device manufacturer's software."},
            {"tag": "CRED", "name": "Credential layer", "function": "A standardized Access Control Credential format and endpoint model defining how a digital key is provisioned and securely stored (typically in a phone's Secure Element), so any Aliro-certified reader can validate it."},
            {"tag": "SEC", "name": "Secure transaction layer", "function": "A mutual-authentication and encrypted-transaction protocol between the endpoint (phone) and the reader (lock), designed so neither a cloned credential nor a spoofed reader can succeed."},
            {"tag": "RADIO", "name": "Radio / transport layer", "function": "NFC for instant tap-to-unlock with no pairing step, and BLE (optionally combined with UWB) for hands-free, walk-up proximity unlock -- UWB adds precise ranging to prevent relay attacks that plain BLE proximity is vulnerable to."},
        ],
        "core_concepts": [
            {"term": "Digital Key credential", "definition": "The cryptographic access token issued to a user's device, functionally equivalent to a physical key or card, but revocable and shareable digitally."},
            {"term": "Reader vs. Endpoint", "definition": "The Reader is the lock's radio + validation hardware; the Endpoint is the phone or wearable holding the credential that presents itself to the Reader."},
            {"term": "NFC tap vs. BLE/UWB proximity", "definition": "NFC requires a deliberate tap (very fast, no pairing); BLE/UWB proximity unlock is hands-free as the user simply walks up, with UWB providing precise distance/angle for security."},
            {"term": "Relay-attack resistance", "definition": "Plain Bluetooth 'in range' checks can be tricked by relaying signals over the internet between a thief's phone and the real key; UWB ranging measures true physical distance/angle, closing that hole."},
            {"term": "Interoperability certification", "definition": "The core promise of Aliro: a credential issued by any certified wallet app must work with any certified reader, regardless of manufacturer."},
        ],
        "how_it_works": [
            {"title": "1. Provisioning", "detail": "A digital key is issued to the user's device (e.g. via a hotel or residential app) and stored securely, typically in the phone's Secure Element or equivalent protected storage."},
            {"title": "2. Discovery", "detail": "As the user approaches or taps, the Reader and Endpoint discover each other via NFC field detection or BLE advertising."},
            {"title": "3. Mutual authentication", "detail": "The Reader and Endpoint perform a cryptographic handshake confirming both are genuine and that the credential is valid and has not been revoked."},
            {"title": "4. Ranging (optional, UWB)", "detail": "For walk-up-and-unlock scenarios, UWB measures precise distance and angle to confirm the phone is physically at the door -- protecting against relay attacks that a simple 'is it in Bluetooth range' check cannot."},
            {"title": "5. Unlock", "detail": "Once authenticated (and, where used, ranging-confirmed), the Reader actuates the physical lock mechanism and can log the access event."},
        ],
        "developer_view": [
            {"title": "Wallet/app integration", "detail": "App developers integrate against the CSA-published Aliro Digital Key API to provision credentials into secure storage and present them to readers -- the app doesn't need to know the internal lock brand's protocol."},
            {"title": "Reader/lock integration", "detail": "Lock manufacturers implement Aliro's reader-side validation stack so their hardware accepts credentials from any certified wallet, rather than shipping a proprietary companion app per lock line."},
            {"title": "Radio hardware choices", "detail": "Chip vendors offer combined NFC + BLE (+ optional UWB) modules and reference designs specifically targeting Aliro Reader and Endpoint roles -- this is a key design decision when picking silicon for a lock or wearable product."},
        ],
        "use_cases": [
            "Residential smart locks", "Hotel room access", "Corporate badge / building access replacement", "Connected-car digital key",
        ],
        "resources": [
            {"label": "CSA -- Aliro overview", "url": "https://csa-iot.org/all-solutions/aliro/"},
            {"label": "FiRa Consortium (UWB ranging used by Aliro)", "url": "https://www.firaconsortium.org/"},
        ],
    },
    {
        "slug": "zigbee",
        "label": "Zigbee",
        "spec_family": "zigbee",
        "tagline": "A full mesh network + application framework on top of 802.15.4 -- standardized clusters let multi-vendor devices interoperate out of the box.",
        "overview": (
            "Zigbee is a complete low-power mesh networking and application standard (governed by the "
            "Connectivity Standards Alliance) that runs on the IEEE 802.15.4 radio. Where 802.15.4 stops "
            "at PHY and MAC, Zigbee adds everything above: a Network (NWK) layer for mesh routing, an "
            "Application Support Sublayer (APS) for endpoint addressing and binding, the Zigbee Device "
            "Object (ZDO) for device and service management, and the Zigbee Cluster Library (ZCL) that "
            "defines standardized application behavior. That ZCL layer is the key idea -- because clusters "
            "like On/Off, Level Control, and Color Control are standardized, a bulb from one vendor and a "
            "switch from another interoperate. Zigbee is a mature, widely deployed ecosystem for lighting, "
            "sensors, and building automation, and it now interworks with Matter through bridges."
        ),
        "architecture": [
            {"tag": "ZCL", "name": "Application layer (ZCL + application objects)", "function": "Standardized Clusters (On/Off, Level Control, Color Control, Thermostat, etc.) exposed on Endpoints. Each cluster defines Attributes (state) and Commands (actions) -- the interoperable behavior contract between devices from different vendors."},
            {"tag": "APS", "name": "Application Support Sublayer (APS)", "function": "Endpoint addressing, the binding table (linking, e.g., a switch endpoint to a light endpoint), APS-level security, and fragmentation/reassembly of large application messages."},
            {"tag": "ZDO", "name": "Zigbee Device Object (ZDO)", "function": "Device and service discovery, network join/leave management, binding management, and definition of the device roles (Coordinator, Router, End Device)."},
            {"tag": "NWK", "name": "Network layer (NWK)", "function": "Mesh route discovery and forwarding, 16-bit network address assignment, network-key security, and neighbor/route table maintenance across routers."},
            {"tag": "MAC", "name": "IEEE 802.15.4 MAC", "function": "Reused unchanged: CSMA-CA channel access, acknowledgment/retry, addressing, and optional AES-CCM* link security (see the 802.15.4 tab)."},
            {"tag": "PHY", "name": "IEEE 802.15.4 PHY", "function": "Reused unchanged: 2.4 GHz O-QPSK DSSS at 250 kbps (channels 11-26), plus sub-GHz options in some regional profiles."},
        ],
        "block_diagram": {
            "caption": "Zigbee builds a full mesh + application framework on top of the 802.15.4 MAC/PHY. Each layer talks to the one below through defined service primitives (APS uses NLDE/NLME; NWK uses the 802.15.4 MCPS/MLME SAPs). ZDO sits beside APS as the management brain of the device.",
            "blocks": [
                {"name": "Application (ZCL + App Objects + ZDO)", "sub": "Endpoints | Clusters (On/Off, Level, Color) | Attributes | Commands", "kind": "upper", "iface": "APSDE / APSME"},
                {"name": "APS -- Application Support Sublayer", "sub": "Endpoint addressing | binding table | APS security | fragmentation", "kind": "nwk", "iface": "NLDE / NLME"},
                {"name": "NWK -- Network Layer", "sub": "Mesh routing | 16-bit address assignment | network-key security | route discovery", "kind": "mac", "iface": "MCPS / MLME (SAPs)"},
                {"name": "IEEE 802.15.4 MAC", "sub": "CSMA-CA | ACK / retry | beacons | AES-CCM*", "kind": "phy", "iface": "PD / PLME"},
                {"name": "IEEE 802.15.4 PHY + Radio", "sub": "2.4 GHz O-QPSK DSSS | channels 11-26 (+ sub-GHz)", "kind": "medium"},
            ],
        },
        "layer_details": [
            {
                "title": "ZCL: the interoperability contract",
                "detail": "The Zigbee Cluster Library standardizes application behavior into Clusters. A cluster (e.g. On/Off) defines a fixed set of Attributes (like the current on/off state) and Commands (like Toggle). Because these are standardized, any certified controller can operate any certified device -- this is Zigbee's equivalent of BLE's GATT services.",
                "points": ["Clusters", "Attributes", "Commands", "Vendor interoperability"],
            },
            {
                "title": "APS: endpoints, binding, and fragmentation",
                "detail": "The Application Support Sublayer routes messages to the correct Endpoint on a node, maintains the binding table (which links a source endpoint/cluster to a destination so a switch 'knows' which light it controls), applies APS-level link-key security, and fragments large payloads.",
                "points": ["Endpoints", "Binding table", "APS security", "Fragmentation"],
            },
            {
                "title": "ZDO: device and service management",
                "detail": "The Zigbee Device Object handles discovery (what endpoints/clusters a node exposes), network management (join/leave), and binding management. It also defines the three logical device roles that determine routing capability.",
                "points": ["Service discovery", "Join / leave", "Roles"],
            },
            {
                "title": "NWK: the mesh brain",
                "detail": "The Network layer does mesh route discovery and forwarding, assigns 16-bit network addresses, enforces network-key security, and maintains neighbor and routing tables so packets traverse multiple hops reliably.",
                "points": ["Mesh routing", "Address assignment", "Network key", "Many-to-one optimization", "Route repair"],
            },
            {
                "title": "MAC + PHY: reused 802.15.4 radio",
                "detail": "Zigbee does not change the radio -- it uses the same 802.15.4 MAC (CSMA-CA, ACK/retry, AES-CCM* link security) and PHY (2.4 GHz O-QPSK) covered on the 802.15.4 tab. All of Zigbee's differentiation is above the MAC.",
                "points": ["802.15.4 MAC", "802.15.4 PHY", "CSMA-CA"],
            },
        ],
        "core_concepts": [
            {"term": "Coordinator / Router / End Device", "definition": "Exactly one Coordinator forms the network and holds the Trust Center role. Routers relay mesh traffic and can host children. End Devices are simple (often battery) leaves that talk only to a parent Router."},
            {"term": "Endpoint & Cluster", "definition": "A node exposes up to 240 application Endpoints; each Endpoint implements one or more Clusters. Endpoint+Cluster is how you address a specific function on a device (e.g. endpoint 1, On/Off cluster)."},
            {"term": "Attribute vs. Command", "definition": "An Attribute is a readable/reportable value (state); a Command is an action you invoke. Controllers read/report attributes and send commands -- directly parallel to BLE GATT characteristics and writes."},
            {"term": "Binding", "definition": "A stored link (source endpoint/cluster -> destination) that lets a device send directly to another without a controller in the loop -- e.g. a physical switch bound to a group of lights."},
            {"term": "Trust Center", "definition": "The security authority (usually the Coordinator) that authorizes joins and distributes the network key and optional link keys."},
            {"term": "Network key vs. Link key", "definition": "The network key encrypts NWK-layer traffic shared by the whole mesh; link keys secure APS-layer communication between specific device pairs for stronger isolation."},
            {"term": "Groups & Scenes", "definition": "Groups let one command address many devices at once (all kitchen lights); Scenes store and recall preset attribute combinations (a 'movie' lighting scene)."},
        ],
        "how_it_works": [
            {"title": "1. Network formation", "detail": "The Coordinator scans for a quiet channel, picks a PAN ID, forms the network, and takes on the Trust Center role."},
            {"title": "2. Permit-join window", "detail": "The Coordinator (or a Router) opens a time-limited permit-join window during which new devices are allowed to associate -- limiting exposure of the join process."},
            {"title": "3. Association & authentication", "detail": "A joining device associates at the 802.15.4 MAC, then the Trust Center authenticates it and delivers the network key (protected by a well-known or install-code-derived key)."},
            {"title": "4. Address assignment", "detail": "The device receives a 16-bit network address; it also retains its globally-unique 64-bit IEEE address for stable identity."},
            {"title": "5. Service discovery", "detail": "ZDO queries reveal which Endpoints and Clusters the new device exposes, so a controller knows how to operate it."},
            {"title": "6. Binding (optional)", "detail": "Bindings are created so devices can talk peer-to-peer (a switch bound directly to lights) without routing every action through a hub."},
            {"title": "7. Application messaging", "detail": "Controllers read/report Attributes and send Commands on ZCL Clusters; the APS and NWK layers handle secure delivery and multi-hop routing beneath."},
            {"title": "8. Mesh routing & self-heal", "detail": "NWK discovers and repairs routes as devices move or drop; the 802.15.4 MAC handles per-hop contention, ACKs, and retries."},
        ],
        "developer_view": [
            {"title": "You program against ZCL clusters", "detail": "Application development is mostly implementing or consuming standard ZCL clusters on endpoints. Reuse standard clusters for interoperability instead of inventing proprietary ones wherever possible."},
            {"title": "Model your device with endpoints", "detail": "Map each independent function to an endpoint (e.g. a 3-gang switch = 3 endpoints, each with an On/Off cluster). Controllers then treat each endpoint independently."},
            {"title": "Security & commissioning choices", "detail": "Decide between well-known default join keys (convenient) and install-code-based joining (stronger). Plan Trust Center policy early -- it affects how easily devices onboard and how secure the network is."},
            {"title": "Debugging strategy", "detail": "Use a Zigbee sniffer to watch ZCL frames and NWK routing, and read Coordinator/Trust Center logs for join and key-distribution problems. As with 802.15.4, isolate radio/MAC issues (retries, channel) before blaming application logic."},
        ],
        "zigbee_in_depth": [
            {
                "title": "Full stack above 802.15.4",
                "detail": "Zigbee layers NWK + APS + ZDO + ZCL on the 802.15.4 MAC/PHY. NWK provides mesh routing and network management; APS manages endpoint addressing, binding, and security to application objects; ZDO handles device/service discovery and management; ZCL defines interoperable application behavior (clusters, attributes, commands).",
            },
            {
                "title": "Addressing and endpoints",
                "detail": "A node is referenced by its 16-bit NWK address (assigned at join) and its stable 64-bit IEEE address. Application functions live on Endpoints (1-240), each implementing clusters. Example: endpoint 1 hosts On/Off and Level Control clusters for a dimmable bulb.",
            },
            {
                "title": "Trust Center security model",
                "detail": "The Trust Center controls admission and key distribution. Devices join through permit-join windows, receive the network key, and may establish APS link keys for pairwise security depending on the profile and policy (default keys vs. install codes).",
            },
            {
                "title": "Mesh routing behavior",
                "detail": "Routing runs in the NWK layer among the Coordinator and Routers; End Devices reach the mesh through their parent Router. Routes are discovered and repaired dynamically, while the 802.15.4 MAC still handles per-link contention, ACK, and retries on every hop.",
            },
            {
                "title": "Interworking with Matter",
                "detail": "Zigbee remains its own ecosystem rather than native IPv6, so cloud/service integration is typically done at a hub. Zigbee devices can be exposed to Matter ecosystems through a bridge, letting existing Zigbee deployments participate in Matter controllers.",
            },
            {
                "title": "Capability profile for product teams",
                "detail": "Zigbee's strongest capability set is mature low-power mesh control: standardized device semantics (ZCL), robust group/scene behavior for lighting at scale, and stable multi-vendor modules. It is excellent for cost-sensitive, high-node-count control networks when a hub is acceptable.",
            },
            {
                "title": "Operational levers that move outcomes",
                "detail": "In production, reliability is usually determined by three levers: router density (mains nodes), channel plan quality, and Trust Center policy (install-code onboarding and key updates). App logic is often correct while these levers are the real root cause of field issues.",
            },
        ],
        "use_cases": [
            "Smart lighting (bulbs, dimmers, switches)",
            "Home & building sensors (motion, contact, temperature)",
            "Energy metering and load control",
            "Commercial lighting and building automation",
            "Existing Zigbee fleets bridged into Matter ecosystems",
        ],
        "resources": [
            {"label": "Connectivity Standards Alliance -- Zigbee", "url": "https://csa-iot.org/all-solutions/zigbee/"},
            {"label": "CSA specifications & downloads", "url": "https://csa-iot.org/developer-resource/specifications-download-request/"},
            {"label": "IEEE 802.15.4 (radio layer Zigbee runs on)", "url": "https://standards.ieee.org/ieee/802.15.4/7029/"},
        ],
    },
]

TECH_TUTORIALS_BY_SLUG: dict[str, dict] = {t["slug"]: t for t in TECH_TUTORIALS}
