import { useId } from "react";

const sizes = {
  sm: { wrap: 28, pad: 6, title: "1rem", tag: "0.65rem" },
  md: { wrap: 36, pad: 8, title: "1.15rem", tag: "0.72rem" },
  lg: { wrap: 48, pad: 10, title: "1.35rem", tag: "0.8rem" },
};

/** Inline SVG mark: branching path + nodes + spark. No external assets. */
function MarkGlyph({ size, gid }) {
  const s = sizes[size] || sizes.md;
  const w = s.wrap;
  const h = s.wrap;
  const g1 = `brandGrad-${gid}`;
  const g2 = `brandGrad2-${gid}`;
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="brand-logo-mark"
    >
      <path
        d="M8 36 L8 24 Q8 18 14 16 L22 14 Q28 12 32 8"
        stroke={`url(#${g1})`}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M8 24 L8 12 Q8 8 14 10 L24 12"
        stroke={`url(#${g2})`}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
      <circle cx="8" cy="36" r="3.5" fill="var(--primary, #4f46e5)" />
      <circle cx="32" cy="8" r="3.2" fill="var(--secondary, #0d9488)" />
      <circle cx="24" cy="12" r="2.6" fill="#6366f1" />
      <path
        d="M38 6 l1.8 3.6 4 0.5-3 2.6 0.9 3.9-3.5-2.1-3.5 2.1 0.9-3.9-3-2.6 4-0.5z"
        fill="var(--accent, #d97706)"
        opacity="0.95"
      />
      <defs>
        <linearGradient id={g1} x1="8" y1="36" x2="32" y2="8" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#0d9488" />
        </linearGradient>
        <linearGradient id={g2} x1="8" y1="24" x2="28" y2="10" gradientUnits="userSpaceOnUse">
          <stop stopColor="#818cf8" />
          <stop offset="1" stopColor="#5eead4" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/**
 * @param {{ size?: "sm" | "md" | "lg"; showText?: boolean }} props
 */
export default function BrandLogo({ size = "md", showText = true }) {
  const gid = useId().replace(/:/g, "");
  const s = sizes[size] || sizes.md;
  return (
    <div className="brand-logo" style={{ gap: showText ? s.pad : 0 }}>
      <MarkGlyph size={size} gid={gid} />
      {showText ? (
        <div className="brand-logo-text">
          <span className="brand-logo-title" style={{ fontSize: s.title }}>
            Psychometric Insights
          </span>
          <span className="brand-logo-tagline" style={{ fontSize: s.tag }}>
            Adaptive stories. Explainable insights.
          </span>
        </div>
      ) : null}
    </div>
  );
}
