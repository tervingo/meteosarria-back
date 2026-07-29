"""Utilidades compartidas por los distintos endpoints de previsión."""

from datetime import datetime

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def day_and_date(date_str):
    """A partir de una fecha ISO ('YYYY-MM-DD...'), devuelve (día_semana, 'dd/mm')."""
    date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
    return DIAS_SEMANA[date_obj.weekday()], date_obj.strftime('%d/%m')
