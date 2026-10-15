"""Small, versioned analytical tool protocol independent of an LLM provider."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRequest(StrictModel):
    run_id: str
    product: str
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    scope: Literal["overview", "monitor", "release", "evidence", "category"] = "overview"
    release_id: str | None = None
    category: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=16)
    effort: Literal["low", "medium", "high"] | None = "medium"


class ToolCall(StrictModel):
    tool: Literal["review_breakdown", "find_evidence", "query_schema", "read_only_sql"]
    group_by: Literal["language", "week", "playtime"]
    language: str | None
    category: str | None
    recommended: bool | None
    start: str | None
    end: str | None
    sql: str | None = Field(default=None, max_length=12000)


class MetricReference(StrictModel):
    fact_id: str
    value: float


class Claim(StrictModel):
    text: str
    status: Literal["supported", "hypothesis", "insufficient"]
    fact_ids: list[str]
    evidence_ids: list[str]


class AgentAnswer(StrictModel):
    mode: Literal["answer", "tool_request"]
    summary: str
    claims: list[Claim] = Field(max_length=8)
    metrics: list[MetricReference] = Field(max_length=24)
    tool_calls: list[ToolCall] = Field(max_length=2)
    limitations: list[str] = Field(max_length=10)
    next_actions: list[str] = Field(max_length=8)


def output_schema() -> dict:
    schema = AgentAnswer.model_json_schema()

    def required_fields(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                value["required"] = list(value.get("properties", {}))
                value["additionalProperties"] = False
            for child in value.values():
                required_fields(child)
        elif isinstance(value, list):
            for child in value:
                required_fields(child)

    required_fields(schema)
    return schema
