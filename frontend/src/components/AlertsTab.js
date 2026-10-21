import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { formatAmount } from "../format";

const CONDITIONS = [
  ["price_above", "Price above", true],
  ["price_below", "Price below", true],
  ["rsi_above", "RSI above", true],
  ["rsi_below", "RSI below", true],
  ["ma_cross_up", "MA20 crosses above MA50", false],
  ["ma_cross_down", "MA20 crosses below MA50", false],
  ["volume_spike", "Volume ≥ k× 20d avg", true],
];

export default function AlertsTab({ user }) {
  const [alerts, setAlerts] = useState([]);
  const [events, setEvents] = useState([]);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [conditionType, setConditionType] = useState("price_above");
  const [threshold, setThreshold] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);

  const needsThreshold = CONDITIONS.find((c) => c[0] === conditionType)?.[2];

  const loadAll = useCallback(async () => {
    try {
      const [alertsRes, eventsRes] = await Promise.all([
        api.get("/alerts"),
        api.get("/alerts/events"),
      ]);
      setAlerts(alertsRes.data.alerts);
      setEvents(eventsRes.data.events);
    } catch {
      /* backend offline */
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const createAlert = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/alerts", {
        symbol: symbol.trim(),
        condition_type: conditionType,
        threshold: needsThreshold ? parseFloat(threshold) : null,
      });
      setThreshold("");
      loadAll();
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not create the alert."));
    }
  };

  const removeAlert = async (id) => {
    await api.delete("/alerts", { data: { id } });
    loadAll();
  };

  const checkNow = async () => {
    setChecking(true);
    setError("");
    try {
      const { data } = await api.post("/alerts/check");
      setLastChecked({
        triggered: data.triggered.length,
        at: new Date().toLocaleTimeString(),
      });
      loadAll();
    } catch (requestError) {
      setError(errorMessage(requestError, "Alert check failed."));
    } finally {
      setChecking(false);
    }
  };

  if (!user?.authenticated) {
    return (
      <section className="card">
        <h2 className="card-title">Alerts</h2>
        <p className="card-hint">
          Sign in to create price, RSI, crossover, and volume alerts that are
          checked against live market data.
        </p>
        <p className="note">Use the Sign in button in the header to enable alerts.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2 className="card-title">Alerts</h2>
      <p className="card-hint">
        Threshold and crossover alerts evaluated against fresh Yahoo Finance
        data. Triggered alerts appear in the event feed below.
      </p>

      <form onSubmit={createAlert} className="row">
        <div className="field" style={{ flex: "1 1 160px" }}>
          <label className="field-label">Symbol</label>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} required />
        </div>
        <div className="field" style={{ flex: "2 1 220px" }}>
          <label className="field-label">Condition</label>
          <select value={conditionType} onChange={(e) => setConditionType(e.target.value)}>
            {CONDITIONS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        {needsThreshold && (
          <div className="field" style={{ flex: "1 1 120px" }}>
            <label className="field-label">Threshold</label>
            <input
              type="number"
              step="any"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              required
            />
          </div>
        )}
        <button type="submit" className="btn">Create alert</button>
        <button type="button" className="btn" onClick={checkNow} disabled={checking}>
          {checking ? "Checking..." : "Check now"}
        </button>
      </form>

      {lastChecked && (
        <p className="note">
          Last check {lastChecked.at}: {lastChecked.triggered} alert(s) triggered.
        </p>
      )}
      {error && <div className="alert" role="alert">{error}</div>}

      <h3 className="section-title" style={{ marginTop: "22px" }}>Active alerts ({alerts.length})</h3>
      {alerts.length === 0 ? (
        <p className="note">No alerts yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Condition</th>
              <th className="right">Threshold</th>
              <th>Last triggered</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id}>
                <td><strong>{alert.symbol}</strong></td>
                <td>{CONDITIONS.find((c) => c[0] === alert.condition_type)?.[1] || alert.condition_type}</td>
                <td className="right">{alert.threshold ?? "\u2014"}</td>
                <td>{alert.last_triggered_at ? alert.last_triggered_at.slice(0, 16).replace("T", " ") : "Never"}</td>
                <td>
                  <button type="button" className="btn btn-small" onClick={() => removeAlert(alert.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 className="section-title" style={{ marginTop: "22px" }}>Recent triggers</h3>
      {events.length === 0 ? (
        <p className="note">Nothing has triggered yet.</p>
      ) : (
        <ul className="event-list">
          {events.map((event) => (
            <li key={event.id}>
              <span className="event-time">{event.triggered_at.slice(0, 16).replace("T", " ")}</span>
              <span>{event.message}</span>
              {event.price != null && <span className="event-price">{formatAmount(event.price)}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
