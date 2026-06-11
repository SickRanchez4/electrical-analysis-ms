"""
Servicio de machine learning para prediccion de consumo.
Contiene toda la logica de carga de artefactos, construccion de features
y ejecucion de predicciones.
"""

from pathlib import Path
from typing import Any, Optional, cast

import joblib
import numpy as np
import pandas as pd


class PrediccionMLService:
    """Encapsula toda la funcionalidad de ML para prediccion de consumo."""

    def __init__(
        self,
        ruta_modelo: str = "./model/model.pkl",
        ruta_encoder: str = "./model/label_encoder_ubicacion.pkl",
        ruta_features: str = "./model/features_list.pkl",
        umbral_alerta_pct: float = 25.0,
    ) -> None:
        self.ruta_modelo = ruta_modelo
        self.ruta_encoder = ruta_encoder
        self.ruta_features = ruta_features
        self.umbral_alerta_pct = umbral_alerta_pct

        self.modelo = None
        self.encoder_ubicacion = None
        self.features_lista = None
        self.error_carga = None

        self._cargar_artefactos()

    def _cargar_artefactos(self) -> None:
        errores = []
        for ruta in [self.ruta_modelo, self.ruta_encoder, self.ruta_features]:
            if not Path(ruta).exists():
                errores.append(ruta)

        if errores:
            self.error_carga = (
                f"Archivos de modelo no encontrados: {errores}. "
                f"Ejecuta primero: python train_model.py"
            )
            return

        self.modelo = joblib.load(self.ruta_modelo)
        self.encoder_ubicacion = joblib.load(self.ruta_encoder)
        self.features_lista = joblib.load(self.ruta_features)
        self.error_carga = None

    @property
    def disponible(self) -> bool:
        return self.modelo is not None

    def _asegurar_modelo_listo(self) -> tuple[Any, list[str]]:
        if self.modelo is None or self.features_lista is None:
            raise RuntimeError(
                self.error_carga or "Modelo no cargado. Ejecuta train_model.py primero."
            )
        return self.modelo, cast(list[str], self.features_lista)

    def codificar_ubicacion(self, ubicacion: Optional[str]) -> int:
        if ubicacion is None or self.encoder_ubicacion is None:
            return 0
        try:
            return int(self.encoder_ubicacion.transform([ubicacion])[0])
        except ValueError:
            return 0

    @staticmethod
    def calcular_confianza(std_kwh_6m: float, media_kwh_6m: float) -> str:
        if media_kwh_6m <= 0:
            return "baja"
        cv = std_kwh_6m / media_kwh_6m
        if cv < 0.10:
            return "alta"
        if cv < 0.25:
            return "media"
        return "baja"

    def construir_vector_features(self, req) -> pd.DataFrame:
        _, features_lista = self._asegurar_modelo_listo()

        seno_mes = np.sin(2 * np.pi * req.mes_actual / 12)
        coseno_mes = np.cos(2 * np.pi * req.mes_actual / 12)
        ubicacion_enc = self.codificar_ubicacion(req.ubicacion)

        fila = {
            "i1": req.i1,
            "i2": req.i2,
            "i3": req.i3,
            "v1": req.v1,
            "v2": req.v2,
            "v3": req.v3,
            "factor_total": req.factor_total,
            "i1_ftc": req.i1_ftc,
            "i2_ftc": req.i2_ftc,
            "i3_ftc": req.i3_ftc,
            "potencia_max": req.potencia_max,
            "kwh_lag1": req.kwh_lag1,
            "kwh_lag3": req.kwh_lag3,
            "kwh_lag6": req.kwh_lag6,
            "kwh_lag12": req.kwh_lag12,
            "factor_lag1": req.factor_lag1,
            "potencia_lag1": req.potencia_lag1,
            "var_kwh_1m": req.var_kwh_1m,
            "var_kwh_3m": req.var_kwh_3m,
            "media_kwh_3m": req.media_kwh_3m,
            "media_kwh_6m": req.media_kwh_6m,
            "std_kwh_6m": req.std_kwh_6m,
            "tendencia_kwh_6m": req.tendencia_kwh_6m,
            "seno_mes": seno_mes,
            "coseno_mes": coseno_mes,
            "mes_num": req.mes_actual,
            "ubicacion_enc": ubicacion_enc,
        }

        return pd.DataFrame([fila])[features_lista]

    def predecir_desde_request(self, req) -> dict:
        modelo, _ = self._asegurar_modelo_listo()
        x = self.construir_vector_features(req)
        kwh_predicho = float(modelo.predict(x)[0])
        kwh_predicho = max(0.0, round(kwh_predicho, 2))

        variacion_pct = ((kwh_predicho - req.kwh_lag1) / (req.kwh_lag1 + 1e-6)) * 100
        variacion_pct = round(variacion_pct, 2)

        alerta = abs(variacion_pct) > self.umbral_alerta_pct
        mensaje_alerta = None
        if alerta:
            if variacion_pct < 0:
                mensaje_alerta = (
                    f"Se espera una CAIDA del {abs(variacion_pct):.1f}% en el consumo. "
                    f"Posible anomalia o inicio de hurto."
                )
            else:
                mensaje_alerta = (
                    f"Se espera un AUMENTO del {variacion_pct:.1f}% en el consumo. "
                    f"Verificar si hay nueva actividad o equipo instalado."
                )

        confianza = self.calcular_confianza(req.std_kwh_6m, req.media_kwh_6m)

        return {
            "kwh_predicho": kwh_predicho,
            "variacion_esperada_pct": variacion_pct,
            "alerta": alerta,
            "mensaje_alerta": mensaje_alerta,
            "confianza": confianza,
        }

    def predecir_desde_dataframe_excel(self, df: pd.DataFrame) -> dict:
        modelo, features_lista = self._asegurar_modelo_listo()

        columnas_requeridas = [
            "CUENTA",
            "KWH MES",
            "FACTOR TOTAL",
            "I1 (A)",
            "I2 (A)",
            "I3 (A)",
            "V1 (V)",
            "V2 (V)",
            "V3 (V)",
            "POTENCIA MAX (KW)",
        ]
        faltantes = [c for c in columnas_requeridas if c not in df.columns]
        if faltantes:
            raise ValueError(f"Columnas faltantes en el Excel: {faltantes}")

        df = df.rename(
            columns={
                "CUENTA": "cuenta",
                "KWH MES": "kwh",
                "FACTOR TOTAL": "factor_total",
                "POTENCIA MAX (KW)": "potencia_max",
                "I1 (A)": "i1",
                "I2 (A)": "i2",
                "I3 (A)": "i3",
                "V1 (V)": "v1",
                "V2 (V)": "v2",
                "V3 (V)": "v3",
                "I1 x FTC": "i1_ftc",
                "I2 x FTC": "i2_ftc",
                "I3 x FTC": "i3_ftc",
                "Ubicacion": "ubicacion",
                "Ubicación": "ubicacion",
            }
        )

        resultados = []
        for _, fila in df.iterrows():
            cuenta = str(fila.get("cuenta", "DESCONOCIDA"))
            kwh = float(fila.get("kwh", 0) or 0)
            if kwh <= 0:
                continue

            kwh_est = kwh
            factor = float(fila.get("factor_total", 0.9) or 0.9)
            potencia = float(fila.get("potencia_max", 0) or 0)
            ubicacion = str(fila.get("ubicacion", "")) if pd.notna(fila.get("ubicacion")) else None

            fila_features = {
                "i1": float(fila.get("i1", 0) or 0),
                "i2": float(fila.get("i2", 0) or 0),
                "i3": float(fila.get("i3", 0) or 0),
                "v1": float(fila.get("v1", 220) or 220),
                "v2": float(fila.get("v2", 220) or 220),
                "v3": float(fila.get("v3", 220) or 220),
                "factor_total": factor,
                "i1_ftc": float(fila.get("i1_ftc", 0) or 0),
                "i2_ftc": float(fila.get("i2_ftc", 0) or 0),
                "i3_ftc": float(fila.get("i3_ftc", 0) or 0),
                "potencia_max": potencia,
                "kwh_lag1": kwh_est,
                "kwh_lag3": kwh_est,
                "kwh_lag6": kwh_est,
                "kwh_lag12": kwh_est,
                "factor_lag1": factor,
                "potencia_lag1": potencia,
                "var_kwh_1m": 0.0,
                "var_kwh_3m": 0.0,
                "media_kwh_3m": kwh_est,
                "media_kwh_6m": kwh_est,
                "std_kwh_6m": kwh_est * 0.1,
                "tendencia_kwh_6m": 0.0,
                "seno_mes": np.sin(2 * np.pi * 1 / 12),
                "coseno_mes": np.cos(2 * np.pi * 1 / 12),
                "mes_num": 1,
                "ubicacion_enc": self.codificar_ubicacion(ubicacion),
            }

            x = pd.DataFrame([fila_features])[features_lista]
            kwh_predicho = float(modelo.predict(x)[0])
            kwh_predicho = max(0.0, round(kwh_predicho, 2))
            variacion_pct = round(((kwh_predicho - kwh) / (kwh + 1e-6)) * 100, 2)

            resultados.append(
                {
                    "cuenta": cuenta,
                    "kwh_actual": round(kwh, 2),
                    "kwh_predicho_proximo_mes": kwh_predicho,
                    "variacion_esperada_pct": variacion_pct,
                    "alerta": abs(variacion_pct) > self.umbral_alerta_pct,
                }
            )

        if not resultados:
            raise ValueError("No se encontraron cuentas validas en el Excel.")

        cuentas_con_alerta = sum(1 for r in resultados if r["alerta"])
        return {
            "total_cuentas": len(resultados),
            "cuentas_con_alerta": cuentas_con_alerta,
            "nota": "Para mayor precision usa /prediccion/consumo con historial real de cada cuenta.",
            "predicciones": resultados,
        }

    def estado_modelo(self) -> dict:
        if not self.disponible:
            return {
                "estado": "no_disponible",
                "mensaje": self.error_carga or "Modelo no cargado. Ejecuta train_model.py primero.",
            }
        return {
            "estado": "listo",
            "mensaje": "Modelo de prediccion de consumo activo.",
            "features_count": len(self.features_lista) if self.features_lista else 0,
            "umbral_alerta_pct": self.umbral_alerta_pct,
        }
