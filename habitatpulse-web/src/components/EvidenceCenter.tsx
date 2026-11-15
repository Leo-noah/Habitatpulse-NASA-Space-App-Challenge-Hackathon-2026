import { useEffect, useMemo, useState } from "react";

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

type Env = {
  latest?: {
    observed_at_utc: string;
    co2_ppm: number | null;
    temperature_c: number | null;
    humidity_percent: number | null;
    anomaly_flag: number | boolean;
  };
};

type InventoryItem = {
  id: number;
  medication_name: string;
  form_description: string | null;
  quantity_available: number;
  expiry_date: string | null;
};

type Hypothesis = {
  title: string;
  score: string;
  supports: string[];
  limits: string[];
};

type Suggestions = {
  nutrition: string[];
  activity: string[];
};

type EvidenceCenterProps = {
  crewId: string;
};

const ENV_API =
  "http://127.0.0.1:8000/api/v1/environment/dashboard?module=all&window=24h&limit=500";

const INVENTORY_API =
  "http://127.0.0.1:8000/api/v1/medication-inventory";

function buildHypotheses(
  latest: Checkin | null,
  environment: Env | null,
): Hypothesis[] {
  const symptoms = latest?.symptoms?.map((item) => item.toLowerCase()) ?? [];
  const items: Hypothesis[] = [];

  const hasLowWellbeing =
    latest?.wellbeing !== null &&
    latest?.wellbeing !== undefined &&
    latest.wellbeing <= 2;

  const hasShortSleep =
    latest?.sleep !== null &&
    latest?.sleep !== undefined &&
    latest.sleep < 6;

  const hasHeadache = symptoms.some((item) => item.includes("headache"));
  const hasFatigue = symptoms.some((item) => item.includes("fatigue"));
  const hasEnvironmentFlag = Boolean(environment?.latest?.anomaly_flag);

  if (hasHeadache || hasLowWellbeing) {
    items.push({
      title: "Headache / wellbeing pattern",
      score: "Review priority: elevated",
      supports: [
        `Reported symptoms: ${latest?.symptoms?.join(", ") || "not recorded"}`,
        `Overall wellbeing: ${latest?.wellbeing ?? "not recorded"} / 5`,
      ],
      limits: [
        "Screening pattern only; no diagnosis is made.",
        "Clinical interview and medical judgement are required.",
      ],
    });
  }

  if (hasShortSleep || hasFatigue) {
    items.push({
      title: "Sleep or fatigue pattern",
      score: "Review priority: moderate",
      supports: [
        `Sleep hours: ${latest?.sleep ?? "not recorded"}`,
        `Symptoms: ${latest?.symptoms?.join(", ") || "none recorded"}`,
      ],
      limits: [
        "This does not identify a cause.",
        "More trend data may be needed.",
      ],
    });
  }

  if (hasEnvironmentFlag) {
    items.push({
      title: "Environment context overlap",
      score: "Review priority: moderate",
      supports: [
        `CO₂: ${environment?.latest?.co2_ppm ?? "not recorded"} ppm`,
        `Environment flag time: ${
          environment?.latest?.observed_at_utc ?? "not recorded"
        }`,
      ],
      limits: [
        "Time overlap is not proof of cause.",
        "Environment model flag is not a safety limit.",
      ],
    });
  }

  if (items.length === 0) {
    items.push({
      title: "No elevated pattern in the latest check-in",
      score: "Review priority: routine",
      supports: [
        `Wellbeing: ${latest?.wellbeing ?? "not recorded"} / 5`,
        `Symptoms: ${latest?.symptoms?.join(", ") || "none recorded"}`,
        `Sleep: ${latest?.sleep ?? "not recorded"} hours`,
      ],
      limits: [
        "A normal screening result does not replace medical review.",
        "Future check-ins may show a different trend.",
      ],
    });
  }

  return items.slice(0, 3);
}

