/* ================= SAFE HELPERS ================= */

async function getcollabid(){
const res = await fetch("/api/get-collab-id");
    const data = await res.json();   // ✅ IMPORTANT

    const COLLAB_ID = data.collab_id; // adjust key if needed
    return `/data/collaborator/${COLLAB_ID}/display`;
}
let BASE_PATH = null;

async function initBasePath() {
  BASE_PATH = await getcollabid(); // ✅ wait for real value
}

function safeGet(id) {
  return document.getElementById(id);
}

function safeUncheck(id) {
  const el = safeGet(id);
  if (el) el.checked = false;
}
// ================= COLOR CLASSIFICATION =================

// Precipitation breaks (mm) – adjust if needed
const PRECIP_BREAKS = [800, 1000, 1200, 1400, 1700];

// Temperature breaks (°C)
const TEMP_BREAKS = [24.9, 25.5, 26, 26.5, 27.3];


function getPrecipColor(val) {
  if (val === null || isNaN(val)) return null;
  if (val <= PRECIP_BREAKS[0]) return "#f7fbff"; // no value
  if (val <= PRECIP_BREAKS[1]) return "#c6dbef"; // very low
  if (val <= PRECIP_BREAKS[2]) return "#6baed6"; // low
  if (val <= PRECIP_BREAKS[3]) return "#2171b5"; // medium
  if (val <= PRECIP_BREAKS[4]) return "#08519c"; // high
  return "#08306b";                              // very high
}

function getTempColor(val) {
  if (val === null || isNaN(val)) return null;

  if (val <= TEMP_BREAKS[0]) return "#f7fbff"; // very low ()
  if (val <= TEMP_BREAKS[1]) return "#c6dbef";
  if (val <= TEMP_BREAKS[2]) return "#6baed6";
  if (val <= TEMP_BREAKS[3]) return "#2171b5";
  if (val <= TEMP_BREAKS[4]) return "#08519c";
  return "#08306b"; // very high (dark red)
}

function getStreamFlowColor(val) {
  return getPrecipColor(val);
}

function getWaterLevelColor(val) {
  return getPrecipColor(val);
}

function toggleMenu() {
  const menu = document.getElementById("menu");
  menu.style.display = (menu.style.display === "block") ? "none" : "block";
  updateZoomPosition();
}

function updateZoomPosition() {
  const menu = document.getElementById("menu");
  const zoomEl = document.querySelector(".leaflet-control-zoom");
  if (menu.style.display === "block") {
    zoomEl.style.top = menu.offsetHeight + 5 + "px";
  } else {
    zoomEl.style.top = "5px";
  }
}

/* ================= MAP ================= */
const map = L.map("map", { zoomControl: false, attributionControl: false }).setView([23, 78], 6);
const zoomControl = L.control.zoom({ position: "topleft" });
zoomControl.addTo(map);

function popupContent(props) {
  let html = "<table>";
  for (let k in props) html += `<tr><td><b>${k}</b></td><td>${props[k]}</td></tr>`;
  html += "</table>";
  return html;
}

const overlayMaps = {};
const layerControl = L.control.layers(null, overlayMaps, { collapsed: false }).addTo(map);

function registerLayer(layer, name, addByDefault = false) {
  overlayMaps[name] = layer;
  layerControl.addOverlay(layer, name);
  if (addByDefault) layer.addTo(map);
}

// ---------- STATE ----------
fetch("/data/admin/display/geojson/state_boundary.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { style: { color: "#000", weight: 2, fillOpacity: 0.4 }, onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "State Boundary", true); layer.bringToBack(); map.fitBounds(layer.getBounds());
});

// ---------- DISTRICT ----------
fetch("/data/admin/display/geojson/district_boundary.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { style: { color: "#444", weight: 1, fillOpacity: 0.2 }, onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "District Boundary");
});

// ---------- NARMADA POLYGON ----------
fetch("/data/admin/display/geojson/narmada.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { style: { color: "blue", fillOpacity: 0.2 }, onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "Narmada Polygon", true); layer.bringToBack();
});

// ---------- RIVER NETWORK ----------
fetch("/data/admin/display/geojson/narmada_named_network.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { style: { color: "cyan", weight: 1.5 }, onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "Named River Network", true);
});

// ---------- CENTERLINE ----------
fetch("/data/admin/display/geojson/narmada_centerline.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { style: { color: "navy", weight: 3 }, onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "Narmada Centerline", true); layer.bringToFront();
});

// ---------- STATE HQ ----------
fetch("/data/admin/display/geojson/state_hq.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 6, color: "red", fillOpacity: 1 }), onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "State HQ");
});

// ---------- DISTRICT HQ ----------
fetch("/data/admin/display/geojson/district_hq.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 4, color: "darkred", fillOpacity: 1 }), onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "District HQ");
});

// ---------- MAJOR TOWNS ----------
fetch("/data/admin/display/geojson/major_towns.geojson").then(r => r.json()).then(data => {
  const layer = L.geoJSON(data, { pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 3, color: "orange", fillOpacity: 1 }), onEachFeature: (f, l) => l.bindPopup(popupContent(f.properties)) });
  registerLayer(layer, "Major Towns");
});

