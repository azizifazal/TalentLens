from __future__ import annotations

from decimal import Decimal
from typing import Any


def floats_to_decimal(obj: Any) -> Any:
    """Recursively convert Python floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [floats_to_decimal(v) for v in obj]
    return obj


def decimals_to_float(obj: Any) -> Any:
    """Recursively convert DynamoDB Decimal values back to Python floats/ints."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimals_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimals_to_float(v) for v in obj]
    return obj
