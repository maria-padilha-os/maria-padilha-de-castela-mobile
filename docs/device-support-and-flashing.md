# Device support and flashing runbook

- **Status:** Documented, not device-validated
- **Date:** 2026-11-14
- **Scope:** A supported path from a stock Pixel to official GrapheneOS plus the
  Castela app layer
- **Reference device:** Pixel 9a (`tegu`)
- **Preflight checker:** [`tools/check_flash_inputs.py`](../tools/check_flash_inputs.py)
- **Policy:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md) ·
  [attribution, trademark, and redistribution rules](legal/grapheneos-aosp-attribution.md)

> **Castela Mobile is not official GrapheneOS.** It is an independent project
> that runs on official GrapheneOS. It is not a GrapheneOS fork, an official
> GrapheneOS build, or an "unofficial build" of GrapheneOS. GrapheneOS and its
> logo are trademarks of the GrapheneOS project; Android and Pixel are
> trademarks of Google LLC. This project is not affiliated with, endorsed by, or
> supported by either project.

> **There is no Castela system image.** This runbook installs **official
> GrapheneOS** on a supported Pixel, locks the bootloader, and then installs
> signed Castela apps. It does not authorize a Castela ROM, a custom verified
> boot key, a Castela OTA server, or a preinstalled Castela system image.

> **The repository never flashes a device.** Nothing in this checkout runs an
> unlock, erase, install, or flash command. The checker is read-only, and every
> write in this runbook is a manual operator action performed outside the
> repository after reading the official GrapheneOS instructions.

## 1. Supported path

```text
stock, carrier-agnostic Pixel from the matrix
        |
        |  manual backup, then official GrapheneOS installer
        |  (bootloader unlock -> official images -> bootloader lock)
        v
official GrapheneOS, locked bootloader, verified boot intact
        |
        |  install signed Castela APKs from the private channel
        v
Castela app layer: launcher, theme/assets, security panel, setup companion
```

The supported path has three hard rules:

1. **Install official GrapheneOS only.** Download it from the official
   GrapheneOS release site and verify its official OpenSSH signature. Do not
   mirror, rehost, re-sign, or modify the images.
