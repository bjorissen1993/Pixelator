import type { SpriteAsset } from "@shared";
import { invalidBaseReasons } from "../baseValidation";

export function BaseCompositionPanel({ asset, title = "Base composition debug" }: { asset?: SpriteAsset | null; title?: string }) {
  const validation = asset?.validation;
  const debug = asset?.debug;
  if (!asset || !validation) return null;
  const occupancyPct = Math.round((validation.occupancy ?? 0) * 100);
  const reasons = invalidBaseReasons(validation);
  return (
    <details className="debug-panel base-composition-debug">
      <summary>{title}</summary>
      {reasons.length ? (
        <ul className="quality-warnings invalid-base">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : (
        <p className="hint">Valid full-body candidate.</p>
      )}
      <dl>
        <div>
          <dt>composition score</dt>
          <dd>{validation.compositionScore ?? validation.score ?? "—"}</dd>
        </div>
        <div>
          <dt>valid for base</dt>
          <dd>{validation.validForBase === false ? "no" : "yes"}</dd>
        </div>
        <div>
          <dt>bounding box</dt>
          <dd>
            {validation.bboxLeft ?? 0},{validation.bboxTop ?? 0} → {validation.bboxRight ?? 0},{validation.bboxBottom ?? 0}
          </dd>
        </div>
        <div>
          <dt>canvas occupied</dt>
          <dd>{occupancyPct}%</dd>
        </div>
        <div>
          <dt>touches edges</dt>
          <dd>
            {[
              validation.touchesTop ? "top" : null,
              validation.touchesBottom ? "bottom" : null,
              validation.touchesLeft ? "left" : null,
              validation.touchesRight ? "right" : null,
            ]
              .filter(Boolean)
              .join(", ") || "none"}
          </dd>
        </div>
        <div>
          <dt>portrait rule</dt>
          <dd>{validation.portraitFailed ? "failed" : "passed"}</dd>
        </div>
        <div>
          <dt>crop rule</dt>
          <dd>{validation.cropFailed ? "failed" : "passed"}</dd>
        </div>
        <div>
          <dt>full-body rule</dt>
          <dd>{validation.fullBodyFailed ? "failed" : "passed"}</dd>
        </div>
        <div>
          <dt>auto-retry</dt>
          <dd>
            {debug?.retryTriggered || validation.retryTriggered ? "triggered" : "no"}
            {debug?.cropRetries ? ` (${debug.cropRetries})` : ""}
          </dd>
        </div>
      </dl>
    </details>
  );
}