// ---------- LEGEND ----------
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = `
      <b>Legend</b><br>
      <span style="background:#000"></span>State Boundary<br>
      <span style="background:#444"></span>District Boundary<br>
      <span style="background:blue"></span>Narmada Polygon<br>
      <span style="background:navy"></span>Narmada Centerline<br>
      <span style="background:cyan"></span>River Network<br>
      <span style="background:red"></span>State HQ<br>
      <span style="background:darkred"></span>District HQ<br>
      <span style="background:orange"></span>Major Towns
    `;
  return div;
};
legend.addTo(map);

// ================= RASTER LEGEND =================
let rasterLegend = L.control({ position: "bottomright" });

function showPrecipLegend(title) {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;800 mm)<br>
      <span style="background:#6baed6"></span> Low (801–1000 mm)<br>
      <span style="background:#2171b5"></span> Medium (1001–1200 mm)<br>
      <span style="background:#08519c"></span> High (1201–1400 mm)<br>
      <span style="background:#08306b"></span> Very High (&gt;1400 mm)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

function showTempLegend() {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>Mean Temperature (°C)</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;24.9 °C)<br>
      <span style="background:#6baed6"></span> Low (25.0–25.5 °C)<br>
      <span style="background:#2171b5"></span> Medium (25.6–26.0 °C)<br>
      <span style="background:#08519c"></span> High (26.1–26.5 °C)<br>
      <span style="background:#08306b"></span> Very High (&gt;26.5 °C)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

