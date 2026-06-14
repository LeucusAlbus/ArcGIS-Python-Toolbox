import importlib
from pathlib import Path
import arcpy
import feature_layer_to_leaflet_utils.color_functions as color_functions
import feature_layer_to_leaflet_templates.html_template as html_template

importlib.reload(color_functions)
importlib.reload(html_template)

cim_color_to_rgba = color_functions.cim_color_to_rgba
rgba_to_hex = color_functions.rgba_to_hex
html = html_template.html


def run_tool(fc, selected_fields, background, basemap, html_option, output_folder, messages):

    web_title = "© Andres Guilabert"
    shapetype = arcpy.Describe(fc).shapetype
    

    #----------------------------------------------------------------------------------------------------------------------------------
    # BACKGROUND CONFIGURATION (map canvas vs basemap)
    # Resolves map canvas background color or external basemap dependency.
    #----------------------------------------------------------------------------------------------------------------------------------

    if background == "Active Map Background Color":
        basemap = None

        # Access current ArcGIS Pro map document (session context)
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        map0 = aprx.activeMap
        if map0:
            # Extract CIM definition to access rendering properties
            cim_map0 = map0.getDefinition("V3")

            # Convert ArcGIS CIM color (RGBA) into web-compatible HEX format (utils.py function)
            mb_color = cim_color_to_rgba(cim_map0.backgroundColor)
            messages.addMessage(f"Map background Color: {str(mb_color)}")
            mb_color_hex = rgba_to_hex(mb_color[0], mb_color[1], mb_color[2], mb_color[3]*255/100)
            messages.addMessage(f"Map background Color: {mb_color_hex}")
            
        else:
            raise RuntimeError("Mapa no encontrado")
        
    elif background == "Custom BaseMap":
        # Fully transparent canvas (basemap-driven rendering)
        mb_color_hex = "#00000000"


    #----------------------------------------------------------------------------------------------------------------------------------
    # BASEMAP RESOLUTION (tile provider configuration)
    # Resolves basemap selection into Leaflet tile layer definition
    #----------------------------------------------------------------------------------------------------------------------------------
    
    if basemap:
      
          
      dict_basemaps = {"ESRI streets" : "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                      "ESRI satellite" : "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                      "CARTO dark" : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
                      "CARTO positron" : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                      "CARTO voyager" : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"}

      basemap_url = dict_basemaps[basemap]

      # Generate Leaflet tile layer (provider-specific configuration)
      if basemap in ["CARTO dark","CARTO positron","CARTO voyager"]:

          html_basemap = """
          L.tileLayer('%%basemap_url%%', {
              attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
              subdomains: 'abcd',
              maxZoom: 20
          }).addTo(map);
          """

      elif basemap in ["ESRI streets", "ESRI satellite"]:
          html_basemap = """
          L.tileLayer('%%basemap_url%%', {
              attribution: 'Tiles &copy; Esri',
              maxZoom: 20
          }).addTo(map);
      
            """

      # Inject resolved tile URL into template    
      html_basemap = html_basemap.replace("%%basemap_url%%", basemap_url)


    else:
        # Active Map Color Background selected -> no Leaflet basemap injected
        html_basemap = ""

    
# ------------------------------------------------------------------
# LEAFLET STYLE FUNCTION GENERATION
# ------------------------------------------------------------------
# Build geometry-specific styling logic to be injected into
# the Leaflet template.

    if shapetype == "Polygon":
        html_style = """
        function style(feature) {
            return {
                fillColor: feature.properties.fill_color,
                fillOpacity: feature.properties.fill_opacity,
                color: feature.properties.outline_color,
                opacity: feature.properties.outline_opacity,
                weight: feature.properties.outline_width_px
            };
        }  """

        html_layer = "style: style"
        
    elif shapetype == "Polyline":
        html_style = """
        function style(feature) {
            return {
                color: feature.properties.line_color,
                opacity: feature.properties.line_opacity,
                weight: feature.properties.line_width_px
            };
        }  """

        html_layer = "style: style"

        
    elif shapetype == "Point":
        html_style = """
        function pointToLayer(feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 6,
                fillColor: feature.properties.fill_color,
                fillOpacity: feature.properties.fill_opacity,
                color: feature.properties.outline_color,
                opacity: feature.properties.outline_opacity,
                weight: feature.properties.outline_width_px
            });
        }"""

        html_layer = "pointToLayer: pointToLayer"
    
    

    #----------------------------------------------------------------------------------------------------------------------------------
    # TOOLTIP CONSTRUCTION 
    # Builds dynamic Leaflet tooltip content from selected feature attributes
    #----------------------------------------------------------------------------------------------------------------------------------
    
    parts = []
    for f in selected_fields:
        parts.append(f"'<b>{f}:</b> ' + feature.properties.{f}")

    tooltip_html = " + '<br>' + ".join(parts)

    # Wrap tooltip content in styled HTML container
    tooltip_html = (
        "'<div style=\"font-size:13px; line-height:1.2; padding:8px 10px; "
        "background:white; color:black; border-radius:4px;\">' + "
        + tooltip_html +
        " + '</div>'"
    )


    #----------------------------------------------------------------------------------------------------------------------------------
    # GEOJSON GENERATION PIPELINE
    # Converts ArcGIS feature class into web-ready GeoJSON dataset
    #----------------------------------------------------------------------------------------------------------------------------------

    
    # Attribute filtering based on feature class geometry type
    shapetype = arcpy.Describe(fc).shapetype

    if shapetype in ["Point", "Polygon"]:
        sym_fields = ["fill_color", "fill_opacity", "outline_color", "outline_opacity", "outline_width_px"]
    elif shapetype == "Polyline":
        sym_fields = ["line_color", "line_opacity", "line_width_px"]

    # Merge user-selected fields with symbology attributes
    fields = selected_fields + sym_fields

    # Remove duplicates while preserving order
    fields = list(dict.fromkeys(fields)) #Elimino duplicados en caso de haberlos
    
    # Build ArcPy field mappings
    fields_mappings = arcpy.FieldMappings()
    for f in fields:
        field_map = arcpy.FieldMap()
        field_map.addInputField(fc, f)
        fields_mappings.addFieldMap(field_map)
       
    # Store current ArcPy environment settings for later restoration
    old_z = arcpy.env.outputZFlag
    old_addoutput = arcpy.env.addOutputsToMap
    old_overwrite = arcpy.env.overwriteOutput
    
    try:
        # Set geoprocessing environment for 2D export workflow
        arcpy.env.outputZFlag = False
        arcpy.env.addOutputsToMap = False
        arcpy.env.overwriteOutput = True
        
    
        # Export to GeoJSON workflow
        output_folder = Path(output_folder)
        output_path = output_folder / "geodata.geojson"
        output_path.unlink(missing_ok=True)
        output_geojson = str(output_path)
        fc_temp = arcpy.CreateUniqueName("fc_temp","memory")
        arcpy.conversion.ExportFeatures(fc, fc_temp, field_mapping=fields_mappings)
        arcpy.conversion.FeaturesToJSON(fc_temp, output_geojson, geoJSON="GEOJSON")

              
   
    finally:

        # Restore geoprocessing environment
        arcpy.env.outputZFlag = old_z
        arcpy.env.addOutputsToMap = old_addoutput
        arcpy.env.overwriteOutput = old_overwrite
        
        # Cleanup in-memory dataset
        if fc_temp:
            arcpy.management.Delete(fc_temp)
        
        messages.addMessage("Leaflet map successfully generated.")
    

    #----------------------------------------------------------------------------------------------------------------------------------
    # TEMPLATE RENDERING (inject runtime values into HTML)
    # Resolves Leaflet web map by injecting computed GIS values into HTML template
    #----------------------------------------------------------------------------------------------------------------------------------

        
    if html_option:
        with open(output_geojson, "r", encoding="utf-8") as f:
            geojson_text = f.read()

        html_loader = """
        const datos = %%geojson%%;
        layer.addData(datos);
        fitMapToData(datos);"""

        html_loader = html_loader.replace("%%geojson%%", geojson_text)

        #Delete geojson data file
        output_path.unlink()
        messages.addMessage("BORRADO")
        
    
    else:
        html_loader = """
        fetch('geodata.geojson')
            .then(r => r.json())
            .then(datos => {
                layer.addData(datos);
                fitMapToData(datos);
            });"""

    # Inject runtime values into HTML template placeholders
    html_index = (html.replace("%%mb_color%%", mb_color_hex)
                  .replace("%%basemap%%", html_basemap)
                  .replace("%%tooltip_html%%", tooltip_html)
                  .replace("%%web_title%%", web_title)
                  .replace("%%style%%", html_style)
                  .replace("%%layer%%", html_layer)
                  .replace("%%loader%%", html_loader))
    
    
    

    # Write Webmap to disk
    output_html = str(output_folder / "index.html")      
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_index)