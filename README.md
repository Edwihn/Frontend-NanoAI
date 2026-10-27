# 🚀 Nano-AI: Sistema Híbrido de Predicción Térmica y Detección de Anomalías

> **Nodo Visualizador (Dashboard Local) y Servidor Embebido en Edge AI**
> Track 4: Lab Forecaster (+30 min) | Track 3: Machine Anomaly Detector (Autoencoder)

---

## 📌 1. Descripción del Proyecto

**Nano-AI** es una plataforma de inteligencia artificial ejecutada en el borde (**Edge AI**), diseñada para:
- Monitorear en tiempo real la temperatura de un laboratorio mediante un sensor físico **DS18B20** conectado por bus 1-Wire (GPIO 4).
- Predecir el comportamiento térmico con **30 minutos de anticipación** mediante inferencia de red neuronal optimizada en ONNX Runtime.
- Detectar anomalías térmicas en tiempo real mediante un **Autoencoder** entrenado exclusivamente sobre condiciones normales.
- Visualizar telemetría de hardware, semáforo térmico escalonado de 4 niveles, curvas de pronóstico en Chart.js, auditoría de incidentes con exportación CSV y un chatbot asistente determinista de 0 ms.

---

## 📋 2. Reglas Inviolables de Operación

1. **Inferencia 100% en Edge (Raspberry Pi):** La laptop externa actúa exclusivamente como visor web; ejecutar inferencia en la laptop invalida los criterios de evaluación.
2. **Autonomía Offline Estricta:** El frontend (`static/index.html`) utiliza librerías empaquetadas localmente en `static/vendor/` (`chart.min.js` y `tailwind.css`), permitiendo operar sin conexión a internet en el Demo Day.
3. **Blindaje contra AP Isolation (Aislamiento Wi-Fi):** Conexión vía Hotspot personal o enlace directo por cable Ethernet con IPs fijas (`192.168.50.1` en la Pi y `192.168.50.2` en la Laptop).

---

## 🛠️ 3. Estructura de Archivos

```
Nano AI/
├── app/
│   ├── main.py                 # Servidor FastAPI, SQLite WAL, bucle async, API REST y WS
│   └── models/                 # Modelos ONNX y escaladores (regressor_30m.onnx, autoencoder.onnx, scaler.json)
├── nvme_data/
│   └── telemetry.db            # Base de datos SQLite persistente en modo WAL
├── static/
│   ├── index.html              # Dashboard SPA (Bento Grid B&W, Chart.js, Chatbot, Incidentes)
│   └── vendor/
│       ├── chart.min.js        # Chart.js local minificado (offline)
│       └── tailwind.css        # Tailwind CSS compilado local (offline)
├── nano-ai.service             # Unidad systemd para auto-arranque en Raspberry Pi
├── requirements.txt            # Dependencias fijadas de Python
├── PLANEACION.md               # Especificación técnica y arquitectura completa
├── ROADMAP_IMPLEMENTACION.md   # Registro de progreso y fases de ingeniería
└── README.md                   # Esta guía
```

---

## 💻 4. Instalación y Ejecución Local (Desarrollo y Pruebas)

### 4.1. Clonar o acceder a la carpeta del proyecto
```bash
cd "Nano AI"
```

### 4.2. Crear y activar el entorno virtual
```bash
# En Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1

# En Linux / Raspberry Pi OS:
python3 -m venv venv
source venv/bin/activate
```

### 4.3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4.4. Iniciar el servidor
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4.5. Acceder al Dashboard
Abre tu navegador en:
- `http://localhost:8000/` (o `http://127.0.0.1:8000/`)
- Diagnóstico del servidor: `http://localhost:8000/api/health`
- Historial en frío: `http://localhost:8000/api/history?limit=50`

---

## 🍓 5. Despliegue en la Raspberry Pi 4GB (Edge Node)

### 5.1. Copiar archivos a la Raspberry Pi
```bash
scp -r * pi@raspberrypi.local:/home/pi/nano-ai-system/
```

### 5.2. Habilitar el servicio systemd (Auto-arranque en arranque)
```bash
sudo cp nano-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nano-ai.service
sudo systemctl start nano-ai.service
sudo systemctl status nano-ai.service
```

### 5.3. Configuración de Red Anti-AP Isolation (Cable Ethernet Directo)
Si la red del auditorio bloquea la comunicación entre dispositivos:

1. **En la Raspberry Pi (`/etc/dhcpcd.conf` o NetworkManager):**
   ```text
   interface eth0
   static ip_address=192.168.50.1/24
   ```
2. **En la Laptop Visualizadora (Configuración de Red Ethernet):**
   - Dirección IP: `192.168.50.2`
   - Máscara de subred: `255.255.255.0`
   - Puerta de enlace: `192.168.50.1`
3. **Acceso desde el navegador:**
   - `http://192.168.50.1:8000` o `http://raspberrypi.local:8000`

---

## 🧪 6. Matriz de Validación para el Demo Day (P1 - P6)

| Prueba | Descripción | Validación Esperada |
|---|---|---|
| **P1** | **Carga Offline Total** | Desconectar internet; la web carga en 0 ms con estilos y lienzos Chart.js íntegros. |
| **P2** | **Hidratación Inmediata** | `GET /api/history?limit=200` puebla las gráficas y el historial al instante. |
| **P3** | **Reacción a Anomalía** | La tarjeta cambia a rojo pulsante, suena el pitido y se genera registro en incidentes. |
| **P4** | **Reconexión Resiliente** | Tras desconectar el cable de red, el badge entra en reconexión con *exponential backoff* y retoma el stream sin recargar. |
| **P5** | **Modo Proyector** | Las líneas de las gráficas engrosan a 4.5px y las cifras son legibles a 15 metros. |
| **P6** | **Inferencia en Edge** | Se comprueba que `onnxruntime` corre en la CPU ARM de la Pi y la laptop solo consume JSON. |
