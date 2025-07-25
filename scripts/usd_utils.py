import os
from datetime import datetime
from pxr import Usd, UsdShade, UsdGeom, Sdf, UsdRender, UsdSkel



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


def unassign_material_from_prim(prim: Usd.Prim):
    """
     unassigns material from a prim
     :rtype: bool
    """
    return UsdShade.MaterialBindingAPI(prim).Unbind()


def unassign_material_from_prims(prims: Usd.Prim):
    """
     unassigns material from a list of prims
    """
    for prim in prims:
        unassign_material_from_prim(prim)

def unassign_material_from_stage(stage:Usd.Stage, prim_type=UsdGeom.Mesh):
    """
     unassigns material from an entire stage
    """
    prims = stage.Traverse()
    for prim in prims:
        if prim.IsA(prim_type):
            check = unassign_material_from_prim(prim)
            if not check:
                raise Exception(f"Couldn't unbing material from: '{prim.GetPath()}'")
            # print(f"Unassigned material on: {prim.GetPath()}")


def set_layer_metadata(usd_layer):
    """
    [WIP not working] sets layer metadata on a usd layer
    :param usd_layer (Sdf.Layer): an editable Sdf.Layer object
    """
    username = os.getlogin()
    # machine_name = socket.gethostname()
    date = datetime.today()
    formatted_date = date.strftime("%Y-%m-%d")

    usd_layer.SetMetadata('author', username)
    usd_layer.SetMetadata('creationDate', formatted_date)
    usd_layer.SetMetadata('description', '')



def get_render_camera_from_rendersettings(stage):
    """
    given a usd stage, get the render settings prim and from it extract the render camera if it exists
    :param stage: input stage
    :return: does_camera_exists, camera_prim_path
    :rtype: (bool, str)
    """
    if not stage:
        return False, f"Couldn't get Input Stage, probably node is uncooked"

    render_settings_prim = None
    for prim in stage.Traverse():
        if prim.GetPrimTypeInfo().GetTypeName() == 'RenderSettings':
            render_settings_prim = prim
            break
    if not render_settings_prim:
        return False, f"Couldn't get Render Settings Prim"

    render_settings = UsdRender.Settings(render_settings_prim)
    camera_rel: Usd.Relationship = render_settings.GetCameraRel()
    camera_path: Sdf.Path = camera_rel.GetTargets()[0]
    camera_path_str: str = camera_path.pathString
    camera_prim: Usd.Prim = stage.GetPrimAtPath(camera_path)

    cam_exists = False
    if camera_prim.IsValid():
        cam_exists = True

    return cam_exists, camera_path_str


def delete_prim_attributes(prim):
    """
    given a prim, removes all it's attributes and properties.
    """
    for attr in prim.GetAttributes():
        prim.RemoveProperty(attr.GetName())
    for prop in prim.GetProperties():
        prim.RemoveProperty(prop.GetName())


def copy_prim_to_new_location(stage, prim, new_path):
    edit_layer = stage.GetEditTarget().GetLayer()
    prim_path = prim.GetPath()
    for spec in prim.GetPrimStack():
        layer = spec.layer
        Sdf.CopySpec(layer, prim_path, edit_layer, new_path)
    return stage.GetPrimAtPath(new_path)


def ref_prim_to_new_location_local(stage, orig_primpath: str, referenced_primpath: str):
    """
    adds an internal reference on 'orig_primpath' pointing to the 'referenced_primpath'
    """
    dup_prim = stage.OverridePrim(orig_primpath)
    dup_prim.GetReferences().AddInternalReference(referenced_primpath)


def ref_prim_to_new_location(stage, layer, referenced_prim, orig_primpath: str):
    """
    adds a layer reference on 'orig_primpath' pointing to the 'referenced_primpath'
    """
    referenced_primpath = referenced_prim.GetPath()
    dup_prim = stage.OverridePrim(orig_primpath)
    dup_prim.GetReferences().AddReference(layer.identifier, referenced_primpath)


