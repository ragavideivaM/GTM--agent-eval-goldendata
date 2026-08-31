"""Token, tool, and estimated-cost reporting contracts."""

from pydantic import BaseModel, Field


class ApiUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)


class CostEstimate(BaseModel):
    operation: str
    model: str
    input_token_budget: int = Field(ge=0)
    output_token_cap: int = Field(ge=0)
    tool_call_cap: int = Field(default=0, ge=0)
    estimated_ceiling_usd: float = Field(ge=0)
    is_hard_dollar_cap: bool = False
