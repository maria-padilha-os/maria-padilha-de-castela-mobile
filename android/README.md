# Android resource and overlay sources

This directory is the Android-facing part of the Padilha design system. It does
not contain a full Gradle/Android SDK project and does not build or flash a ROM.
See [`docs/branding/overlay-and-build.md`](../docs/branding/overlay-and-build.md)
for the complete surface matrix.

## Layout

| Path | Purpose |
| --- | --- |
| `design/src/main/res/` | Light and `values-night` colour tokens, theme attributes, font families, overlayable declaration |
| `overlays/padilha-palette/` | Reference runtime resource overlay (RRO) for one Castela-owned package |
| `system/bootanimation/` | System-build-only boot-animation source contract; not installable |

Shared binaries and generated drawables live under `../assets/android-res/` so
the browser preview and the Android resources use the same canonical files. A
future app build should add both directories as resource sources:

```kotlin
android {
    sourceSets["main"].res.srcDirs(
        "src/main/res",
        "../../assets/android-res",
    )
}
```

## Build constraints

- Do not add `systemui`, `android`, `com.android.settings`,
  `com.android.packageinstaller`, or another security-critical package as an
  overlay target.
- Do not add privileged permissions, `android:sharedUserId`, background
  services, or exported components for theming.
- Do not add a signing config, AVB key, or update-channel change. App signing is
  handled outside this design-resource task.
- The boot animation is system-build only and remains out of scope for the
  current ADR.
- Run `bash tests/all.sh` after changing resources.

The overlay is optional. The base palette in `design/` is enough for Castela
apps; the RRO exists for a signed app-suite build that wants a runtime palette
without a new APK of the target app.
