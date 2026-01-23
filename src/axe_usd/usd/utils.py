"""USD utility helpers.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

from typing import List, Optional, Tuple

from pxr import Usd



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
        print(f"Invalid prim: {parent_prim}")
        return False, []

    prims_found = []

    def _recursive_search(prim: Usd.Prim) -> List[Usd.Prim]:
        """Recursively collect matching prims."""
        for child_prim in prim.GetChildren():  # child_prim: Usd.Prim
            if child_prim.IsA(prim_type):
                if contains_str:
                    if contains_str in child_prim.GetName():
                        prims_found.append(child_prim)
                else:
                    prims_found.append(child_prim)
            else:
                if recursive:  # if prim not the type we want, go recurse inside
                    _recursive_search(child_prim)
        return prims_found

    all_prims_found = _recursive_search(parent_prim)
    return True, all_prims_found


