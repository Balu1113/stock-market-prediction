import { useState } from "react";
import Plot from "react-plotly.js";
import { api, errorMessage } from "../api";
import { formatAmount, formatPercent, parsePlot } from "../format";

export default function TopPicksTab({ onOpenSymbol }) {
  const [limit, setLimit] = useState(15);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);

  const runRank = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/rank", { limit });
      setResults(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not rank symbols."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <h2 className="card-title">Top Picks</h2>
      <p className="card-hint">
        Ranks the Nifty 50 by a lightweight next-day forecast blended with the
        composite stock score (momentum, trend, volatility, volume, model).
      </p>

      <div className="row" style={{ marginBottom: "18px" }}>
        <div className="field" style={{ flex: "0 0 160px" }}>
          <label className="field-label">Number of picks</label>
          <input
            type="number"
            min="5"
            max="50"
            value={limit}
            onChange={(e) => setLimit(Math.max(5, Math.min(50, parseInt(e.target.value) || 15)))}
          />
        </div>
        <button type="button" className="btn btn-primary" style={{ width: "auto" }} onClick={runRank} disabled={loading}>
          {loading ? "Ranking (may take a minute)..." : "Rank Nifty 50"}
        </button>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}

      {loading && (
        <div className="spinner-row">
          <span className="spinner" />
          Scoring and forecasting each symbol...
        </div>
      )}

      {results && (
        <>
          <p className="note" style={{ marginTop: 0 }}>
            {results.count} symbols ranked &middot; {results.ranked_at?.slice(0, 16).replace("T", " ")} UTC
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Symbol</th>
                  <th className="right">Price</th>
                  <th className="right">Pred. next day</th>
                  <th className="right">Score</th>
                  <th>Rating</th>
                  <th>Signals</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {results.results.map((row, index) => (
                  <tr key={row.symbol}>
                    <td>{index + 1}</td>
                    <td>
                      <strong>{row.label}</strong>
                      {row.sector && <span className="muted-inline"> · {row.sector}</span>}
                    </td>
                    <td className="right">{formatAmount(row.price)}</td>
                    <td className={`right ${row.predicted_return_pct >= 0 ? "positive" : "negative"}`}>
                      {formatPercent(row.predicted_return_pct, 3)}
                    </td>
                    <td className="right">
                      <span className={`score-pill score-${row.rating.toLowerCase()}`}>{row.score}</span>
                    </td>
                    <td>{row.rating}</td>
                    <td className="patterns-cell">
                      {(row.patterns || []).map((pattern) => (
                        <span key={pattern} className="pattern-chip">{pattern}</span>
                      ))}
                      {row.score_summary && <span className="note-inline">{row.score_summary}</span>}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-small"
                        onClick={() => onOpenSymbol?.(row.symbol)}
                      >
                        Analyze
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

export function SeasonalityPanel({ symbol }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [plot, setPlot] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/yahoo/seasonality", { params: { symbol } });
      setPlot(parsePlot(data.plot));
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load seasonality."));
    } finally {
      setLoading(false);
    }
  };

  if (!symbol) return null;

  return (
    <div style={{ marginBottom: "30px" }}>
      <h3 className="section-title">
        Seasonality
        <button type="button" className="btn btn-small" style={{ marginLeft: "12px" }} onClick={load} disabled={loading}>
          {loading ? "Loading..." : `Load for ${symbol}`}
        </button>
      </h3>
      {error && <div className="alert">{error}</div>}
      {plot && (
        <div className="plot-wrap">
          <Plot
            data={plot.data}
            layout={plot.layout}
            style={{ width: "100%", height: "640px" }}
            useResizeHandler
          />
        </div>
      )}
    </div>
  );
}
