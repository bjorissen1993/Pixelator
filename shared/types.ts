import type {
  APPLY_MODES,
  BODY_MOVEMENT,
  CAMERA_ANGLES,
  DETAIL_LEVELS,
  DIRECTIONS_8,
  EXPRESSIVENESS,
  FACIAL_RANGE,
  HEAD_VARIANTS,
  OUTLINE_STYLES,
} from "./constants";

export type Direction = (typeof DIRECTIONS_8)[number];
export type DirectionsMode = "8" | "4" | "1";
export type CameraAngle = (typeof CAMERA_ANGLES)[number];
export type DetailLevel = (typeof DETAIL_LEVELS)[number];
export type OutlineStyle = (typeof OUTLINE_STYLES)[number];
export type Expressiveness = (typeof EXPRESSIVENESS)[number];
export type BodyMovement = (typeof BODY_MOVEMENT)[number];
export type FacialRange = (typeof FACIAL_RANGE)[number];
export type HeadVariant = (typeof HEAD_VARIANTS)[number];
export type SpriteKind = "full" | "body" | "head" | "overlay";
export type StateKind = "static" | "animated";
export type ApplyMode = (typeof APPLY_MODES)[number];
export type LayerKind = "full" | "body" | "head";
export type WarningSeverity = "warning" | "error";

export interface IdentityLock {
  lockFace: boolean;
  lockHair: boolean;
  lockClothing: boolean;
  lockPalette: boolean;
  lockBodyProportions: boolean;
  lockSilhouette: boolean;
  lockSpiritForm: boolean;
  lockAccessories: boolean;
}

export interface SpiritSettings {
  enabled: boolean;
  noLegs: boolean;
  spectralTail: boolean;
  mistFade: boolean;
  auraColor: string;
  notes: string;
}

export interface PaletteSettings {
  colorCount: number;
  locked: boolean;
  colors: string[];
}

export interface EmotionProfile {
  expressiveness: Expressiveness;
  bodyMovement: BodyMovement;
  facialRange: FacialRange;
  defaultMood: string;
  laughterStyle: string;
  sadnessStyle: string;
  angerStyle: string;
  talkingStyle: string;
  customEmotionNotes: string;
}

export interface HeadAnchor {
  headAnchorX: number;
  headAnchorY: number;
  headOffsetX: number;
  headOffsetY: number;
}

export interface QualityWarning {
  code: string;
  message: string;
  severity: WarningSeverity;
}

export interface QualityValidation {
  ok: boolean;
  warnings: QualityWarning[];
  futureChecks: string[];
}

export interface SpriteAsset {
  id: string;
  kind: SpriteKind;
  path: string;
  width: number;
  height: number;
  seed?: number | null;
  prompt: string;
  createdAt: string;
  accepted: boolean;
  validation?: QualityValidation | null;
  head?: HeadAnchor | null;
}

export interface DirectionSlot {
  direction: Direction;
  frames: SpriteAsset[];
  body?: SpriteAsset | null;
  head?: SpriteAsset | null;
  overlays: SpriteAsset[];
  headVariants: Partial<Record<HeadVariant, SpriteAsset>>;
  headAnchor: HeadAnchor;
}

export interface CharacterState {
  id: string;
  name: string;
  baseType: string;
  customPrompt: string;
  directionsMode: DirectionsMode;
  selectedDirections: Direction[];
  frameCount: number;
  loop: boolean;
  animationSpeed: number;
  headSeparated: boolean;
  blinkingEnabled: boolean;
  lookAtTargetEnabled: boolean;
  kind: StateKind;
  createdAt: string;
  directions: DirectionSlot[];
}

export interface AcceptedBase {
  sprite: SpriteAsset;
  acceptedAt: string;
  seed?: number | null;
  prompt: string;
}

export interface CharacterProfile {
  id: string;
  slug: string;
  name: string;
  masterPrompt: string;
  appearance: string;
  clothing: string;
  bodyType: string;
  species: string;
  spirit: SpiritSettings;
  spriteSize: number;
  camera: CameraAngle;
  palette: PaletteSettings;
  outline: OutlineStyle;
  detail: DetailLevel;
  seed?: number | null;
  identityLock: IdentityLock;
  emotion: EmotionProfile;
  states: CharacterState[];
  pendingBase?: SpriteAsset | null;
  acceptedBase?: AcceptedBase | null;
  createdAt: string;
  updatedAt: string;
}

export interface PromptLayers {
  globalStyle: string;
  masterPrompt: string;
  identity: string;
  state: string;
  direction: string;
  expression: string;
  override: string;
  final: string;
}

export interface StateTemplate {
  id: string;
  name: string;
  category: "core" | "social" | "emotional" | "spirit" | "custom";
  baseType: string;
  prompt: string;
  directionsMode: DirectionsMode;
  frameCount: number;
  loop: boolean;
  animationSpeed: number;
  kind: StateKind;
}

export interface ProviderInfo {
  id: string;
  name: string;
  modelId: string;
  supportsReference: boolean;
  nativePixelOutput: boolean;
  notes: string;
}

export interface GenerationResult {
  character: CharacterProfile;
  prompt: PromptLayers;
  usedReference: boolean;
  asset?: SpriteAsset | null;
}

export interface WorkspaceSection {
  id: "character" | "states" | "directions" | "emotion" | "head" | "generation" | "export";
  label: string;
}
