# Design: RTS Receiver — Track Physical Remote Presses

Status: **Draft / proposal**
Target: Pi-Somfy v3.2+

## 1 Motivation

Pi-Somfy transmits Somfy RTS frames and estimates shutter position from motor
travel times (`durationDown` / `durationUp`). This works well as long as
**every** command goes through Pi-Somfy. The moment someone presses a button on
a physical Somfy remote, the blind moves but Pi-Somfy (and therefore Home
Assistant) never learns about it — the tracked position is wrong until the next
full up/down through the software.

RTS is a one-way broadcast protocol: remotes transmit, motors listen, nobody
acknowledges. But that also means anyone tuned to 433.42 MHz can hear the
remotes. This design adds an **RF receiver** so Pi-Somfy hears physical remote
presses and runs the *same* position estimation it already uses for its own
commands.

```
Physical remote press
  → RF receiver (433.42 MHz OOK, data pin on RXGPIO)
  → edge timestamps (pigpio callbacks on Pi 1–4 / lgpio alerts on Pi 5)
  → RTS decoder (sync detect → manchester → de-XOR → checksum)
  → frame {remote address, button, rolling code}
  → filters: self-echo, repeated frames
  → [PhysicalRemotes] mapping: address → shutterId(s)
  → existing position simulation (rise/lower/stop math)
  → setPosition() → existing callbacks → MQTT → Home Assistant
```

## 2 Goals / Non-goals

**Goals**

1. Detect UP / DOWN / STOP(MY) presses from physical RTS remotes and update the
   tracked position of the mapped shutter(s).
2. Position changes propagate to MQTT / Home Assistant through the existing
   callback path with no HA-side changes.
3. Simple pairing flow to map a physical remote (channel) to one or more
   shutters.
4. Work on Pi 1–5, bare Raspbian install and the Home Assistant add-on alike.
5. Do not disturb the existing TX path in any way.

**Non-goals (v1)**

- Decoding encrypted Somfy io-homecontrol devices (different protocol entirely).
- Tilt/long-press handling (future work, see §10).
- Replacing the TX hardware with the receiver's transceiver (future work).

## 3 Protocol background

The decoder is the exact inverse of `Shutter.sendCommand()` in
`operateShutters.py`, which is the authoritative in-repo reference for the
frame layout. On air, one button press is:

| Element | Timing |
|---|---|
| Wake-up pulse | 9 415 µs high, 89 565 µs low (first frame only) |
| Hardware sync | 2 560 µs high + 2 560 µs low, ×2 (first frame) or ×7 (repeats) |
| Software sync | 4 550 µs high + 640 µs low |
| Payload | 56 bits, manchester: `1` = low→high, `0` = high→low, 640 µs half-symbol |
| Inter-frame gap | 30 415 µs silence |

Payload after de-obfuscation (`plain[i] = recv[i] XOR recv[i-1]`, i = 6…1):

| Byte | Content |
|---|---|
| 0 | "Encryption key", 0xA0–0xAF |
| 1 | Button in high nibble (0x1 My/Stop, 0x2 Up, 0x4 Down, 0x8 Prog), 4-bit checksum in low nibble |
| 2–3 | Rolling code, big endian — increments on every press |
| 4–6 | Remote address (24 bit) — **unique per remote channel**; a 5-channel Telis appears as 5 addresses |

Checksum check: XOR of all 14 nibbles of the de-obfuscated frame must equal 0.

Every press is transmitted as one frame plus several repeats **with the same
rolling code**, so `(address, rollingCode)` uniquely identifies one press and
is a perfect de-duplication key. A held button keeps repeating frames
(same code) — the repeat count distinguishes short from long press.

## 4 Hardware

### 4.1 Why the frequency matters (again)

Somfy RTS uses 433.**42** MHz; generic modules ship tuned to 433.**92** MHz.
For the transmitter the fix was swapping the 3-pin SAW resonator. **The same
trick does not exist for receivers:**

- The cheap kit receiver (XY-MK-5V style, super-regenerative) sets its
  frequency with an LC tank — there is no resonator to swap. It will hear
  Somfy remotes only at very short range and is extremely noisy. Not viable.
- Superheterodyne receivers (RXB6/RXB8) use a local-oscillator crystal at
  ~1/64 of the receive frequency; a 433.42 MHz cut (~6.73 MHz) is not a
  commodity part. Running one unmodified (centered 500 kHz off) loses most of
  its sensitivity.

### 4.2 CC1101 transceiver module (~$3)

