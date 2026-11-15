import { useEffect, useMemo, useState } from "react";
import "./GroundDashboard.css";
import {
  getGroundReports,
  type GroundHandoverReport,
} from "./groundHandover";

type GroundDashboardProps = {
  onSignOut: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
};

type ReviewStatus = "Awaiting review" | "In review" | "Reviewed";

type Checkin = {
  id: string;
  crewId: string;
  time: string;
  wellbeing: number | null;
  mood: number | null;
  sleep: number | null;
  fluid: number | null;
  symptoms: string[];
  urgent: boolean;
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

type ChartLine = {
  label: string;
  color: string;
  meaning: string;
  values: Array<number | null>;
};

const HEALTH_API = "http://127.0.0.1:8000/api/v1/health/checkins";
const ENVIRONMENT_API =
  "http://127.0.0.1:8000/api/v1/environment/dashboard";

function formatDate(value?: string) {
  if (!value) return "Not recorded";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValue(
  value: number | null | undefined,
  suffix = "",
  fallback = "—",
) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }

  return `${value.toLocaleString()}${suffix}`;
}

function lastSevenCheckinDays(rows: Checkin[]) {
  if (rows.length === 0) return [];

  const newestTime = new Date(rows[rows.length - 1].time).getTime();
  const cutoff = newestTime - 7 * 24 * 60 * 60 * 1000;

  return rows.filter((row) => new Date(row.time).getTime() >= cutoff);
}

