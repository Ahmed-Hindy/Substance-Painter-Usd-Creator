"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""


from pxr import Usd



def collect_prims_of_type(parent_prim, prim_type, contains_str=None, recursive=False):
    """
    gets a list of prims of specific type under a parent prim
    :param parent_prim: parent primitive
    :type parent_prim: Usd.Prim
    :param prim_type: primitive type we are selecting
    :type prim_type: UsdShade.Material
    :return: list of all prims found
    :rtype: (bool, List[Usd.Prim])
    """
    if not parent_prim.IsValid():
        print(f"Invalid prim: {parent_prim}")
        return False, []

    prims_found = []

    def _recursive_search(prim: Usd.Prim):
        """
        inner function. Don't use
        """
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


