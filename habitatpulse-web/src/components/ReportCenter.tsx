import { useEffect, useMemo, useState } from "react";
import type { DemoRecord } from "./DemoCheckin";
import { queueGroundReport } from "./groundHandover";

type ReportCenterProps = {
  records: DemoRecord[];
  crewId: string;
  crewName: string;
  crewRole: string;
  onOpenGround?: () => void;
};

type EnvironmentPoint = {
  observed_at_utc: string;
  temperature_c: number | null;
  humidity_percent: number | null;
  co2_ppm: number | null;
};

type EnvironmentData = {
  series?: EnvironmentPoint[];
};

type ChartLine = {
  key: string;
  label: string;
  color: string;
  meaning: string;
  values: Array<number | null>;
};

const ENV_API = "http://127.0.0.1:8000/api/v1/environment/dashboard";

function formatDate(value?: string) {
  if (!value) return "Not recorded";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function lastSevenDays<T extends { time: string }>(rows: T[]) {
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;

  return rows.filter((row) => new Date(row.time).getTime() >= cutoff);
}

function lastSevenEnvironmentDays(rows: EnvironmentPoint[]) {
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;

  return rows.filter(
    (row) => new Date(row.observed_at_utc).getTime() >= cutoff,
  );
}

function optionalNumber(record: DemoRecord, keys: string[]) {
  const source = record as unknown as Record<string, unknown>;

  for (const key of keys) {
    const value = source[key];

    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);

      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return null;
}

function chartPoints(values: Array<number | null>) {
  const width = 860;
  const height = 260;
  const left = 58;
  const right = 24;
  const top = 22;
  const bottom = 42;

  const numbers = values.filter(
    (value): value is number => typeof value === "number",
  );

  if (numbers.length === 0) return "";

  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  const range = Math.max(max - min, 1);

  return values
    .map((value, index) => {
      if (value === null) return "";

      const x =
        left +
        (index * (width - left - right)) / Math.max(values.length - 1, 1);

      const normalised = ((value - min) / range) * 100;

      const y =
        top + ((100 - normalised) * (height - top - bottom)) / 100;

      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function ReportChart({
  title,
  description,
  lines,
  startDate,
  endDate,
}: {
  title: string;
  description: string;
  lines: ChartLine[];
  startDate?: string;
  endDate?: string;
}) {
  const hasData = lines.some((line) =>
    line.values.some((value) => value !== null),
  );

  return (
    <article className="report-chart-card">
      <header className="report-chart-heading">
        <h4>{title}</h4>
        <p>{description}</p>
      </header>

      <div className="report-legend" aria-label={`${title} colour legend`}>
        {lines.map((line) => (
          <span key={line.key}>
            <i style={{ background: line.color }} />
            <strong>{line.label}</strong>
            <small>{line.meaning}</small>
          </span>
        ))}
      </div>

      {!hasData ? (
        <p className="report-empty-chart">
          No stored data is available for this graph.
        </p>
      ) : (
        <>
          <svg
            className="report-line-chart"
            viewBox="0 0 860 260"
            role="img"
            aria-label={title}
          >
            {[0, 25, 50, 75, 100].map((value) => {
              const y = 22 + ((100 - value) * (260 - 22 - 42)) / 100;

              return (
                <g key={value}>
                  <line
                    x1="58"
                    x2="836"
                    y1={y}
                    y2={y}
                    className="report-grid-line"
                  />
                  <text x="12" y={y + 4} className="report-axis-text">
                    {value}%
                  </text>
                </g>
              );
            })}

            <line
              x1="58"
              x2="58"
              y1="22"
              y2="218"
              className="report-axis-line"
            />

            <line
              x1="58"
              x2="836"
              y1="218"
              y2="218"
              className="report-axis-line"
            />

            {lines.map((line) => (
              <polyline
                key={line.key}
                points={chartPoints(line.values)}
                fill="none"
                stroke={line.color}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}

            <text
              x="430"
              y="248"
              textAnchor="middle"
              className="report-axis-text"
            >
              Time — oldest to newest
            </text>
          </svg>

          <div className="report-chart-times">
            <span>{formatDate(startDate)}</span>
            <span>{formatDate(endDate)}</span>
          </div>

          <p className="report-normalized-note">
            Each colour is normalised separately to a 0–100% visual scale.
            Read the legend for the real measurement and meaning.
          </p>
        </>
      )}
    </article>
  );
}

export default function ReportCenter({
  records,
  crewId,
  crewName,
  crewRole,
}: ReportCenterProps) {
  const [environmentWeek, setEnvironmentWeek] = useState<EnvironmentPoint[]>(
    [],
  );
  const [environmentAll, setEnvironmentAll] = useState<EnvironmentPoint[]>([]);
  const [environmentError, setEnvironmentError] = useState("");
  const [groundNote, setGroundNote] = useState("");
  const [queueMessage, setQueueMessage] = useState("");

  const sortedRecords = useMemo(
    () =>
      [...records].sort((first, second) =>
        first.time.localeCompare(second.time),
      ),
    [records],
  );

  const latest = sortedRecords.at(-1);
  const printableGroundNote = groundNote.trim();

  const symptomSummary =
    latest?.symptoms && latest.symptoms.length > 0
      ? latest.symptoms.join(", ")
      : "No symptoms recorded";

  const evidencePatterns = useMemo(() => {
    const patterns: string[] = [];

    if (
      latest &&
      (latest.symptoms.some((item) =>
        item.toLowerCase().includes("headache"),
      ) ||
        (latest.wellbeing ?? 5) <= 2)
    ) {
      patterns.push("Headache / wellbeing pattern for human review");
    }

    if (
      latest &&
      ((latest.sleep ?? 24) < 6 ||
        latest.symptoms.some((item) =>
          item.toLowerCase().includes("fatigue"),
        ))
    ) {
      patterns.push("Sleep or fatigue pattern for human review");
    }

    if (patterns.length === 0) {
      patterns.push("No elevated pattern in the latest check-in");
    }

    return patterns;
  }, [latest]);

  useEffect(() => {
    let cancelled = false;

    async function loadEnvironment() {
      try {
        const [weekResponse, allResponse] = await Promise.all([
          fetch(`${ENV_API}?module=all&window=7d&limit=3000`),
          fetch(`${ENV_API}?module=all&window=all&limit=12000`),
        ]);

        if (!weekResponse.ok || !allResponse.ok) {
          throw new Error("Environment API is unavailable.");
        }

        const weekData = (await weekResponse.json()) as EnvironmentData;
        const allData = (await allResponse.json()) as EnvironmentData;

        if (!cancelled) {
          setEnvironmentWeek(weekData.series ?? []);
          setEnvironmentAll(allData.series ?? []);
          setEnvironmentError("");
        }
      } catch {
        if (!cancelled) {
          setEnvironmentError(
            "Environment graphs need environment_api.py running on port 8000.",
          );
        }
      }
    }

    void loadEnvironment();

    return () => {
      cancelled = true;
    };
  }, []);

  const healthWeek = lastSevenDays(sortedRecords);

  const healthLines = (rows: DemoRecord[]): ChartLine[] => [
    {
      key: "wellbeing",
      label: "Wellbeing",
      color: "#14b8a6",
      meaning: "self-reported scale 1–5",
      values: rows.map((row) => row.wellbeing),
    },
    {
      key: "sleep",
      label: "Sleep",
      color: "#f59e0b",
      meaning: "hours of sleep",
      values: rows.map((row) => row.sleep),
    },
    {
      key: "fluid",
      label: "Fluid intake",
      color: "#ec4899",
      meaning: "millilitres (ml)",
      values: rows.map((row) => row.fluid),
    },
    {
      key: "heart-rate",
      label: "Heart rate",
      color: "#ef4444",
      meaning: "beats per minute (BPM)",
      values: rows.map((row) =>
        optionalNumber(row, ["heartRate", "heart_rate", "pulse_bpm"]),
      ),
    },
    {
      key: "spo2",
      label: "Blood oxygen",
      color: "#3b82f6",
      meaning: "SpO₂ percent (%)",
      values: rows.map((row) =>
        optionalNumber(row, ["spo2", "spo2Percent", "spo2_percent"]),
      ),
    },
    {
      key: "body-temperature",
      label: "Body temperature",
      color: "#8b5cf6",
      meaning: "degrees Celsius (°C)",
      values: rows.map((row) =>
        optionalNumber(row, [
          "bodyTemperature",
          "body_temperature",
          "body_temperature_c",
        ]),
      ),
    },
  ];

  const environmentLines = (
    rows: EnvironmentPoint[],
  ): ChartLine[] => [
    {
      key: "co2",
      label: "Carbon dioxide",
      color: "#06b6d4",
      meaning: "CO₂ in ppm",
      values: rows.map((row) => row.co2_ppm),
    },
    {
      key: "temperature",
      label: "Habitat temperature",
      color: "#f59e0b",
      meaning: "degrees Celsius (°C)",
      values: rows.map((row) => row.temperature_c),
    },
    {
      key: "humidity",
      label: "Relative humidity",
      color: "#10b981",
      meaning: "relative humidity (%)",
      values: rows.map((row) => row.humidity_percent),
    },
  ];

  function printReport() {
    window.print();
  }

  function queueForGround() {
    const risk: "Low" | "Moderate" | "Elevated" =
      latest?.urgent || (latest?.wellbeing ?? 5) <= 2
        ? "Elevated"
        : latest?.symptoms?.length
          ? "Moderate"
          : "Low";

    queueGroundReport({
      crewId,
      crewName,
      title: "Crew health and habitat report",
      habitat: "HAB-MODULE-B",
      concern:
        symptomSummary === "No symptoms recorded"
          ? "Routine crew health summary"
          : `Reported symptoms: ${symptomSummary}`,
      risk,
      note: printableGroundNote,
      latestCheckin: latest?.time ?? "",
      wellbeing: latest?.wellbeing ?? null,
      symptoms: latest?.symptoms ?? [],
      recordCount: sortedRecords.length,
    });

    setQueueMessage(
      "Report has been saved in the local Ground handover queue. It remains available while offline.",
    );
  }

  return (
    <section className="report-page" aria-label="Crew health report">
      <div className="page-intro">
        <span className="eyebrow">MISSION REPORTS</span>
        <h2>Crew health and habitat report</h2>
        <p>
          Printable evidence, MySQL check-in trends, habitat trends, and a
          Ground Medical handover note.
        </p>
      </div>

      <section className="report-card report-print-area">
        <div className="report-card-heading">
          <div>
            <span className="eyebrow">CREW REPORT</span>
            <h3>{crewName}</h3>
            <p>
              {crewId} · {crewRole} · HAB-MODULE-B
            </p>
          </div>

          <div className="report-actions no-print">
            <button type="button" className="trends-cta" onClick={printReport}>
              Print / Save PDF
            </button>

            <button
              type="button"
              className="report-ground-button"
              onClick={queueForGround}
            >
              Queue for Ground
            </button>
          </div>
        </div>

        {queueMessage && (
          <p className="report-queue-message" role="status">
            ✓ {queueMessage}
          </p>
        )}

        <div className="report-grid">
          <article>
            <small>Latest check-in</small>
            <strong>{formatDate(latest?.time)}</strong>
          </article>

          <article>
            <small>Overall wellbeing</small>
            <strong>{latest?.wellbeing ?? "—"} / 5</strong>
          </article>

          <article>
            <small>Recorded symptoms</small>
            <strong>{latest?.symptoms?.length ?? 0}</strong>
          </article>

          <article>
            <small>Stored check-ins</small>
            <strong>{sortedRecords.length}</strong>
          </article>
        </div>

        <section className="report-section">
          <span className="eyebrow">EVIDENCE OUTPUT</span>
          <h4>Patterns for human review</h4>

          <ul className="report-pattern-list">
            {evidencePatterns.map((pattern) => (
              <li key={pattern}>{pattern}</li>
            ))}
          </ul>

          <p>
            Latest symptoms: <strong>{symptomSummary}</strong>
          </p>

          <p className="report-disclaimer">
            These are screening patterns, not diagnoses. Human medical review
            remains required.
          </p>
        </section>

        <section className="report-graphs">
          <div className="report-section-title">
            <span className="eyebrow">CREW CHECK-IN DATA</span>
            <h4>Health indicators</h4>
            <p>
              Each graph has its own bordered card. The legend explains every
              line colour and real measurement unit.
            </p>
          </div>

          <ReportChart
            title="Crew check-in trends — last 7 days"
            description="Recent crew health indicators stored in MySQL."
            lines={healthLines(healthWeek)}
            startDate={healthWeek[0]?.time}
            endDate={healthWeek.at(-1)?.time}
          />

          <ReportChart
            title="Crew check-in trends — all stored records"
            description="All locally loaded check-ins for this crew member."
            lines={healthLines(sortedRecords)}
            startDate={sortedRecords[0]?.time}
            endDate={sortedRecords.at(-1)?.time}
          />
        </section>

        <section className="report-graphs">
          <div className="report-section-title">
            <span className="eyebrow">ENVIRONMENT DATA</span>
            <h4>Habitat conditions</h4>
            <p>
              CO₂, temperature, and humidity are displayed with a separate
              normalised scale for each line.
            </p>
          </div>

          {environmentError && (
            <p className="report-api-error">{environmentError}</p>
          )}

          <ReportChart
            title="Habitat trends — last 7 days"
            description="Local MySQL environmental records for the latest week."
            lines={environmentLines(
              lastSevenEnvironmentDays(environmentWeek),
            )}
            startDate={environmentWeek[0]?.observed_at_utc}
            endDate={environmentWeek.at(-1)?.observed_at_utc}
          />

          <ReportChart
            title="Habitat trends — all stored records"
            description="The latest stored environment records available locally."
            lines={environmentLines(environmentAll)}
            startDate={environmentAll[0]?.observed_at_utc}
            endDate={environmentAll.at(-1)?.observed_at_utc}
          />
        </section>

        <section className="report-section report-ground-note">
          <span className="eyebrow">GROUND MEDICAL HANDOVER</span>
          <h4>Question, explanation, or follow-up request</h4>

          <textarea
            value={groundNote}
            onChange={(event) => setGroundNote(event.target.value)}
            placeholder="Write a question or explanation for Ground Medical. It appears in the PDF only when text is entered."
            rows={5}
          />
        </section>

        {printableGroundNote && (
          <section className="print-ground-note">
            <span className="eyebrow">GROUND MEDICAL HANDOVER</span>
            <h4>Crew question, explanation, or follow-up request</h4>
            <p>{printableGroundNote}</p>
          </section>
        )}

        <p className="report-footer-disclaimer">
          Prototype display only. This report does not diagnose illness,
          prescribe medicine, or replace human medical review.
        </p>
      </section>
    </section>
  );
}