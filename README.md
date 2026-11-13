# 🚀 Nano-AI: Sistema Híbrido de Predicción Térmica y Detección de Anomalías

> **Nodo Visualizador (Dashboard Local) y Servidor Embebido en Edge AI**
> Track 4: Lab Forecaster (`forecaster_real.onnx`, +30 min) | Track 3: Machine Anomaly Detector (`autoencoder_real.onnx`, $\theta = 0.6653$)

---

## 📌 1. Descripción del Proyecto y Modelos en Producción (KAN-18 / KAN-20)

**Nano-AI** es una plataforma de inteligencia artificial ejecutada 100% en el borde (**Edge AI** en Raspberry Pi 4GB ARM64 `aarch64` + NVMe SSD), diseñada para:
- **Captura 1-Wire en Tiempo Real:** Monitorear la temperatura ambiental mediante el sensor digital **DS18B20** en `GPIO 4` con detección de desconexión física (`DISCONNECTED`, `CRC_ERROR`, `READ_ERROR`, `HARDWARE_FAULT`).
- **Modelo 1 — Pronóstico Térmico a +30 min (`forecaster_real.onnx`):**
  - Arquitectura: Perceptrón Multicapa (MLP) $20 \rightarrow 32 \rightarrow 16 \rightarrow 1$ ($1,217$ parámetros, `float32`, `opset 17`).
  - Entrada (`[1, 20]`): 18 lecturas limpias $[T_{t-17}, \dots, T_t]$ + codificación cíclica horaria ($\text{hour\_sin}, \text{hour\_cos}$).
  - Validación Ciega en Día 4 (1,803 pares causales): $\text{MAE}_{\text{model}} = \mathbf{0.2903\ ^\circ\text{C}}$ vs. $\text{MAE}_{\text{baseline}} = \mathbf{0.6094\ ^\circ\text{C}}$ (**$+52.36\%$ de mejora**, $\Delta\text{MAE} = +0.3191\ ^\circ\text{C}$, $\text{RMSE} = 0.4571\ ^\circ\text{C}$, $R^2 = 0.9138$).
- **Modelo 2 — Detector de Anomalías (`autoencoder_real.onnx`):**
  - Arquitectura: Autoencoder simétrico $12 \rightarrow 8 \rightarrow 3 \rightarrow 8 \rightarrow 12$ ($271$ parámetros, *One-Class Normalcy Learning*).
  - Entrada (`[1, 12]`): 10 lecturas limpias $[T_{t-9}, \dots, T_t]$ + media móvil $\bar{T}_{10}$ + derivada inmediata $\Delta T$.
  - Umbral calibrado en producción (`anomaly_threshold`): **`0.6653`** ($1.19 \times P_{99}$ del Día 4, $F_1 = 0.8877$, **$0.00\%$ de falsos positivos** en $2,000$ ventanas normales).
  - Clasificación automática de `anomaly_type`: `"NINGUNA"`, `"ANOMALIA_CALOR"` ($\ge 23.1484\ ^\circ\text{C}$) y `"ANOMALIA_FRIO"` ($< 23.1484\ ^\circ\text{C}$).
- **Benchmark Hardware Edge:**
  - `ONNX Runtime 1.31.1` (`CPUExecutionProvider`, FP32): Latencia media total de **`0.2726 ms`** (`0.0927 ms` Regresor + `0.1799 ms` Autoencoder) y huella de RAM de **`~56 – 93 MB RSS`**.

---

## 🌐 2. Direcciones de Conexión del Nodo Edge y Contrato de API

