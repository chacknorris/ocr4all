from __future__ import annotations
"""
LLM integration for complex field extraction.
Supports local Ollama and external APIs (OpenAI-compatible).
"""
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from core.config import get_settings

settings = get_settings()


@dataclass
class LLMConfig:
    provider: str = "ollama"  # "ollama", "openai", "anthropic"
    model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 60


@dataclass
class ExtractionPrompt:
    """Prompt template for field extraction."""
    system: str
    user_template: str


# Default extraction prompts
EXTRACTION_PROMPTS = {
    "default": ExtractionPrompt(
        system="""Eres un asistente especializado en extraer información de documentos chilenos (facturas, boletas, guías de despacho).
Tu tarea es extraer campos específicos del texto OCR proporcionado.
Responde SOLO con un JSON válido, sin explicaciones adicionales.
Si no encuentras un campo, usa null como valor.""",
        user_template="""Extrae los siguientes campos del texto de este documento:

Campos a extraer:
{fields}

Texto del documento:
```
{text}
```

Responde con un JSON con esta estructura:
{schema}"""
    ),
    "invoice": ExtractionPrompt(
        system="""Eres un experto en procesamiento de facturas electrónicas chilenas.
Extrae la información solicitada del texto OCR.
Los RUTs tienen formato XX.XXX.XXX-X o XXXXXXXX-X.
Las fechas pueden estar en formato DD/MM/YYYY o DD-MM-YYYY.
Los montos pueden tener puntos como separadores de miles.
Responde SOLO con JSON válido.""",
        user_template="""Extrae la información de esta factura chilena:

Campos requeridos:
- rut_emisor: RUT del emisor/vendedor
- razon_social_emisor: Nombre o razón social del emisor
- rut_receptor: RUT del receptor/cliente
- razon_social_receptor: Nombre o razón social del receptor
- numero_factura: Número de la factura
- fecha_emision: Fecha de emisión (formato YYYY-MM-DD)
- monto_neto: Monto neto sin IVA (solo número)
- monto_iva: Monto del IVA (solo número)
- monto_total: Monto total (solo número)
- direccion_emisor: Dirección del emisor
- giro_emisor: Giro comercial del emisor

Texto OCR:
```
{text}
```

Responde con JSON:"""
    ),
    "receipt": ExtractionPrompt(
        system="""Eres un experto en procesamiento de boletas electrónicas chilenas.
Extrae la información del texto OCR proporcionado.
Responde SOLO con JSON válido.""",
        user_template="""Extrae la información de esta boleta:

Campos requeridos:
- rut_emisor: RUT del comercio
- razon_social: Nombre del comercio
- numero_boleta: Número de boleta
- fecha: Fecha (formato YYYY-MM-DD)
- total: Monto total (solo número)
- items: Lista de productos/servicios con nombre, cantidad y precio

Texto OCR:
```
{text}
```

Responde con JSON:"""
    ),
}


class LLMExtractor:
    """LLM-based field extractor."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout)

    async def close(self):
        await self.client.aclose()

    async def extract(
        self,
        text: str,
        fields: list[dict],
        prompt_type: str = "default",
    ) -> dict[str, Any]:
        """
        Extract fields from text using LLM.

        Args:
            text: OCR text to process
            fields: List of field definitions with 'name', 'label', 'description'
            prompt_type: Type of prompt to use

        Returns:
            Dictionary of extracted field values
        """
        prompt_template = EXTRACTION_PROMPTS.get(prompt_type, EXTRACTION_PROMPTS["default"])

        # Build field descriptions
        fields_desc = "\n".join(
            f"- {f['name']}: {f.get('description', f.get('label', f['name']))}"
            for f in fields
        )

        # Build expected schema
        schema = {f["name"]: f.get("example", "valor o null") for f in fields}
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)

        # Build prompt
        user_prompt = prompt_template.user_template.format(
            fields=fields_desc,
            text=text[:8000],  # Limit text length
            schema=schema_str,
        )

        # Call LLM
        response = await self._call_llm(prompt_template.system, user_prompt)

        # Parse JSON response
        return self._parse_json_response(response)

    async def extract_with_schema(
        self,
        text: str,
        schema: dict,
        prompt_type: str = "default",
    ) -> dict[str, Any]:
        """
        Extract fields using a JSON schema definition.
        """
        fields = [
            {"name": k, "description": v.get("description", k)}
            for k, v in schema.get("properties", {}).items()
        ]
        return await self.extract(text, fields, prompt_type)

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM API based on provider."""
        if self.config.provider == "ollama":
            return await self._call_ollama(system_prompt, user_prompt)
        elif self.config.provider == "openai":
            return await self._call_openai(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.provider}")

    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama API."""
        url = f"{self.config.base_url}/api/generate"

        payload = {
            "model": self.config.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama API error: {e}")

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI-compatible API."""
        url = f"{self.config.base_url}/v1/chat/completions"

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            raise RuntimeError(f"OpenAI API error: {e}")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        # Try to extract JSON from response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first and last lines (code block markers)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)

        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return empty dict if parsing fails
        return {}


async def extract_with_llm(
    text: str,
    doc_type: str = "default",
    config: Optional[LLMConfig] = None,
) -> dict[str, Any]:
    """
    Convenience function to extract fields using LLM.

    Args:
        text: OCR text
        doc_type: Document type for prompt selection
        config: LLM configuration

    Returns:
        Extracted fields as dictionary
    """
    extractor = LLMExtractor(config)
    try:
        prompt_type = {
            "factura": "invoice",
            "boleta": "receipt",
        }.get(doc_type, "default")

        # Define fields based on doc type
        if doc_type == "factura":
            fields = [
                {"name": "rut_emisor", "label": "RUT Emisor"},
                {"name": "razon_social_emisor", "label": "Razón Social Emisor"},
                {"name": "rut_receptor", "label": "RUT Receptor"},
                {"name": "numero_factura", "label": "Número Factura"},
                {"name": "fecha_emision", "label": "Fecha Emisión"},
                {"name": "monto_neto", "label": "Monto Neto"},
                {"name": "monto_iva", "label": "IVA"},
                {"name": "monto_total", "label": "Total"},
            ]
        elif doc_type == "boleta":
            fields = [
                {"name": "rut_emisor", "label": "RUT Emisor"},
                {"name": "numero_boleta", "label": "Número Boleta"},
                {"name": "fecha", "label": "Fecha"},
                {"name": "total", "label": "Total"},
            ]
        else:
            fields = []

        return await extractor.extract(text, fields, prompt_type)
    finally:
        await extractor.close()
