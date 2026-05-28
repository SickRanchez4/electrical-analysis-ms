from io import BytesIO
from typing import Iterable
import pandas as pd
from openai import OpenAI

from app.core.config import get_settings
from app.core.logging import get_logger


class ElectricalAnalysisService:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.logger = get_logger(__name__)

        resolved_api_key = api_key or settings.openai_api_key
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en el entorno.")

        self.client = OpenAI(
            api_key=resolved_api_key,
            timeout=30.0,
            max_retries=2,
        )
        self.model = model or settings.openai_model

    def load_xl_data(
        self,
        excel_content: bytes,
        columnas_deseadas: Iterable[str] | None = None,
        excel_filename: str | None = None,
    ) -> str:
        if not excel_content:
            raise ValueError("El archivo Excel es obligatorio en la solicitud HTTP.")

        try:
            excel_source = BytesIO(excel_content)
            if columnas_deseadas:
                dataframe = pd.read_excel(excel_source, usecols=list(columnas_deseadas))
            else:
                dataframe = pd.read_excel(excel_source)
            return dataframe.to_csv(index=False)
        except ValueError as exc:
            source_name = excel_filename or "archivo_subido"
            raise ValueError(f"El archivo Excel '{source_name}' es inválido o no tiene formato compatible.") from exc

    def _ask_model(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Error calling OpenAI model")
            raise RuntimeError("No se pudo completar la solicitud al modelo.") from exc

    def chat_with_llm(
        self,
        user_query: str,
        excel_content: bytes,
        excel_filename: str | None = None,
    ) -> str:
        excel_data = self.load_xl_data(excel_content=excel_content, excel_filename=excel_filename)

        prompt = f"""
        Eres un experto analista de datos de consumo electrico.
        Tu tarea es responder preguntas basadas en los registros de mediciones de consumo de distintas cuentas de usuarios.

        --- INICIO DE DATOS DE EXCEL ---
        {excel_data}
        --- FIN DE DATOS DE EXCEL ---

        Basandote unicamente en los datos anteriores, responde a mi pregunta de forma clara y directa.
        Si la informacion no esta presente en los datos, indicalo.

        --- INICIO DE PREGUNTA ---
        {user_query}
        --- FIN DE PREGUNTA ---
        """

        return self._ask_model(prompt)

    def cuentas_sospechosas(
        self,
        excel_content: bytes,
        excel_filename: str | None = None,
    ) -> str:
        columnas_deseadas = ["CUENTA", "I1 (A)", "I2 (A)", "I3 (A)", "V1 (V)", "V2 (V)", "V3 (V)", "KWH MES"]
        excel_data = self.load_xl_data(
            columnas_deseadas=columnas_deseadas,
            excel_content=excel_content,
            excel_filename=excel_filename,
        )

        prompt = f"""
        Eres un analista experto en energia electrica.
        Tu tarea es detectar anomalias en el consumo electrico de diferentes cuentas usando datos de mediciones electricas ['CUENTA', 'I1 (A)', 'I2 (A)', 'I3 (A)', 'V1 (V)', 'V2 (V)', 'V3 (V)', 'KWH MES'].
        Tu analisis debe devolver una lista de cuentas sospechosas con sus metricas calculadas y una breve justificacion (por que fue marcada como sospechosa).

        Aqui estan los datos:
            {excel_data}
        """

        return self._ask_model(prompt)

    def desequilibrios_de_fase(
        self,
        excel_content: bytes,
        excel_filename: str | None = None,
    ) -> str:
        columnas_deseadas = ["CUENTA", "I1 (A)", "I2 (A)", "I3 (A)", "V1 (V)", "V2 (V)", "V3 (V)"]
        excel_data = self.load_xl_data(
            columnas_deseadas=columnas_deseadas,
            excel_content=excel_content,
            excel_filename=excel_filename,
        )

        prompt = f"""
        Realiza un analisis de 'Desequilibrio severo' por cuenta, sobre los siguientes datos de mediciones electricas.
        Criterios de Analisis
            - Corrientes(I): Se considera desequilibrio si alguna de las corrientes se desvia mas de un 25% del promedio de las 3.
            - Tensiones(V): Se considera desequilibrio si alguna de las tensiones se desvia mas de un 25% del promedio de las 3.

        Responde solamente con una tabla html con 2 columnas "cuentas sospechosas" y "justificacion".
        Aqui estan los datos:
            {excel_data}
        """

        return self._ask_model(prompt)

    def html_table_formatting(self, html_table: str) -> str:
        prompt = f"""
        Mira la siguiente tabla HTML corrupta, limpiala y dale formato:
            {html_table}

        - Devuelve solamente la tabla html, sin Markdown Code Block, sin comentarios.
        """

        return self._ask_model(prompt)
