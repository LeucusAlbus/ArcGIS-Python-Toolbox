import pandas as pd
import arcpy
import importlib
import feature_layer_to_leaflet_utils.color_functions as color_functions

importlib.reload(color_functions)

arcgis_color_to_rgba = color_functions.arcgis_color_to_rgba
cim_color_to_rgba = color_functions.cim_color_to_rgba
rgba_to_hex = color_functions.rgba_to_hex


def run_tool(lyr_obj, output_path, mode, messages):
    
    
    symb = {} # Execution context for symbology processing pipeline
    
    symb["lyr_obj"] = lyr_obj                                       # Input layer reference    
    symb["output_path"] = output_path                               # Feature class output path
    symb["option"] = mode                                           # Color encoding mode
    symb["lyr_sym"] = lyr_obj.symbology                             # ArcGIS Pro symbology object  
    symb["lyr_cim"] = lyr_obj.getDefinition("V3")                   # CIM definition
    symb["shape_type"] = arcpy.da.Describe(lyr_obj)['shapeType']    # Geometry type of input feature class
    
    # Renderer object
    renderer = getattr(symb["lyr_sym"], "renderer", None)
    symb["renderer"] = renderer                                     # Renderer object


    # ------------------------------------------------------------------
    # RENDERER STATE EVALUATION (ArcGIS Pro snapshot behavior)
    # ------------------------------------------------------------------
    # The renderer object is re-evaluated at execution time to ensure
    # compatibility with the current symbology state.
    # This is required because ArcGIS Pro exposes symbology as a snapshot
    # of the layer state at selection time in the tool UI.
    
    # Set system note (informational, not validation error)
    messages.addMessage("Note: symbology is evaluated at layer selection time (ArcGIS Pro behavior)") 
    
    # Ensure layer has a valid symbology renderer
    if not renderer:
        msg = "Layer has no valid renderer"
        messages.addMessage(msg)
        raise ValueError(msg)
    
    # Extract renderer type
    renderer_type = renderer.type
    symb["renderer_type"] = renderer_type

    # Define supported renderer types
    supported_renderers = {"UniqueValueRenderer", "SimpleRenderer", "GraduatedColorsRenderer"}
    
    # Validate renderer compatibility with export engine
    if renderer_type not in supported_renderers:
        msg = f"Unsupported renderer type: {renderer_type}"
        messages.addMessage(msg)
        raise ValueError(msg)
     
    # Detect CIM-based value expression configuration
    cim_value_expression = getattr(symb["lyr_cim"].renderer, "valueExpressionInfo", None)
    expression_info = getattr(cim_value_expression, "title", None)
    
    # Bivariate (relationship-based) symbology is not supported
    if renderer_type =="UniqueValueRenderer" and expression_info == "Relationship":
        msg = "Bivariate symbology is not supported"
        messages.addMessage(msg)
        raise ValueError(msg)
    
    # Reject layers using Arcade / expression-driven symbology
    if expression_info:
        msg = "Value-based expressions are not supported"
        messages.addMessage(msg)
        raise ValueError(msg)
        
        
    
    # ------------------------------------------------------------------
    # SYMBOLOGY PROPERTY EXTRACTION
    # ------------------------------------------------------------------
    # Extracts renderer-specific styling information from ArcGIS CIM / renderer objects
    # and normalizes it into a structured internal representation for export pipeline.
    
    lyr_cim = symb["lyr_cim"]
    renderer = symb["renderer"]
    renderer_type = symb["renderer_type"]
    values_tuple = None   # Placeholder for value-based classification mapping (used in UniqueValueRenderer)
    
    
    # ------------------------------------------------------------------
    # SIMPLE RENDERER PROCESSING
    # ------------------------------------------------------------------
    if renderer_type == "SimpleRenderer":
    
        # Extract single-symbol styling
        symb["fill_colors"] = arcgis_color_to_rgba (renderer.symbol.color)
        symb["outline_colors"] = arcgis_color_to_rgba (renderer.symbol.outlineColor)
        symb["outline_widths"] = renderer.symbol.outlineWidth
        
    # ------------------------------------------------------------------
    # UNIQUE VALUE RENDERER PROCESSING
    # ------------------------------------------------------------------
    elif renderer_type == "UniqueValueRenderer":
    
        # Unique Value renderers may use multiple fields, where categories
        # are defined by combinations of attribute values across those fields.
        symb["classif_fields"] = renderer.fields
        
        # Default symbol (default styling for out of range values)
        symb["default_fill_color"] = arcgis_color_to_rgba(renderer.defaultSymbol.color)
        symb["default_outline_color"] = arcgis_color_to_rgba(renderer.defaultSymbol.outlineColor)
        symb["default_outline_width"] = renderer.defaultSymbol.outlineWidth
        

        if renderer.groups:
            
            # Properties used to build the Unique Values classification
            symb["classif_values"] = [ x.values[0] for x in renderer.groups[0].items]
    
            # Normalize values to ensure consistent key formatting
            def normalize(x):
                try:
                    return f"{float(x):.7f}"
                except:
                    return str(x)
                    
            symb["classif_values"] = [[normalize(v) for v in row] for row in symb["classif_values"]]

            # Extract styling per category      
            symb["fill_colors"] = [ arcgis_color_to_rgba(x.symbol.color) for x in renderer.groups[0].items]
            symb["outline_colors"] = [ arcgis_color_to_rgba(x.symbol.outlineColor) for x in renderer.groups[0].items]
            symb["outline_widths"] = [ x.symbol.outlineWidth for x in renderer.groups[0].items ]
     
            # Build Unique Values → Symbol mapping dictionaries (classification values into tuples to enable use as dictionary keys)
            values_tuple = [tuple(value) for value in symb["classif_values"]] 
           
            # Build lookup tables for styling
            symb["mapping_fill_color"] = dict(zip(values_tuple, symb["fill_colors"])) 
            symb["mapping_outline_color"] = dict(zip(values_tuple, symb["outline_colors"])) 
            symb["mapping_outline_width"] = dict(zip(values_tuple, symb["outline_widths"]))
       

    # ------------------------------------------------------------------
    # GRADUATED COLORS RENDERER PROCESSING
    # ------------------------------------------------------------------  
    
    elif renderer_type == "GraduatedColorsRenderer":
    
        # Classification properties used to build graduated color ranges
        symb["classbreaks"] = [_.upperBound for _ in renderer.classBreaks]  
        symb["lower_bound"] = renderer.lowerBound
        symb["classif_fields"] = [renderer.classificationField]
        
        # Extract class-based symbology from ArcGIS renderer
        fill_colors = [arcgis_color_to_rgba(x.symbol.color) for x in renderer.classBreaks] 
        outline_colors = [arcgis_color_to_rgba(x.symbol.outlineColor) for x in renderer.classBreaks] 
        outline_widths = [ x.symbol.outlineWidth for x in renderer.classBreaks ]
    
        # Access CIM symbology for out-of-range values (not accessible via arcpy)
        # -----------------------------------------------------------------------

        # Polygon default fill symbol
        if symb["shape_type"] == "Polygon":
            default_fill_color_cim = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[1].color
            default_fill_color = cim_color_to_rgba (default_fill_color_cim) # CIM color to RGBA using custom utility function

        # Dummy fill value to preserve downstream processing logic
        if symb["shape_type"] == "Polyline":
            default_fill_color = [0,0,0,0] 
    
        # Default line symbol
        if symb["shape_type"] in ["Polygon", "Polyline"]:
            default_outline_color_cim = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[0].color
            default_outline_color = cim_color_to_rgba (default_outline_color_cim) 
            default_outline_width = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[0].width

        # Point marker default symbol
        if symb["shape_type"] == "Point":
            default_fill_color_cim = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[0].markerGraphics[0].symbol.symbolLayers[1].color
            default_fill_color = cim_color_to_rgba (default_fill_color_cim) 
            default_outline_color_cim = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[0].markerGraphics[0].symbol.symbolLayers[0].color
            default_outline_color = cim_color_to_rgba (default_outline_color_cim)
            default_outline_width = lyr_cim.renderer.defaultSymbol.symbol.symbolLayers[0].markerGraphics[0].symbol.symbolLayers[0].width
            
        
        # Insert default symbol as class 0

        fill_colors = [default_fill_color] + fill_colors
        outline_colors = [default_outline_color] + outline_colors
        outline_widths = [default_outline_width] + outline_widths
        
        # Build lookup tables for class-based symbology assignment
        symb["mapping_fill_color"] = dict(enumerate(fill_colors))
        symb["mapping_outline_color"] = dict(enumerate(outline_colors))
        symb["mapping_outline_width"] = dict(enumerate(outline_widths))
    
    
    
    # ------------------------------------------------------------------
    # ATTRIBUTE TABLE EXTRACTION
    # ------------------------------------------------------------------
    # Load classification fields into a pandas DataFrame to support
    # renderer-specific symbology assignment logic.

    # Extract classification fields used to build categorical symbology.
    if symb.get("classif_fields"):
        sedf = pd.DataFrame(arcpy.da.SearchCursor(lyr_obj.dataSource, symb["classif_fields"]), columns=symb["classif_fields"]).convert_dtypes()
    
    # Extract OBJECTID as a fallback attribute when symbology is not field-based
    else:
        sedf = pd.DataFrame(arcpy.da.SearchCursor(lyr_obj.dataSource, ["OBJECTID"]), columns=["OBJECTID"])
    
    
    # ------------------------------------------------------------------
    # SYMBOLOGY ATTRIBUTE ASSIGNMENT
    # ------------------------------------------------------------------
    # Resolve renderer-driven symbology and write styling properties to attributes 
    
    renderer_type = symb["renderer_type"]
    
    # Assign a single symbol definition to all features
    if renderer_type == "SimpleRenderer":
      
        sedf["fill_color"] = [symb["fill_colors"]] * len(sedf)
        sedf["outline_color"] = [symb["outline_colors"]] * len(sedf)
        sedf["outline_width"] = [symb["outline_widths"]] * len(sedf)
    
    # Resolve category-based symbology from classification values
    elif renderer_type == "UniqueValueRenderer":
    
        if renderer.groups:

            # Normalize classification values to match ArcGIS renderer key formatting.
            # Numeric values are converted to a fixed precision string representation
            # so that feature attributes can be matched against renderer categories.
            for field in sedf[symb["classif_fields"]]:
                if pd.api.types.is_numeric_dtype(sedf[field]):
                    sedf[field] = sedf[field].apply(lambda x: f"{float(x):.7f}" if pd.notna(x) else None)
                else:
                    sedf[field] = sedf[field].astype(str)
                    
            # Build composite classification keys from renderer fields.
            # Unique Value renderers may be based on multiple attributes, therefore
            # category lookup requires a tuple-based key per feature.              
            keys = sedf[symb["classif_fields"]].astype(str).agg(tuple, axis=1)
            
            # Resolve fill color from category (features without a matching category receive the default symbol)
            values_fill_color = keys.map(symb["mapping_fill_color"])
            sedf["fill_color"] = values_fill_color.where(~values_fill_color.isna(), symb["default_fill_color"])

            # Resolve outline color from category
            values_outline_color = keys.map(symb["mapping_outline_color"])
            sedf["outline_color"] = values_outline_color.where(~values_outline_color.isna(), symb["default_outline_color"])

            # Resolve outline width from category    
            values_outline_width = keys.map(symb["mapping_outline_width"])
            sedf["outline_width"] = values_outline_width.where(~values_outline_width.isna(), symb["default_outline_width"])
    
        else:
            sedf["fill_color"] = [symb["default_fill_color"]] * len(sedf)
            sedf["outline_color"] = [symb["default_outline_color"]] * len(sedf)
            sedf["outline_width"] = [symb["default_outline_width"]] * len(sedf)
    
     
    elif renderer_type == "GraduatedColorsRenderer":
    
        # Build classification intervals from renderer break definitions
        classif_fields = symb["classif_fields"]
        bins_cut = [symb["lower_bound"] - 1e-9] + symb["classbreaks"]

        # Generate sequential class identifiers    
        labels_cut = list(range(1, len(bins_cut)))
        
        # Classify features into renderer-defined value ranges
        sedf["_symbology_class_"] = pd.cut(sedf[classif_fields[0]], bins=bins_cut, labels=labels_cut).astype("Int64")
        
        # Assign class 0 to values outside classification ranges
        sedf["_symbology_class_"] = sedf["_symbology_class_"].fillna(0)
      
        # Resolve symbology properties from class lookup tables
        sedf["fill_color"] = sedf["_symbology_class_"].map(symb["mapping_fill_color"])
        sedf["outline_color"] = sedf["_symbology_class_"].map(symb["mapping_outline_color"])
        sedf["outline_width"] = sedf["_symbology_class_"].map(symb["mapping_outline_width"])

        # Remove temporary classification field  
        sedf = sedf.drop("_symbology_class_", axis=1)
        
    
    else:
        raise ErrorValue("Renderer Type not Supported")
    
    

