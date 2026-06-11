"""
train_model.py
==============
Script para entrenar un modelo de predicción de consumo mensual (KWH MES)
por cuenta eléctrica, usando datos históricos desde múltiples archivos Excel.

Flujo:
  1. Cargar y unir todos los excels de la carpeta
  2. Construir features temporales (lags, tendencias, estacionalidad)
  3. Entrenar un modelo XGBoost
  4. Evaluar el modelo
  5. Guardar el modelo en disco (model.pkl) para usarlo en FastAPI

Requisitos:
  pip install pandas numpy scikit-learn xgboost openpyxl joblib
"""

import os
import re
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Carpeta donde están todos tus archivos Excel
CARPETA_EXCELS = "./reportes"

# Ruta donde se guardará el modelo entrenado
RUTA_MODELO = "./generated-model/model.pkl"
RUTA_MODELO_RAIZ = "./generated-model"

# Nombre exacto de las columnas en el excel
COL_CUENTA     = "CUENTA"
COL_I1         = "I1 (A)"
COL_I2         = "I2 (A)"
COL_I3         = "I3 (A)"
COL_V1         = "V1 (V)"
COL_V2         = "V2 (V)"
COL_V3         = "V3 (V)"
COL_FACTOR     = "FACTOR TOTAL"
COL_I1FTC      = "I1 x FTC"
COL_I2FTC      = "I2 x FTC"
COL_I3FTC      = "I3 x FTC"
COL_KWH        = "KWH MES"
COL_POT_MAX    = "POTENCIA MAX (KW)"
COL_UBICACION  = "Ubicación"

