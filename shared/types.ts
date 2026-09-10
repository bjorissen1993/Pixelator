import type {
  APPLY_MODES,
  ASSET_STATUSES,
  BODY_MOVEMENT,
  BODY_TEMPLATES,
  CAMERA_ANGLES,
  DETAIL_LEVELS,
  DIRECTIONS_8,
  EXPRESSIVENESS,
  FACIAL_RANGE,
  HEAD_VARIANTS,
  JOB_STATUSES,
  OUTLINE_STYLES,
  PALETTE_MODES,
  REJECTION_REASONS,
  SEED_MODES,
  SHADING_STYLES,
} from "./constants";

export type Direction = (typeof DIRECTIONS_8)[number];
export type DirectionsMode = "8" | "4" | "1";
export type CameraAngle = (typeof CAMERA_ANGLES)[number];
export type DetailLevel = (typeof DETAIL_LEVELS)[number];
export type OutlineStyle = (typeof OUTLINE_STYLES)[number];
export type ShadingStyle = (typeof SHADING_STYLES)[number];
export type PaletteMode = (typeof PALETTE_MODES)[number];
export type BodyTemplate = (typeof BODY_TEMPLATES)[number];
export type AssetStatus = (typeof ASSET_STATUSES)[number];
export type JobStatus = (typeof JOB_STATUSES)[number];
export type SeedMode = (typeof SEED_MODES)[number];
export type RejectionReason = (typeof REJECTION_REASONS)[number];
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

export interface CompositionSettings {
  fullBodySprite: boolean;
  entireSilhouetteVisible: boolean;
  preventCropping: boolean;
  centerCharacter: boolean;
  fitSafeMargins: boolean;
  noPortraitCloseup: boolean;
  showFullSpiritTail: boolean;
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
  score?: number;
  warnings: QualityWarning[];
  futureChecks: string[];
  occupancy?: number;
  heightRatio?: number;
  widthRatio?: number;
  centerX?: number;
  centerY?: number;
}

export interface GenerationDebug {
  provider: string;
  model: string;
  lora: string;
  loraLoaded: boolean;
  seed?: number | null;
  steps?: number | null;
  guidance?: number | null;
  strength?: number | null;
  referenceDirection?: Direction | null;
  referenceAssetId?: string;
  prompt: string;
  negativePrompt: string;
  workingResolution?: number | null;
  targetResolution?: number | null;
  paletteMode: string;
  usedReference: boolean;
  usedIpAdapter: boolean;
  cropRetries?: number;
}

export interface SpriteAsset {
  id: string;
  kind: SpriteKind;
  path: string;
  previewPath?: string;
  sourcePath?: string;
  width: number;
  height: number;
  seed?: number | null;
  prompt: string;
  negativePrompt?: string;
  createdAt: string;
  accepted: boolean;
  status?: AssetStatus;
  validation?: QualityValidation | null;
  head?: HeadAnchor | null;
  providerId?: string;
  fromDirection?: Direction | null;
  referenceDirection?: Direction | null;
  referenceAssetId?: string;
  strength?: number | null;
  debug?: GenerationDebug | null;
}

export interface GenerationProgress {
  active: boolean;
  label: string;
  step: string;
  steps: string[];
  stepIndex: number;
  current?: number;
  total?: number | null;
  currentItem?: string;
}

export interface DirectionSlot {
  direction: Direction;
  frames: SpriteAsset[];
  candidates?: SpriteAsset[];
  body?: SpriteAsset | null;
  head?: SpriteAsset | null;
  overlays: SpriteAsset[];
  headVariants: Partial<Record<HeadVariant, SpriteAsset>>;
  headAnchor: HeadAnchor;
  status: AssetStatus;
  locked: boolean;
  seed?: number | null;
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
  seed?: number | null;
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
  negativePrompt: string;
  appearance: string;
  clothing: string;
  bodyType: string;
  bodyTemplate: BodyTemplate;
  species: string;
  spirit: SpiritSettings;
  spriteSize: number;
  camera: CameraAngle;
  palette: PaletteSettings;
  paletteMode: PaletteMode;
  outline: OutlineStyle;
  shading: ShadingStyle;
  detail: DetailLevel;
  seed?: number | null;
  seedLocked: boolean;
  styleProfileId?: string | null;
  externalProviderId?: string | null;
  externalCharacterId?: string | null;
  identityLock: IdentityLock;
  composition: CompositionSettings;
  emotion: EmotionProfile;
  states: CharacterState[];
  pendingBase?: SpriteAsset | null;
  acceptedBase?: AcceptedBase | null;
  createdAt: string;
  updatedAt: string;
}

