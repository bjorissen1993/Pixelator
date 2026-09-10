export function assetUrl(path?: string | null, cacheKey?: string | number | null) {
  if (!path) return "";
  const bust = cacheKey ? `?t=${encodeURIComponent(String(cacheKey))}` : "";
  return `/data/${path}${bust}`;
}

export function previewSrc(asset?: { path?: string | null; previewPath?: string | null; createdAt?: string } | null) {
  if (!asset) return "";
  const preview = asset.previewPath || asset.path;
  if (!preview) return "";
  return assetUrl(preview, asset.createdAt);
}

export function spriteSrc(asset?: { path?: string | null; createdAt?: string } | null) {
  if (!asset?.path) return "";
  return assetUrl(asset.path, asset.createdAt);
}
