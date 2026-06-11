from typing import Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.logging import get_logger
from app.core.security import enforce_rate_limit, verify_service_api_key
from app.schemas.analysis import AnalysisResponse, AnomalyDetectionItem, AnomalyDetectionResponse, HtmlTableRequest
from app.services.analysis_service import ElectricalAnalysisService
from app.services.machine_learning import MachineLearningAnalysisService
from app.schemas.analysis import PrediccionRequest, PrediccionResponse


logger = get_logger(__name__)


router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(verify_service_api_key), Depends(enforce_rate_limit)],
)


ALLOWED_EXCEL_EXTENSIONS = (".xlsx", ".xls")


def get_analysis_service() -> ElectricalAnalysisService:
    try:
        return ElectricalAnalysisService()
    except ValueError as exc:
        logger.exception("Service initialization failed")
        raise HTTPException(status_code=500, detail="Servicio no disponible.") from exc


def get_machine_learning_service() -> MachineLearningAnalysisService:
    return MachineLearningAnalysisService()


def _is_multipart_request(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    return "multipart/form-data" in content_type.lower()


async def _extract_excel_from_form(form: Any) -> tuple[bytes, str]:
    uploaded_file = form.get("excel_file")
    if uploaded_file is None:
        raise HTTPException(status_code=422, detail="El campo 'excel_file' es obligatorio.")

    # request.form() returns Starlette UploadFile instances.
    if not isinstance(uploaded_file, StarletteUploadFile):
        raise HTTPException(status_code=422, detail="El campo 'excel_file' debe ser un archivo.")

    filename = (uploaded_file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="El archivo Excel no tiene nombre.")

    if not filename.lower().endswith(ALLOWED_EXCEL_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .xlsx o .xls.")

    file_content = await uploaded_file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="El archivo Excel está vacío.")

    return file_content, filename


async def _extract_required_excel_from_request(request: Request) -> tuple[bytes, str]:
    if not _is_multipart_request(request):
        raise HTTPException(
            status_code=415,
            detail="Content-Type inválido. Debe ser multipart/form-data con campo 'excel_file'.",
        )

    form = await request.form()
    return await _extract_excel_from_form(form)


async def _parse_chat_request(request: Request) -> tuple[str, bytes, str]:
    if not _is_multipart_request(request):
        raise HTTPException(
            status_code=415,
            detail="Content-Type inválido. Debe ser multipart/form-data con campos 'query' y 'excel_file'.",
        )

    form = await request.form()
    query = form.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=422, detail="El campo 'query' es obligatorio.")

    excel_content, excel_filename = await _extract_excel_from_form(form)
    return query.strip(), excel_content, excel_filename


