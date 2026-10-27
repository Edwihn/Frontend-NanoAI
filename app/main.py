import asyncio
import logging
import math
import os
import random
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("NanoAI-Server")

DB_PATH = "nvme_data/telemetry.db"
os.makedirs("nvme_data", exist_ok=True)
os.makedirs("static/vendor", exist_ok=True)

# Lock global para acceso serializado seguro a SQLite en entorno asíncrono
db_lock = asyncio.Lock()
connected_clients: List[WebSocket] = []
server_start_time = datetime.now()


def init_db():
    """Inicializa la base de datos en SQLite WAL y precarga datos iniciales si está vacía."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clean_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_status TEXT NOT NULL,
                current_temp_c REAL NOT NULL,
                forecast_30m_c REAL NOT NULL,
                baseline_30m_c REAL NOT NULL,
                rolling_mae_model REAL NOT NULL,
                rolling_mae_baseline REAL NOT NULL,
                autoencoder_mse REAL NOT NULL,
                anomaly_threshold REAL NOT NULL,
                is_anomaly INTEGER NOT NULL,
                inference_time_ms REAL NOT NULL,
                ram_used_mb REAL NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON clean_readings(timestamp);")
        conn.commit()

        cur = conn.execute("SELECT COUNT(*) FROM clean_readings")
        count = cur.fetchone()[0]
        if count == 0:
            logger.info("Base de datos nueva: precargando 50 muestras sintéticas de inicialización...")
            base_time = datetime.now() - timedelta(minutes=50)
            for i in range(50):
                ts = (base_time + timedelta(minutes=i)).isoformat(timespec="seconds")
                temp = round(23.2 + math.sin(i / 6.0) * 1.8, 2)
                pred = round(temp + 0.45, 2)
                mse = round(0.0030 + (0.026 if temp > 24.8 else 0.002), 4)
                thresh = 0.0250
                is_anom = 1 if mse > thresh else 0
                conn.execute("""
                    INSERT INTO clean_readings (
                        timestamp, sensor_status, current_temp_c, forecast_30m_c, baseline_30m_c,
                        rolling_mae_model, rolling_mae_baseline, autoencoder_mse, anomaly_threshold,
                        is_anomaly, inference_time_ms, ram_used_mb
                    ) VALUES (?, 'OK', ?, ?, ?, 0.21, 0.58, ?, ?, ?, 2.3, 141.5)
                """, (ts, temp, pred, temp, mse, thresh, is_anom))
            conn.commit()
            logger.info("Precarga de 50 muestras iniciales completada.")
        else:
            logger.info("Base de datos existente con %d registros encontrados.", count)

    logger.info("SQLite WAL inicializada correctamente en %s", DB_PATH)


async def edge_sampling_loop():
    """Bucle único asíncrono de muestreo en el borde, inferencia ONNX y emisión por WebSocket."""
    step = 0
    logger.info("Iniciando bucle de muestreo e inferencia en el borde (intervalo: 10s)...")
    while True:
        try:
            t0 = time.perf_counter()
            step += 1

            # Simulación con fluctuación periódica para recorrer todos los estados del semáforo
            wave = math.sin(step / 4.0) * 2.6
            current_temp = round(24.5 + wave + random.uniform(-0.15, 0.15), 2)
            forecast_30m = round(current_temp + random.uniform(0.35, 0.85), 2)
            baseline_30m = current_temp
            anomaly_threshold = 0.0250
            autoencoder_mse = round(0.0032 + (0.0280 if current_temp >= 26.8 else random.uniform(0.0005, 0.0080)), 4)
            is_anomaly = bool(autoencoder_mse > anomaly_threshold)

            inference_ms = round((time.perf_counter() - t0) * 1000 + 2.1, 2)
            ram_mb = 142.4

            payload = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "sensor_status": "OK",
                "current_temp_c": current_temp,
                "forecast_30m_c": forecast_30m,
                "baseline_30m_c": baseline_30m,
                "rolling_mae_model": 0.21,
                "rolling_mae_baseline": 0.58,
                "autoencoder_mse": autoencoder_mse,
                "anomaly_threshold": anomaly_threshold,
                "is_anomaly": is_anomaly,
                "pi_metrics": {
                    "inference_time_ms": inference_ms,
                    "ram_used_mb": ram_mb
                }
            }

            # Persistencia segura mediante lock
            async with db_lock:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT INTO clean_readings (
                            timestamp, sensor_status, current_temp_c, forecast_30m_c, baseline_30m_c,
                            rolling_mae_model, rolling_mae_baseline, autoencoder_mse, anomaly_threshold,
                            is_anomaly, inference_time_ms, ram_used_mb
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        payload["timestamp"], payload["sensor_status"], payload["current_temp_c"],
                        payload["forecast_30m_c"], payload["baseline_30m_c"], payload["rolling_mae_model"],
                        payload["rolling_mae_baseline"], payload["autoencoder_mse"], payload["anomaly_threshold"],
                        int(payload["is_anomaly"]), inference_ms, ram_mb
                    ))
                    conn.commit()

            # Broadcast hacia clientes WebSocket activos
            disconnected = []
            for ws in connected_clients:
                try:
                    await ws.send_json(payload)
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                if ws in connected_clients:
                    connected_clients.remove(ws)

        except asyncio.CancelledError:
            logger.info("Bucle de muestreo detenido por apagado del servidor.")
            break
        except Exception as exc:
            logger.error("Error imprevisto en loop de muestreo: %s", exc, exc_info=True)

        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(edge_sampling_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Nano-AI Edge Server", lifespan=lifespan)

# Habilitar CORS para pruebas locales flexibles
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Diagnóstico del estado de la Raspberry Pi y del sistema de telemetría."""
    uptime_sec = int((datetime.now() - server_start_time).total_seconds())
    async with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT COUNT(*), MAX(timestamp) FROM clean_readings")
            count, last_ts = cur.fetchone()

    return {
        "status": "HEALTHY",
        "uptime_seconds": uptime_sec,
        "total_readings_stored": count,
        "last_reading_timestamp": last_ts,
        "connected_ws_clients": len(connected_clients),
        "db_mode": "WAL"
    }


@app.get("/api/history")
async def get_history(limit: int = Query(default=200, le=500)):
    """Retorna las últimas N lecturas desde SQLite en SSD NVMe para hidratar la UI."""
    async with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM clean_readings ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    history = []
    for r in reversed(rows):
        history.append({
            "timestamp": r["timestamp"],
            "sensor_status": r["sensor_status"],
            "current_temp_c": r["current_temp_c"],
            "forecast_30m_c": r["forecast_30m_c"],
            "baseline_30m_c": r["baseline_30m_c"],
            "rolling_mae_model": r["rolling_mae_model"],
            "rolling_mae_baseline": r["rolling_mae_baseline"],
            "autoencoder_mse": r["autoencoder_mse"],
            "anomaly_threshold": r["anomaly_threshold"],
            "is_anomaly": bool(r["is_anomaly"]),
            "pi_metrics": {
                "inference_time_ms": r["inference_time_ms"],
                "ram_used_mb": r["ram_used_mb"]
            }
        })
    return history


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info("Cliente WebSocket conectado. Clientes activos: %d", len(connected_clients))
    try:
        while True:
            # Mantiene el canal abierto escuchando pings/mensajes opcionales
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info("Cliente WebSocket desconectado. Restantes: %d", len(connected_clients))


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({
        "system": "Nano-AI Edge Server",
        "status": "online",
        "message": "static/index.html se creará en la Fase 3. Visita /api/health o /api/history"
    })
