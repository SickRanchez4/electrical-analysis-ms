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
- LOG_LEVEL: nivel de logs (default: INFO).
- SERVICE_API_KEY: si se define, protege todos los endpoints de /analysis y exige header x-api-key.
- ENFORCE_SERVICE_API_KEY: obliga a definir SERVICE_API_KEY (default: false).
- RATE_LIMIT_ENABLED: habilita rate limiting para /analysis (default: true).
- RATE_LIMIT_REQUESTS_PER_WINDOW: maximo de requests por ventana (default: 60).
- RATE_LIMIT_WINDOW_SECONDS: duracion de la ventana en segundos (default: 60).

Ejemplo en PowerShell:

```powershell
$env:OPENAI_API_KEY="tu_api_key"
$env:OPENAI_MODEL="gpt-5.4-mini"
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

- http://127.0.0.1:8080/docs

## Ejecucion con Docker

Construir imagen:

```powershell
docker build -t electrical-ai:latest .
```

Ejecutar contenedor en PowerShell:

```powershell
docker run --rm -p 8080:8080 `
  -e OPENAI_API_KEY="tu_api_key" `
  -e OPENAI_MODEL="gpt-5.4-mini" `
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

- GET /health devuelve 200 solo cuando OPENAI_API_KEY esta configurada y la politica de SERVICE_API_KEY es valida.
- Si falta alguna de esas dependencias, devuelve 503 con status degraded.

## Endpoints

### Health

- GET /health

Ejemplo:

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8080/health"
```

### Chat con datos del Excel

- POST /analysis/chat
- Requiere multipart/form-data con los campos query y excel_file.

Ejemplo enviando Excel por HTTP:

```powershell
$headers = @{ "x-api-key" = "mi_clave_interna" }
$form = @{
 	query = "Cual cuenta tuvo mayor consumo KWH?"
  excel_file = Get-Item "C:\ruta\ReporteMedidores.xlsx"
}
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8080/analysis/chat" -Headers $headers -Form $form
```

### Cuentas sospechosas

- POST /analysis/cuentas-sospechosas
- Requiere multipart/form-data con el campo excel_file.

Ejemplo enviando Excel por HTTP:

```powershell
$headers = @{ "x-api-key" = "mi_clave_interna" }
$form = @{ excel_file = Get-Item "C:\ruta\ReporteMedidores.xlsx" }
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8080/analysis/cuentas-sospechosas" -Headers $headers -Form $form
```

### Desequilibrios de fase

- POST /analysis/desequilibrios-fase
- Requiere multipart/form-data con el campo excel_file.

Ejemplo enviando Excel por HTTP:

```powershell
$headers = @{ "x-api-key" = "mi_clave_interna" }
$form = @{ excel_file = Get-Item "C:\ruta\ReporteMedidores.xlsx" }
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8080/analysis/desequilibrios-fase" -Headers $headers -Form $form
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
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8080/analysis/html-table-formatting" `
	-Headers @{ "x-api-key" = "mi_clave_interna" } `
	-ContentType "application/json" `
	-Body '{"html_table":"<table><tr><td>Dato</td></tr></table>"}'
```

## Errores comunes

- 500 OPENAI_API_KEY no esta configurada: define la variable de entorno.
- 415 Content-Type invalido: usa multipart/form-data en endpoints de analisis de Excel.
- 422 Faltan campos obligatorios: incluye excel_file (y query en /analysis/chat).
- 401 Unauthorized: x-api-key incorrecta o faltante cuando SERVICE_API_KEY esta habilitada.
- 502 Error al hacer la solicitud al modelo: error upstream de OpenAI o conectividad.