@router.post("/chat", response_model=AnalysisResponse)
async def chat_with_llm(
    request: Request,
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        query, excel_content, excel_filename = await _parse_chat_request(request)
        return AnalysisResponse(
            result=service.chat_with_llm(
                query,
                excel_content=excel_content,
                excel_filename=excel_filename,
            )
        )
    except ValueError as exc:
        logger.exception("Invalid Excel file during chat request")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during chat request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/cuentas-sospechosas", response_model=AnalysisResponse)
async def cuentas_sospechosas(
    request: Request,
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        excel_content, excel_filename = await _extract_required_excel_from_request(request)
        return AnalysisResponse(
            result=service.cuentas_sospechosas(
                excel_content=excel_content,
                excel_filename=excel_filename,
            )
        )
    except ValueError as exc:
        logger.exception("Invalid Excel file during suspicious accounts request")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during suspicious accounts request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/desequilibrios-fase", response_model=AnalysisResponse)
async def desequilibrios_de_fase(
    request: Request,
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        excel_content, excel_filename = await _extract_required_excel_from_request(request)
        return AnalysisResponse(
            result=service.desequilibrios_de_fase(
                excel_content=excel_content,
                excel_filename=excel_filename,
            )
        )
    except ValueError as exc:
        logger.exception("Invalid Excel file during phase imbalance request")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during phase imbalance request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/html-table-formatting", response_model=AnalysisResponse)
def html_table_formatting(
    payload: HtmlTableRequest,
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        return AnalysisResponse(result=service.html_table_formatting(payload.html_table))
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during HTML formatting request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/ml-deteccion-anomalias", response_model=AnomalyDetectionResponse)
async def anomaly_detection(
    request: Request,
    service: MachineLearningAnalysisService = Depends(get_machine_learning_service),
) -> AnomalyDetectionResponse:
    try:
        excel_content, excel_filename = await _extract_required_excel_from_request(request)
        result = service.detect_anomalies(
            excel_content=excel_content,
            excel_filename=excel_filename,
        )
        return AnomalyDetectionResponse(
            total_accounts=result["total_accounts"],
            anomalies_detected=result["anomalies_detected"],
            anomalies=[AnomalyDetectionItem(**item) for item in result["anomalies"]],
        )
    except ValueError as exc:
        logger.exception("Invalid Excel file during anomaly detection request")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

# =============================================================================
# ML SUPERVISADO ENDPOINTS
# =============================================================================

from app.services.model_prediction import PrediccionMLService
import pandas as pd
import io

RUTA_MODELO = "./model/model.pkl"
RUTA_ENCODER = "./model/label_encoder_ubicacion.pkl"
RUTA_FEATURES = "./model/features_list.pkl"
UMBRAL_ALERTA_PCT = 25.0

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
RUTA_MODELO = str(MODEL_DIR / "model.pkl")
RUTA_ENCODER = str(MODEL_DIR / "label_encoder_ubicacion.pkl")
RUTA_FEATURES = str(MODEL_DIR / "features_list.pkl")

SERVICIO_ML = PrediccionMLService(
    ruta_modelo=RUTA_MODELO,
    ruta_encoder=RUTA_ENCODER,
    ruta_features=RUTA_FEATURES,
    umbral_alerta_pct=UMBRAL_ALERTA_PCT,
)

def verificar_modelo() -> None:
    """Lanza error 503 si el modelo no esta cargado."""
    if not SERVICIO_ML.disponible:
        raise HTTPException(
            status_code=503,
            detail=SERVICIO_ML.error_carga or "Modelo no disponible. Ejecuta train_model.py primero.",
        )


@router.post(
    "/consumo",
    response_model=PrediccionResponse,
    summary="Predice el KWH del proximo mes para una cuenta",
    description=(
        "Recibe las mediciones del mes actual y el historial reciente de una cuenta "
        "y retorna el consumo estimado para el proximo mes junto con alertas."
    ),
)
async def predecir_consumo(request: PrediccionRequest):
    verificar_modelo()

    pred = SERVICIO_ML.predecir_desde_request(request)

    return PrediccionResponse(
        cuenta=request.cuenta,
        kwh_predicho=pred["kwh_predicho"],
        kwh_mes_anterior=request.kwh_lag1,
        variacion_esperada_pct=pred["variacion_esperada_pct"],
        alerta=pred["alerta"],
        mensaje_alerta=pred["mensaje_alerta"],
        confianza=pred["confianza"],
    )


@router.post(
    "/consumo/excel",
    summary="Predice consumo para multiples cuentas desde un Excel",
    description=(
        "Recibe un archivo Excel con lecturas de cuentas y retorna predicciones para "
        "todas las cuentas validas encontradas."
    ),
)
async def predecir_consumo_excel(file: UploadFile = File(...)):
    verificar_modelo()

    contenido = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contenido))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo el Excel: {e}")

    try:
        return SERVICIO_ML.predecir_desde_dataframe_excel(df)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/estado-modelo",
    summary="Verifica si el modelo esta cargado y listo",
)
async def estado_modelo():
    return SERVICIO_ML.estado_modelo()