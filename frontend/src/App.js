import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import Plot from "react-plotly.js";
import "./App.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000/api";

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function parsePlot(plot) {
  try {
    const parsed = JSON.parse(plot);
    return {
      data: parsed.data,
      layout: {
        ...parsed.layout,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { ...parsed.layout?.font, color: "#cbd5e1" },
      },
    };
  } catch {
    return null;
  }
}

const CURRENCY_SYMBOLS = {
  INR: "\u20b9",
  USD: "$",
  EUR: "\u20ac",
  GBP: "\u00a3",
  JPY: "\u00a5",
};

function currencySymbol(code) {
  if (!code) return "$";
  const upper = code.toUpperCase();
  return CURRENCY_SYMBOLS[upper] || `${upper} `;
}

function formatAmount(value, code) {
  if (value == null || Number.isNaN(Number(value))) return "\u2014";
  return `${currencySymbol(code)}${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSigned(value, code) {
  if (value == null || Number.isNaN(Number(value))) return "\u2014";
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${formatAmount(Math.abs(value), code)}`;
}

function LivePrice({ quote, loading, error, currency, onRefresh }) {
  if (error) {
    return (
      <div className="live-price">
        <div>
          <span className="live-price-label">Current price</span>
          <div className="live-price-value muted">Unavailable</div>
        </div>
        <button type="button" className="btn" onClick={onRefresh}>
          Retry
        </button>
      </div>
    );
  }

  if (!quote) {
    return (
      <div className="live-price">
        <div>
          <span className="live-price-label">Current price</span>
          <div className="live-price-value muted">
            {loading ? "Loading..." : "\u2014"}
          </div>
        </div>
        {loading && <span className="spinner" />}
      </div>
    );
  }

  const up = quote.change == null ? null : quote.change >= 0;
  return (
    <div className="live-price">
      <div>
        <span className="live-price-label">Current price</span>
        <div className="live-price-value">
          {formatAmount(quote.price, currency)}
          {up != null && (
            <span className={`live-change ${up ? "positive" : "negative"}`}>
              {formatSigned(quote.change, currency)}
              {quote.change_percent != null &&
                ` (${quote.change_percent >= 0 ? "+" : ""}${quote.change_percent.toFixed(2)}%)`}
            </span>
          )}
        </div>
      </div>
      <div className="live-meta">
        {quote.latest_trading_day && (
          <span>As of {quote.latest_trading_day}</span>
        )}
        <button type="button" className="btn" onClick={onRefresh}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>
    </div>
  );
}

