"""OpenWeather y TomTom desde servidor, con caché y errores sin secretos.

Documentación: https://docs.openweather.co.uk/current
https://docs.openweather.co.uk/api/air-pollution
https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data
https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-incidents/incident-details
"""
import copy
import json
import math
import os
import ssl
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, HTTPSHandler, build_opener

from flask import current_app

try:
    import truststore
except ImportError:
    truststore = None

AQI = {1: "Bueno", 2: "Aceptable", 3: "Moderado", 4: "Malo", 5: "Muy malo"}
INCIDENT_CATEGORIES = {
    0: "Incidente", 1: "Accidente", 2: "Niebla", 3: "Condición peligrosa",
    4: "Lluvia", 5: "Hielo", 6: "Congestión", 7: "Carril cerrado",
    8: "Vía cerrada", 9: "Obras", 10: "Viento", 11: "Inundación",
    14: "Vehículo averiado",
}
DELAY_MAGNITUDES = {0: "Desconocida", 1: "Menor", 2: "Moderada", 3: "Alta", 4: "Indefinida"}
_state_lock = threading.Lock()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _secure_opener():
    """Usa el almacén de certificados del sistema sin desactivar HTTPS."""
    if truststore is not None:
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    else:
        context = ssl.create_default_context()
    return build_opener(_NoRedirect(), HTTPSHandler(context=context))


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Número inválido")
    return result


def _stamp(value):
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat()


def _weather(data):
    main = data["main"]
    weather = data["weather"][0]
    temperature = _number(main["temp"])
    if temperature is None or not isinstance(weather["description"], str):
        raise ValueError("Clima incompleto")
    return {"status": "ok", "temperatura": temperature,
            "sensacion_termica": _number(main.get("feels_like")),
            "humedad": _number(main.get("humidity")),
            "condicion": weather["description"][:120],
            "codigo_condicion": int(weather["id"]),
            "viento_kmh": (_number(data.get("wind", {}).get("speed")) * 3.6
                           if data.get("wind", {}).get("speed") is not None else None),
            "lluvia_1h": _number(data.get("rain", {}).get("1h")),
            "observado_en": _stamp(data["dt"])}


def _air(data):
    item = data["list"][0]
    value = _number(item["main"]["aqi"])
    if value not in AQI:
        raise ValueError("AQI inválido")
    components = item["components"]
    if not isinstance(components, dict):
        raise ValueError("Contaminantes inválidos")
    result = {"status": "ok", "aqi": int(value), "categoria": AQI[value],
              "escala": "OpenWeather 1–5", "unidad": "µg/m³",
              "observado_en": _stamp(item["dt"])}
    for name in ("co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"):
        result["pm25" if name == "pm2_5" else name] = _number(components.get(name))
    return result


def _state():
    with _state_lock:
        return current_app.extensions.setdefault("geo_v2_external_cache", {
            "lock": threading.Lock(), "entries": OrderedDict(), "inflight": set(), "blocked_until": 0.0})


def _tomtom_state():
    with _state_lock:
        return current_app.extensions.setdefault("geo_v2_tomtom_cache", {
            "lock": threading.Lock(), "entries": OrderedDict(), "inflight": set(), "blocked_until": 0.0})


def _unavailable(kind, message=None):
    return {"status": "unavailable", "message": message or (
        "Datos meteorológicos no disponibles" if kind == "weather" else "Calidad del aire no disponible")}


def _config_number(name, default, lower, upper):
    try:
        n = float(current_app.config.get(name, os.environ.get(name, default)))
        return min(upper, max(lower, n)) if math.isfinite(n) else default
    except (ValueError, TypeError):
        return default


def _safe_error(error):
    """Detalle útil para diagnóstico, eliminando las claves antes de registrarlo."""
    detail = str(error)[:300]
    for name in ("OPENWEATHER_API_KEY", "TOMTOM_API_KEY"):
        secret = current_app.config.get(name) or os.environ.get(name)
        if secret:
            detail = detail.replace(str(secret), "[CLAVE OCULTA]")
    return type(error).__name__, detail or "Sin detalle"


