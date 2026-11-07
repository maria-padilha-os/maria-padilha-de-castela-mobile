# Signing key custody

Release signing keys are the trust root for updates and verified boot. They
must never be committed, copied into the source tree, printed by a script, or
uploaded. This scaffold keeps them outside the checkout and provides a
metadata-only presence checker.

## Location and layout

The default location is:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/castela-mobile/signing/<device>/
```

Override it with `CASTELA_SIGNING_KEY_DIR` or `--key-dir`. The path must be
outside this repository; `scripts/check-signing-keys.sh` refuses a key store
inside the checkout.

Expected files per device, as listed in
[`config/signing-keys.txt`](../config/signing-keys.txt):

```text
releasekey.pk8              releasekey.x509.pem
platform.pk8                platform.x509.pem
shared.pk8                  shared.x509.pem
media.pk8                   media.x509.pem
networkstack.pk8            networkstack.x509.pem
bluetooth.pk8               bluetooth.x509.pem
sdk_sandbox.pk8             sdk_sandbox.x509.pem
gmscompat_lib.pk8           gmscompat_lib.x509.pem
nfc.pk8                     nfc.x509.pem
avb.pem                     avb_pkmd.bin
id_ed25519
```

`avb_pkmd.bin` is the public AVB verification key and is safe to publish in
principle, but it stays with the rest of the set so no key material enters git.

Permissions must be owner-only: directories `700` or stricter, private files
`600` or stricter. The checker accepts a stricter mode and rejects group/other
access. Keys should be encrypted at rest with a passphrase, backed up offline,
and generated per device variant. Use an encrypted or no-swap environment during
signing.

## Presence checker

```sh
./scripts/check-signing-keys.sh --device tegu
./scripts/check-signing-keys.sh --device tegu --quiet
./scripts/check-signing-keys.sh --allow-missing   # CI/doctor only
```

The checker verifies paths, regular files and permission bits. It does not run
`cat`, `openssl`, `ssh-keygen -y`, or any other command that would reveal key
contents. It prints only device/file names and modes. `--allow-missing` turns a
completely absent key store into a skip for CI and `doctor`; an existing but
incomplete or badly permissioned store still fails.

## Signing a build

After a successful unsigned build:

```sh
./build.sh sign --device tegu --build-number 2026110200
```

The command:

1. Re-verifies the synced manifest tag and commit.
2. Runs the presence/permission checker against the external key store.
3. Creates a `keys` symlink inside the ignored source tree, only if one does
   not already exist.
4. Builds `otatools-package`, runs `script/finalize.sh`, and runs
   `script/generate-release.sh` with `OFFICIAL_BUILD=false`.
5. Leaves signed artifacts under the ignored source tree at
   `.scratch/grapheneos/releases/<build-number>/`.

It does not upload, publish, configure an update server, or write release
metadata into this repository. Do not point the Updater app at the official
GrapheneOS update server: a build signed with different keys cannot use it.

## Rotation and recovery

The signing keys cannot be changed after a device is locked without a factory
reset and re-flash. Generate unique keys per device variant, keep multiple
offline backups, and record only their location and a private inventory outside
this repository. Never put key material, recovery phrases, or passwords in git,
issues, CI logs, or build artifacts.

If the checker fails, stop. Do not bypass it by copying keys into the checkout
or loosening permissions on a shared directory.
