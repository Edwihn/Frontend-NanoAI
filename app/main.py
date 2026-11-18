import asyncio
import json
import logging
import os
import sqlite3
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("NanoAI-EdgeBridge")

# URL oficial de la Raspberry Pi en producción
RASPI_BASE_URL = os.getenv("RASPI_BASE_URL", "http://nanoaitemp.local:8000").rstrip("/")
DB_PATH = os.getenv("NANO_AI_DB_PATH", "nvme_data/telemetry.db")
ANOMALY_THRESHOLD_PROD = 0.6653

os.makedirs(os.path.dirname(DB_PATH) or "nvme_data", exist_ok=True)
os.makedirs("static/vendor", exist_ok=True)

db_lock = asyncio.Lock()
connected_clients: List[WebSocket] = []
latest_state: Dict[str, Any] = {}


def fetch_remote_json(path: str, timeout: float = 3.5) -> Optional[Dict[str, Any]]:
    """Obtiene el JSON en tiempo real directamente desde la Raspberry Pi (http://nanoaitemp.local:8000)."""
    url = f"{RASPI_BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def sync_from_raspi_loop():
    """
    Sincroniza continuamente desde http://nanoaitemp.local:8000/api/history
    y retransmite cualquier lectura nueva a los clientes WebSocket locales.
    No inventa ni simula temperaturas falsas.
    """
    global latest_state
    last_timestamp = None
    logger.info("Sincronizando en vivo con Raspberry Pi en %s/api/history ...", RASPI_BASE_URL)
    while True:
        try:
            data = await asyncio.to_thread(fetch_remote_json, "/api/history?limit=60", 3.0)
            if data and isinstance(data, dict):
                remote_latest = data.get("latest_state")
                if remote_latest and isinstance(remote_latest, dict):
                    latest_state = remote_latest
                    ts = remote_latest.get("timestamp")
                    if ts and ts != last_timestamp:
                        last_timestamp = ts
                        await broadcast_payload(remote_latest)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Esperando conexión con %s: %s", RASPI_BASE_URL, exc)

        await asyncio.sleep(1.5)


