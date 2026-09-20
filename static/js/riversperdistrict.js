Promise.all([
  fetch("/data/admin/display/geojson/district_boundary.geojson").then(r => r.json()),
  fetch("/data/admin/display/geojson/narmada_named_network.geojson").then(r => r.json())
]).then(([districts, rivers]) => {

  const tbody = document.querySelector("#resultTable tbody");

  districts.features.forEach(district => {
    const districtName =
      district.properties.DISTRICT ||
      district.properties.NAME ||
      "Unknown District";

    const riverNames = new Set();

    rivers.features.forEach(river => {
      // Spatial intersection check
      if (turf.booleanIntersects(district, river)) {
        const rName =
          river.properties.NAME ||
          river.properties.RIVER_NAME ||
          "Unnamed River";
        riverNames.add(rName);
      }
    });

    // Create table row
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${districtName}</td>
      <td class="count">${riverNames.size}</td>
      <td class="river-list">${[...riverNames].join(", ") || "-"}</td>
    `;

    tbody.appendChild(tr);
  });
});