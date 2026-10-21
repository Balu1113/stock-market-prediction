const CURRENCY_SYMBOLS = {
  INR: "\u20b9",
  USD: "$",
  EUR: "\u20ac",
  GBP: "\u00a3",
  JPY: "\u00a5",
};

export function currencySymbol(code) {
  if (!code) return "\u20b9";
  const upper = code.toUpperCase();
  return CURRENCY_SYMBOLS[upper] || `${upper} `;
}

export function formatAmount(value, code = "INR") {
  if (value == null || Number.isNaN(Number(value))) return "\u2014";
  return `${currencySymbol(code)}${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatSigned(value, code = "INR") {
  if (value == null || Number.isNaN(Number(value))) return "\u2014";
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${formatAmount(Math.abs(value), code)}`;
}

export function formatPercent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "\u2014";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(digits)}%`;
}

export function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

export function parsePlot(plot) {
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