function showLulcLegend() {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>LULC</b><br>
      <span style="background:#c6dbef"></span> Very Low (0–20%)<br>
      <span style="background:#6baed6"></span> Low (21–40%)<br>
      <span style="background:#2171b5"></span> Medium (41–60%)<br>
      <span style="background:#08519c"></span> High (61–80%)<br>
      <span style="background:#08306b"></span> Very High (&gt;80%)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

function showPopLegend() {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>Population Density</b><br>
      <span style="background:#c6dbef"></span> Very Low (0–20%)<br>
      <span style="background:#6baed6"></span> Low (21–40%)<br>
      <span style="background:#2171b5"></span> Medium (41–60%)<br>
      <span style="background:#08519c"></span> High (61–80%)<br>
      <span style="background:#08306b"></span> Very High (&gt;80%)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

function showStreamFlowLegend(title) {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (0–20%)<br>
      <span style="background:#6baed6"></span> Low (21–40%)<br>
      <span style="background:#2171b5"></span> Medium (41–60%)<br>
      <span style="background:#08519c"></span> High (61–80%)<br>
      <span style="background:#08306b"></span> Very High (&gt;80%)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

function showWaterLevelLegend(title) {
  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (0–20%)<br>
      <span style="background:#6baed6"></span> Low (21–40%)<br>
      <span style="background:#2171b5"></span> Medium (41–60%)<br>
      <span style="background:#08519c"></span> High (61–80%)<br>
      <span style="background:#08306b"></span> Very High (&gt;80%)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

// ================= INPUT PARAMETERS =================
const inputControl = L.control({ position: "bottomleft" });

inputControl.onAdd = function () {
  const div = L.DomUtil.create("div", "input-box");
  div.innerHTML = `

      <h4>Input Parameters</h4>

      <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
  <button id="navUp">⬆</button>
  <button id="navDown">⬇</button>
</div>

<div class="accordion">

  <div class="acc-item" id="block-precip-static">
    <div class="acc-header" onclick="toggleAcc(this)">
      <span id="collabPrecipClipLabel">Precipitation</span>
    </div>
    <div class="acc-body">
      <button id="clipPrecipBtn">Clip Raster</button><br><br>
      <label>
        <input type="checkbox" id="showPrecipRaster">
        Show Layer
      </label>
    </div>
  </div>

  <div class="acc-item" id="block-temp-static">
    <div class="acc-header" onclick="toggleAcc(this)">
      <span id="collabTempClipLabel">Mean Temperature</span>
    </div>
    <div class="acc-body">
      <button id="clipTempBtn">Clip Raster</button><br><br>
      <label>
        <input type="checkbox" id="showTempRaster">
        Show Layer
      </label>
    </div>
  </div>

  <div class="acc-item" id="block-full-precip">
    <div class="acc-header" onclick="toggleAcc(this)">
      <span id="collabPrecipFullLabel">Precipitation</span>
    </div>
    <div class="acc-body">
      <label>
        <input type="checkbox" id="showFullPrecip">
        Show Layer
      </label>
    </div>
  </div>

  <div class="acc-item" id="block-full-temp">
    <div class="acc-header" onclick="toggleAcc(this)">
      <span id="collabTempFullLabel">Mean Temperature</span>
    </div>
    <div class="acc-body">
      <label>
        <input type="checkbox" id="showFullTemp">
        Show Layer
      </label>
    </div>
  </div>

   <!-- ================= YEAR-WISE PRECIPITATION ================= -->
<div class="acc-item" id="block-precip-dynamic">
  <div class="acc-header" onclick="toggleAcc(this)">
     Precipitation (Year-wise)
  </div>

  <div class="acc-body">

    <label for="precipYear"><b>Select Year</b></label><br>
    <select id="precipYear" style="width:100%; margin-top:6px;">
      <!-- Years will be populated by JS -->
    </select>

    <br><br>

    <button id="clipYearPrecipBtn">Generate Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearPrecip">
      Show Layer
    </label>

  </div>
</div>

 <!-- ================= YEAR-WISE MeanTemp ================= -->
<div class="acc-item" id="block-temp-dynamic">
  <div class="acc-header" onclick="toggleAcc(this)">
     MeanTemperature (Year-wise)
  </div>

  <div class="acc-body">

    <label for="tempYear"><b>Select Year</b></label><br>
    <select id="tempYear" style="width:100%; margin-top:6px;">
      <!-- Years will be populated by JS -->
    </select>

    <br><br>

    <button id="clipYearTempBtn">Generate Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearTemp">
      Show Layer
    </label>

  </div>
</div>

<!-- ================= YEAR-WISE LULC ================= -->
<div class="acc-item" id="block-lulc-static">
  <div class="acc-header" onclick="toggleAcc(this)">
     LandUse LandCover (Year-wise)
  </div>

  <div class="acc-body">

    <label for="LulcYear"><b>Select Year</b></label><br>
    <select id="LulcYear" style="width:100%; margin-top:6px;">
      <!-- Years will be populated by JS -->
    </select>

    <br><br>

    <button id="clipYearLulcBtn">Load Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearLulc">
      Show Layer
    </label>

  </div>
</div>

<!-- ================= YEAR-WISE POPULATION DENSITY ================= -->
<div class="acc-item" id="block-pop-static">
  <div class="acc-header" onclick="toggleAcc(this)">
     Population Density (Year-wise)
  </div>

  <div class="acc-body">

    <label for="PopYear"><b>Select Year</b></label><br>
    <select id="PopYear" style="width:100%; margin-top:6px;">
      <!-- Years will be populated by JS -->
    </select>

    <br><br>

    <button id="clipYearPopBtn">Load Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearPop">
      Show Layer
    </label>

  </div>
</div>

 <!-- ================= YEAR-WISE StreamFlow ================= -->
<div class="acc-item" id="block-streamflow">
  <div class="acc-header" onclick="toggleAcc(this)">
     StreamFlow (Monthly)
  </div>

  <div class="acc-body">

    <div style="margin-bottom:12px;">
  <label for="StreamFlowYear"><b>Select Year</b></label>
  <select id="StreamFlowYear" style="width:100%; margin-top:6px;"></select>
</div>

<div style="margin-bottom:12px;">
  <label for="StreamFlowMonth"><b>Select Month</b></label>
  <select id="StreamFlowMonth" style="width:100%; margin-top:6px;"></select>
</div>

    <br><br>

    <button id="clipYearStreamFlowBtn">Generate Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearStreamFlow">
      Show Layer
    </label>

  </div>
</div>

 <!-- ================= YEAR-WISE WaterLevel ================= -->
<div class="acc-item" id="block-waterlevel">
  <div class="acc-header" onclick="toggleAcc(this)">
     WaterLevel (Monthly)
  </div>

  <div class="acc-body">

   <div style="margin-bottom:12px;">
  <label for="WaterLevelYear"><b>Select Year</b></label>
  <select id="WaterLevelYear" style="width:100%; margin-top:6px;"></select>
</div>

<div style="margin-bottom:12px;">
  <label for="WaterLevelMonth"><b>Select Month</b></label>
  <select id="WaterLevelMonth" style="width:100%; margin-top:6px;"></select>
</div>

    <br><br>

    <button id="clipYearWaterLevelBtn">Generate Raster</button><br><br>

    <label>
      <input type="checkbox" id="showYearWaterLevel">
      Show Layer
    </label>

  </div>
</div>

</div>



    `;
  L.DomEvent.disableClickPropagation(div);
  return div;
};
inputControl.addTo(map);

// Variable to hold raster overlay
let precipRasterLayer = null;
let tempRasterLayer = null;
let fullPrecipLayer = null;
let fullTempLayer = null;
let yearPrecipLayer = null;
let yearTempLayer = null;
let yearPopLayer = null;
let yearLulcLayer = null;
let yearStreamFlowLayer = null;
let yearWaterLevelLayer = null;

let rasterRangeMeta = {
  precip: null,
  temp: null,
};

function defaultRangeLabel(kind) {
  return kind === "precip" ? "Precipitation" : "Mean Temperature";
}

function getRangeLabel(kind) {
  const meta = rasterRangeMeta[kind];
  if (!meta || !meta.startYear || !meta.endYear) {
    return defaultRangeLabel(kind);
  }

  const base = kind === "precip" ? "Precipitation" : "Mean Temperature";
  return `${base} (${meta.startYear}-${meta.endYear})`;
}

function getRangeFileUrl(kind) {
  const meta = rasterRangeMeta[kind];
  if (!meta || !meta.file || !BASE_PATH) return null;
  return `${BASE_PATH}/raster/${meta.file}`;
}

async function loadCollaboratorRasterRangeMeta() {
  try {
    const res = await fetch("/api/collaborator-raster-range-meta");
    if (!res.ok) return;

    const data = await res.json();
    rasterRangeMeta.precip = data?.precip || null;
    rasterRangeMeta.temp = data?.temp || null;

    const precipLabel = getRangeLabel("precip");
    const tempLabel = getRangeLabel("temp");

    const clipPrecipEl = document.getElementById("collabPrecipClipLabel");
    const fullPrecipEl = document.getElementById("collabPrecipFullLabel");
    const clipTempEl = document.getElementById("collabTempClipLabel");
    const fullTempEl = document.getElementById("collabTempFullLabel");

    if (clipPrecipEl) clipPrecipEl.textContent = precipLabel;
    if (fullPrecipEl) fullPrecipEl.textContent = precipLabel;
    if (clipTempEl) clipTempEl.textContent = tempLabel;
    if (fullTempEl) fullTempEl.textContent = tempLabel;
  } catch (err) {
    console.error("Collaborator raster meta load failed:", err);
  }
}


function clearRasterLegend() {
  try {
    map.removeControl(rasterLegend);
  } catch (e) { }
}

function removeAllRasters() {
 safeUncheck("showPrecipRaster");
safeUncheck("showTempRaster");
safeUncheck("showFullPrecip");
safeUncheck("showFullTemp");
safeUncheck("showYearPrecip");
safeUncheck("showYearTemp");
safeUncheck("showYearPop");
safeUncheck("showYearLulc");
safeUncheck("showYearStreamFlow");
safeUncheck("showYearWaterLevel");
  clearRasterLegend();
}

// ================= HELPER: build year-precip legend with actual min/max =================
function showYearPrecipLegend(title, min, max) {
  const range = max - min;
  const b1 = (min + range * 0.2).toFixed(1);
  const b2 = (min + range * 0.4).toFixed(1);
  const b3 = (min + range * 0.6).toFixed(1);
  const b4 = (min + range * 0.8).toFixed(1);

  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;${b1} mm)<br>
      <span style="background:#6baed6"></span> Low (${b1}–${b2} mm)<br>
      <span style="background:#2171b5"></span> Medium (${b2}–${b3} mm)<br>
      <span style="background:#08519c"></span> High (${b3}–${b4} mm)<br>
      <span style="background:#08306b"></span> Very High (&gt;${b4} mm)
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

// ================= HELPER: build streamflow legend with actual min/max =================
function showYearStreamFlowLegendDynamic(title, min, max) {
  const range = max - min;
  const b1 = (min + range * 0.2).toFixed(2);
  const b2 = (min + range * 0.4).toFixed(2);
  const b3 = (min + range * 0.6).toFixed(2);
  const b4 = (min + range * 0.8).toFixed(2);

  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;${b1})<br>
      <span style="background:#6baed6"></span> Low (${b1}–${b2})<br>
      <span style="background:#2171b5"></span> Medium (${b2}–${b3})<br>
      <span style="background:#08519c"></span> High (${b3}–${b4})<br>
      <span style="background:#08306b"></span> Very High (&gt;${b4})
    `;
    return div;
  };
  rasterLegend.addTo(map);
}
 
// ================= HELPER: build water level legend with actual min/max =================
function showYearWaterLevelLegendDynamic(title, min, max) {
  const range = max - min;
  const b1 = (min + range * 0.2).toFixed(2);
  const b2 = (min + range * 0.4).toFixed(2);
  const b3 = (min + range * 0.6).toFixed(2);
  const b4 = (min + range * 0.8).toFixed(2);

  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>${title}</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;${b1})<br>
      <span style="background:#6baed6"></span> Low (${b1}–${b2})<br>
      <span style="background:#2171b5"></span> Medium (${b2}–${b3})<br>
      <span style="background:#08519c"></span> High (${b3}–${b4})<br>
      <span style="background:#08306b"></span> Very High (&gt;${b4})
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

// ================= HELPER: build LULC legend with actual min/max =================
function showYearLulcLegendDynamic(min, max) {
  const range = max - min;
  const b1 = (min + range * 0.2).toFixed(1);
  const b2 = (min + range * 0.4).toFixed(1);
  const b3 = (min + range * 0.6).toFixed(1);
  const b4 = (min + range * 0.8).toFixed(1);

  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>LULC</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;${b1})<br>
      <span style="background:#6baed6"></span> Low (${b1}–${b2})<br>
      <span style="background:#2171b5"></span> Medium (${b2}–${b3})<br>
      <span style="background:#08519c"></span> High (${b3}–${b4})<br>
      <span style="background:#08306b"></span> Very High (&gt;${b4})
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

// ================= HELPER: build Population legend with actual min/max =================
function showYearPopLegendDynamic(min, max) {
  const range = max - min;
  const b1 = Math.round(min + range * 0.2);
  const b2 = Math.round(min + range * 0.4);
  const b3 = Math.round(min + range * 0.6);
  const b4 = Math.round(min + range * 0.8);

  rasterLegend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = `
      <b>Population Density</b><br>
      <span style="background:#c6dbef"></span> Very Low (&le;${b1})<br>
      <span style="background:#6baed6"></span> Low (${b1}–${b2})<br>
      <span style="background:#2171b5"></span> Medium (${b2}–${b3})<br>
      <span style="background:#08519c"></span> High (${b3}–${b4})<br>
      <span style="background:#08306b"></span> Very High (&gt;${b4})
    `;
    return div;
  };
  rasterLegend.addTo(map);
}

document.addEventListener("click", async function (e) {

  // ================= CLIP PRECIP =================
  if (e.target.id === "clipPrecipBtn") {
    const r = await fetch("/api/collaborator-clip-precip");
    if (!r.ok) return alert("Error");

    const t = await fetch(`${BASE_PATH}/raster/precip_clipped.tif?ts=` + Date.now());
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);

    if (precipRasterLayer) map.removeLayer(precipRasterLayer);

    precipRasterLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => getPrecipColor(v[0])
    });

    precipRasterLayer.addTo(map);
    showPrecipLegend(getRangeLabel("precip"));
    document.getElementById("showPrecipRaster").checked = true;
  }

  // ================= TOGGLE PRECIP =================
  if (e.target.id === "showPrecipRaster") {
    if (!precipRasterLayer) return alert("Clip first");

    if (e.target.checked) {
      precipRasterLayer.addTo(map);
      showPrecipLegend(getRangeLabel("precip"));
    } else {
      map.removeLayer(precipRasterLayer);
      clearRasterLegend();
    }
  }

  // ================= CLIP TEMP =================
  if (e.target.id === "clipTempBtn") {
    const r = await fetch("/api/collaborator-clip-temperature");
    if (!r.ok) return alert("Error");

    const t = await fetch(`${BASE_PATH}/raster/temp_clipped.tif?ts=` + Date.now());
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);

    if (tempRasterLayer) map.removeLayer(tempRasterLayer);

    tempRasterLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => getTempColor(v[0])
    });

    tempRasterLayer.addTo(map);
    showTempLegend();
    document.getElementById("showTempRaster").checked = true;
  }

  // ================= TOGGLE TEMP =================
  if (e.target.id === "showTempRaster") {
    if (!tempRasterLayer) return alert("Clip first");

    if (e.target.checked) {
      tempRasterLayer.addTo(map);
      showTempLegend();
    } else {
      map.removeLayer(tempRasterLayer);
      clearRasterLegend();
    }
  }

  // ================= FULL PRECIP =================
  if (e.target.id === "showFullPrecip") {
    if (e.target.checked) {
      const precipUrl = getRangeFileUrl("precip");
      if (!precipUrl) {
        e.target.checked = false;
        return alert("Precipitation full raster not found in collaborator raster folder");
      }
      if (!fullPrecipLayer) {
        const r = await fetch(`${precipUrl}?ts=${Date.now()}`);
        const b = await r.arrayBuffer();
        const g = await parseGeoraster(b);

        fullPrecipLayer = new GeoRasterLayer({
          georaster: g,
          opacity: 0.7,
          resolution: 256,
          pixelValuesToColorFn: v => getPrecipColor(v[0])
        });
      }

      fullPrecipLayer.addTo(map);
  showPrecipLegend(getRangeLabel("precip"));

    } else {
      if (fullPrecipLayer) map.removeLayer(fullPrecipLayer);
      clearRasterLegend();
    }
  }

  // ================= FULL TEMP =================
  if (e.target.id === "showFullTemp") {
    if (e.target.checked) {
      const tempUrl = getRangeFileUrl("temp");
      if (!tempUrl) {
        e.target.checked = false;
        return alert("Temperature full raster not found in collaborator raster folder");
      }
      if (!fullTempLayer) {
        const r = await fetch(`${tempUrl}?ts=${Date.now()}`);
        const b = await r.arrayBuffer();
        const g = await parseGeoraster(b);

        fullTempLayer = new GeoRasterLayer({
          georaster: g,
          opacity: 0.7,
          resolution: 256,
          pixelValuesToColorFn: v => getTempColor(v[0])
        });
      }

      fullTempLayer.addTo(map);
      showTempLegend();

    } else {
      if (fullTempLayer) map.removeLayer(fullTempLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR PRECIP GENERATE =================
  if (e.target.id === "clipYearPrecipBtn") {
    const year = document.getElementById("precipYear").value;
    if (!year) return alert("Select year");

    await fetch(`/api/collaborator-generate-precip-year?year=${year}`);

    const t = await fetch(`${BASE_PATH}/precip/output_precip_rasters/precip_${year}_30m.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);

    const min = g.mins[0];
    const max = g.maxs[0];

    if (yearPrecipLayer) map.removeLayer(yearPrecipLayer);

    yearPrecipLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => {
        const val = v[0];
        if (val == null || isNaN(val)) return null;

        const ratio = (val - min) / (max - min);
        if (ratio < 0.2) return "#c6dbef";
        if (ratio < 0.4) return "#6baed6";
        if (ratio < 0.6) return "#2171b5";
        if (ratio < 0.8) return "#08519c";
        return "#08306b";
      }
    });

    yearPrecipLayer.addTo(map);
    clearRasterLegend();
    showYearPrecipLegend(`Precipitation (${year})`, min, max);
    document.getElementById("showYearPrecip").checked = true;
  }

  // ================= YEAR PRECIP TOGGLE =================
  if (e.target.id === "showYearPrecip") {
    if (!yearPrecipLayer) return alert("Generate first");

    if (e.target.checked) {
      yearPrecipLayer.addTo(map);
      // Re-show legend with stored min/max via georaster
      showPrecipLegend(`Precipitation (${document.getElementById("precipYear").value})`);
    } else {
      map.removeLayer(yearPrecipLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR TEMP GENERATE =================
  if (e.target.id === "clipYearTempBtn") {
    const year = document.getElementById("tempYear").value;
    if (!year) return alert("Select year");

    await fetch(`/api/collaborator-generate-temp-year?year=${year}`);

    const t = await fetch(`${BASE_PATH}/temp/output_temp_rasters/temp_${year}_30m.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);

    if (yearTempLayer) map.removeLayer(yearTempLayer);

    yearTempLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => getTempColor(v[0])
    });

    yearTempLayer.addTo(map);
    showTempLegend();
    document.getElementById("showYearTemp").checked = true;
  }

  // ================= YEAR TEMP TOGGLE =================
  if (e.target.id === "showYearTemp") {
    if (!yearTempLayer) return alert("Generate first");

    if (e.target.checked) {
      yearTempLayer.addTo(map);
      showTempLegend();
    } else {
      map.removeLayer(yearTempLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR LULC GENERATE =================
  if (e.target.id === "clipYearLulcBtn") {
    const year = document.getElementById("LulcYear").value;
    if (!year) return alert("Select year");

    const t = await fetch(`${BASE_PATH}/raster/lulc/lulc_${year}.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);
    const min = g.mins[0];
    const max = g.maxs[0];

    if (yearLulcLayer) map.removeLayer(yearLulcLayer);

    yearLulcLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => {
        const val = v[0];
        if (val == null || isNaN(val)) return null;

       const ratio = (val - min) / (max - min);
        if (ratio < 0.2) return "#c6dbef";
        if (ratio < 0.4) return "#6baed6";
        if (ratio < 0.6) return "#2171b5";
        if (ratio < 0.8) return "#08519c";
        return "#08306b";
      }
    });

    yearLulcLayer.addTo(map);
    clearRasterLegend();
    showYearLulcLegendDynamic(min, max);
    document.getElementById("showYearLulc").checked = true;
  }

  // ================= YEAR LULC TOGGLE =================
  if (e.target.id === "showYearLulc") {
    if (!yearLulcLayer) return alert("Generate first");

    if (e.target.checked) {
      yearLulcLayer.addTo(map);
      showLulcLegend();
    } else {
      map.removeLayer(yearLulcLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR POP GENERATE =================
  if (e.target.id === "clipYearPopBtn") {
    const year = document.getElementById("PopYear").value;
    if (!year) return alert("Select year");

    const t = await fetch(`${BASE_PATH}/raster/pop/pop_${year}.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);
    const min = g.mins[0];
    const max = g.maxs[0];

    if (yearPopLayer) map.removeLayer(yearPopLayer);

    yearPopLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => {
        const val = v[0];
        if (val == null || isNaN(val)) return null;

       const ratio = (val - min) / (max - min);
        if (ratio < 0.2) return "#c6dbef";
        if (ratio < 0.4) return "#6baed6";
        if (ratio < 0.6) return "#2171b5";
        if (ratio < 0.8) return "#08519c";
        return "#08306b";
      }
    });

    yearPopLayer.addTo(map);
    clearRasterLegend();
    showYearPopLegendDynamic(min, max);
    document.getElementById("showYearPop").checked = true;
  }

  // ================= YEAR POP TOGGLE =================
  if (e.target.id === "showYearPop") {
    if (!yearPopLayer) return alert("Generate first");

    if (e.target.checked) {
      yearPopLayer.addTo(map);
      showPopLegend();
    } else {
      map.removeLayer(yearPopLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR STREAMFLOW GENERATE =================
  if (e.target.id === "clipYearStreamFlowBtn") {
    const year = document.getElementById("StreamFlowYear").value;
    const month = document.getElementById("StreamFlowMonth").value;
    if (!year) return alert("Select year");

    await fetch(`/api/collaborator-generate-streamflow-year?year=${year}&month=${month}`);

    const t = await fetch(`${BASE_PATH}/streamflow/output_streamflow_rasters/streamflow_${year}_${month}_30m.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);

    if (yearStreamFlowLayer) map.removeLayer(yearStreamFlowLayer);

    const min = g.mins[0];
    const max = g.maxs[0];

    yearStreamFlowLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => {
        const val = v[0];
        if (val == null || isNaN(val)) return null;

        const ratio = (val - min) / (max - min);
        if (ratio < 0.2) return "#c6dbef";
        if (ratio < 0.4) return "#6baed6";
        if (ratio < 0.6) return "#2171b5";
        if (ratio < 0.8) return "#08519c";
        return "#08306b";
      }
    });

    yearStreamFlowLayer.addTo(map);
    clearRasterLegend();
    showYearStreamFlowLegendDynamic(`StreamFlow (${year} - ${month})`, min, max);
    document.getElementById("showYearStreamFlow").checked = true;
  }

  // ================= YEAR STREAMFLOW TOGGLE =================
  if (e.target.id === "showYearStreamFlow") {
    if (!yearStreamFlowLayer) return alert("Generate first");
    const year = document.getElementById("StreamFlowYear").value;
    const month = document.getElementById("StreamFlowMonth").value;
    if (e.target.checked) {
      yearStreamFlowLayer.addTo(map);
      showStreamFlowLegend(`StreamFlow (${year} - ${month})`);
    } else {
      map.removeLayer(yearStreamFlowLayer);
      clearRasterLegend();
    }
  }

  // ================= YEAR WATERLEVEL GENERATE =================
  if (e.target.id === "clipYearWaterLevelBtn") {
    const year = document.getElementById("WaterLevelYear").value;
    const month = document.getElementById("WaterLevelMonth").value;
    if (!year) return alert("Select year");

    await fetch(`/api/collaborator-generate-waterlevel-year?year=${year}&month=${month}`);

    const t = await fetch(`${BASE_PATH}/waterlevel/output_waterlevel_rasters/waterlevel_${year}_${month}_30m.tif?ts=${Date.now()}`);
    const b = await t.arrayBuffer();
    const g = await parseGeoraster(b);
    const min = g.mins[0];
    const max = g.maxs[0];

    if (yearWaterLevelLayer) map.removeLayer(yearWaterLevelLayer);

    yearWaterLevelLayer = new GeoRasterLayer({
      georaster: g,
      opacity: 0.7,
      resolution: 256,
      pixelValuesToColorFn: v => {
        const val = v[0];
        if (val == null || isNaN(val)) return null;

        const ratio = (val - min) / (max - min);
        if (ratio < 0.2) return "#c6dbef";
        if (ratio < 0.4) return "#6baed6";
        if (ratio < 0.6) return "#2171b5";
        if (ratio < 0.8) return "#08519c";
        return "#08306b";
      }
    });

    yearWaterLevelLayer.addTo(map);
    clearRasterLegend();
    showYearWaterLevelLegendDynamic(`Water Level (${year} - ${month})`, min, max);
    document.getElementById("showYearWaterLevel").checked = true;
  }

  // ================= YEAR WATERLEVEL TOGGLE =================
  if (e.target.id === "showYearWaterLevel") {
    if (!yearWaterLevelLayer) return alert("Generate first");
    const year = document.getElementById("WaterLevelYear").value;
    const month = document.getElementById("WaterLevelMonth").value;
    if (e.target.checked) {
      yearWaterLevelLayer.addTo(map);
      showWaterLevelLegend(`Water Level (${year} - ${month})`);
    } else {
      map.removeLayer(yearWaterLevelLayer);
      clearRasterLegend();
    }
  }

});

