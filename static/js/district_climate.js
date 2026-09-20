// ─── Load districts dropdown ───────────────────────────────────────────────
fetch("/api/admin-districts")
  .then(res => res.json())
  .then(data => {
    const dropdown = document.getElementById("districtDropdown");
    dropdown.innerHTML = '<option value="">-- Select District --</option>';
    data.forEach(d => {
      const option = document.createElement("option");
      option.value = d;
      option.text = d;
      dropdown.appendChild(option);
    });
  });


// ─── Unit & icon config per parameter ────────────────────────────────────────
const PARAM_CONFIG = {
  "precipitation": {
    unit: "mm/year",
    badge: "Precipitation",
    badgeClass: "badge-blue",
    accentVar: "--color-background-info"
  },
  "temperature": {
    unit: "°C",
    badge: "Temperature",
    badgeClass: "badge-amber",
    accentVar: "--color-background-warning"
  },
  "streamflow": {
    unit: "m³/s",
    badge: "Streamflow",
    badgeClass: "badge-teal",
    accentVar: "--color-background-success"
  },
  "water level": {
    unit: "m",
    badge: "Water level",
    badgeClass: "badge-green",
    accentVar: "--color-background-success"
  }
};

function getParamConfig(label) {
  const key = label.toLowerCase().trim();
  for (const [k, v] of Object.entries(PARAM_CONFIG)) {
    if (key.includes(k)) return v;
  }
  return { unit: "", badge: label, badgeClass: "badge-gray" };
}


// ─── Parse output lines into structured objects ──────────────────────────────
function parseOutputLines(rawText) {
  const lines = rawText.split("\n").map(l => l.trim()).filter(Boolean);
  const params = [];

  for (const line of lines) {
    // Match: "Mean Precipitation: 1248.70 [stations=6, records=432, years=2001-2023, months=Jan, Feb]"
    const match = line.match(
      /^Mean\s+(.+?):\s*([\d.]+)\s*(?:\[(.+)\])?/i
    );
    if (!match) continue;

    const label    = match[1].trim();
    const value    = parseFloat(match[2]);
    const metaStr  = match[3] || "";

    const meta = {};
    metaStr.split(",").forEach(part => {
      const [k, v] = part.split("=").map(s => s.trim());
      if (k && v) meta[k] = v;
    });

    params.push({ label, value, meta });
  }

  return params;
}


// ─── Build a single param card ───────────────────────────────────────────────
function buildParamCard(label, value, meta) {
  const config   = getParamConfig(label);
  const valueStr = isNaN(value) ? "N/A" : value.toFixed(2);
  const period   = meta.years  ? meta.years.replace("-", " – ") : "—";
  const stations = meta.stations || "—";
  const records  = meta.records  || "—";
  const months   = meta.months   || "—";

  return `
    <div class="param-card">
      <p class="param-label">Mean ${label.toLowerCase()}</p>
      <p class="param-value">
        ${valueStr}
        <span class="param-unit">${config.unit}</span>
      </p>
      <div class="param-meta">
        <span><span>Stations</span><b>${stations}</b></span>
        <span><span>Records</span><b>${records}</b></span>
        <span><span>Period</span><b>${period}</b></span>
        <span><span>Months</span><b>${months}</b></span>
      </div>
      <span class="badge ${config.badgeClass}">${config.badge}</span>
    </div>
  `;
}


// ─── Build raster summary row ─────────────────────────────────────────────────
function buildRasterRow(rawText) {
  const precipMatch = rawText.match(/Mean Precipitation.*raster[^:]*:\s*([\d.]+)/i);
  const tempMatch   = rawText.match(/Mean Temperature.*raster[^:]*:\s*([\d.]+)/i);

  if (!precipMatch && !tempMatch) return "";

  let html = `<div class="raster-section">
    <p class="raster-heading">Long-term raster averages</p>
    <div class="raster-grid">`;

  if (precipMatch) {
    html += `
      <div class="raster-card">
        <p class="param-label">Precipitation (raster)</p>
        <p class="param-value">${parseFloat(precipMatch[1]).toFixed(2)}<span class="param-unit">mm/year</span></p>
      </div>`;
  }
  if (tempMatch) {
    html += `
      <div class="raster-card">
        <p class="param-label">Temperature (raster)</p>
        <p class="param-value">${parseFloat(tempMatch[1]).toFixed(2)}<span class="param-unit">°C</span></p>
      </div>`;
  }

  html += `</div></div>`;
  return html;
}


// ─── Main calculate function ──────────────────────────────────────────────────
function calculate() {
  const district  = document.getElementById("districtDropdown").value;
  const resultDiv = document.getElementById("result");
  const status    = document.getElementById("status");

  if (!district) { alert("Please select a district"); return; }

  status.innerText = "Calculating…";
  resultDiv.innerHTML = "";

  fetch(`/api/admin-mean?district=${encodeURIComponent(district)}`)
    .then(res => res.json())
    .then(data => {

      if (data.error) {
        resultDiv.innerHTML = `<p style="color:var(--color-text-danger)">${data.error}</p>`;
        status.innerText = "Failed";
        return;
      }

      const raw = String(data.output || "").trim();
      if (!raw) {
        resultDiv.innerHTML = `<p style="color:var(--color-text-secondary)">No data found for ${district}.</p>`;
        status.innerText = "No data";
        return;
      }

      const params   = parseOutputLines(raw);
      const rasterHtml = buildRasterRow(raw);

      const cardsHtml = params.length
        ? params.map(p => buildParamCard(p.label, p.value, p.meta)).join("")
        : `<p class="no-data">No parameter data found.</p>`;

      resultDiv.innerHTML = `
        <div class="result-wrap">
          <p class="district-heading">${district}</p>
          <div class="params-grid">${cardsHtml}</div>
          ${rasterHtml}
        </div>
      `;

      status.innerText = "Done";
    })
    .catch(() => {
      resultDiv.innerHTML = `<p style="color:var(--color-text-danger)">Failed to fetch data.</p></p>`;
      status.innerText = "Failed";
    });
}