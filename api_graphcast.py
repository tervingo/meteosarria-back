"""
api_graphcast.py

Pipeline: ECMWF Open Data (AIFS GRIB2) → GeoTIFF → rio-tiler → XYZ tiles.

Modelo: aifs-single (ECMWF AI Integrated Forecasting System).
GraphCast fue retirado de ECMWF Open Data; AIFS ofrece la misma funcionalidad.

Sin GEE. Sin GCS. Sin coste externo.

Variables de entorno necesarias: ninguna (pipeline local).

Endpoints:
  POST /api/graphcast/run-pipeline          → lanza pipeline en background
  GET  /api/graphcast/status                → estado + pasos disponibles
  GET  /api/graphcast/tiles/<z>/<x>/<y>     → tesela PNG (rio-tiler)
         ?var=t2m|tp|wind  &step=6..240
"""

import os
import sys
import threading
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request, make_response

# ── Logging a stdout (visible en Render) ────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s [AIFS] %(levelname)s %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

graphcast_bp = Blueprint("graphcast", __name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

GRAPHCAST_DIR = "/tmp/graphcast"
STEPS = list(range(6, 241, 6))   # 6, 12, …, 240 h

# Parámetros a descargar (GRIB2 shortName)
GRIB_PARAMS = ["2t", "tp", "10u", "10v"]

VARIABLES_CONFIG = {
    "t2m": {
        "label": "Temperatura 2m (°C)",
        "vis_min": -10.0,
        "vis_max": 45.0,
        "colormap": "RdBu_r",
    },
    "tp": {
        "label": "Precipitación (mm)",
        "vis_min": 0.0,
        "vis_max": 50.0,
        "colormap": "Blues",
    },
    "wind": {
        "label": "Viento 10m (m/s)",
        "computed": True,
        "vis_min": 0.0,
        "vis_max": 30.0,
        "colormap": "YlOrRd",
    },
}

# ---------------------------------------------------------------------------
# Estado global (protegido por lock)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_status = {
    "state": "idle",
    "message": "",
    "last_run": None,
    "run_date": None,
    "run_time": None,
    "available_steps": {},
}


def _update(**kw):
    with _lock:
        _status.update(kw)
    # Forzar flush para que Render muestre el log inmediatamente
    sys.stdout.flush()


def _get():
    with _lock:
        return dict(_status)


def _log(msg: str):
    """Log + flush inmediato para Render."""
    logger.info(msg)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_latest_run():
    """
    Devuelve (date_str, time_str) del último run AIFS disponible,
    teniendo en cuenta el delay de publicación de ECMWF (~6 h).
    """
    now = datetime.now(timezone.utc)
    if now.hour >= 18:
        return now.strftime("%Y%m%d"), "12"
    elif now.hour >= 6:
        return now.strftime("%Y%m%d"), "00"
    else:
        prev = now - timedelta(days=1)
        return prev.strftime("%Y%m%d"), "12"


def geotiff_path(var: str, step: int) -> str:
    return os.path.join(GRAPHCAST_DIR, f"{var}_step{step:03d}.tif")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _open_grib_var(grib_file: str, short_name: str):
    """
    Abre UNA sola variable del GRIB2 con filter_by_keys.
    Mucho más rápido que cfgrib.open_datasets() porque solo escanea
    los mensajes del parámetro solicitado.
    """
    import xarray as xr
    return xr.open_dataset(
        grib_file,
        engine="cfgrib",
        backend_kwargs={"filter_by_keys": {"shortName": short_name}},
        chunks={},          # lazy loading
    )


def _clip_iberia(da):
    """Recorta a [-9.5, 4.5] lon / [35.5, 44.5] lat, normalizando 0-360 si es necesario."""
    if float(da.longitude.max()) > 180:
        da = da.assign_coords(longitude=((da.longitude + 180) % 360) - 180)
        da = da.sortby("longitude")
    lat0, lat1 = float(da.latitude[0]), float(da.latitude[-1])
    if lat0 > lat1:
        return da.sel(latitude=slice(44.5, 35.5), longitude=slice(-9.5, 4.5))
    return da.sel(latitude=slice(35.5, 44.5), longitude=slice(-9.5, 4.5))


