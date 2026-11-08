/* Padilha palette resolution for the stock-device preview.
 *
 * The rules mirror design/padilha_palette.py: dynamic colour may replace the
 * accent only when every checked pair still passes. Otherwise the canonical
 * Padilha palette is used, including when token data is missing or partial.
 */

export const REQUIRED_TOKENS = [
  "background",
  "surface",
  "surfaceRaised",
  "textPrimary",
  "textSecondary",
  "accent",
  "accentStrong",
  "onAccent",
  "onAccentStrong",
  "border",
  "success",
  "warning",
  "danger",
];

export const DYNAMIC_ACCENT_PAIRS = [
  ["accent", "background", 4.5],
  ["accent", "surface", 4.5],
  ["accent", "surfaceRaised", 4.5],
  ["onAccent", "accent", 4.5],
];

const HEX_RE = /^#[0-9a-f]{6}$/i;

export function isHex(value) {
  return typeof value === "string" && HEX_RE.test(value);
}

export function normalizeHex(value) {
  if (!isHex(value)) {
    throw new Error(`not a #RRGGBB colour: ${value}`);
  }
  return value.toUpperCase();
}

function channel(value) {
  const normalized = value / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

export function luminance(hexColor) {
  const color = normalizeHex(hexColor).slice(1);
  const red = parseInt(color.slice(0, 2), 16);
  const green = parseInt(color.slice(2, 4), 16);
  const blue = parseInt(color.slice(4, 6), 16);
  return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
}

export function contrast(foreground, background) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

export function bestTextOn(background) {
  const dark = contrast("#000000", background);
  const light = contrast("#FFFFFF", background);
  return dark >= light ? "#000000" : "#FFFFFF";
}

export function themeWithFallback(themeName, data = globalThis.PADILHA_DATA) {
  const fallback = data?.fallbackThemes?.[themeName];
  const supplied = data?.themes?.[themeName];
  if (!fallback && !supplied) {
    return { theme: null, partial: true, missing: true };
  }

  const theme = {};
  let partial = false;
  for (const token of REQUIRED_TOKENS) {
    const candidate = supplied?.[token];
    if (isHex(candidate)) {
      theme[token] = normalizeHex(candidate);
    } else if (isHex(fallback?.[token])) {
      theme[token] = normalizeHex(fallback[token]);
      partial = true;
    } else {
      return { theme: null, partial: true, missing: true };
    }
  }
  return { theme, partial, missing: false };
}

export function validateTheme(theme, pairs = globalThis.PADILHA_DATA?.contrastPairs ?? []) {
  return pairs.map((pair) => {
    const ratio = contrast(theme[pair.foreground], theme[pair.background]);
    return {
      ...pair,
      ratio,
      ok: ratio + 1e-9 >= pair.min,
    };
  });
}

export function resolvePalette(themeName, dynamicAccent = null, data = globalThis.PADILHA_DATA) {
  const resolved = themeWithFallback(themeName, data);
  const meta = {
    theme: themeName,
    source: resolved.missing
      ? "missing-palette"
      : resolved.partial
        ? "partial-fallback"
        : "tokens",
    fallback: resolved.partial,
    dynamic: false,
    reason: null,
  };

  if (!resolved.theme) {
    return { theme: null, meta, checks: [] };
  }

  let theme = { ...resolved.theme };

  if (dynamicAccent !== null && dynamicAccent !== undefined && dynamicAccent !== "") {
    if (!isHex(dynamicAccent)) {
      meta.reason = "dynamic accent is not a #RRGGBB colour";
    } else {
      const candidate = {
        ...theme,
        accent: normalizeHex(dynamicAccent),
        onAccent: bestTextOn(dynamicAccent),
      };
      const failures = [];
      for (const [foreground, background, minimum] of DYNAMIC_ACCENT_PAIRS) {
        const ratio = contrast(candidate[foreground], candidate[background]);
        if (ratio + 1e-9 < minimum) {
          failures.push(
            `${foreground} on ${background} is ${ratio.toFixed(2)}:1 (minimum ${minimum}:1)`,
          );
        }
      }
      if (failures.length === 0) {
        theme = candidate;
        meta.dynamic = true;
        meta.reason = "dynamic accent accepted after contrast checks";
      } else {
        meta.reason = `dynamic accent rejected: ${failures.join("; ")}`;
      }
    }
  }

  return {
    theme,
    meta,
    checks: validateTheme(theme, data?.contrastPairs ?? []),
  };
}

export function cssVariables(theme) {
  const variables = {};
  for (const [name, value] of Object.entries(theme)) {
    const kebab = name.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
    variables[`--color-${kebab}`] = value;
  }
  return variables;
}
