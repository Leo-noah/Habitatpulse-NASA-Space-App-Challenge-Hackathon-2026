import { useEffect, useMemo, useState } from "react";
import CheckinTrends from "./CheckinTrends";
import type { DemoRecord } from "./DemoCheckin";

type OverviewProps = {
  records?: DemoRecord[];
  onOpenCheckin: () => void;
  onOpenEnvironment: () => void;
  onOpenEvidence: () => void;
  onOpenReports: () => void;
};

type EnvironmentPoint = {
  observed_at_utc: string;
  co2_ppm: number | null;
  temperature_c: number | null;
  humidity_percent: number | null;
};

type EnvironmentResponse = {
  series?: EnvironmentPoint[];
};

const ENV_API = "http://127.0.0.1:8000/api/v1/environment/dashboard";

function formatTime(value?: string) {
  if (!value) return "Not recorded";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalisedPoints(values: Array<number | null>) {
  const width = 900;
  const height = 240;
  const left = 52;
  const right = 20;
  const top = 18;
  const bottom = 38;

  const numbers = values.filter(
    (value): value is number => typeof value === "number",
  );

  if (numbers.length === 0) return "";

  const minimum = Math.min(...numbers);
  const maximum = Math.max(...numbers);
  const range = Math.max(maximum - minimum, 1);

  return values
    .map((value, index) => {
      if (value === null) return "";

      const x =
        left +
        (index * (width - left - right)) / Math.max(values.length - 1, 1);

      const percentage = ((value - minimum) / range) * 100;

      const y =
        top + ((100 - percentage) * (height - top - bottom)) / 100;

      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function EnvironmentOverviewGraph() {
  const [points, setPoints] = useState<EnvironmentPoint[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadEnvironment() {
      try {
        const response = await fetch(
          `${ENV_API}?module=all&window=7d&limit=3000`,
        );

        if (!response.ok) {
          throw new Error("Could not load habitat records.");
        }

        const payload = (await response.json()) as EnvironmentResponse;

        if (!cancelled) {
          setPoints(payload.series ?? []);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setError(
            "Environment graph is unavailable. Start environment_api.py.",
          );
        }
      }
    }

    void loadEnvironment();

    return () => {
      cancelled = true;
    };
  }, []);

  const chartPoints = useMemo(() => {
    const stride = Math.max(1, Math.ceil(points.length / 700));

    return points.filter(
      (_, index) =>
        index % stride === 0 || index === points.length - 1,
    );
  }, [points]);

  const co2 = chartPoints.map((point) => point.co2_ppm);
  const temperature = chartPoints.map((point) => point.temperature_c);
  const humidity = chartPoints.map((point) => point.humidity_percent);

  const hasData = chartPoints.some(
    (point) =>
      point.co2_ppm !== null ||
      point.temperature_c !== null ||
      point.humidity_percent !== null,
  );

  return (
    <section className="overview-environment-trends">
      <div className="overview-environment-heading">
        <div>
          <span className="trends-eyebrow">HABITAT CONDITIONS · 7 DAYS</span>
          <h3>Environment at a glance</h3>
          <p>
            CO₂, temperature, and relative humidity from the local MySQL
            database.
          </p>
        </div>

        
      </div>

      <div
        className="overview-environment-legend"
        aria-label="Environment graph colour legend"
      >
        <span>
          <i className="legend-co2" />
          <strong>CO₂</strong>
          <small>parts per million (ppm)</small>
        </span>

        <span>
          <i className="legend-temperature" />
          <strong>Temperature</strong>
          <small>degrees Celsius (°C)</small>
        </span>

        <span>
          <i className="legend-humidity" />
          <strong>Relative humidity</strong>
          <small>percentage (%)</small>
        </span>
      </div>

      {error ? (
        <p className="overview-environment-error">{error}</p>
      ) : !hasData ? (
        <div className="overview-environment-empty">
          No stored environment data is available.
        </div>
      ) : (
        <>
          <svg
            className="overview-environment-chart"
            viewBox="0 0 900 240"
            role="img"
            aria-label="Environment trends for carbon dioxide, temperature, and humidity"
          >
            {[0, 25, 50, 75, 100].map((value) => {
              const y = 18 + ((100 - value) * (240 - 18 - 38)) / 100;

              return (
                <g key={value}>
                  <line
                    x1="52"
                    x2="880"
                    y1={y}
                    y2={y}
                    className="overview-grid-line"
                  />
                  <text x="8" y={y + 4} className="overview-axis-label">
                    {value}%
                  </text>
                </g>
              );
            })}

            <line
              x1="52"
              y1="18"
              x2="52"
              y2="202"
              className="overview-axis-line"
            />

            <line
              x1="52"
              y1="202"
              x2="880"
              y2="202"
              className="overview-axis-line"
            />

            <polyline
              points={normalisedPoints(co2)}
              fill="none"
              stroke="#16b9d4"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <polyline
              points={normalisedPoints(temperature)}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <polyline
              points={normalisedPoints(humidity)}
              fill="none"
              stroke="#19b985"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <text
              x="450"
              y="228"
              textAnchor="middle"
              className="overview-axis-label"
            >
              Time — oldest to newest
            </text>
          </svg>

          <div className="overview-environment-times">
            <span>{formatTime(chartPoints[0]?.observed_at_utc)}</span>
            <span>
              {formatTime(
                chartPoints[chartPoints.length - 1]?.observed_at_utc,
              )}
            </span>
          </div>

          <p className="overview-environment-note">
            Each colour is normalised separately to a 0–100% visual scale so
            the three different units can be compared visually.
          </p>
        </>
      )}
    </section>
  );
}

export default function Overview({
  records = [],
  onOpenCheckin,
  onOpenEnvironment,
  onOpenEvidence,
  onOpenReports,
}: OverviewProps) {
  const latest = records.length > 0 ? records[records.length - 1] : null;

  return (
    <section className="overview-page">
      <div className="welcome">
        <span className="eyebrow">YOUR WORKSPACE</span>
        <h2>Mission overview</h2>
        <p>
          Review crew wellbeing, create a health check-in, and explore habitat
          environment records.
        </p>
      </div>

      <section className="overview-basic">
        <span className="eyebrow">CURRENT STATUS</span>
        <h3>Crew health summary</h3>

        <div className="demo-context">
          <div>
            <small>Latest check-in</small>
            <strong>
              {latest
                ? new Date(latest.time).toLocaleString()
                : "No check-in recorded"}
            </strong>
          </div>

          <div>
            <small>Latest wellbeing</small>
            <strong>
              {latest?.wellbeing !== null &&
              latest?.wellbeing !== undefined
                ? `${latest.wellbeing} / 5`
                : "Not recorded"}
            </strong>
          </div>

          <div>
            <small>Reported symptoms</small>
            <strong>
              {latest?.symptoms?.length
                ? latest.symptoms.join(", ")
                : "None recorded"}
            </strong>
          </div>

          <div>
            <small>System mode</small>
            <strong>Local MySQL database</strong>
          </div>
        </div>

        <p>
          Health records are prototype data. This interface does not diagnose
          illness or replace human medical review.
        </p>
      </section>

      <CheckinTrends records={records} onNewCheckin={onOpenCheckin} />

      <EnvironmentOverviewGraph />

      <div className="overview-cards">
        <button
          type="button"
          className="overview-card"
          onClick={onOpenCheckin}
        >
          <span className="card-icon">♡</span>
          <span className="card-kicker">CREW WELLBEING</span>
          <strong>Crew check-in</strong>
          <span>
            Record vitals, wellbeing, sleep, symptoms, and safety-review
            answers.
          </span>
          <em>Start check-in →</em>
        </button>

        <button
          type="button"
          className="overview-card"
          onClick={onOpenEnvironment}
        >
          <span className="card-icon">◉</span>
          <span className="card-kicker">HABITAT INTELLIGENCE</span>
          <strong>Environment dashboard</strong>
          <span>
            View stored temperature, humidity, CO₂, and anomaly-screening
            records.
          </span>
          <em>Open environment →</em>
        </button>

        <button
          type="button"
          className="overview-card"
          onClick={onOpenEvidence}
        >
          <span className="card-icon">▤</span>
          <span className="card-kicker">MEDICAL EVIDENCE</span>
          <strong>Evidence review</strong>
          <span>
            Combine crew check-ins with habitat context for transparent human
            medical review.
          </span>
          <em>Open evidence →</em>
        </button>

        <button
          type="button"
          className="overview-card"
          onClick={onOpenReports}
        >
          <span className="card-icon">▥</span>
          <span className="card-kicker">MISSION REPORTS</span>
          <strong>Crew reports</strong>
          <span>
            Review printable crew health, environment trends, and Ground
            Medical handover notes.
          </span>
          <em>Open reports →</em>
        </button>
      </div>

      <div className="overview-footnote">
        ⓘ Prototype only · Historical and simulated records must remain clearly
        labelled.
      </div>
    </section>
  );
}