# Mapeo de nombres de mes en español a número
MESES_ES = {
    "ene": 1,  "enero": 1,
    "feb": 2,  "febrero": 2,
    "mar": 3,  "marzo": 3,
    "abr": 4,  "abril": 4,
    "may": 5,  "mayo": 5,
    "jun": 6,  "junio": 6,
    "jul": 7,  "julio": 7,
    "ago": 8,  "agosto": 8,
    "sep": 9,  "septiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}


# =============================================================================
# PASO 1: Cargar y unir todos los excels
# =============================================================================

def extraer_fecha_del_nombre(nombre_archivo: str):
    """
    Extrae mes y año del nombre del archivo.
    Ejemplos soportados:
      ene_2016.xlsx  → (1, 2016)
      febrero_2020.xlsx → (2, 2020)
      03_2021.xlsx → (3, 2021)
    """
    nombre = nombre_archivo.lower().replace(".xlsx", "").replace(".xls", "")

    # Intentar extraer año (4 dígitos)
    anio_match = re.search(r"(20\d{2})", nombre)
    if not anio_match:
        return None, None
    anio = int(anio_match.group(1))

    # Intentar mes por nombre en español
    for nombre_mes, num_mes in MESES_ES.items():
        if nombre_mes in nombre:
            return num_mes, anio

    # Intentar mes por número (01, 02, ... 12)
    mes_match = re.search(r"\b(0?[1-9]|1[0-2])\b", nombre)
    if mes_match:
        return int(mes_match.group(1)), anio

    return None, None


def cargar_todos_los_excels(carpeta: str) -> pd.DataFrame:
    """
    Lee todos los archivos .xlsx de la carpeta, agrega columnas 'mes' y 'anio',
    y los concatena en un único DataFrame.
    """
    archivos = [f for f in os.listdir(carpeta) if f.endswith((".xlsx", ".xls"))]

    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos Excel en: {carpeta}")

    print(f"📂 Encontrados {len(archivos)} archivos Excel. Cargando...")

    dfs = []
    errores = []

    for archivo in sorted(archivos):
        mes, anio = extraer_fecha_del_nombre(archivo)

        if mes is None or anio is None:
            errores.append(archivo)
            print(f"  ⚠️  No se pudo extraer fecha de: {archivo} — omitido")
            continue

        ruta = os.path.join(carpeta, archivo)
        try:
            df = pd.read_excel(ruta)
            df["mes"]  = mes
            df["anio"] = anio
            # Crear columna de fecha como primer día del mes
            df["fecha"] = pd.to_datetime({"year": df["anio"], "month": df["mes"], "day": 1})
            dfs.append(df)
        except Exception as e:
            print(f"  ❌ Error leyendo {archivo}: {e}")
            errores.append(archivo)

    if not dfs:
        raise ValueError("No se pudo cargar ningún archivo Excel correctamente.")

    df_total = pd.concat(dfs, ignore_index=True)
    print(f"\n✅ Dataset maestro: {len(df_total)} registros de {len(dfs)} archivos")
    if errores:
        print(f"   ⚠️  Archivos omitidos: {errores}")

    return df_total


# =============================================================================
# PASO 2: Limpieza y preparación base
# =============================================================================

def limpiar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Estandariza nombres de columnas
    - Elimina filas sin CUENTA o sin KWH
    - Convierte columnas numéricas
    - Ordena por cuenta y fecha
    """
    # Renombrar columnas para trabajar más fácil internamente
    rename_map = {
        COL_CUENTA:    "cuenta",
        COL_I1:        "i1",
        COL_I2:        "i2",
        COL_I3:        "i3",
        COL_V1:        "v1",
        COL_V2:        "v2",
        COL_V3:        "v3",
        COL_FACTOR:    "factor_total",
        COL_I1FTC:     "i1_ftc",
        COL_I2FTC:     "i2_ftc",
        COL_I3FTC:     "i3_ftc",
        COL_KWH:       "kwh",
        COL_POT_MAX:   "potencia_max",
        COL_UBICACION: "ubicacion",
    }
    df = df.rename(columns=rename_map)

    # Eliminar filas sin cuenta ni kwh (son esenciales)
    df = df.dropna(subset=["cuenta", "kwh"])

    # Convertir columnas numéricas (por si vienen como texto)
    cols_numericas = ["i1", "i2", "i3", "v1", "v2", "v3",
                      "factor_total", "i1_ftc", "i2_ftc", "i3_ftc",
                      "kwh", "potencia_max"]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Eliminar filas donde kwh sea negativo o nulo (datos corruptos)
    df = df[df["kwh"] > 0]

    # Ordenar cronológicamente por cuenta
    df = df.sort_values(["cuenta", "fecha"]).reset_index(drop=True)

    print(f"🧹 Después de limpieza: {len(df)} registros, {df['cuenta'].nunique()} cuentas únicas")
    return df


# =============================================================================
# PASO 3: Ingeniería de features temporales
# =============================================================================

def construir_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Por cada cuenta, construye features que capturan el comportamiento histórico:

    - LAG features: valores de meses anteriores
        kwh_lag1  = KWH del mes anterior
        kwh_lag3  = KWH de hace 3 meses
        kwh_lag6  = KWH de hace 6 meses
        kwh_lag12 = KWH del mismo mes el año pasado

    - Features de cambio:
        var_kwh_1m  = % de variación vs mes anterior
        var_kwh_3m  = % de variación vs hace 3 meses

    - Features de estadísticas recientes:
        media_kwh_3m = promedio de los últimos 3 meses
        std_kwh_6m   = desviación estándar últimos 6 meses (estabilidad)

    - Features de tendencia:
        tendencia_kwh_6m = pendiente de regresión lineal de 6 meses

    - Estacionalidad:
        mes_num       = número del mes (1-12)
        seno_mes / coseno_mes = codificación cíclica del mes

    La variable objetivo (target) es el KWH del MES SIGUIENTE.
    """

    grupos = []

    for cuenta, grupo in df.groupby("cuenta"):
        g = grupo.copy().sort_values("fecha")

        # --- LAG features ---
        g["kwh_lag1"]  = g["kwh"].shift(1)   # mes anterior
        g["kwh_lag3"]  = g["kwh"].shift(3)   # hace 3 meses
        g["kwh_lag6"]  = g["kwh"].shift(6)   # hace 6 meses
        g["kwh_lag12"] = g["kwh"].shift(12)  # mismo mes año pasado

        g["factor_lag1"]    = g["factor_total"].shift(1)
        g["potencia_lag1"]  = g["potencia_max"].shift(1)

        # --- Features de cambio porcentual ---
        g["var_kwh_1m"] = (g["kwh"] - g["kwh_lag1"]) / (g["kwh_lag1"] + 1e-6)
        g["var_kwh_3m"] = (g["kwh"] - g["kwh_lag3"]) / (g["kwh_lag3"] + 1e-6)

        # --- Estadísticas de ventana deslizante ---
        g["media_kwh_3m"]  = g["kwh"].shift(1).rolling(3).mean()
        g["media_kwh_6m"]  = g["kwh"].shift(1).rolling(6).mean()
        g["std_kwh_6m"]    = g["kwh"].shift(1).rolling(6).std()

        # --- Tendencia (pendiente lineal de los últimos 6 meses) ---
        def calcular_tendencia(arr):
            """
            Calcula la pendiente de una regresión lineal simple.
            Recibe un numpy.ndarray (raw=True es más rápido que raw=False).
            """
            if len(arr) < 2 or np.any(np.isnan(arr)):
                return np.nan
            x = np.arange(len(arr))
            slope = np.polyfit(x, arr, 1)[0]
            return slope

        g["tendencia_kwh_6m"] = (
            g["kwh"].shift(1)
            .rolling(6)
            .apply(calcular_tendencia, raw=True)  # raw=True → ndarray, más rápido
        )

        # --- VARIABLE OBJETIVO: KWH del mes siguiente ---
        g["target_kwh"] = g["kwh"].shift(-1)

        grupos.append(g)

    df_features = pd.concat(grupos, ignore_index=True)

    # --- Features de estacionalidad ---
    df_features["mes_num"] = df_features["mes"]
    # Codificación cíclica: el modelo entiende que dic(12) y ene(1) son cercanos
    df_features["seno_mes"]   = np.sin(2 * np.pi * df_features["mes"] / 12)
    df_features["coseno_mes"] = np.cos(2 * np.pi * df_features["mes"] / 12)

    # Codificar ubicación como número (LabelEncoder)
    if "ubicacion" in df_features.columns:
        le = LabelEncoder()
        df_features["ubicacion_enc"] = le.fit_transform(
            df_features["ubicacion"].fillna("desconocida").astype(str)
        )
        # Guardamos el encoder para usarlo en predicción
        joblib.dump(le, os.path.join(RUTA_MODELO_RAIZ, "label_encoder_ubicacion.pkl"))
    else:
        df_features["ubicacion_enc"] = 0

    print(f"🔧 Features construidas. Dataset final: {len(df_features)} filas")
    return df_features


# =============================================================================
# PASO 4: Preparar X e y para entrenamiento
# =============================================================================

# Columnas que usará el modelo como entrada
FEATURES = [
    # Snapshot del mes actual
    "i1", "i2", "i3",
    "v1", "v2", "v3",
    "factor_total",
    "i1_ftc", "i2_ftc", "i3_ftc",
    "potencia_max",

    # Historial de consumo
    "kwh_lag1", "kwh_lag3", "kwh_lag6", "kwh_lag12",
    "factor_lag1", "potencia_lag1",

    # Cambios
    "var_kwh_1m", "var_kwh_3m",

    # Estadísticas recientes
    "media_kwh_3m", "media_kwh_6m", "std_kwh_6m",

    # Tendencia
    "tendencia_kwh_6m",

    # Estacionalidad
    "seno_mes", "coseno_mes", "mes_num",

    # Ubicación codificada
    "ubicacion_enc",
]

TARGET = "target_kwh"


def preparar_Xy(df: pd.DataFrame):
    """
    Filtra filas con NaN en features o target, y separa X e y.
    Las filas con NaN aparecen en los primeros meses de cada cuenta
    (no tienen suficiente historial para calcular lags).
    """
    df_modelo = df[FEATURES + [TARGET, "cuenta", "fecha"]].dropna()

    print(f"📐 Filas para entrenamiento (sin NaN): {len(df_modelo)}")

    X = df_modelo[FEATURES]
    y = df_modelo[TARGET]

    return X, y, df_modelo


# =============================================================================
# PASO 5: Entrenar el modelo
# =============================================================================

def entrenar_modelo(X: pd.DataFrame, y: pd.Series):
    """
    Divide datos en train/test respetando el orden temporal,
    entrena XGBoost y evalúa métricas.
    """
    # División temporal (NO aleatoria): los últimos 15% de datos = test
    # Esto simula predecir meses futuros con datos pasados
    split_idx = int(len(X) * 0.85)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"\n🏋️  Entrenando con {len(X_train)} filas | Evaluando con {len(X_test)} filas")

    modelo = XGBRegressor(
        n_estimators=300,       # número de árboles
        max_depth=6,            # profundidad máxima de cada árbol
        learning_rate=0.05,     # paso de aprendizaje (bajo = más preciso, más lento)
        subsample=0.8,          # % de datos por árbol (evita sobreajuste)
        colsample_bytree=0.8,   # % de features por árbol
        random_state=42,
        n_jobs=-1,              # usar todos los núcleos del CPU
        verbosity=0,
    )

    modelo.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Evaluación ---
    y_pred = modelo.predict(X_test)

    mae   = mean_absolute_error(y_test, y_pred)
    rmse  = np.sqrt(mean_squared_error(y_test, y_pred))
    r2    = r2_score(y_test, y_pred)
    mape  = np.mean(np.abs((y_test - y_pred) / (y_test + 1e-6))) * 100

    print("\n📊 Métricas de evaluación (set de test temporal):")
    print(f"   MAE   (Error Absoluto Medio):      {mae:.2f} KWH")
    print(f"   RMSE  (Error Cuadrático Medio):    {rmse:.2f} KWH")
    print(f"   MAPE  (Error Porcentual Absoluto): {mape:.2f}%")
    print(f"   R²    (Coef. de determinación):    {r2:.4f}  (1.0 = perfecto)")

    # Importancia de features (top 10)
    importancias = pd.Series(modelo.feature_importances_, index=FEATURES)
    print("\n🏆 Top 10 features más importantes:")
    print(importancias.nlargest(10).to_string())

    return modelo


