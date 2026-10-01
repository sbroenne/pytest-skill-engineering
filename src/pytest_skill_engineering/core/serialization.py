"""Lossless serialization and strict loading of the current native report schema."""

from __future__ import annotations

import base64
import binascii
import sys
from dataclasses import fields, is_dataclass
from types import UnionType
from typing import TYPE_CHECKING, Any, Literal, TypeVar, Union, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from pytest_skill_engineering.reporting.collector import SuiteReport

T = TypeVar("T")


def serialize_dataclass(obj: Any) -> Any:
    """Convert public dataclass fields recursively, encoding bytes as base64."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: serialize_dataclass(getattr(obj, field.name))
            for field in fields(obj)
            if not field.name.startswith("_")
        }
    if isinstance(obj, (list, tuple)):
        return [serialize_dataclass(item) for item in obj]
    if isinstance(obj, dict):
        return {key: serialize_dataclass(value) for key, value in obj.items()}
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    return obj


def _decode_dataclass(cls: type[T], data: Any, *, path: str) -> T:
    from pytest_skill_engineering.copilot.requests import RequestAudit
    from pytest_skill_engineering.core.result import EvalResult

    if not is_dataclass(cls):
        raise TypeError(f"{cls} is not a native report dataclass")
    context = f"{cls.__name__} at {path}"
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be an object")
    public_fields = [field for field in fields(cls) if not field.name.startswith("_")]
    unexpected = data.keys() - {field.name for field in public_fields}
    if unexpected:
        raise ValueError(f"{context} has unexpected fields: {sorted(unexpected)}")
    annotations = get_type_hints(
        cls,
        globalns={
            **vars(sys.modules[cls.__module__]),
            "RequestAudit": RequestAudit,
            "EvalResult": EvalResult,
        },
    )
    values: dict[str, Any] = {}
    for field in public_fields:
        if field.name not in data:
            raise ValueError(f"{context} is missing required field {field.name!r}")
        values[field.name] = _decode_value(
            annotations[field.name], data[field.name], path=f"{path}.{field.name}"
        )
    return cls(**values)


def _decode_value(annotation: Any, value: Any, *, path: str) -> Any:
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if annotation is Any:
        return value
    if origin in (Union, UnionType):
        if value is None and type(None) in arguments:
            return None
        alternatives = [item for item in arguments if item is not type(None)]
        if len(alternatives) != 1:
            raise TypeError(f"Unsupported native report field type at {path}: {annotation}")
        return _decode_value(alternatives[0], value, path=path)
    if origin is Literal:
        if value not in arguments:
            raise ValueError(f"{path} must be one of {arguments!r}")
        return value
    if origin in (list, tuple):
        if not isinstance(value, list):
            raise ValueError(f"{path} must be a list")
        if origin is list:
            return [
                _decode_value(arguments[0], item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if len(value) != len(arguments):
            raise ValueError(f"{path} must contain {len(arguments)} values")
        return tuple(
            _decode_value(kind, item, path=f"{path}[{index}]")
            for index, (kind, item) in enumerate(zip(arguments, value, strict=True))
        )
    if origin is dict:
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        return {
            _decode_value(arguments[0], key, path=f"{path} key"): _decode_value(
                arguments[1], item, path=f"{path}[{key!r}]"
            )
            for key, item in value.items()
        }
    if isinstance(annotation, type) and is_dataclass(annotation):
        return _decode_dataclass(annotation, value, path=path)
    if annotation is bytes:
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a base64 string")
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"{path} contains invalid base64 image data") from exc
    if annotation is float:
        if type(value) not in (int, float):
            raise ValueError(f"{path} must be a number")
        return float(value)
    if annotation in (str, int, bool) and type(value) is annotation:
        return value
    raise ValueError(f"{path} must be {annotation.__name__}")


def deserialize_suite_report(data: dict[str, Any]) -> SuiteReport:
    """Load every current producer field; missing evidence is never inferred."""
    from pytest_skill_engineering.reporting.collector import SuiteReport

    payload = {key: value for key, value in data.items() if key != "schema_version"}
    return _decode_dataclass(SuiteReport, payload, path="suite")
