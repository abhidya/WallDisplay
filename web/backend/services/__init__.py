"""Service package.

Keep package init light; importing concrete services here creates circular
import pressure during test collection and standalone module imports.
"""

__all__ = []
