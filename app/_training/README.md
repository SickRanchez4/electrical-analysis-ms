# Modelo de aprendizaje automático

Pequeño proyecto para el entrenamiento supervisado de la predicción del consumo mensual de electricidad (`KWH MES`).

## Objetivo del proyecto

- `train_model.py`: crea y entrena el modelo a partir de archivos de Excel en `reportes/`.

- `prediccion_ml_service.py`: ejemplo basado en clases para cargar y consumir el modelo entrenado en una API/servicio.

## Datos esperados

La capacitación espera archivos de Excel en la carpeta `reportes/` con columnas como:

- `CUENTA`
- `I1 (A)`, `I2 (A)`, `I3 (A)`
- `V1 (V)`, `V2 (V)`, `V3 (V)`
- `FACTOR TOTAL`
- `I1 x FTC`, `I2 x FTC`, `I3 x FTC`
- `KWH MES`
- `POTENCIA MÁX (KW)`
- `Ubicación` (opcional)

Los nombres de los archivos deben incluir mes/año (ejemplos: `ENE-2016.xlsx`, `03_2021.xlsx`).

## Configuración

Crea y activa un entorno virtual, luego instala las dependencias:

```powershell
python -m venv _venv
.\_venv\Scripts\Activate.ps1
pip install pandas numpy scikit-learn xgboost openpyxl joblib fastapi uvicorn
```

## Entrenamiento del modelo

```powershell
python .\train_model.py
```

Después del entrenamiento, los artefactos se guardan en `model/`:

- `model/model.pkl`
- `model/label_encoder_ubicacion.pkl`
- `model/features_list.pkl`

## Uso de la clase del modelo

`prediccion_ml_service.py` expone `PrediccionMLService` para:

- Cargar los artefactos una sola vez.

- Construir las características del modelo a partir de las cargas útiles de entrada.
- Predecir registros únicos (`predecir_desde_request`).
- Predecir múltiples filas a partir de DataFrames tipo Excel (`predecir_desde_dataframe_excel`).
- Informe de preparación del modelo (`estado_modelo`).

Ejemplo de uso rápido:

```pitón
desde prediccion_ml_service importar PrediccionMLService

servicio = PredicciónMLService( 
ruta_modelo="./model/model.pkl", 
ruta_encoder="./model/label_encoder_ubicacion.pkl", 
ruta_features="./model/features_list.pkl",
)

imprimir(servicio.estado_modelo())
```