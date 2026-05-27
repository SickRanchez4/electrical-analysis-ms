from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import get_logger
from app.core.security import enforce_rate_limit, verify_service_api_key
from app.schemas.analysis import AnalysisResponse, HtmlTableRequest, UserQueryRequest
from app.services.analysis_service import ElectricalAnalysisService


logger = get_logger(__name__)


router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(verify_service_api_key), Depends(enforce_rate_limit)],
)


def get_analysis_service() -> ElectricalAnalysisService:
    try:
        return ElectricalAnalysisService()
    except ValueError as exc:
        logger.exception("Service initialization failed")
        raise HTTPException(status_code=500, detail="Servicio no disponible.") from exc


@router.post("/chat", response_model=AnalysisResponse)
def chat_with_llm(
    payload: UserQueryRequest,
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        return AnalysisResponse(result=service.chat_with_llm(payload.query))
    except FileNotFoundError as exc:
        logger.exception("Excel file not found during chat request")
        raise HTTPException(status_code=404, detail="Archivo de datos no disponible.") from exc
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during chat request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/cuentas-sospechosas", response_model=AnalysisResponse)
def cuentas_sospechosas(
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        return AnalysisResponse(result=service.cuentas_sospechosas())
    except FileNotFoundError as exc:
        logger.exception("Excel file not found during suspicious accounts request")
        raise HTTPException(status_code=404, detail="Archivo de datos no disponible.") from exc
    except RuntimeError as exc:
        logger.exception("OpenAI request failed during suspicious accounts request")
        raise HTTPException(status_code=502, detail="No se pudo completar el análisis.") from exc


@router.post("/desequilibrios-fase", response_model=AnalysisResponse)
def desequilibrios_de_fase(
    service: ElectricalAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        return AnalysisResponse(result=service.desequilibrios_de_fase())
    except FileNotFoundError as exc:
        logger.exception("Excel file not found during phase imbalance request")
        raise HTTPException(status_code=404, detail="Archivo de datos no disponible.") from exc
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