function App() {
  const initialToDate = new Date();
  const initialFromDate = new Date();
  initialFromDate.setDate(initialFromDate.getDate() - 365);

  const [file, setFile] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState("csv");
  const [modelType, setModelType] = useState("Ridge Regression");
  const [features, setFeatures] = useState([]);
  const [trainSize, setTrainSize] = useState(80);
  const [predictionDays, setPredictionDays] = useState(7);
  const [simulateTrading, setSimulateTrading] = useState(false);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [yahooSearchQuery, setYahooSearchQuery] = useState("");
  const [yahooSymbols, setYahooSymbols] = useState([]);
  const [yahooSymbol, setYahooSymbol] = useState("");
  const [kiteConfigured, setKiteConfigured] = useState(false);
  const [kiteConnected, setKiteConnected] = useState(false);
  const [kiteUserName, setKiteUserName] = useState("");
  const [kiteMessage, setKiteMessage] = useState("");
  const [exchange, setExchange] = useState("NSE");
  const [symbolQuery, setSymbolQuery] = useState("");
  const [instruments, setInstruments] = useState([]);
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  const [interval, setInterval] = useState("day");
  const [fromDate, setFromDate] = useState(formatDate(initialFromDate));
  const [toDate, setToDate] = useState(formatDate(initialToDate));
  const [error, setError] = useState("");
  const [livePrice, setLivePrice] = useState(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState("");

  useEffect(() => {
    const callbackResult = new URLSearchParams(window.location.search).get(
      "kite",
    );
    if (callbackResult) {
      setKiteMessage(
        callbackResult === "connected"
          ? "Kite account connected."
          : "Kite login was not completed. Please try again.",
      );
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    axios
      .get(`${API_BASE}/kite/status`, { withCredentials: true })
      .then(({ data }) => {
        setKiteConfigured(data.configured);
        setKiteConnected(data.connected);
        setKiteUserName(data.user_name || "");
      })
      .catch(() =>
        setKiteMessage("Start the Django backend to use Kite Connect."),
      );
  }, []);

  const fetchLivePrice = useCallback(async () => {
    if (source === "yahoo") {
      if (!yahooSymbol) {
        setLivePrice(null);
        return;
      }
      setLiveLoading(true);
      setLiveError("");
      try {
        const { data } = await axios.get(`${API_BASE}/yahoo/quote`, {
          params: { symbol: yahooSymbol },
        });
        setLivePrice({ ...data, currency: data.currency || "INR" });
      } catch (requestError) {
        setLivePrice(null);
        setLiveError(
          requestError.response?.data?.error ||
            "Could not load the live price.",
        );
      } finally {
        setLiveLoading(false);
      }
    } else if (source === "kite") {
      if (!kiteConnected || !selectedInstrument) {
        setLivePrice(null);
        return;
      }
      setLiveLoading(true);
      setLiveError("");
      try {
        const { data } = await axios.get(`${API_BASE}/kite/quote`, {
          params: {
            exchange,
            tradingsymbol: selectedInstrument.tradingsymbol,
            instrument_token: selectedInstrument.instrument_token,
          },
          withCredentials: true,
        });
        setLivePrice({ ...data, currency: "INR" });
      } catch (requestError) {
        setLivePrice(null);
        setLiveError(
          requestError.response?.data?.error ||
            "Could not load the live price.",
        );
      } finally {
        setLiveLoading(false);
      }
    } else {
      setLivePrice(null);
    }
  }, [
    source,
    yahooSymbol,
    kiteConnected,
    selectedInstrument,
    exchange,
  ]);

  useEffect(() => {
    fetchLivePrice();
  }, [fetchLivePrice]);

  useEffect(() => {
    const ready =
      (source === "yahoo" && yahooSymbol) ||
      (source === "kite" && kiteConnected && selectedInstrument);
    if (!ready) return undefined;
    const timer = window.setInterval(fetchLivePrice, 30000);
    return () => window.clearInterval(timer);
  }, [fetchLivePrice, source, yahooSymbol, kiteConnected, selectedInstrument]);

  const handleFeatureChange = (e) => {
    const { value, checked } = e.target;
    if (checked) {
      setFeatures((prev) => [...prev, value]);
    } else {
      setFeatures((prev) => prev.filter((feature) => feature !== value));
    }
  };

  const handleKiteConnect = () => {
    const returnTo = encodeURIComponent(window.location.origin);
    window.location.href = `${API_BASE}/kite/login?return_to=${returnTo}`;
  };

  const handleKiteDisconnect = async () => {
    try {
      await axios.post(
        `${API_BASE}/kite/disconnect`,
        {},
        { withCredentials: true },
      );
      setKiteConnected(false);
      setKiteUserName("");
      setSelectedInstrument(null);
      setInstruments([]);
      setKiteMessage("Kite account disconnected.");
    } catch {
      setKiteMessage("Could not disconnect from Kite.");
    }
  };

  const handleYahooSymbolSearch = async () => {
    setError("");
    setYahooSymbols([]);
    setYahooSymbol("");
    try {
      const { data } = await axios.get(`${API_BASE}/yahoo/symbols`, {
        params: { keywords: yahooSearchQuery.trim() },
      });
      setYahooSymbols(data.symbols);
      if (data.symbols.length === 0)
        setError("No matching NSE/BSE symbols found.");
    } catch (requestError) {
      setError(
        requestError.response?.data?.error ||
          "Could not search Yahoo Finance symbols.",
      );
    }
  };

  const handleInstrumentSearch = async (e) => {
    e.preventDefault();
    setError("");
    setInstruments([]);
    setSelectedInstrument(null);
    try {
      const { data } = await axios.get(`${API_BASE}/kite/instruments`, {
        params: { exchange, q: symbolQuery },
        withCredentials: true,
      });
      setInstruments(data.instruments);
      if (data.instruments.length === 0)
        setKiteMessage("No matching equity symbols found.");
    } catch (requestError) {
      setError(
        requestError.response?.data?.error ||
          "Could not search Kite instruments.",
      );
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResults(null);
    setError("");

    try {
      let response;
      if (source === "csv") {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("model_type", modelType);
        features.forEach((feature) => formData.append("features[]", feature));
        formData.append("train_size", trainSize);
        formData.append("prediction_days", predictionDays);
        formData.append("simulate_trading", simulateTrading);
        if (simulateTrading) formData.append("initial_capital", initialCapital);
        response = await axios.post(`${API_BASE}/predict`, formData);
      } else if (source === "yahoo") {
        response = await axios.post(`${API_BASE}/predict/yahoo`, {
          symbol: yahooSymbol,
          model_type: modelType,
          features,
          train_size: trainSize,
          prediction_days: predictionDays,
          simulate_trading: simulateTrading,
          initial_capital: initialCapital,
        });
      } else {
        response = await axios.post(
          `${API_BASE}/predict/kite`,
          {
            exchange,
            instrument_token: selectedInstrument.instrument_token,
            tradingsymbol: selectedInstrument.tradingsymbol,
            from_date: fromDate,
            to_date: toDate,
            interval,
            model_type: modelType,
            features,
            train_size: trainSize,
            prediction_days: predictionDays,
            simulate_trading: simulateTrading,
            initial_capital: initialCapital,
          },
          { withCredentials: true },
        );
      }
      setResults(response.data);
    } catch (requestError) {
      setError(
        requestError.response?.data?.error ||
          "Analysis failed. Check that the backend is running and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const plot = results && results.plot ? parsePlot(results.plot) : null;
  const symbolLabel = results?.instrument?.tradingsymbol
    ? `${results.instrument.exchange}:${results.instrument.tradingsymbol}`
    : results?.instrument?.symbol || "";
  const providerLabel = results?.instrument?.provider || "";
  const resultCurrency =
    results?.instrument?.currency ||
    (source === "csv" ? "" : "INR");

  return (
    <div className="app">
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              &#128200;
            </div>
            <div>
              <h1 className="brand-title">Stock Prediction &amp; Trading</h1>
              <p className="brand-subtitle">
                Forecast prices, backtest strategies, explore markets
              </p>
            </div>
          </div>
          <span className="badge">
            <span className="badge-dot" />
            Powered by ML models
          </span>
        </header>

        <form className="card" onSubmit={handleSubmit}>
          <h2 className="card-title">Configure analysis</h2>
          <p className="card-hint">
            Choose a data source, pick a model, then run the analysis.
          </p>

          <div className="source-tabs" role="group" aria-label="Data source">
            <button
              type="button"
              className={`tab ${source === "csv" ? "active" : ""}`}
              aria-pressed={source === "csv"}
              onClick={() => setSource("csv")}
            >
              Upload CSV
            </button>
            <button
              type="button"
              className={`tab ${source === "yahoo" ? "active" : ""}`}
              aria-pressed={source === "yahoo"}
              onClick={() => setSource("yahoo")}
            >
              Yahoo Finance (NSE/BSE)
            </button>
            <button
              type="button"
              className={`tab ${source === "kite" ? "active" : ""}`}
              aria-pressed={source === "kite"}
              onClick={() => setSource("kite")}
            >
              Zerodha Kite
            </button>
          </div>

          {source === "csv" ? (
            <div className="field">
              <label className="field-label" htmlFor="csv-file">
                Upload CSV file
              </label>
              <input
                id="csv-file"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files[0])}
                required
              />
              <p className="note">
                The file must contain at least Date and Close columns.
              </p>
            </div>
          ) : source === "yahoo" ? (
            <section className="panel" aria-label="Yahoo Finance data source">
              <div className="panel-title">
                Yahoo Finance
                <span className="status-pill ok">No API key needed</span>
              </div>
              <div className="row">
                <div className="field" style={{ flex: "1 1 240px" }}>
                  <label className="field-label">Search stocks</label>
                  <input
                    value={yahooSearchQuery}
                    onChange={(e) => {
                      setYahooSearchQuery(e.target.value);
                      setYahooSymbols([]);
                      setYahooSymbol("");
                    }}
                    placeholder="Company or ticker, e.g. Reliance"
                  />
                </div>
                <button
                  type="button"
                  className="btn"
                  onClick={handleYahooSymbolSearch}
                  disabled={yahooSearchQuery.trim().length < 2}
                >
                  Search
                </button>
              </div>
              {yahooSymbols.length > 0 && (
                <div className="field" style={{ marginTop: "14px" }}>
                  <label className="field-label">Matching stocks</label>
                  <select
                    value={yahooSymbol}
                    onChange={(e) => setYahooSymbol(e.target.value)}
                    required
                  >
                    <option value="">Select a stock</option>
                    {yahooSymbols.map((item) => (
                      <option key={item.symbol} value={item.symbol}>
                        {item.name} ({item.exchange}) - {item.symbol}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {yahooSymbol && (
                <LivePrice
                  quote={livePrice}
                  loading={liveLoading}
                  error={liveError}
                  currency="INR"
                  onRefresh={fetchLivePrice}
                />
              )}
              <p className="note">
                Indian equities only (NSE and BSE). Quotes are near real-time
                during market hours (up to about a 15-minute delay); daily
                history is used for the analysis. No API key or sign-up is
                required. Use Zerodha Kite for a truly live price.
              </p>
            </section>
          ) : (
            <section className="panel" aria-label="Kite data source">
              <div className="panel-title">
                Kite Connect
                <span className={`status-pill ${kiteConnected ? "ok" : "off"}`}>
                  {kiteConnected
                    ? `Connected${kiteUserName ? ` as ${kiteUserName}` : ""}`
                    : "Not connected"}
                </span>
              </div>
              {!kiteConnected ? (
                <button
                  type="button"
                  className="btn"
                  disabled={!kiteConfigured}
                  onClick={handleKiteConnect}
                >
                  Connect Kite account
                </button>
              ) : (
                <button
                  type="button"
                  className="btn"
                  onClick={handleKiteDisconnect}
                >
                  Disconnect
                </button>
              )}
              {!kiteConfigured && (
                <p className="note">
                  Set KITE_API_KEY and KITE_API_SECRET in the backend
                  environment, then restart Django.
                </p>
              )}
              {kiteMessage && (
                <p className="status-line" role="status">
                  {kiteMessage}
                </p>
              )}

              {kiteConnected && (
                <>
                  <div className="row" style={{ marginTop: "16px" }}>
                    <div className="field" style={{ flex: "0 0 120px" }}>
                      <label className="field-label">Exchange</label>
                      <select
                        value={exchange}
                        onChange={(e) => {
                          setExchange(e.target.value);
                          setSelectedInstrument(null);
                        }}
                      >
                        <option value="NSE">NSE</option>
                        <option value="BSE">BSE</option>
                      </select>
                    </div>
                    <div className="field" style={{ flex: "1 1 200px" }}>
                      <label className="field-label">Symbol or company</label>
                      <input
                        value={symbolQuery}
                        onChange={(e) => setSymbolQuery(e.target.value)}
                        placeholder="e.g. INFY"
                      />
                    </div>
                    <button
                      type="button"
                      className="btn"
                      onClick={handleInstrumentSearch}
                      disabled={!symbolQuery.trim()}
                    >
                      Search
                    </button>
                  </div>

                  {instruments.length > 0 && (
                    <div className="field" style={{ marginTop: "14px" }}>
                      <label className="field-label">
                        Matching instruments
                      </label>
                      <select
                        value={selectedInstrument?.instrument_token || ""}
                        onChange={(e) =>
                          setSelectedInstrument(
                            instruments.find(
                              (item) =>
                                item.instrument_token ===
                                Number(e.target.value),
                            ) || null,
                          )
                        }
                      >
                        <option value="">Select a stock</option>
                        {instruments.map((item) => (
                          <option
                            key={item.instrument_token}
                            value={item.instrument_token}
                          >
                            {item.tradingsymbol}
                            {item.name ? ` - ${item.name}` : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="row" style={{ marginTop: "14px" }}>
                    <div className="field" style={{ flex: "1 1 140px" }}>
                      <label className="field-label">Candle interval</label>
                      <select
                        value={interval}
                        onChange={(e) => setInterval(e.target.value)}
                      >
                        <option value="day">Daily</option>
                        <option value="60minute">60 minutes</option>
                        <option value="15minute">15 minutes</option>
                        <option value="5minute">5 minutes</option>
                        <option value="minute">1 minute</option>
                      </select>
                    </div>
                    <div className="field" style={{ flex: "1 1 160px" }}>
                      <label className="field-label">From</label>
                      <input
                        type="date"
                        value={fromDate}
                        max={toDate}
                        onChange={(e) => setFromDate(e.target.value)}
                        required
                      />
                    </div>
                    <div className="field" style={{ flex: "1 1 160px" }}>
                      <label className="field-label">To</label>
                      <input
                        type="date"
                        value={toDate}
                        min={fromDate}
                        max={formatDate(new Date())}
                        onChange={(e) => setToDate(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  {selectedInstrument && (
                    <LivePrice
                      quote={livePrice}
                      loading={liveLoading}
                      error={liveError}
                      currency="INR"
                      onRefresh={fetchLivePrice}
                    />
                  )}
                </>
              )}
            </section>
          )}

          <hr className="divider" />

          <div className="field-grid">
            <div className="field">
              <label className="field-label">Model type</label>
              <select
                value={modelType}
                onChange={(e) => setModelType(e.target.value)}
              >
                <option value="Ridge Regression">
                  Ridge Regression (recommended)
                </option>
                <option value="Ensemble (Auto)">
                  Ensemble (Ridge + Trees + Boosting)
                </option>
                <option value="LSTM (Colab)">
                  LSTM (train free on Google Colab)
                </option>
              </select>
              {modelType === "LSTM (Colab)" && (
                <p className="note">
                  The LSTM is trained on Google Colab (free GPU). Run
                  colab/train_lstm_nse.py there, then place nse_lstm.keras and
                  nse_lstm_config.json in the repo models/ folder and restart
                  Django. Needs Yahoo/Kite data (Open/High/Low/Volume).
                </p>
              )}
            </div>

            <div className="field">
              <label className="field-label">Train size (%)</label>
              <input
                type="number"
                value={trainSize}
                onChange={(e) =>
                  setTrainSize(
                    Math.max(1, Math.min(99, parseInt(e.target.value))),
                  )
                }
                min="1"
                max="99"
              />
            </div>

            <div className="field">
              <label className="field-label">Prediction days</label>
              <input
                type="number"
                value={predictionDays}
                onChange={(e) =>
                  setPredictionDays(Math.max(1, parseInt(e.target.value)))
                }
                min="1"
              />
            </div>

            {simulateTrading && (
              <div className="field">
                <label className="field-label">Initial capital</label>
                <input
                  type="number"
                  value={initialCapital}
                  onChange={(e) =>
                    setInitialCapital(Math.max(1, parseFloat(e.target.value)))
                  }
                  min="1"
                  step="any"
                />
              </div>
            )}
          </div>

          <div className="field" style={{ marginTop: "18px" }}>
            <span className="field-label">Features</span>
            <div className="chip-row">
              <label
                className={`chip ${
                  features.includes("Moving Average") ? "chip-active" : ""
                }`}
              >
                <input
                  type="checkbox"
                  value="Moving Average"
                  checked={features.includes("Moving Average")}
                  onChange={handleFeatureChange}
                />
                Moving Average
              </label>
              <label
                className={`chip ${
                  features.includes("RSI") ? "chip-active" : ""
                }`}
              >
                <input
                  type="checkbox"
                  value="RSI"
                  checked={features.includes("RSI")}
                  onChange={handleFeatureChange}
                />
                RSI
              </label>
              <label
                className={`chip ${
                  features.includes("MACD") ? "chip-active" : ""
                }`}
              >
                <input
                  type="checkbox"
                  value="MACD"
                  checked={features.includes("MACD")}
                  onChange={handleFeatureChange}
                />
                MACD
              </label>
            </div>
          </div>

          <div style={{ marginTop: "18px" }}>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={simulateTrading}
                onChange={(e) => setSimulateTrading(e.target.checked)}
              />
              Simulate trading
            </label>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={
              loading ||
              (source === "csv"
                ? !file
                : source === "yahoo"
                  ? !yahooSymbol.trim()
                  : !kiteConnected || !selectedInstrument)
            }
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {loading && (
          <div className="spinner-row">
            <span className="spinner" />
            Processing your analysis...
          </div>
        )}
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        {results && (
          <section className="card" style={{ marginTop: "22px" }}>
            <h2 className="results-title">
              Analysis results
              {(symbolLabel || providerLabel) && (
                <span className="results-symbol">
                  {providerLabel ? `${providerLabel} · ` : ""}
                  {symbolLabel}
                </span>
              )}
            </h2>

            {plot && (
              <div style={{ marginBottom: "30px" }}>
                <h3 className="section-title">Price prediction plot</h3>
                <div className="plot-wrap">
                  <Plot
                    data={plot.data}
                    layout={plot.layout}
                    style={{ width: "100%", height: "500px" }}
                    useResizeHandler={true}
                  />
                </div>
              </div>
            )}

            {results.metrics && (
              <div style={{ marginBottom: "30px" }}>
                <h3 className="section-title">Prediction model metrics</h3>
                <p className="note" style={{ marginTop: 0 }}>
                  All error metrics are on next-day log returns. Compare RMSE
                  with the no-change baseline — if the model cannot beat it,
                  the signal is not usable.
                </p>
                <div className="metrics-grid">
                  <div className="stat">
                    <span className="stat-label">RMSE (returns)</span>
                    <span className="stat-value">
                      {results.metrics.rmse.toFixed(6)}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Baseline RMSE (no-change)</span>
                    <span className="stat-value">
                      {results.metrics.baseline_rmse != null
                        ? results.metrics.baseline_rmse.toFixed(6)
                        : "\u2014"}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">MAE (returns)</span>
                    <span className="stat-value">
                      {results.metrics.mae.toFixed(6)}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">R2 Score</span>
                    <span className="stat-value">
                      {results.metrics.r2.toFixed(4)}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Directional accuracy</span>
                    <span className="stat-value">
                      {results.metrics.directional_accuracy != null
                        ? `${(results.metrics.directional_accuracy * 100).toFixed(1)}%`
                        : "\u2014"}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">
                      Baseline direction (always up)
                    </span>
                    <span className="stat-value">
                      {results.metrics.baseline_directional_accuracy != null
                        ? `${(results.metrics.baseline_directional_accuracy * 100).toFixed(1)}%`
                        : "\u2014"}
                    </span>
                  </div>
                </div>
                {results.walk_forward && (
                  <>
                    <h3 className="section-title" style={{ marginTop: "18px" }}>
                      Walk-forward backtest (expanding window)
                    </h3>
                    <div className="metrics-grid">
                      <div className="stat">
                        <span className="stat-label">Folds</span>
                        <span className="stat-value">
                          {results.walk_forward.folds}
                        </span>
                      </div>
                      <div className="stat">
                        <span className="stat-label">
                          Directional accuracy (mean)
                        </span>
                        <span className="stat-value">
                          {(
                            results.walk_forward.directional_accuracy_mean *
                            100
                          ).toFixed(1)}
                          %
                        </span>
                      </div>
                      <div className="stat">
                        <span className="stat-label">
                          Directional accuracy (std)
                        </span>
                        <span className="stat-value">
                          {(
                            results.walk_forward.directional_accuracy_std * 100
                          ).toFixed(1)}
                          %
                        </span>
                      </div>
                      <div className="stat">
                        <span className="stat-label">RMSE (mean)</span>
                        <span className="stat-value">
                          {results.walk_forward.rmse_mean.toFixed(6)}
                        </span>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {results.feature_importance &&
              results.feature_importance.length > 0 && (
                <div style={{ marginBottom: "30px" }}>
                  <h3 className="section-title">
                    Feature importance
                    {results.model ? ` — ${results.model}` : ""}
                  </h3>
                  <p className="note" style={{ marginTop: 0 }}>
                    Share of the model's signal coming from each feature.
                    Features are known at time t; the model forecasts the next
                    day's return.
                  </p>
                  {results.feature_importance.map((item) => (
                    <div
                      key={item.feature}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        marginBottom: "6px",
                      }}
                    >
                      <span
                        style={{
                          flex: "0 0 140px",
                          fontSize: "13px",
                          color: "#cbd5e1",
                        }}
                      >
                        {item.feature}
                      </span>
                      <div
                        style={{
                          flex: "1 1 auto",
                          background: "rgba(255,255,255,0.06)",
                          borderRadius: "4px",
                          height: "10px",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.max(1, item.importance * 100)}%`,
                            height: "100%",
                            background: "#4A90E2",
                          }}
                        />
                      </div>
                      <span
                        style={{
                          flex: "0 0 52px",
                          textAlign: "right",
                          fontSize: "13px",
                          color: "#cbd5e1",
                        }}
                      >
                        {(item.importance * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}

            {results.trading_metrics &&
              Object.keys(results.trading_metrics).length > 0 && (
                <div style={{ marginBottom: "30px" }}>
                  <h3 className="section-title">Trading simulation</h3>
                  <div className="metrics-grid">
                    <div className="stat">
                      <span className="stat-label">Initial capital</span>
                      <span className="stat-value">
                        {formatAmount(initialCapital, resultCurrency)}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Final capital</span>
                      <span className="stat-value">
                        {formatAmount(
                          results.trading_metrics.final_capital,
                          resultCurrency,
                        )}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Total P&amp;L</span>
                      <span
                        className={`stat-value ${
                          results.trading_metrics.total_pnl >= 0
                            ? "positive"
                            : "negative"
                        }`}
                      >
                        {formatSigned(
                          results.trading_metrics.total_pnl,
                          resultCurrency,
                        )}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Total trades</span>
                      <span className="stat-value">
                        {results.trading_metrics.total_trades}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Profitable trades</span>
                      <span className="stat-value">
                        {results.trading_metrics.profitable_trades}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Win rate</span>
                      <span className="stat-value">
                        {results.trading_metrics.win_rate.toFixed(2)}%
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Avg return / trade</span>
                      <span
                        className={`stat-value ${
                          results.trading_metrics.avg_return >= 0
                            ? "positive"
                            : "negative"
                        }`}
                      >
                        {results.trading_metrics.avg_return.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}

            {results.future_predictions &&
              results.future_predictions.dates &&
              results.future_predictions.dates.length > 0 && (
                <div>
                  <h3 className="section-title">
                    Future price predictions ({predictionDays} days)
                  </h3>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th className="right">Predicted close price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.future_predictions.dates.map((date, index) => (
                        <tr key={date}>
                          <td>{date}</td>
                          <td className="right">
                            {formatAmount(
                              results.future_predictions.values[index],
                              resultCurrency,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </section>
        )}
      </div>
    </div>
  );
}

export default App;