let accIndex = 0;
function toggleAcc(header) {
  const items = document.querySelectorAll(".acc-item");
  const item = header.parentElement;

  items.forEach((i, idx) => {
    if (i === item) {
      i.classList.add("active");
      accIndex = idx;
    } else {
      i.classList.remove("active");
    }
  });
}

function openAccordionByIndex(idx) {
  const items = document.querySelectorAll(".acc-item");
  items.forEach(i => i.classList.remove("active"));

  if (items[idx]) {
    items[idx].classList.add("active");
    accIndex = idx;
  }
}

document.getElementById("navUp").onclick = () => {
  const items = document.querySelectorAll(".acc-item");
  if (accIndex > 0) openAccordionByIndex(accIndex - 1);
};

document.getElementById("navDown").onclick = () => {
  const items = document.querySelectorAll(".acc-item");
  if (accIndex < items.length - 1) openAccordionByIndex(accIndex + 1);
};

// Open first parameter by default
openAccordionByIndex(0);

async function populateYearsDynamic(selectId, dataset) {
  const select = document.getElementById(selectId);
  if (!select) return;

  try {
    const res = await fetch(`/api/collaborator-get-years/${dataset}`);
    const years = await res.json();

    select.innerHTML = ""; // clear old

    if (!years.length) {
      const opt = document.createElement("option");
      opt.textContent = "No data";
      select.appendChild(opt);
      return;
    }

    years.forEach(y => {
      const opt = document.createElement("option");
      opt.value = y;
      opt.textContent = y;
      select.appendChild(opt);
    });

  } catch (err) {
    console.error("Year load failed:", err);
  }
}

