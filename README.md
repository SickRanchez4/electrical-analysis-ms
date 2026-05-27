# Electrical AI Microservice

Microservicio FastAPI para analizar consumo electrico a partir de un archivo Excel y consultas a un modelo OpenAI.

## Arquitectura

- Entrada de la app: app/main.py
- Rutas HTTP: app/api/analysis.py
- Logica de negocio: app/services/analysis_service.py
- Schemas de entrada/salida: app/schemas/analysis.py
- Configuracion central: app/core/config.py
- Logging: app/core/logging.py
- Seguridad por API key: app/core/security.py

## Requisitos

- Python 3.13+
- Archivo ReporteMedidores.xlsx en la raiz del proyecto (o configurar EXCEL_FILE_PATH)
- Dependencias instaladas desde requirements.txt

## Instalacion

1. Crear y activar entorno virtual.
2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

## Variables de entorno

Variables obligatorias:

- OPENAI_API_KEY: API key para OpenAI.

Variables opcionales:

- OPENAI_MODEL: modelo a usar (default: gpt-4.1-mini).
- EXCEL_FILE_PATH: ruta del archivo Excel (default: ReporteMedidores.xlsx en raiz del repo).
- LOG_LEVEL: nivel de logs (default: INFO).
- SERVICE_API_KEY: si se define, protege todos los endpoints de /analysis y exige header x-api-key.
- ENFORCE_SERVICE_API_KEY: obliga a definir SERVICE_API_KEY (default: false).
- RATE_LIMIT_ENABLED: habilita rate limiting para /analysis (default: true).
- RATE_LIMIT_REQUESTS_PER_WINDOW: maximo de requests por ventana (default: 60).
- RATE_LIMIT_WINDOW_SECONDS: duracion de la ventana en segundos (default: 60).

Ejemplo en PowerShell:

```powershell
$env:OPENAI_API_KEY="tu_api_key"
$env:OPENAI_MODEL="gpt-4.1-mini"
$env:EXCEL_FILE_PATH="ReporteMedidores.xlsx"
$env:LOG_LEVEL="INFO"
$env:SERVICE_API_KEY="mi_clave_interna"
$env:ENFORCE_SERVICE_API_KEY="true"
$env:RATE_LIMIT_ENABLED="true"
$env:RATE_LIMIT_REQUESTS_PER_WINDOW="60"
$env:RATE_LIMIT_WINDOW_SECONDS="60"
```

## Ejecucion

Iniciar servidor de desarrollo (PowerShell):

```powershell
uvicorn app.main:app --reload
```

Swagger UI:

- http://127.0.0.1:8000/docs

## Ejecucion con Docker

Construir imagen:

```powershell
docker build -t electrical-ai:latest .
```

Ejecutar contenedor en PowerShell:

```powershell
docker run --rm -p 8000:8000 `
  -e OPENAI_API_KEY="tu_api_key" `
  -e OPENAI_MODEL="gpt-4.1-mini" `
  -e EXCEL_FILE_PATH="ReporteMedidores.xlsx" `
  -e LOG_LEVEL="INFO" `
  -e SERVICE_API_KEY="mi_clave_interna" `
  -e ENFORCE_SERVICE_API_KEY="true" `
  -e RATE_LIMIT_ENABLED="true" `
  -e RATE_LIMIT_REQUESTS_PER_WINDOW="60" `
  -e RATE_LIMIT_WINDOW_SECONDS="60" `
  electrical-ai:latest
```

Nota: si no quieres proteger rutas de analisis, omite SERVICE_API_KEY.

## Seguridad

- Si SERVICE_API_KEY no esta definida, los endpoints /analysis quedan sin autenticacion.
- Si SERVICE_API_KEY esta definida, debes enviar el header x-api-key en cada request a /analysis.
- Si ENFORCE_SERVICE_API_KEY=true y falta SERVICE_API_KEY, el servicio no inicia.
- El rate limiting en /analysis devuelve 429 cuando se supera el limite de ventana.

## Health Check

- GET /health devuelve 200 solo cuando OPENAI_API_KEY esta configurada y el archivo Excel existe.
- Si falta alguna de esas dependencias, devuelve 503 con status degraded.

## Endpoints

### Health

- GET /health

Ejemplo:

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/health"
```

### Chat con datos del Excel

- POST /analysis/chat

Body:

```json
{
	"query": "Cual cuenta tuvo mayor consumo KWH?"
}
```

Ejemplo con API key:

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/analysis/chat" `
	-Headers @{ "x-api-key" = "mi_clave_interna" } `
	-ContentType "application/json" `
	-Body '{"query":"Cual cuenta tuvo mayor consumo KWH?"}'
```

### Cuentas sospechosas

- POST /analysis/cuentas-sospechosas

Ejemplo:

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/analysis/cuentas-sospechosas" -Headers @{ "x-api-key" = "mi_clave_interna" }
```

### Desequilibrios de fase

- POST /analysis/desequilibrios-fase

Ejemplo:

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/analysis/desequilibrios-fase" -Headers @{ "x-api-key" = "mi_clave_interna" }
```

### Formateo de tabla HTML

- POST /analysis/html-table-formatting

Body:

```json
{
	"html_table": "<table><tr><td>...</td></tr></table>"
}
```

Ejemplo:

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/analysis/html-table-formatting" `
	-Headers @{ "x-api-key" = "mi_clave_interna" } `
	-ContentType "application/json" `
	-Body '{"html_table":"<table><tr><td>Dato</td></tr></table>"}'
```

## Errores comunes

- 500 OPENAI_API_KEY no esta configurada: define la variable de entorno.
- 404 El archivo Excel no se encontro: revisa EXCEL_FILE_PATH.
- 401 Unauthorized: x-api-key incorrecta o faltante cuando SERVICE_API_KEY esta habilitada.
- 502 Error al hacer la solicitud al modelo: error upstream de OpenAI o conectividad.