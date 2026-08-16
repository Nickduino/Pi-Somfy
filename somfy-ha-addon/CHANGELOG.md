# Changelog

This add-on's version always matches the [Pi-Somfy](https://github.com/Nickduino/Pi-Somfy)
release it's built on, so each entry below is what's new in that release.

## 3.2

- Fixed the add-on showing an incorrect version number, which could cause the add-on to fail
  to install or update properly.
- Add support for a CC1101 RF receiver, so button presses on a physical Somfy remote are
  tracked and stay in sync with the app and Home Assistant.
- Added an optional CC1101 transmitter as an alternative to the built-in one.
- Redesigned the schedule editor and the manual-operation remote control in the web UI.

## 3.1

- Added native Home Assistant integration: Pi-Somfy shutters now show up as proper cover
  entities in Home Assistant, with position control, instead of needing a separate setup.
- Added support for running on a Raspberry Pi 5, detected automatically.
- Made the optional MQTT integration easier to set up.

## 3.0

- Initial release as Home Assistant add-on
- Web UI with ingress and external port access
- Auto-discovery for Pi-Somfy custom integration
- Debian-based container with pigpiod for GPIO access
- Persistent configuration across updates
- Watchdog health monitoring