const months = [
  { name: "Jan", value: "01" },
  { name: "Feb", value: "02" },
  { name: "Mar", value: "03" },
  { name: "Apr", value: "04" },
  { name: "May", value: "05" },
  { name: "Jun", value: "06" },
  { name: "Jul", value: "07" },
  { name: "Aug", value: "08" },
  { name: "Sep", value: "09" },
  { name: "Oct", value: "10" },
  { name: "Nov", value: "11" },
  { name: "Dec", value: "12" }
];

function populateMonths(id) {
  const select = document.getElementById(id);
  if (!select) return;

  months.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = m.name;
    select.appendChild(opt);
  });
}

window.addEventListener("load", async () => {

  await populateYearsDynamic("precipYear", "precip");
  await populateYearsDynamic("tempYear", "temp");
  await populateYearsDynamic("LulcYear", "lulc");
  await populateYearsDynamic("PopYear", "pop");
  await populateYearsDynamic("StreamFlowYear", "streamflow");
  await populateYearsDynamic("WaterLevelYear", "waterlevel");
  populateMonths("StreamFlowMonth");
  populateMonths("WaterLevelMonth");
});


/* ============================================================
   ✅ CONDITIONAL PARAMETER VISIBILITY ENGINE
   ============================================================ */

// 🔹 CONFIG (manual control if needed)
const DATA_CONFIG = {
  static: {
    precip: true,
    temp: true,
    fullPrecip: true,
    fullTemp: true,
    lulc: true,
    pop: true
  },
  dynamic: {
    precip: true,
    temp: true,
    lulc: true,
    pop: true,
    streamflow: true,
    waterlevel: true
  }
};

