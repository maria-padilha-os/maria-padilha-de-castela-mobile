# Castela Mobile

Public-source cybersecurity mobile image based on GrapheneOS, with the look and
feel of Maria Padilha. **Release builds remain private.**

This is **not official GrapheneOS**. It is a private project that uses the
GrapheneOS/AOSP base and adds a Padilha design overlay plus a security panel.

## Status

**Scaffold / feasibility.** The first task is an ADR comparing a full
GrapheneOS build against a Padilha overlay/companion on stock GrapheneOS,
covering build requirements, supported Pixel devices, signing, OTA updates, and
maintenance cost. No ROM is built and no device has been flashed.

## Planned surface

- Padilha wallpaper, palette, fonts, icons, launcher, and boot treatment
- readable light/dark colours with contrast checks
- a dedicated security panel with authorized lab mode
- local network inventory, pcap review, and permission/integrity audits
- no automatic scanning, no hidden privileged service, no telemetry

## Safety

Do not flash a device until the device matrix, recovery documentation, and
signed build pipeline exist. Do not publish builds; release artifacts remain
private. Do not claim this is official GrapheneOS.

## Relationship to the other repositories

The Padilha design language and shell work live in
[`maria-padilha-de`](https://github.com/maria-padilha-os/maria-padilha-de).
The normal mobile OS is
[`maria-padilha-mobile`](https://github.com/maria-padilha-os/maria-padilha-mobile).
The desktop cyber image is
[`maria-padilha-de-castela`](https://github.com/maria-padilha-os/maria-padilha-de-castela).
