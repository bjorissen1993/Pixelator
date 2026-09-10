import type { QualityValidation, SpriteAsset } from "@shared";

const INVALID_BASE_MESSAGES: Record<string, string> = {
  likely_portrait: "Invalid base: likely portrait composition",
  likely_closeup: "Invalid base: likely portrait composition",
  likely_non_full_body: "Invalid base: likely portrait composition",
  likely_cropped: "Invalid base: likely cropped",
  touches_top: "Invalid base: likely cropped",
  touches_bottom: "Invalid base: likely cropped",
  touches_left: "Invalid base: likely cropped",
  touches_right: "Invalid base: likely cropped",
  touches_edges: "Invalid base: likely cropped",
  silhouette_incomplete: "Invalid base: likely cropped",
  missing_lower_body: "Invalid base: missing lower body / spirit tail",
  lower_spirit_body_missing: "Invalid base: missing lower body / spirit tail",
  missing_spirit_tail: "Invalid base: missing lower body / spirit tail",
};

export function invalidBaseReasons(validation?: QualityValidation | null): string[] {
  if (!validation) return [];
  const reasons: string[] = [];
  for (const warning of validation.warnings ?? []) {
    const message = INVALID_BASE_MESSAGES[warning.code];
    if (message && !reasons.includes(message)) reasons.push(message);
  }
  if (validation.validForBase === false && reasons.length === 0) {
    reasons.push("Invalid base: likely non-full-body output");
  }
  return reasons;
}

export function canAcceptAsBase(asset?: SpriteAsset | null): boolean {
  if (!asset) return false;
  return invalidBaseReasons(asset.validation).length === 0 && asset.validation?.validForBase !== false;
}
