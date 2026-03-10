"""USD utility helpers.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import logging
from typing import List, Optional, Tuple

from pxr import Usd

logger = logging.getLogger(__name__)


def collect_prims_of_type(
    parent_prim: Usd.Prim,
    prim_type: type,
    contains_str: Optional[str] = None,
    recursive: bool = False,
) -> Tuple[bool, List[Usd.Prim]]:
    """Collect prims of a given type under a parent prim.

    Args:
        parent_prim: Parent primitive to search under.
        prim_type: USD prim type to match.
        contains_str: Optional name substring filter.
        recursive: Whether to traverse descendants recursively.

    Returns:
        Tuple[bool, List[Usd.Prim]]: Success flag and list of matching prims.
    """
    if not parent_prim.IsValid():
        logger.warning("Invalid prim: %s", parent_prim)
        return False, []

    def _walk(prim: Usd.Prim):
        for child in prim.GetChildren():
            if child.IsA(prim_type):
                if not contains_str or contains_str in child.GetName():
                    yield child
            elif recursive:
                yield from _walk(child)

    return True, list(_walk(parent_prim))