def set_render_and_proxy_relationship(stage, render_prim_path: str, proxy_prim_path: str):
    """
    sets relationship between 2 prims, one will be proxy and other render.
    """
    # Get the render and proxy prims at the specified paths
    render_prim = stage.GetPrimAtPath(render_prim_path)
    proxy_prim = stage.GetPrimAtPath(proxy_prim_path)

    # Check if the prims are valid
    if not render_prim.IsValid() or not proxy_prim.IsValid():
        print(f"Invalid prims at '{render_prim_path}' or '{proxy_prim_path}'")
        return

    proxy_rel = render_prim.CreateRelationship("proxyPrim")
    proxy_rel.SetTargets([proxy_prim.GetPath()])
    render_prim.CreateAttribute("purpose", Sdf.ValueTypeNames.String).Set("render")
    proxy_prim.CreateAttribute("purpose", Sdf.ValueTypeNames.String).Set("proxy")


def create_scope_for_mesh(stage, prim):
    """
    given a prim (e.g. Mesh prim), will create next to it 2 new prims:
        /<parent_prim>/geo/render
        /<parent_prim>/geo/proxy
    """
    # Get the parent path of the current mesh
    parent_path = prim.GetPath().GetParentPath()

    geo_prim_path = parent_path.AppendChild("geo")
    geo_prim = stage.DefinePrim(geo_prim_path, "Scope")

    proxy_scope_prim_path = geo_prim_path.AppendChild("proxy")
    proxy_scope_prim = stage.DefinePrim(proxy_scope_prim_path, "Scope")
    render_scope_prim_path = geo_prim_path.AppendChild("render")
    render_scope_prim = stage.DefinePrim(render_scope_prim_path, "Scope")

    return render_scope_prim_path, proxy_scope_prim_path


def get_elementsize(mesh_prim):
    """
    [not used]
    """
    joint_weights_attr = mesh_prim.GetAttribute("primvars:skel:jointWeights")
    joint_weights_primvar = UsdGeom.Primvar(joint_weights_attr)

    if joint_weights_primvar:
        element_size = joint_weights_primvar.GetElementSize()
        mesh_prim.CreateAttribute("primvars:skel:jointWeights_elementSize", Sdf.ValueTypeNames.Int).Set(element_size)


def create_variantset_and_reference_contents(stage, orig_primpath, new_primpath, variant_set_name, variant_name):
    """
    [DOCSTRING WIP] Creates a Variant Set on 'new_primpath' that references all children of 'orig_primpath'
    """
    UsdGeom.Xform.Define(stage, new_primpath)
    new_prim = stage.GetPrimAtPath(new_primpath)
    orig_prim = stage.GetPrimAtPath(orig_primpath)

    vset = new_prim.GetVariantSets().GetVariantSet(variant_set_name)
    if not vset:
        vset = new_prim.GetVariantSets().AddVariantSet(variant_set_name)
        print(f"vset doesn't exist yet!")

    vset.AddVariant(variant_name)
    vset.SetVariantSelection(variant_name)
    with vset.GetVariantEditContext():
        orig_children = orig_prim.GetChildren()
        for orig_childprim in orig_children:
            childprim_path = orig_childprim.GetPath().pathString
            childprim_name = orig_childprim.GetName()
            ref_prim_to_new_location_local(stage, f"{new_primpath}/{childprim_name}", childprim_path)


def copy_prim_properties(src_prim, dst_prim):
    """
    copies all prim properties from 'src_prim' to 'dst_prim'.
    """
    time = Usd.TimeCode.Default()

    # copy attributes:
    for attr in src_prim.GetAttributes():
        name = attr.GetName()
        type_name = attr.GetTypeName()
        dst_attr = dst_prim.CreateAttribute(name, type_name)
        if not attr.HasAuthoredValueOpinion():
            continue
        value = attr.Get(time)
        if not value:
            continue

        dst_attr.Set(value, time)
        src_metadata_keys = attr.GetAllMetadata()
        for key, value in src_metadata_keys.items():
            dst_attr.SetMetadata(key, value)
            # print(f"DEBUG:  {value=}")

    # copy schema:
    for schema in src_prim.GetAppliedSchemas():
        dst_prim.ApplyAPI(schema)

    # copy relationships:
    for rel in src_prim.GetRelationships():
        name = rel.GetName()
        # print(f"DEBUG:  rel {name=}")
        dst_rel = dst_prim.CreateRelationship(name)
        targets = rel.GetTargets()
        if targets:
            dst_rel.SetTargets(targets)

        metadata_dict = rel.GetAllMetadata()
        for key, value in metadata_dict.items():
            dst_rel.SetMetadata(key, value)

