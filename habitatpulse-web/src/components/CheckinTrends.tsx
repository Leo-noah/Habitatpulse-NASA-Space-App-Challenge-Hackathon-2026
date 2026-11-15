import { useMemo } from "react";
import type { DemoRecord } from "./DemoCheckin";

type CheckinTrendsProps = {
  records: DemoRecord[];
  onNewCheckin: () => void;
};

type MetricKey = "wellbeing" | "mood" | "sleep" | "fluid";

type ChartRow = {
  time: string;
  wellbeing: number | null;
  mood: number | null;
  sleep: number | null;
  fluid: number | null;
};

type Series = {
  key: MetricKey;
  label: string;
  rangeLabel: string;
  color: string;
  minimum: number;
  maximum: number;
};

const SERIES: Series[] = [
  {
    key: "wellbeing",
    label: "Wellbeing",
    rangeLabel: "1–5",
    color: "#16b8a6",
    minimum: 1,
    maximum: 5,
  },
  {
    key: "mood",
    label: "Mood / stress",
    rangeLabel: "1–5",
    color: "#5966f2",
    minimum: 1,
    maximum: 5,
  },
  {
    key: "sleep",
    label: "Sleep",
    rangeLabel: "0–12 h",
    color: "#f59a23",
    minimum: 0,
    maximum: 12,
  },
  {
    key: "fluid",
    label: "Fluid intake",
    rangeLabel: "0–3000 ml",
    color: "#ec4c9a",
    minimum: 0,
    maximum: 3000,
  },
];

function formatTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  return date.toLocaleString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function numericValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export default function CheckinTrends({
  records,
  onNewCheckin,
}: CheckinTrendsProps) {
  const orderedRecords = useMemo(() => {
    return [...records]
      .filter((record) => Number.isFinite(new Date(record.time).getTime()))
      .sort(
        (first, second) =>
          new Date(first.time).getTime() - new Date(second.time).getTime(),
      );
  }, [records]);

  const latest = orderedRecords.length
    ? orderedRecords[orderedRecords.length - 1]
    : null;

  const chart = useMemo(() => {
    /*
      Use the latest check-in as the end of the graph.
      The chart then includes only the seven days before it.
    */
    const newestTime = latest ? new Date(latest.time).getTime() : 0;
    const sevenDaysInMilliseconds = 7 * 24 * 60 * 60 * 1000;
    const startTime = newestTime - sevenDaysInMilliseconds;

    const rows: ChartRow[] = orderedRecords
      .filter((record) => {
        const recordTime = new Date(record.time).getTime();

        return recordTime >= startTime && recordTime <= newestTime;
      })
      .slice(-300)
      .map((record) => ({
        time: record.time,
        wellbeing: numericValue(record.wellbeing),
        mood: numericValue(record.mood),
        sleep: numericValue(record.sleep),
        fluid: numericValue(record.fluid),
      }));

    const width = 760;
    const height = 310;
    const left = 72;
    const right = 32;
    const top = 28;
    const bottom = 55;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;

    function pointFor(
      value: number,
      index: number,
      series: Series,
      total: number,
    ) {
      const x = left + (index * plotWidth) / Math.max(total - 1, 1);

      const normalized =
        ((value - series.minimum) / (series.maximum - series.minimum)) * 100;

      const safeValue = Math.max(0, Math.min(100, normalized));
      const y = top + plotHeight - (safeValue / 100) * plotHeight;

      return { x, y };
    }

    function lineFor(series: Series) {
      let path = "";
      let connected = false;

      rows.forEach((row, index) => {
        const value = row[series.key];

        if (value === null) {
          connected = false;
          return;
        }

        const point = pointFor(value, index, series, rows.length);

        path += `${connected ? "L" : "M"} ${point.x.toFixed(1)} ${point.y.toFixed(1)} `;
        connected = true;
      });

      return path.trim();
    }

    return {
      rows,
      width,
      height,
      left,
      top,
      plotWidth,
      plotHeight,
      lines: SERIES.map((series) => ({
        ...series,
        path: lineFor(series),
      })),
    };
  }, [orderedRecords, latest]);

  return (
    <section className="glass-trends" aria-label="Crew check-in history">
      <div className="trends-top">
        <div>
          <span className="trends-eyebrow">CREW HEALTH · HISTORY</span>
          <h3>Health at a glance</h3>
          <p>Check-ins loaded from the local MySQL database.</p>
        </div>
      </div>

      <div className="trends-stats">
        <div>
          <small>Total check-ins</small>
          <strong>{orderedRecords.length}</strong>
          <span>Stored database records</span>
        </div>

        <div>
          <small>Latest wellbeing</small>
          <strong>{latest?.wellbeing ?? "—"}</strong>
          <span>{latest ? "Latest recorded value" : "No check-in yet"}</span>
        </div>

        <div>
          <small>Latest entry</small>
          <strong className="stat-date">
            {latest ? formatTime(latest.time) : "Not recorded"}
          </strong>
          <span>Local MySQL database</span>
        </div>
      </div>

      <div className="trends-chart-header">
        <div>
          <h4>Crew wellbeing trend — last 7 days</h4>
          <p>
            Four health indicators are normalized to a shared 0–100 scale for
            visual comparison.
          </p>
        </div>
      </div>

      <div
        aria-label="Chart colour legend"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "14px",
          margin: "16px 0 18px",
        }}
      >
        {SERIES.map((series) => (
          <span
            key={series.key}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 12px",
              border: "1px solid #d2e3eb",
              borderRadius: "10px",
              background: "#ffffff",
              color: "#173d59",
              fontSize: "13px",
              fontWeight: 700,
            }}
          >
            <i
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: "24px",
                height: "3px",
                borderRadius: "99px",
                background: series.color,
              }}
            />

            {series.label}

            <small style={{ color: "#66859a", fontWeight: 600 }}>
              ({series.rangeLabel})
            </small>
          </span>
        ))}
      </div>

      {chart.rows.length === 0 ? (
        <div className="trends-empty">
          <span aria-hidden="true">⌁</span>
          <strong>No check-in history during the latest 7 days</strong>
          <p>Complete the crew check-in form to build a health trend.</p>

          <button type="button" onClick={onNewCheckin}>
            Start check-in
          </button>
        </div>
      ) : (
        <div className="trends-plot">
          <svg
            className="combined-health-chart"
            viewBox={`0 0 ${chart.width} ${chart.height}`}
            role="img"
            aria-label="Combined crew wellbeing, mood, sleep, and fluid intake trend for the latest seven days"
          >
            {[0, 25, 50, 75, 100].map((percentage) => {
              const y =
                chart.top +
                chart.plotHeight -
                (percentage / 100) * chart.plotHeight;

              return (
                <g key={percentage}>
                  <line
                    className="grid-line"
                    x1={chart.left}
                    y1={y}
                    x2={chart.left + chart.plotWidth}
                    y2={y}
                  />

                  <text
                    className="tick-label"
                    x={chart.left - 12}
                    y={y + 4}
                    textAnchor="end"
                  >
                    {percentage}%
                  </text>
                </g>
              );
            })}

            <line
              className="axis-line"
              x1={chart.left}
              y1={chart.top}
              x2={chart.left}
              y2={chart.top + chart.plotHeight}
            />

            <line
              className="axis-line"
              x1={chart.left}
              y1={chart.top + chart.plotHeight}
              x2={chart.left + chart.plotWidth}
              y2={chart.top + chart.plotHeight}
            />

            <text
              className="axis-title"
              x="18"
              y={chart.top + chart.plotHeight / 2}
              textAnchor="middle"
              transform={`rotate(-90 18 ${chart.top + chart.plotHeight / 2})`}
            >
              Relative level (%)
            </text>

            <text
              className="axis-title"
              x={chart.left + chart.plotWidth / 2}
              y={chart.height - 12}
              textAnchor="middle"
            >
              Check-in time
            </text>

            {chart.lines.map((series) =>
              series.path ? (
                <path
                  key={series.key}
                  d={series.path}
                  fill="none"
                  stroke={series.color}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null,
            )}
          </svg>

          <div className="trends-plot-footer">
            <span>{formatTime(chart.rows[0].time)}</span>
            <span>
              {formatTime(chart.rows[chart.rows.length - 1].time)}
            </span>
          </div>
        </div>
      )}

      <p className="trends-disclaimer">
        Prototype display only. It does not diagnose illness or replace human
        medical review.
      </p>
    </section>
  );
}