The CC1101 is tuned **in software**: we write its frequency registers once at
startup and set it to OOK receive with *asynchronous serial output*, after
which its `GDO0`/`GDO2` pin behaves exactly like the data pin of a dumb
receiver — demodulated 0/1 that we timestamp with GPIO edge callbacks, matching
the project's existing GPIO style. No soldering, no rare parts, exact
433.42 MHz, 3.3 V native (Pi-safe).

Wiring (SPI is only used for one-time configuration; see §5.1):

| CC1101 pin | Signal | Default GPIO | Physical pin (Pi 4) | Note |
|---|---|---|---|---|
| VCC | 3.3 V supply | — | 17 (or 1) | **never 5 V** |
| GND | ground | — | 39 | keeps the whole harness in one corner (34 also works) |
| SCK | SPI clock | GPIO 21 (`RXSpiSCK`) | 40 | bit-banged, any free GPIO |
| MOSI (SI) | SPI data → radio | GPIO 20 (`RXSpiMOSI`) | 38 | |
| MISO (SO) | SPI data → Pi | GPIO 19 (`RXSpiMISO`) | 35 | required — read-back verification (§5.1) |
| CSN | chip select | GPIO 16 (`RXSpiCSN`) | 36 | |
| GDO0 | demodulated data out | GPIO 26 (`RXGPIO`) | 37 | the receiver's actual data pin |
| GDO2 | — | not connected | — | |
| ANT | antenna | — | — | 17 cm solid-core wire, **required** — see §4.4 |

The defaults deliberately cluster every signal in the bottom corner of the
40-pin header (physical pins 35–40, plus 3.3 V from pin 17), far from the
existing transmitter on GPIO 4 (physical pin 7). All pins are configurable
(§5.3); module silkscreens vary between CC1101 board revisions, so always
match by label, not by position (MOSI may be printed `SI`, MISO `SO`).

```
                     ┌──────┬──────┐
         3.3V (VCC)  │  17  │  18  │
                     │  ..  │  ..  │
                     │  33  │  34  │
      GPIO19 (MISO)  │  35  │  36  │  GPIO16 (CSN)
      GPIO26 (GDO0)  │  37  │  38  │  GPIO20 (MOSI)
          GND        │  39  │  40  │  GPIO21 (SCK)
                     └──────┴──────┘
```

### 4.3 Antenna

Today's antenna-less transmitter reaches the whole house because the *blind
motors* have good factory antennas — the weak TX signal is compensated by good
ears on the receiving end. For the new receive direction the roles flip: the
Pi must hear a handheld remote pressed 15–20 m and several walls away, and a
receiver without an antenna has terrible ears. The 17 cm quarter-wave wire
(same as the README describes for TX) is mandatory on the receiver; many
CC1101 modules ship with a coil antenna or SMA connector.

## 5 Software design

### 5.1 New module: `receiver.py`

A `Receiver(threading.Thread)` class following the existing service pattern
(`MQTT`, `Alexa`): constructed with `kwargs = {log, shutter, config}`, a
`shutdown_flag`, started from `operateShutters.ProcessCommand`. Enabled when
`RXGPIO` is present in `[General]` — no new CLI flag.

Internal components:

- **`CC1101` init helper** — bit-banged SPI using the project's existing GPIO
  libraries (pigpio's built-in `bb_spi_*` functions on Pi 1–4, plain `lgpio`
  writes on Pi 5) writing the ~50 configuration registers: 433.42 MHz carrier,
  OOK/ASK, no packet engine, async serial mode routing demodulated data to
  GDO0. Runs once at startup; speed is irrelevant, so software SPI is fine and
  avoids requiring the hardware-SPI overlay (important for the HA add-on, §7).
  The MISO line is not optional even for this one-time setup: init must prove
  the radio is really there and configured — read `PARTNUM`/`VERSION`, check
  the status byte returned with every transfer, read back each written
  register, and abort startup loudly on any mismatch (a mis-wired SPI
  otherwise degrades silently into a deaf receiver). Register values: see
  Appendix A.
