import { useCallback, useEffect, useState } from "react";
import "./App.css";

import Overview from "./components/Overview";
import CrewCheckin from "./components/CrewCheckin";
import EnvironmentDashboard from "./components/EnvironmentDashboard";
import EvidenceCenter from "./components/EvidenceCenter";
import ReportCenter from "./components/ReportCenter";
import Login, { type LoginUser } from "./components/Login";
import GroundLogin from "./components/GroundLogin";
import GroundDashboard from "./components/GroundDashboard";
import type { DemoRecord } from "./components/DemoCheckin";

type Page =
  | "overview"
  | "checkin"
  | "environment"
  | "evidence"
  | "reports"
  | "ground";

type Theme = "light" | "dark";

const USER_STORAGE_KEY = "habitatpulse-demo-user";

function pageFromHash(): Page {
  const value = window.location.hash.replace("#", "");

  if (
    value === "checkin" ||
    value === "environment" ||
    value === "evidence" ||
    value === "reports" ||
    value === "ground"
  ) {
    return value;
  }

  return "overview";
}

function initialTheme(): Theme {
  return window.localStorage.getItem("habitatpulse-theme") === "dark"
    ? "dark"
    : "light";
}

function savedUser(): LoginUser | null {
  try {
    const stored = window.localStorage.getItem(USER_STORAGE_KEY);

    if (!stored) {
      return null;
    }

    const user = JSON.parse(stored) as LoginUser;

    if (
      typeof user.crewId !== "string" ||
      typeof user.displayName !== "string" ||
      typeof user.role !== "string"
    ) {
      return null;
    }

    return user;
  } catch {
    return null;
  }
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [newRecords, setNewRecords] = useState<DemoRecord[]>([]);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [user, setUser] = useState<LoginUser | null>(savedUser);
  const [groundSignedIn, setGroundSignedIn] = useState(false);

  const loadDatabaseCheckins = useCallback(
    async (crewId: string, signal?: AbortSignal) => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/v1/health/checkins?crew_code=${encodeURIComponent(
            crewId,
          )}&limit=500`,
          { signal },
        );

        if (!response.ok) {
          throw new Error("Could not load check-ins.");
        }

        const payload = (await response.json()) as {
          records?: DemoRecord[];
        };

        if (!signal?.aborted) {
          setNewRecords(payload.records ?? []);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        // Keep the interface usable while the local database API is offline.
      }
    },
    [],
  );

  useEffect(() => {
    function syncPageFromHash() {
      setPage(pageFromHash());
    }

    window.addEventListener("hashchange", syncPageFromHash);

    return () => {
      window.removeEventListener("hashchange", syncPageFromHash);
    };
  }, []);

  useEffect(() => {
    if (!user) {
      return;
    }

    const controller = new AbortController();

    const timer = window.setTimeout(() => {
      void loadDatabaseCheckins(user.crewId, controller.signal);
    }, 0);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [user, loadDatabaseCheckins]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("habitatpulse-theme", theme);
  }, [theme]);

  function goTo(nextPage: Page) {
    window.location.hash = nextPage;
    setPage(nextPage);
  }

  function handleLogin(nextUser: LoginUser) {
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser));
    setNewRecords([]);
    setUser(nextUser);
    goTo("overview");
  }

  function handleSignOut() {
    window.localStorage.removeItem(USER_STORAGE_KEY);
    setNewRecords([]);
    setUser(null);
    goTo("overview");
  }

  function saveNewRecord(record: DemoRecord) {
    setNewRecords((oldRecords) =>
      [...oldRecords.filter((item) => item.id !== record.id), record]
        .sort((first, second) => first.time.localeCompare(second.time))
        .slice(-500),
    );

    if (user) {
      window.setTimeout(() => {
        void loadDatabaseCheckins(user.crewId);
      }, 0);
    }
  }

  function toggleTheme() {
    setTheme((currentTheme) =>
      currentTheme === "light" ? "dark" : "light",
    );
  }

  // Ground Medical access is separate from crew access.
  if (page === "ground") {
    if (!groundSignedIn) {
      return (
        <GroundLogin
          onSignIn={() => {
            setGroundSignedIn(true);
          }}
        />
      );
    }

    return (
  <GroundDashboard
    theme={theme}
    onToggleTheme={toggleTheme}
    onSignOut={() => {
      setGroundSignedIn(false);
    }}
  />
);
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <main className="app">
      <aside className="sidebar">
        <div className="logo">
          Habitat<span>Pulse</span>
        </div>

        <nav aria-label="HabitatPulse pages">
          <a
            href="#overview"
            className={page === "overview" ? "active" : ""}
            onClick={() => goTo("overview")}
          >
            ⌂ <span>Overview</span>
          </a>

          <a
            href="#checkin"
            className={page === "checkin" ? "active" : ""}
            onClick={() => goTo("checkin")}
          >
            ♡ <span>Crew Check-ins</span>
          </a>

          <a
            href="#environment"
            className={page === "environment" ? "active" : ""}
            onClick={() => goTo("environment")}
          >
            ◒ <span>Environment</span>
          </a>

          <a
            href="#evidence"
            className={page === "evidence" ? "active" : ""}
            onClick={() => goTo("evidence")}
          >
            ▤ <span>Evidence</span>
          </a>

          <a
            href="#reports"
            className={page === "reports" ? "active" : ""}
            onClick={() => goTo("reports")}
          >
            ▥ <span>Reports</span>
          </a>
        </nav>

        <div className="sidebar-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label="Change colour theme"
          >
            <span className="theme-icon">
              {theme === "light" ? "☾" : "☀"}
            </span>
            {theme === "light" ? "Dark mode" : "Light mode"}
          </button>

          <button
            type="button"
            className="theme-toggle sample-profile-button"
            onClick={() => goTo("checkin")}
            title="Open current crew profile"
          >
            ◉ {user.crewId} · {user.displayName}
          </button>

          <button
            type="button"
            className="theme-toggle"
            onClick={handleSignOut}
          >
            Sign out
          </button>
        </div>
      </aside>

      <section className="content">
        {page === "overview" && (
  <Overview
    records={newRecords}
    onOpenCheckin={() => goTo("checkin")}
    onOpenEnvironment={() => goTo("environment")}
    onOpenEvidence={() => goTo("evidence")}
    onOpenReports={() => goTo("reports")}
  />
)}

        {page === "checkin" && (
          <CrewCheckin onSaved={saveNewRecord} />
        )}

        {page === "environment" && <EnvironmentDashboard />}

        {page === "evidence" && (
          <EvidenceCenter crewId={user.crewId} />
        )}

        {page === "reports" && (
          <ReportCenter
            records={newRecords}
            crewId={user.crewId}
            crewName={user.displayName}
            crewRole={user.role}
            onOpenGround={() => goTo("ground")}
          />
        )}
      </section>
    </main>
  );
}