def _to_raster(da, path: str):
    da = da.squeeze(drop=True)
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.set_spatial_dims(x_dim="longitude", y_dim="latitude")
    da.rio.to_raster(path, driver="GTiff", compress="lzw")


def _run_pipeline():
    """Hilo background: GRIB2 → GeoTIFF."""
    import numpy as np
    import xarray as xr
    import rioxarray  # noqa: F401 – activa el accessor .rio

    os.makedirs(GRAPHCAST_DIR, exist_ok=True)

    try:
        run_date, run_time = get_latest_run()

        # ── 1. Descarga GRIB2 ────────────────────────────────────────────
        _update(state="downloading",
                message=f"Descargando AIFS run {run_date} {run_time}z…")
        _log(f"Descargando AIFS {run_date} {run_time}z")

        from ecmwf.opendata import Client

        grib_file = os.path.join(GRAPHCAST_DIR, "latest.grib2")
        Client(source="ecmwf").retrieve(
            model="aifs-single",
            date=run_date,
            time=run_time,
            step=STEPS,
            param=GRIB_PARAMS,
            target=grib_file,
        )
        size_mb = os.path.getsize(grib_file) / 1e6
        _log(f"GRIB2 descargado: {size_mb:.1f} MB")

        # ── 2. GRIB2 → GeoTIFFs recortados a la Península Ibérica ────────
        _update(state="processing",
                message="Procesando variables… (puede tardar varios minutos)")
        _log("Iniciando conversión GRIB2 → GeoTIFF")

        local: dict[str, dict[int, str]] = {
            "t2m": {}, "tp": {}, "u10": {}, "v10": {}}

        # Definición de cada variable: (shortName, clave_local, transformación)
        var_specs = [
            ("2t",  "t2m", lambda x: x - 273.15),   # K → °C
            ("tp",  "tp",  lambda x: x * 1000),       # m → mm
            ("10u", "u10", lambda x: x),
            ("10v", "v10", lambda x: x),
        ]

        for short_name, key, transform in var_specs:
            _update(message=f"Procesando {short_name}…")
            _log(f"  Abriendo {short_name} con filter_by_keys…")
            try:
                ds = _open_grib_var(grib_file, short_name)
            except Exception as e:
                _log(f"  AVISO: no se pudo abrir {short_name}: {e}")
                continue

            # La variable principal del dataset
            data_vars = [v for v in ds.data_vars
                         if v not in ("valid_time", "number")]
            if not data_vars:
                _log(f"  AVISO: dataset de {short_name} vacío")
                continue
            main_var = data_vars[0]
            _log(f"  Variable principal en dataset: {main_var}")

            da = ds[main_var]
            da_ib = _clip_iberia(da)

            if "step" not in da_ib.dims:
                _log(f"  AVISO: {short_name} no tiene dimensión 'step'")
                continue

            n = min(len(STEPS), int(da_ib.step.size))
            _log(f"  Escribiendo {n} GeoTIFFs para {key}…")
            for i in range(n):
                s = STEPS[i]
                try:
                    step_da = transform(da_ib.isel(step=i))
                    path = geotiff_path(key, s)
                    _to_raster(step_da, path)
                    local[key][s] = path
                except Exception as e:
                    _log(f"  Error guardando {key} +{s}h: {e}")

            _log(f"  {key}: {len(local[key])} pasos guardados")
            ds.close()

        # ── Viento: √(u10² + v10²) ────────────────────────────────────────
        _update(message="Calculando velocidad de viento…")
        _log("Calculando velocidad de viento…")
        local["wind"] = {}
        for s in STEPS:
            u_p = local["u10"].get(s)
            v_p = local["v10"].get(s)
            if not (u_p and v_p):
                continue
            try:
                u = xr.open_dataarray(u_p, engine="rasterio")
                v = xr.open_dataarray(v_p, engine="rasterio")
                wind = np.sqrt(u**2 + v**2)
                path = geotiff_path("wind", s)
                wind.rio.write_crs("EPSG:4326")
                wind.rio.to_raster(path, driver="GTiff", compress="lzw")
                local["wind"][s] = path
            except Exception as e:
                _log(f"  Error viento +{s}h: {e}")

        _log(f"  wind: {len(local['wind'])} pasos guardados")

        # ── Resumen ────────────────────────────────────────────────────────
        available_steps = {
            var: sorted(steps.keys())
            for var, steps in local.items()
            if var in VARIABLES_CONFIG and steps
        }
        _log(f"Pipeline completado. Pasos disponibles: "
             f"{ {v: len(s) for v, s in available_steps.items()} }")

        _update(
            state="ready",
            message=f"Pipeline completado. Run: {run_date} {run_time}z",
            last_run=datetime.now(timezone.utc).isoformat(),
            run_date=run_date,
            run_time=f"{run_time}z",
            available_steps=available_steps,
        )

    except Exception as exc:
        _log(f"ERROR en pipeline: {exc}")
        logger.exception("Pipeline AIFS falló")
        _update(state="error", message=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@graphcast_bp.route("/api/graphcast/run-pipeline", methods=["POST"])
def run_pipeline():
    with _lock:
        state = _status["state"]

    if state in ("downloading", "processing"):
        return jsonify({"error": "Pipeline ya en ejecución", "state": state}), 409

    _update(state="downloading", message="Iniciando pipeline…",
            available_steps={}, last_run=None, run_date=None, run_time=None)

    threading.Thread(target=_run_pipeline, daemon=True,
                     name="aifs-pipeline").start()
    return jsonify({"message": "Pipeline iniciado", "state": "downloading"}), 202


@graphcast_bp.route("/api/graphcast/status", methods=["GET"])
def get_status():
    return jsonify(_get())


@graphcast_bp.route("/api/graphcast/tiles/<int:z>/<int:x>/<int:y>")
def serve_tile(z: int, x: int, y: int):
    """Tesela PNG generada on-the-fly con rio-tiler."""
    var  = request.args.get("var", "t2m")
    step = request.args.get("step", 6, type=int)

    tiff = geotiff_path(var, step)
    if not os.path.exists(tiff):
        return _empty_png(), 200

    cfg = VARIABLES_CONFIG.get(var, {})
    vis_min = cfg.get("vis_min", 0.0)
    vis_max = cfg.get("vis_max", 1.0)
    cm_name = cfg.get("colormap", "viridis")

    try:
        from rio_tiler.io import Reader
        from rio_tiler.colormap import cmap

        with Reader(tiff) as src:
            img = src.tile(x, y, z, indexes=1)

        img.rescale(in_range=((vis_min, vis_max),), out_range=(0, 255))
        colormap = cmap.get(cm_name)
        content = img.render(img_format="PNG", colormap=colormap)

        resp = make_response(content, 200)
        resp.headers["Content-Type"] = "image/png"
        resp.headers["Cache-Control"] = "public, max-age=1800"
        return resp

    except Exception as e:
        name = type(e).__name__
        if "OutsideBounds" not in name and "TileOutside" not in name:
            logger.error(f"Tile {z}/{x}/{y} ({var}+{step}h): {e}")
        return _empty_png(), 200


@graphcast_bp.route("/api/graphcast/variables", methods=["GET"])
def get_variables():
    result = {
        var: {"label": cfg["label"],
              "vis_min": cfg["vis_min"],
              "vis_max": cfg["vis_max"]}
        for var, cfg in VARIABLES_CONFIG.items()
    }
    return jsonify({"variables": result, "steps": STEPS})


# ---------------------------------------------------------------------------
# Utilidad
# ---------------------------------------------------------------------------

def _empty_png() -> bytes:
    """PNG transparente 256×256."""
    import struct, zlib

    def chunk(name, data):
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(c[4:]) & 0xFFFFFFFF)

    raw = chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
    row = b"\x00" + b"\x00\x00\x00\x00" * 256
    raw += chunk(b"IDAT", zlib.compress(row * 256))
    raw += chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + raw
