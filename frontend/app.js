/**
 * Sakthi Manufacturing MIS Dashboard — Frontend Controller
 * Fetches KPIs, manages division/period state, and renders calm Plotly charts.
 */

let currentDivision = "ALL";
let currentMode = "weekly";
let currentPeriod = "2026-W45";

// Dribbble Color System
const PALETTE = {
  accent: "#8E9BFF",
  accentSoft: "#E6E9FF",
  good: "#A8DCC4",
  warn: "#F6DDA8",
  bad: "#F4B9C0",
  sky: "#B7D8F5",
  lavender: "#D8D0F5",
  text: "#3F4558",
  textMuted: "#8A90A6",
  bg: "#F4F5F9",
  surface: "#FBFBFD",
  surfaceAlt: "#EEF0F6",
};

// Common Plotly Layout Config
const BASE_LAYOUT = {
  font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color: PALETTE.text, size: 11 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { l: 40, r: 20, t: 30, b: 40 },
  hovermode: "closest",
  xaxis: { showgrid: false, zeroline: false, linecolor: PALETTE.surfaceAlt },
  yaxis: { showgrid: true, gridcolor: PALETTE.surfaceAlt, zeroline: false },
};

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadDashboardData();
  loadReportsLibrary();
});

function initEventListeners() {
  // Division segment buttons
  document.querySelectorAll("#divisionSwitch .segment-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#divisionSwitch .segment-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentDivision = btn.dataset.division;
      loadDashboardData();
    });
  });

  // Period mode segment buttons (Weekly vs Monthly)
  document.querySelectorAll("#periodTypeSwitch .segment-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#periodTypeSwitch .segment-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = btn.dataset.mode;

      const select = document.getElementById("periodSelect");
      select.innerHTML = "";
      if (currentMode === "weekly") {
        select.innerHTML = `<option value="2026-W45">ISO Week 45 (Nov 02 - Nov 08, 2026)</option>`;
        currentPeriod = "2026-W45";
      } else {
        select.innerHTML = `<option value="2026-11">November 2026 (Monthly Quality Review)</option>`;
        currentPeriod = "2026-11";
      }
      loadDashboardData();
    });
  });
}

function onPeriodChange() {
  currentPeriod = document.getElementById("periodSelect").value;
  loadDashboardData();
}

async function loadDashboardData() {
  try {
    const res = await fetch(`/api/kpis?division=${currentDivision}&period=${currentPeriod}`);
    const data = await res.json();

    updateKPICards(data.kpis);
    renderProductionChart(data.productionSeries);
    renderParetoChart(data.paretoSeries);
    renderRejectionTrendChart(data.trendSeries);
    renderCategorySplitDonut(data.categorySplit);
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
  }
}

function updateKPICards(kpis) {
  if (!kpis) return;
  document.getElementById("kpiProduced").textContent = (kpis.produced_qty || 0).toLocaleString();
  document.getElementById("kpiRejected").textContent = (kpis.rejected_qty || 0).toLocaleString();
  document.getElementById("kpiRate").textContent = (kpis.rejection_pct || 0).toFixed(2) + "%";
  document.getElementById("kpiCost").textContent = "INR " + Math.round(kpis.scrap_cost || 0).toLocaleString();

  const chip = document.getElementById("kpiStatusChip");
  const status = (kpis.status || "good").toLowerCase();
  chip.className = "kpi-chip " + (status === "critical" || status === "bad" ? "chip-bad" : (status === "warning" || status === "warn" ? "chip-warn" : "chip-good"));
  chip.textContent = status.toUpperCase();

  document.getElementById("kpiTargetChip").textContent = "Target: " + (kpis.target_qty || 0).toLocaleString();
}

function renderProductionChart(series) {
  if (!series || !series.dates) return;

  const barTrace = {
    x: series.dates,
    y: series.produced,
    type: "bar",
    name: "Produced Pcs",
    marker: { color: PALETTE.accent, opacity: 0.85, cornerRadius: 8 },
  };

  const lineTrace = {
    x: series.dates,
    y: series.target,
    type: "scatter",
    mode: "lines",
    name: "Target Pcs",
    line: { color: PALETTE.textMuted, dash: "dot", width: 2 },
  };

  const layout = {
    ...BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: "h", y: 1.15, x: 0.5, xanchor: "center" },
    barmode: "group",
  };

  Plotly.newPlot("chartProduction", [barTrace, lineTrace], layout, { responsive: true, displayModeBar: false });
}

