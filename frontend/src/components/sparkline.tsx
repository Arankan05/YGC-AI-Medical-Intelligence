import { cn } from "@/lib/utils";
import type { LabPoint } from "@/lib/types";

const STROKE = {
  ok: "var(--status-ok)",
  medium: "var(--risk-med)",
  high: "var(--risk-high)",
} as const;

/**
 * Figma: `sparkline` inside a trend card (node 27:691) — a 48px line with a
 * marker per test. The line stretches with the card; markers are positioned on
 * top so they stay circular.
 */
export function Sparkline({
  points,
  severity,
  className,
}: {
  points: LabPoint[];
  severity: "ok" | "medium" | "high";
  className?: string;
}) {
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = points.length > 1 ? 92 / (points.length - 1) : 0;

  const x = (index: number) => 4 + step * index;
  const y = (value: number) => 15 + ((max - value) / span) * 70;
  const stroke = STROKE[severity];

  return (
    <div className={cn("relative h-12 w-full", className)}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden
        className="absolute inset-0 size-full"
      >
        <polyline
          points={points
            .map((point, index) => `${x(index)},${y(point.value)}`)
            .join(" ")}
          fill="none"
          stroke={stroke}
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {points.map((point, index) => {
        const last = index === points.length - 1;
        return (
          <span
            key={point.date}
            title={`${point.date}: ${point.value}`}
            style={{
              left: `${x(index)}%`,
              top: `${y(point.value)}%`,
              borderColor: stroke,
              backgroundColor: last ? stroke : "var(--neutral-0)",
            }}
            className={cn(
              "absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2",
              last ? "size-[11px]" : "size-[9px]"
            )}
          />
        );
      })}
    </div>
  );
}