# ------------------------------------------------------------------
# COLOR ENCODING TRANSFORMATION
# ------------------------------------------------------------------
# Convert internal RGBA symbology values into web-compatible
# CSS color representations.
    
    # Selected output color encoding
    colormode = symb["option"]
    
    # Validate requested color encoding
    if colormode not in ["CSS RGBA", "8-digit HEX", "HEX + Opacity"]:
        raise ValueError("option 'CSS RGBA', '8-digit HEX', 'HEX + Opacity'")
    
    # Each encoding strategy defines how alpha transparency is exported
    # (inline CSS, packed HEX, or separated opacity attribute)

    # Convert RGBA arrays into CSS rgba() 
    if colormode == "CSS RGBA":
        sedf["fill_color"] = sedf["fill_color"].apply(lambda x: f"rgba({x[0]},{x[1]},{x[2]},{x[3]/100})") 
        sedf["outline_color"] = sedf["outline_color"].apply(lambda x: f"rgba({x[0]},{x[1]},{x[2]},{x[3]/100})") 
    
    # Convert RGBA arrays into CSS 8-digit hexadecimal notation (#RRGGBBAA)
    elif colormode == "8-digit HEX":
        sedf["fill_color"] = sedf["fill_color"].apply(lambda x: rgba_to_hex(x[0], x[1], x[2], x[3]*255/100))
        sedf["outline_color"] = sedf["outline_color"].apply(lambda x: rgba_to_hex(x[0], x[1], x[2], x[3]*255/100))
    
    # Split alpha channel into dedicated opacity attributes and convert colors to standard hexadecimal notation
    elif colormode == "HEX + Opacity":
        sedf["fill_opacity"] = sedf["fill_color"].apply(lambda x: x[3] / 100)
        sedf["fill_color"] = sedf["fill_color"].apply(lambda x: rgba_to_hex(x[0], x[1], x[2]))
        sedf["outline_opacity"] = sedf["outline_color"].apply(lambda x: x[3] / 100)
        sedf["outline_color"] = sedf["outline_color"].apply(lambda x: rgba_to_hex(x[0], x[1], x[2]))
        
    # Convert ArcGIS line widths from points to CSS pixels   
    sedf["outline_width"] = sedf["outline_width"] * 96/72 

    # Rename field to reflect output unit
    sedf = sedf.rename({"outline_width":"outline_width_px"}, axis=1)
    
    
    # ------------------------------------------------------------------
    # FEATURE CLASS EXPORT AND ATTRIBUTE MATERIALIZATION
    # ------------------------------------------------------------------
    # Rendered symbology attributes into a new feature class
    
    output_path = symb["output_path"]
    
    # Extract attribute arrays for efficient row-wise updates
    fill_color = sedf["fill_color"].to_list()
    outline_color = sedf["outline_color"].to_list()
    outline_width_px = sedf["outline_width_px"].to_list()

    # Opacity arrays are only required for split-opacity encoding mode
    if colormode == "HEX + Opacity":
        fill_opacity = sedf["fill_opacity"].to_list()
        outline_opacity = sedf["outline_opacity"].to_list()
        
    
    # Preserve ArcGIS environment state
    old_add = arcpy.env.addOutputsToMap
    old_overwrite = arcpy.env.overwriteOutput
    
    # Temporarily override environment for controlled export
    arcpy.env.addOutputsToMap = False
    arcpy.env.overwriteOutput = True
    
    # Create output feature class from input layer source
    fc = arcpy.management.CopyFeatures(lyr_obj.dataSource, output_path)[0]
    
    # Apply line symbology attributes for polyline geometries
    if symb["shape_type"] == "Polyline":
        
        # Store line color and line width attributes without separated opacity field
        if colormode in ["CSS RGBA", "8-digit HEX"]:    
            arcpy.management.AddField(fc, "line_color", "TEXT")
            arcpy.management.AddField(fc, "line_width_px", "DOUBLE")
            
            with arcpy.da.UpdateCursor(fc, ["line_color", "line_width_px"]) as cursor:
                for i, row in enumerate(cursor):
                    row[0] = outline_color[i]
                    row[1] = outline_width_px[i]
                    cursor.updateRow(row)

        # Store line color and line width attributes with separated opacity field
        elif colormode == "HEX + Opacity":
            arcpy.management.AddField(fc, "line_color", "TEXT")
            arcpy.management.AddField(fc, "line_opacity", "DOUBLE")
            arcpy.management.AddField(fc, "line_width_px", "DOUBLE")
            
            
            with arcpy.da.UpdateCursor(fc, ["line_color", "line_opacity", "line_width_px"]) as cursor:
                for i, row in enumerate(cursor):
                    row[0] = outline_color[i]
                    row[1] = outline_opacity[i]
                    row[2] = outline_width_px[i]
                    cursor.updateRow(row)
            
    
    
    elif symb["shape_type"] in ["Point", "Polygon"]:
    
        # Store fill and outline symbology attributes for polygon/point geometries without separated opacity field
        if colormode in ["CSS RGBA", "8-digit HEX"]:
            arcpy.management.AddField(fc, "fill_color", "TEXT")
            arcpy.management.AddField(fc, "outline_color", "TEXT")
            arcpy.management.AddField(fc, "outline_width_px", "DOUBLE")
            
            with arcpy.da.UpdateCursor(fc, ["fill_color", "outline_color", "outline_width_px"]) as cursor:
                for i, row in enumerate(cursor):
                    row[0] = fill_color[i]
                    row[1] = outline_color[i]
                    row[2] = outline_width_px[i]
                    cursor.updateRow(row)
    
        # Store fill and outline symbology attributes for polygon/point geometries with separated opacity field
        elif colormode == "HEX + Opacity":
            arcpy.management.AddField(fc, "fill_color", "TEXT")
            arcpy.management.AddField(fc, "fill_opacity", "DOUBLE")
            arcpy.management.AddField(fc, "outline_color", "TEXT")
            arcpy.management.AddField(fc, "outline_opacity", "DOUBLE")
            arcpy.management.AddField(fc, "outline_width_px", "DOUBLE")
            
            with arcpy.da.UpdateCursor(fc, ["fill_color", "fill_opacity", "outline_color", "outline_opacity", "outline_width_px"]) as cursor:
                for i, row in enumerate(cursor):
                    row[0] = fill_color[i]
                    row[1] = fill_opacity[i]
                    row[2] = outline_color[i]
                    row[3] = outline_opacity[i]
                    row[4] = outline_width_px[i]
                    cursor.updateRow(row)
    
        
    # Create feature layer for immediate visualization in ArcGIS Pro
    arcpy.env.addOutputsToMap = True
    arcpy.management.MakeFeatureLayer(fc)
    
    # Restore original ArcGIS environment configuration
    arcpy.env.addOutputsToMap = old_add
    arcpy.env.overwriteOutput = old_overwrite


