# Design: RTS Receiver — Track Physical Remote Presses

Status: **M0 core pipeline validated on real hardware** — loopback 100 %, a
real remote decodes correctly (§7, §8); the farthest-room range test and the
24 h noise/CPU soak are still open but non-blocking. M1+ still draft/proposal
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
- Tilt/long-press handling (future work, see §11).
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
    That daemon must be started **without** `-m` (disable alerts) — `-m` is
    what `operateShutters.py`'s `startGPIO()` passes today, harmlessly for a
    TX-only daemon, but it silently kills `pi.callback()` delivery entirely
    (confirmed the hard way during the M0 POC; see §10). pigpiod timestamps
    every edge daemon-side in µs ticks, so Python scheduling jitter does not
    affect decoding accuracy.
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
- **v2 (web UI), concretely, in the existing settings page** (`html/index.html`
  — no separate page): the shutter/motor setup UI is already an accordion of
  sections (`#collapseOne` location, `#collapseTwo` "Add/Remove Shutter",
  a schedule section) inside one `#accordion`. Physical-remote pairing gets
  its own sibling section, **"Physical Remotes"**, added the same way:
  - A table of currently-paired remotes (address → shutter name(s)), with an
    unassign action — mirrors the existing `#shutters` table
    (`webserver.py`'s `addShutter`/`editShutter`/`deleteShutter` pattern).
  - Below it, a "recently heard" list from `GET /cmd/getUnheardRemotes`
    (`{address, lastButton, count, secondsAgo}`), each row with an "Assign"
    button opening a small modal. That modal reuses the **existing
    multi-select shutter picker** already in `index.html` (`<select
    id="shutters" class="shuttersList" multiple="multiple">`, currently used
    for scheduling) to tick which shutter(s) the address controls — group
    channels naturally become a multi-shutter tick, no new widget needed.
    Saving calls `POST /cmd/assignRemote`, which writes to `[PhysicalRemotes]`
    the same way `addShutter` writes to `[Shutters]`.
  - Nice-to-have, not required for the MVP (still **not implemented** —
    deferred past M2, see §11): each shutter row's existing "Configure"
    wizard (wrench icon → the step-by-step modal that already has Initial
    Setup / Adjust Limits / My Position accordion steps) gets one more step,
    "Pair a Physical Remote to This Shutter", that deep-links to the
    Physical Remotes section with this shutter pre-ticked — convenient during
    initial motor setup, when the user is already in that wizard.
  - The pairing UI should also prompt for `[ShutterIntermediatePositions]`
    when it's unset for a shutter being paired (§5.2's mandatory-in-practice
    note) — natural to fold into the same "Assign" modal or the Configure
    wizard's existing "My Position" step. Also **deferred past M2**.
  - **Implemented in M2**: the paired-remotes table with unassign, the
    "Recently Heard" list, and the Assign modal (reusing the existing
    multi-select) exactly as designed above.

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