2. **Use a supported Pixel.** The device must be in the
   [matrix below](#2-supported-pixel-and-device-matrix), carrier-agnostic, and
   supported by GrapheneOS at installation time. Generic system images,
   non-Pixel ports, and source-only targets are not supported.
3. **Keep the bootloader locked after installation.** An unlocked bootloader is
   a development state, not a supported daily-use or release-validation state.

The Castela apps are ordinary apps. They are not preinstalled, do not use a
system partition, do not use `sharedUserId`, and do not need root. They also do
not replace the GrapheneOS boot animation, system font, system UI, lock screen,
or default apps. Those remain GrapheneOS-owned.

## 2. Supported Pixel and device matrix

The matrix follows GrapheneOS official production support and the OEM minimum
support dates published by GrapheneOS as of **2026-11-14**. Re-check the
[official supported-devices list](https://grapheneos.org/faq#supported-devices)
and the [official releases page](https://grapheneos.org/releases) before every
installation cycle.

| Device | Codename | OEM minimum support end | Castela role |
| --- | --- | --- | --- |
| Pixel 9a | `tegu` | April 2032 | **Reference device and primary validation** |
| Pixel 8a | `akita` | May 2031 | Secondary validation (minimum practical spec) |
| Pixel 8 | `shiba` | October 2030 | Compatibility testing |
| Pixel 8 Pro | `husky` | October 2030 | Compatibility testing |
| Pixel 9 | `tokay` | August 2031 | Compatibility testing |
| Pixel 9 Pro | `caiman` | August 2031 | Compatibility testing |
| Pixel 9 Pro XL | `komodo` | August 2031 | Compatibility testing |
| Pixel 9 Pro Fold | `comet` | August 2031 | Best-effort foldable layout |
| Pixel 10 | `frankel` | August 2032 | Compatibility testing |
| Pixel 10 Pro | `blazer` | August 2032 | Compatibility testing |
| Pixel 10 Pro XL | `mustang` | August 2032 | Compatibility testing |
| Pixel 10 Pro Fold | `rango` | October 2032 | Best-effort foldable layout |
| Pixel 10a | `stallion` | March 2033 | Future reference; compatibility testing |
| Pixel 7 | `panther` | October 2027 | Legacy best-effort |
| Pixel 7 Pro | `cheetah` | October 2027 | Legacy best-effort |
| Pixel 7a | `lynx` | May 2028 | Legacy best-effort |
| Pixel 6 | `oriole` | October 2026 | OEM minimum ended; no guarantee |
| Pixel 6 Pro | `raven` | October 2026 | OEM minimum ended; no guarantee |
| Pixel 6a | `bluejay` | July 2027 | Legacy best-effort |
| Pixel Fold | `felix` | June 2028 | Best-effort foldable layout |
| Pixel Tablet | `tangorpro` | June 2028 | Best-effort tablet layout |

Rules:

- A device is supported only while **GrapheneOS officially supports it** and
  publishes an official build for it. A device still being sold is not proof of
  support.
- "Compatibility testing" means the app suite is expected to install and pass
  smoke tests. It does not mean every layout has been tuned for that device.
- "Legacy best-effort" means no performance or long-term support promise. The
  OEM minimum support window may already have ended or be close to ending.
- Foldables and tablets need explicit layout review. Do not assume a phone
  layout scales.
- The reference device must run **official GrapheneOS stable with a locked
  bootloader** before a release is signed off. Rooted or unlocked devices are
  development-only.
- Carrier variants are not recommended. A carrier lock can prevent OEM
  unlocking and therefore prevent installing GrapheneOS. Do not try to bypass a
  carrier lock.
- No unlisted device, generic system image, emulator, or non-Pixel port is
  supported for release validation. An emulator may be used for app layout work,
  never as evidence that flashing or verified boot works.

## 3. Prerequisites

### 3.1 Device and authority

- One physically owned, carrier-agnostic Pixel from the matrix. You must have
  the right to erase it and install another operating system on it.
- A device that is not managed by an employer, carrier, school, or another party
  whose policy forbids unlocking.
- Enough battery charge for the whole process. Keep the device on a charger when
  the installer asks for it.
- The device's current lock method and account credentials, if the stock OS
  requires them before a reset. Remove accounts you cannot recover **before**
  wiping the device.
- No expectation that data survives. Unlocking and locking both wipe data.

### 3.2 Host computer, cable, and environment

- A bare-metal host is strongly preferred. USB passthrough from a virtual
  machine is a common source of failed installs.
- At least 2 GiB of free memory and 32 GiB of free storage for the installer
  workflow, per the official GrapheneOS guide.
- A high-quality USB-C cable, connected directly to the host. Avoid hubs,
  front-panel ports, and charge-only cables.
- An up-to-date host OS and browser. Use the officially supported host and
  browser combinations from the GrapheneOS install page.
- For the command-line path, an up-to-date `fastboot` (the official guide's
  minimum at the time of writing is 35.0.1) and OpenSSH.
- Non-root operation. If Linux udev rules are missing, a host administrator must
  install the distribution's Android udev package. This repository does not
  install host packages and does not run privileged commands.
- Close or stop software that claims the USB device, such as an automatic
  firmware updater. Fix the host conflict using the official guide; do not
  disable security controls blindly.

### 3.3 Official GrapheneOS artifacts

For the selected codename and version, obtain from the official release site:

- `<codename>-install-<version>.zip` — the factory/install image;
- `<codename>-install-<version>.zip.sig` — its official OpenSSH signature;
- `allowed_signers` — the official GrapheneOS signing key.

Verify the signature with the official guide's `ssh-keygen -Y verify` command
before extracting or flashing. A successful HTTPS download is not a substitute
for signature verification. Keep the verified zip, its signature, and the
allowed-signers file together in a staging directory with restrictive
permissions.

Do **not** use an OTA update package for an initial installation. OTA packages
belong to the update/recovery path after GrapheneOS is already installed.

### 3.4 Castela artifacts

Castela does not ship an OS image. The private app channel supplies signed APKs,
their SHA-256 digests, and the expected signing-certificate digest for each app.
Before installing any APK:

- verify its SHA-256 against the private release record;
- verify the signer with `apksigner verify --print-certs` and compare the
  certificate digest with the release record;
- confirm the version and minimum GrapheneOS/Android version;
- install only from the private, authenticated channel.

There is no signed APK in this repository. A missing release record means stop,
not "install the debug build."

### 3.5 Stop before touching the device if

- the model or codename does not match the matrix;
- the device is carrier-locked and OEM unlocking is unavailable;
- the official release for that codename does not exist;
- the official signature check fails;
- the preflight checker reports a checksum or path failure;
- the bootloader is already in an unknown state or the device shows an
  unexplained custom OS warning;
- the device contains data you have not backed up and cannot lose;
- you are being asked to disable verified boot, root the device, or use a
  third-party flashing tool.

Stop and report the condition. Do not improvise a workaround.

## 4. Bootloader unlock: security consequences

Unlocking the bootloader is a deliberate security downgrade. It is required for
the initial official GrapheneOS installation on a stock Pixel, but it must not
remain the normal operating state.

### 4.1 What unlocking changes

- **All user data is erased.** The unlock confirmation wipes the device,
  including app data, photos, messages, and the encryption keys that protect
  them.
- **Verified boot is no longer enforcing the normal chain.** An unlocked
  bootloader can flash or boot an image that is not the official signed OS.
  The device displays a warning, and the security guarantees of a locked device
  do not apply.
- **A physical attacker has a much larger attack surface.** Someone with brief
  USB access can attempt to replace the OS, recovery, or firmware. Locking the
  bootloader again is part of the installation, not an optional finishing touch.
- **Official GrapheneOS support assumes a locked bootloader.** A device left
  unlocked is treated as an incomplete installation.
- **Locking also wipes data.** The correct sequence is unlock, install, lock,
  and only then set up accounts and restore data.

### 4.2 Security and operational consequences

- Do not unlock a daily driver, a work device, or a device holding data you have
  not backed up. Use a device you can afford to erase and troubleshoot.
- Do not disable verified boot, flash a custom AVB key, or install a third-party
  recovery to "make it easier." That is outside this project's supported path.
- Do not use a locked bootloader as a reason to skip operating-system updates.
  GrapheneOS remains responsible for OS, firmware, kernel, and browser updates.
- An unlocked device may fail hardware-backed attestation, banking, enterprise,
  or anti-theft checks. Relocking correctly restores the official GrapheneOS
  verified-boot identity for a supported device, but it does not undo a data
  wipe or any malicious change made while unlocked.
- Anti-theft and factory-reset protection behavior differs between the stock OS
  and GrapheneOS. Remove unknown accounts before wiping, and do not expect
  account-based recovery to restore the device.
- Carrier locks, leases, insurance terms, and warranties may be affected.
  Check them before unlocking. This project does not help bypass a carrier or
  account lock.
- If the device asks for an account, carrier code, or unlock token you do not
  have, stop. Do not pay a third party to bypass it.

### 4.3 Before you unlock

1. Confirm the exact model and codename.
2. Complete the [backup](#5-backup-before-any-wipe) and test a restore.
3. Confirm that OEM unlocking is enabled in the stock OS developer settings.
4. Read the official GrapheneOS installation page for the current warnings and
   command sequence. The official page is authoritative if it differs from this
   summary.
5. Have the verified official image and the preflight result ready **before**
   starting the unlock.

## 5. Backup before any wipe

Unlocking and locking both erase the device. Treat the first backup as the only
copy until you prove the restore works.

Back up and verify:

- photos, videos, voice notes, downloads, and documents;
- contacts, calendar, SMS/MMS, call history, and chat exports that support
  export;
- authenticator seeds, recovery codes, password-manager recovery material, and
  any hardware-token backup;
- eSIM/SIM transfer information and carrier account access;
- app-specific exports and any data that cannot be re-downloaded;
- device encryption recovery keys, if the stock OS exposes them;
- a written record of the current OS build, model, codename, and any carrier or
  account restrictions.

Rules for the backup:

- Use a trusted, encrypted local destination. Do not upload sensitive backups to
  a service you do not trust.
- Keep at least one copy offline or on a separate device.
- Perform a restore test before wiping: open several representative files,
  restore contacts, and confirm that recovery codes work.
- Do not put backups, captures, keys, or personal data in this repository. The
  security panel's pcap and inventory data are separate sensitive data and must
  be exported only to a user-chosen destination.
- After the new OS is installed and locked, restore data only after confirming
  that the device boots normally and verified boot is in the expected state.

No backup means the data is gone. Do not rely on a carrier or repair shop to
recover it after a wipe.

## 6. Read-only preflight checker

[`tools/check_flash_inputs.py`](../tools/check_flash_inputs.py) is a local
guard rail. It verifies **device-specific image paths and SHA-256 digests**, prints
a report, and exits. It does not download, write, open a USB device, invoke the
bootloader, or run an installer. It **never flashes** anything.

### 6.1 Staging layout

Keep the verified official image, its signature, and a manifest together:

```text
/secure/staging/tegu/
  SHA256SUMS
  tegu-install-2026110800.zip
  tegu-install-2026110800.zip.sig
```

Generate the manifest only after the official OpenSSH signature has verified.
SHA-256 is an integrity check for the local copy; it is not proof of
publisher authenticity.

```bash
cd /secure/staging/tegu
sha256sum tegu-install-2026110800.zip tegu-install-2026110800.zip.sig > SHA256SUMS
```

### 6.2 Run the checker

```bash
python3 tools/check_flash_inputs.py \
  --device tegu \
  --image-dir /secure/staging/tegu \
  --manifest /secure/staging/tegu/SHA256SUMS
```

A successful run prints:

```text
preflight ok: tegu (Pixel 9a)
...
No write, USB access, bootloader command, or flash was performed.
```

The checker refuses, with a non-zero exit status:

- an unsupported or misspelled device codename;
- an image filename for a different device;
- absolute paths, `..`, nested paths, backslashes, or other non-bare filenames;
- symbolic links, missing files, directories, and empty files;
- a manifest with a malformed digest, duplicate entry, or no install zip;
- an OTA-only manifest, which cannot perform an initial installation;
- any SHA-256 mismatch.

### 6.3 What the checker cannot do

- It does **not** verify the official OpenSSH signature. Do that separately
  with the command in the official GrapheneOS guide.
- It does **not** detect the physical device, its serial number, its current
  bootloader state, or whether the USB cable is connected. Those are operator
  checks in the official installer.
- It does **not** verify Castela APK signatures. Use the private release record
  and `apksigner verify --print-certs`.
- A passing check is permission to continue reviewing the manual procedure, not
  permission to flash without reading it.

## 7. Manual flashing procedure

> **Do not execute these steps as part of repository maintenance or CI.** This
> section is an operator runbook. The repository contains no script that
> performs them, and the checker stops before any write.

Use the official [web installer](https://grapheneos.org/install/web) unless you
specifically need the [command-line guide](https://grapheneos.org/install/cli).
The official guide is authoritative. The summary below exists so the reader
knows the shape of the process and the safety gates.

### 7.1 Recommended: official web installer

1. Back up and test the restore. Confirm you can lose all device data.
2. Update the stock OS, enable developer options, and enable **OEM unlocking**.
3. Open the official GrapheneOS web installer in a supported, up-to-date
   browser. Do not use private/incognito mode, a Snap/Flatpak browser, or a
   virtual machine unless the official guide explicitly supports it.
4. Boot the Pixel into the bootloader interface and connect the USB cable
   directly to the host.
5. Follow the installer's **Unlock bootloader** action and confirm on the device.
   This wipes the device.
6. Let the installer download or select the official release, then flash it.
   Do not interrupt the firmware or OS flashing stage.
7. Follow the installer's **Lock bootloader** action before setting up the
   device. This wipes again.
8. Boot GrapheneOS, complete the first-run setup, and disable OEM unlocking when
   the setup screen offers it.
9. Verify the verified-boot state as described in the official guide. For the
   Pixel 9a reference device, the official GrapheneOS verified-boot key hash at
   the time of writing is
   `0508de44ee00bfb49ece32c418af1896391abde0f05b64f41bc9a2dfb589445b`.
10. Install the signed Castela apps only after the OS is locked and updated.

### 7.2 Command-line reference

This is a summary, not a copy of the official guide. Use the official CLI page
for exact package setup, troubleshooting, and current versions.

1. Verify that `fastboot --version` is at least the official minimum (35.0.1 at
   the time of writing) and that `ssh-keygen` is available. Run unprivileged.
2. Enable **OEM unlocking** in the stock OS. Back up first.
3. Boot into the bootloader interface and connect the device directly.
4. Unlock, confirming on the device. **This wipes all data.**

   ```bash
   fastboot flashing unlock
   ```

5. Download the official install zip and signature, plus `allowed_signers`.
6. Verify the official signature before extraction:

   ```bash
   ssh-keygen -Y verify \
     -f allowed_signers \
     -I contact@grapheneos.org \
     -n "factory images" \
     -s tegu-install-VERSION.zip.sig \
     < tegu-install-VERSION.zip
   ```

7. Create the SHA-256 manifest and run the read-only checker from section 6.
8. Extract the verified zip and run the official flashing script from inside the
   extracted directory:

   ```bash
   bsdtar xvf tegu-install-VERSION.zip
   cd tegu-install-VERSION
   bash flash-all.sh
   ```

   On Windows, use the official `flash-all.bat`. Do not substitute an
   unofficial flashing script.
9. Wait until the script finishes completely. Do not unplug the device, press
   buttons, or start setup early.
10. Lock the bootloader before using the device. **This wipes data again.**

    ```bash
    fastboot flashing lock
    ```

11. Reboot, verify the verified-boot key hash in the official list, disable OEM
    unlocking, and only then restore data.

### 7.3 After the first boot

- Confirm the device boots without an unlocked-bootloader warning.
- Confirm the model and codename match the matrix.
- Apply GrapheneOS updates through the normal updater. Castela does not proxy,
  mirror, or re-sign OS updates.
- Install the Castela apps from the private channel after checking their
  SHA-256 digests and signer certificates.
- Do not grant root, device-admin, or accessibility permissions that the app
  does not need. The security panel is an ordinary app; it does not have kernel,
  baseband, or verified-boot visibility.
- Keep the previous signed APKs and release notes so an app rollback is a normal
  reinstall rather than an OS recovery event.

### 7.4 What is not installed

This path does **not** install a Castela boot animation, system font, system UI
theme, preinstalled launcher, or custom OTA channel. Those require a system
image and a new architecture decision. The Castela launcher is a user-installed
default-home replacement; the wallpaper and icons are app assets.

## 8. Recovery

Recovery starts with stopping. Do not run random erase commands, "unbrick"
utilities, EDL tools, or third-party ROMs. They can destroy the evidence needed
to recover the device and may make a recoverable device unrecoverable.

| Situation | Safe action |
| --- | --- |
| Preflight or signature check fails | Stop. Re-download from the official release site, re-verify, and regenerate the manifest. Do not flash the failed file. |
| Device is not detected | Try a known-good direct USB cable and another direct port. Remove hubs and virtual machines. Confirm the official `fastboot` version and close firmware updaters that claim the device. |
| Wrong model or codename in the installer | Stop. Never flash another codename's image. Re-check the matrix and official release name. |
| Unlock fails or OEM unlocking is unavailable | Stop. The device may be carrier-locked or account-locked. Do not use a paid unlock bypass. |
| Flash fails before the bootloader is locked | Keep the device in the bootloader interface. Re-verify the official image and rerun the official installer. Check cable, port, host memory, and temporary-directory space. |
| Device is locked but will not boot after installation | Boot to the bootloader if possible. If it can still be unlocked, unlock, reinstall the verified official image, and lock again. If it cannot, stop and use official GrapheneOS support channels. |
| Device boots with an unlocked-bootloader warning | Finish the installation by locking the bootloader. Locking wipes data, so do this before restoring anything sensitive. |
| OTA update boot loop after a working install | Use the official recovery/sideload path with the official full OTA package, or factory reset. Do not use an OTA package for an initial install. Do not attempt a downgrade. |
| Device shows an unexpected custom OS or verified-boot warning | Stop. Record the warning and ask the official GrapheneOS community. Do not relock over an unknown image. |
| Data is missing after a wipe | Restore from the tested backup after the OS is locked and booting normally. If there is no backup, the data cannot be recovered by this project. |
| You need to return to the stock OS | Follow the official GrapheneOS guide's "replacing GrapheneOS with the stock OS" section, including erasing the custom AVB key before flashing and locking. Do not use a Castela image. |

Recovery rules:

- Never relock the bootloader over an image you have not verified.
- Never use an OTA package for the initial installation.
- Never downgrade; Android verified boot and rollback protection may refuse it.
- Do not disable verified boot or flash a custom AVB key to get past a warning.
- If the device is physically damaged, wet, overheating, or showing hardware
  failure, stop and use the manufacturer's service path.
- Keep the verified image, manifest, and a written log of what was attempted.

## 9. Validation status and review cadence

This document defines the intended supported path. It is not a claim that a
device has been flashed or that the Castela app suite has passed device
validation.

Current status:

- No Castela system image, ROM, OTA package, or custom verified-boot key exists.
- No device has been flashed by this repository.
- The Pixel 9a reference device has not yet been signed off for release
  validation in this checkout.
- The checker and this runbook are tested offline with generated files only.

Before any tester distribution, the maintainers must record:

- the reference device model, codename, official GrapheneOS version, and
  verified-boot key hash;
- a successful official signature and SHA-256 preflight;
- a locked bootloader and a normal boot without an unlocked warning;
- a tested backup and restore;
- a recovery rehearsal that does not depend on an unofficial tool;
- the signed Castela APK digests and signer certificate digests.

Review this matrix and the official support dates every six months, and before
each release. Update the matrix when GrapheneOS changes official support. A
future Castela system image would require a new ADR, signing ceremony, recovery
plan, and legal review; this runbook does not authorize one.

## 10. References

Accessed 2026-11-14.

- [GrapheneOS installation overview](https://grapheneos.org/install/)
- [GrapheneOS web installer](https://grapheneos.org/install/web)
- [GrapheneOS command-line install guide](https://grapheneos.org/install/cli)
- [GrapheneOS supported devices and support lifetimes](https://grapheneos.org/faq#supported-devices)
- [GrapheneOS releases and official image signatures](https://grapheneos.org/releases)
- [GrapheneOS usage and updates](https://grapheneos.org/usage#updates)
- [Google Pixel factory images and web flashing tool](https://flash.android.com/back-to-public)
- [ADR 0001: GrapheneOS base, device support, and Padilha branding](adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- [Attribution, trademark, and redistribution rules](legal/grapheneos-aosp-attribution.md)
- [Padilha security panel contract](security-panel.md)
