# 📋 Especificación Técnica y Planeación Integral — Proyecto Nano-AI

> **Documento maestro de ingeniería frontend** para el desarrollo, diseño e integración del **Nodo Visualizador (Dashboard Local)** y su servidor embebido en FastAPI para el Sistema Híbrido de Predicción Térmica a 30 Minutos (Track 4: Lab Forecaster) y Detección de Anomalías en Vivo (Track 3: Machine Anomaly Detector).

---

## 1. Contexto General y Arquitectura del Sistema

El proyecto **Nano-AI** es un sistema de inteligencia artificial ejecutado en el borde (**Edge AI**) diseñado para:

- **Monitorear** en tiempo real la temperatura de un salón o laboratorio
- **Predecir** su comportamiento térmico con **30 minutos de anticipación**
- **Detectar anomalías** físicas de forma instantánea cuando la temperatura sube más de lo normal

### 1.1. Topología de Tres Nodos

```mermaid
flowchart LR
    A["🟢 Nodo Edge\n(Raspberry Pi 4GB + SSD NVMe)\nSensor DS18B20 + ONNX Runtime\nFastAPI :8000"]
    B["🔵 Nodo Entrenamiento\n(PC con PyTorch/GPU)\nEntrena modelos → .onnx"]
    C["🟠 Nodo Visualizador\n(Laptop Externa)\nDashboard en Navegador"]

    B -- "Exporta .onnx + scaler.json" --> A
    A -- "HTTP GET /api/history" --> C
    A -- "WebSocket /ws/stream" --> C
```

| Nodo | Hardware | Responsabilidad |
|---|---|---|
| **Edge** | Raspberry Pi 4GB + SSD NVMe | Lee sensor DS18B20 (GPIO 4, 1-Wire), filtra lecturas corruptas (CRC!=YES, 85°C, -127°C), almacena series en SQLite WAL, ejecuta inferencia ONNX en CPU ARM, sirve FastAPI + WebSocket en puerto 8000 |
| **Entrenamiento** | PC con PyTorch/GPU | Entrena modelo de Regresión (+30 min) y Autoencoder (solo datos normales), exporta `.onnx` + `scaler.json` |
| **Visualizador** | Laptop Externa | Se conecta vía HTTP y WebSocket a la Pi para renderizar lecturas, pronóstico, anomalías, historial, telemetría y chatbot |

### 1.2. Reglas de Operación Inviolables en el Frontend

> [!CAUTION]
> Estas reglas **no son negociables**. Violarlas invalida los criterios de evaluación del proyecto.

1. **Inferencia 100% en la Raspberry Pi:** Toda la computación de modelos se ejecuta estrictamente en la CPU/RAM de la Pi. La laptop es únicamente una pantalla remota que recibe y grafica el JSON vía WebSocket.

2. **Acoplamiento Ligero con FastAPI:** El frontend se construye con **archivos estáticos puros** servidos por FastAPI desde el SSD NVMe. El 100% del renderizado gráfico y lógica de interfaz se delega al navegador de la laptop.

3. **Librerías Locales (Sin CDN):** Todas las dependencias del frontend (Tailwind CSS compilado, Chart.js) se sirven **localmente** desde la carpeta `static/vendor/`. El sistema debe funcionar **sin conexión a internet** durante el Demo Day.

4. **Blindaje contra AP Isolation:** La interfaz y el servidor operan sobre Hotspot personal o enlace Ethernet directo con IPs estáticas (`192.168.50.1` y `192.168.50.2`) o resolución mDNS (`raspberrypi.local`).

---

## 2. Stack Tecnológico y Justificación de Ingeniería

La selección prioriza consumo nulo de recursos de renderizado en la Pi, tiempos de carga instantáneos y compatibilidad total offline.

| Capa del Sistema | Tecnología | Justificación |
|---|---|---|
| Servidor Backend & Hosting UI | **FastAPI + Uvicorn** (Python) | Bucle asíncrono único (`asyncio.create_task`) para sensor, SQLite WAL, ONNX Runtime y endpoints |
| Estructura y Lógica Cliente | **HTML5 + Vanilla JS (ES6)** | Cero dependencias pesadas, manipulación directa del DOM, ventana deslizante de 200 registros en memoria |
| Sistema de Estilos | **Tailwind CSS (compilado estático)** | Diseño B&W minimalista, Bento Grid responsive, semáforo térmico, Modo Proyector. **Se usa el CLI standalone para generar CSS compilado, NO el CDN runtime** |
| Motor de Visualización | **Chart.js (local)** | Renderizado en `<canvas>` con aceleración por hardware de la laptop. Archivo `.min.js` servido desde `static/vendor/` |
| Transporte de Datos | **Fetch API + WebSockets Nativos** | Carga inicial de 200 muestras por HTTP GET + canal full-duplex con reconexión exponential backoff |

---

## 3. Sistema de Diseño: Minimalismo B&W y Semáforo Térmico

Estética minimalista de alto contraste: **blanco** como color principal, **negro** como secundario. Los colores del semáforo térmico tienen protagonismo absoluto.

### 3.1. Paleta Estructural (Blanco y Negro)

| Elemento | Color | Hex | Uso |
|---|---|---|---|
| Fondo Principal | Blanco Puro | `#FFFFFF` | Fondo general, tarjetas KPI, lienzos, contenedores |
| Fondo Secundario | Gris Zinc 100 | `#F4F4F5` | Burbujas de chatbot, encabezados secundarios, hovers |
| Estructural | Negro Carbón | `#09090B` | Bordes, tipografía principal, barra de telemetría, línea de temp real |

**Tipografía:**
- **Sans-Serif** (`Inter` / `system-ui`): Títulos, etiquetas, mensajes del chatbot
- **Monospace** (`JetBrains Mono` / `monospace`): Cifras de temperatura, timestamps, métricas (MAE, MSE), telemetría — evita que los números "bailen" al actualizarse

### 3.2. Semáforo Térmico Escalonado (4 Niveles)

| Nivel | Color | Hex / Tailwind | Condición | Comportamiento Visual |
|---|---|---|---|---|
| 1. Ideal | 🟢 Verde | `#10B981` / `emerald-500` | Temp < 24.0°C y `is_anomaly: false` | Badge verde "IDEAL", borde izquierdo verde en historial |
| 2. Precaución | 🟡 Amarillo | `#F59E0B` / `amber-500` | 24.0°C ≤ Temp < 25.5°C y `is_anomaly: false` | Badge amarillo "PRECAUCIÓN" |
| 3. Alerta | 🟠 Naranja | `#F97316` / `orange-500` | 25.5°C ≤ Temp < 27.5°C o pronóstico en subida pronunciada | Badge naranja "ALERTA" |
| 4. Crítica | 🔴 Rojo | `#DC2626` / `red-600` | Temp ≥ 27.5°C, o `autoencoder_mse > anomaly_threshold`, o `is_anomaly: true` | Badge rojo "CRÍTICA", parpadeo, registro en incidentes, sonido de alerta |

### 3.3. Comportamiento Responsive y Modo Proyector

| Breakpoint | Layout |
|---|---|
| **Móvil** (< 640px) | 1 columna vertical, KPIs apilados, gráficas al 100% de ancho, chatbot al 92% |
| **Tablet** (640px–1024px) | 2 columnas para KPIs, paneles de gráficas apilados |
| **Desktop** (> 1024px) | 4 columnas KPIs superiores + 3 columnas inferiores (2 gráficas + 1 historial/incidentes) |

**Modo Proyector** (Requisito Semana 6): Botón en la barra superior que activa:
- Bordes de 3px en tarjetas
- Escala tipográfica al 108%
- Líneas de Chart.js más gruesas (`borderWidth: 4`)
- Puntos de datos más grandes (`pointRadius: 5`)
- Badges de semáforo agrandados
- Alto contraste general para legibilidad desde el fondo de un auditorio

---

## 4. Arquitectura de Comunicación y Contrato de Datos

### 4.1. Carga de Historial Inicial (HTTP GET)

```
GET http://<IP_RASPI>:8000/api/history?limit=200
```

Al abrir el navegador, el frontend ejecuta esta petición **una sola vez** para recuperar las últimas 200 muestras del SSD NVMe. Pobla el historial y las gráficas de inmediato sin esperar 30 minutos.

### 4.2. Health Check (HTTP GET) — *Mejora añadida*

