from flask import Flask
from flask_cors import CORS
from flask_caching import Cache
import os


# Import blueprints and database
from api_live import live_bp
from api_meteo_data import meteo_bp
from api_yearly_data import yearly_bp
from api_burgos_weather import burgos_bp
from api_barcelona_rain import barcelona_rain_bp
from api_radar_aemet import radar_bp
from api_historico import historico_bp
from api_burgos_estadisticas import burgos_stats_bp

app = Flask(__name__)

# Configure CORS with specific settings
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure Flask-Caching based on environment
if os.getenv('FLASK_ENV') == 'production' or os.getenv('RENDER') == 'true':
    # Production configuration (Render)
    from production_config import get_production_cache_config
    cache_config = get_production_cache_config()
else:
    # Development configuration
    cache_config = {
        'CACHE_TYPE': 'simple',  # In-memory cache
        'CACHE_DEFAULT_TIMEOUT': 3600,  # 1 hour for development
        'CACHE_KEY_PREFIX': 'meteosarria_dev_'
    }

app.config.from_mapping(cache_config)
cache = Cache(app)


# Register blueprints
app.register_blueprint(live_bp)
app.register_blueprint(meteo_bp)
app.register_blueprint(yearly_bp)
app.register_blueprint(burgos_bp)
app.register_blueprint(barcelona_rain_bp)
app.register_blueprint(radar_bp)
app.register_blueprint(historico_bp)
app.register_blueprint(burgos_stats_bp)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)