- **Edge source** — mirrors the TX path's library split (selected by the
  existing `IS_PI5` flag), so the receiver runs on the exact stack the project
  already ships:
  - *Pi 1–4:* `pigpio` edge callbacks (`pi.callback(RXGPIO, EITHER_EDGE)`) on
    the **same pigpiod daemon the TX path already runs** — no extra footprint.
    pigpiod timestamps every edge daemon-side in µs ticks, so Python
    scheduling jitter does not affect decoding accuracy.
    `pi.set_glitch_filter(RXGPIO, 150)` drops sub-150 µs noise glitches inside
    the daemon before they ever reach Python (the shortest real pulse is
    640 µs).
  - *Pi 5:* `lgpio.gpio_claim_alert` + callback with kernel timestamps (ns),
    `lgpio.gpio_set_debounce_micros(…, 150)` as the glitch filter — the same
    library the TX path's Pi 5 branch uses.

  A thin `EdgeSource` wrapper normalises both backends to a stream of
  `(level, timestamp_µs)` events, keeping the decoder itself library-free and
  unit-testable.
- **Decoder** — a small state machine fed `(level, timestamp)` events:
  1. Hunt for ≥2 hardware-sync pairs (2 560 µs ± 30 %).
  2. Expect software sync (4 550 µs high ± 30 %, then 640 µs low).
  3. Collect manchester transitions: durations classify as one half-symbol
     (640 µs ± 35 %) or two (1 280 µs ± 35 %). The machine fails fast: the
     first out-of-tolerance duration aborts straight back to sync hunt
     (re-examining the offending edge as a candidate new sync), and a
     whole-frame watchdog (~90 ms, longer than any legal frame) catches
     stalls — noise must never leave the decoder waiting for its 56th bit.
     Emit 56 bits.
  4. De-obfuscate, verify checksum, extract `{address, button, rollingCode}`.

  The decoder is a pure function of an edge-timestamp stream — fully unit
  testable off-Pi with synthetic or recorded streams (§9).
- **Press filter**:
  - *Self-echo:* frames whose address matches a key in `config.Shutters` are
    the Pi's own transmissions (their state is already updated by the TX path)
    → ignored. Additionally the Receiver pauses decoding while
    `Shutter.sendCommand` holds its lock, so TX energy doesn't feed garbage
    into the state machine. The receiver sits centimetres from the
    transmitter and is fully RF-saturated during TX, so when the
    transmitting flag clears the Receiver must also discard any queued edge
    events and reset the decoder to sync hunt — trailing saturation
    artifacts must not corrupt the first real frame heard afterwards.
  - *De-dup:* remember `(address, rollingCode)` with a ~3 s TTL; the frame
    repeats of a single press collapse into one press event. Repeat count is
    retained on the event for future long-press features.
  - *Unknown addresses:* counted and kept in a small ring buffer for the
    learning UI (§5.5); logged at INFO (`Unknown remote 0x14A2C7 pressed UP`).

### 5.2 `Shutter` refactor: share the position simulation

Today `rise`/`lower`/`stop` interleave "send RF" with "update the position
model". Extract the model updates into internal methods so the RX path can
invoke them without transmitting:

| New method | Extracted from | Behaviour |
|---|---|---|
| `_simulateUp(shutterId)` | `rise()` | `registerCommand('up')` + `waitAndSetFinalPosition(…, 100)` thread |
| `_simulateDown(shutterId)` | `lower()` | `registerCommand('down')` + `waitAndSetFinalPosition(…, 0)` thread |
| `_simulateStop(shutterId)` | `stop()` | elapsed-time position math incl. the intermediate-("my"-)position fallback |

`_simulateStop` inherits the full MY-button ping-pong the motors implement:
MY while stationary travels toward the stored MY position (up if below, down if
above), MY mid-travel stops and estimates the reached position, and a further
MY resumes travel toward MY. This falls out of the existing
`lastCommandDirection` / fallback logic in `stop()` — no new code, but two
consequences for physical-remote tracking:

- **`[ShutterIntermediatePositions]` becomes effectively mandatory** for
  tracked shutters. When it is unset the model assumes a stationary MY press
  "stays put", while the real motor travels to its stored favourite — with
  physical remotes (where MY is the most-used button) this would be the main
  source of position drift. The pairing UI (§5.5) should prompt for it.
- The M1 refactor should switch `stop()`'s elapsed-time math from
  `int(round(...))` seconds with a `> 0` guard to float seconds: a MY press
  within ~0.5 s of a movement command currently misclassifies as a stationary
  go-to-MY press, and quick double-presses are far more likely on a physical
  remote than via the network path.

`rise()` becomes `sendCommand(…, buttonUp); _simulateUp(…)` — a pure refactor,
no behaviour change for the TX path. The Receiver calls
`shutter.recordExternalCommand(shutterId, button)`, which dispatches to the
same `_simulate*` methods. Interruption handling (a press arriving while a
previous movement simulation is still counting down) already works via the
`lastCommandTime` check in `waitAndSetFinalPosition`.

