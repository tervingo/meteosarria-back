from flask import Flask, jsonify
from livedata import get_meteohub_parameter
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/live')
def live_weather():
    live_data = {
        "external_temperature": get_meteohub_parameter("ext_temp"),
        "internal_temperature": get_meteohub_parameter("int_temp"),
        "humidity": get_meteohub_parameter("hum"),
        "wind_direction": get_meteohub_parameter("wind_dir"),
        "wind_speed": get_meteohub_parameter("wind_speed"),
        "gust_speed": get_meteohub_parameter("gust_speed"),
        "pressure": get_meteohub_parameter("press"),
        "current_rain_rate": get_meteohub_parameter("cur_rain"),
        "total_rain": get_meteohub_parameter("total_rain"),
        "solar_radiation": get_meteohub_parameter("rad"),
        "uv_index": get_meteohub_parameter("uv"),
    }

    if any(value is None for value in live_data.values()):
        return jsonify({"error": "Could not retrieve complete live weather data"}), 500

    return jsonify(live_data)

if __name__ == '__main__':
    app.run(debug=True)