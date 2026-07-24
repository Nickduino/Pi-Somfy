# RTS Sniffer — proof of concept

Standalone Home Assistant add-on that listens for Somfy RTS remote presses on
433.42 MHz and logs every decoded press:

```
0x14A2C7  UP  code=1337  repeats=4
```

This is **M0** of the receiver design (see
`documentation/Receiver Design.md` §7): it validates hardware, frequency,
range and the decoder with zero coupling to Pi-Somfy's code. Only after the
POC passes its success criteria does the decoder move into `receiver.py` for
the integrated feature.

## Hardware

A CC1101 transceiver module (~$3) tuned in software to exactly 433.42 MHz.
SPI is bit-banged on ordinary GPIOs and only used once at startup, so no
host `config.txt` changes or reboots are needed. Match module pins by
silkscreen **label**, not position (MOSI may be printed `SI`, MISO `SO`):

| CC1101 pin | Signal | Default GPIO | Physical pin (Pi 4) |
|---|---|---|---|
| VCC | 3.3 V supply | — | 17 (or 1) — **never 5 V** |
| GND | ground | — | 39 |
| SCK | SPI clock | GPIO 21 | 40 |
| MOSI (SI) | SPI data → radio | GPIO 20 | 38 |
| MISO (SO) | SPI data → Pi | GPIO 19 | 35 |
| CSN | chip select | GPIO 16 | 36 |
| GDO0 | demodulated data out | GPIO 26 | 37 |
| GDO2 | — | not connected | — |
| ANT | antenna | — | 17 cm solid-core wire, **required** |

## Install (local add-on)

1. Copy this folder to `/addons/rts_sniffer_poc` on the HAOS host (via the
   Samba or SSH add-on).
2. Settings → Add-ons → Add-on Store → ⋮ → *Check for updates*, then install
   "RTS Sniffer (POC)".
3. **Stop the Pi-Somfy add-on first** (Pi 1–4): each container starts its own
   pigpiod, and two daemons contending for DMA/`/dev/mem` is not supported.
4. Start the add-on and watch the log while pressing a physical remote.

## Loopback test (no physical remote, no CC1101 required for TX)

Set `test_tx_interval` to e.g. `30`: the add-on transmits a test frame from
dummy address `0xDEC0DE` through the existing 433.42 MHz **transmitter**
(GPIO 4 by default) every 30 s and verifies its own receiver decodes it,
logging a running success rate. TX and RX share the one pigpiod, which is
exactly how the integrated feature will run.

## POC success criteria (design doc §7)

1. Loopback: ≥95 % of test transmissions decoded with correct
   address/button/rolling code.
2. Range: every physical remote press from the farthest room is decoded.
3. Noise: zero checksum-valid false positives over 24 h of idle listening.
4. Load: sniffer CPU < 5 % on a Pi 4 (watch the periodic `Status:` log line).

## Decoder unit tests (run anywhere, no Pi needed)

```
python3 -m unittest discover addons/rts_sniffer_poc
```

## Notes

- The CC1101 register map derivations live in `sniffer.py`
  (`CC1101_RX_CONFIG`); AGC/TEST analog values are the SmartRF OOK starting
  point and are finalised in the M0 tuning loop per Appendix A of the design.
- Startup is deliberately loud about SPI problems: VERSION is read first and
  every register write is read back — a mis-wired SPI otherwise degrades
  silently into a deaf receiver.
