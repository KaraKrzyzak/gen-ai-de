"""Imports every parser module so their @register decorators run.

One file per parser type (aka.py, fitssey.py, ...). To add a new type: create
<type>.py with a function decorated by @register("<type>") and import it here.
"""
import aka  # noqa: F401  (registers "aka")
import fitssey  # noqa: F401  (registers "fitssey")
import perfectgym  # noqa: F401  (registers "perfectgym")
import wod_guru  # noqa: F401  (registers "wod_guru")
import fitro  # noqa: F401  (registers "fitro")
import activklub  # noqa: F401  (registers "activklub")
import efitness  # noqa: F401  (registers "efitness")
import delta_sections  # noqa: F401  (registers "delta_sections")