def _get(kind, lat, lng):
    try:
        lat, lng = _number(lat), _number(lng)
        if lat is None or lng is None or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            return _unavailable(kind)
    except (ValueError, TypeError, OverflowError):
        return _unavailable(kind)
    secret = current_app.config.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")
    if not secret:
        return _unavailable(kind)
    # Clave sólo en memoria del servidor; nunca se devuelve ni se registra la URL.
    key = (kind, round(lat, 4), round(lng, 4))
    state, now = _state(), time.monotonic()
    stale = None
    with state["lock"]:
        entry = state["entries"].get(key)
        if entry and entry["until"] > now:
            state["entries"].move_to_end(key)
            return copy.deepcopy(entry["result"])
        if entry and entry.get("good") and now - entry["good_at"] < 3600:
            stale = copy.deepcopy(entry["good"])
            stale.update(desactualizado=True, message="Última consulta disponible; actualización pendiente")
        if key in state["inflight"] or state["blocked_until"] > now:
            return stale or _unavailable(kind, "Consulta temporalmente no disponible; vuelve a intentarlo en un minuto")
        state["inflight"].add(key)
    ttl = _config_number("GEO_V2_EXTERNAL_TTL", 600, 60, 1800)
    timeout = _config_number("GEO_V2_EXTERNAL_TIMEOUT", 3, 1, 5)
    success = False
    try:
        params = {"lat": key[1], "lon": key[2], "appid": secret}
        if kind == "weather":
            params.update(units="metric", lang="es")
        url = "https://api.openweathermap.org/data/2.5/" + kind + "?" + urlencode(params)
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "LH-Score-GeoV2/2.0"})
        with _secure_opener().open(req, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("Respuesta no válida")
            raw = response.read(131073)
            if len(raw) > 131072:
                raise ValueError("Respuesta demasiado grande")
        data = json.loads(raw)
        result = (_weather if kind == "weather" else _air)(data)
        # No transmitir un dato antiguo como actual, aunque el proveedor responda 200.
        observed = datetime.fromisoformat(result["observado_en"]).timestamp()
        result.update(fuente="OpenWeather", consultado_en=datetime.now(timezone.utc).isoformat(),
                      desactualizado=time.time() - observed > 10800)
        success = True
    except HTTPError as error:
        if error.code in (401, 403, 429):
            with state["lock"]:
                state["blocked_until"] = time.monotonic() + (300 if error.code == 429 else 60)
        current_app.logger.warning("Geo V2: %s HTTP %s", kind, error.code)
        result = stale or _unavailable(kind)
    except Exception:
        current_app.logger.warning("Geo V2: %s temporalmente no disponible", kind)
        result = stale or _unavailable(kind)
    with state["lock"]:
        state["inflight"].discard(key)
        state["entries"][key] = {"result": copy.deepcopy(result),
            "until": time.monotonic() + (ttl if success else 60),
            "good": copy.deepcopy(result) if success else (entry.get("good") if entry else None),
            "good_at": time.monotonic() if success else (entry.get("good_at", 0) if entry else 0)}
        state["entries"].move_to_end(key)
        while len(state["entries"]) > 256:
            state["entries"].popitem(last=False)
    return result


def obtener_clima(lat, lng):
    return _get("weather", lat, lng)


def obtener_calidad_aire(lat, lng):
    return _get("air_pollution", lat, lng)


def _tomtom_unavailable(message=None):
    return {"status": "unavailable", "message": message or "Movilidad no disponible"}


def _tomtom_json(path, params, timeout):
    secret = current_app.config.get("TOMTOM_API_KEY") or os.environ.get("TOMTOM_API_KEY")
    if not secret:
        raise LookupError("TomTom no configurado")
    query = dict(params)
    query["key"] = secret
    url = "https://api.tomtom.com" + path + "?" + urlencode(query)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "LH-Score-GeoV2/2.0"})
    with _secure_opener().open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Respuesta no válida")
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Respuesta demasiado grande")
    return json.loads(raw)


