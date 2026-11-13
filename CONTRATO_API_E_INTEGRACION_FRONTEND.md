# Guía de Integración y Contrato de API — Nano-AI Edge Backend → Frontend

> **Propósito de este documento:** Este archivo contiene toda la especificación técnica, URLs de conexión, contratos JSON (REST y WebSocket), estados de error, lógica de los modelos ONNX en producción y tipos TypeScript para que el asistente de IA del **Frontend** conecte la interfaz web con los datos reales generados por la **Raspberry Pi (Nodo Edge)**.

---

## 1. Arquitectura de Conexión y Direcciones del Servidor (Base URLs)

Toda la captura del sensor físico **DS18B20** y el **100% de la inferencia de IA** (pronóstico a $+30\text{ min}$ y detección de anomalías por Autoencoder) se ejecutan localmente en la **Raspberry Pi (`aarch64`)** dentro de un servidor **FastAPI + Uvicorn** en el **puerto `8000`** con **CORS totalmente habilitado (`allow_origins=["*"]`)**.

El Frontend **NO** debe ejecutar modelos ni normalizar datos; únicamente consume los endpoints HTTP REST (para carga inicial de historial/estado) y la conexión **WebSocket** (para actualizaciones en tiempo real en cada ciclo del bucle asíncrono).

### Direcciones de Red Disponibles

| Entorno de Conexión | HTTP Base URL | WebSocket Base URL | Cuándo usarlo |
| :--- | :--- | :--- | :--- |
| **Red Local / Wi-Fi (mDNS Avahi)** | `http://nanoaitemp.local:8000` | `ws://nanoaitemp.local:8000` | Conexión estándar cuando Laptop y Raspberry Pi están en la misma red local. |
| **Cable Ethernet Directo (Demo Segura)** | `http://192.168.50.1:8000` | `ws://192.168.50.1:8000` | Perfil `eth-directo` preconfigurado en `eth0` de la Raspberry Pi para demostraciones sin Wi-Fi. |
| **Mismo Host / Túnel SSH Local** | `http://localhost:8000` | `ws://localhost:8000` | Pruebas locales o reenvío de puertos por SSH (`ssh -L 8000:localhost:8000 nanoai@nanoaitemp.local`). |

> **Recomendación para el Frontend:** Centralizar la URL base en variables de entorno (por ejemplo, `VITE_API_BASE_URL=http://nanoaitemp.local:8000` y `VITE_WS_URL=ws://nanoaitemp.local:8000/ws/stream`) con opción de cambiarla dinámicamente o hacer fallback.

---

## 2. Resumen de Modelos de IA en Producción (Contexto del Backend)

