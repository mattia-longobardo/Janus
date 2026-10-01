import clsx from "clsx";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export const inputClass =
  "h-11 w-full rounded-lg border border-line2 bg-bg px-3 text-[15px] text-text outline-none focus:border-accent";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("rounded-2xl border border-line bg-card", className)} {...props} />;
}

const VARIANTS = {
  primary: "border-accent bg-accent text-accent-ink font-semibold",
  secondary: "border-line2 bg-card text-text",
  danger: "border-line2 bg-card text-bad",
  ghost: "border-transparent bg-transparent text-muted hover:text-text",
} as const;

export function Button({
  variant = "secondary",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof VARIANTS }) {
  return (
    <button
      type={type}
      className={clsx(
        "inline-flex h-11 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

export function StatusDot({ online }: { online: boolean }) {
  return <span aria-hidden className={clsx("inline-block size-2 shrink-0 rounded-full", online ? "bg-ok" : "bg-off")} />;
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "accent" | "bad" | "ok"; children: ReactNode }) {
  const tones = {
    neutral: "border-line2 text-muted",
    accent: "border-accent-line text-accent-text",
    bad: "border-bad text-bad",
    ok: "border-ok text-ok",
  };
  return <span className={clsx("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium", tones[tone])}>{children}</span>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        <h1 className="font-display text-3xl font-bold tracking-tight lg:text-4xl">{title}</h1>
        {subtitle && <p className="font-mono text-[13px] text-faint">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </header>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="font-display text-xl font-bold">{children}</h2>;
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-2">
        <span className="text-[13px] font-medium text-text2">{label}</span>
        {children}
      </label>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "success"; children: ReactNode }) {
  const tones = { info: "border-line2 text-text2", error: "border-bad text-bad", success: "border-ok text-ok" };
  return (
    <p role={tone === "error" ? "alert" : "status"} className={clsx("mb-4 rounded-lg border bg-card px-3 py-2 text-sm", tones[tone])}>
      {children}
    </p>
  );
}