def _normalize_flow(data):
    flow = data["flowSegmentData"]
    current_speed = _number(flow["currentSpeed"])
    free_speed = _number(flow["freeFlowSpeed"])
    current_time = _number(flow.get("currentTravelTime"))
    free_time = _number(flow.get("freeFlowTravelTime"))
    if current_speed is None or free_speed is None or free_speed <= 0:
        raise ValueError("Flujo incompleto")
    congestion = round(min(100.0, max(0.0, (1.0 - current_speed / free_speed) * 100.0)), 1)
    closed = bool(flow.get("roadClosure"))
    if closed:
        level = "Vía cerrada"
    elif congestion >= 50:
        level = "Alta"
    elif congestion >= 25:
        level = "Media"
    elif congestion >= 10:
        level = "Leve"
    else:
        level = "Fluido"
    delay = max(0.0, (current_time or 0.0) - (free_time or 0.0))
    confidence = _number(flow.get("confidence"))
    return {
        "nivel": level,
        "velocidad_actual_kmh": round(current_speed, 1),
        "velocidad_libre_kmh": round(free_speed, 1),
        "congestion_pct": congestion,
        "tiempo_actual_min": round(current_time / 60.0, 1) if current_time is not None else None,
        "tiempo_libre_min": round(free_time / 60.0, 1) if free_time is not None else None,
        "demora_min": round(delay / 60.0, 1),
        "confianza_pct": round(confidence * 100.0, 1) if confidence is not None else None,
        "cierre_vial": closed,
    }


def _normalize_incidents(data):
    incidents = data.get("incidents", [])
    if not isinstance(incidents, list):
        raise ValueError("Incidentes inválidos")
    result = []
    for item in incidents[:20]:
        properties = item.get("properties", {}) if isinstance(item, dict) else {}
        events = properties.get("events") or []
        event = events[0] if isinstance(events, list) and events and isinstance(events[0], dict) else {}
        category_id = event.get("iconCategory", properties.get("iconCategory", 0))
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            category_id = 0
        description = event.get("description")
        if not isinstance(description, str) or not description.strip():
            description = INCIDENT_CATEGORIES.get(category_id, "Incidente vial")
        magnitude = properties.get("magnitudeOfDelay", 0)
        try:
            magnitude = int(magnitude)
        except (ValueError, TypeError):
            magnitude = 0
        delay = _number(properties.get("delay"))
        length = _number(properties.get("length"))
        result.append({
            "id": str(properties.get("id", ""))[:120],
            "nombre": description.strip()[:200],
            "categoria": INCIDENT_CATEGORIES.get(category_id, "Incidente"),
            "severidad": DELAY_MAGNITUDES.get(magnitude, "Desconocida"),
            "desde": str(properties.get("from", ""))[:160] or None,
            "hasta": str(properties.get("to", ""))[:160] or None,
            "demora_min": round(max(0.0, delay) / 60.0, 1) if delay is not None else None,
            "longitud_km": round(max(0.0, length) / 1000.0, 2) if length is not None else None,
            "inicio": properties.get("startTime"),
            "fin": properties.get("endTime"),
        })
    return result


