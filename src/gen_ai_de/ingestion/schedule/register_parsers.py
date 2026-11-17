"""Imports every parser module so their @register decorators run.

One file per parser type (aka.py, fitssey.py, ...). To add a new type: create
<type>.py with a function decorated by @register("<type>") and add it to the import below.
"""

from gen_ai_de.ingestion.schedule import (  # noqa: F401
    activklub,
    aka,
    delta_sections,
    efitness,
    fitro,
    fitssey,
    perfectgym,
    wod_guru,
)
