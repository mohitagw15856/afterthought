"""verify: tag every claim in a model output as SOURCED, INFERRED or UNVERIFIED."""

from .pipeline import VerifyReport, verify_text

__all__ = ["VerifyReport", "verify_text"]
