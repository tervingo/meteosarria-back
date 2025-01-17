import requests
from xml.etree import ElementTree as ET
import re

def get_meteohub_parameter(parameter_name):
    """
    Fetches data from the Meteohub and extracts the value of a specific
    parameter from the XML response.

    Args:
        parameter_name: The name of the parameter to extract (e.g., "ext_temp",
                         "int_temp", "hum", "wind_dir", "wind_speed", "press",
                         "cur_rain", "total_rain", "rad").

    Returns:
        The value of the specified parameter, or None if the parameter is not
        found or an error occurs.
    """
#    url = "http://192.168.1.115/meteolog.cgi?type=xml&mode=data"
    url = "http://tervingo.hopto.me:81/meteolog.cgi?type=xml&mode=data"

    # Mapping of parameter names to Meteohub sensor IDs and attributes
    parameter_map = {
        "ext_temp": {"id": "TH", "attribute": "temp"},
        "int_temp": {"id": "THB", "attribute": "temp"},
        "hum": {"id": "TH", "attribute": "hum"},
        "wind_dir": {"id": "WIND", "attribute": "dir"},
        "wind_speed": {"id": "WIND", "attribute": "wind"},
        "gust_speed": {"id": "WIND", "attribute": "gust"},
        "press": {"id": "THB", "attribute": "press"},
        "sea_press": {"id": "THB", "attribute": "seapress"},
        "cur_rain": {"id": "RAIN", "attribute": "rate"},
        "total_rain": {"id": "RAIN", "attribute": "total"},
        "rad": {"id": "SOL", "attribute": "rad"},
        "uv": {"id": "UV", "attribute": "index"},
    }

    if parameter_name not in parameter_map:
        print(f"Error: Invalid parameter name '{parameter_name}'")
        return None

    try:
        response = requests.get(url)
        response.raise_for_status()
  
        # Workaround: Add double quotes around attribute values
        xml_string = response.text

        # Corrected regular expression to add quotes around attribute values
        xml_string = re.sub(r'(\w+)=([^\s>]+)', r'\1="\2"', xml_string)

        # Ensure all tags except <logger> are properly closed
        xml_string = re.sub(r'(<(?!logger)\w+[^/>]*)(?<!/)>', r'\1/>', xml_string)

        root = ET.fromstring(xml_string)
        
        sensor_id = parameter_map[parameter_name]["id"]
        attribute_name = parameter_map[parameter_name]["attribute"]

        for element in root:
            if element.tag.upper() == sensor_id:
                if attribute_name in element.attrib:
                    value = element.attrib[attribute_name]
                    # Convert to appropriate data type based on attribute
                    if attribute_name in ("temp", "hum", "wind", "gust", "press", "sea_press", "rate", "total", "rad", "index"):
                        return float(value)
                    else:
                        return value  # Return as string if not a numeric attribute

        return None  # Parameter not found

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Meteohub: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        print(f"Problematic XML:\n{xml_string}")  # Print the XML for debugging
        return None
    except re.error as e:
        print(f"Error in regular expression substitution: {e}")
        print(f"Problematic XML:\n{xml_string}")  # Print the XML for debugging
        return None