function normalizedPoints(
  values: Array<number | null>,
  width = 820,
  height = 230,
) {
  const left = 50;
  const right = 20;
  const top = 18;
  const bottom = 35;

  const actual = values.filter(
    (value): value is number =>
      typeof value === "number" && Number.isFinite(value),
  );

  if (actual.length === 0) return "";

  const minimum = Math.min(...actual);
  const maximum = Math.max(...actual);
  const range = Math.max(maximum - minimum, 1);

  return values
    .map((value, index) => {
      if (value === null || !Number.isFinite(value)) return "";

      const x =
        left + (index * (width - left - right)) / Math.max(values.length - 1, 1);

      const normalized = ((value - minimum) / range) * 100;
      const y = top + ((100 - normalized) * (height - top - bottom)) / 100;

      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function GroundChart({
  title,
  description,
  lines,
  start,
  end,
}: {
  title: string;
  description: string;
  lines: ChartLine[];
  start?: string;
  end?: string;
}) {
  const hasData = lines.some((line) =>
    line.values.some((value) => value !== null),
  );

  return (
    <section className="ground-chart-card">
      <header className="ground-chart-heading">
        <h3>{title}</h3>
        <p>{description}</p>
      </header>

      <div className="ground-chart-legend">
        {lines.map((line) => (
          <span key={line.label}>
            <i style={{ background: line.color }} />
            <strong>{line.label}</strong>
            <small>{line.meaning}</small>
          </span>
        ))}
      </div>

      {!hasData ? (
        <p className="ground-no-data">
          No database values are available for this graph.
        </p>
      ) : (
        <>
          <svg
            className="ground-line-chart"
            viewBox="0 0 820 230"
            role="img"
            aria-label={title}
          >
            {[0, 25, 50, 75, 100].map((value) => {
              const y = 18 + ((100 - value) * (230 - 18 - 35)) / 100;

              return (
                <g key={value}>
                  <line
                    x1="50"
                    x2="800"
                    y1={y}
                    y2={y}
                    className="ground-grid-line"
                  />
                  <text x="11" y={y + 4} className="ground-axis-text">
                    {value}%
                  </text>
                </g>
              );
            })}

            <line
              x1="50"
              y1="18"
              x2="50"
              y2="195"
              className="ground-axis-line"
            />

            <line
              x1="50"
              y1="195"
              x2="800"
              y2="195"
              className="ground-axis-line"
            />

            {lines.map((line) =>
              normalizedPoints(line.values) ? (
                <polyline
                  key={line.label}
                  points={normalizedPoints(line.values)}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null,
            )}

            <text
              x="425"
              y="220"
              textAnchor="middle"
              className="ground-axis-text"
            >
              Time — oldest to newest
            </text>
          </svg>

          <div className="ground-chart-date">
            <span>{formatDate(start)}</span>
            <span>{formatDate(end)}</span>
          </div>

          <p className="ground-normalized-note">
            Each line uses its own 0–100% visual scale. Read the legend for the
            actual unit and meaning.
          </p>
        </>
      )}
    </section>
  );
}

export default function GroundDashboard({
  onSignOut,
  theme,
  onToggleTheme,
}: GroundDashboardProps) {
  const [reports, setReports] = useState<GroundHandoverReport[]>(
    getGroundReports,
  );
  const [selectedReportId, setSelectedReportId] = useState("");
  const [checkins, setCheckins] = useState<Checkin[]>([]);
  const [environmentWeek, setEnvironmentWeek] = useState<EnvironmentPoint[]>(
    [],
  );
  const [environmentAll, setEnvironmentAll] = useState<EnvironmentPoint[]>([]);
  const [replyByReport, setReplyByReport] = useState<Record<string, string>>(
    {},
  );
  const [statusByReport, setStatusByReport] = useState<
    Record<string, ReviewStatus>
  >({});
  const [actionMessage, setActionMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    function refreshQueue() {
      setReports(getGroundReports());
    }

    window.addEventListener(
      "habitatpulse-ground-handover-updated",
      refreshQueue,
    );
    window.addEventListener("storage", refreshQueue);

    return () => {
      window.removeEventListener(
        "habitatpulse-ground-handover-updated",
        refreshQueue,
      );
      window.removeEventListener("storage", refreshQueue);
    };
  }, []);

  const selectedReport =
    reports.find((report) => report.id === selectedReportId) ?? reports[0];

  const selectedCrewId = selectedReport?.crewId;

  useEffect(() => {
    if (!selectedCrewId) return;

    let cancelled = false;

    async function loadDatabaseData() {
      try {
        const [healthResponse, weekResponse, allResponse] = await Promise.all([
          fetch(
            `${HEALTH_API}?crew_code=${encodeURIComponent(
              selectedCrewId,
            )}&limit=500`,
          ),
          fetch(`${ENVIRONMENT_API}?module=all&window=7d&limit=3000`),
          fetch(`${ENVIRONMENT_API}?module=all&window=all&limit=12000`),
        ]);

        if (!healthResponse.ok || !weekResponse.ok || !allResponse.ok) {
          throw new Error("Could not load local MySQL data.");
        }

        const healthData = (await healthResponse.json()) as {
          records?: Checkin[];
        };
        const weekData = (await weekResponse.json()) as EnvironmentResponse;
        const allData = (await allResponse.json()) as EnvironmentResponse;

        if (!cancelled) {
          setCheckins(healthData.records ?? []);
          setEnvironmentWeek(weekData.series ?? []);
          setEnvironmentAll(allData.series ?? []);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setError(
            "MySQL data cannot load. Start environment_api.py on port 8000.",
          );
        }
      }
    }

    void loadDatabaseData();

    return () => {
      cancelled = true;
    };
  }, [selectedCrewId]);

  const sortedCheckins = useMemo(() => {
    return [...checkins].sort(
      (first, second) =>
        new Date(first.time).getTime() - new Date(second.time).getTime(),
    );
  }, [checkins]);

  const sortedEnvironmentWeek = useMemo(() => {
    return [...environmentWeek].sort(
      (first, second) =>
        new Date(first.observed_at_utc).getTime() -
        new Date(second.observed_at_utc).getTime(),
    );
  }, [environmentWeek]);

  const sortedEnvironmentAll = useMemo(() => {
    return [...environmentAll].sort(
      (first, second) =>
        new Date(first.observed_at_utc).getTime() -
        new Date(second.observed_at_utc).getTime(),
    );
  }, [environmentAll]);

  const weekCheckins = lastSevenCheckinDays(sortedCheckins);
  const latestCheckin =
    sortedCheckins.length > 0
      ? sortedCheckins[sortedCheckins.length - 1]
      : null;

  const latestEnvironment =
    sortedEnvironmentWeek.length > 0
      ? sortedEnvironmentWeek[sortedEnvironmentWeek.length - 1]
      : null;

  const currentStatus: ReviewStatus = selectedReport
    ? statusByReport[selectedReport.id] ?? "Awaiting review"
    : "Awaiting review";

  const currentReply = selectedReport
    ? replyByReport[selectedReport.id] ?? ""
    : "";

  const evidencePatterns = useMemo(() => {
    if (!latestCheckin) {
      return ["No local MySQL check-in data found."];
    }

    const patterns: string[] = [];

    if (
      latestCheckin.symptoms.some((symptom) =>
        symptom.toLowerCase().includes("headache"),
      ) ||
      (latestCheckin.wellbeing ?? 5) <= 2
    ) {
      patterns.push("Headache / low wellbeing pattern for human review");
    }

    if (
      (latestCheckin.sleep ?? 24) < 6 ||
      latestCheckin.symptoms.some((symptom) =>
        symptom.toLowerCase().includes("fatigue"),
      )
    ) {
      patterns.push("Sleep or fatigue pattern for human review");
    }

    if (patterns.length === 0) {
      patterns.push("No elevated pattern in the latest check-in");
    }

    return patterns;
  }, [latestCheckin]);

  const checkinLines = (rows: Checkin[]): ChartLine[] => [
    {
      label: "Wellbeing",
      color: "#14b8a6",
      meaning: "self-reported scale 1–5",
      values: rows.map((row) => row.wellbeing),
    },
    {
      label: "Sleep",
      color: "#f59e0b",
      meaning: "hours of sleep",
      values: rows.map((row) => row.sleep),
    },
    {
      label: "Fluid intake",
      color: "#ec4899",
      meaning: "millilitres (ml)",
      values: rows.map((row) => row.fluid),
    },
    {
      label: "Mood / stress",
      color: "#6366f1",
      meaning: "self-reported scale 1–5",
      values: rows.map((row) => row.mood),
    },
  ];

  const environmentLines = (rows: EnvironmentPoint[]): ChartLine[] => [
    {
      label: "Carbon dioxide",
      color: "#06b6d4",
      meaning: "CO₂ in ppm",
      values: rows.map((row) => row.co2_ppm),
    },
    {
      label: "Temperature",
      color: "#f59e0b",
      meaning: "degrees Celsius (°C)",
      values: rows.map((row) => row.temperature_c),
    },
    {
      label: "Humidity",
      color: "#10b981",
      meaning: "relative humidity (%)",
      values: rows.map((row) => row.humidity_percent),
    },
  ];

  function setReviewStatus(status: ReviewStatus) {
    if (!selectedReport) return;

    const next = {
      ...statusByReport,
      [selectedReport.id]: status,
    };

    setStatusByReport(next);

    window.localStorage.setItem(
      "habitatpulse-ground-review-status",
      JSON.stringify(next),
    );

    setActionMessage(`Review status saved locally: ${status}.`);
  }

  function saveReply() {
    if (!selectedReport) return;

    const cleanReply = currentReply.trim();

    if (!cleanReply) {
      setActionMessage("Write a response before saving.");
      return;
    }

    window.localStorage.setItem(
      `habitatpulse-ground-reply-${selectedReport.id}`,
      cleanReply,
    );

    setActionMessage("Ground Medical response saved locally.");
  }

  if (!selectedReport) {
    return (
      <div className="ground-app">
        <aside className="ground-sidebar">
          <div className="ground-brand">
            Habitat<span>Pulse</span>
          </div>

          <div className="ground-actions-bar">
            <button
              type="button"
              className="ground-theme-toggle"
              onClick={onToggleTheme}
            >
              {theme === "light" ? "☾ Dark mode" : "☀ Light mode"}
            </button>

            <button
              type="button"
              className="ground-signout"
              onClick={onSignOut}
            >
              Sign out
            </button>
          </div>
        </aside>

        <main className="ground-main">
          <section className="ground-empty-report">
            <span className="ground-eyebrow">GROUND MEDICAL</span>
            <h1>No incoming report yet</h1>
            <p>
              Open the Space-side Reports page and select “Queue for Ground”.
            </p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="ground-app">
      <aside className="ground-sidebar">
        <div className="ground-brand">
          Habitat<span>Pulse</span>
        </div>

        <div className="ground-actions-bar">
          <button
            type="button"
            className="ground-theme-toggle"
            onClick={onToggleTheme}
          >
            {theme === "light" ? "☾ Dark mode" : "☀ Light mode"}
          </button>

          <button type="button" className="ground-profile-button">
            ◉ Ground Medical Officer
          </button>

          <button
            type="button"
            className="ground-signout"
            onClick={onSignOut}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="ground-main">
        <section className="ground-page-heading">
          <span className="ground-eyebrow">GROUND MEDICAL REVIEW</span>
          <h1>Incoming crew report</h1>
          <p>
            Review queued crew data, evidence patterns, habitat context, and
            prepare a local Ground Medical response.
          </p>
        </section>

        <label className="ground-report-select">
          Select incoming report
          <select
            value={selectedReport.id}
            onChange={(event) => {
              setSelectedReportId(event.target.value);
              setActionMessage("");
            }}
          >
            {reports.map((report) => (
              <option key={report.id} value={report.id}>
                {report.crewId} — {report.crewName} —{" "}
                {formatDate(report.createdAt)}
              </option>
            ))}
          </select>
        </label>

        {error && <p className="ground-error">{error}</p>}

        <section className="ground-review-strip" aria-label="Review status">
          <div>
            <span className="ground-strip-dot" />
            <strong>Local queue received</strong>
            <small>Offline-ready handover record</small>
          </div>

          <div>
            <small>Priority</small>
            <strong
              className={`ground-priority ground-priority-${selectedReport.risk.toLowerCase()}`}
            >
              {selectedReport.risk}
            </strong>
          </div>

          <div>
            <small>Review status</small>
            <strong>{currentStatus}</strong>
          </div>
        </section>

        <section className="ground-clinical-snapshot">
          <article>
            <small>Latest check-in</small>
            <strong>{formatDate(latestCheckin?.time)}</strong>
            <span>
              {latestCheckin?.symptoms?.length
                ? `${latestCheckin.symptoms.length} symptom(s) recorded`
                : "No symptoms recorded"}
            </span>
          </article>

          <article>
            <small>Wellbeing & rest</small>
            <strong>{latestCheckin?.wellbeing ?? "—"} / 5 wellbeing</strong>
            <span>{formatValue(latestCheckin?.sleep, " h")} sleep</span>
          </article>

          <article>
            <small>Habitat snapshot</small>
            <strong>{formatValue(latestEnvironment?.co2_ppm, " ppm")} CO₂</strong>
            <span>
              {formatValue(latestEnvironment?.temperature_c, " °C")} ·{" "}
              {formatValue(latestEnvironment?.humidity_percent, " %")}
            </span>
          </article>
        </section>

        <section className="ground-panel">
          <span className="ground-eyebrow">SPACE-SIDE REPORT CONTENT</span>
          <h2>Evidence and crew request</h2>

          <div className="ground-content-columns">
            <div>
              <h3>Evidence patterns for human review</h3>

              <ul>
                {evidencePatterns.map((pattern) => (
                  <li key={pattern}>{pattern}</li>
                ))}
              </ul>

              <p>
                <strong>Latest symptoms:</strong>{" "}
                {latestCheckin?.symptoms?.length
                  ? latestCheckin.symptoms.join(", ")
                  : "None recorded"}
              </p>
            </div>

            <div>
              <h3>Crew request / report note</h3>
              <p className="ground-request-note">
                {selectedReport.note ||
                  "No additional request was written by the crew member."}
              </p>
            </div>
          </div>
        </section>

        <section className="ground-panel ground-action-panel">
          <span className="ground-eyebrow">MEDICAL OFFICER ACTION</span>
          <h2>Review and respond</h2>

          <div className="ground-action-controls">
            <label>
              Review status
              <select
                value={currentStatus}
                onChange={(event) =>
                  setReviewStatus(event.target.value as ReviewStatus)
                }
              >
                <option value="Awaiting review">Awaiting review</option>
                <option value="In review">In review</option>
                <option value="Reviewed">Reviewed</option>
              </select>
            </label>

            <button
              type="button"
              className="ground-mark-reviewed"
              onClick={() => setReviewStatus("Reviewed")}
            >
              Mark reviewed
            </button>
          </div>

          <label className="ground-reply-label">
            Reply to crew / follow-up request
            <textarea
              value={currentReply}
              onChange={(event) => {
                setReplyByReport({
                  ...replyByReport,
                  [selectedReport.id]: event.target.value,
                });
                setActionMessage("");
              }}
              placeholder="Write guidance, a follow-up question, or a handover note for the crew..."
              rows={5}
            />
          </label>

          <button
            type="button"
            className="ground-save-reply"
            onClick={saveReply}
          >
            Save response locally
          </button>

          {actionMessage && (
            <p className="ground-action-message">{actionMessage}</p>
          )}

          <p className="ground-disclaimer">
            Prototype review workflow only. A qualified medical officer must
            make all clinical decisions and verify any medical action.
          </p>
        </section>

        <GroundChart
          title="Crew check-in graph — last 7 days"
          description="Recent health indicators from the selected crew member."
          lines={checkinLines(weekCheckins)}
          start={weekCheckins[0]?.time}
          end={weekCheckins[weekCheckins.length - 1]?.time}
        />

        <GroundChart
          title="Crew check-in graph — all stored records"
          description="All locally loaded MySQL check-ins for this crew member."
          lines={checkinLines(sortedCheckins)}
          start={sortedCheckins[0]?.time}
          end={sortedCheckins[sortedCheckins.length - 1]?.time}
        />

        <GroundChart
          title="Habitat environment graph — last 7 days"
          description="Local MySQL habitat records for the latest week."
          lines={environmentLines(sortedEnvironmentWeek)}
          start={sortedEnvironmentWeek[0]?.observed_at_utc}
          end={
            sortedEnvironmentWeek[sortedEnvironmentWeek.length - 1]
              ?.observed_at_utc
          }
        />

        <GroundChart
          title="Habitat environment graph — all stored records"
          description="Latest available stored environment records."
          lines={environmentLines(sortedEnvironmentAll)}
          start={sortedEnvironmentAll[0]?.observed_at_utc}
          end={
            sortedEnvironmentAll[sortedEnvironmentAll.length - 1]
              ?.observed_at_utc
          }
        />
      </main>
    </div>
  );
}