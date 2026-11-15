import { useState, type FormEvent } from "react";
import "./login.css";

export type LoginUser = {
  crewId: string;
  displayName: string;
  role: string;
};

type LoginProps = {
  onLogin: (user: LoginUser) => void;
};

const CREW_MEMBERS: Record<string, LoginUser> = {
  "CREW-01": {
    crewId: "CREW-01",
    displayName: "Alex Morgan",
    role: "Mission Specialist",
  },
  "CREW-02": {
    crewId: "CREW-02",
    displayName: "Jordan Lee",
    role: "Flight Engineer",
  },
  "CREW-03": {
    crewId: "CREW-03",
    displayName: "Taylor Brooks",
    role: "Science Officer",
  },
  "CREW-04": {
    crewId: "CREW-04",
    displayName: "Casey Rivera",
    role: "Systems Engineer",
  },
  "CREW-05": {
    crewId: "CREW-05",
    displayName: "Morgan Chen",
    role: "Medical Officer",
  },
};

export default function Login({ onLogin }: LoginProps) {
  const [crewId, setCrewId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const selectedCrew = CREW_MEMBERS[crewId.trim().toUpperCase()];

    if (!selectedCrew) {
      setError("Use a crew ID from CREW-01 to CREW-05.");
      return;
    }

    if (!password.trim()) {
      setError("Enter a password to continue.");
      return;
    }

    setError("");
    onLogin(selectedCrew);
  }


  return (
    <main className="login-page">
      <section className="login-visual">
        <img
          src="https://images-assets.nasa.gov/image/iss065e045357/iss065e045357~orig.jpg"
          alt="NASA astronaut receiving an eye health check aboard the International Space Station"
        />

        <div className="login-visual-shade" />

        <div className="login-visual-content">
          <p>MISSION HEALTH SYSTEM</p>
          <h1>Supporting crew health beyond Earth.</h1>
          <span>
            Crew check-ins, habitat monitoring, and human medical review in one
            workspace.
          </span>
        </div>
      </section>

      <section className="login-panel">
        <section className="login-card" aria-labelledby="login-title">
          <div className="login-brand">
            <div className="login-brand-icon">◉</div>

            <div>
              <strong>
                Habitat<span>Pulse</span>
              </strong>
              <small>Crew Health & Habitat Monitor</small>
            </div>
          </div>

          <p className="login-eyebrow">ONBOARD ACCESS · PROTOTYPE</p>
          <h2 id="login-title">Welcome aboard</h2>
          <p className="login-description">
            Sign in with your assigned crew account.
          </p>

          <form onSubmit={handleSubmit}>
            <label htmlFor="crew-id">
              Crew ID
              <input
                id="crew-id"
                type="text"
                value={crewId}
                onChange={(event) => setCrewId(event.target.value)}
                placeholder="Example: CREW-01"
                autoComplete="username"
              />
            </label>

            <label htmlFor="password">
              Password
              <div className="password-wrap">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter password"
                  autoComplete="current-password"
                />

                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>

            {error && <p className="login-error">{error}</p>}

            <button type="submit" className="login-submit">
              Sign in
            </button>
          </form>

          <p className="login-help">
            Access problem? Contact your mission administrator.
          </p>

          
        </section>
      </section>
    </main>
  );
}