import colorsys


def arcgis_color_to_rgba(code):
    
    if "RGB" in code:
        # print ("RGB")
        r,g,b,alpha = code["RGB"]
        alpha = round(alpha)             
        return [round(r),round(g),round(b),alpha]
        
    elif "HSV" in code:
        # print("HSV")
        h,s,v, alpha = code["HSV"]
        hsv_list = list(colorsys.hsv_to_rgb(h/360, s/100, v/100)) 
        hsv_list = [round(255 * x) for x in hsv_list]
        return hsv_list + [round(alpha)]

    elif "HSL" in code:        
        # print("HSL")
        h,s,l, alpha = code["HSL"]
        hsl_list = list(colorsys.hls_to_rgb(h/360, l/100, s/100)) #Distinto orden de coeficientes en el estándar web (HLS)
        hsl_list = [round(255 * x) for x in hsl_list]
        return hsl_list + [round(alpha)]

    elif "Gray" in code:
        # print("Gray")
        gray,alpha = code["Gray"]
        alpha = round(alpha)
        return [gray, gray, gray, alpha]

    elif "CMYK" in code:
        # print("CMYK")
        c,m,y,k,alpha = code["CMYK"]
        c /= 100
        m /= 100
        y /= 100
        k /= 100
        
        r = round(255 * (1-c) * (1-k))
        g = round(255 * (1-m) * (1-k))
        b = round(255 * (1-y) * (1-k))
        alpha  = round(alpha)

        return [r,g,b,alpha]
    
    else:
        raise ValueError(f"Unsupported color model:{code}")

def cim_color_to_rgba (obj):

    obj_code = type(obj).__name__
    obj_values = obj.values
    
    color_map = {
        "CIMRGBColor": "RGB",
        "CIMHSVColor": "HSV",
        "CIMHSLColor": "HSL",
        "CIMGrayColor": "Gray",
        "CIMLABColor": "LAB",
        "CIMCMYKColor" : "CMYK"
        
    }
    
    color_dict = { color_map[obj_code] : obj_values}
    
    return arcgis_color_to_rgba(color_dict)

def rgba_to_hex(r, g, b, a=None):
    if a is None:
        return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
    return "#{:02X}{:02X}{:02X}{:02X}".format(int(r), int(g), int(b), int(a))

