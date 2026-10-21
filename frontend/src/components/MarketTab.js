import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { formatAmount, formatPercent } from "../format";

function SymbolTable({ title, rows, onOpenSymbol }) {
  if (!rows?.length) return null;
  return (
    <div style={{ marginBottom: "20px" }}>
      <h3 className="section-title">{title}</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="right">Price</th>
            <th className="right">Change</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td>
                <strong>{row.label}</strong>
                {row.sector && <span className="muted-inline"> · {row.sector}</span>}
              </td>
              <td className="right">{formatAmount(row.price)}</td>
              <td className={`right ${row.change_pct >= 0 ? "positive" : "negative"}`}>
                {formatPercent(row.change_pct)}
              </td>
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
  );
}

export default function MarketTab({ onOpenSymbol }) {
  const [breadth, setBreadth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/market/breadth");
      setBreadth(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load market breadth."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const ratio = breadth
    ? breadth.advancers / Math.max(1, breadth.advancers + breadth.decliners)
    : 0;

  return (
    <section className="card">
      <h2 className="card-title">Market Dashboard</h2>
      <p className="card-hint">
        Nifty 50 breadth — advance/decline, new 52-week highs/lows, and sector
        performance (cached for 15 minutes).
      </p>
      <button type="button" className="btn" onClick={load} disabled={loading}>
        {loading ? "Loading..." : "Refresh"}
      </button>

      {error && <div className="alert" role="alert">{error}</div>}

      {breadth && (
        <>
          <div className="metrics-grid" style={{ marginTop: "20px" }}>
            <div className="stat">
              <span className="stat-label">Nifty 50</span>
              <span className={`stat-value ${(breadth.index?.change_pct || 0) >= 0 ? "positive" : "negative"}`}>
                {breadth.index ? formatAmount(breadth.index.value) : "\u2014"}
                {breadth.index && (
                  <span style={{ fontSize: "0.9rem", marginLeft: "8px" }}>
                    {formatPercent(breadth.index.change_pct)}
                  </span>
                )}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Advancers</span>
              <span className="stat-value positive">{breadth.advancers}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Decliners</span>
              <span className="stat-value negative">{breadth.decliners}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Unchanged</span>
              <span className="stat-value">{breadth.unchanged}</span>
            </div>
            <div className="stat">
              <span className="stat-label">New 52w highs</span>
              <span className="stat-value">{breadth.new_highs.length}</span>
            </div>
            <div className="stat">
              <span className="stat-label">New 52w lows</span>
              <span className="stat-value">{breadth.new_lows.length}</span>
            </div>
          </div>

          <div className="breadth-bar" aria-hidden="true">
            <div className="breadth-adv" style={{ width: `${ratio * 100}%` }} />
            <div className="breadth-dec" style={{ width: `${(1 - ratio) * 100}%` }} />
          </div>
          <p className="note" style={{ marginTop: "6px" }}>
            {Math.round(ratio * 100)}% of traded Nifty constituents advanced.
          </p>

          <SymbolTable title="Top gainers" rows={breadth.top_gainers} onOpenSymbol={onOpenSymbol} />
          <SymbolTable title="Top losers" rows={breadth.top_losers} onOpenSymbol={onOpenSymbol} />

          {breadth.sectors.length > 0 && (
            <>
              <h3 className="section-title">Sector performance (avg)</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Sector</th>
                    <th className="right">Avg change</th>
                    <th className="right">Constituents</th>
                  </tr>
                </thead>
                <tbody>
                  {breadth.sectors.map((sector) => (
                    <tr key={sector.sector}>
                      <td>{sector.sector}</td>
                      <td className={`right ${sector.avg_change_pct >= 0 ? "positive" : "negative"}`}>
                        {formatPercent(sector.avg_change_pct)}
                      </td>
                      <td className="right">{sector.constituents}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </section>
  );
}
