from flask import Flask
from flask_cors import CORS


# Import blueprints and database
from api_live import live_bp
from api_meteo_data import meteo_bp
from api_yearly_data import yearly_bp
from api_burgos_weather import burgos_bp
from api_barcelona_rain import barcelona_rain_bp
from api_radar_aemet import radar_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(live_bp)
app.register_blueprint(meteo_bp)
app.register_blueprint(yearly_bp)
app.register_blueprint(burgos_bp)
app.register_blueprint(barcelona_rain_bp)
app.register_blueprint(radar_bp)


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)