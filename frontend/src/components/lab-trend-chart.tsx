import { cn } from "@/lib/utils";
import type { LabPoint } from "@/lib/types";

/**
 * Figma: `chart` (node 20:177) — reference-range band, dashed guides, a
 * connecting line and one marker per result. Drawn as inline SVG so it scales
 * with the panel; no charting dependency is needed for this shape.
 *
 * The band and line stretch with the container (`preserveAspectRatio="none"`),
 * so the markers are rendered as positioned elements on top to stay circular.
 */
export function LabTrendChart({
  points,
  referenceLow,
  referenceHigh,
  outOfRange,
  height = 132,
  className,
}: {
  points: LabPoint[];
  referenceLow: number;
  referenceHigh: number;
  /** Colours the line and markers red when the latest value breaches the range. */
  outOfRange?: boolean;
  height?: number;
  className?: string;
}) {
  const values = points.map((point) => point.value);
  const min = Math.min(...values, referenceLow) - 1;
  const max = Math.max(...values, referenceHigh) + 1;
  const span = max - min || 1;

  const left = 4;
  const right = 96;
  const step = points.length > 1 ? (right - left) / (points.length - 1) : 0;

  const x = (index: number) => left + step * index;
  const y = (value: number) => ((max - value) / span) * 100;

  const stroke = outOfRange ? "var(--risk-high)" : "var(--brand-700)";

  return (
    <div className={cn("relative w-full", className)} style={{ height }}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Trend from ${points[0]?.date} to ${points.at(-1)?.date}`}
        className="absolute inset-0 size-full"
      >
        <rect
          x={left}
          y={y(referenceHigh)}
          width={right - left}
          height={Math.max(0, y(referenceLow) - y(referenceHigh))}
          fill="var(--status-ok-bg)"
        />
        {[referenceHigh, referenceLow].map((value) => (
          <line
            key={value}
            x1={left}
            x2={right}
            y1={y(value)}
            y2={y(value)}
            stroke="var(--status-ok)"
            strokeWidth={0.4}
            strokeDasharray="2 2"
            vectorEffect="non-scaling-stroke"
            opacity={0.55}
          />
        ))}
        <line
          x1={left}
          x2={right}
          y1={100}
          y2={100}
          stroke="var(--neutral-200)"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
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
              backgroundColor: last && outOfRange ? stroke : "var(--neutral-0)",
            }}
            className="absolute size-[9px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
          />
        );
      })}
    </div>
  );
}
