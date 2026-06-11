from typing import Optional
from pydantic import BaseModel, Field


class HtmlTableRequest(BaseModel):
    html_table: str = Field(..., min_length=1, description="Tabla HTML a limpiar")


class AnalysisResponse(BaseModel):
    result: str


class AnomalyDetectionItem(BaseModel):
    account: str
    anomaly_score: float
    risk: str
    anomaly_type: str
    reasons: list[str]


class AnomalyDetectionResponse(BaseModel):
    total_accounts: int
    anomalies_detected: int
    anomalies: list[AnomalyDetectionItem]

# =============================================================================
# MACHINE LEARNING SCHEMAS
# =============================================================================

class PrediccionRequest(BaseModel):
    """Datos necesarios para predecir el KWH del proximo mes de una cuenta."""

    cuenta: str = Field(..., description="Identificador de la cuenta")
    mes_actual: int = Field(..., ge=1, le=12, description="Mes actual (1-12)")

    i1: float = Field(..., description="Corriente fase 1 (A)")
    i2: float = Field(..., description="Corriente fase 2 (A)")
    i3: float = Field(..., description="Corriente fase 3 (A)")
    v1: float = Field(..., description="Voltaje fase 1 (V)")
    v2: float = Field(..., description="Voltaje fase 2 (V)")
    v3: float = Field(..., description="Voltaje fase 3 (V)")
    factor_total: float = Field(..., description="Factor de potencia total")
    i1_ftc: float = Field(..., description="I1 x FTC")
    i2_ftc: float = Field(..., description="I2 x FTC")
    i3_ftc: float = Field(..., description="I3 x FTC")
    potencia_max: float = Field(..., description="Potencia maxima (KW)")
    ubicacion: Optional[str] = Field(None, description="Ubicacion de la cuenta")

    kwh_lag1: float = Field(..., description="KWH del mes anterior")
    kwh_lag3: float = Field(..., description="KWH de hace 3 meses")
    kwh_lag6: float = Field(..., description="KWH de hace 6 meses")
    kwh_lag12: float = Field(..., description="KWH del mismo mes hace 1 ano")
    factor_lag1: float = Field(..., description="Factor total del mes anterior")
    potencia_lag1: float = Field(..., description="Potencia max del mes anterior")

    media_kwh_3m: float = Field(..., description="Promedio KWH ultimos 3 meses")
    media_kwh_6m: float = Field(..., description="Promedio KWH ultimos 6 meses")
    std_kwh_6m: float = Field(..., description="Desviacion estandar KWH 6 meses")
    tendencia_kwh_6m: float = Field(..., description="Tendencia (pendiente) KWH 6 meses")
    var_kwh_1m: float = Field(..., description="Variacion % KWH vs mes anterior")
    var_kwh_3m: float = Field(..., description="Variacion % KWH vs hace 3 meses")


class CuentaHistorialItem(BaseModel):
    """Una fila del historial de una cuenta (para el endpoint con Excel)."""

    cuenta: str
    fecha: str
    kwh: float
    i1: float
    i2: float
    i3: float
    v1: float
    v2: float
    v3: float
    factor_total: float
    potencia_max: float
    ubicacion: Optional[str] = None


class PrediccionResponse(BaseModel):
    """Respuesta del endpoint de prediccion."""

    cuenta: str
    kwh_predicho: float = Field(..., description="KWH estimado para el proximo mes")
    kwh_mes_anterior: float = Field(..., description="KWH del mes actual (referencia)")
    variacion_esperada_pct: float = Field(..., description="% de cambio esperado vs mes anterior")
    alerta: bool = Field(..., description="True si la variacion supera el umbral de alerta")
    mensaje_alerta: Optional[str] = Field(None, description="Descripcion de la alerta si existe")
    confianza: str = Field(..., description="Nivel de confianza: alta / media / baja")

# =============================================================================
# =============================================================================