from __future__ import annotations

from typing import TypeAlias

# Definition of basic types used for Serializable configuration generation
ScalarType: TypeAlias = str | int | float | bool
SerializableType: TypeAlias = (
    ScalarType | list["SerializableType"] | dict[str, "SerializableType"] | None
)
Config: TypeAlias = dict[str, SerializableType]

__all__ = ["ScalarType", "Config"]
