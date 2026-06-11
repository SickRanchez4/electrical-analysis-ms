from io import BytesIO
from typing import TypedDict

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.core.logging import get_logger


class AnomalyDetectionResultItem(TypedDict):
    account: str
    anomaly_score: float
    risk: str
    anomaly_type: str
    reasons: list[str]


class AnomalyDetectionResult(TypedDict):
    total_accounts: int
    anomalies_detected: int
    anomalies: list[AnomalyDetectionResultItem]


class MachineLearningAnalysisService:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    # Carga y validación del DataFrame a partir del contenido del Excel
    def _load_dataframe(self, excel_content: bytes, excel_filename: str | None = None) -> pd.DataFrame:
        if not excel_content:
            raise ValueError("El archivo Excel es obligatorio en la solicitud HTTP.")

        try:
            return pd.read_excel(BytesIO(excel_content))
        except Exception as exc:
            source_name = excel_filename or "archivo_subido"
            self.logger.exception("Error reading Excel file")
            raise ValueError(
                f"El archivo Excel '{source_name}' es inválido o no tiene formato compatible."
            ) from exc

    def detect_anomalies(
        self,
        excel_content: bytes,
        excel_filename: str | None = None,
    ) -> AnomalyDetectionResult:
        df = self._load_dataframe(excel_content=excel_content, excel_filename=excel_filename)

        required_columns = [
            "CUENTA",
            "I1 (A)",
            "I2 (A)",
            "I3 (A)",
            "V1 (V)",
            "V2 (V)",
            "V3 (V)",
            "FACTOR TOTAL",
            "KWH MES",
            "POTENCIA MAX (KW)",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(f"Faltan columnas requeridas: {missing_columns}")

        if len(df) < 100:
            raise ValueError("Se requieren al menos 100 registros.")

        electric_current_columns = [
            "I1 (A)",
            "I2 (A)",
            "I3 (A)",
        ]

        voltage_columns = [
            "V1 (V)",
            "V2 (V)",
            "V3 (V)",
        ]

        # Feature engineering: creación de nuevas características basadas en las existentes
        df["AVG_ELECTRIC_CURRENT"] = df[electric_current_columns].mean(axis=1)
        df["AVG_VOLTAGE"] = df[voltage_columns].mean(axis=1)
        df["ELECTRIC_CURRENT_IMBALANCE"] = (
            df[electric_current_columns].max(axis=1)
            - df[electric_current_columns].min(axis=1)
        )
        df["ELECTRIC_CURRENT_IMBALANCE_PCT"] = np.where(
            df["AVG_ELECTRIC_CURRENT"] > 0,
            (
                df["ELECTRIC_CURRENT_IMBALANCE"]
                / df["AVG_ELECTRIC_CURRENT"]
            ) * 100,
            0,
        )
        df["VOLTAGE_IMBALANCE"] = (
            df[voltage_columns].max(axis=1)
            - df[voltage_columns].min(axis=1)
        )
        df["KWH_PER_KW"] = np.where(
            df["POTENCIA MAX (KW)"] > 0,
            df["KWH MES"] / df["POTENCIA MAX (KW)"],
            0,
        )
        df["TOTAL_ELECTRIC_CURRENT"] = (
            df["I1 (A)"]
            + df["I2 (A)"]
            + df["I3 (A)"]
        )

        # Matriz de características para el modelo de detección de anomalías
        features = [
            "I1 (A)",
            "I2 (A)",
            "I3 (A)",
            "V1 (V)",
            "V2 (V)",
            "V3 (V)",
            "FACTOR TOTAL",
            "KWH MES",
            "POTENCIA MAX (KW)",
            "AVG_ELECTRIC_CURRENT",
            "AVG_VOLTAGE",
            "ELECTRIC_CURRENT_IMBALANCE",
            "ELECTRIC_CURRENT_IMBALANCE_PCT",
            "VOLTAGE_IMBALANCE",
            "KWH_PER_KW",
            "TOTAL_ELECTRIC_CURRENT",
        ]

        feature_matrix = (
            df[features]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )

        # Escalado de características para mejorar el rendimiento del modelo
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(feature_matrix)

        # Entrenamiento del modelo de detección de anomalías (Isolation Forest)
        model = IsolationForest(
            contamination="auto",
            n_estimators=200,
            random_state=42,
        )
        model.fit(scaled_features)

        df["ML_LABEL"] = model.predict(scaled_features)
        df["ML_SCORE"] = model.decision_function(scaled_features)

        # Identificación de anomalías y generación de resultados con explicaciones
        anomalies = (
            df[df["ML_LABEL"] == -1]
            .sort_values("ML_SCORE")
        )

        high_consumption_threshold = df["KWH_PER_KW"].quantile(0.95)
        results: list[AnomalyDetectionResultItem] = []

        for _, row in anomalies.iterrows():
            reasons: list[str] = []
            has_current_imbalance = row["ELECTRIC_CURRENT_IMBALANCE_PCT"] > 25
            has_voltage_imbalance = row["VOLTAGE_IMBALANCE"] > 10
            has_low_power_factor = row["FACTOR TOTAL"] < 0.8
            has_unusual_energy_usage = row["KWH_PER_KW"] > high_consumption_threshold

            if has_current_imbalance:
                reasons.append("alto desequilibrio de corriente eléctrica")

            if has_voltage_imbalance:
                reasons.append("alto desequilibrio de voltaje")

            if has_low_power_factor:
                reasons.append("bajo factor de potencia")

            if has_unusual_energy_usage:
                reasons.append("consumo de energía inusual")

            if len(reasons) >= 2:
                anomaly_type = "mixto"
            elif has_current_imbalance:
                anomaly_type = "desequilibrio de corriente"
            elif has_voltage_imbalance:
                anomaly_type = "desequilibrio de voltaje"
            elif has_low_power_factor:
                anomaly_type = "bajo factor potencia"
            elif has_unusual_energy_usage:
                anomaly_type = "consumo atipico"
            else:
                anomaly_type = "anomalia estadistica"

            results.append(
                {
                    "account": str(row["CUENTA"]),
                    "anomaly_score": round(float(abs(row["ML_SCORE"])), 4),
                    "risk": "ALTO" if abs(row["ML_SCORE"]) > 0.15 else "MEDIO",
                    "anomaly_type": anomaly_type,
                    "reasons": reasons,
                }
            )

        return {
            "total_accounts": int(len(df)),
            "anomalies_detected": len(results),
            "anomalies": results,
        }