export interface PromptLayers {
  globalStyle: string;
  visualStyle?: string;
  masterPrompt: string;
  identity: string;
  hardConstraints?: string;
  composition?: string;
  state: string;
  direction: string;
  expression: string;
  override: string;
  negative: string;
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

export interface ProviderCapabilities {
  supportsTextToImage: boolean;
  supportsImg2Img?: boolean;
  supportsImageToImage: boolean;
  supportsReferenceImage: boolean;
  supportsNegativePrompt: boolean;
  supportsLoRA?: boolean;
  supportsControlNet?: boolean;
  supportsIPAdapter?: boolean;
  supportsPaletteConditioning?: boolean;
  supportsDirectionGeneration: boolean;
  supportsBatchDirections: boolean;
  supportsTargetPalette: boolean;
  supportsInitImage: boolean;
  supportsInpainting: boolean;
  supportsAnimation: boolean;
  supportsSkeletonGuidance: boolean;
  nativePixelOutput: boolean;
  preferredSizes: number[];
  preferredSize: number;
  workingSize?: number;
  batchIsSequential: boolean;
}

export interface ProviderInfo {
  id: string;
  name: string;
  modelId: string;
  supportsReference: boolean;
  nativePixelOutput: boolean;
  notes: string;
  capabilities: ProviderCapabilities;
  loraPath?: string;
  loraLoaded?: boolean;
  loraStrength?: number;
  controlnetLoaded?: boolean;
  ipAdapterLoaded?: boolean;
  fallbackTurbo?: boolean;
  device?: string;
  dtype?: string;
  workingSize?: number;
}

export interface GenerationJob {
  id: string;
  characterId: string;
  operation: string;
  status: JobStatus;
  label: string;
  current: number;
  total: number | null;
  currentItem: string;
  error: string;
  usedReference: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface GenerationResult {
  character: CharacterProfile;
  prompt: PromptLayers;
  usedReference: boolean;
  asset?: SpriteAsset | null;
  candidates?: SpriteAsset[];
  job?: GenerationJob | null;
}

export interface StyleProfile {
  id: string;
  name: string;
  palette: PaletteSettings;
  camera: CameraAngle;
  outline: OutlineStyle;
  shading: ShadingStyle;
  detail: DetailLevel;
  spriteSize: number;
  globalPositive: string;
  globalNegative: string;
  referencePaths: string[];
  createdAt: string;
  updatedAt: string;
}

export interface MemoryEntry {
  id: string;
  kind: "accepted" | "rejected";
  characterId: string;
  characterName: string;
  prompt: string;
  negativePrompt: string;
  seed?: number | null;
  outline: OutlineStyle;
  shading: ShadingStyle;
  detail: DetailLevel;
  camera: CameraAngle;
  palette: string[];
  providerId: string;
  stateName: string;
  direction?: Direction | null;
  rejectionReason?: RejectionReason | null;
  customReason: string;
  assetPath: string;
  createdAt: string;
}

export interface MemorySuggestions {
  recommendedSeeds: number[];
  recommendedPalettes: string[][];
  promptFragments: string[];
  defaultOutline?: OutlineStyle;
  defaultShading?: ShadingStyle;
  defaultDetail?: DetailLevel;
  notes: string[];
}

export interface WorkspaceSection {
  id: "studio" | "identity" | "library" | "export";
  label: string;
}
