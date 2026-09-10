export function assetUrl(path?: string | null, cacheKey?: string | number | null) {
  if (!path) return "";
  const bust = cacheKey ? `?t=${encodeURIComponent(String(cacheKey))}` : "";
  return `/data/${path}${bust}`;
}
