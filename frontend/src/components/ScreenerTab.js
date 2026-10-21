import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { formatAmount, formatPercent } from "../format";

const FIELDS = [
  ["close", "Close price"],
  ["volume", "Volume"],
  ["change_pct", "Change % (1d)"],
  ["ret_21d", "Return % (1m)"],
  ["ret_63d", "Return % (3m)"],
  ["RSI", "RSI (14)"],
  ["MA20", "SMA 20"],
  ["MA50", "SMA 50"],
  ["MACD", "MACD"],
  ["BB_pctb", "Bollinger %B"],
  ["BB_width", "Bollinger width"],
  ["SUPERTREND_DIST", "Supertrend distance"],
  ["SUPERTREND_DIR", "Supertrend direction"],
  ["STOCH_K", "Stochastic %K"],
  ["ADX", "ADX"],
  ["CLOSE_VWAP_RATIO", "Close / VWAP"],
  ["OBV_CHANGE_5", "OBV momentum"],
];

const OPS = [
  ["gt", ">"],
  ["gte", ">="],
  ["lt", "<"],
  ["lte", "<="],
  ["eq", "="],
  ["crosses_above", "crosses above"],
  ["crosses_below", "crosses below"],
];

const PRESETS = [
  {
    name: "RSI oversold",
    rules: { op: "AND", conditions: [{ condition: { field: "RSI", op: "lt", value: 30 } }] },
  },
  {
    name: "Supertrend bullish",
    rules: {
      op: "AND",
      conditions: [
        { condition: { field: "SUPERTREND_DIR", op: "gt", value: 0 } },
        { condition: { field: "close", op: "gt", value: 0 } },
      ],
    },
  },
  {
    name: "MACD positive + SMA uptrend",
    rules: {
      op: "AND",
      conditions: [
        { condition: { field: "MACD", op: "gt", value: 0 } },
        { condition: { field: "MA20", op: "gt", value: 0 } },
        { condition: { field: "close", op: "gt", value: 0 } },
      ],
    },
  },
  {
    name: "Above average volume",
    rules: {
      op: "AND",
      conditions: [{ condition: { field: "volume", op: "gt", value: 0 } }],
    },
  },
];

function defaultCondition() {
  return { field: "RSI", op: "lt", value: 30 };
}

