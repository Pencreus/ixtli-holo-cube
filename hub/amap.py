"""Amap-compatible weather replies built from Home Assistant (OpenWeatherMap, US units).

The Huanjing Pro's weather clock is hard-wired to China's Amap API. The patched app
(patch_en.py) calls this hub instead and still expects Amap's JSON shape. It strcmp()s the
'weather' text against its own icon table, so the words below MUST match that table.
"""
import datetime as dt

import ha

# Home Assistant condition -> exact word from the patched icon table
COND = {
    "sunny": "Sun", "clear-night": "Sun", "partlycloudy": "Part Cloudy", "cloudy": "Cloudy",
    "rainy": "Rain", "pouring": "Rain", "lightning-rainy": "T-Storm", "lightning": "T-Storm",
    "hail": "T-Storm w/ hail", "snowy": "Snow", "snowy-rainy": "Sleet", "fog": "Fog",
    "windy": "Windy", "windy-variant": "Windy", "exceptional": "Sun",
}
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
ENTITY = "weather.openweathermap"


def _w(cond):
    return COND.get((cond or "").lower(), "Cloudy")


def _s(v, default="0"):
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return default


def ip_reply():
    return {"status": "1", "info": "OK", "infocode": "10000", "province": "California", "city": "Home",
            "adcode": "999999", "rectangle": "0,0;0,0"}


def live_reply():
    cond = ha.value(ENTITY) or "cloudy"
    wdir = ha.number("sensor.openweathermap_wind_direction")
    return {"status": "1", "count": "1", "info": "OK", "infocode": "10000",
            "lives": [{"province": "California", "city": "Home", "adcode": "999999", "weather": _w(cond),
                       "temperature": _s(ha.number("sensor.openweathermap_temperature")),
                       "winddirection": DIRS[int(((wdir or 0) + 22.5) % 360 // 45)],
                       "windpower": _s(ha.number("sensor.openweathermap_wind_speed")),
                       "humidity": _s(ha.number("sensor.openweathermap_humidity")),
                       "reporttime": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]}


def forecast_reply():
    fc = ha.forecast(ENTITY) or []
    casts = []
    for i, day in enumerate(fc[:4]):
        d = dt.datetime.fromisoformat(day["datetime"].replace("Z", "+00:00")).astimezone()
        w = _w(day.get("condition"))
        casts.append({"date": d.strftime("%Y-%m-%d"), "dayweather": w,
                      "daytemp": _s(day.get("temperature")), "nighttemp": _s(day.get("templow", day.get("temperature")))})
    return {"status": "1", "count": "1", "info": "OK", "infocode": "10000",
            "forecasts": [{"adcode": "999999", "casts": casts}]}
