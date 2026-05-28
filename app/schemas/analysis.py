from pydantic import BaseModel, Field


class HtmlTableRequest(BaseModel):
    html_table: str = Field(..., min_length=1, description="Tabla HTML a limpiar")


class AnalysisResponse(BaseModel):
    result: str
