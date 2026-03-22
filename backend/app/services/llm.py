from typing import Any

from pydantic import BaseModel, ValidationError


class ExtractionSchema(BaseModel):
    name: str
    summary: str
    facts: list[str]


class LLMService:
    """Structured-output wrapper; does not invent data.

    This implementation intentionally requires upstream fact bundles and validates
    shape before accepting model output.
    """

    @staticmethod
    def validate_structured_output(payload: dict[str, Any]) -> ExtractionSchema | None:
        try:
            return ExtractionSchema.model_validate(payload)
        except ValidationError:
            return None