def obtener_movilidad(lat, lng):
    """Devuelve flujo del segmento cercano e incidentes actuales de TomTom."""
    try:
        lat, lng = _number(lat), _number(lng)
        if lat is None or lng is None or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            return _tomtom_unavailable("Ubicación no disponible")
    except (ValueError, TypeError, OverflowError):
        return _tomtom_unavailable("Ubicación no disponible")
    secret = current_app.config.get("TOMTOM_API_KEY") or os.environ.get("TOMTOM_API_KEY")
    if not secret:
        return _tomtom_unavailable("TomTom no está configurado en el servidor")

    key = (round(lat, 4), round(lng, 4))
    state, now = _tomtom_state(), time.monotonic()
    stale = None
    with state["lock"]:
        entry = state["entries"].get(key)
        if entry and entry["until"] > now:
            state["entries"].move_to_end(key)
            return copy.deepcopy(entry["result"])
        if entry and entry.get("good") and now - entry["good_at"] < 1800:
            stale = copy.deepcopy(entry["good"])
            stale.update(desactualizado=True, message="Última consulta de tráfico disponible")
        if key in state["inflight"] or state["blocked_until"] > now:
            return stale or _tomtom_unavailable("Consulta temporalmente no disponible; vuelve a intentarlo")
        state["inflight"].add(key)

    ttl = _config_number("GEO_V2_TRAFFIC_TTL", 300, 60, 900)
    timeout = _config_number("GEO_V2_EXTERNAL_TIMEOUT", 3, 1, 5)
    radius_km = _config_number("GEO_V2_INCIDENT_RADIUS_KM", 3, 1, 10)
    flow_result, incidents, failures = None, [], []
    auth_or_limit = None
    try:
        flow_data = _tomtom_json(
            "/traffic/services/4/flowSegmentData/absolute/10/json",
            {"point": f"{key[0]},{key[1]}", "unit": "kmph"}, timeout)
        flow_result = _normalize_flow(flow_data)
    except HTTPError as error:
        auth_or_limit = error.code if error.code in (401, 403, 429) else None
        failures.append("flujo")
        current_app.logger.warning("Geo V2: TomTom flujo HTTP %s", error.code)
    except Exception as error:
        failures.append("flujo")
        error_type, error_detail = _safe_error(error)
        current_app.logger.warning(
            "Geo V2: TomTom flujo error %s: %s",
            error_type,
            error_detail,
        )

    if auth_or_limit is None:
        try:
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / max(20.0, 111.0 * abs(math.cos(math.radians(lat))))
            bbox = f"{lng-lon_delta:.6f},{lat-lat_delta:.6f},{lng+lon_delta:.6f},{lat+lat_delta:.6f}"
            fields = "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,from,to,length,delay}}}"
            incident_data = _tomtom_json(
                "/traffic/services/5/incidentDetails",
                {"bbox": bbox, "fields": fields, "language": "es-ES", "timeValidityFilter": "present"},
                timeout)
            incidents = _normalize_incidents(incident_data)
        except HTTPError as error:
            auth_or_limit = error.code if error.code in (401, 403, 429) else None
            failures.append("incidentes")
            current_app.logger.warning("Geo V2: TomTom incidentes HTTP %s", error.code)
        except Exception as error:
            failures.append("incidentes")
            error_type, error_detail = _safe_error(error)
            current_app.logger.warning(
                "Geo V2: TomTom incidentes error %s: %s",
                error_type,
                error_detail,
            )

    if auth_or_limit:
        with state["lock"]:
            state["blocked_until"] = time.monotonic() + (300 if auth_or_limit == 429 else 60)

    success = flow_result is not None or "incidentes" not in failures
    if success:
        result = {"status": "ok", **(flow_result or {}), "incidentes": incidents,
                  "incidentes_total": len(incidents), "fuente": "TomTom",
                  "consultado_en": datetime.now(timezone.utc).isoformat(),
                  "desactualizado": False, "parcial": bool(failures)}
        if failures:
            result["message"] = "Información parcial: " + ", ".join(failures) + " no disponibles"
    else:
        result = stale or _tomtom_unavailable()

    with state["lock"]:
        state["inflight"].discard(key)
        state["entries"][key] = {
            "result": copy.deepcopy(result), "until": time.monotonic() + (ttl if success else 60),
            "good": copy.deepcopy(result) if success else (entry.get("good") if entry else None),
            "good_at": time.monotonic() if success else (entry.get("good_at", 0) if entry else 0),
        }
        state["entries"].move_to_end(key)
        while len(state["entries"]) > 256:
            state["entries"].popitem(last=False)
    return result


def obtener_contexto_externo(lat, lng, es_virtual=False):
    if es_virtual or lat is None or lng is None:
        reason = "No aplica a la tienda virtual" if es_virtual else "Ubicación no disponible"
        return {"clima": _unavailable("weather", reason),
                "calidad_aire": _unavailable("air_pollution", reason),
                "movilidad": {"status": "unavailable", "message": reason}, "eventos": []}
    movilidad = obtener_movilidad(lat, lng)
    return {"clima": obtener_clima(lat, lng), "calidad_aire": obtener_calidad_aire(lat, lng),
            "movilidad": movilidad, "eventos": movilidad.get("incidentes", [])}
