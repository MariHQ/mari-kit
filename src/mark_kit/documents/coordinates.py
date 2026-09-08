"""Explicit conversion between character and encoded-byte source offsets."""

from __future__ import annotations

import codecs
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceCoordinateMap:
    encoding: str
    character_to_byte: tuple[int, ...]

    @classmethod
    def build(cls, text: str, *, encoding: str = "utf-8") -> SourceCoordinateMap:
        encoder = codecs.getincrementalencoder(encoding)()
        total = len(encoder.encode("", final=False))
        offsets = [total]
        for character in text:
            total += len(encoder.encode(character, final=False))
            offsets.append(total)
        total += len(encoder.encode("", final=True))
        offsets[-1] = total
        return cls(encoding=encoding, character_to_byte=tuple(offsets))

    @property
    def character_length(self) -> int:
        return len(self.character_to_byte) - 1

    @property
    def byte_length(self) -> int:
        return self.character_to_byte[-1]

    def to_byte(self, character_offset: int) -> int:
        if character_offset < 0 or character_offset > self.character_length:
            raise ValueError("character offset is outside the source")
        return self.character_to_byte[character_offset]

    def to_character(self, byte_offset: int, *, exact: bool = True) -> int:
        if byte_offset < 0 or byte_offset > self.byte_length:
            raise ValueError("byte offset is outside the source")
        try:
            return self.character_to_byte.index(byte_offset)
        except ValueError:
            if exact:
                raise ValueError("byte offset is not a character boundary") from None
            return next(
                index - 1
                for index, value in enumerate(self.character_to_byte)
                if value > byte_offset
            )

    def byte_span_to_characters(self, start: int, end: int) -> tuple[int, int]:
        if end < start:
            raise ValueError("span end must not precede start")
        return self.to_character(start), self.to_character(end)


def line_column(text: str, character_offset: int) -> tuple[int, int]:
    """Return a one-based line and zero-based character column."""

    if character_offset < 0 or character_offset > len(text):
        raise ValueError("character offset is outside the source")
    line = text.count("\n", 0, character_offset) + 1
    prior = text.rfind("\n", 0, character_offset)
    return line, character_offset if prior < 0 else character_offset - prior - 1