function renderParetoChart(pareto) {
  if (!pareto || !pareto.defects) return;

  const barTrace = {
    x: pareto.defects,
    y: pareto.quantities,
    type: "bar",
    name: "Defect Count",
    marker: { color: PALETTE.sky, opacity: 0.9, cornerRadius: 6 },
    yaxis: "y",
  };

  const cumLine = {
    x: pareto.defects,
    y: pareto.cumPct,
    type: "scatter",
    mode: "lines+markers",
    name: "Cumulative %",
    line: { color: PALETTE.accent, width: 2.5 },
    marker: { size: 6, color: PALETTE.accent },
    yaxis: "y2",
  };

  const layout = {
    ...BASE_LAYOUT,
    showlegend: false,
    yaxis: { ...BASE_LAYOUT.yaxis, title: "" },
    yaxis2: {
      title: "",
      overlaying: "y",
      side: "right",
      range: [0, 105],
      showgrid: false,
      tickformat: ".0%",
    },
  };

  Plotly.newPlot("chartPareto", [barTrace, cumLine], layout, { responsive: true, displayModeBar: false });
}

function renderRejectionTrendChart(trend) {
  if (!trend || !trend.dates) return;

  const traceRej = {
    x: trend.dates,
    y: trend.rejectionRates,
    type: "scatter",
    mode: "lines+markers",
    name: "Rejection %",
    line: { color: "#B25A66", width: 2.5 },
    marker: { size: 6, color: "#B25A66" },
  };

  const traceWarn = {
    x: trend.dates,
    y: Array(trend.dates.length).fill(trend.warnLimit || 3.5),
    type: "scatter",
    mode: "lines",
    name: "Warning Limit",
    line: { color: "#E0B34E", dash: "dash", width: 1.5 },
  };

  const traceCrit = {
    x: trend.dates,
    y: Array(trend.dates.length).fill(trend.critLimit || 4.5),
    type: "scatter",
    mode: "lines",
    name: "Critical Limit",
    line: { color: "#D96B77", dash: "dash", width: 1.5 },
  };

  const layout = {
    ...BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: "h", y: 1.15, x: 0.5, xanchor: "center" },
  };

  Plotly.newPlot("chartRejection", [traceRej, traceWarn, traceCrit], layout, { responsive: true, displayModeBar: false });
}

function renderCategorySplitDonut(split) {
  if (!split || !split.labels) return;

  const trace = {
    labels: split.labels,
    values: split.values,
    type: "pie",
    hole: 0.65,
    textinfo: "percent",
    marker: {
      colors: [PALETTE.accent, PALETTE.good, PALETTE.sky, PALETTE.warn, PALETTE.bad],
    },
  };

  const layout = {
    ...BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: "h", y: 1.15, x: 0.5, xanchor: "center" },
    annotations: [
      {
        font: { size: 12, family: "inherit", color: PALETTE.textMuted },
        showarrow: false,
        text: "Quality<br>Defects",
        x: 0.5,
        y: 0.5,
      },
    ],
  };

  Plotly.newPlot("chartSplit", [trace], layout, { responsive: true, displayModeBar: false });
}