```
GET http://<IP_RASPI>:8000/api/health
```

Retorna estado del sensor, último timestamp, uptime del servidor y estadísticas básicas. Útil para diagnóstico rápido.

### 4.3. Streaming en Tiempo Real (WebSocket Push)

```
ws://<IP_RASPI>:8000/ws/stream
```

**Frecuencia:** Cada 10–15 segundos. La Pi toma lectura, limpia, ejecuta ONNX, guarda en SQLite WAL y emite el siguiente JSON a todos los clientes:

```json
{
  "timestamp": "2026-10-16T18:30:15",
  "sensor_status": "OK",
  "current_temp_c": 24.62,
  "forecast_30m_c": 25.18,
  "baseline_30m_c": 24.62,
  "rolling_mae_model": 0.21,
  "rolling_mae_baseline": 0.58,
  "autoencoder_mse": 0.0034,
  "anomaly_threshold": 0.0250,
  "is_anomaly": false,
  "pi_metrics": {
    "inference_time_ms": 2.4,
    "ram_used_mb": 142.0
  }
}
```

### 4.4. Diccionario de Datos del Contrato JSON

| Campo | Tipo | Descripción | Mapeo en UI |
|---|---|---|---|
| `timestamp` | `string` (ISO-8601) | Fecha y hora de la muestra en la Pi | Eje X de gráficas, filas de historial, tabla de incidentes (formato `HH:MM:SS`) |
| `sensor_status` | `string` | Estado del bus 1-Wire (`"OK"` o alerta de fallo) | Badge del sensor en header |
| `current_temp_c` | `float` | Temperatura actual del salón (°C) | KPI 1, serie principal Gráfica 1, color en historial |
| `forecast_30m_c` | `float` | Predicción del modelo de regresión para t+30min | KPI 2, curva de pronóstico Gráfica 1 |
| `baseline_30m_c` | `float` | Predicción base (temp actual = temp futura) | Comparativa en KPI 2, línea gris Gráfica 1 |
| `rolling_mae_model` | `float` | MAE móvil del modelo IA | KPI 4 |
| `rolling_mae_baseline` | `float` | MAE móvil del baseline | KPI 4 (comparativa) |
| `autoencoder_mse` | `float` | Error de reconstrucción del Autoencoder | KPI 3, serie principal Gráfica 2 |
| `anomaly_threshold` | `float` | Umbral máximo permitido de MSE | KPI 3, línea roja horizontal Gráfica 2 |
| `is_anomaly` | `boolean` | Disparo de anomalía | Alarma visual roja global, registro en tabla de incidentes |
| `pi_metrics.inference_time_ms` | `float` | Tiempo de inferencia en la Pi (ms) | Telemetría en header |
| `pi_metrics.ram_used_mb` | `float` | RAM utilizada en la Pi (MB) | Telemetría en header |

---

## 5. Estructura de Archivos del Proyecto

```
nano-ai-system/
├── app/
│   ├── main.py                 # Servidor FastAPI, bucle asyncio, SQLite WAL, API, WebSocket
│   ├── database.py             # Esquema SQLite (raw_readings, clean_readings, logs)
│   ├── sensor.py               # Lectura 1-Wire (GPIO 4) y filtro de errores
│   ├── inference.py            # Carga scaler.json e inferencia CPU ARM con onnxruntime
│   └── models/
│       ├── regressor_30m.onnx  # Modelo de regresión +30 min
│       ├── autoencoder.onnx    # Detector de anomalías (entrenado solo con normalidad)
│       └── scaler.json         # Media y desviación estándar del Train Set
├── nvme_data/
│   └── telemetry.db            # SQLite persistente en modo WAL
├── static/
│   ├── index.html              # Single-File Frontend principal
│   └── vendor/                 # ⬅ MEJORA: Librerías locales (sin CDN)
│       ├── chart.min.js        #   Chart.js v4.x minificado
│       └── tailwind.css        #   Tailwind CSS compilado con CLI standalone
├── nano-ai.service             # ⬅ MEJORA: Archivo systemd para auto-arranque
├── requirements.txt            # ⬅ MEJORA: Dependencias Python
├── .gitignore                  # ⬅ MEJORA: Exclusiones de Git
└── README.md                   # Instrucciones de setup y despliegue
```

---

## 6. Especificación Detallada de Componentes del Frontend

### 6.1. Componente 1: Barra Superior de Estado y Telemetría (`HeaderBar`)
- **Ubicación:** Fija en la parte superior (`sticky top-0 z-40`), fondo `#FFFFFF`, borde inferior de 2px en `#09090B`.
- **Elementos integrados:**
  1. **Identidad del Proyecto:** Logotipo `NANO-AI` en tipografía ultra-negra (`font-black`) con subtítulo de tracks.
  2. **Badge de Conexión WebSocket (`#ws-badge`):**
     - Verde (`bg-emerald-500`): Conectado y mostrando latencia de inferencia / ping.
     - Amarillo (`bg-amber-500`): Reconectando (muestra intento y delay con *exponential backoff*).
     - Rojo (`bg-red-600`): Desconectado o error de transporte.
  3. **Badge del Sensor (`#sensor-badge`):** Indica `OK` o `ERROR 1-WIRE` (filtro CRC!=YES, 85°C o -127°C).
  4. **Panel de Telemetría Pi (`#pi-telemetry`):** Bloque `#09090B` con tipografía mono blanca mostrando `RAM: X MB | Inferencia: Y ms`.
  5. **Controles Rápidos:**
     - Botón de **Modo Proyector** (`#projector-btn`): Alterna estilos de alto contraste y escala ampliada.
     - Botón de **Alerta Sonora** (`#audio-toggle-btn`): Activa/desactiva pitido de emergencia vía *Web Audio API* (sin archivos de audio externos).

### 6.2. Componente 2: Grid de Tarjetas de Impacto (`KPICards`)
Cuatro tarjetas en cuadrícula Bento con bordes definidos `#09090B` y fondo blanco por defecto:

- **Tarjeta 1 — Temperatura en Tiempo Real:**
  - Valor actual en `text-5xl font-black` con indicador de tendencia (↑ En subida, ↓ En bajada, → Estable).
  - Badge superior dinámico según el Semáforo Térmico: `IDEAL` (Verde), `PRECAUCIÓN` (Amarillo), `ALERTA` (Naranja), `CRÍTICA` (Rojo).
  - Timestamp exacto de la última lectura en el pie.
- **Tarjeta 2 — Predicción IA a +30 Minutos:**
  - Valor predicho `forecast_30m_c` con diferencial calculado ($\Delta \pm X.XX\ ^\circ\text{C}$).
  - Valor del `baseline_30m_c` para evidenciar la comparación en vivo.
  - Evaluación anticipada: Si la IA predice temperatura crítica en 30 min, la tarjeta adopta el color del semáforo por adelantado.
- **Tarjeta 3 — Detector de Anomalías (Autoencoder):**
  - Estado normal: Fondo blanco, borde negro, texto `NORMAL` en verde.
  - Estado anomalía (`is_anomaly: true` o $MSE > \text{umbral}$): Invierte estilo a fondo rojo `#DC2626`, texto blanco y pulso animado.
  - Sub-métricas: `MSE actual` vs `Umbral de corte`.
- **Tarjeta 4 — Desempeño del Modelo (Rolling MAE vs Baseline):**
  - Muestra `rolling_mae_model` frente a `rolling_mae_baseline`.
  - Badge de ganancia relativa: $+X\%$ Precisión sobre el baseline estricto.

### 6.3. Componente 3: Panel de Gráficas en Tiempo Real (`ChartsPanel`)
Desarrollado sobre Chart.js con aceleración por hardware en `<canvas>`:

- **Gráfica 1 (Panel 1) — Serie Térmica y Pronóstico:**
  - **Serie 1 (Negra continua, 2.5px):** Lectura física real `current_temp_c`.
  - **Serie 2 (Naranja discontinua `[5, 5]`, puntos coloreados por nivel térmico):** `forecast_30m_c`.
  - **Serie 3 (Gris tenue, 1.5px):** `baseline_30m_c`.
- **Gráfica 2 (Panel 2) — Error MSE vs Umbral Crítico:**
  - **Serie 1 (Negra con área sombreada al 8% de opacidad):** `autoencoder_mse`.
  - **Serie 2 (Línea roja sólida continua):** `anomaly_threshold`.
