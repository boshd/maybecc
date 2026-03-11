"""Extract C source code from LLM response text."""

from __future__ import annotations

import re


def extract_c_source(response: str) -> str:
    """Extract C source code from an LLM response containing markdown code blocks.

    Looks for ```c ... ``` blocks first.  Falls back to any ``` ... ``` block.
    If nothing is found, returns the raw response as a last resort.
    """
    c_blocks = re.findall(r"```c\n(.*?)```", response, re.DOTALL)
    if c_blocks:
        return max(c_blocks, key=len).strip()

    any_blocks = re.findall(r"```\n(.*?)```", response, re.DOTALL)
    if any_blocks:
        return max(any_blocks, key=len).strip()

    return response.strip()


def extract_files(response: str) -> dict[str, str]:
    """Extract named .c/.h files from an LLM response.

    Handles patterns like:
        ```c filename.c
        ...code...
        ```
    Falls back to a single unnamed source file.
    """
    named = re.findall(
        r"```c\s+(\S+\.(?:c|h))\n(.*?)```", response, re.DOTALL
    )
    if named:
        return {name: code.strip() for name, code in named}

    source = extract_c_source(response)
    if source:
        return {"program.c": source}

    return {}
