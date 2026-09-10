import { useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import type { ApiErrorPayload, GenerationProgress, SpriteAsset } from "@shared";
import { previewSrc } from "../asset";

export function Button({
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" | "remove" }) {
  return <button className={`btn ${variant}`} {...props} />;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}

export function Area(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} />;
}

export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function PipelineSteps({ progress }: { progress?: GenerationProgress | null }) {
  const steps = progress?.steps ?? [];
  if (!steps.length) return null;
  return (
    <ol className="pipeline-steps">
      {steps.map((step, index) => {
        const state = index < (progress?.stepIndex ?? 0) ? "done" : index === (progress?.stepIndex ?? 0) ? "current" : "";
        return (
          <li key={step} className={state}>
            {step}
          </li>
        );
      })}
    </ol>
  );
}

export function PixelImage({
  asset,
  path,
  previewPath,
  cacheKey,
  scale = 8,
  size,
  alt = "sprite",
  empty = "No sprite",
}: {
  asset?: SpriteAsset | null;
  path?: string | null;
  previewPath?: string | null;
  cacheKey?: string | number | null;
  scale?: number;
  size?: number;
  alt?: string;
  empty?: string;
}) {
  const [failed, setFailed] = useState(false);
  const resolved = previewSrc(
    asset ?? {
      path: path ?? "",
      previewPath: previewPath ?? "",
      createdAt: cacheKey ? String(cacheKey) : "",
    },
  );
  useEffect(() => setFailed(false), [resolved]);
  if (!resolved || failed) return <div className="pixel-empty">{empty}</div>;
  const dim = size ? size * scale : undefined;
  return (
    <img
      src={resolved}
      alt={alt}
      className="pixel"
      style={dim ? { width: dim, height: dim } : undefined}
      onError={() => setFailed(true)}
    />
  );
}

export function GenerationStatus({
  busy,
  generating,
  progress,
  error,
}: {
  busy?: string;
  generating?: boolean;
  progress?: GenerationProgress | null;
  error?: ApiErrorPayload | string | null;
}) {
  if (!error && !busy && !generating) return null;
  if (error) {
    const payload = typeof error === "string" ? { message: error } : error;
    return (
      <div className="banner error" role="alert">
        <strong>{payload.message}</strong>
        {payload.traceId ? <p className="hint">Trace {payload.traceId}</p> : null}
        {payload.context && Object.keys(payload.context).length ? (
          <p className="hint">
            {Object.entries(payload.context)
              .map(([key, value]) => `${key}: ${value}`)
              .join(" · ")}
          </p>
        ) : null}
        {payload.details ? (
          <details className="error-details">
            <summary>Technical details</summary>
            <pre>{payload.details}</pre>
          </details>
        ) : null}
      </div>
    );
  }
  const current = progress?.step || busy || "Working…";
  return (
    <div className="banner busy generation-status" aria-live="polite">
      <Spinner />
      <div>
        <strong>{progress?.label || busy}</strong>
        <p>
          {current}
          {progress?.total ? ` · ${progress.current ?? 0}/${progress.total}` : ""}
        </p>
        {generating && <PipelineSteps progress={progress} />}
      </div>
    </div>
  );
}

export function SpritePreviewCard({
  title,
  empty,
  asset,
  loading,
  progress,
  actions,
}: {
  title: string;
  empty: string;
  asset?: SpriteAsset | null;
  loading?: boolean;
  progress?: GenerationProgress | null;
  actions: ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  const src = previewSrc(asset);
  useEffect(() => setFailed(false), [src]);
  const showImage = Boolean(src) && !failed;
  const size = Math.max(192, (asset?.width || 48) * 8);
  return (
    <article className="sprite-card">
      <header>
        <h3>{title}</h3>
        {asset && !failed ? (
          <span className="sprite-meta">
            {asset.width}×{asset.height} preview
          </span>
        ) : null}
      </header>
      <div className={`sprite-stage ${loading ? "is-loading" : ""}`}>
        {showImage ? (
          <img
            src={src}
            alt={title}
            className="pixel sprite-preview"
            style={{ width: size, height: size }}
            onError={() => setFailed(true)}
          />
        ) : loading ? null : (
          <div className="pixel-empty sprite-empty">{empty}</div>
        )}
        {loading ? (
          <div className="sprite-loading" aria-live="polite">
            <Spinner />
            <strong>{progress?.label || "Generating…"}</strong>
            <span>{progress?.step || "Generating sprite"}</span>
            <PipelineSteps progress={progress} />
          </div>
        ) : null}
      </div>
      <footer className="chip-row">{actions}</footer>
    </article>
  );
}

export function Banner({ error, busy }: { error?: string; busy?: string }) {
  if (!error && !busy) return null;
  return <div className={`banner ${error ? "error" : "busy"}`}>{error || busy}</div>;
}

export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="block">
      <header className="block-head">
        <h2>{title}</h2>
        {actions}
      </header>
      {children}
    </section>
  );
}