Because `_simulate*` ends in `setPosition()`, the existing callback chain
(`mqtt.set_state` → position + open/closed/stopped topics) fires for physical
presses with **zero MQTT/HA changes**.

### 5.3 Configuration

```ini
[General]
# (Optional) GPIO where the RF receiver's data pin is connected.
# Presence of this key enables the receiver.
RXGPIO = 26
# CC1101 bit-banged SPI pins
RXSpiSCK = 21
RXSpiMOSI = 20
RXSpiMISO = 19
RXSpiCSN = 16

# Maps a physical remote (channel) address to the shutter(s) it controls.
# One press updates all listed shutters (group channels list several ids).
[PhysicalRemotes]
0x14A2C7 = 0x279620
0x14A2C8 = 0x279620, 0x279621
```

`MyConfig.LoadConfig` gains parsing for these keys, mirroring the existing
`[Shutters]` handling. Addresses are normalised to the same `0x%06X` string
form used as shutter ids so self-echo comparison and mapping lookups are plain
dict operations.

### 5.4 Movement state (opening/closing) for HA

Today `opening`/`closing` are only published from the MQTT command handler
(`mqtt.receiveMessageFromMQTT`), so physical presses would jump straight from
one resting state to another. Fix the asymmetry at the source: add a second
callback list to `Shutter` (`registerMovementCallBack`), invoked from
`_simulateUp/_simulateDown/_simulateStop` with `opening` / `closing` /
`stopped`. MQTT registers for it and drops its own inline `_publish_state`
calls. Both the software and physical paths then report movement identically.

### 5.5 Learning mode (pairing UX)

Users don't know their remotes' addresses, so pairing is "press a button, then
claim what was heard":

- **v1 (config-file):** unknown presses are logged; the user copies the
  address into `[PhysicalRemotes]`.
- **v2 (web UI):** a "Remotes" page backed by two endpoints —
  `GET /cmd/getUnheardRemotes` returns the ring buffer of recently heard
  unknown addresses `{address, lastButton, count, secondsAgo}`;
  `POST /cmd/assignRemote` writes the mapping to `[PhysicalRemotes]`. The flow
  mirrors the existing shutter-programming UI: open page → press the physical
  remote → the address appears → tick the shutter(s) it controls → save.

### 5.6 Position persistence across restarts

Today positions live only in RAM (`Shutter.shutterStateList`); nothing writes
them to disk. After a reboot every shutter re-initialises to 0 and MQTT's
`on_connect` publishes 0/"closed" for all shutters — overwriting even the
retained topics HA still had. The model only re-anchors on the next full
up/down. This predates the receiver, but once physical presses are tracked the
position becomes trustworthy enough that losing it on every reboot is the
weakest link. So M1 adds persistence:

- New config section `[ShutterPositions]`, written through the existing
  atomic `MyConfig.WriteValue` — the same mechanism that already rewrites the
  config on **every** command for rolling codes, so SD-card write load stays
  in the same order of magnitude.
- Written only when a position *settles* (end of `waitAndSetFinalPosition`,
  `stop()`, and the partial-move completions) — not on transient
  opening/closing states.
- Loaded in `MyConfig.LoadConfig` and used to seed `shutterStateList` at
  startup, so MQTT's reconnect publish reports the last known position
  instead of 0.
- In the HA add-on the config already lives in `/data/operateShutters.conf`
  (persistent volume), so restored positions survive add-on restarts, HA
  updates and host reboots with no packaging change.

Residual, accepted gap: movements made **while the Pi is off** (physical
remote during downtime or a power outage) are invisible to any design — the
restored position is a best guess until the next full up/down re-anchors the
model at 0/100. The receiver shrinks this window from "any physical press,
ever" to "physical presses during downtime only".

## 6 What stays untouched

- The TX path (`sendCommand`, waveforms, pigpio/lgpio TX split, rolling-code
  persistence).
- The MQTT topic scheme, HA discovery payloads and the HA custom component.
- Scheduler, Alexa, web UI (until the v2 learning page).

## 7 Proof of concept — standalone, before touching this codebase

