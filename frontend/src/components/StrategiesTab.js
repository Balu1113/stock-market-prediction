import { useState } from "react";
import Plot from "react-plotly.js";
import { api, errorMessage } from "../api";
import { formatAmount, formatPercent, parsePlot } from "../format";

const STRATEGIES = [
  ["cross", "Golden/Death cross (SMA 20/50)"],
  ["rsi_reversion", "RSI mean reversion"],
  ["supertrend", "Supertrend flip"],
  ["macd_cross", "MACD crossover"],
];

export default function StrategiesTab() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("cross");
  const [capital, setCapital] = useState(10000);
  const [period, setPeriod] = useState("2y");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const run = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/backtest", {
        symbol: symbol.trim(),
        strategy,
        initial_capital: capital,
        period,
      });
      setResult(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Backtest failed."));
    } finally {
      setLoading(false);
    }
  };

  const plot = result?.plot ? parsePlot(result.plot) : null;

  return (
    <section className="card">
      <h2 className="card-title">Strategy Backtester</h2>
      <p className="card-hint">
        No-code backtests with buy/sell markers, equity curve, and a full trade
        log — same engine the analysis page uses, exposed as standalone presets.
      </p>

      <form onSubmit={run}>
        <div className="field-grid">
          <div className="field">
            <label className="field-label">Symbol (NSE)</label>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} required />
          </div>
          <div className="field">
            <label className="field-label">Strategy</label>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              {STRATEGIES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Initial capital</label>
            <input
              type="number"
              min="1"
              value={capital}
              onChange={(e) => setCapital(Math.max(1, parseFloat(e.target.value) || 10000))}
            />
          </div>
          <div className="field">
            <label className="field-label">History</label>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="1y">1 year</option>
              <option value="2y">2 years</option>
              <option value="5y">5 years</option>
            </select>
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: "16px" }}>
          {loading ? "Running backtest..." : "Run backtest"}
        </button>
      </form>

      {error && <div className="alert" role="alert">{error}</div>}

      {result && (
        <div style={{ marginTop: "24px" }}>
          <div className="metrics-grid">
            <div className="stat">
              <span className="stat-label">Final capital</span>
              <span className="stat-value">{formatAmount(result.metrics.final_capital)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Total P&amp;L</span>
              <span className={`stat-value ${result.metrics.total_pnl >= 0 ? "positive" : "negative"}`}>
                {formatAmount(result.metrics.total_pnl)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Trades</span>
              <span className="stat-value">{result.metrics.total_trades}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Win rate</span>
              <span className="stat-value">{result.metrics.win_rate.toFixed(1)}%</span>
            </div>
            <div className="stat">
              <span className="stat-label">Buy &amp; hold return</span>
              <span className={`stat-value ${(result.metrics.buy_hold_return_pct || 0) >= 0 ? "positive" : "negative"}`}>
                {formatPercent(result.metrics.buy_hold_return_pct)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Avg return / trade</span>
              <span className={`stat-value ${result.metrics.avg_return >= 0 ? "positive" : "negative"}`}>
                {formatPercent(result.metrics.avg_return)}
              </span>
            </div>
          </div>

          {plot && (
            <div className="plot-wrap" style={{ marginTop: "20px" }}>
              <Plot data={plot.data} layout={plot.layout} style={{ width: "100%", height: "620px" }} useResizeHandler />
            </div>
          )}

          {result.trades.length > 0 && (
            <>
              <h3 className="section-title" style={{ marginTop: "22px" }}>Trade log</h3>
              <div style={{ overflowX: "auto", maxHeight: "320px" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Entry</th>
                      <th className="right">Entry price</th>
                      <th>Exit</th>
                      <th className="right">Exit price</th>
                      <th className="right">Qty</th>
                      <th className="right">P&amp;L</th>
                      <th className="right">Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((trade, index) => (
                      <tr key={`${trade.entry_date}-${index}`}>
                        <td>{trade.entry_date}</td>
                        <td className="right">{formatAmount(trade.entry_price)}</td>
                        <td>{trade.exit_date}</td>
                        <td className="right">{formatAmount(trade.exit_price)}</td>
                        <td className="right">{trade.quantity}</td>
                        <td className={`right ${trade.pnl >= 0 ? "positive" : "negative"}`}>
                          {formatAmount(trade.pnl)}
                        </td>
                        <td className={`right ${trade.return_pct >= 0 ? "positive" : "negative"}`}>
                          {formatPercent(trade.return_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