El Dashboard (`static/index.html`) incluye un **Selector de Nodo Edge en vivo** en la barra superior que permite conectar o cambiar sin recargar entre los 3 entornos oficiales definidos en [`CONTRATO_API_E_INTEGRACION_FRONTEND.md`](file:///d:/CUATRI%209/Learn%20AI/Nano%20AI/CONTRATO_API_E_INTEGRACION_FRONTEND.md):

| Entorno de Conexión | HTTP Base URL | WebSocket Base URL | Uso Recomendado |
| :--- | :--- | :--- | :--- |
| **Red Local / Wi-Fi (mDNS Avahi)** | `http://nanoaitemp.local:8000` | `ws://nanoaitemp.local:8000/ws/stream` | Laptop y Raspberry Pi en la misma red local. |
| **Cable Ethernet Directo (`eth-directo`)** | `http://192.168.50.1:8000` | `ws://192.168.50.1:8000/ws/stream` | Demostración segura sin Wi-Fi (Anti-AP Isolation). |
| **Mismo Host / Túnel SSH Local** | `http://localhost:8000` | `ws://localhost:8000/ws/stream` | Pruebas locales o túnel SSH (`ssh -L 8000:localhost:8000 nanoai@nanoaitemp.local`). |

### Endpoints Implementados (100% Compatibles con Producción):
- **WebSockets en Tiempo Real:** `WS /ws`, `WS /ws/telemetry`, `WS /ws/stream` (envía inmediatamente `latest_state` en `onopen` y hace broadcast en cada ciclo).
- **Historial desde SQLite WAL:** `GET /api/history?limit=120` y `GET /history?limit=60` (devuelve `{ count, latest_state, history }`).
- **Estado y Diagnóstico Edge:** `GET /api/state`, `GET /health` y `GET /api/health` (devuelve `simulate_sensor`, `journal_mode: "wal"`, `db_path`, `ws_clients`, `latest_state`).
- **Simulador E2E KAN-20:** `POST /api/kan20/simulate?mode=ANOMALIA_CALOR|ANOMALIA_FRIO|DISCONNECTED|NORMAL`.

---

## 💻 3. Cómo Iniciar el Proyecto en tu Laptop

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
cd "d:\CUATRI 9\Learn AI\Nano AI"
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8500 --reload
```

Luego abre en tu navegador:
👉 **[http://localhost:8500](http://localhost:8500)**

> El puerto 8000 está siendo reenviado al backend de la Raspberry Pi (`Nano-AI Edge Server (R3)`) y el puerto 8080 está reservado por Windows (`WinError 10013`), por lo que el Dashboard local corre en el puerto **8500**.

---

## 🧪 4. Guía de Verificación End-to-End (Jira KAN-20)

Dentro del Dashboard encontrarás la **Consola de Verificación End-to-End (JIRA KAN-20)** con botones interactivos para validar todos los criterios de aceptación:

1. **🔥 Simular `ANOMALIA_CALOR` (`31.40 °C`, `MSE = 14.8321 > 0.6653`):**
   - Verifica la reacción visual inmediata (< 50 ms) cuando se recibe `"is_anomaly": true` y `"anomaly_type": "ANOMALIA_CALOR"`.
   - Se activa el banner crítico rojo pulsante, la tarjeta KPI 3 cambia a `¡ANOMALÍA CALOR!`, suena la alarma acústica (si `Audio: ON`) y se abre un nuevo registro en la pestaña **Incidentes**.
2. **❄️ Simular `ANOMALIA_FRIO` (`14.20 °C`, `MSE = 6.4190 > 0.6653`):**
   - Verifica la reacción ante choque térmico frío (`"anomaly_type": "ANOMALIA_FRIO"`, `"thermal_sensation": "Frío"`).
3. **🔌 Simular `Sensor DISCONNECTED` (`current_temp_c: null`):**
   - Verifica el blindaje del frontend cuando el sensor físico DS18B20 se desconecta en `GPIO 4`: muestra el banner de alerta de hardware sin romper las gráficas ni insertar valores `null`.
4. **🗄️ Auditar Respaldo SQLite WAL:**
   - Consulta en vivo `/api/state` y `/api/history` verificando que `journal_mode=WAL`, que todas las predicciones estén respaldadas en `clean_readings` y que no existan registros corruptos.