The POC validates hardware, frequency, range and the decoder **with zero
coupling to Pi-Somfy's code**, packaged the same way the project already
ships: as a Home Assistant add-on. It deliberately uses **the same library
stack and build recipe as the production add-on** — pigpio on Pi 1–4 / lgpio
on Pi 5, built from source exactly as in
`Home Assistant/addon/pi_somfy/Dockerfile`, with the same access grants
(`gpio: true`, `SYS_RAWIO`, `/dev/mem`, `/dev/gpiochip*`) — so what the POC
proves is the configuration the integrated feature will actually run, not a
lookalike:

```
addons/rts_sniffer_poc/
├── config.yaml       # same grants as the pi_somfy add-on, no ingress
├── Dockerfile        # same base + pigpio/lgpio source builds as pi_somfy
├── run.sh            # starts pigpiod on Pi 1–4, exactly like pi_somfy
└── sniffer.py        # CC1101 init (bb_spi) + edge decoder + test TX + logging
```

- `sniffer.py` is self-contained (~350 lines): configure the CC1101 via
  pigpio `bb_spi_*`, register edge callbacks on the data pin, decode, and log
  every frame (`0x14A2C7  UP  code=1337  repeats=4`) to the add-on log.
  Optionally publish to MQTT topic `somfy_sniffer/event` for visibility in HA.
- **Built-in loopback transmitter:** the sniffer embeds the frame/waveform
  generation from `sendCommand` (copied, not imported) and can transmit a
  test frame from a dummy address on the TX GPIO every N seconds — TX and RX
  through the **one shared pigpiod**, which is precisely how the integrated
  feature will run on Pi 1–4. No physical remote needed for the first test.
- Installed as a **local add-on** (copy the folder to `/addons` via the
  Samba/SSH add-on, then Add-on Store → ⋮ → Check for updates).
- **Stop the Pi-Somfy add-on while the POC runs** (Pi 1–4): each container
  would start its own pigpiod, and two daemons contending for DMA/`/dev/mem`
  is not supported. The built-in test transmitter keeps the loopback test
  available regardless. The restriction disappears after integration — one
  process, one daemon, both directions.
- Bit-banged SPI means **no HAOS host changes** — no `dtparam=spi=on` edit of
  `config.txt`, no reboot.

**POC success criteria**

1. Loopback: ≥95 % of the built-in test transmissions decoded with correct
   address/button/rolling code.
2. Range: every physical remote press from the farthest room is decoded
   (each press repeats its frame several times, so catching any one repeat
   counts).
3. Noise: zero checksum-valid false positives over 24 h of idle listening.
4. Load: sniffer CPU < 5 % on a Pi 4 in a normal RF environment.

Only after the POC passes do we start the integration milestones — and
`sniffer.py`'s decoder moves into `receiver.py` nearly verbatim.

## 8 Milestones

| # | Deliverable | Depends on |
|---|---|---|
| M0 | POC sniffer add-on (§7) + decoder unit tests | CC1101 hardware |
| M1 | `receiver.py`, `Shutter` `_simulate*` refactor, `[PhysicalRemotes]`, self-echo + de-dup filters, config-file pairing, position persistence (§5.6) | M0 |
| M2 | Movement-state callback (§5.4), web UI learning page (§5.5), README hardware chapter, add-on options (`rx_gpio_pin`, SPI pins) | M1 |
| M3 | Nice-to-haves: HA event entities per physical remote (any RTS remote as automation trigger), long-press/tilt, Somfy sun/wind sensors (Soliris/Eolis speak RTS too) | M2 |

## 9 Testing

- **Decoder unit tests** (run anywhere, incl. CI/Windows like the existing
  platform stubs): feed synthetic edge streams generated from the *same* pulse
  tables `sendCommand` uses, plus recorded real-remote captures; assert
  decoded frames, checksum rejection, glitch tolerance, truncated-frame reset.
- **TX→RX loopback** on-device: Pi-Somfy transmits (known frame), receiver
  decodes; run in a soak loop.
- **Simulation-equivalence tests:** for each button sequence, assert
  `recordExternalCommand` leaves the position model in the same state as the
  equivalent `rise`/`lower`/`stop` call (minus the RF side effect).
- **Manual matrix:** short press up/down/stop, stop-while-moving,
  stop-while-stationary (my-position fallback), the MY ping-pong sequence
  (stationary MY → travels toward stored MY; second MY mid-travel → stops;
  third MY → continues to MY — verify in both directions), group channel,
  presses during a software-initiated movement, presses on unmapped remotes.

## 10 Risks & mitigations

