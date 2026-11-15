export type GroundReportStatus =
  | "Needs Review"
  | "Reviewing"
  | "Reviewed";

export type GroundHandoverReport = {
  id: string;
  crewId: string;
  crewName: string;
  title: string;
  createdAt: string;
  habitat: string;
  status: GroundReportStatus;
  concern: string;
  risk: "Low" | "Moderate" | "Elevated";
  note: string;
  latestCheckin: string;
  wellbeing: number | null;
  symptoms: string[];
  recordCount: number;
};

const STORAGE_KEY = "habitatpulse-ground-handover-queue";
const UPDATE_EVENT = "habitatpulse-ground-handover-updated";

function readReports(): GroundHandoverReport[] {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = value ? JSON.parse(value) : [];
    return Array.isArray(parsed) ? (parsed as GroundHandoverReport[]) : [];
  } catch {
    return [];
  }
}

function saveReports(reports: GroundHandoverReport[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
  window.dispatchEvent(new Event(UPDATE_EVENT));
}

export const getGroundReports = readReports;

export function queueGroundReport(
  report: Omit<GroundHandoverReport, "id" | "createdAt" | "status">,
) {
  const queued: GroundHandoverReport = {
    ...report,
    id: `AG-${Date.now().toString().slice(-6)}`,
    createdAt: new Date().toISOString(),
    status: "Needs Review",
  };

  saveReports([queued, ...readReports()]);
  return queued;
}

export function updateGroundReport(
  id: string,
  changes: Partial<Pick<GroundHandoverReport, "status" | "note">>,
) {
  saveReports(
    readReports().map((report) =>
      report.id === id ? { ...report, ...changes } : report,
    ),
  );
}

export function subscribeToGroundReports(callback: () => void) {
  window.addEventListener(UPDATE_EVENT, callback);
  window.addEventListener("storage", callback);

  return () => {
    window.removeEventListener(UPDATE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}