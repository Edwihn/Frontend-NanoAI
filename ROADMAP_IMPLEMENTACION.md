# 🗺️ Roadmap de Implementación Fase por Fase: Proyecto Nano-AI

Este documento desglosa la [PLANEACION.md](file:///d:/CUATRI%209/Learn%20AI/Nano%20AI/PLANEACION.md) en **8 fases secuenciales e incrementales**. Cada fase está diseñada para ser autocontenida, verificable y ejecutable paso a paso, asegurando que cada componente funcione antes de pasar al siguiente.

---

## 📊 Matriz de Fases y Progreso

| Fase | Nombre | Objetivo Principal | Estado |
|---|---|---|:---:|
| **Fase 0** | Entorno y Estructura Base | Preparar carpetas, gitignore, requirements y librerías estáticas offline | `[x] Completada` |
| **Fase 1** | Persistencia y Endpoints Base | SQLite WAL, precarga de datos, `GET /api/history` y `GET /api/health` | `[x] Completada` |
| **Fase 2** | Streaming de Telemetría (WebSocket) | Bucle de muestreo async a 10s y canal `ws://.../ws/stream` | `[x] Completada` |
| **Fase 3** | Frontend Base y Bento Grid KPI | Layout B&W, conexión WS con exponential backoff y 4 tarjetas KPI reactivas | `[x] Completada` |
| **Fase 4** | Gráficas en Vivo y Semáforo Térmico | Serie Térmica (+30m, baseline) y MSE vs Umbral en Chart.js | `[x] Completada` |
| **Fase 5** | Historial, Incidentes y Exportación | Pestañas de historial escalonado, tabla de incidentes y descarga CSV | `[x] Completada` |
| **Fase 6** | Chatbot Deterministico y Modo Proyector | Asistente en cliente (0 ms), quick asks, audio alarma y modo auditorio | `[x] Completada` |
| **Fase 7** | Despliegue en Edge y Validación Demo Day | Systemd service, IP estática anti-AP isolation y batería de pruebas P1-P6 | `[x] Completada` |

---

## 🛠️ Detalle de Cada Fase de Implementación

---

### 🔹 Fase 0: Preparación de Entorno y Estructura Base

#### 🎯 Objetivo
Configurar el andamiaje del proyecto, aislar dependencias con entorno virtual y disponer de las librerías frontend locales para garantizar funcionamiento sin conexión a internet.

#### 📋 Tareas Específicas
- [x] Crear la estructura completa de directorios del proyecto:
  ```
  app/
  app/models/
  nvme_data/
  static/
  static/vendor/
  ```
- [x] Crear el archivo `.gitignore` con exclusiones de entornos, cachés y bases de datos runtime.
- [x] Crear el archivo `requirements.txt` con las versiones fijadas de FastAPI, Uvicorn, WebSockets y ONNX Runtime.
- [x] Descargar o configurar `static/vendor/chart.min.js` y `static/vendor/tailwind.css` para cumplir con la regla de operación offline.

#### 🧪 Criterio de Verificación
- La estructura de carpetas existe.
- Las dependencias se pueden instalar en un entorno virtual (`pip install -r requirements.txt`).
- `static/vendor/` contiene los archivos de soporte gráfico y de estilos.

---

### 🔹 Fase 1: Persistencia y Endpoints Base (FastAPI + SQLite WAL)

#### 🎯 Objetivo
Construir el backend central con SQLite en modo WAL sobre el SSD NVMe, permitiendo lectura/escritura concurrente sin bloqueos y sirviendo los endpoints REST fundamentales.

#### 📋 Tareas Específicas
- [x] Crear `app/main.py` con:
  - Inicialización de la base de datos `nvme_data/telemetry.db` con `PRAGMA journal_mode=WAL;`.
  - Creación de tabla `clean_readings` con índices para `timestamp`.
  - Lógica de precarga automática de 50 muestras sintéticas si la base está vacía.
  - Endpoint `GET /api/history?limit=200` para hidratación en frío.
  - Endpoint `GET /api/health` para telemetría del servidor y del sistema de almacenamiento.
  - Montaje de archivos estáticos en `/static`.
  - Ruta raíz `GET /` que sirva `static/index.html`.

#### 🧪 Criterio de Verificación
- Iniciar el servidor: `uvicorn app.main:app --port 8000`.
- Comprobar con navegador o `curl`:
  - `http://localhost:8000/api/health` devuelve estado `HEALTHY`.
  - `http://localhost:8000/api/history?limit=10` devuelve una lista JSON con las últimas lecturas.
  - La base `nvme_data/telemetry.db` genera los archivos `-wal` y `-shm`.

---

### 🔹 Fase 2: Canal de Streaming en Tiempo Real (WebSocket Push)

#### 🎯 Objetivo
Habilitar la comunicación full-duplex continua cada 10-15 segundos desde el servidor hacia los clientes conectados, encapsulando inferencia simulada y telemetría de hardware.

#### 📋 Tareas Específicas
- [x] Implementar el endpoint WebSocket `/ws/stream` en `app/main.py`.
- [x] Registrar y gestionar la lista de clientes conectados (`connected_clients`), limpiando desconexiones limpias o abruptas.
- [x] Implementar la función de fondo `edge_sampling_loop()` gestionada en el `lifespan` de FastAPI:
  - Generador de lecturas físicas / simuladas con onda sinusoidal para recorrer los 4 niveles del semáforo.
  - Cálculo de `current_temp_c`, `forecast_30m_c`, `baseline_30m_c`, `rolling_mae_model`, `autoencoder_mse`, `anomaly_threshold` e `is_anomaly`.
  - Registro de métricas de la Pi (`inference_time_ms`, `ram_used_mb`).
  - Escritura segura en SQLite protegida por `asyncio.Lock`.
  - Emisión (*broadcast*) del contrato JSON cada 10 segundos.

#### 🧪 Criterio de Verificación
- Conectar un cliente WebSocket de prueba o script Python.
- Verificar la recepción continua de paquetes JSON válidos cada 10 segundos.
- Confirmar que las lecturas se van persistiendo en la tabla `clean_readings`.

---

### 🔹 Fase 3: Frontend Base y Bento Grid de Tarjetas KPI

#### 🎯 Objetivo
Construir la estructura visual HTML5 en blanco y negro, el encabezado de estado y las 4 tarjetas KPI con reactividad en vivo y reconexión automática resiliente.

#### 📋 Tareas Específicas
- [x] Crear `static/index.html` con layout responsivo (móvil, tablet, desktop).
- [x] Construir la `HeaderBar`:
  - Logotipo NANO-AI y subtítulos de tracks.
  - Badges de estado: Conexión WS con latencia, estado del sensor y telemetría de hardware (RAM / ms).
- [x] Construir el Bento Grid con las 4 tarjetas KPI:
  - **KPI 1:** Temperatura actual con tipografía extra grande, badge del semáforo y flecha de tendencia (`↑`, `↓`, `→`).
  - **KPI 2:** Predicción a +30 minutos, diferencial $\Delta$ y valor baseline.
  - **KPI 3:** Estado del Autoencoder (Normal vs Inversión a fondo rojo con pulso si `is_anomaly == true`).
  - **KPI 4:** Comparativa en vivo de Rolling MAE vs Baseline con porcentaje de ganancia.
- [x] Implementar módulo de conexión WebSocket en JavaScript:
  - Algoritmo de reconexión con *exponential backoff* y *jitter* (1s a 15s).
  - Función `ingestSample()` para actualizar reactivamente los valores y colores de las tarjetas.

#### 🧪 Criterio de Verificación
- Abrir `http://localhost:8000/` en el navegador.
- El badge WS muestra "Conectado" en color verde y la latencia.
- Las 4 tarjetas KPI se actualizan automáticamente cada 10 segundos con valores coherentes.
- Simular desconexión deteniendo Uvicorn: el badge pasa a color ámbar mostrando el conteo de reintentos.

---

### 🔹 Fase 4: Gráficas en Tiempo Real y Semáforo Térmico Escalonado

#### 🎯 Objetivo
Integrar las dos visualizaciones continuas con Chart.js acelerado por hardware y codificar la lógica estricta del semáforo térmico de 4 niveles.

#### 📋 Tareas Específicas
- [x] Implementar función `getThermalScale(temp, isAnomaly)` con los 4 niveles:
  - Verde (`IDEAL`, < 24.0°C)
  - Amarillo (`PRECAUCIÓN`, 24.0°C - 25.4°C)
  - Naranja (`ALERTA`, 25.5°C - 27.4°C)
  - Rojo (`CRÍTICA`, ≥ 27.5°C o `is_anomaly == true`)
- [x] Configurar **Gráfica 1 (Panel 1):**
  - Serie 1: Temperatura real (Línea negra sólida).
  - Serie 2: Predicción a 30m (Línea punteada naranja con puntos cromáticos según el semáforo).
  - Serie 3: Baseline (Línea gris tenue).
- [x] Configurar **Gráfica 2 (Panel 2):**
  - Serie 1: Autoencoder MSE (Línea negra con sombreado de área suave).
  - Serie 2: Umbral de anomalía (Línea roja horizontal constante).
- [x] Implementar la hidratación en frío inicial:
  - Petición `fetch("/api/history?limit=200")` al arrancar.
  - Población inmediata de las gráficas sin esperar nuevos ticks del sensor.
- [x] Manejo de ventana deslizante fija (50 muestras) en Chart.js para evitar degradación de memoria.

#### 🧪 Criterio de Verificación
- Al recargar la página, ambas gráficas se dibujan completas al instante con datos del historial.
- Cada nuevo paquete recibido añade un punto a la derecha y retira el más antiguo suavemente.
- Los puntos de predicción cambian de color según el rango térmico calculado.

---

### 🔹 Fase 5: Historial Escalonado, Detección de Incidentes y Exportación CSV

#### 🎯 Objetivo
Desarrollar la columna lateral con panel de pestañas para auditar el historial cromático de temperaturas, detectar automáticamente rachas de anomalías y permitir descarga de reportes.

#### 📋 Tareas Específicas
- [x] Implementar el sistema de pestañas B&W (Pestaña Historial vs Pestaña Incidentes).
- [x] Pestaña 1 - Historial Escalonado:
  - Renderizado cronológico inverso de las últimas 200 lecturas.
  - Borde lateral izquierdo (`border-l-4`) y badge con el color del semáforo térmico.
- [x] Pestaña 2 - Registro Autónomo de Incidentes:
  - Detección de transiciones: inicio cuando `is_anomaly == true` y cierre cuando se normaliza.
  - Registro de Hora Inicio, Hora Fin (o "En curso"), Temp Máxima y MSE Máximo.
  - Contador reactivo de incidentes en el título de la pestaña.
- [x] Botón de **Exportación a CSV**:
  - Función en JavaScript para serializar el arreglo de 200 lecturas en formato CSV descargable con nombre timestamped.
- [x] Generador de **Alerta Sonora** nativo:
  - Sintetizador con Web Audio API (onda senoidal a 880 Hz durante 350 ms).
  - Botón de conmutación en el header: `Audio: ON / OFF`.

#### 🧪 Criterio de Verificación
- El historial acumula hasta 200 filas con sus respectivos colores.
- Al activarse una anomalía, se crea automáticamente una fila en la tabla de incidentes y suena el pitido (si audio está en ON).
- Al hacer clic en "Descargar CSV", el navegador descarga un archivo `.csv` con todas las columnas del contrato JSON.

---

### 🔹 Fase 6: Chatbot Asistente Determinista y Modo Proyector

#### 🎯 Objetivo
Integrar el asistente conversacional interactivo ejecutado 100% en el navegador y el conmutador de alto contraste para presentaciones en auditorio.

#### 📋 Tareas Específicas
- [x] Crear la ventana emergente flotante del Chatbot:
  - Encabezado B&W con botón de cierre.
  - Contenedor de burbujas con scroll automático.
  - Barra de chips rápidos (*Quick Asks*).
  - Campo de entrada de texto y botón enviar.
  - Botón flotante en la esquina inferior derecha con indicador luminoso de alerta crítica.
- [x] Implementar el motor conversacional determinista `generateChatbotReply(query)`:
  - Consultas de temperatura actual y estado del sensor.
  - Consultas de tendencia y predicción a 30 minutos.
  - Consultas de detección de anomalías y conteo de incidentes.
  - Consultas de telemetría de hardware de la Raspberry Pi.
- [x] Implementar el **Modo Proyector**:
  - Clase CSS `.projector-mode` que incrementa escala tipográfica al 112% y bordes a 3px.
  - Reconfiguración dinámica de Chart.js al alternar el botón:
    - Grosor de líneas aumentado a 4.5px.
    - Radio de puntos aumentado a 4.5px / 5.5px.

#### 🧪 Criterio de Verificación
- Abrir el chat y enviar consultas libres y con los botones rápidos; la respuesta es instantánea (0 ms).
- Si hay anomalía activa, el botón del chat parpadea en rojo.
- Al presionar "Modo Proyector: ON", toda la interfaz y las dos gráficas aumentan su grosor y tamaño de texto de forma visible.

---

### 🔹 Fase 7: Despliegue en Edge (Raspberry Pi) y Validación Demo Day

#### 🎯 Objetivo
Configurar el entorno físico en la Raspberry Pi 4GB con SSD NVMe, habilitar el auto-arranque desatendido y validar la batería completa de pruebas anti-fallos.

#### 📋 Tareas Específicas
- [x] Configurar el archivo de servicio `nano-ai.service` en `/etc/systemd/system/` y habilitarlo para auto-arranque al encender la Pi.
- [x] Configurar la interfaz Ethernet fija (`192.168.50.1/24`) y mDNS (`raspberrypi.local`).
- [x] Configurar la IP estática en la laptop (`192.168.50.2/24`).
- [x] Descargar los binarios offline a `static/vendor/` en la Pi.
- [x] Ejecutar la matriz de validación de 6 pruebas de aceptación:
  - **P1:** Arranque en frío sin conexión a internet.
  - **P2:** Hidratación inmediata en < 500 ms con 200 muestras.
  - **P3:** Reacción visual (< 100 ms) y acústica ante calor forzado en el sensor.
  - **P4:** Desconexión y reconexión física de cable Ethernet sin recargar la web.
  - **P5:** Visibilidad en proyector a 15 metros de distancia.
  - **P6:** Verificación de consumo de recursos (inferencia 100% en Pi ARM, laptop como cliente ligero).

#### 🧪 Criterio de Verificación
- La Raspberry Pi arranca y sirve la aplicación automáticamente al conectarle alimentación.
- El sistema pasa con éxito las 6 pruebas de la matriz del Demo Day.

---

## 🚀 Próximo Paso Recomendado

Para comenzar, ejecutaremos la **Fase 0: Preparación de Entorno y Estructura Base**, creando las carpetas del proyecto, `.gitignore`, `requirements.txt` y los archivos estáticos necesarios en `static/vendor/`.