| Risk | Mitigation |
|---|---|
| Frequency offset kills range | CC1101 tuned to exactly 433.42 MHz; POC range test before integration |
| RF noise floods the edge callback | 150 µs kernel debounce, cheap state-machine reset, checksum, address filter; POC criterion #4 |
| Receiver hears the Pi's own TX | Address self-echo filter + decode pause while `sendCommand` holds its lock |
| STOP while stationary moves to stored "my" position | Already modelled by the existing intermediate-position fallback in `stop()` — physical presses inherit it, incl. the MY ping-pong (see §5.2). Requires `[ShutterIntermediatePositions]` to match the motor's stored MY |
| Physical 5 s MY long-press reprograms the motor's stored MY, silently invalidating `[ShutterIntermediatePositions]` | Document in README; M3 detects it (high MY repeat count while the model says stationary), logs a warning and raises an HA notification that the configured intermediate position may have diverged |
| POC add-on and Pi-Somfy add-on each start a pigpiod (DMA/`/dev/mem` contention) | Never run both at once; the POC's built-in test transmitter covers loopback without Pi-Somfy. Not an issue after integration: one process, one daemon for TX+RX |
| `operateShutters.py`'s `startGPIO()` starts pigpiod with `-l -m` — `-m` disables alerts, the mechanism `pi.callback()` uses for edge notifications. TX never needed alerts so this went unnoticed; M1's receiver adding an edge callback onto this same daemon would silently never fire (confirmed during the M0 POC: edges stayed at 0 across every CC1101 register configuration tried until `-m` was removed, at which point loopback immediately hit 100 %) | Drop `-m` from `operateShutters.py`'s pigpiod startup when M1 wires the receiver into the shared daemon |
| Edge-timestamp jitter under load | Timestamps come from pigpiod (µs ticks, Pi 1–4) or the kernel (lgpio, Pi 5), not from Python; symbol tolerance ±35 % (±224 µs) vs typical jitter of tens of µs; loopback soak validates |
| Positions lost on reboot (all shutters report "closed" to HA) | Persist settled positions to `[ShutterPositions]` and restore at startup (§5.6); blinds moved while the Pi is off remain a best guess until the next full up/down |

## 11 Future work

- Use the CC1101 for TX as well (it is a transceiver): retires the
  soldered-resonator transmitter and the pigpio waveform path entirely.
- Long-press detection (repeat count) → venetian tilt steps.
- Rolling-code plausibility tracking per physical remote to flag stuck/replayed
  frames.
- Decode RTS sensors (Soliris sun/wind) as HA sensor entities.

## Appendix A — CC1101 configuration notes (finalised in M0)

The exact register map is settled during M0, anchored in this order: the
CC1101 datasheet formulas, TI SmartRF Studio output for 433.42 MHz OOK, and
proven open-source Somfy implementations (ESPSomfy-RTS is the reference).
Third-party register dumps — including AI-suggested ones — must be re-derived
against the datasheet before use. Cautionary example from review: a suggested
`MDMCFG4 = 0xC7` annotated as "~325 kHz bandwidth" actually computes to
≈102 kHz (`BW = 26 MHz / (8 × (4+CHANBW_M) × 2^CHANBW_E)` with E=3, M=0) —
narrow, i.e. the opposite of its stated intent of catching drifted remotes.

Requirements the final map must satisfy (26 MHz crystal assumed):

| Concern | Register(s) | Requirement |
|---|---|---|
| Carrier | `FREQ2/1/0` | 433.42 MHz exactly: `FREQ = round(433.42 MHz × 2^16 / 26 MHz)` |
| Modulation | `MDMCFG2` | ASK/OOK; sync-word detection disabled (raw stream) |
| Serial output | `PKTCTRL0`, `IOCFG0` | asynchronous serial mode; GDO0 routes demodulated data (0x0D) |
| RX bandwidth | `MDMCFG4` (high nibble) | wide enough for aged, drifting handheld remotes — target ~200–325 kHz; narrow only if the noise floor forces it |
| Data-rate filter | `MDMCFG4` (low nibble), `MDMCFG3` | matched to the 640 µs half-symbol stream (~1.6 kBaud chip rate) |
| OOK demod behaviour | `AGCCTRL2..0` | AGC/decision thresholds from a proven Somfy OOK profile |
| Comms sanity | `PARTNUM`, `VERSION` | read at startup; abort if SPI read-back fails (§5.1) |

The empirical tuning loop is the M0 loopback transmitter plus a real remote
at increasing distances: adjust bandwidth and AGC until success criteria
§7 (1)–(4) pass. Register values judged "working" without that loop are not
accepted.
