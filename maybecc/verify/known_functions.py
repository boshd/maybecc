"""Registry of known functions available in contract expressions.

Maps function names to their C linkage requirements so the harness
generator can emit correct #include directives and linker flags.
"""

from __future__ import annotations

from typing import TypedDict


class KnownFunction(TypedDict, total=False):
    header: str
    link_flags: list[str]
    signature: str
    notes: str


KNOWN_FUNCTIONS: dict[str, KnownFunction] = {
    "crc32": {
        "header": "<zlib.h>",
        "link_flags": ["-lz"],
        "signature": "unsigned long crc32(unsigned long crc, const unsigned char *buf, unsigned int len)",
        "notes": "Initial crc should be 0 for standalone use",
    },
    "strlen": {
        "header": "<string.h>",
        "link_flags": [],
        "signature": "size_t strlen(const char *s)",
    },
    "memcmp": {
        "header": "<string.h>",
        "link_flags": [],
        "signature": "int memcmp(const void *s1, const void *s2, size_t n)",
    },
    "memcpy": {
        "header": "<string.h>",
        "link_flags": [],
        "signature": "void *memcpy(void *dest, const void *src, size_t n)",
    },
    "memset": {
        "header": "<string.h>",
        "link_flags": [],
        "signature": "void *memset(void *s, int c, size_t n)",
    },
}
