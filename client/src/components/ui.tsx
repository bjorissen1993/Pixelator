import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { assetUrl } from "../asset";

export function Button({
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
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

export function PixelImage({
  path,
  cacheKey,
  scale = 8,
  size,
  alt = "sprite",
}: {
  path?: string | null;
  cacheKey?: string | number | null;
  scale?: number;
  size?: number;
  alt?: string;
}) {
  if (!path) return <div className="pixel-empty">No sprite</div>;
  const dim = size ? size * scale : undefined;
  return (
    <img
      src={assetUrl(path, cacheKey)}
      alt={alt}
      className="pixel"
      style={dim ? { width: dim, height: dim } : undefined}
    />
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
