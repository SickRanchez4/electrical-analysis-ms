from pydantic import BaseModel, Field


class UserQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Pregunta del usuario")


class HtmlTableRequest(BaseModel):
    html_table: str = Field(..., min_length=1, description="Tabla HTML a limpiar")


class AnalysisResponse(BaseModel):
    result: str
