import { useState, type FormEvent } from "react";
import "./login.css";

type GroundLoginProps = {
  onSignIn: () => void;
};

const DEMO_ACCOUNT = "GROUND-DEMO";
const DEMO_PASSWORD = "DemoGround123!";

export default function GroundLogin({ onSignIn }: GroundLoginProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const form = new FormData(event.currentTarget);
    const account = String(form.get("account") ?? "").trim().toUpperCase();
    const password = String(form.get("password") ?? "");

    if (account !== DEMO_ACCOUNT || password !== DEMO_PASSWORD) {
      setError("The demo account ID or password is incorrect.");
      return;
    }

    onSignIn();
  }

  return (
    <main className="login-page">
      <section className="login-visual" aria-label="Mission health">
        <img
          src="https://images-assets.nasa.gov/image/iss065e045357/iss065e045357~orig.jpg"
          alt="NASA astronauts conducting an eye health check aboard the International Space Station"
        />

        <div className="login-visual-shade" aria-hidden="true" />

        <div className="login-visual-content">
          <p>MISSION HEALTH SYSTEM</p>
          <h1>Supporting crew health from Earth.</h1>
          <span>
            Review incoming crew reports, compare them with habitat readings,
            and record follow-up guidance.
          </span>
        </div>
      </section>

      <section className="login-panel">
        <section className="login-card" aria-labelledby="ground-login-title">
          <div className="login-brand">
            <div className="login-brand-icon" aria-hidden="true">◉</div>
            <div>
              <strong>Habitat<span>Pulse</span></strong>
              <small>Ground Medical Hub</small>
            </div>
          </div>

          <p className="login-eyebrow">GROUND ACCESS · PROTOTYPE</p>
          <h2 id="ground-login-title">Ground Medical Sign-in</h2>
          <p className="login-description">
            Sign in to review crew health reports.
          </p>

          <form onSubmit={handleSubmit} onChange={() => setError("")}>
            <label htmlFor="ground-account">
              Ground account ID
              <input
                id="ground-account"
                name="account"
                type="text"
                placeholder="GROUND-DEMO"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
              />
            </label>

            <div>
              <label htmlFor="ground-password">Password</label>
              <div className="password-wrap" style={{ marginTop: 8 }}>
                <input
                  id="ground-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter password"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  aria-controls="ground-password"
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <p className="login-error" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="login-submit">
              Sign in
            </button>
          </form>

        
        </section>
      </section>
    </main>
  );
}