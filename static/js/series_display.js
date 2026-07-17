// series_display.js - Frontend-only series label sanitizer

export function stripLeadingBracketTags(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';

  // Remove leading tags like [Author] or {Group} while preserving the original value fallback.
  const stripped = raw.replace(/^\s*(?:(?:\[[^\]]+\]|\{[^}]+\})\s*)+/u, '').trim();
  return stripped || raw;
}