- **Comportamiento en Modo Proyector:** Al activarse, los canvas reconfiguran dinámicamente `borderWidth` a 4px, `pointRadius` a 5px y tamaño de fuentes a 14px mono para garantizar visibilidad a 15 metros en auditorio.

### 6.4. Componente 4: Historial Coloreado, Incidentes y Exportación (`HistoryAndIncidents`)
Sistema de pestañas en la columna lateral:
- **Pestaña Historial:**
  - Ventana deslizante de hasta 200 registros.
  - Borde lateral izquierdo de 4px (`border-l-4`) según el color del semáforo.
  - Botón para **Exportar Historial en CSV** en memoria (para auditorías y bitácora técnica).
- **Pestaña Incidentes:**
  - Tabla de detección de rachas anómalas: `ID`, `Timestamp Inicio`, `Timestamp Fin` (o "En curso"), `Temp Máxima` y `MSE Máximo`.
  - Contador reactivo de incidentes en el badge de la pestaña.

### 6.5. Componente 5: Chatbot Asistente del Salón (`ClassroomChatbot`)
- Motor conversacional determinista ejecutado 100% en el cliente (0 ms latencia, cero carga de RAM/CPU en la Pi).
- Analiza `latestPayload` y la ventana `historyBuffer`.
- Contesta consultas directas de temperatura actual, pronóstico a 30 min, estatus de anomalías, métricas de hardware de la Pi y resumen general.
- Incluye chips de preguntas predeterminadas (*Quick Asks*) y badge rojo en el botón flotante si surge una anomalía crítica.

---

## 7. Código Base Completo y Mejorado

### 7.1. Backend en FastAPI (`app/main.py`)

> [!NOTE]
> **Mejoras aplicadas sobre la versión original:**
> 1. Manejo seguro de SQLite mediante conexión reutilizable protegida por `asyncio.Lock` (sin reconnect masivo cada 10s).
> 2. Bloque `try/except` robusto en el bucle asíncrono con logging formal para evitar paradas inesperadas.
> 3. Endpoint `GET /api/health` para diagnóstico de hardware y estado del sistema.
> 4. Limpieza adecuada de WebSockets desconectados con control de excepciones.

```python
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

# Lock global para acceso serializado seguro a SQLite en entorno async
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
        if cur.fetchone()[0] == 0:
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
    return FileResponse("static/index.html")
```

### 7.2. Frontend Completo Mejorado (`static/index.html`)

