# -*- coding: utf-8 -*-
import sys
import os
import importlib

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import feature_layer_to_leaflet_core.symb_to_attr as script1
import feature_layer_to_leaflet_core.attr_to_leaflet as script2
importlib.reload(script1)
importlib.reload(script2)

run_tool_1 = script1.run_tool
run_tool_2 = script2.run_tool


class Toolbox:
    def __init__(self):
        self.label = "Feature Layer to Leaflet"
        self.alias = "Feature Layer to Leaflet"
        self.tools = [attr_to_leaflet_tool, symb_to_attr_tool]


class symb_to_attr_tool:

    def __init__(self):
        self.label = "1. Symbology to Attributes"
        self.description = "Transfers basic symbology to attribute description" 

    
    def getParameterInfo(self):
    
        # Input feature layer (source dataset for symbology extraction)
        p0 = arcpy.Parameter(
            displayName="Input Feature Layer",
            name="in_layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        # Output feature class (enriched dataset with symbology attributes)
        p1 = arcpy.Parameter(
            displayName="Output Feature Class",
            name="out_fc",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
    
        # Symbology color encoding selection
        p2 = arcpy.Parameter(
            displayName="Color Encoding",
            name="color_encoding",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p2.filter.type = "ValueList"
        p2.filter.list = ["Leaflet Format", "Custom Format"]
        p2.value = "Leaflet Format"

        # Custom color encoding selection (used only if Custom Format is enabled)
        p3 = arcpy.Parameter(
            displayName="Custom Color Encoding",
            name="custom_color_encoding",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
    
        p3.filter.type = "ValueList"
        p3.filter.list = ["CSS RGBA", "8-digit HEX", "HEX + Opacity"]
        p3.value = "HEX + Opacity"
    
        return [p0, p1, p2, p3]
    
    def updateParameters(self, parameters):
        
        # Enable/disable advanced color encoding options based on schema selection
        if parameters[2].value == "Custom Format":
            parameters[3].enabled = True
        else:
            parameters[3].enabled = False
        return
        

    def updateMessages(self, parameters):
         
        # Validate input layer symbology compatibility before execution
        if parameters[0].value:

            try:
                # Resolve layer object from current ArcGIS Pro session
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                lyrs = [lyr for m in aprx.listMaps() for lyr in m.listLayers()]
                lyr_obj = next(l for l in lyrs if l.name == parameters[0].value.name) #aquí puedo poner None

                # Supported renderer types for symbology encoding
                supported_renderers = {"UniqueValueRenderer", "SimpleRenderer", "GraduatedColorsRenderer"}
                
                # Validate renderer availability
                sym = getattr(lyr_obj, "symbology", None)
                if not sym:
                    parameters[0].setErrorMessage("Symbol-based Symbology not supported")
                    return
                
                renderer = getattr(sym, "renderer", None)
                if not renderer:
                    parameters[0].setErrorMessage("Symbol-based Symbology not supported")
                    return
                
                renderer_type = renderer.type
                
                # Reject unsupported renderer types
                if renderer_type not in supported_renderers:
                    parameters[0].setErrorMessage(f"{renderer_type} not supported")
                    return
                                    
                
                
                # Detect advanced CIM-based symbology constraints
                cim = lyr_obj.getDefinition("V3")
                cim_value_expression = getattr(cim.renderer, "valueExpressionInfo", None)
                expression_info = getattr(cim_value_expression, "title", None)

                # Bivariate symbology not supported
                if renderer_type =="UniqueValueRenderer" and expression_info == "Relationship":
                    parameters[0].setErrorMessage("Bivariate Colors symbology not supported")
                    return
                
                # Value-based expressions are not supported
                if expression_info:
                    parameters[0].setErrorMessage("Value Expressions not supported")
                    return
            
            except Exception as ex:
                # Non-fatal validation error (UI-level warning)
                parameters[0].setWarningMessage(str(ex))

        # Validate color encoding compatibility with Leaflet renderer
        if parameters[3].value:
                
            if parameters[3].valueAsText in ['CSS RGBA', '8-digit HEX']:
                parameters[3].setWarningMessage("Selected encoding is not supported by the web map generation tool (Tool 2)")
                                        
  
    def isLicensed(self):
        return True
       
    def execute(self, parameters, messages):
        # Input layer
        lyr = parameters[0].value

        # Output feature class path
        out = parameters[1].valueAsText

        # Resolve color encoding mode based on UI schema selection
        if parameters[2].valueAsText == "Leaflet Format":
            mode ="HEX + Opacity"
        else:
            # Custom Format encoding option
            mode = parameters[3].valueAsText

        # Symbology processing and export
        run_tool_1(lyr, out, mode, messages) 

    def postExecute(self, parameters):
        return
    

class attr_to_leaflet_tool:
    """
    Creates an interactive Leaflet web map from a processed feature layer, with custom tooltips and configurable basemap/background.
    """

    def __init__(self):
        self.label = "2. Attributes to Leaflet"
        self.description = "Creates a Leaflet web map from a processed feature layer."

    def getParameterInfo(self):

        # Input feature layer
        p0 = arcpy.Parameter(name="input",
                             displayName="Input Feature Class",
                             direction="Input",
                             datatype="DEFeatureClass", 
                             parameterType="Required")

        # Fields used to to build tooltip
        p1 = arcpy.Parameter(name="fields_names",
                             displayName="Tooltip Fields",
                             direction = "Input",
                             datatype="Field",
                             parameterType="Required",
                             multiValue=True) 
        
        # Link field selector to input layer schema
        p1.parameterDependencies = [p0.name] 

        # Background mode selection (color vs basemap)
        p2 = arcpy.Parameter(name="background_option",
                           displayName="Background",
                           direction="Input",
                           datatype="GPString",
                           parameterType="Required")
               
        p2.filter.type = "ValueList"
        p2.filter.list = ["Active Map Background Color", "Custom Basemap"]
        p2.value = "Custom Basemap" # Sets default Value

        # Basemap selection (used when custom background is not applied)
        p3 = arcpy.Parameter(name="basemap",
                             displayName="Basemap",
                             direction="Input",
                             datatype="GPString",
                             parameterType="Required")

        p3.filter.type = "ValueList"
        p3.filter.list = ["ESRI streets", "ESRI satellite", "CARTO dark", "CARTO positron", "CARTO voyager"] #Luego modifico esto para dejarlo "bonito"
        p3.value = "ESRI streets"

        p4 = arcpy.Parameter(name="standalone_html",
                             displayName="Standalone HTML",
                             direction="Input",
                             datatype="GPBoolean",
                             parameterType="Required")
        p4.value=True
        p4.description = (
        "If checked, GeoJSON data will be embedded directly into the HTML file "
        "(no external file required). If unchecked, the tool will generate an "
        "external GeoJSON file and load it via fetch()."
        )



        # Output folder for generated Leaflet web map
        p5 = arcpy.Parameter(name="output_folder",
                             displayName="Output Folder",
                             direction="Input",
                             datatype="DEFolder",
                             parameterType="Required")
     
                             
                            
        return [p0, p1, p2, p3, p4, p5]
 
    def isLicensed(self):
        return True

    def updateParameters(self, parameters):

        # Enable/disable basemap selection depending on background mode (UI parameter control)
        background_option = parameters[2]
        basemap_param = parameters[3]

        if background_option.value == "Custom Basemap":
            basemap_param.enabled = True
            
        else:
            basemap_param.enabled = False

        return


    def updateMessages(self, parameters):

        # Validate input feature layer and required symbology schema

        if parameters[0].value:            
            
            lyr_obj = parameters[0].value
            desc = arcpy.Describe(lyr_obj)
            shapetype = desc.shapetype
            
            # Define required symbology fields depending on geometry type
            if shapetype in ["Polygon","Point"]:
                sym_fields = {'fill_color', 'fill_opacity', 'outline_color', 'outline_opacity', 'outline_width_px'}
            elif shapetype == "Polyline":
                sym_fields = {"line_color", "line_opacity", "line_width_px"}
            else:
                parameters[0].setErrorMessage("Unsupported geometry type")
                        
            try:
                # Check if required symbology fields exist in the input layer schema               
                lyr_obj_fields = set(f.name for f in arcpy.ListFields(lyr_obj))

                if not sym_fields.issubset(lyr_obj_fields):
                    parameters[0].setErrorMessage("Required symbology attributes not found in input layer")

            except Exception as ex:
                parameters[0].setErrorMessage(str(ex))
              
        return

    def execute(self, parameters, messages):

        try:
            # Extract and normalize tool inputs from ArcGIS Pro UI
            input_fc = parameters[0].value
            selected_fields = parameters[1].valueAsText.split(";")
            background_option = parameters[2].valueAsText
            basemap = parameters[3].valueAsText
            html_option = parameters[4].value        
            output_folder = parameters[5].valueAsText
            
            # Execute core processing logic
            run_tool_2(input_fc, selected_fields, background_option, basemap, html_option, output_folder, messages)

            

        except Exception as e: 
            # Catch and report runtime errors to ArcGIS Pro geoprocessing UI
            
            messages.addErrorMessage(str(e)) # Short error message
            messages.addErrorMessage(traceback.format_exc()) # Full stack trace for debugging
            raise #Detiene la ejecución
    

    def postExecute(self, parameters):
        return