async def broadcast_payload(payload: Dict[str, Any]):
    """Envía el payload real a todos los clientes WebSocket conectados."""
    disconnected = []
    for ws in list(connected_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        if ws in connected_clients:
            connected_clients.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(sync_from_raspi_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Nano-AI Frontend & Edge Proxy Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/history")
@app.get("/history")
async def get_history(limit: int = Query(default=60, ge=1, le=1000)):
    """
    Obtiene y devuelve los valores reales directamente desde
    http://nanoaitemp.local:8000/api/history.
    """
    global latest_state
    try:
        remote_data = await asyncio.to_thread(fetch_remote_json, f"/api/history?limit={limit}", 4.0)
        if remote_data and isinstance(remote_data, dict):
            if remote_data.get("latest_state"):
                latest_state = remote_data["latest_state"]
            return remote_data
    except Exception as exc:
        logger.warning("No se pudo contactar %s/api/history: %s", RASPI_BASE_URL, exc)

    return {
        "count": 0,
        "latest_state": latest_state,
        "history": [],
        "error": f"No se pudo conectar a {RASPI_BASE_URL}/api/history"
    }


@app.get("/api/metrics")
@app.get("/metrics")
async def get_official_metrics():
    """Obtiene la tabla oficial de métricas desde la Raspberry Pi o desde el respaldo local."""
    try:
        remote_metrics = await asyncio.to_thread(fetch_remote_json, "/api/metrics", 3.0)
        if remote_metrics and isinstance(remote_metrics, dict):
            return remote_metrics
    except Exception:
        pass

    local_metrics_path = "nvme_data/official_evaluation_metrics.json"
    if os.path.exists(local_metrics_path):
        with open(local_metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return JSONResponse(status_code=404, content={"detail": "Official evaluation metrics not found."})


@app.get("/api/state")
@app.get("/health")
@app.get("/api/health")
async def get_system_state():
    """Obtiene el estado real desde http://nanoaitemp.local:8000/api/state o /api/history."""
    global latest_state
    try:
        remote_state = await asyncio.to_thread(fetch_remote_json, "/api/state", 3.0)
        if remote_state and isinstance(remote_state, dict):
            if remote_state.get("latest_state"):
                latest_state = remote_state["latest_state"]
            return remote_state
    except Exception:
        pass

    try:
        remote_hist = await asyncio.to_thread(fetch_remote_json, "/api/history?limit=1", 3.0)
        if remote_hist and isinstance(remote_hist, dict):
            if remote_hist.get("latest_state"):
                latest_state = remote_hist["latest_state"]
            return {
                "status": "ok",
                "simulate_sensor": False,
                "journal_mode": "wal",
                "db_path": "/mnt/nvme/nano_ai/data/telemetry.db",
                "ws_clients": len(connected_clients),
                "latest_state": latest_state,
            }
    except Exception as exc:
        logger.warning("No se pudo obtener estado de %s: %s", RASPI_BASE_URL, exc)

    return {
        "status": "offline",
        "simulate_sensor": False,
        "journal_mode": "wal",
        "db_path": "/mnt/nvme/nano_ai/data/telemetry.db",
        "ws_clients": len(connected_clients),
        "latest_state": latest_state,
    }


class ChatProxyRequest(BaseModel):
    question: str


@app.post("/api/chat")
@app.post("/chat")
async def proxy_chat(body: ChatProxyRequest):
    """
    Reenvía la petición POST /api/chat directamente al motor EdgeChatEngine
    (Guardrail ONNX + SLM Qwen2.5-0.5B GGUF) en http://nanoaitemp.local:8000/api/chat.
    """
    global latest_state
    q = (body.question or "").strip()
    if not q or len(q) > 500:
        return JSONResponse(
            status_code=422,
            content={"detail": "Field 'question' must be between 1 and 500 characters."},
        )

    def _post_chat() -> Dict[str, Any]:
        url = f"{RASPI_BASE_URL}/api/chat"
        payload_bytes = json.dumps({"question": q}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        result = await asyncio.to_thread(_post_chat)
        if isinstance(result, dict) and isinstance(result.get("telemetry_snapshot"), dict):
            latest_state = result["telemetry_snapshot"]
        return result
    except urllib.error.HTTPError as http_err:
        try:
            err_body = json.loads(http_err.read().decode("utf-8"))
        except Exception:
            err_body = {"detail": str(http_err)}
        return JSONResponse(status_code=http_err.code, content=err_body)
    except Exception as exc:
        logger.warning("No se pudo contactar %s/api/chat: %s", RASPI_BASE_URL, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": f"No se pudo conectar con el motor de chat en {RASPI_BASE_URL}/api/chat ({exc})."},
        )


class SimulationRequest(BaseModel):
    mode: str = "ANOMALIA_CALOR"


@app.post("/api/telemetry/simulate")
@app.get("/api/telemetry/simulate")
@app.post("/api/kan20/simulate")
@app.get("/api/kan20/simulate")
async def simulate_telemetry_event(mode: str = Query(default="ANOMALIA_CALOR"), body: Optional[SimulationRequest] = None):
    """Permite probar la reacción visual de la UI ante eventos térmicos bajo demanda."""
    global latest_state
    target_mode = (body.mode if body else mode).upper().strip()
    now_iso = datetime.now().isoformat(timespec="seconds")

    if target_mode in ("DISCONNECTED", "CRC_ERROR", "READ_ERROR", "HARDWARE_FAULT"):
        fault_payload = {
            "timestamp": now_iso,
            "sensor_status": target_mode,
            "current_temp_c": None,
        }
        latest_state = fault_payload
        await broadcast_payload(fault_payload)
        return {"status": "ok", "simulated_mode": target_mode, "payload": fault_payload}

    if target_mode == "ANOMALIA_CALOR":
        payload = {
            "timestamp": now_iso,
            "sensor_status": "OK",
            "current_temp_c": 28.75,
            "thermal_sensation": "Caluroso",
            "forecast_30m_c": 23.94,
            "baseline_30m_c": 28.75,
            "rolling_mae_model": 0.2932,
            "rolling_mae_baseline": 0.7367,
            "autoencoder_mse": 1.6009,
            "anomaly_threshold": ANOMALY_THRESHOLD_PROD,
            "is_anomaly": True,
            "anomaly_type": "ANOMALIA_CALOR",
            "pi_metrics": {
                "inference_time_ms": 0.307,
                "ram_used_mb": 88.4,
            },
        }
    elif target_mode == "ANOMALIA_FRIO":
        payload = {
            "timestamp": now_iso,
            "sensor_status": "OK",
            "current_temp_c": 14.20,
            "thermal_sensation": "Frío",
            "forecast_30m_c": 16.45,
            "baseline_30m_c": 14.20,
            "rolling_mae_model": 0.2932,
            "rolling_mae_baseline": 0.7367,
            "autoencoder_mse": 6.4190,
            "anomaly_threshold": ANOMALY_THRESHOLD_PROD,
            "is_anomaly": True,
            "anomaly_type": "ANOMALIA_FRIO",
            "pi_metrics": {
                "inference_time_ms": 0.307,
                "ram_used_mb": 88.4,
            },
        }
    else:
        # Restaurar leyendo directamente el estado real actual de la Raspberry Pi
        try:
            remote_data = await asyncio.to_thread(fetch_remote_json, "/api/history?limit=1", 3.0)
            if remote_data and remote_data.get("latest_state"):
                latest_state = remote_data["latest_state"]
                await broadcast_payload(latest_state)
                return {"status": "ok", "simulated_mode": "REAL_PI", "payload": latest_state}
        except Exception:
            pass
        return {"status": "ok", "simulated_mode": "NORMAL", "payload": latest_state}

    latest_state = payload
    await broadcast_payload(payload)
    return {"status": "ok", "simulated_mode": target_mode, "payload": payload}


async def _handle_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    if latest_state:
        try:
            await websocket.send_json(latest_state)
        except Exception:
            pass
    try:
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping" and latest_state:
                await websocket.send_json(latest_state)
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.websocket("/ws")
async def websocket_root(websocket: WebSocket):
    await _handle_websocket(websocket)


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await _handle_websocket(websocket)


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await _handle_websocket(websocket)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"system": "Nano-AI Edge Server", "status": "online"})