El motor [`EdgeInferenceEngine`](file:///mnt/nvme/nano_ai/app/inference_engine.py) ejecuta dos modelos en formato **ONNX (`opset 17`, `float32`)** usando `CPUExecutionProvider` en ARM64 y los parámetros de estandarización de [`models/scaler_real.json`](file:///mnt/nvme/nano_ai/models/scaler_real.json):

### 2.1. Modelo 1: Pronóstico de Temperatura a $+30\text{ min}$ (`forecaster_real.onnx`)
- **Arquitectura:** Perceptrón Multicapa (MLP) de 3 capas ($20 \rightarrow 32 \rightarrow 16 \rightarrow 1$), $1,217$ parámetros.
- **Entrada (`sensor_window_and_time`, shape `[1, 20]`):**
  - Últimas **18 lecturas limpias** de temperatura en °C: $[T_{t-17}, T_{t-16}, \dots, T_t]$. *(Si la BD tiene menos de 18 lecturas al arrancar, aplica Cold-Start Padding repitiendo la primera lectura).*
  - Codificación cíclica de la hora actual ($h \in [0, 24)$): $\text{hour\_sin} = \sin(2\pi h / 24)$ y $\text{hour\_cos} = \cos(2\pi h / 24)$.
- **Salida des-normalizada:**
  - `forecast_30m_c`: Temperatura predicha en °C para dentro de **30 minutos**.
  - `baseline_30m_c`: Predicción del modelo ingenuo de persistencia ($\hat{T}_{t+30\text{m}} = T_t$, es decir, igual a `current_temp_c`).
- **Métricas Oficiales de Validación (KAN-18 - Día 4 Completo, 1,803 pares causales):**
  - $\text{MAE}_{\text{model}} = \mathbf{0.2903\ ^\circ\text{C}}$ vs. $\text{MAE}_{\text{baseline}} = \mathbf{0.6094\ ^\circ\text{C}}$ (**Ganancia del $+52.36\%$**, $\Delta\text{MAE} = +0.3191\ ^\circ\text{C}$).
  - $\text{RMSE}_{\text{model}} = 0.4571\ ^\circ\text{C}$, $R^2 = 0.9138$.

### 2.2. Modelo 2: Detección de Anomalías Térmicas (`autoencoder_real.onnx`)
- **Arquitectura:** Autoencoder simétrico ($12 \rightarrow 8 \rightarrow 3 \rightarrow 8 \rightarrow 12$), $271$ parámetros, entrenado exclusivamente con operación normal (*One-Class Normalcy Learning*).
- **Entrada (`normal_window_features`, shape `[1, 12]`):**
  - Últimas **10 lecturas limpias** en °C: $[T_{t-9}, \dots, T_t]$.
  - Media móvil de las 10 lecturas ($\bar{T}_{10}$) y derivada térmica inmediata ($\Delta T = T_t - T_{t-1}$).
- **Cálculo de Anomalía y Umbral Calibrado:**
  - Calcula el Error Cuadrático Medio de reconstrucción sobre el vector estandarizado (`autoencoder_mse`).
  - **Umbral calibrado en producción (`anomaly_threshold`):** **`0.6653`** (registrado en `scaler_real.json` como `0.6652797292399258`, redondeado a 4 decimales `0.6653`; calibrado a $1.19\times P_{99}$ del Día 4 con $0.00\%$ de falsos positivos en operación normal y $F_1 = 0.8877$).
  - **Regla de disparo:**
    - Si `autoencoder_mse > anomaly_threshold` $\Rightarrow$ `is_anomaly = true`.
    - Clasificación de `anomaly_type`:
      - `"ANOMALIA_CALOR"` si `is_anomaly == true` y `current_temp_c >= 23.1484` ($\mu_{\text{normal}}$).
      - `"ANOMALIA_FRIO"` si `is_anomaly == true` y `current_temp_c < 23.1484`.
      - `"NINGUNA"` si `is_anomaly == false`.

### 2.3. Clasificación de Sensación Térmica (`thermal_sensation`)
Calculada directamente sobre `current_temp_c`:
- `< 18.0 °C` $\rightarrow$ `"Frío"`
- `18.0 °C` a `26.0 °C` (inclusive) $\rightarrow$ `"Templado / Normal"`
- `> 26.0 °C` $\rightarrow$ `"Caluroso"`

---

## 3. Contrato Detallado de la API (REST + WebSockets)

### 3.1. WebSocket en Tiempo Real (Canal Principal del Dashboard)

El backend expone **tres rutas equivalentes** (puedes conectarte a cualquiera de las tres, hacen exactamente lo mismo):
- ` WS /ws `
- ` WS /ws/telemetry `
- ` WS /ws/stream `

#### Comportamiento del Ciclo de Vida del WebSocket:
1. **Al abrir la conexión (`onopen`):** Si el servidor ya tiene una lectura en memoria (`latest_state`), **envía inmediatamente un primer mensaje JSON** sin esperar al siguiente ciclo del sensor.
2. **Transmisión continua (`onmessage`):** En cada ciclo de lectura del sensor (configurable por `SAMPLE_INTERVAL_SEC`, típicamente cada **1 a 10 segundos**), el servidor hace `broadcast` automático del nuevo objeto JSON a todos los clientes conectados.
3. **Keep-alive:** El servidor mantiene un bucle `await ws.receive_text()`. El frontend no necesita enviar mensajes obligatoriamente para recibir el stream, pero puede enviar un `"ping"` de texto periódico si desea detectar desconexiones silenciosas.

#### Payload JSON del WebSocket — Caso Normal / Lectura Válida (`OK` o `SIMULATED_OK`):
```json
{
  "timestamp": "2026-11-05T18:31:17",
  "sensor_status": "OK",
  "current_temp_c": 22.25,
  "thermal_sensation": "Templado / Normal",
  "forecast_30m_c": 21.91,
  "baseline_30m_c": 22.25,
  "rolling_mae_model": 0.0,
  "rolling_mae_baseline": 0.0,
  "autoencoder_mse": 0.0194,
  "anomaly_threshold": 0.6653,
  "is_anomaly": false,
  "anomaly_type": "NINGUNA",
  "pi_metrics": {
    "inference_time_ms": 1.211,
    "ram_used_mb": 92.9
  }
}
```

#### Payload JSON del WebSocket — Caso de Anomalía Detectada:
```json
{
  "timestamp": "2026-11-05T18:40:10",
  "sensor_status": "OK",
  "current_temp_c": 31.40,
  "thermal_sensation": "Caluroso",
  "forecast_30m_c": 26.85,
  "baseline_30m_c": 31.40,
  "rolling_mae_model": 0.0,
  "rolling_mae_baseline": 0.0,
  "autoencoder_mse": 14.8321,
  "anomaly_threshold": 0.6653,
  "is_anomaly": true,
  "anomaly_type": "ANOMALIA_CALOR",
  "pi_metrics": {
    "inference_time_ms": 0.612,
    "ram_used_mb": 93.1
  }
}
```

#### Payload JSON del WebSocket — Caso de Fallo Físico del Sensor (`DISCONNECTED`, `CRC_ERROR`, `READ_ERROR`, `HARDWARE_FAULT`):
> **¡MUY IMPORTANTE PARA EL FRONTEND!** Si el cable del sensor DS18B20 se desconecta o falla el CRC cuando `SIMULATE_SENSOR=0`, el servidor envía un **objeto reducido** donde `current_temp_c` es `null` y **no vienen las llaves de inferencia**. El frontend debe validar `data.current_temp_c !== null` antes de renderizar métricas o gráficas:
```json
{
  "timestamp": "2026-11-05T18:45:00",
  "sensor_status": "DISCONNECTED",
  "current_temp_c": null
}
```

---

### 3.2. Endpoint REST: Historial de Lecturas Limpias

Rutas equivalentes:
- `GET /api/history?limit=60`
- `GET /history?limit=60`

#### Parámetros Query:
| Parámetro | Tipo | Default | Rango Permitido | Descripción |
| :--- | :---: | :---: | :---: | :--- |
| `limit` | `int` | `60` | `1` a `1000` | Cantidad de lecturas históricas más recientes a devolver (ordenadas cronológicamente de más antigua a más reciente). |

#### Respuesta Exitosa (`200 OK`):
> **Diferencia clave en `history[]` vs `latest_state`:** Los elementos dentro del arreglo `history` provienen directamente de la tabla SQLite `clean_readings`, por lo que:
> 1. Incluyen el campo `id` (entero autoincremental).
> 2. `is_anomaly` viene como entero SQLite (`0` o `1`) en lugar de booleano (`false`/`true`). En el frontend conviene evaluar `Boolean(item.is_anomaly)`.
> 3. `inference_time_ms` y `ram_used_mb` vienen en el **nivel raíz** de cada fila de `history`, mientras que en `latest_state` (y en el WebSocket) vienen anidados dentro del objeto `pi_metrics: { inference_time_ms, ram_used_mb }`.

```json
{
  "count": 2,
  "latest_state": {
    "timestamp": "2026-11-05T18:31:17",
    "sensor_status": "OK",
    "current_temp_c": 22.25,
    "thermal_sensation": "Templado / Normal",
    "forecast_30m_c": 21.91,
    "baseline_30m_c": 22.25,
    "rolling_mae_model": 0.0,
    "rolling_mae_baseline": 0.0,
    "autoencoder_mse": 0.0194,
    "anomaly_threshold": 0.6653,
    "is_anomaly": false,
    "anomaly_type": "NINGUNA",
    "pi_metrics": {
      "inference_time_ms": 1.211,
      "ram_used_mb": 92.9
    }
  },
  "history": [
    {
      "id": 101,
      "timestamp": "2026-11-05T18:31:07",
      "current_temp_c": 22.20,
      "thermal_sensation": "Templado / Normal",
      "forecast_30m_c": 21.88,
      "baseline_30m_c": 22.20,
      "rolling_mae_model": 0.0,
      "rolling_mae_baseline": 0.0,
      "autoencoder_mse": 0.0181,
      "anomaly_threshold": 0.6653,
      "is_anomaly": 0,
      "anomaly_type": "NINGUNA",
      "inference_time_ms": 0.985,
      "ram_used_mb": 92.9
    },
    {
      "id": 102,
      "timestamp": "2026-11-05T18:31:17",
      "current_temp_c": 22.25,
      "thermal_sensation": "Templado / Normal",
      "forecast_30m_c": 21.91,
      "baseline_30m_c": 22.25,
      "rolling_mae_model": 0.0,
      "rolling_mae_baseline": 0.0,
      "autoencoder_mse": 0.0194,
      "anomaly_threshold": 0.6653,
      "is_anomaly": 0,
      "anomaly_type": "NINGUNA",
      "inference_time_ms": 1.211,
      "ram_used_mb": 92.9
    }
  ]
}
```

---

### 3.3. Endpoint REST: Estado del Sistema y Diagnóstico Edge

Rutas equivalentes:
- `GET /api/state`
- `GET /health`

#### Respuesta Exitosa (`200 OK`):
Útil para mostrar en el header/footer del Dashboard si el sistema está conectado en modo **Sensor Físico Real (`simulate_sensor: false`)** o **Modo Simulado (`simulate_sensor: true`)**, el modo `wal` de SQLite y cuántos clientes WebSocket están activos.

```json
{
  "status": "ok",
  "simulate_sensor": false,
  "journal_mode": "wal",
  "db_path": "/mnt/nvme/nano_ai/data/telemetry.db",
  "ws_clients": 1,
  "latest_state": {
    "timestamp": "2026-11-05T18:31:17",
    "sensor_status": "OK",
    "current_temp_c": 22.25,
    "thermal_sensation": "Templado / Normal",
    "forecast_30m_c": 21.91,
    "baseline_30m_c": 22.25,
    "rolling_mae_model": 0.0,
    "rolling_mae_baseline": 0.0,
    "autoencoder_mse": 0.0194,
    "anomaly_threshold": 0.6653,
    "is_anomaly": false,
    "anomaly_type": "NINGUNA",
    "pi_metrics": {
      "inference_time_ms": 1.211,
      "ram_used_mb": 92.9
    }
  }
}
```

---

## 4. Diccionario Completo de Campos y Valores Posibles

| Campo | Tipo | Unidad / Valores Posibles | Descripción para la UI |
| :--- | :---: | :--- | :--- |
| `timestamp` | `string` | ISO 8601 (`"YYYY-MM-DDTHH:MM:SS"`) | Hora local de la lectura en la Raspberry Pi. |
| `sensor_status` | `string` | `"OK"` \| `"SIMULATED_OK"` \| `"DISCONNECTED"` \| `"CRC_ERROR"` \| `"READ_ERROR"` \| `"HARDWARE_FAULT"` | Estado del bus 1-Wire (`GPIO 4`). `"OK"` = Sensor físico DS18B20 real; `"SIMULATED_OK"` = Simulador sinusoidal activo. Cualquier otro valor indica error físico. |
| `current_temp_c` | `number \| null` | Grados Celsius (`°C`, 2 decimales) | Temperatura actual del cuarto. Es `null` si `sensor_status` es un error. |
| `thermal_sensation` | `string` | `"Frío"` \| `"Templado / Normal"` \| `"Caluroso"` | Clasificación ambiental para badges o cambio de color de tema. |
| `forecast_30m_c` | `number` | Grados Celsius (`°C`, 2 decimales) | **Predicción a +30 minutos** generada por la red neuronal `forecaster_real.onnx`. |
| `baseline_30m_c` | `number` | Grados Celsius (`°C`, 2 decimales) | Predicción base de persistencia ($T_t$) para comparar contra el modelo IA. |
| `autoencoder_mse` | `number` | Adimensional (4 decimales, ej. `0.0194`) | Error cuadrático medio de reconstrucción del Autoencoder (`autoencoder_real.onnx`). En operación normal suele estar entre `0.0005` y `0.5500`; en anomalías sube de `0.67` hasta `>2000`. |
| `anomaly_threshold` | `number` | `0.6653` | Umbral crítico calibrado ($\theta_{\text{AE}}$). Graficar como una línea horizontal punteada roja en la gráfica de MSE. |
| `is_anomaly` | `boolean` (WS) / `0\|1` (DB) | `true` / `false` (`1` / `0` en `/api/history`) | Indica si `autoencoder_mse > anomaly_threshold`. Cuando es `true`, activar alerta visual/sonora en el frontend. |
| `anomaly_type` | `string` | `"NINGUNA"` \| `"ANOMALIA_CALOR"` \| `"ANOMALIA_FRIO"` | Tipo específico de anomalía detectada para mostrar en el banner de alerta. |
| `pi_metrics.inference_time_ms` | `number` | Milisegundos (`ms`, 3 decimales, ej. `0.298` – `1.250`) | Tiempo real que tardó la CPU ARM64 de la Raspberry Pi en correr ambos modelos ONNX. |
| `pi_metrics.ram_used_mb` | `number` | Megabytes (`MB`, 1 decimal, ej. `92.9`) | Memoria RAM RSS consumida por el proceso del servidor en la Raspberry Pi. |

---

## 5. Interfaces TypeScript Listas para Copiar en el Frontend

```typescript
export type SensorStatus =
  | "OK"
  | "SIMULATED_OK"
  | "DISCONNECTED"
  | "CRC_ERROR"
  | "READ_ERROR"
  | "HARDWARE_FAULT";

export type ThermalSensation = "Frío" | "Templado / Normal" | "Caluroso";

export type AnomalyType = "NINGUNA" | "ANOMALIA_CALOR" | "ANOMALIA_FRIO";

export interface PiMetrics {
  inference_time_ms: number;
  ram_used_mb: number;
}

/** Estado completo cuando la lectura del sensor es válida (OK o SIMULATED_OK) */
export interface TelemetryReading {
  timestamp: string;
  sensor_status: "OK" | "SIMULATED_OK";
  current_temp_c: number;
  thermal_sensation: ThermalSensation;
  forecast_30m_c: number;
  baseline_30m_c: number;
  rolling_mae_model: number;
  rolling_mae_baseline: number;
  autoencoder_mse: number;
  anomaly_threshold: number;
  is_anomaly: boolean;
  anomaly_type: AnomalyType;
  pi_metrics: PiMetrics;
}

/** Estado reducido cuando el sensor físico falla o se desconecta */
export interface TelemetrySensorError {
  timestamp: string;
  sensor_status: Exclude<SensorStatus, "OK" | "SIMULATED_OK">;
  current_temp_c: null;
}

export type WebSocketPayload = TelemetryReading | TelemetrySensorError;

/** Fila devuelta dentro del arreglo history[] en GET /api/history */
export interface CleanReadingRow {
  id: number;
  timestamp: string;
  current_temp_c: number;
  thermal_sensation: ThermalSensation;
  forecast_30m_c: number;
  baseline_30m_c: number;
  rolling_mae_model: number;
  rolling_mae_baseline: number;
  autoencoder_mse: number;
  anomaly_threshold: number;
  is_anomaly: number | boolean; // 0 o 1 desde SQLite
  anomaly_type: AnomalyType;
  inference_time_ms: number;
  ram_used_mb: number;
}

export interface HistoryResponse {
  count: number;
  latest_state: WebSocketPayload | Record<string, never>;
  history: CleanReadingRow[];
}

export interface SystemStateResponse {
  status: "ok";
  simulate_sensor: boolean;
  journal_mode: string;
  db_path: string;
  ws_clients: number;
  latest_state: WebSocketPayload | Record<string, never>;
}
```

---

## 6. Flujo Recomendado de Conexión en el Frontend (Paso a Paso)

Para que la interfaz cargue instantáneamente con gráficas pobladas y se actualice sola en tiempo real:

### Paso 1: Carga Inicial (Hidratación de Gráficas y Estado del Sistema)
Al montar la aplicación (`useEffect` inicial o `onMount`):
1. Hacer `GET ${API_BASE}/api/history?limit=120` para obtener las últimas 120 lecturas históricas y poblar la gráfica de serie de tiempo (`current_temp_c` vs `forecast_30m_c`) y la gráfica del Autoencoder (`autoencoder_mse` vs `anomaly_threshold`).
2. Normalizar cada elemento `row` de `history` usando una función adaptadora para unificar la estructura con la del WebSocket:
   ```typescript
   function normalizeHistoryRow(row: CleanReadingRow): TelemetryReading {
     return {
       timestamp: row.timestamp,
       sensor_status: "OK",
       current_temp_c: row.current_temp_c,
       thermal_sensation: row.thermal_sensation,
       forecast_30m_c: row.forecast_30m_c,
       baseline_30m_c: row.baseline_30m_c,
       rolling_mae_model: row.rolling_mae_model,
       rolling_mae_baseline: row.rolling_mae_baseline,
       autoencoder_mse: row.autoencoder_mse,
       anomaly_threshold: row.anomaly_threshold,
       is_anomaly: Boolean(row.is_anomaly),
       anomaly_type: row.anomaly_type,
       pi_metrics: {
         inference_time_ms: row.inference_time_ms,
         ram_used_mb: row.ram_used_mb,
       },
     };
   }
   ```
3. (Opcional) Hacer `GET ${API_BASE}/api/state` para conocer `simulate_sensor`, `journal_mode` y `ws_clients`.

### Paso 2: Suscripción en Tiempo Real vía WebSocket con Reconexión Automática
1. Conectar a `ws://<HOST>:8000/ws/stream` (o `/ws`).
2. En cada evento `onmessage`:
   - Parsear `const data: WebSocketPayload = JSON.parse(event.data)`.
   - **Verificar si es un error de hardware:**
     ```typescript
     if (data.current_temp_c === null) {
       // Mostrar banner de alerta de hardware: data.sensor_status (ej. "DISCONNECTED" o "CRC_ERROR")
       // NO agregar punto nulo a las gráficas de inferencia
       return;
     }
     ```
   - **Si la lectura es válida (`data.current_temp_c !== null`):**
     - Actualizar las tarjetas principales:
       - Temperatura actual: `data.current_temp_c` °C y tendencia `data.forecast_30m_c - data.current_temp_c` °C.
       - Predicción a +30 min: `data.forecast_30m_c` °C (comparada contra `data.baseline_30m_c` °C).
       - Sensación térmica: `data.thermal_sensation`.
       - Estado de anomalía: si `data.is_anomaly === true`, resaltar alerta con `data.anomaly_type` (`"ANOMALIA_CALOR"` o `"ANOMALIA_FRIO"`) y mostrar `data.autoencoder_mse` frente al umbral `data.anomaly_threshold` (`0.6653`).
       - Telemetría de la Raspberry Pi: `data.pi_metrics.inference_time_ms` ms y `data.pi_metrics.ram_used_mb` MB.
     - Agregar el nuevo punto al final del arreglo del historial (evitando duplicados si el `timestamp` del primer mensaje al conectar ya venía en `/api/history`) y mantener una ventana deslizante (por ejemplo, últimos 120 puntos: `prev.slice(-119).concat(data)`).
3. En `onclose` / `onerror`, programar reconexión automática con backoff (ej. reintentar cada 3 segundos) e indicar en la UI el estado de la conexión WebSocket (`Conectado en vivo` / `Reconectando...`).

---

## 7. Métricas Estáticas del Modelo para Mostrar en Tarjetas Informativas (Opcional en UI)

Si el frontend tiene una sección de **"Ficha Técnica del Modelo / Evaluación KAN-18"**, estos son los valores reales auditados en [`models/scaler_real.json`](file:///mnt/nvme/nano_ai/models/scaler_real.json) y [`data/kan18_evaluation_results.json`](file:///mnt/nvme/nano_ai/data/kan18_evaluation_results.json):

- **Hardware Edge:** Raspberry Pi ARM64 (`aarch64`) + NVMe SSD (`SQLite WAL`) + Sensor digital 1-Wire `DS18B20`.
- **Motor de Inferencia:** `ONNX Runtime 1.31.1` (`CPUExecutionProvider`, FP32).
- **Latencia Media de Inferencia (Benchmark 1,000 iteraciones):** `0.2726 ms` (`0.0927 ms` Regresor + `0.1799 ms` Autoencoder).
- **Huella de RAM del Daemon Completo:** `~56 – 93 MB RSS`.
- **Desempeño del Regresor (+30 min) en Día 4 (Validación Ciega):**
  - `MAE Modelo ONNX`: **`0.2903 °C`**
  - `MAE Baseline Persistencia`: **`0.6094 °C`**
  - `Mejora sobre Baseline`: **`+52.36%`** ($\Delta\text{MAE} = 0.3191\ ^\circ\text{C}$)
  - `R² Score`: **`0.9138`**
- **Desempeño del Autoencoder de Anomalías:**
  - `Umbral Calibrado (anomaly_threshold)`: **`0.6653`** ($1.19\times P_{99}$)
  - `F1-Score`: **`0.8877`**
  - `Falsos Positivos en Operación Normal (Día 4)`: **`0.00% (0 / 2,000 ventanas)`**

