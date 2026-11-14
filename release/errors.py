"""Shared release-pipeline errors.

The release tools are intentionally fail-closed. Every validation or signing
problem is reported as a :class:`ReleaseError` so the command-line entry point
can print a short message without a traceback or key material.
"""

from __future__ import annotations


class ReleaseError(ValueError):
    """A release-pipeline refusal that is safe to show to the operator."""


class ConfigError(ReleaseError):
    """The signing configuration is missing, public, or unsafe."""


class ChecksumError(ReleaseError):
    """An artifact, manifest, or checksum did not verify."""


class ApprovalError(ReleaseError):
    """Explicit human approval is missing, stale, or does not match."""


class PipelineError(ReleaseError):
    """A release step cannot proceed safely."""
