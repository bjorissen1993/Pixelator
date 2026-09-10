export const DIRECTIONS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;
export const DIRECTIONS_4 = ["N", "E", "S", "W"] as const;
export const DIRECTIONS_1 = ["S"] as const;
export const EXPORT_DIRECTION_ORDER = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"] as const;

export const HEAD_VARIANTS = ["center", "left", "right", "slightUp", "slightDown"] as const;

export const CAMERA_ANGLES = ["high-top-down", "low-top-down", "front"] as const;
export const DETAIL_LEVELS = ["simple", "balanced", "high"] as const;
export const OUTLINE_STYLES = ["none", "soft", "dark"] as const;
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

export const DEFAULT_SPRITE_SIZES = [32, 48, 56, 64] as const;