## 7 Proof of concept — standalone, before touching this codebase (✅ M0 complete)

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
├── config.yaml         # same grants as the pi_somfy add-on, no ingress
├── Dockerfile          # same base + pigpio/lgpio source builds as pi_somfy
├── patch_pigpiod.py    # build-time patch, see below
├── run.sh              # starts pigpiod on Pi 1–4, exactly like pi_somfy
├── sniffer.py          # CC1101 init (bb_spi) + edge decoder + test TX + logging
└── test_sniffer.py     # 19 decoder unit tests, run anywhere (§9)
```

- `sniffer.py` configures the CC1101 via pigpio `bb_spi_*`, registers edge
  callbacks on the data pin, decodes, and logs every frame
  (`0x14A2C7  UP  code=1337  repeats=4`) to the add-on log. Optionally
  publishes to MQTT topic `somfy_sniffer/event` for visibility in HA.
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
- `patch_pigpiod.py` patches one thing at build time: pigpiod's `main()`
  unconditionally tries to create an error-reporting FIFO under `/dev`
  (`unlink`/`mkfifo`/`chmod` on `/dev/pigerr`), with no flag to disable it.
  In this container `/dev` is read-only beyond the specific devices granted,
  so that call aborts startup; the patch replaces it with a direct
  `errFifo = stderr`, since the sniffer only ever talks to pigpiod over its
  TCP socket interface and never needed the FIFO anyway.

**POC success criteria**

1. ✅ Loopback: ≥95 % of the built-in test transmissions decoded with correct
   address/button/rolling code — **measured 100 %** on a Pi 4 + CC1101
   (2026-07-24).
2. 🟡 Range: every physical remote press from the farthest room is decoded
   (each press repeats its frame several times, so catching any one repeat
   counts) — a real remote was heard and decoded correctly (address, button,
   incrementing rolling code, repeat-count tracking all confirmed working),
   but not yet specifically tested at the farthest-room distance this
   criterion calls for.
3. ⬜ Noise: zero checksum-valid false positives over 24 h of idle listening —
   not yet run; worth doing before M1 sign-off.
4. ⬜ Load: sniffer CPU < 5 % on a Pi 4 in a normal RF environment — not yet
   measured.

The path to these results was not the CC1101 register tuning it initially
looked like (see the full account in §10 and Appendix A) — it was a single
`pigpiod` startup flag (`-m`, disables alerts) inherited unquestioned from
`operateShutters.py`'s TX-only startup, which silently broke `pi.callback()`
delivery regardless of any RF-side configuration. That is now understood and
fixed in the POC's `run.sh`, and is the single most important thing to carry
into M1 (§10, §12).

Criteria 1 and (partially) 2 are met — the core pipeline is proven correct on
real hardware. Criteria 3 and 4, and the specific farthest-room range test,
remain open; worth running before M1 sign-off, but they don't block starting
the integration work: `sniffer.py`'s decoder and CC1101 register map move
into `receiver.py` (§5.1) as M1 — see §12 for how to do that without
fighting the upstream fork relationship.

## 8 Milestones

| # | Deliverable | Depends on |
|---|---|---|
| M0 | ✅ **Done.** POC sniffer add-on (§7) + decoder unit tests. Loopback 100 %, real remote decoded. Noise/CPU soak (POC criteria 3–4) still worth running before M1 sign-off | CC1101 hardware |
| M1 | ✅ **Done.** `receiver.py`, `Shutter` `_simulate*` refactor, `[PhysicalRemotes]`, self-echo + de-dup filters, config-file pairing, position persistence (§5.6) — validated end-to-end on real hardware (CC1101 configures, real remote presses decode and dispatch correctly) | M0 |
| M2 | ✅ **Done.** Movement-state callback (§5.4), web UI learning section in the existing settings page (§5.5), README hardware chapter (§2.1), add-on options (`rx_gpio_pin`, SPI pins) | M1 |
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

- Configure-wizard deep-link into the Physical Remotes section, and
  prompting for `[ShutterIntermediatePositions]` during pairing (§5.5
  nice-to-haves, deferred past M2).
- Use the CC1101 for TX as well (it is a transceiver): retires the
  soldered-resonator transmitter and the pigpio waveform path entirely.
- Long-press detection (repeat count) → venetian tilt steps.
- Rolling-code plausibility tracking per physical remote to flag stuck/replayed
  frames.
- Decode RTS sensors (Soliris sun/wind) as HA sensor entities.

## 12 Fork-friendly implementation strategy

This repo is a fork of `Nickduino/Pi-Somfy` — `origin` in this checkout points
at the fork, not upstream, and `README.md` already documents cherry-picking
specific upstream fixes by PR number (#164, #156, #159) into files this fork
has since diverged from. That practice — take specific upstream fixes,
reapply by hand where they no longer apply cleanly — is the existing norm,
not a full periodic merge. M1 should be built to keep that norm cheap, since
`operateShutters.py`, `config.py`, `webserver.py` and `html/*` are all files
upstream continues to patch.

**Practical step:** add upstream as a second remote so future syncing is a
`git fetch` away instead of a manual re-diff:
```
git remote add upstream https://github.com/Nickduino/Pi-Somfy.git
```

**Per-file strategy for M1:**

| File | Upstream touches it? | Approach |
|---|---|---|
| `receiver.py` (new) | No | Whole new file — zero conflict surface by construction |
| `operateShutters.py` | Yes, actively | `rise()`/`lower()`/`stop()` become one-line bodies calling `sendCommand(...)` + the new `_simulate*` method (§5.2) — the *new* logic lives entirely in the new `_simulate*` methods (additions), not in edits to the old bodies. A future upstream fix to `rise()`/`lower()`/`stop()` then conflicts on one line, not a rewritten block. Same principle for `ProcessCommand` (one new line starting the `Receiver` thread) and `startGPIO()` (drop `-m`, a one-token diff, not a rewrite) |
| `config.py` | Yes, actively | New sections (`[PhysicalRemotes]`, `[ShutterPositions]`, `RXGPIO`/SPI keys) parsed by new helper methods (e.g. `_loadPhysicalRemotes()`), called from one new line appended at the end of `LoadConfig` — not interleaved with existing section-parsing logic |
| `webserver.py` | Yes, occasionally | `getUnheardRemotes`/`assignRemote` (§5.5) as entirely new methods + new route registrations, following the existing `addShutter`/`editShutter` pattern exactly rather than inventing a new one |
| `mqtt.py` | Yes, occasionally | `registerMovementCallBack` (§5.4) is a new registration call; the existing inline `_publish_state` calls it replaces should be deleted in the same commit, not left dead, but kept to that one mechanical swap |
| `html/index.html`, `operateShutters.js` | Yes, actively (UI tweaks land often) | New "Physical Remotes" accordion section (§5.5) appended after the existing sections, not spliced between them — new `<script>` functions for it appended near the related existing ones (`addShutter`/`editShutter`), not reshuffling existing functions |
| `documentation/Receiver Design.md`, `addons/rts_sniffer_poc/` | No | Fork-only; upstream has no receiver, so no conflict risk ever |

**General rule for the whole milestone:** prefer additions (new methods, new
files, new config sections, one new call-site line) over edits to existing
function bodies. Where an existing function's *behaviour* genuinely must
change (e.g. `stop()`'s elapsed-time math moving from `int(round(...))` to
float seconds, §5.2), make that specific change as small and isolated as
possible and say why in a comment — a future upstream patch to the same
function will conflict on that line either way, but a small, well-explained
diff is a five-second manual reapply instead of a re-derivation.

Land M1 as a sequence of small, reviewable commits along the boundaries in
the table above, rather than one large patch — it keeps "what's fork-specific
vs. a candidate to also send upstream" legible long after this design doc is
forgotten.

## Appendix A — CC1101 configuration notes (finalised and validated in M0)

The register map below is validated end-to-end on real hardware (Pi 4 +
CC1101, loopback 100 %, real remote decoded — §7) as `CC1101_RX_CONFIG` in
`addons/rts_sniffer_poc/sniffer.py`. `receiver.py` should port it verbatim
at M1 rather than re-deriving it.

Cautionary tale that motivated getting to an actually-validated table rather
than trusting datasheet-formula derivations alone: an early draft used
`MDMCFG4 = 0xC7` annotated as "~325 kHz bandwidth" — it actually computes to
≈102 kHz (`BW = 26 MHz / (8 × (4+CHANBW_M) × 2^CHANBW_E)` with E=3, M=0),
narrow rather than wide. The *value* 0xC7 turned out to be correct for the
final config below, but the annotation was backwards — a reminder that
third-party register dumps and formula-derived guesses both need checking
against real hardware, not just each other.

| Addr | Reg | Value | Note |
|---|---|---|---|
| 0x00 | IOCFG2 | 0x2E | GDO2 high impedance (unused, not wired) |
| 0x02 | IOCFG0 | 0x0D | GDO0 = asynchronous serial RX data |
| 0x06 | PKTLEN | 0x00 | unused in infinite-length async mode |
| 0x07 | PKTCTRL1 | 0x04 | no address check, no status append |
| 0x08 | PKTCTRL0 | 0x32 | asynchronous serial mode, no CRC, infinite length |
| 0x09 | ADDR | 0x00 | unused (no address check) |
| 0x0A | CHANNR | 0x00 | channel 0, no channel hopping |
| 0x0B | FSCTRL1 | 0x06 | IF = 26MHz·6/2¹⁰ = 152 kHz |
| 0x0D–0x0F | FREQ2/1/0 | 0x10, 0xAB, 0x85 | `FREQ = round(433.42MHz × 2¹⁶ / 26MHz)` → carrier 433.419995 MHz |
| 0x10 | MDMCFG4 | 0xC7 | RX BW 26MHz/(8·(4+0)·2³) = 101.6 kHz (CHANBW_E=3,M=0); DRATE_E=7 |
| 0x11 | MDMCFG3 | 0x93 | DRATE_M, paired with DRATE_E=7 above |
| 0x12 | MDMCFG2 | 0x3C | DC-blocking filter on; ASK/OOK; MANCHESTER_EN=1, SYNC_MODE=100 (see below) |
| 0x13 | MDMCFG1 | 0x02 | no FEC, minimal preamble (irrelevant in async mode) |
| 0x14 | MDMCFG0 | 0xF8 | channel spacing (irrelevant, no channel hopping) |
| 0x15 | DEVIATN | 0x47 | frequency deviation (FSK-only, irrelevant for OOK) |
| 0x18 | MCSM0 | 0x18 | auto-calibrate synthesizer on IDLE→RX |
| 0x19 | FOCCFG | 0x16 | frequency offset compensation |
| 0x1A | BSCFG | 0x1C | bit synchronization config |
| 0x1B | AGCCTRL2 | 0x03 | **full** LNA/DVGA gain, 33 dB magnitude target |
| 0x1C | AGCCTRL1 | 0x00 | no relative carrier-sense thresholds |
| 0x1D | AGCCTRL0 | 0x91 | OOK decision boundary 8 dB above averaged noise floor |
| 0x21 | FREND1 | 0x56 | RX front end |
| 0x22 | FREND0 | 0x11 | OOK PA table index 1 (TX side, unused here) |
| 0x23–0x26 | FSCAL3/2/1/0 | 0xE9, 0x2A, 0x00, 0x1F | frequency synthesizer calibration |
| 0x29 | FSTEST | 0x59 | — |
| 0x2C–0x2E | TEST2/1/0 | 0x81, 0x35, 0x09 | datasheet threshold values for the ≥325 kHz RX-BW regime; still correct despite our narrower filter — not a linear function of bandwidth |

**Key departures from the initial (untested) draft, discovered only by
testing on real hardware:**

- **Full gain, not capped.** `AGCCTRL2` with the top-3 DVGA gain stages
  capped (0xC7, seen in some reference implementations) reliably killed all
  receive activity in every combination tried on this specific board —
  independent of bandwidth, AGCCTRL0, or the DC-blocking filter. Full gain
  (0x03) is required just to get any signal at all.
- **`DRATE_E=7`, not 5.** The original assumption — that the data-rate
  register must match the protocol's 640 µs half-symbol timing — is wrong.
  Asynchronous serial mode streams the demodulator's raw real-time decision,
  not a clocked bitstream; DRATE mainly shapes internal filtering, not
  output timing. A generic value works fine.
- **`FOCCFG`, `BSCFG`, `FSCAL0-3`, `FSTEST`, `DEVIATN`, `MDMCFG1/0`,
  `CHANNR`, `ADDR`, `PKTLEN`** were never configured in earlier drafts (left
  at whatever the chip's power-on-reset defaults happened to be). All are
  now explicit.
- **`MANCHESTER_EN`/`SYNC_MODE`** (in `MDMCFG2`) are set to match a proven
  reference implementation but are, per the datasheet, packet-engine
  features tied to bit-clock recovery that asynchronous serial mode has
  none of — almost certainly don't-care bits here, kept only because they
  match hardware this exact configuration is proven against. If `receiver.py`
  is ever changed to expect an already-Manchester-decoded bitstream instead
  of the raw half-symbol stream the current decoder expects, revisit this
  — it would mean these bits do something after all.
- **The actual blocker was never the CC1101 at all.** See §7/§10: pigpiod
  started with `-m` (disables alerts) silently prevented `pi.callback()`
  from ever firing, regardless of RF-side tuning. Register correctness
  matters and is captured here, but don't let a future regression send
  someone back through this whole table before checking that flag first.