export default function ScreenerTab({ onOpenSymbol }) {
  const [conditions, setConditions] = useState([defaultCondition()]);
  const [combine, setCombine] = useState("AND");
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scans, setScans] = useState([]);
  const [scanName, setScanName] = useState("");
  const [backtestSymbol, setBacktestSymbol] = useState("");
  const [backtest, setBacktest] = useState(null);
  const [btLoading, setBtLoading] = useState(false);

  const loadScans = useCallback(async () => {
    try {
      const { data } = await api.get("/screener/scans");
      setScans(data.scans);
    } catch {
      /* backend offline */
    }
  }, []);

  useEffect(() => {
    loadScans();
  }, [loadScans]);

  const buildRules = () => ({
    op: combine,
    conditions: conditions.map((condition) => ({ condition })),
  });

  const updateCondition = (index, patch) => {
    setConditions((prev) =>
      prev.map((condition, i) => (i === index ? { ...condition, ...patch } : condition))
    );
  };

  const runScan = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/screener/scan", { rules: buildRules() });
      setMatches(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Scan failed."));
    } finally {
      setLoading(false);
    }
  };

  const saveScan = async () => {
    if (!scanName.trim()) return;
    try {
      await api.post("/screener/scans", { name: scanName.trim(), rules: buildRules() });
      setScanName("");
      loadScans();
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not save the scan."));
    }
  };

  const loadScan = (scan) => {
    const conds = (scan.rules.conditions || []).map((item) => item.condition || item);
    setConditions(conds.length ? conds : [defaultCondition()]);
    setCombine(scan.rules.op || "AND");
  };

  const deleteScan = async (id) => {
    await api.delete("/screener/scans", { data: { id } });
    loadScans();
  };

  const runBacktest = async () => {
    if (!backtestSymbol.trim()) return;
    setBtLoading(true);
    setError("");
    try {
      const { data } = await api.post("/screener/backtest", {
        rules: buildRules(),
        symbol: backtestSymbol.trim(),
        months: 12,
        forward_days: 5,
      });
      setBacktest(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Backtest failed."));
    } finally {
      setBtLoading(false);
    }
  };

  return (
    <section className="card">
      <h2 className="card-title">Stock Screener</h2>
      <p className="card-hint">
        Chartink-style rule scanner over the Nifty 50. Combine conditions on
        price, volume, and technical indicators; backtest a rule on one symbol.
      </p>

      <div className="chip-row" style={{ marginBottom: "16px" }}>
        {PRESETS.map((preset) => (
          <button
            key={preset.name}
            type="button"
            className="chip"
            onClick={() => {
              const conds = preset.rules.conditions.map((item) => item.condition);
              setConditions(conds);
              setCombine(preset.rules.op || "AND");
            }}
          >
            {preset.name}
          </button>
        ))}
      </div>

      <div className="row" style={{ marginBottom: "12px" }}>
        <div className="field" style={{ flex: "0 0 140px" }}>
          <label className="field-label">Combine with</label>
          <select value={combine} onChange={(e) => setCombine(e.target.value)}>
            <option value="AND">AND (all)</option>
            <option value="OR">OR (any)</option>
          </select>
        </div>
      </div>

      {conditions.map((condition, index) => (
        <div className="row condition-row" key={index}>
          <div className="field" style={{ flex: "2 1 200px" }}>
            <label className="field-label">Field</label>
            <select
              value={condition.field}
              onChange={(e) => updateCondition(index, { field: e.target.value })}
            >
              {FIELDS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 140px" }}>
            <label className="field-label">Operator</label>
            <select
              value={condition.op}
              onChange={(e) => updateCondition(index, { op: e.target.value })}
            >
              {OPS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 110px" }}>
            <label className="field-label">Value</label>
            <input
              type="number"
              step="any"
              value={condition.value}
              onChange={(e) => updateCondition(index, { value: parseFloat(e.target.value) })}
            />
          </div>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => setConditions((prev) => prev.filter((_, i) => i !== index))}
            disabled={conditions.length === 1}
          >
            Remove
          </button>
        </div>
      ))}

      <div className="row" style={{ marginTop: "16px" }}>
        <button
          type="button"
          className="btn"
          onClick={() => setConditions((prev) => [...prev, defaultCondition()])}
        >
          Add condition
        </button>
        <button type="button" className="btn btn-primary" style={{ width: "auto" }} onClick={runScan} disabled={loading}>
          {loading ? "Scanning..." : "Run scan"}
        </button>
        <input
          style={{ flex: "1 1 180px" }}
          placeholder="Save scan as..."
          value={scanName}
          onChange={(e) => setScanName(e.target.value)}
        />
        <button type="button" className="btn" onClick={saveScan} disabled={!scanName.trim()}>
          Save
        </button>
      </div>

      {scans.length > 0 && (
        <div className="saved-scans">
          <span className="field-label">Saved scans</span>
          <div className="chip-row">
            {scans.map((scan) => (
              <span key={scan.id} className="chip">
                <button type="button" className="link-button" onClick={() => loadScan(scan)}>
                  {scan.name}
                </button>
                <button type="button" className="link-button danger" onClick={() => deleteScan(scan.id)}>
                  ✕
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {error && <div className="alert" role="alert">{error}</div>}

      {matches && (
        <div style={{ marginTop: "20px" }}>
          <h3 className="section-title">{matches.count} matches (Nifty 50)</h3>
          {matches.count === 0 ? (
            <p className="note">No stocks passed these filters today.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th className="right">Close</th>
                    <th className="right">Change</th>
                    <th className="right">RSI</th>
                    <th className="right">SMA 20</th>
                    <th className="right">SMA 50</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {matches.matches.map((row) => (
                    <tr key={row.symbol}>
                      <td><strong>{row.label}</strong></td>
                      <td className="right">{formatAmount(row.close)}</td>
                      <td className={`right ${row.change_pct >= 0 ? "positive" : "negative"}`}>
                        {formatPercent(row.change_pct)}
                      </td>
                      <td className="right">{row.rsi != null ? row.rsi.toFixed(1) : "\u2014"}</td>
                      <td className="right">{row.sma20 != null ? formatAmount(row.sma20) : "\u2014"}</td>
                      <td className="right">{row.sma50 != null ? formatAmount(row.sma50) : "\u2014"}</td>
                      <td>
                        <button type="button" className="btn btn-small" onClick={() => onOpenSymbol?.(row.symbol)}>
                          Analyze
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <hr className="divider" />
      <h3 className="section-title">Backtest this scan on one symbol</h3>
      <div className="row">
        <div className="field" style={{ flex: "1 1 200px" }}>
          <label className="field-label">Symbol (NSE)</label>
          <input
            placeholder="e.g. RELIANCE"
            value={backtestSymbol}
            onChange={(e) => setBacktestSymbol(e.target.value.toUpperCase())}
          />
        </div>
        <button type="button" className="btn" onClick={runBacktest} disabled={btLoading || !backtestSymbol.trim()}>
          {btLoading ? "Backtesting..." : "Backtest 12 months"}
        </button>
      </div>
      {backtest && (
        <div style={{ marginTop: "16px" }}>
          <div className="metrics-grid">
            <div className="stat">
              <span className="stat-label">Total signals</span>
              <span className="stat-value">{backtest.total_signals}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Hit rate (5d forward)</span>
              <span className="stat-value">
                {backtest.overall_hit_rate != null ? `${backtest.overall_hit_rate.toFixed(1)}%` : "\u2014"}
              </span>
            </div>
          </div>
          {backtest.months.length > 0 && (
            <table className="data-table" style={{ marginTop: "14px" }}>
              <thead>
                <tr>
                  <th>Month</th>
                  <th className="right">Signals</th>
                  <th className="right">Hit rate</th>
                  <th className="right">Avg forward return</th>
                </tr>
              </thead>
              <tbody>
                {backtest.months.map((row) => (
                  <tr key={row.month}>
                    <td>{row.month}</td>
                    <td className="right">{row.signals}</td>
                    <td className="right">{row.hit_rate != null ? `${row.hit_rate.toFixed(1)}%` : "\u2014"}</td>
                    <td className={`right ${(row.avg_forward_return_pct || 0) >= 0 ? "positive" : "negative"}`}>
                      {formatPercent(row.avg_forward_return_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