// 🔹 Check file existence (for auto-detection)
async function checkFileExists(url) {
  try {
    const res = await fetch(url, { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}

// 🔹 Auto detect available datasets (FINAL VERSION)
async function autoDetectData() {

  try {
    /* ================= BASE PATH ================= */

    
    

    /* ================= STATIC DATA ================= */

    DATA_CONFIG.static.precip =
      await checkFileExists(`${BASE_PATH}/raster/precip_raster.tif`);

    DATA_CONFIG.static.temp =
      await checkFileExists(`${BASE_PATH}/raster/temp_raster.tif`);

     DATA_CONFIG.static.fullPrecip = !!getRangeFileUrl("precip");

     DATA_CONFIG.static.fullTemp = !!getRangeFileUrl("temp");

    DATA_CONFIG.static.lulc =
      await checkFileExists(`${BASE_PATH}/raster/lulc/sample.tif`);

    DATA_CONFIG.static.pop =
      await checkFileExists(`${BASE_PATH}/raster/pop/sample.tif`);

    /* ================= DYNAMIC DATA ================= */
    // We check ONE sample file to confirm dataset exists

    DATA_CONFIG.dynamic.precip =
      await checkFileExists(`${BASE_PATH}/precip/sample.csv`);

    DATA_CONFIG.dynamic.temp =
      await checkFileExists(`${BASE_PATH}/temp/sample.csv`);

    DATA_CONFIG.dynamic.lulc =
      await checkFileExists(`${BASE_PATH}/lulc/sample.csv`);

    DATA_CONFIG.dynamic.pop =
      await checkFileExists(`${BASE_PATH}/pop/sample.csv`);

    DATA_CONFIG.dynamic.streamflow =
      await checkFileExists(`${BASE_PATH}/streamflow/sample.csv`);

    DATA_CONFIG.dynamic.waterlevel =
      await checkFileExists(`${BASE_PATH}/waterlevel/sample.csv`);

    /* ================= APPLY UI ================= */

    applyVisibilityRules();

  } catch (err) {

    console.warn("⚠️ Auto-detect failed, falling back to defaults", err);

    // fallback → show basic layers
    DATA_CONFIG.static.precip = true;
    DATA_CONFIG.static.temp = true;

    DATA_CONFIG.dynamic.precip = true;
    DATA_CONFIG.dynamic.temp = true;

    applyVisibilityRules();
  }
}

// 🔹 Apply visibility rules to UI
function applyVisibilityRules() {

  const rules = [
    // ===== STATIC =====
    { id: "block-precip-static", show: DATA_CONFIG.static.precip },
    { id: "block-temp-static", show: DATA_CONFIG.static.temp },
    { id: "block-full-precip", show: DATA_CONFIG.static.fullPrecip },
    { id: "block-full-temp", show: DATA_CONFIG.static.fullTemp },
    { id: "block-lulc-static", show: DATA_CONFIG.static.lulc },
    { id: "block-pop-static", show: DATA_CONFIG.static.pop },

    // ===== DYNAMIC =====
    { id: "block-precip-dynamic", show: DATA_CONFIG.dynamic.precip },
    { id: "block-temp-dynamic", show: DATA_CONFIG.dynamic.temp },
    { id: "block-lulc-dynamic", show: DATA_CONFIG.dynamic.lulc },
    { id: "block-pop-dynamic", show: DATA_CONFIG.dynamic.pop },
    { id: "block-streamflow", show: DATA_CONFIG.dynamic.streamflow },
    { id: "block-waterlevel", show: DATA_CONFIG.dynamic.waterlevel }
  ];

  rules.forEach(r => {
    const el = document.getElementById(r.id);
    if (el) {
      el.style.display = r.show ? "block" : "none";
    }
  });

  // Reset accordion index if hidden
  setTimeout(() => {
    const visibleItems = Array.from(document.querySelectorAll(".acc-item"))
      .filter(el => el.style.display !== "none");

    if (visibleItems.length > 0) {
      visibleItems[0].classList.add("active");
    }
  }, 100);
}

/* ============================================================
   🚀 INIT (IMPORTANT)
   ============================================================ */

window.addEventListener("load", async () => {
  await initBasePath();   // ✅ ensure it's ready
  await loadCollaboratorRasterRangeMeta();
  await autoDetectData(); // now safe to use BASE_PATH
});