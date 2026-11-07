# CI and device boundaries

The build is split so that a shared CI runner never needs a device, a signing
key, or hundreds of gigabytes of source. The same checks can be run locally.

## What runs where

| Stage | Where | Needs network | Needs device | Notes |
| --- | --- | --- | --- | --- |
| `./build.sh plan` | Any machine, CI | No | No | Prints the pin and requirements. |
| `./build.sh check` | Any machine, CI | No | No | Offline pin, tools, secret, metadata, blob and key-presence checks. |
| `./build.sh test` | Any machine, CI | No | No | Full test suite. |
| `./build.sh verify-pin` | Any machine, CI | No | No | Validates recorded pin data offline. |
| `./build.sh verify-pin --network` | Any machine, scheduled CI | Yes | No | Fetches only the manifest repository and verifies the SSH-signed tag. |
| `./build.sh sync --dry-run` | Any machine, CI | No | No | Prints the repo commands. |
| `./build.sh build --dry-run` | Any machine, CI | No | No | Prints the lunch/make commands. |
| `./build.sh sign --dry-run` | Any machine, CI | No | No | Prints the signing commands. |
| `./build.sh sync` | Build host | Yes | No | 90-136 GiB source plus history. |
| `./build.sh build` | Build host | No | No | 32 GiB+ RAM, 100 GiB+ build space. |
| `./build.sh sign` | Offline build host | No | No | Keys outside the repository. |
| Bootloader unlock, flashing, OTA sideload, hardware tests | Physical device | No | Yes | Manual and intentionally not scripted. |

## CI workflows

- [`ci.yml`](../.github/workflows/ci.yml) runs `./tests/all.sh` on pushes and
  pull requests using a read-only token. It does not upload artifacts, use
  secrets, sync AOSP, build a ROM, or touch a device.
- [`pin-verify.yml`](../.github/workflows/pin-verify.yml) runs weekly and on
  demand. It runs `./scripts/verify-pin.sh --network`, which clones only the
  manifest repository into `.scratch/`, verifies the signed tag and commit, and
  deletes the temporary clone. It does not download vendor blobs.

Both workflows use a pinned `actions/checkout` commit and
`permissions: contents: read`. Neither uses `pull_request_target`.

## What the tests validate

- The pinned release tag is a 10-digit GrapheneOS tag, the tag object and commit
  are distinct 40-character ids, the AOSP baseline is fixed, and the default
  device/product match `config/devices.tsv`.
- The vendored allowed-signers file has the SHA-256 recorded in the pin, and the
  local manifest is well-formed XML.
- Required CI tools are present, and the tool checker reports missing tools
  instead of silently continuing.
- No private key material, API tokens, keystore passwords, or tracked key-store
  filenames are present. Findings print file and line only.
- No public release download URLs, OTA/factory artifact names, update-channel
  metadata, release paths, or tracked release artifacts are present.
- No vendor/firmware/blob paths or oversized tracked files are present.
- The signing key checker rejects a key store inside the repository, checks
  permissions, prints only file names, and never emits key contents.
- The entry point refuses device and publish/release commands, and dry runs do
  not execute anything.
- Required docs cover disk, RAM, Java, Android SDK, CI/device split, signing
  custody, and private-release policy.

## Running locally

```sh
./tests/all.sh
# or
./build.sh check
./build.sh test
```

The full `doctor` check is meant for a build host; a laptop with less than
32 GiB RAM or 236 GiB free will correctly fail it. Use `./build.sh doctor
--no-resources` only to inspect tools and the offline checks.
