"""Maps the `parser` value from list_Schedule.yml to a Python function.
 
A parser is any callable:   parser(config: dict) -> pandas.DataFrame
where `config` is the full YAML entry (url, studio_id, latitude, ...).
"""
from __future__ import annotations
 
from typing import Callable
 
import pandas as pd
 
ParserFunc = Callable[[dict], pd.DataFrame]
_PARSERS: dict[str, ParserFunc] = {}
 
 
def register(name: str) -> Callable[[ParserFunc], ParserFunc]:
    """Decorator: @register("aka") makes `parser: "aka"` in the YAML work."""
    def decorator(func: ParserFunc) -> ParserFunc:
        if name in _PARSERS:
            raise ValueError(f"Parser '{name}' is already registered")
        _PARSERS[name] = func
        return func
    return decorator
 
 
def get_parser(name: str) -> ParserFunc:
    try:
        return _PARSERS[name]
    except KeyError:
        known = ", ".join(sorted(_PARSERS)) or "none"
        raise KeyError(f"Unknown parser '{name}'. Registered: {known}") from None
 