async function loadReportsLibrary() {
  try {
    const res = await fetch("/api/reports");
    const reports = await res.json();
    const tbody = document.getElementById("reportsTableBody");
    tbody.innerHTML = "";

    if (!reports || reports.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No reports generated yet. Click "Generate Reports" to build.</td></tr>`;
      return;
    }

    reports.forEach((r) => {
      const tr = document.createElement("tr");

      let excelLink = r.excel_url ? `<a href="${r.excel_url}" class="file-pill file-pill-excel" download>📊 Excel</a>` : "";
      let pdfLink = r.pdf_url ? `<a href="${r.pdf_url}" class="file-pill file-pill-pdf" target="_blank">📄 PDF</a>` : "";
      let htmlLink = r.html_url ? `<a href="${r.html_url}" class="file-pill file-pill-html" target="_blank">🌐 Web</a>` : "";

      tr.innerHTML = `
        <td style="font-weight: 600;">${r.title}</td>
        <td>${r.division}</td>
        <td><code>${r.period}</code></td>
        <td>${(r.produced || 0).toLocaleString()}</td>
        <td style="font-weight: 600;">${(r.rejection_pct || 0).toFixed(2)}%</td>
        <td><span class="kpi-chip ${r.status === 'SUCCESS' ? 'chip-good' : 'chip-warn'}">${r.status}</span></td>
        <td><div class="file-pills">${excelLink} ${pdfLink} ${htmlLink}</div></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load reports library:", err);
  }
}

async function triggerReportPipeline() {
  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  btn.innerHTML = "Generating...";

  try {
    const res = await fetch("/api/reports/generate", { method: "POST" });
    const data = await res.json();

    showToast("MIS Reports successfully regenerated!");
    loadDashboardData();
    loadReportsLibrary();
  } catch (err) {
    showToast("Generation encountered an error.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"></polyline>
        <polyline points="1 20 1 14 7 14"></polyline>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
      </svg>
      Generate Reports
    `;
  }
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  document.getElementById("toastMsg").textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3500);
}

// ---------------------------------------------------------------------------
// Custom CSV Upload & Report Generation
// ---------------------------------------------------------------------------
let selectedProdFile = null;
let selectedRejFile = null;

function handleFileSelected(type) {
  if (type === "prod") {
    const input = document.getElementById("prodFileInput");
    if (input.files && input.files[0]) {
      selectedProdFile = input.files[0];
      document.getElementById("prodFileLabel").textContent = `📄 ${selectedProdFile.name} (${(selectedProdFile.size / 1024).toFixed(1)} KB)`;
    }
  } else if (type === "rej") {
    const input = document.getElementById("rejFileInput");
    if (input.files && input.files[0]) {
      selectedRejFile = input.files[0];
      document.getElementById("rejFileLabel").textContent = `📄 ${selectedRejFile.name} (${(selectedRejFile.size / 1024).toFixed(1)} KB)`;
    }
  }
}

function readFileContent(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (err) => reject(err);
    reader.readAsText(file);
  });
}

async function uploadAndGenerateReports() {
  if (!selectedProdFile && !selectedRejFile) {
    alert("Please choose at least a Production CSV or Rejection CSV file to upload.");
    return;
  }

  const btn = document.getElementById("uploadProcessBtn");
  btn.disabled = true;
  btn.textContent = "Processing ETL & Generating Reports...";

  const resultBox = document.getElementById("uploadResultBox");
  resultBox.style.display = "none";

  try {
    const [prodContent, rejContent] = await Promise.all([
      readFileContent(selectedProdFile),
      readFileContent(selectedRejFile),
    ]);

    const periodInput = document.getElementById("customPeriodInput").value.trim();
    let targetWeek = null;
    let targetMonth = null;
    if (periodInput) {
      if (periodInput.includes("-W") || periodInput.includes("W")) targetWeek = periodInput;
      else if (periodInput.includes("-")) targetMonth = periodInput;
    }

    const payload = {
      prod_content: prodContent,
      rej_content: rejContent,
      week: targetWeek,
      month: targetMonth,
    };

    const response = await fetch("/api/upload-csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (data.status === "SUCCESS") {
      showToast(`Batch ${data.batch_id} ingested! Generated reports for ${data.week_key}.`);

      resultBox.style.display = "block";
      resultBox.style.backgroundColor = "var(--good-bg)";
      resultBox.style.color = "var(--good-text)";

      const f = data.reports.weekly_foundry;
      const m = data.reports.weekly_machine_shop;
      const mon = data.reports.monthly_rejection;

      resultBox.innerHTML = `
        <div style="font-weight: 700; margin-bottom: 6px;">
          ✅ Successfully processed: ${data.production_rows_loaded} production rows, ${data.rejection_rows_loaded} rejection rows. Period: <code>${data.week_key}</code>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px;">
          <a href="${f.excel_url}" class="file-pill file-pill-excel" download>📊 Foundry Excel</a>
          <a href="${f.pdf_url}" class="file-pill file-pill-pdf" target="_blank">📄 Foundry PDF</a>
          <a href="${m.excel_url}" class="file-pill file-pill-excel" download>📊 Machine Shop Excel</a>
          <a href="${m.pdf_url}" class="file-pill file-pill-pdf" target="_blank">📄 Machine Shop PDF</a>
          <a href="${mon.excel_url}" class="file-pill file-pill-excel" download>📊 Monthly Rejection Excel</a>
          <a href="${mon.pdf_url}" class="file-pill file-pill-pdf" target="_blank">📄 Monthly Rejection PDF</a>
        </div>
      `;

      // Refresh dashboard charts and report library
      loadDashboardData();
      loadReportsLibrary();
    } else {
      resultBox.style.display = "block";
      resultBox.style.backgroundColor = "var(--bad-bg)";
      resultBox.style.color = "var(--bad-text)";
      resultBox.textContent = `❌ Ingestion error: ${data.error || "Unknown error"}`;
    }
  } catch (err) {
    resultBox.style.display = "block";
    resultBox.style.backgroundColor = "var(--bad-bg)";
    resultBox.style.color = "var(--bad-text)";
    resultBox.textContent = `❌ Request failed: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      Process CSV & Generate Reports
    `;
  }
}

