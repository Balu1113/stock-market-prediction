import { useCallback, useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { api, errorMessage } from "../api";
import { formatAmount, formatPercent } from "../format";

export default function PortfolioTab({ user }) {
  const [portfolio, setPortfolio] = useState(null);
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/portfolio/summary");
      setPortfolio(data);
    } catch {
      /* backend offline */
    }
  }, []);

  useEffect(() => {
    if (user?.authenticated) load();
  }, [user, load]);

  const addHolding = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/portfolio/holdings", {
        symbol: symbol.trim(),
        quantity: parseFloat(quantity),
        average_price: parseFloat(price),
      });
      setSymbol("");
      setQuantity("");
      setPrice("");
      load();
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not save the holding."));
    }
  };

  const removeHolding = async (id) => {
    await api.delete("/portfolio/holdings", { data: { id } });
    load();
  };

  if (!user?.authenticated) {
    return (
      <section className="card">
        <h2 className="card-title">Portfolio</h2>
        <p className="card-hint">
          Track holdings, P&amp;L, allocation, and performance versus the Nifty
          50. Sign in to enable the portfolio.
        </p>
        <p className="note">Use the Sign in button in the header.</p>
      </section>
    );
  }

  const pie = portfolio?.allocation?.length
    ? {
        data: [
          {
            labels: portfolio.allocation.map((row) => row.label),
            values: portfolio.allocation.map((row) => row.weight || 0),
            type: "pie",
            hole: 0.45,
            marker: { colors: ["#4f8cff", "#2fd48a", "#7c5cff", "#ffb45e", "#ff6b6b", "#5ad1e6"] },
          },
        ],
        layout: {
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: "#cbd5e1" },
          height: 320,
          margin: { t: 20, b: 20, l: 20, r: 20 },
          showlegend: true,
        },
      }
    : null;

  return (
    <section className="card">
      <h2 className="card-title">Portfolio</h2>
      <p className="card-hint">
        Holdings with live valuation from Yahoo Finance, P&amp;L, allocation,
        and a Nifty 50 benchmark comparison.
      </p>

      <form onSubmit={addHolding} className="row">
        <div className="field" style={{ flex: "1 1 150px" }}>
          <label className="field-label">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="INFY"
            required
          />
        </div>
        <div className="field" style={{ flex: "1 1 110px" }}>
          <label className="field-label">Quantity</label>
          <input type="number" min="0.01" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
        </div>
        <div className="field" style={{ flex: "1 1 130px" }}>
          <label className="field-label">Avg price</label>
          <input type="number" min="0.01" step="any" value={price} onChange={(e) => setPrice(e.target.value)} required />
        </div>
        <button type="submit" className="btn">Add / update</button>
      </form>
      {error && <div className="alert" role="alert">{error}</div>}

      {portfolio && (
        <>
          <div className="metrics-grid" style={{ marginTop: "20px" }}>
            <div className="stat">
              <span className="stat-label">Market value</span>
              <span className="stat-value">{formatAmount(portfolio.summary.total_value)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Total cost</span>
              <span className="stat-value">{formatAmount(portfolio.summary.total_cost)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Total P&amp;L</span>
              <span className={`stat-value ${portfolio.summary.total_pnl >= 0 ? "positive" : "negative"}`}>
                {formatAmount(portfolio.summary.total_pnl)}{" "}
                ({formatPercent(portfolio.summary.total_pnl_pct)})
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Nifty 50 (1y)</span>
              <span className={`stat-value ${(portfolio.benchmark?.return_1y_pct || 0) >= 0 ? "positive" : "negative"}`}>
                {formatPercent(portfolio.benchmark?.return_1y_pct)}
              </span>
            </div>
          </div>

          {pie && (
            <div className="plot-wrap" style={{ marginTop: "20px", maxWidth: "420px" }}>
              <Plot data={pie.data} layout={pie.layout} useResizeHandler style={{ width: "100%" }} />
            </div>
          )}

          <h3 className="section-title" style={{ marginTop: "22px" }}>Holdings</h3>
          {portfolio.holdings.length === 0 ? (
            <p className="note">Add your first holding above.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th className="right">Qty</th>
                    <th className="right">Avg price</th>
                    <th className="right">LTP</th>
                    <th className="right">Value</th>
                    <th className="right">P&amp;L</th>
                    <th className="right">Return</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {portfolio.holdings.map((holding) => (
                    <tr key={holding.id}>
                      <td><strong>{holding.label}</strong></td>
                      <td className="right">{holding.quantity}</td>
                      <td className="right">{formatAmount(holding.average_price)}</td>
                      <td className="right">{formatAmount(holding.current_price)}</td>
                      <td className="right">{formatAmount(holding.value)}</td>
                      <td className={`right ${(holding.pnl || 0) >= 0 ? "positive" : "negative"}`}>
                        {formatAmount(holding.pnl)}
                      </td>
                      <td className={`right ${(holding.pnl_pct || 0) >= 0 ? "positive" : "negative"}`}>
                        {formatPercent(holding.pnl_pct)}
                      </td>
                      <td>
                        <button type="button" className="btn btn-small" onClick={() => removeHolding(holding.id)}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {portfolio.benchmark && (
            <div className="metrics-grid" style={{ marginTop: "18px" }}>
              <div className="stat">
                <span className="stat-label">Nifty 50 · 1m</span>
                <span className="stat-value">{formatPercent(portfolio.benchmark.return_1m_pct)}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Nifty 50 · 3m</span>
                <span className="stat-value">{formatPercent(portfolio.benchmark.return_3m_pct)}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Nifty 50 · 1y</span>
                <span className="stat-value">{formatPercent(portfolio.benchmark.return_1y_pct)}</span>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
