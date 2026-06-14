html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>%%web_title%%</title>

  <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

  <style>
    body { margin: 0; }
    #map {
      height: 100vh;
    }
  </style>
</head>

<body>

<div id="map"></div>

<script>
  // -------------------------
  // 1. MAPA
  // -------------------------
  var map = L.map('map', {
    zoomControl: true
  }).setView([20, 0], 2);

  map.getContainer().style.background = '%%mb_color%%';



  // -------------------------
  // 2. BASE MAP
  // -------------------------
  %%basemap%%


  // -------------------------
  // 3. ESTILO DEL LAYER
  // -------------------------
  %%style%%



  // -------------------------
  // 4. TOOLTIP (REEMPLAZADO)
  // -------------------------
  const tooltip = L.tooltip({
    sticky: false,
    opacity: 0.9,
    direction: 'auto'
  });
  
  function onEachFeature(feature, layer) {

    layer.on('mouseover', function (e) {

      tooltip
        .setContent(%%tooltip_html%%)
        .setLatLng(e.latlng)
        .addTo(map)
        .openOn(map);
    });

    layer.on('mousemove', function (e) {
      tooltip.setLatLng(e.latlng);
    });

    layer.on('mouseout', function () {
      map.closeTooltip(tooltip);
    });
  }


  // -------------------------
  // 5. ZOOM Y LÍMITES
  // -------------------------
  function fitMapToData(datos) {

    const bounds = L.geoJSON(datos).getBounds();
    const padded = bounds.pad(0.2);

    map.setMaxBounds(padded);
    map.options.maxBoundsViscosity = 1.0;

    map.setMinZoom(2);
    map.setMaxZoom(18);
  }


  // -------------------------
  // 6. LAYER
  // -------------------------
  var layer = L.geoJSON(null, {
    %%layer%%,
    onEachFeature: onEachFeature
  }).addTo(map);


  // -------------------------
  // 7. CARGA DE DATOS
  // -------------------------
  %%loader%%

</script>

</body>
</html>
"""