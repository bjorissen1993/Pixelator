export const DIRECTIONS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;
export const DIRECTIONS_4 = ["N", "E", "S", "W"] as const;
export const DIRECTIONS_1 = ["S"] as const;
export const EXPORT_DIRECTION_ORDER = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"] as const;

export const HEAD_VARIANTS = ["center", "left", "right", "slightUp", "slightDown"] as const;

export const CAMERA_ANGLES = ["high-top-down", "low-top-down", "side"] as const;
export const DETAIL_LEVELS = ["low", "medium", "high"] as const;
export const OUTLINE_STYLES = ["black", "colored", "selective", "lineless"] as const;
export const SHADING_STYLES = ["none", "basic", "medium", "detailed"] as const;
export const PALETTE_MODES = ["generated", "project", "custom", "locked"] as const;
export const BODY_TEMPLATES = ["bipedal", "semi-chibi-bipedal", "quadrupedal", "custom"] as const;
export const ASSET_STATUSES = ["missing", "pending", "accepted", "rejected", "locked"] as const;
export const JOB_STATUSES = ["queued", "generating", "processing", "completed", "failed"] as const;
export const SEED_MODES = ["random", "reuse_base", "locked", "variation"] as const;
export const FRAME_COUNTS = [1, 4, 6, 8, 10, 12, 16] as const;
export const REJECTION_REASONS = [
  "wrong_identity",
  "wrong_clothing",
  "wrong_colors",
  "wrong_body_shape",
  "wrong_direction",
  "wrong_pose",
  "wrong_spirit_form",
  "poor_pixel_quality",
  "too_much_detail",
  "too_little_detail",
  "custom",
] as const;

export const EXPRESSIVENESS = ["low", "medium", "high"] as const;
export const BODY_MOVEMENT = ["subtle", "natural", "animated"] as const;
export const FACIAL_RANGE = ["limited", "balanced", "broad"] as const;

export const APPLY_MODES = [
  "future_only",
  "regenerate_current_state",
  "regenerate_selected_direction",
  "regenerate_all_states",
  "regenerate_head_layers",
] as const;

export const DEFAULT_SPRITE_SIZES = [32, 48, 56, 64, 96, 128] as const;
