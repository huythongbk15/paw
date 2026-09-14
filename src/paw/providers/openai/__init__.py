"""
PAW Providers — OpenAI Cloud Provider Adapter (E4-11..14)

Provides a cloud teacher baseline and bounded training capability via the
OpenAI API. This is a replaceable adapter — injected via parameters,
not hardcoded in PAW core. Implements both ModelProvider (for baseline
measurement) and TrainingProvider (for bounded training).

Pure stdlib HTTP (urllib) wrapped in asyncio.to_thread to stay async
without adding third-party HTTP dependencies.

Requires OPENAI_API_KEY environment variable. If absent, the provider
reports available=False and all measurement functions degrade gracefully
(zero accuracy / NotImplementedError-free fallback).
"""

from paw.providers.openai.provider import (
    OpenAITrainingProvider,
    TrainingProvider,
    estimate_training_cost,
)

__all__ = ["OpenAITrainingProvider", "TrainingProvider", "estimate_training_cost"]
