from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.logging import get_logger
from app.core.security import enforce_rate_limit, verify_service_api_key
from app.schemas.analysis import AnalysisResponse, HtmlTableRequest
from app.services.analysis_service import ElectricalAnalysisService


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
