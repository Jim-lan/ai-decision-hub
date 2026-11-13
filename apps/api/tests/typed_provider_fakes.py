"""Typed, deterministic ProviderPort fakes shared by contract tests."""

from dataclasses import replace

from app.ports import (
    CostEstimate,
    GenerationRequest,
    GenerationResult,
    ModelCapabilities,
    ProviderPort,
)


class StaticFixtureProvider(ProviderPort):
    def __init__(self, result: GenerationResult, capabilities: ModelCapabilities):
        self.result = result
        self.model_capabilities = capabilities

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.requested_model_id != self.result.requested_model_id:
            raise ValueError("Fixture does not match the requested model")
        actual = self.result.actual_model_id
        if self.result.status == "succeeded" and actual is not None and actual not in request.allowed_model_ids:
            return replace(self.result, status="failed", content=None, error_code="invalid_response")
        return self.result

    async def capabilities(self, model_id: str) -> ModelCapabilities:
        return replace(self.model_capabilities, model_id=model_id)

    async def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        return CostEstimate(
            amount_microusd=0,
            input_token_bound=len(request.model_visible_input),
            output_token_bound=request.max_output_tokens,
            price_verified_at=self.model_capabilities.verified_at,
        )


class MappingFixtureProvider(ProviderPort):
    def __init__(
        self,
        results: dict[str, GenerationResult],
        capabilities: ModelCapabilities,
    ):
        self.results = results
        self.model_capabilities = capabilities

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        result = self.results[request.requested_model_id]
        actual = result.actual_model_id
        if result.status == "succeeded" and actual is not None and actual not in request.allowed_model_ids:
            return replace(result, status="failed", content=None, error_code="invalid_response")
        return result

    async def capabilities(self, model_id: str) -> ModelCapabilities:
        return replace(self.model_capabilities, model_id=model_id)

    async def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        return CostEstimate(
            amount_microusd=0,
            input_token_bound=len(request.model_visible_input),
            output_token_bound=request.max_output_tokens,
            price_verified_at=self.model_capabilities.verified_at,
        )


def require_provider(provider: ProviderPort) -> ProviderPort:
    """Make structural conformance a static type-checking obligation."""
    return provider
