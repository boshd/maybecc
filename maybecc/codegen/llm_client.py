"""Anthropic API wrapper for code generation."""

from __future__ import annotations

import os

import anthropic


def generate_code(
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Call the Anthropic API to generate code from a prompt.

    Requires the ``ANTHROPIC_API_KEY`` environment variable to be set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get one at https://console.anthropic.com/"
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
