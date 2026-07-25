from typing import Literal

from pydantic import BaseModel, Field


class CompanionAssessment(BaseModel):
    """Structured output requested from Claude for a single check-in."""

    message: str = Field(description="Warm, supportive coaching message, under 100 words.")
    risk_level: Literal["low", "medium", "high"]
    suggested_action: str = Field(description="One concrete, actionable next step.")