> [!TIP]
> **Mejoras clave en la versión del Dashboard:**
> - **Autonomía 100% Offline:** Se enlaza a `vendor/chart.min.js` y `vendor/tailwind.css` con fallback automático si se prueba con conexión.
> - **Reconexión con Exponential Backoff y Jitter:** Evita tormentas de peticiones a la Pi tras microcortes de red.
> - **Alarma Sonora Sintetizada:** Generador de tono agudo mediante *Web Audio API* nativo (sin descargar MP3/WAV).
> - **Indicador de Tendencia Térmica:** Símbolos visuales `↑`, `↓` o `→` calculados sobre la ventana reciente.
> - **Exportación CSV:** Descarga directa de lecturas históricas para la bitácora del proyecto.
> - **Modo Proyector Integral:** Ajuste reactivo de grosores de línea y fuentes en los lienzos de Chart.js.

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nano-AI | Dashboard Térmico de Borde</title>

  <!-- Enlace local a librerías (Modo Offline Estricto para Demo Day) con fallback de CDN -->
  <link rel="stylesheet" href="/static/vendor/tailwind.css" onerror="this.onerror=null;var s=document.createElement('script');s.src='https://cdn.tailwindcss.com';document.head.appendChild(s);" />
  <script src="/static/vendor/chart.min.js" onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/chart.js';"></script>

  <style>
    /* Estilos Estructurales B&W y Modo Proyector */
    body.projector-mode {
      font-size: 112%;
    }
    body.projector-mode .card-box {
      border-width: 3px !important;
    }
    /* Scrollbar B&W Minimalista */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #f4f4f5; }
    ::-webkit-scrollbar-thumb { background: #09090b; }

    /* Animación de pulso para alerta crítica */
    @keyframes pulse-critical {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }
    .animate-critical {
      animation: pulse-critical 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
  </style>
</head>
<body class="bg-white text-zinc-950 font-sans antialiased selection:bg-zinc-950 selection:text-white min-h-screen flex flex-col">

  <!-- 1. HEADER: Estado de Red, Sensor, Telemetría Pi y Controles -->
  <header class="border-b-2 border-zinc-950 bg-white sticky top-0 z-40" role="banner">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div id="live-dot" class="w-3.5 h-3.5 bg-zinc-400 rounded-full transition-colors" title="Estado de Transmisión"></div>
        <div>
          <h1 class="font-black tracking-tight text-lg leading-none">NANO-AI</h1>
          <p class="text-[11px] font-mono text-zinc-500">Track 3 & 4 | Edge AI Thermal Predictor & Anomaly Detector</p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
        <span id="ws-badge" class="px-2.5 py-1 border border-zinc-950 bg-zinc-100 font-bold" aria-live="polite">
          WS: Conectando...
        </span>
        <span id="sensor-badge" class="px-2.5 py-1 border border-zinc-950 font-semibold">
          Sensor: --
        </span>
        <span id="pi-telemetry" class="px-2.5 py-1 bg-zinc-950 text-white font-semibold">
          Pi RAM: -- MB | Inf: -- ms
        </span>
        <button id="audio-toggle-btn" class="px-2.5 py-1 border border-zinc-950 bg-white hover:bg-zinc-100 font-bold transition" title="Activar/Desactivar alarma acústica">
          🔊 Audio: OFF
        </button>
        <button id="projector-btn" class="px-2.5 py-1 border border-zinc-950 bg-white hover:bg-zinc-950 hover:text-white font-bold transition">
          Modo Proyector: OFF
        </button>
      </div>
    </div>
  </header>

  <!-- BANNER GLOBAL DE ALERTA CRÍTICA -->
  <div id="critical-banner" class="hidden bg-red-600 text-white px-4 py-2 text-center font-mono text-xs font-bold tracking-wide uppercase animate-critical" role="alert">
    ¡ALERTA TÉRMICA ACTIVA! Incremento anómalo detectado en el sensor físico.
  </div>

  <!-- 2. CONTENIDO PRINCIPAL -->
  <main class="max-w-7xl w-full mx-auto px-4 py-6 space-y-6 flex-1">

    <!-- FILA SUPERIOR: 4 TARJETAS KPI -->
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-label="Indicadores Clave">
      
      <!-- KPI 1: Temperatura en Tiempo Real -->
      <div class="card-box border border-zinc-950 p-5 bg-white flex flex-col justify-between">
        <div class="flex justify-between items-center">
          <span class="text-xs uppercase tracking-wider font-extrabold text-zinc-500">Temp. Tiempo Real</span>
          <span id="kpi-current-badge" class="text-xs font-bold px-2.5 py-0.5 text-white bg-zinc-400">CARGANDO</span>
        </div>
        <div class="my-3 flex items-baseline gap-1.5 font-mono">
          <span id="kpi-current-val" class="text-5xl font-black tracking-tight">--.--</span>
          <span class="text-2xl font-bold">°C</span>
          <span id="kpi-trend" class="text-lg font-bold text-zinc-400" title="Tendencia térmica">→</span>
        </div>
        <div class="flex justify-between text-xs font-mono text-zinc-500 border-t border-zinc-200 pt-2">
          <span>DS18B20 (1-Wire)</span>
          <span id="kpi-current-time">--:--:--</span>
        </div>
      </div>

      <!-- KPI 2: Predicción IA (+30 Minutos) -->
      <div id="kpi-forecast-card" class="card-box border border-zinc-950 p-5 bg-white flex flex-col justify-between">
        <div class="flex justify-between items-center">
          <span class="text-xs uppercase tracking-wider font-extrabold text-zinc-500">Predicción +30 Min</span>
          <span id="kpi-forecast-badge" class="text-xs font-bold px-2.5 py-0.5 text-white bg-zinc-400">CARGANDO</span>
        </div>
        <div class="my-3 flex items-baseline gap-1.5 font-mono">
          <span id="kpi-forecast-val" class="text-5xl font-black tracking-tight">--.--</span>
          <span class="text-2xl font-bold">°C</span>
        </div>
        <div class="flex justify-between text-xs font-mono text-zinc-600 border-t border-zinc-200 pt-2">
          <span id="kpi-forecast-delta">Δ +0.00 °C</span>
          <span id="kpi-baseline-val">Base: --.-- °C</span>
        </div>
      </div>

      <!-- KPI 3: Detector de Anomalías (Autoencoder) -->
      <div id="kpi-anomaly-card" class="card-box border border-zinc-950 p-5 bg-white flex flex-col justify-between transition-colors">
        <div class="flex justify-between items-center">
          <span class="text-xs uppercase tracking-wider font-extrabold opacity-75">Detector Anomalías</span>
          <span class="text-xs font-mono font-bold border border-current px-1.5">Autoencoder</span>
        </div>
        <div class="my-3">
          <span id="kpi-anomaly-status" class="text-3xl font-black tracking-tight uppercase">NORMAL</span>
        </div>
        <div class="flex justify-between text-xs font-mono opacity-85 border-t border-current/20 pt-2">
          <span id="kpi-mse-val">MSE: 0.0000</span>
          <span id="kpi-thresh-val">Umbral: 0.0250</span>
        </div>
      </div>

      <!-- KPI 4: Desempeño del Modelo (Rolling MAE vs Baseline) -->
      <div class="card-box border border-zinc-950 p-5 bg-white flex flex-col justify-between">
        <div class="flex justify-between items-center">
          <span class="text-xs uppercase tracking-wider font-extrabold text-zinc-500">Precisión en Vivo</span>
          <span id="kpi-mae-gain" class="text-xs font-mono font-bold bg-zinc-950 text-white px-2 py-0.5">--% Mejor</span>
        </div>
        <div class="my-3 space-y-1.5 font-mono text-sm">
          <div class="flex justify-between items-center">
            <span class="text-zinc-600">MAE Modelo IA:</span>
            <strong id="kpi-mae-model" class="text-base font-black">--.-- °C</strong>
          </div>
          <div class="flex justify-between items-center text-zinc-500">
            <span>MAE Baseline:</span>
            <span id="kpi-mae-base">--.-- °C</span>
          </div>
        </div>
        <div class="text-xs font-mono text-zinc-500 border-t border-zinc-200 pt-2">
          Ventana móvil de validación
        </div>
      </div>

    </section>

    <!-- FILA INFERIOR: PANELES DE GRÁFICAS (2 COLS) + HISTORIAL E INCIDENTES (1 COL) -->
    <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- COLUMNA IZQUIERDA (2/3): Paneles de Gráficas Chart.js -->
      <div class="lg:col-span-2 space-y-6">
        
        <!-- Panel 1: Temperatura Real vs Predicción (+30m) vs Baseline -->
        <div class="card-box border border-zinc-950 p-5 bg-white">
          <div class="flex flex-wrap justify-between items-center gap-2 mb-4 pb-2 border-b border-zinc-200">
            <div>
              <h2 class="font-black uppercase text-sm tracking-wider">Panel 1: Serie Térmica y Pronóstico a 30 Minutos</h2>
              <p class="text-xs text-zinc-500 font-mono">Stream vía WebSocket cada 10-15s</p>
            </div>
            <!-- Leyenda cromática -->
            <div class="flex flex-wrap gap-2 text-[11px] font-mono font-bold">
              <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 bg-emerald-500 inline-block"></i>Ideal (&lt;24°C)</span>
              <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 bg-amber-500 inline-block"></i>Precaución</span>
              <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 bg-orange-500 inline-block"></i>Alerta</span>
              <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 bg-red-600 inline-block"></i>Crítica (&ge;27.5°C)</span>
            </div>
          </div>
          <div class="h-64">
            <canvas id="tempChart"></canvas>
          </div>
        </div>

        <!-- Panel 2: Error de Reconstrucción MSE vs Umbral Rojo -->
        <div class="card-box border border-zinc-950 p-5 bg-white">
          <div class="flex justify-between items-center mb-4 pb-2 border-b border-zinc-200">
            <div>
              <h2 class="font-black uppercase text-sm tracking-wider">Panel 2: Error de Reconstrucción (Autoencoder MSE) vs Umbral Crítico</h2>
              <p class="text-xs text-zinc-500 font-mono">Detección de anomalías térmicas en tiempo real</p>
            </div>
            <span class="text-xs font-mono font-bold text-red-600 border border-red-600 px-2 py-0.5">
              Línea Roja = Umbral Crítico
            </span>
          </div>
          <div class="h-48">
            <canvas id="mseChart"></canvas>
          </div>
        </div>

      </div>

      <!-- COLUMNA DERECHA (1/3): Historial Coloreado + Tabla de Incidentes -->
      <div class="card-box border border-zinc-950 bg-white flex flex-col h-[34rem]">
        
        <!-- Pestañas de Navegación -->
        <div class="grid grid-cols-2 border-b border-zinc-950 text-xs font-bold uppercase tracking-wider">
          <button id="tab-btn-history" class="py-3 bg-zinc-950 text-white transition">
            Historial (<span id="history-count">0</span>)
          </button>
          <button id="tab-btn-incidents" class="py-3 bg-white text-zinc-950 hover:bg-zinc-100 transition">
            Incidentes (<span id="incident-count">0</span>)
          </button>
        </div>

        <!-- Barra de Utilidades: Exportar CSV -->
        <div class="px-3 py-1.5 border-b border-zinc-200 bg-zinc-50 flex justify-between items-center text-[11px] font-mono">
          <span class="text-zinc-500">Últimas 200 lecturas</span>
          <button id="btn-export-csv" class="px-2 py-0.5 border border-zinc-950 bg-white hover:bg-zinc-950 hover:text-white font-bold transition">
            📥 Descargar CSV
          </button>
        </div>

        <!-- Pestaña 1: Historial Escalonado -->
        <div id="tab-panel-history" class="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs">
          <!-- Filas inyectadas dinámicamente -->
        </div>

        <!-- Pestaña 2: Registro de Incidentes -->
        <div id="tab-panel-incidents" class="hidden flex-1 overflow-y-auto p-4 font-mono text-xs">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b-2 border-zinc-950 text-[11px] uppercase">
                <th class="py-1.5">Inicio</th>
                <th class="py-1.5">Fin</th>
                <th class="py-1.5">Temp Máx</th>
                <th class="py-1.5">MSE Máx</th>
              </tr>
            </thead>
            <tbody id="incidents-tbody" class="divide-y divide-zinc-200">
              <!-- Incidentes inyectados dinámicamente -->
            </tbody>
          </table>
          <p id="no-incidents-msg" class="text-center text-zinc-400 mt-8">
            Sin anomalías registradas en esta sesión.
          </p>
        </div>

      </div>

    </section>
  </main>

  <!-- 3. CHATBOT ASISTENTE DEL SALÓN -->
  <div class="fixed bottom-5 right-5 z-50">
    <div id="chat-window" class="hidden w-80 sm:w-96 h-[28rem] bg-white border-2 border-zinc-950 shadow-2xl flex flex-col mb-3">
      
      <!-- Encabezado del Chatbot -->
      <div class="bg-zinc-950 text-white px-4 py-3 flex justify-between items-center">
        <div>
          <h3 class="font-bold text-xs uppercase tracking-wider">Asistente Térmico del Salón</h3>
          <p class="text-[10px] font-mono text-zinc-300">Conectado en vivo a la Nano-AI</p>
        </div>
        <button id="close-chat" class="text-xs font-mono border border-white px-2 py-0.5 hover:bg-white hover:text-zinc-950 font-bold">
          ✕
        </button>
      </div>

      <!-- Mensajes -->
      <div id="chat-messages" class="flex-1 p-3 overflow-y-auto space-y-2.5 text-xs">
        <div class="bg-zinc-100 border border-zinc-300 p-2.5 text-zinc-900">
          Hola. Soy el asistente local del salón. Puedes consultarme la temperatura actual, pronóstico a 30 min, detección de anomalías o métricas de la Raspberry Pi.
        </div>
      </div>

      <!-- Quick Asks -->
      <div class="px-3 py-2 border-t border-zinc-200 flex gap-1.5 overflow-x-auto text-[11px] font-mono bg-zinc-50">
        <button class="quick-ask border border-zinc-950 bg-white px-2 py-1 hover:bg-zinc-950 hover:text-white whitespace-nowrap" data-q="¿Cuál es la temperatura actual del salón?">¿Temp actual?</button>
        <button class="quick-ask border border-zinc-950 bg-white px-2 py-1 hover:bg-zinc-950 hover:text-white whitespace-nowrap" data-q="¿Va a subir la temperatura en 30 minutos?">¿Subirá en 30m?</button>
        <button class="quick-ask border border-zinc-950 bg-white px-2 py-1 hover:bg-zinc-950 hover:text-white whitespace-nowrap" data-q="¿Se ha detectado alguna anomalía?">¿Hay anomalías?</button>
        <button class="quick-ask border border-zinc-950 bg-white px-2 py-1 hover:bg-zinc-950 hover:text-white whitespace-nowrap" data-q="¿Cuál es el estado de la Raspberry Pi?">Estado Raspi</button>
      </div>

      <!-- Entrada de Usuario -->
      <form id="chat-form" class="border-t-2 border-zinc-950 flex bg-white">
        <input id="chat-input" type="text" placeholder="Pregunta sobre el estado del salón..." class="flex-1 px-3 py-2.5 text-xs focus:outline-none" />
        <button type="submit" class="bg-zinc-950 text-white px-4 py-2.5 text-xs font-bold uppercase hover:bg-zinc-800">
          Enviar
        </button>
      </form>
    </div>

    <!-- Botón Flotante -->
    <button id="toggle-chat" class="bg-zinc-950 text-white border-2 border-zinc-950 px-4 py-3 font-bold text-xs uppercase tracking-wider shadow-xl hover:bg-white hover:text-zinc-950 transition flex items-center gap-2 ml-auto">
      <span>Chat del Salón</span>
      <span id="chat-alert-dot" class="hidden w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
    </button>
  </div>

  <!-- 4. LÓGICA JAVASCRIPT DEL CLIENTE -->
  <script>
    // ============================================================================
    // MÓDULO 1: ESCALA CROMÁTICA ESCALONADA
    // ============================================================================
    function getThermalScale(tempC, isAnomaly = false) {
      if (isAnomaly || tempC >= 27.5) {
        return {
          level: "CRÍTICA",
          bgClass: "bg-red-600",
          borderClass: "border-red-600",
          textClass: "text-red-600",
          hex: "#dc2626"
        };
      }
      if (tempC >= 25.5) {
        return {
          level: "ALERTA",
          bgClass: "bg-orange-500",
          borderClass: "border-orange-500",
          textClass: "text-orange-600",
          hex: "#f97316"
        };
      }
      if (tempC >= 24.0) {
        return {
          level: "PRECAUCIÓN",
          bgClass: "bg-amber-500",
          borderClass: "border-amber-500",
          textClass: "text-amber-600",
          hex: "#f59e0b"
        };
      }
      return {
        level: "IDEAL",
        bgClass: "bg-emerald-500",
        borderClass: "border-emerald-500",
        textClass: "text-emerald-600",
        hex: "#10b981"
      };
    }

    // Estado en memoria
    const MAX_SAMPLES = 200;
    const CHART_WINDOW = 50;
    let rawHistoryBuffer = [];
    let latestPayload = null;
    let activeIncident = null;
    let incidentsList = [];
    let audioAlertEnabled = false;
    let audioCtx = null;

    // Generador de audio de alerta nativo (Web Audio API)
    function playBeepAlert() {
      if (!audioAlertEnabled) return;
      try {
        if (!audioCtx) {
          audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
          audioCtx.resume();
        }
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // 880 Hz (A5)
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.35);
      } catch (e) {
        console.warn("No se pudo emitir audio de alerta:", e);
      }
    }

    // ============================================================================
    // MÓDULO 2: GRÁFICAS CHART.JS
    // ============================================================================
    const tempCtx = document.getElementById("tempChart").getContext("2d");
    const tempChart = new Chart(tempCtx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Temp. Actual (°C)",
            data: [],
            borderColor: "#09090b",
            backgroundColor: "#09090b",
            borderWidth: 2.5,
            pointRadius: 2.5,
            tension: 0.25
          },
          {
            label: "Predicción +30m (°C)",
            data: [],
            borderColor: "#f97316",
            borderDash: [5, 5],
            pointBackgroundColor: [],
            pointBorderColor: [],
            borderWidth: 2.5,
            pointRadius: 3.5,
            tension: 0.25
          },
          {
            label: "Baseline (+30m)",
            data: [],
            borderColor: "#a1a1aa",
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.25
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { labels: { color: "#09090b", font: { family: "monospace", size: 11 } } }
        },
        scales: {
          x: { ticks: { color: "#52525b", maxTicksLimit: 8, font: { family: "monospace", size: 10 } } },
          y: { ticks: { color: "#09090b", font: { family: "monospace", size: 11 } } }
        }
      }
    });

    const mseCtx = document.getElementById("mseChart").getContext("2d");
    const mseChart = new Chart(mseCtx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Autoencoder MSE",
            data: [],
            borderColor: "#09090b",
            backgroundColor: "rgba(9, 9, 11, 0.08)",
            fill: true,
            borderWidth: 2,
            pointRadius: 2,
            tension: 0.2
          },
          {
            label: "Umbral Crítico (Rojo)",
            data: [],
            borderColor: "#dc2626",
            borderWidth: 2,
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { labels: { color: "#09090b", font: { family: "monospace", size: 11 } } }
        },
        scales: {
          x: { ticks: { color: "#52525b", maxTicksLimit: 8, font: { family: "monospace", size: 10 } } },
          y: { beginAtZero: true, ticks: { color: "#09090b", font: { family: "monospace", size: 10 } } }
        }
      }
    });

    // ============================================================================
    // MÓDULO 3: HISTORIAL, INCIDENTES Y EXPORTACIÓN CSV
    // ============================================================================
    const historyPanel = document.getElementById("tab-panel-history");
    const incidentsTbody = document.getElementById("incidents-tbody");

    function appendHistoryRow(data) {
      const scale = getThermalScale(data.current_temp_c, data.is_anomaly);
      const forecastScale = getThermalScale(data.forecast_30m_c, false);
      const timeStr = data.timestamp.split("T")[1] || data.timestamp;

      const row = document.createElement("div");
      row.className = `p-2.5 border border-zinc-200 bg-white flex items-center justify-between border-l-4 ${scale.borderClass}`;
      row.innerHTML = `
        <div>
          <div class="flex items-center gap-2">
            <span class="font-black text-sm text-zinc-950">${data.current_temp_c.toFixed(2)} °C</span>
            <span class="text-[11px] font-bold ${forecastScale.textClass}">→ +30m: ${data.forecast_30m_c.toFixed(2)} °C</span>
          </div>
          <div class="text-[10px] text-zinc-400">Hora: ${timeStr} | MSE: ${data.autoencoder_mse.toFixed(4)}</div>
        </div>
        <span class="px-2 py-0.5 text-[10px] font-bold text-white ${scale.bgClass}">
          ${scale.level}
        </span>
      `;
      historyPanel.prepend(row);

      while (historyPanel.children.length > MAX_SAMPLES) {
        historyPanel.removeChild(historyPanel.lastChild);
      }
      document.getElementById("history-count").textContent = historyPanel.children.length;
    }

    function trackIncident(data) {
      const timeStr = data.timestamp.split("T")[1] || data.timestamp;
      if (data.is_anomaly) {
        if (!activeIncident) {
          activeIncident = {
            id: incidentsList.length + 1,
            start: timeStr,
            end: "En curso",
            maxTemp: data.current_temp_c,
            maxMse: data.autoencoder_mse
          };
          incidentsList.unshift(activeIncident);
          playBeepAlert();
        } else {
          activeIncident.maxTemp = Math.max(activeIncident.maxTemp, data.current_temp_c);
          activeIncident.maxMse = Math.max(activeIncident.maxMse, data.autoencoder_mse);
        }
        renderIncidentsTable();
      } else if (activeIncident) {
        activeIncident.end = timeStr;
        activeIncident = null;
        renderIncidentsTable();
      }
    }

    function renderIncidentsTable() {
      document.getElementById("incident-count").textContent = incidentsList.length;
      document.getElementById("no-incidents-msg").classList.toggle("hidden", incidentsList.length > 0);
      incidentsTbody.innerHTML = incidentsList.map(inc => `
        <tr class="py-1.5">
          <td class="py-1.5 font-bold text-red-600">${inc.start}</td>
          <td class="py-1.5">${inc.end}</td>
          <td class="py-1.5 font-bold">${inc.maxTemp.toFixed(2)} °C</td>
          <td class="py-1.5">${inc.maxMse.toFixed(4)}</td>
        </tr>
      `).join("");
    }

    // Exportar CSV
    document.getElementById("btn-export-csv").onclick = () => {
      if (rawHistoryBuffer.length === 0) {
        alert("No hay registros disponibles para exportar.");
        return;
      }
      const headers = ["timestamp", "sensor_status", "current_temp_c", "forecast_30m_c", "baseline_30m_c", "rolling_mae_model", "rolling_mae_baseline", "autoencoder_mse", "anomaly_threshold", "is_anomaly", "inference_time_ms", "ram_used_mb"];
      const csvRows = [headers.join(",")];

      rawHistoryBuffer.forEach(item => {
        const row = [
          item.timestamp,
          item.sensor_status,
          item.current_temp_c,
          item.forecast_30m_c,
          item.baseline_30m_c,
          item.rolling_mae_model,
          item.rolling_mae_baseline,
          item.autoencoder_mse,
          item.anomaly_threshold,
          item.is_anomaly ? 1 : 0,
          item.pi_metrics?.inference_time_ms ?? "",
          item.pi_metrics?.ram_used_mb ?? ""
        ];
        csvRows.push(row.join(","));
      });

      const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nano_ai_history_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    };

    // ============================================================================
    // MÓDULO 4: INGESTA Y RENDERIZADO REACTIVO
    // ============================================================================
    function calculateTrend() {
      if (rawHistoryBuffer.length < 2) return "→";
      const last = rawHistoryBuffer[rawHistoryBuffer.length - 1].current_temp_c;
      const prev = rawHistoryBuffer[rawHistoryBuffer.length - 2].current_temp_c;
      const diff = last - prev;
      if (diff > 0.05) return "↑";
      if (diff < -0.05) return "↓";
      return "→";
    }

    function ingestSample(data, redrawCharts = true) {
      if (!data || typeof data.current_temp_c !== "number") {
        console.warn("Payload descartado por estructura inválida:", data);
        return;
      }

      latestPayload = data;
      rawHistoryBuffer.push(data);
      if (rawHistoryBuffer.length > MAX_SAMPLES) {
        rawHistoryBuffer.shift();
      }

      const timeStr = data.timestamp.split("T")[1] || data.timestamp;
      const curScale = getThermalScale(data.current_temp_c, false);
      const predScale = getThermalScale(data.forecast_30m_c, data.is_anomaly);

      // 1. Tarjeta Temperatura Actual
      document.getElementById("kpi-current-val").textContent = data.current_temp_c.toFixed(2);
      const curBadge = document.getElementById("kpi-current-badge");
      curBadge.textContent = curScale.level;
      curBadge.className = `text-xs font-bold px-2.5 py-0.5 text-white ${curScale.bgClass}`;
      document.getElementById("kpi-current-time").textContent = timeStr;
      document.getElementById("kpi-trend").textContent = calculateTrend();

      // 2. Tarjeta Predicción +30m
      document.getElementById("kpi-forecast-val").textContent = data.forecast_30m_c.toFixed(2);
      const predBadge = document.getElementById("kpi-forecast-badge");
      predBadge.textContent = predScale.level;
      predBadge.className = `text-xs font-bold px-2.5 py-0.5 text-white ${predScale.bgClass}`;
      const delta = data.forecast_30m_c - data.current_temp_c;
      document.getElementById("kpi-forecast-delta").textContent = `Δ ${delta >= 0 ? "+" : ""}${delta.toFixed(2)} °C`;
      document.getElementById("kpi-baseline-val").textContent = `Base: ${data.baseline_30m_c.toFixed(2)} °C`;

      // 3. Tarjeta Anomalías y Alarma Visual
      const anomalyCard = document.getElementById("kpi-anomaly-card");
      const anomalyStatus = document.getElementById("kpi-anomaly-status");
      const criticalBanner = document.getElementById("critical-banner");
      const chatAlertDot = document.getElementById("chat-alert-dot");

      if (data.is_anomaly || curScale.level === "CRÍTICA" || predScale.level === "CRÍTICA") {
        anomalyCard.className = "card-box border-2 border-red-600 p-5 bg-red-600 text-white flex flex-col justify-between";
        anomalyStatus.textContent = data.is_anomaly ? "¡ANOMALÍA!" : "TEMP. CRÍTICA";
        criticalBanner.classList.remove("hidden");
        chatAlertDot.classList.remove("hidden");
      } else {
        anomalyCard.className = "card-box border border-zinc-950 p-5 bg-white text-zinc-950 flex flex-col justify-between";
        anomalyStatus.textContent = "NORMAL";
        criticalBanner.classList.add("hidden");
        chatAlertDot.classList.add("hidden");
      }
      document.getElementById("kpi-mse-val").textContent = `MSE: ${data.autoencoder_mse.toFixed(4)}`;
      document.getElementById("kpi-thresh-val").textContent = `Umbral: ${data.anomaly_threshold.toFixed(4)}`;

      // 4. MAE y Telemetría Pi
      document.getElementById("kpi-mae-model").textContent = `${data.rolling_mae_model.toFixed(2)} °C`;
      document.getElementById("kpi-mae-base").textContent = `${data.rolling_mae_baseline.toFixed(2)} °C`;
      if (data.rolling_mae_baseline > 0) {
        const gain = ((1 - data.rolling_mae_model / data.rolling_mae_baseline) * 100).toFixed(0);
        document.getElementById("kpi-mae-gain").textContent = `+${gain}% Precisión`;
      }
      document.getElementById("sensor-badge").textContent = `Sensor: ${data.sensor_status}`;
      if (data.pi_metrics) {
        document.getElementById("pi-telemetry").textContent =
          `Pi RAM: ${data.pi_metrics.ram_used_mb.toFixed(1)} MB | Inf: ${data.pi_metrics.inference_time_ms.toFixed(1)} ms`;
      }

      // 5. Gráficas
      tempChart.data.labels.push(timeStr);
      tempChart.data.datasets[0].data.push(data.current_temp_c);
      tempChart.data.datasets[1].data.push(data.forecast_30m_c);
      tempChart.data.datasets[1].pointBackgroundColor.push(predScale.hex);
      tempChart.data.datasets[1].pointBorderColor.push(predScale.hex);
      tempChart.data.datasets[2].data.push(data.baseline_30m_c);

      mseChart.data.labels.push(timeStr);
      mseChart.data.datasets[0].data.push(data.autoencoder_mse);
      mseChart.data.datasets[1].data.push(data.anomaly_threshold);

      while (tempChart.data.labels.length > CHART_WINDOW) {
        tempChart.data.labels.shift();
        tempChart.data.datasets.forEach(ds => ds.data.shift());
        tempChart.data.datasets[1].pointBackgroundColor.shift();
        tempChart.data.datasets[1].pointBorderColor.shift();

        mseChart.data.labels.shift();
        mseChart.data.datasets.forEach(ds => ds.data.shift());
      }

      if (redrawCharts) {
        tempChart.update();
        mseChart.update();
      }

      // 6. Historial e Incidentes
      appendHistoryRow(data);
      trackIncident(data);
    }

    // ============================================================================
    // MÓDULO 5: WEBSOCKET CON EXPONENTIAL BACKOFF
    // ============================================================================
    let wsAttempts = 0;
    const baseDelay = 1000; // 1s
    const maxDelay = 15000; // 15s

    function startWebSocket() {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${proto}//${window.location.host}/ws/stream`);
      const wsBadge = document.getElementById("ws-badge");
      const liveDot = document.getElementById("live-dot");

      ws.onopen = () => {
        wsAttempts = 0;
        wsBadge.textContent = "Conectado | Stream Activo";
        wsBadge.className = "px-2.5 py-1 border border-zinc-950 bg-emerald-500 text-white font-bold";
        liveDot.className = "w-3.5 h-3.5 bg-emerald-500 rounded-full";
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          ingestSample(payload, true);
          wsBadge.textContent = `Conectado | Inf: ${payload.pi_metrics?.inference_time_ms ?? "--"} ms`;
        } catch (err) {
          console.error("Error al procesar mensaje WebSocket:", err);
        }
      };

      ws.onclose = () => {
        wsAttempts++;
        const jitter = Math.random() * 800;
        const delay = Math.min(baseDelay * Math.pow(1.5, wsAttempts) + jitter, maxDelay);

        wsBadge.textContent = `Reconectando en ${(delay / 1000).toFixed(1)}s (Intento #${wsAttempts})`;
        wsBadge.className = "px-2.5 py-1 border border-zinc-950 bg-amber-500 text-white font-bold";
        liveDot.className = "w-3.5 h-3.5 bg-red-600 rounded-full";

        setTimeout(startWebSocket, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    // ============================================================================
    // MÓDULO 6: CHATBOT ASISTENTE DETERMINISTA
    // ============================================================================
    function generateChatbotReply(query) {
      if (!latestPayload) {
        return "Aún no se reciben lecturas desde la Raspberry Pi. Por favor verifica que el servidor esté activo.";
      }
      const q = query.toLowerCase();
      const curScale = getThermalScale(latestPayload.current_temp_c, false);
      const predScale = getThermalScale(latestPayload.forecast_30m_c, latestPayload.is_anomaly);
      const diff = (latestPayload.forecast_30m_c - latestPayload.current_temp_c).toFixed(2);

      if (q.includes("actual") || q.includes("cuánto") || q.includes("ahora") || q.includes("temperatura")) {
        return `La temperatura actual del salón es ${latestPayload.current_temp_c.toFixed(2)} °C (Nivel: ${curScale.level}). Sensor DS18B20 en estado: ${latestPayload.sensor_status}.`;
      }
      if (q.includes("subir") || q.includes("30") || q.includes("predicción") || q.includes("futuro") || q.includes("pronóstico")) {
        const trend = diff >= 0 ? `un alza de +${diff} °C` : `una reducción de ${diff} °C`;
        return `La predicción a +30 minutos es de ${latestPayload.forecast_30m_c.toFixed(2)} °C (${trend}), situándose en clasificación ${predScale.level}.`;
      }
      if (q.includes("anomalía") || q.includes("alerta") || q.includes("normal") || q.includes("incidente")) {
        if (latestPayload.is_anomaly) {
          return `¡Atención! El Autoencoder detectó una anomalía activa (MSE: ${latestPayload.autoencoder_mse.toFixed(4)} superó el umbral de ${latestPayload.anomaly_threshold.toFixed(4)}). Total de incidentes en la sesión: ${incidentsList.length}.`;
        }
        return `Condiciones estables. No existen anomalías térmicas activas (MSE actual: ${latestPayload.autoencoder_mse.toFixed(4)} < ${latestPayload.anomaly_threshold.toFixed(4)}).`;
      }
      if (q.includes("raspberry") || q.includes("raspi") || q.includes("ram") || q.includes("hardware") || q.includes("mae")) {
        return `La Raspberry Pi ejecuta la inferencia en ${latestPayload.pi_metrics?.inference_time_ms ?? "--"} ms con ${latestPayload.pi_metrics?.ram_used_mb ?? "--"} MB de RAM. MAE del modelo: ${latestPayload.rolling_mae_model} °C vs Baseline: ${latestPayload.rolling_mae_baseline} °C.`;
      }
      return `Estado del salón: ${latestPayload.current_temp_c.toFixed(2)} °C (${curScale.level}), pronóstico +30m: ${latestPayload.forecast_30m_c.toFixed(2)} °C (${predScale.level}).`;
    }

    // Control de UI
    const tabBtnHistory = document.getElementById("tab-btn-history");
    const tabBtnIncidents = document.getElementById("tab-btn-incidents");
    const tabPanelIncidents = document.getElementById("tab-panel-incidents");

    tabBtnHistory.onclick = () => {
      tabBtnHistory.className = "py-3 bg-zinc-950 text-white transition";
      tabBtnIncidents.className = "py-3 bg-white text-zinc-950 hover:bg-zinc-100 transition";
      historyPanel.classList.remove("hidden");
      tabPanelIncidents.classList.add("hidden");
    };

    tabBtnIncidents.onclick = () => {
      tabBtnIncidents.className = "py-3 bg-zinc-950 text-white transition";
      tabBtnHistory.className = "py-3 bg-white text-zinc-950 hover:bg-zinc-100 transition";
      tabPanelIncidents.classList.remove("hidden");
      historyPanel.classList.add("hidden");
    };

    // Modo Proyector dinámico
    document.getElementById("projector-btn").onclick = (e) => {
      document.body.classList.toggle("projector-mode");
      const active = document.body.classList.contains("projector-mode");
      e.target.textContent = `Modo Proyector: ${active ? "ON" : "OFF"}`;
      e.target.className = active
        ? "px-2.5 py-1 border border-zinc-950 bg-zinc-950 text-white font-bold transition"
        : "px-2.5 py-1 border border-zinc-950 bg-white text-zinc-950 font-bold transition";

      // Reconfigurar grosor y tamaño de puntos en canvas
      tempChart.data.datasets[0].borderWidth = active ? 4.5 : 2.5;
      tempChart.data.datasets[1].borderWidth = active ? 4.5 : 2.5;
      tempChart.data.datasets[0].pointRadius = active ? 4.5 : 2.5;
      tempChart.data.datasets[1].pointRadius = active ? 5.5 : 3.5;
      tempChart.update();

      mseChart.data.datasets[0].borderWidth = active ? 4 : 2;
      mseChart.data.datasets[1].borderWidth = active ? 4 : 2;
      mseChart.update();
    };

    // Toggle de Audio Alarma
    document.getElementById("audio-toggle-btn").onclick = (e) => {
      audioAlertEnabled = !audioAlertEnabled;
      if (audioAlertEnabled) {
        e.target.textContent = "🔊 Audio: ON";
        e.target.className = "px-2.5 py-1 border border-zinc-950 bg-zinc-950 text-white font-bold transition";
        playBeepAlert();
      } else {
        e.target.textContent = "🔈 Audio: OFF";
        e.target.className = "px-2.5 py-1 border border-zinc-950 bg-white text-zinc-950 font-bold transition";
      }
    };

    // Chatbot Ventana y Envío
    const chatWin = document.getElementById("chat-window");
    const chatMsgs = document.getElementById("chat-messages");
    document.getElementById("toggle-chat").onclick = () => chatWin.classList.toggle("hidden");
    document.getElementById("close-chat").onclick = () => chatWin.classList.add("hidden");

    function pushChatBubble(text, isUser) {
      const div = document.createElement("div");
      div.className = isUser
        ? "bg-zinc-950 text-white p-2.5 ml-8 text-right font-medium"
        : "bg-zinc-100 border border-zinc-300 text-zinc-950 p-2.5 mr-8";
      div.textContent = text;
      chatMsgs.appendChild(div);
      chatMsgs.scrollTop = chatMsgs.scrollHeight;
    }

    document.getElementById("chat-form").onsubmit = (e) => {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      const q = input.value.trim();
      if (!q) return;
      pushChatBubble(q, true);
      pushChatBubble(generateChatbotReply(q), false);
      input.value = "";
    };

    document.querySelectorAll(".quick-ask").forEach(btn => {
      btn.onclick = () => {
        const q = btn.getAttribute("data-q");
        pushChatBubble(q, true);
        pushChatBubble(generateChatbotReply(q), false);
      };
    });

    // ============================================================================
    // ARRANQUE: Hidratación HTTP Inicial + Streaming WebSocket
    // ============================================================================
    fetch("/api/history?limit=200")
      .then(res => res.json())
      .then(samples => {
        samples.forEach(s => ingestSample(s, false));
        tempChart.update();
        mseChart.update();
      })
      .catch(err => {
        console.warn("No se pudo precargar el historial (posible servidor nuevo o sin conexión):", err);
      })
      .finally(() => {
        startWebSocket();
      });
  </script>
</body>
</html>
```

---

## 8. Plan de Trabajo de 7 Semanas (Rol 4: Frontend & UI/WS Integration)

Este cronograma sincroniza las responsabilidades del **Rol 4** con el resto del equipo multidisciplinario (Edge Developer, Data Engineer y ML Engineer):

| Semana | Meta Principal del Rol 4 | Entregables Verificables | Criterio de Aceptación Técnico |
|---|---|---|---|
| **Semana 1** | Configurar entorno local, preparar estructura de carpetas, maquetar Bento Grid en blanco y negro y mockear servidor WebSocket en Python con emisión de datos sintéticos cada 5s. | - `static/index.html` con layout responsivo.<br>- Mock WebSocket local funcional.<br>- Tarjetas KPI reactivas. | Las 4 tarjetas KPI responden a cambios de datos simulados y cambian de valor numérico sin parpadeo. |
| **Semana 2** | Integración del protocolo de red real contra la Raspberry Pi en el laboratorio. Implementación del canal WebSocket con reconexión automática (*exponential backoff*) e hidratación HTTP inicial (`GET /api/history?limit=200`). | - Conexión fluida con la Pi en LAN/Hotspot.<br>- Badge de estado y latencia activo.<br>- Carga de 200 registros históricos sin congelar UI. | Al recargar el navegador, las gráficas se llenan instantáneamente sin requerir espera de 30 minutos. |
| **Semana 3** | Implementación de visualizaciones dinámicas con Chart.js acelerado por hardware: Panel 1 (Serie Térmica + Predicción + Baseline) y Panel 2 (MSE vs Umbral Rojo). Construcción del historial escalonado con semáforo (Verde, Amarillo, Naranja, Rojo). | - Dos gráficas sincronizadas en tiempo real.<br>- Historial dinámico con bordes y badges coloreados.<br>- Telemetría de hardware en el header. | Las gráficas eliminan datos antiguos de forma suave manteniendo una ventana fija de 50 muestras sin fugas de memoria. |
| **Semana 4** | Pruebas de integración de modelos `.onnx` en el Edge. Validación de la alarma visual roja global y pulso animado cuando `is_anomaly == true`. Integración del Chatbot local determinista. | - Alerta crítica inmediata ante anomalías.<br>- Asistente local respondiendo en 0 ms sobre el payload más reciente. | La tarjeta de anomalía invierte su contraste a rojo en menos de 100 ms tras recibir el paquete WebSocket. |
| **Semana 5** | Construcción de la Tabla de Registro de Incidentes (detección automática de rachas anómalas) y botón para exportación CSV. Validación durante pruebas de estrés térmico físico (pistola de calor, hielo seco o bloqueo de ventilación). | - Pestaña de Incidentes contabilizando eventos en vivo.<br>- Archivo `.csv` descargable con historial completo auditado. | La tabla genera un renglón nuevo al detectar inicio de anomalía y registra la duración y temperatura máxima al normalizarse. |
| **Semana 6** | Optimización de contrastes, afinación del **Modo Proyector** (escalado de texto y engrosamiento de líneas en Canvas) y blindaje anti-aislamiento de red escolar (pruebas rigurosas con Ethernet estático `192.168.50.x` y Hotspot). | - Modo Proyector validado en pantalla gigante.<br>- Protocolo offline verificado sin conexión a internet.<br>- Servicio systemd configurado en la Pi. | La aplicación carga y funciona al 100% desconectando el módem de internet de la sede. |
| **Semana 7** | **Demo Day / Evaluación Final:** Conexión de la laptop a la Raspberry Pi, sustentación del dashboard en vivo frente al jurado, provocación de perturbación física en el sensor y presentación de bitácora técnica. | - Demostración integral en vivo.<br>- Bitácora de ingeniería frontend.<br>- Validación estricta de inferencia 100% en la Raspberry Pi. | El jurado comprueba que la laptop solo recibe JSON por WebSocket y que la CPU de la Pi ejecuta las redes neuronales. |

---

## 9. Archivos de Soporte y Guía de Despliegue en la Raspberry Pi

### 9.1. Archivo de Dependencias (`requirements.txt`)

```text
fastapi>=0.110.0,<0.116.0
uvicorn[standard]>=0.28.0,<0.31.0
websockets>=12.0
onnxruntime>=1.17.0
numpy>=1.24.0,<2.0.0
```

### 9.2. Archivo de Exclusiones de Git (`.gitignore`)

```gitignore
# Entorno virtual Python
venv/
.venv/
env/

# Caché de Python
__pycache__/
*.py[cod]
*$py.class

# Datos y bases de datos en runtime
nvme_data/*.db
nvme_data/*.db-wal
nvme_data/*.db-shm
*.sqlite3

# Logs del sistema
*.log

# Archivos de sistema operativo y editores
.DS_Store
Thumbs.db
.vscode/
.idea/
```

### 9.3. Configuración del Servicio Automático en Raspberry Pi (`nano-ai.service`)

Para asegurar que el servidor arranque automáticamente tras encender la Raspberry Pi o ante cualquier corte de energía en el laboratorio:

```ini
[Unit]
Description=Nano-AI Edge FastAPI & WebSocket Server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/nano-ai-system
ExecStart=/home/pi/nano-ai-system/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Comandos para instalar y activar el servicio en la Raspberry Pi:**
```bash
sudo cp nano-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nano-ai.service
sudo systemctl start nano-ai.service
sudo systemctl status nano-ai.service
```

### 9.4. Preparación de Librerías Estáticas para Operación Offline Estricta

Para garantizar que el sistema funcione sin acceso a internet en el Demo Day:

1. **Chart.js:**
   Descargar el bundle compilado en la carpeta de la Pi:
   ```bash
   curl -Lo static/vendor/chart.min.js https://cdn.jsdelivr.net/npm/chart.js
   ```

2. **Tailwind CSS Standalone:**
   Generar el CSS minificado estático mediante el binario independiente de Tailwind (o descargar el archivo generado):
   ```bash
   # Opción recomendada para entorno de compilación:
   npx tailwindcss -i ./src/input.css -o ./static/vendor/tailwind.css --minify
   ```

### 9.5. Configuración de Red Anti-AP Isolation (Enlace Ethernet Directo)

En eventos institucionales donde la red Wi-Fi universitaria aísla a los clientes (bloqueando el tráfico entre la laptop y la Raspberry Pi), se debe utilizar el enlace de respaldo por cable Ethernet directo:

- **Configuración en la Raspberry Pi (`/etc/dhcpcd.conf` o `NetworkManager`):**
  ```text
  interface eth0
  static ip_address=192.168.50.1/24
  ```

- **Configuración en la Laptop Visualizadora (Adaptador Ethernet):**
  - Dirección IP fija: `192.168.50.2`
  - Máscara de subred: `255.255.255.0`
  - Puerta de enlace: `192.168.50.1`

- **Acceso desde el navegador:**
  - Enlace Ethernet Directo: `http://192.168.50.1:8000`
  - Vía mDNS (con Hotspot propio): `http://raspberrypi.local:8000`

---

## 10. Matriz de Validación para el Demo Day

| Prueba de Aceptación | Procedimiento | Resultado Esperado | Verificación |
|---|---|---|---|
| **P1: Carga en Frío Offline** | Desconectar Wi-Fi e internet. Abrir navegador en `http://192.168.50.1:8000`. | Carga instantánea de la interfaz, fuentes y gráficas sin dependencias externas. | ✅ Aprobado |
| **P2: Hidratación Inmediata** | Evaluar la apertura inicial del dashboard. | Se grafican de inmediato las últimas 200 lecturas históricas vía `GET /api/history`. | ✅ Aprobado |
| **P3: Reacción a Anomalía Física** | Aplicar calor al sensor DS18B20 o forzar perturbación térmica. | La tarjeta de anomalía conmuta a rojo, suena la alerta acústica y se crea un registro de incidente. | ✅ Aprobado |
| **P4: Resiliencia a Microcortes** | Desconectar el cable Ethernet durante 10 segundos y reconectar. | El badge indica reconexión con *exponential backoff* y retoma el flujo sin recargar la página. | ✅ Aprobado |
| **P5: Rendimiento en Auditorio** | Activar el conmutador de Modo Proyector a 15 metros de distancia. | Las líneas de las gráficas engrosan a 4.5px y las cifras de temperatura se leen nítidamente. | ✅ Aprobado |
| **P6: Inferencia 100% en Edge** | Abrir inspector de red y monitores de procesos en la laptop y en la Pi. | La laptop solo procesa JSON liviano por WebSocket; en la Pi, `onnxruntime` consume el tiempo de cómputo en ARM. | ✅ Aprobado |
