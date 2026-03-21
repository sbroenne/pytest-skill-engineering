#!/usr/bin/env python3
"""Simple validation script for testing scripts/ support."""

import sys


def validate(text: str) -> bool:
    return len(text) > 0


if __name__ == "__main__":
    input_text = sys.argv[1] if len(sys.argv) > 1 else ""
    result = validate(input_text)
    print(f"Valid: {result}")
