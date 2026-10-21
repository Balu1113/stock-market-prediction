import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";
import AnalyzeTab from "./components/AnalyzeTab";
import TopPicksTab from "./components/TopPicksTab";
import ScreenerTab from "./components/ScreenerTab";
import StrategiesTab from "./components/StrategiesTab";
import AlertsTab from "./components/AlertsTab";
import PortfolioTab from "./components/PortfolioTab";
import MarketTab from "./components/MarketTab";
import "./App.css";

const TABS = [
  ["analyze", "Analyze"],
  ["top-picks", "Top Picks"],
  ["screener", "Screener"],
  ["strategies", "Strategies"],
  ["alerts", "Alerts"],
  ["portfolio", "Portfolio"],
  ["market", "Market"],
];

function AuthControls({ user, onUserChange }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/auth/${mode}`, { username, password });
      onUserChange(data);
      setUsername("");
      setPassword("");
    } catch (requestError) {
      setError(errorMessage(requestError, "Authentication failed."));
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await api.post("/auth/logout");
    onUserChange({ authenticated: false, username: "" });
  };

  if (user?.authenticated) {
    return (
      <div className="auth-bar">
        <span className="auth-user">{user.username}</span>
        <button type="button" className="btn btn-small" onClick={logout}>Sign out</button>
      </div>
    );
  }

  return (
    <form className="auth-bar" onSubmit={submit}>
      <input
        placeholder="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <button type="submit" className="btn btn-small" disabled={busy}>
        {mode === "login" ? "Sign in" : "Register"}
      </button>
      <button
        type="button"
        className="link-button"
        onClick={() => setMode((prev) => (prev === "login" ? "register" : "login"))}
      >
        {mode === "login" ? "Create account" : "Have an account?"}
      </button>
      {error && <span className="auth-error">{error}</span>}
    </form>
  );
}

export default function App() {
  const [tab, setTab] = useState("analyze");
  const [user, setUser] = useState({ authenticated: false, username: "" });
  const [openSymbol, setOpenSymbol] = useState("");

  useEffect(() => {
    api
      .get("/auth/me")
      .then(({ data }) => setUser(data))
      .catch(() => {});
  }, []);

  const openInAnalyze = useCallback((symbol) => {
    setOpenSymbol(symbol);
    setTab("analyze");
  }, []);

  const handleYahooSymbolReady = useCallback((symbol) => {
    if (symbol === openSymbol) return;
  }, [openSymbol]);

  return (
    <div className="app">
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">&#128200;</div>
            <div>
              <h1 className="brand-title">Stock Prediction &amp; Trading</h1>
              <p className="brand-subtitle">
                Forecast, screen, backtest, and track NSE/BSE markets
              </p>
            </div>
          </div>
          <div className="header-side">
            <AuthControls user={user} onUserChange={setUser} />
          </div>
        </header>

        <nav className="nav-tabs" aria-label="Sections">
          {TABS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`nav-tab ${tab === key ? "active" : ""}`}
              aria-pressed={tab === key}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>

        {tab === "analyze" && (
          <AnalyzeTab yahooSymbolOverride={openSymbol} onYahooSymbolReady={handleYahooSymbolReady} />
        )}
        {tab === "top-picks" && <TopPicksTab onOpenSymbol={openInAnalyze} />}
        {tab === "screener" && <ScreenerTab onOpenSymbol={openInAnalyze} />}
        {tab === "strategies" && <StrategiesTab />}
        {tab === "alerts" && <AlertsTab user={user} />}
        {tab === "portfolio" && <PortfolioTab user={user} />}
        {tab === "market" && <MarketTab onOpenSymbol={openInAnalyze} />}
      </div>
    </div>
  );
}