function buildSuggestions(
  latest: Checkin | null,
  hypotheses: Hypothesis[],
): Suggestions {
  const symptoms = latest?.symptoms?.map((item) => item.toLowerCase()) ?? [];

  const hasHeadache =
    symptoms.some((item) => item.includes("headache")) ||
    hypotheses.some((item) => item.title.includes("Headache"));

  const hasSleepPattern = hypotheses.some((item) =>
    item.title.includes("Sleep"),
  );

  const hasUrgentConcern = latest?.urgent === true;

  if (hasUrgentConcern) {
    return {
      nutrition: [
        "Do not delay medical-officer review for food or drink suggestions.",
        "Follow the mission medical officer’s immediate instructions.",
        "Document symptom time and recent food or fluid intake.",
      ],
      activity: [
        "Pause non-essential activity until human review is complete.",
        "Avoid exercise or mission-task changes unless authorised.",
        "Use the required escalation protocol.",
      ],
    };
  }

  return {
    nutrition: [
      hasHeadache
        ? "Matched to headache / wellbeing pattern: maintain regular water intake and record fluid consumption."
        : "Maintain regular hydration and record fluid consumption.",
      "Choose balanced meals with protein, vegetables, fruit, and complex carbohydrates.",
      hasSleepPattern
        ? "Matched to sleep / fatigue pattern: limit caffeine late in the crew day."
        : "Avoid skipping meals during demanding mission tasks.",
    ],
    activity: [
      hasHeadache
        ? "Matched to headache / wellbeing pattern: take a quiet, low-light rest break if operations allow."
        : "Use regular short breaks during sustained work periods.",
      hasSleepPattern
        ? "Matched to sleep / fatigue pattern: prioritise the next scheduled sleep opportunity."
        : "Include light movement and stretching during the crew day.",
      "Report repeated symptoms or reduced ability to complete tasks.",
    ],
  };
}