# =============================================================================
# PASO 6: Guardar el modelo
# =============================================================================

def guardar_modelo(modelo, ruta: str):
    """Serializa el modelo con joblib para cargarlo luego en FastAPI."""
    joblib.dump(modelo, ruta)
    print(f"\n💾 Modelo guardado en: {ruta}")


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  ENTRENAMIENTO: Predicción de Consumo Eléctrico (KWH)")
    print("=" * 60)

    # 1. Cargar excels
    df_raw = cargar_todos_los_excels(CARPETA_EXCELS)

    # 2. Limpiar
    df_limpio = limpiar_datos(df_raw)

    # 3. Construir features temporales
    df_features = construir_features(df_limpio)

    # 4. Separar X e y
    X, y, df_modelo = preparar_Xy(df_features)

    # 5. Entrenar
    modelo = entrenar_modelo(X, y)

    # 6. Guardar
    guardar_modelo(modelo, RUTA_MODELO)

    # Guardar también la lista de features (para validar en FastAPI)
    joblib.dump(FEATURES, os.path.join(RUTA_MODELO_RAIZ, "features_list.pkl"))

    print("\n✅ Entrenamiento completo.")
    print(f"   Archivos generados:")
    print(f"   → {RUTA_MODELO}")
    print(f"   → {RUTA_MODELO_RAIZ}/label_encoder_ubicacion.pkl")
    print(f"   → {RUTA_MODELO_RAIZ}/features_list.pkl")