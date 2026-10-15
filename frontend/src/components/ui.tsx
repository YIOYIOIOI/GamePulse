import { CircleHelp, LoaderCircle } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import type { Tone } from "../format";

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
  flush = false,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Lets a table run edge to edge under the header. */
  flush?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {description && <p>{description}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={flush ? "card-body flush" : "card-body"}>{children}</div>
    </section>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: Tone | "info" | "warn";
  children: ReactNode;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Hint({ children }: { children: ReactNode }) {
  return (
    <span className="hint" tabIndex={0}>
      <CircleHelp size={13} aria-hidden />
      <span className="hint-text" role="tooltip">
        {children}
      </span>
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="spinner">
      <LoaderCircle size={16} className="spin" aria-hidden />
      {label}
    </span>
  );
}

export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  width = 520,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  useEscape(onClose);
  return (
    <div className="overlay" onMouseDown={onClose}>
      <section
        className="modal"
        style={{ width }}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="modal-head">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </section>
    </div>
  );
}

export function Drawer({
  title,
  subtitle,
  onClose,
  children,
  width = 560,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  width?: number;
}) {
  useEscape(onClose);
  return (
    <div className="overlay drawer-overlay" onMouseDown={onClose}>
      <aside
        className="drawer"
        style={{ width }}
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}

function useEscape(onClose: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
}

/** A labelled number for metric strips. */
export function Stat({
  label,
  value,
  hint,
  children,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="stat">
      <div className="stat-label">
        {label}
        {hint && <Hint>{hint}</Hint>}
      </div>
      <div className="stat-value">{value}</div>
      {children && <div className="stat-note">{children}</div>}
    </div>
  );
}

/** "+1.2" in red when worse, green when better; the not-recommended rate going up is worse. */
export function Delta({
  value,
  unit = "",
}: {
  value: number | null | undefined;
  unit?: string;
}) {
  if (value == null) return <span className="delta">—</span>;
  const text =
    (value > 0 ? "+" : value < 0 ? "−" : "") +
    Math.abs(value * 100).toFixed(1) +
    unit;
  return (
    <span
      className={`delta ${value > 0.0005 ? "up" : value < -0.0005 ? "down" : ""}`}
    >
      {text}
    </span>
  );
}