function formatTime(value: string | undefined) {
  if (!value) return "No check-in found";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString([], {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function numberWithUnit(
  value: number | null | undefined,
  unit: string,
) {
  return typeof value === "number" ? `${value.toFixed(1)} ${unit}` : "—";
}

export default function EvidenceCenter({
  crewId,
}: EvidenceCenterProps) {
  const [records, setRecords] = useState<Checkin[]>([]);
  const [environment, setEnvironment] = useState<Env | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function loadEvidence() {
      try {
        const healthApi =
          "http://127.0.0.1:8000/api/v1/health/checkins" +
          `?crew_code=${encodeURIComponent(crewId)}&limit=30`;

        const [healthResponse, environmentResponse, inventoryResponse] =
          await Promise.all([
            fetch(healthApi, { signal: controller.signal }),
            fetch(ENV_API, { signal: controller.signal }),
            fetch(INVENTORY_API, { signal: controller.signal }),
          ]);

        const health = healthResponse.ok ? await healthResponse.json() : null;
        const env = environmentResponse.ok
          ? await environmentResponse.json()
          : null;
        const inventoryData = inventoryResponse.ok
          ? await inventoryResponse.json()
          : null;

        if (!active || controller.signal.aborted) return;

        setRecords(health?.records ?? []);
        setEnvironment(env);
        setInventory(inventoryData?.items ?? []);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        if (!active) return;

        setRecords([]);
        setEnvironment(null);
        setInventory([]);
      }
    }

    const loadTimer = window.setTimeout(() => {
      void loadEvidence();
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(loadTimer);
      controller.abort();
    };
  }, [crewId]);

  const latest = useMemo(() => {
    if (records.length === 0) return null;

    return records.reduce((newest, record) =>
      record.time > newest.time ? record : newest,
    );
  }, [records]);

  const hypotheses = useMemo(
    () => buildHypotheses(latest, environment),
    [latest, environment],
  );

  const suggestions = useMemo(
    () => buildSuggestions(latest, hypotheses),
    [latest, hypotheses],
  );

  return (
    <section className="evidence-center">
      <div className="page-intro">
        <span className="eyebrow">
          MEDICAL INTELLIGENCE & EVIDENCE CENTER
        </span>

        <h2>Evidence review</h2>

        <p>
          Connects {crewId} check-ins and environmental context to support
          human review.
        </p>
      </div>

      <section className="evidence-summary">
        <div>
          <small>Current crew</small>
          <strong>{crewId}</strong>
        </div>

        <div>
          <small>Latest crew check-in</small>
          <strong>{formatTime(latest?.time)}</strong>
        </div>

        <div>
          <small>Wellbeing</small>
          <strong>{latest?.wellbeing ?? "—"} / 5</strong>
        </div>

        <div>
          <small>Symptoms</small>
          <strong>{latest?.symptoms?.join(", ") || "None recorded"}</strong>
        </div>

        <div>
          <small>CO₂</small>
          <strong>{numberWithUnit(environment?.latest?.co2_ppm, "ppm")}</strong>
        </div>

        <div>
          <small>Temperature</small>
          <strong>
            {numberWithUnit(environment?.latest?.temperature_c, "°C")}
          </strong>
        </div>

        <div>
          <small>Relative humidity</small>
          <strong>
            {numberWithUnit(environment?.latest?.humidity_percent, "%")}
          </strong>
        </div>
      </section>

      <section className="assessment-panel">
        <p className="eyebrow">EXPLAINABLE SCREENING</p>
        <h3>Patterns for human review</h3>

        <div className="hypothesis-grid">
          {hypotheses.map((item, index) => (
            <article key={`${item.title}-${index}`}>
              <span>0{index + 1}</span>
              <h4>{item.title}</h4>
              <b>{item.score}</b>

              <p>
                <strong>Supporting evidence</strong>
              </p>

              <ul>
                {item.supports.map((evidence) => (
                  <li key={evidence}>{evidence}</li>
                ))}
              </ul>

              <p>
                <strong>Uncertainty / limit</strong>
              </p>

              <ul>
                {item.limits.map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="suggestions-panel">
        <div className="suggestions-heading">
          <p className="eyebrow">CREW SUPPORT SUGGESTIONS</p>
          <h3>Suggested next actions</h3>
          <p>
            General prototype suggestions based on recorded patterns. A medical
            officer makes all treatment decisions.
          </p>
        </div>

        <div className="suggestion-grid">
          <article className="suggestion-card nutrition-card">
            <span className="suggestion-icon" aria-hidden="true">
              ◉
            </span>

            <p className="eyebrow">NUTRITION & HYDRATION</p>
            <h4>Food and fluid suggestions</h4>

            <ul>
              {suggestions.nutrition.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>

          <article className="suggestion-card activity-card">
            <span className="suggestion-icon" aria-hidden="true">
              ◌
            </span>

            <p className="eyebrow">ACTIVITY & REST</p>
            <h4>Exercise and lifestyle suggestions</h4>

            <ul>
              {suggestions.activity.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>

          <article className="suggestion-card inventory-card">
            <span className="suggestion-icon" aria-hidden="true">
              ▣
            </span>

            <p className="eyebrow">MEDICINE INVENTORY</p>
            <h4>Available stock for medical-officer review</h4>

            <ul>
              {inventory.length > 0 ? (
                inventory.map((item) => (
                  <li key={item.id}>
                    <strong>{item.medication_name}</strong>
                    {" — "}
                    {item.form_description || "No form description"}
                    {" · "}
                    Available: {item.quantity_available}
                    {" · "}
                    Expiry: {item.expiry_date || "not recorded"}
                  </li>
                ))
              ) : (
                <li>No active medication inventory records found.</li>
              )}
            </ul>

            <p className="inventory-note">
              This is an inventory listing only. A medical officer must verify
              approval, expiry, contraindications, and appropriate use.
            </p>
          </article>
        </div>
      </section>
    </section>
  );
}