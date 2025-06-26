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
    url = "http://tervingo.com/meteo/data_now.xml"

    # Mapping of parameter names to XML tags
    parameter_map = {
        "ext_temp": "temp_ext",
        "int_temp": "temp_int",
        "hum": "hum",
        "wind_dir": "wind_dir",
        "wind_speed": "wind_speed",
        "gust_speed": "wind_gust",
        "press": "pres",
        "sea_press": "pres",  # Using pres as sea_press
        "cur_rain": "rain_rate",
        "total_rain": "daily_rain",
        "rad": "solar_rad",
        "uv": "uv_index",
    }

    if parameter_name not in parameter_map:
        print(f"Error: Invalid parameter name '{parameter_name}'")
        return None

    try:
        # Add timeouts to prevent hanging requests
        response = requests.get(url, timeout=(5, 15))  # (connect_timeout, read_timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        
        tag_name = parameter_map[parameter_name]
        element = root.find(tag_name)
        
        if element is not None and element.text:
            value = element.text.strip()
            # Convert to appropriate data type based on parameter
            if parameter_name in ("ext_temp", "int_temp", "hum", "wind_speed", 
                                "gust_speed", "press", "sea_press", "cur_rain", 
                                "total_rain", "rad", "uv") and value != "--":
                return float(value)
            else:
                return value  # Return as string if not a numeric parameter

        return None  # Parameter not found

    except requests.exceptions.Timeout as e:
        print(f"Timeout error fetching data from Meteohub: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error fetching data from Meteohub: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Meteohub: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_meteohub_parameter: {e}")
        return None
