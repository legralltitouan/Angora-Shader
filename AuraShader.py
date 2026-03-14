import bpy
import os

bl_info = {
    "name": "Paint Shader Organized",
    "author": "TonNom",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Paint",
    "description": "Applique un shader paint organisé avec image brush",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

# ==========================================
# 1. CRÉATION DU GROUPE DE SHADER PAINT PAR DÉFAUT
# ==========================================
def create_paint_shader_group():
    """
    Crée un node group "Paint_Shader_Group" qui gère le shader toon style paint.
    Il contient la logique de base color, shadow, light blending et normal input.
    """
    group_name = "Paint_Shader_Group"

    # Vérifie si le groupe existe déjà
    group = bpy.data.node_groups.get(group_name)
    if group:
        return group

    # Création du node group
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    nodes = group.nodes
    links = group.links
    nodes.clear()

    # -------------------
    # INPUT / OUTPUT NODES
    # -------------------
    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-900, 0)

    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (900, 0)

    # Création des sockets du node group
    group.interface.new_socket("Base Color", in_out='INPUT', socket_type='NodeSocketColor').default_value = (0.396, 0.765, 0.996, 1.0)
    group.interface.new_socket("Shadow Color", in_out='INPUT', socket_type='NodeSocketColor').default_value = (0.188, 0.353, 0.737, 1.0)
    group.interface.new_socket("Blend Light Color", in_out='INPUT', socket_type='NodeSocketFloat').default_value = 0.1
    group.interface.new_socket("Cel Shaded?", in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
    group.interface.new_socket("From Min", in_out='INPUT', socket_type='NodeSocketFloat').default_value = 0.0
    group.interface.new_socket("From Max", in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
    group.interface.new_socket("Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket("Result", in_out='OUTPUT', socket_type='NodeSocketColor')

    # -------------------
    # DIFFUSE NODE
    # -------------------
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.location = (-650, 0)
    diffuse.inputs["Roughness"].default_value = 0

    # Conversion shader → color
    shader_to_rgb = nodes.new("ShaderNodeShaderToRGB")
    shader_to_rgb.location = (-450, 0)

    # -------------------
    # LIGHT ANALYSIS (HSV)
    # -------------------
    separate_light = nodes.new("ShaderNodeSeparateColor")
    separate_light.location = (-200, 120)
    separate_light.mode = 'HSV'

    map_range = nodes.new("ShaderNodeMapRange")
    map_range.location = (50, 120)
    map_range.clamp = True

    cell_math = nodes.new("ShaderNodeMath")
    cell_math.location = (250, 120)
    cell_math.operation = 'CEIL'  # Toony threshold

    # -------------------
    # SHADOW MIX
    # -------------------
    mix_shadow = nodes.new("ShaderNodeMix")
    mix_shadow.location = (450, 120)
    mix_shadow.data_type = 'FLOAT'

    # -------------------
    # LIGHT COLOR BLEND (HSV)
    # -------------------
    separate_color = nodes.new("ShaderNodeSeparateColor")
    separate_color.location = (-200, -200)
    separate_color.mode = 'HSV'

    combine_color = nodes.new("ShaderNodeCombineColor")
    combine_color.location = (50, -200)
    combine_color.mode = 'HSV'
    combine_color.inputs[2].default_value = 1.0  # Value

    mix_color = nodes.new("ShaderNodeMix")
    mix_color.location = (300, -200)
    mix_color.data_type = 'RGBA'

    # -------------------
    # FINAL MIX
    # -------------------
    final_mix = nodes.new("ShaderNodeMix")
    final_mix.location = (650, 0)
    final_mix.data_type = 'RGBA'

    # -------------------
    # LIENS DU NODE GROUP
    # -------------------
    links.new(group_in.outputs[6], diffuse.inputs[2])  # Normal vers diffuse
    links.new(diffuse.outputs[0], shader_to_rgb.inputs[0])

    links.new(shader_to_rgb.outputs[0], separate_light.inputs[0])
    links.new(shader_to_rgb.outputs[0], separate_color.inputs[0])

    links.new(separate_light.outputs[2], map_range.inputs[0])  # Value channel
    links.new(group_in.outputs[4], map_range.inputs[1])        # From Min
    links.new(group_in.outputs[5], map_range.inputs[2])        # From Max
    links.new(map_range.outputs[0], cell_math.inputs[0])

    # Shadow threshold
    links.new(group_in.outputs[3], mix_shadow.inputs[0])
    links.new(cell_math.outputs[0], mix_shadow.inputs['A'])
    links.new(cell_math.outputs[0], mix_shadow.inputs['B'])

    # HSV rebuild
    links.new(separate_color.outputs[0], combine_color.inputs[0])
    links.new(separate_color.outputs[1], combine_color.inputs[1])

    # Light blend
    links.new(combine_color.outputs[0], mix_color.inputs[7])
    links.new(group_in.outputs[0], mix_color.inputs[6])
    links.new(group_in.outputs[2], mix_color.inputs[0])

    # Final mix
    links.new(mix_color.outputs['Result'], final_mix.inputs['B'])
    links.new(mix_shadow.outputs[0], final_mix.inputs[0])
    links.new(group_in.outputs[1], final_mix.inputs[6])
    links.new(final_mix.outputs['Result'], group_out.inputs['Result'])

    return group

# ==========================================
# 2. CRÉATION DU MATÉRIEL PAINT PAR DÉFAUT
# ==========================================
def create_default_paint_material(obj_name):
    """
    Crée un matériau avec nodes paint shader + random color + alpha system
    """
    mat_name = f"Paint_Material_{obj_name}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # -------------------
    # RANDOM COLOR SYSTEM
    # -------------------
    attr_rand = nodes.new('ShaderNodeAttribute')
    attr_rand.attribute_name = "random"
    attr_rand.attribute_type = 'INSTANCER'
    attr_rand.location = (-1000, 400)

    sep_color = nodes.new('ShaderNodeSeparateColor')
    sep_color.location = (-750, 400)

    def create_madd(pos, mul, add):
        """Création d’un node Math MULTIPLY_ADD"""
        n = nodes.new('ShaderNodeMath')
        n.operation = 'MULTIPLY_ADD'
        n.inputs[1].default_value = mul
        n.inputs[2].default_value = add
        n.location = pos
        return n

    ma_r = create_madd((-500, 550), 0.02, 0.5)
    ma_g = create_madd((-500, 400), 0.04, 1.0)
    ma_b = create_madd((-500, 250), 0.01, 1.0)

    hsv = nodes.new('ShaderNodeHueSaturation')
    hsv.inputs["Fac"].default_value = 3.0
    hsv.location = (-200, 400)

    # -------------------
    # NORMAL SYSTEM
    # -------------------
    attr_norm = nodes.new('ShaderNodeAttribute')
    attr_norm.attribute_name = "normal"
    attr_norm.attribute_type = 'INSTANCER'
    attr_norm.location = (-1000, 100)

    geom = nodes.new('ShaderNodeNewGeometry')
    geom.location = (-1000, 250)

    mix_norm = nodes.new('ShaderNodeMix')
    mix_norm.data_type = 'VECTOR'
    mix_norm.location = (-750, 200)

    # -------------------
    # TOON SHADER GROUP
    # -------------------
    shader_group = create_paint_shader_group()
    toon = nodes.new('ShaderNodeGroup')
    toon.node_tree = shader_group
    toon.location = (-300, 150)

    toon.inputs['Shadow Color'].default_value = (0.396, 0.765, 0.996, 1.0)
    toon.inputs['Base Color'].default_value = (0.188, 0.353, 0.737, 1.0)
    toon.inputs['Blend Light Color'].default_value = 0.1
    toon.inputs['From Min'].default_value = 0.0
    toon.inputs['From Max'].default_value = 1.0

    # -------------------
    # ALPHA SYSTEM
    # -------------------
    attr_uv = nodes.new('ShaderNodeAttribute')
    attr_uv.attribute_name = "UVMap"
    attr_uv.location = (-1200, -200)

    tex_img = nodes.new('ShaderNodeTexImage')
    tex_img.location = (-950, -200)

    import os

        # --- Détection du chemin du script pour accéder au dossier assets ---
    script_dir = os.path.dirname(os.path.realpath(__file__))
    image_path = os.path.join(script_dir, "assets", "brush_texture.png")

    # --- Nom du fichier ---
    img_name = os.path.basename(image_path)

    # --- Charger l'image dans Blender ---
    if os.path.exists(image_path):
        img = bpy.data.images.get(img_name)
        if not img:
            img = bpy.data.images.load(image_path)
        tex_img.image = img
        tex_img.image.colorspace_settings.name = 'Non-Color'
    else:
        print(f"Image non trouvée : {image_path}")

    light_p = nodes.new('ShaderNodeLightPath')
    light_p.location = (-1200, -500)

    mul_alpha = nodes.new('ShaderNodeMath')
    mul_alpha.operation = 'MULTIPLY'
    mul_alpha.location = (-700, -300)

    mix_alpha = nodes.new('ShaderNodeMix')
    mix_alpha.data_type = 'FLOAT'
    mix_alpha.inputs['A'].default_value = 1.0
    mix_alpha.location = (-450, -200)

    # -------------------
    # FINAL OUTPUT
    # -------------------
    transp = nodes.new('ShaderNodeBsdfTransparent')
    transp.location = (0, -100)

    mix_shader = nodes.new('ShaderNodeMixShader')
    mix_shader.location = (250, 0)

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (450, 0)

    # -------------------
    # LIENS DES NODES DU MATÉRIEL
    # -------------------
    links.new(attr_rand.outputs['Color'], sep_color.inputs['Color'])
    links.new(sep_color.outputs['Red'], ma_r.inputs[0])
    links.new(sep_color.outputs['Green'], ma_g.inputs[0])
    links.new(sep_color.outputs['Blue'], ma_b.inputs[0])
    links.new(ma_r.outputs[0], hsv.inputs['Hue'])
    links.new(ma_g.outputs[0], hsv.inputs['Saturation'])
    links.new(ma_b.outputs[0], hsv.inputs['Value'])
    links.new(hsv.outputs['Color'], mix_shader.inputs[2])

    links.new(geom.outputs['Normal'], mix_norm.inputs[4])
    links.new(attr_norm.outputs['Vector'], mix_norm.inputs[5])
    links.new(attr_norm.outputs[3], mix_alpha.inputs[0])
    links.new(attr_norm.outputs[3], mix_norm.inputs[0])

    # Normal vers toon shader
    links.new(mix_norm.outputs['Result'], toon.inputs['Normal'])

    # Toon → HSV
    links.new(toon.outputs['Result'], hsv.inputs['Color'])

    # UV → Texture
    links.new(attr_uv.outputs['Vector'], tex_img.inputs['Vector'])
    links.new(tex_img.outputs['Alpha'], mul_alpha.inputs[0])
    links.new(light_p.outputs['Is Camera Ray'], mul_alpha.inputs[1])
    links.new(mul_alpha.outputs[0], mix_alpha.inputs[3])
    links.new(mul_alpha.outputs[0], mix_alpha.inputs[5])

    # Shader mix final
    links.new(mix_alpha.outputs[0], mix_shader.inputs[0])
    links.new(transp.outputs['BSDF'], mix_shader.inputs[1])
    links.new(mix_shader.outputs['Shader'], out.inputs['Surface'])

    # Blend et shadow settings
    mat.blend_method = 'BLEND'
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = 'NONE'

    return mat
# ==========================================
# 3. CONFIGURATION DES GEOMETRY NODES ORGANISÉS
# ==========================================
def setup_paint_shader_v3_organized(tree, default_mat):
    """
    Crée et organise un Geometry Node Tree pour gérer le paint shader sur instances.
    Nodes principaux : grid, distribute, instance, translate, rotation, normal + store attributes.
    """
    nodes = tree.nodes
    nodes.clear()
    links = tree.links
    l = links.new  # raccourci

    # --- 1. INTERFACE (API 4.0+)
    itf = tree.interface
    itf.clear()
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    X_socket = itf.new_socket("Size X", in_out='INPUT', socket_type='NodeSocketFloat')
    Y_socket = itf.new_socket("Size Y", in_out='INPUT', socket_type='NodeSocketFloat')
    itf.new_socket("Density", in_out='INPUT', socket_type='NodeSocketFloat').default_value = 50.0
    itf.new_socket("Rotate By", in_out='INPUT', socket_type='NodeSocketRotation')
    itf.new_socket("Material", in_out='INPUT', socket_type='NodeSocketMaterial')
    trans_socket = itf.new_socket("Translation", in_out='INPUT', socket_type='NodeSocketVector')
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    # --- 2. NODES PRINCIPAUX ---
    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-1200, 0)

    # Grid mesh
    grid = nodes.new('GeometryNodeMeshGrid')
    grid.location = (-900, 400)
    grid.inputs[2].default_value = 3
    grid.inputs[3].default_value = 3

    X_socket.subtype = 'DISTANCE'
    X_socket.default_value = 0.29
    Y_socket.subtype = 'DISTANCE'
    Y_socket.default_value = 0.29

    # Stockage UV
    store_uv = nodes.new('GeometryNodeStoreNamedAttribute')
    store_uv.location = (-650, 400)
    store_uv.data_type = 'FLOAT_VECTOR'
    store_uv.inputs[2].default_value = "UVMap"

    # Distribution points
    distribute = nodes.new('GeometryNodeDistributePointsOnFaces')
    distribute.location = (-900, 100)

    # Instancing
    instance = nodes.new('GeometryNodeInstanceOnPoints')
    instance.location = (-300, 200)

    # Translation
    translate = nodes.new('GeometryNodeTranslateInstances')
    translate.location = (-50, 300)
    translate.inputs[3].default_value = True
    trans_socket.subtype = 'TRANSLATION'
    trans_socket.default_value = (0.0, 0.0, -0.24)

    # Stockage normal
    store_normal = nodes.new('GeometryNodeStoreNamedAttribute')
    store_normal.location = (200, 300)
    store_normal.domain = 'INSTANCE'
    store_normal.data_type = 'FLOAT_VECTOR'
    store_normal.inputs[2].default_value = "normal"

    # Random vector
    rand_val = nodes.new('FunctionNodeRandomValue')
    rand_val.location = (200, 550)
    rand_val.data_type = 'FLOAT_VECTOR'
    rand_val.inputs[0].default_value = (-1, -1, -1)
    rand_val.inputs[1].default_value = (1, 1, 1)

    store_rand = nodes.new('GeometryNodeStoreNamedAttribute')
    store_rand.location = (450, 300)
    store_rand.domain = 'INSTANCE'
    store_rand.data_type = 'FLOAT_VECTOR'
    store_rand.inputs[2].default_value = "random"

    # Join geometry
    join = nodes.new('GeometryNodeJoinGeometry')
    join.location = (700, 0)

    # Set material
    set_mat = nodes.new('GeometryNodeSetMaterial')
    set_mat.location = (900, 0)
    set_mat.inputs[2].default_value = default_mat

    # Output
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (1100, 0)

    # --- 3. LOGIQUE DE ROTATION ---
    cam_info = nodes.new('GeometryNodeObjectInfo')
    cam_info.location = (-1200, -300)
    cam_info.transform_space = 'RELATIVE'
    if bpy.context.scene.camera:
        cam_info.inputs[0].default_value = bpy.context.scene.camera

    pos = nodes.new('GeometryNodeInputPosition')
    pos.location = (-1200, -150)

    sub = nodes.new('ShaderNodeVectorMath')
    sub.location = (-1000, -200)
    sub.operation = 'SUBTRACT'

    align_z = nodes.new('FunctionNodeAlignRotationToVector')
    align_z.location = (-750, -200)
    align_z.axis = 'Z'

    comb_xyz = nodes.new('ShaderNodeCombineXYZ')
    comb_xyz.location = (-1200, -600)
    comb_xyz.inputs[1].default_value = 1.0

    vec_rot_cam = nodes.new('ShaderNodeVectorRotate')
    vec_rot_cam.location = (-1000, -550)
    if hasattr(vec_rot_cam, "rotation_type"):
        vec_rot_cam.rotation_type = 'EULER_XYZ'

    cross = nodes.new('ShaderNodeVectorMath')
    cross.location = (-750, -500)
    cross.operation = 'CROSS_PRODUCT'

    align_x = nodes.new('FunctionNodeAlignRotationToVector')
    align_x.location = (-550, -300)
    align_x.axis = 'X'

    self_info = nodes.new('GeometryNodeObjectInfo')
    self_info.location = (-550, -650)
    self_info.transform_space = 'RELATIVE'
    self_info.inputs[0].default_value = bpy.context.active_object

    vec_rot_fin = nodes.new('ShaderNodeVectorRotate')
    vec_rot_fin.location = (-300, -500)
    if hasattr(vec_rot_fin, "rotation_type"):
        vec_rot_fin.rotation_type = 'EULER_XYZ'

    rot_rot = nodes.new('FunctionNodeRotateRotation')
    rot_rot.location = (-50, -150)
    rot_rot.rotation_space = 'LOCAL'

    # --- 4. CONNEXIONS DES NODES ---
    l(g_in.outputs[1], grid.inputs[0])
    l(g_in.outputs[2], grid.inputs[1])
    l(grid.outputs[0], store_uv.inputs[0])
    l(grid.outputs[1], store_uv.inputs[3])
    l(g_in.outputs[0], distribute.inputs[0])
    l(g_in.outputs['Density'], distribute.inputs['Density'])
    l(distribute.outputs[0], instance.inputs[0])
    l(store_uv.outputs[0], instance.inputs[2])
    l(instance.outputs[0], translate.inputs[0])
    l(g_in.outputs[6], translate.inputs[2])
    l(translate.outputs[0], store_normal.inputs[0])
    l(store_normal.outputs[0], store_rand.inputs[0])
    l(rand_val.outputs[0], store_rand.inputs[3])
    l(store_rand.outputs[0], join.inputs[0])
    l(g_in.outputs[0], join.inputs[0])
    l(join.outputs[0], set_mat.inputs[0])
    l(set_mat.outputs[0], g_out.inputs[0])
    l(g_in.outputs[5], set_mat.inputs[2])
    l(cam_info.outputs['Location'], sub.inputs[1])
    l(pos.outputs[0], sub.inputs[0])
    l(sub.outputs[0], align_z.inputs[2])
    l(comb_xyz.outputs[0], vec_rot_cam.inputs[0])
    l(cam_info.outputs['Rotation'], vec_rot_cam.inputs['Rotation'])
    l(sub.outputs[0], cross.inputs[0])
    l(vec_rot_cam.outputs[0], cross.inputs[1])
    l(cross.outputs[0], align_x.inputs[2])
    l(align_z.outputs[0], align_x.inputs[0])
    l(distribute.outputs[1], vec_rot_fin.inputs[0])
    l(self_info.outputs['Rotation'], vec_rot_fin.inputs['Rotation'])
    l(align_x.outputs[0], rot_rot.inputs[0])
    l(g_in.outputs[4], rot_rot.inputs[1])
    l(vec_rot_fin.outputs[0], store_normal.inputs[3])
    l(rot_rot.outputs[0], instance.inputs[5])

# ==========================================
# 4. OPÉRATEURS POUR APPLIQUER / SUPPRIMER LE SHADER
# ==========================================
class OBJECT_OT_apply_organized_paint(bpy.types.Operator):
    """Applique le paint shader à l'objet actif"""
    bl_idname = "object.apply_organized_paint"
    bl_label = "Appliquer Paint Shader"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Sélectionne un MESH !")
            return {'CANCELLED'}

        # Création du matériau
        mat = create_default_paint_material(obj.name)
        if mat.name not in obj.data.materials:
            obj.data.materials.append(mat)

        # Création du modificateur Geometry Nodes
        mod = obj.modifiers.new(name=f"Paint Shader {obj.name}", type='NODES')
        tree = bpy.data.node_groups.new(f"PaintShader_{obj.name}", 'GeometryNodeTree')
        mod.node_group = tree

        # Setup nodes
        setup_paint_shader_v3_organized(tree, mat)

        # Attribution des valeurs par défaut dans l'interface
        for item in tree.interface.items_tree:
            if item.in_out == 'INPUT':
                try:
                    if item.socket_type == 'NodeSocketMaterial':
                        mod[item.identifier] = mat
                    elif hasattr(item, "default_value"):
                        mod[item.identifier] = item.default_value
                except:
                    pass
                
                # --- Brush par défaut ---
        textures = get_default_textures()
        if textures:
            context.scene.selected_texture = textures[0]

        return {'FINISHED'}

# ==========================================
# 5. MISE À JOUR DYNAMIQUE DU PAINT SHADER
# ==========================================
def update_paint_shader(self, context):
    """
    Met à jour dynamiquement les sliders du node group Paint_Shader_Group
    depuis les propriétés de la scène.
    """
    obj = context.active_object
    if not obj or not obj.active_material or not obj.active_material.use_nodes:
        return

    nodes = obj.active_material.node_tree.nodes
    for n in nodes:
        if n.type == 'GROUP' and n.node_tree.name == "Paint_Shader_Group":
            n.inputs["Blend Light Color"].default_value = context.scene.light_blend
            n.inputs["Cel Shaded?"].default_value = context.scene.cel_shaded
            n.inputs["From Min"].default_value = context.scene.light_min
            n.inputs["From Max"].default_value = context.scene.light_max
            
            
def get_default_textures():
    """
    Retourne une liste de textures par défaut dans le dossier assets.
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    assets_dir = os.path.join(script_dir, "assets")
    if not os.path.exists(assets_dir):
        return []

    # Liste des fichiers PNG dans le dossier assets
    default_textures = []
    for filename in os.listdir(assets_dir):
        if filename.endswith(".png"):
            default_textures.append(os.path.join(assets_dir, filename))

    return default_textures

# Propriété pour la sélection de l'image
def get_texture_choices(self, context):

    texture_choices = [
        ('NONE', 'Aucune', 'Pas de texture'),
        ('IMPORT', 'Importer une image...', 'Choisir une image depuis le PC')
    ]

    # Brushes du dossier assets
    for texture_path in get_default_textures():
        name = os.path.basename(texture_path)
        texture_choices.append((texture_path, name, name))

    # Brushes custom utilisateur
    for item in context.scene.custom_brush_textures:
        name = os.path.basename(item.path)
        texture_choices.append((item.path, name + " (Custom)", name))

    return texture_choices

def update_texture(self, context):

    selected_texture = context.scene.selected_texture

    if selected_texture == 'IMPORT':
        bpy.ops.paintshader.import_texture('INVOKE_DEFAULT')
        return

    obj = context.active_object
    if not obj or not obj.active_material:
        return

    mat = obj.active_material
    if not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes

    if selected_texture == 'NONE':
        return

    img_name = os.path.basename(selected_texture)
    img = bpy.data.images.get(img_name)

    if not img:
        img = bpy.data.images.load(selected_texture)

    for n in nodes:
        if n.type == 'TEX_IMAGE':
            n.image = img
            n.image.colorspace_settings.name = 'Non-Color'
            break
        
def sync_brush_selector(scene):

    obj = bpy.context.active_object
    if not obj or not obj.active_material:
        return

    mat = obj.active_material
    if not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes

    for n in nodes:
        if n.type == 'TEX_IMAGE' and n.image:
            scene.selected_texture = n.image.filepath
            break

# ==========================================
# 6. PROPRIÉTÉS DE SCÈNE POUR SLIDERS
# ==========================================
for prop in ["light_blend", "cel_shaded", "light_min", "light_max"]:
    if hasattr(bpy.types.Scene, prop):
        delattr(bpy.types.Scene, prop)

bpy.types.Scene.light_blend = bpy.props.FloatProperty(
    name="Light Blend",
    min=0.0, max=1.0,
    default=0.1,
    subtype='FACTOR',
    update=update_paint_shader
)

bpy.types.Scene.cel_shaded = bpy.props.FloatProperty(
    name="Cel Shading",
    min=0.0, max=1.0,
    default=1.0,
    subtype='FACTOR',
    update=update_paint_shader
)

bpy.types.Scene.light_min = bpy.props.FloatProperty(
    name="Light Threshold Min",
    min=0.0, max=1.0,
    default=0.0,
    subtype='FACTOR',
    update=update_paint_shader
)

bpy.types.Scene.light_max = bpy.props.FloatProperty(
    name="Light Threshold Max",
    min=0.0, max=1.0,
    default=1.0,
    subtype='FACTOR',
    update=update_paint_shader
)
# ==========================================
# 7. MISE À JOUR DYNAMIQUE DU BACKGROUND
# ==========================================
def update_bg_color(self, context):
    """
    Met à jour dynamiquement la couleur du background bleu de la scène.
    Ne modifie pas le noir (ne change que le node bleu).
    """
    scene = context.scene
    if scene.world and scene.world.use_nodes:
        nodes = scene.world.node_tree.nodes
        for n in nodes:
            if n.type == 'BACKGROUND':
                # Ne pas toucher au noir
                if tuple(n.inputs['Color'].default_value[:3]) != (0, 0, 0):
                    n.inputs['Color'].default_value = scene.prereq_bg_color

# Propriété de couleur bleu dynamique pour le background
bpy.types.Scene.prereq_bg_color = bpy.props.FloatVectorProperty(
    name="Background Bleu",
    subtype='COLOR',
    size=4,
    default=(0.314, 0.423, 0.725, 1.0),  # #506CB9FF
    min=0.0, max=1.0,
    description="Couleur du Background bleu du shader ciel",
    update=update_bg_color
)

# ==========================================
# 8. OPÉRATEUR POUR SUPPRIMER LE PAINT SHADER
# ==========================================
class OBJECT_OT_remove_organized_paint(bpy.types.Operator):
    """Supprime le paint shader et le matériau associé de l'objet"""
    bl_idname = "object.remove_organized_paint"
    bl_label = "Supprimer Paint Shader"
    bl_options = {'REGISTER', 'UNDO'}

    obj_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects.get(self.obj_name)
        if not obj:
            self.report({'ERROR'}, "Objet introuvable")
            return {'CANCELLED'}

        # Supprime le modificateur Paint Shader
        mod_name = f"Paint Shader {obj.name}"
        if mod_name in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mod_name])

        # Supprime le matériau Paint
        mats_to_remove = [m for m in obj.data.materials if m.name.startswith("Paint_Material_")]
        for m in mats_to_remove:
            idx = obj.data.materials.find(m.name)
            if idx != -1:
                obj.data.materials.pop(index=idx)

        self.report({'INFO'}, "Paint Shader supprimé")
        return {'FINISHED'}

# ==========================================
# 9. OPÉRATEURS DE CONFIGURATION SÉPARÉS
# ==========================================

class SCENE_OT_setup_render_prereqs(bpy.types.Operator):
    bl_idname = "scene.setup_render_prereqs"
    bl_label = "Configurer Rendu & RT"
    
    def execute(self, context):
        scene = context.scene
        scene.render.engine = 'BLENDER_EEVEE'
        scene.view_settings.view_transform = 'Standard'

        # Active le Raytracing selon la version de Blender
        if hasattr(scene.eevee, "use_raytracing"): # Blender 4.2+
            scene.eevee.use_raytracing = True
        elif hasattr(scene.eevee, "use_ssr"):      # Blender < 4.2
            scene.eevee.use_ssr = True
            scene.eevee.use_gtao = True 
            
        return {'FINISHED'}

class SCENE_OT_setup_sky_shader(bpy.types.Operator):
    """Configure uniquement le shader ciel (World)"""
    bl_idname = "scene.setup_sky_shader"
    bl_label = "Configurer Shader Ciel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        world = scene.world or bpy.data.worlds.new("World")
        scene.world = world
        world.use_nodes = True
        nodes = world.node_tree.nodes
        links = world.node_tree.links
        nodes.clear()

        # Création des nodes pour le mélange technique
        bg_black = nodes.new("ShaderNodeBackground")
        bg_black.inputs['Color'].default_value = (0, 0, 0, 1) # Pour l'éclairage

        bg_color = nodes.new("ShaderNodeBackground")
        bg_color.inputs['Color'].default_value = scene.prereq_bg_color # Pour la caméra

        light_path = nodes.new("ShaderNodeLightPath")
        mix_shader = nodes.new("ShaderNodeMixShader")
        output = nodes.new("ShaderNodeOutputWorld")

        # Liens : Bleu si vu par la caméra, noir pour le reste
        links.new(light_path.outputs['Is Camera Ray'], mix_shader.inputs['Fac'])
        links.new(bg_black.outputs['Background'], mix_shader.inputs[1])
        links.new(bg_color.outputs['Background'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])

        self.report({'INFO'}, "Shader Ciel appliqué")
        return {'FINISHED'}
    
class SCENE_OT_setup_compositing_prereqs(bpy.types.Operator):
    """Configure le post-process Kuwahara + Diamond Sharpen"""
    bl_idname = "scene.setup_compositing_prereqs"
    bl_label = "Configurer Post-Process"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scene = context.scene

        # -------------------------------------------------
        # Détection version Blender
        # -------------------------------------------------

        if hasattr(scene, "node_tree"):  # Blender 3 / 4
            scene.use_nodes = True
            nt = scene.node_tree
            is_scene_tree = True

        else:  # Blender 5+
            if not scene.compositing_node_group:
                scene.compositing_node_group = bpy.data.node_groups.new(
                    name="Compositor",
                    type="CompositorNodeTree"
                )

            nt = scene.compositing_node_group
            is_scene_tree = False

        nodes = nt.nodes
        links = nt.links
        nodes.clear()

        # -------------------------------------------------
        # Blender 5 : créer les sockets du node group
        # -------------------------------------------------

        if not is_scene_tree:

            # supprimer sockets existants
            if hasattr(nt, "interface"):
                for item in list(nt.interface.items_tree):
                    nt.interface.remove(item)

                # socket sortie image
                nt.interface.new_socket(
                    name="Image",
                    in_out='OUTPUT',
                    socket_type='NodeSocketColor'
                )

        # -------------------------------------------------
        # Nodes
        # -------------------------------------------------

        # Render Layers
        rl = nodes.new("CompositorNodeRLayers")
        rl.location = (-500, 0)

        # Premier sharpen
        filt1 = nodes.new("CompositorNodeFilter")
        filt1.location = (-250, 0)
        filt1.inputs[1].default_value = 0.35
        filt1.inputs[2].default_value = 'Diamond Sharpen'

        # Kuwahara
        try:
            kuwa = nodes.new("CompositorNodeKuwahara")
            
            # Size
            kuwa.inputs[1].default_value = 8.0

            # Uniformity (4 → 5)
            kuwa.inputs[3].default_value = 5

            # Eccentricity (réduit à 0.8)
            kuwa.inputs[5].default_value = 0.8
            
        except:
            kuwa = nodes.new("CompositorNodeBlur")
            kuwa.label = "Kuwahara Fallback"

        kuwa.location = (0, 0)

        # Deuxième sharpen
        filt2 = nodes.new("CompositorNodeFilter")
        filt2.location = (250, 0)
        filt2.inputs[1].default_value = 1.0
        filt2.inputs[2].default_value = 'Diamond Sharpen'
        
        # Mix Color
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.blend_type = 'MIX'
        mix.inputs[0].default_value = 0.5
        mix.location = (450, 0)

        # Deuxième Kuwahara
        kuwa2 = nodes.new("CompositorNodeKuwahara")

        kuwa2.inputs[1].default_value = 20.0
        kuwa2.inputs[3].default_value = 5
        kuwa2.inputs[5].default_value = 0.8

        kuwa2.location = (200, -200)

        # Output
        if is_scene_tree:
            out = nodes.new("CompositorNodeComposite")
        else:
            out = nodes.new("NodeGroupOutput")

        out.location = (500, 0)

        # Viewer uniquement Blender 3 / 4
        if is_scene_tree:
            viewer = nodes.new("CompositorNodeViewer")
            viewer.location = (500, 200)

        # -------------------------------------------------
        # Links
        # -------------------------------------------------

        links.new(rl.outputs[0], filt1.inputs[0])
        links.new(filt1.outputs[0], kuwa.inputs[0])
        links.new(kuwa.outputs[0], filt2.inputs[0])
        links.new(mix.outputs[2], out.inputs[0])

        # Filter2 -> Mix A
        links.new(filt2.outputs[0], mix.inputs[6])

        # Render Layers -> Kuwahara2
        links.new(rl.outputs[0], kuwa2.inputs[0])

        # Kuwahara2 -> Mix B
        links.new(kuwa2.outputs[0], mix.inputs[7])

        if is_scene_tree:
            links.new(filt2.outputs[0], viewer.inputs[0])

        self.report({'INFO'}, "Post-Process Paint configuré")
        return {'FINISHED'}
    
# ==========================================
# 10. PANEL UI : PRÉ-REQUIS SCÈNE
# ==========================================
class VIEW3D_PT_paint_prereqs(bpy.types.Panel):
    """Panel avec 3 étapes de configuration intelligentes"""
    bl_label = "Pré-requis Scène"
    bl_idname = "VIEW3D_PT_paint_prereqs"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Paint'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- BLOC 1 : RENDU & RT ---
        is_eevee = scene.render.engine == 'BLENDER_EEVEE'
        is_standard = scene.view_settings.view_transform == 'Standard'
        is_rt = getattr(scene.eevee, "use_raytracing", getattr(scene.eevee, "use_ssr", False))
        
        render_ok = is_eevee and is_standard and is_rt
        
        box = layout.box()
        box.label(text="Moteur & Raytracing", icon='RENDER_RESULT')
        col = box.column(align=True)
        col.label(text="Moteur Eevee", icon='CHECKMARK' if is_eevee else 'ERROR')
        col.label(text="Color Standard", icon='CHECKMARK' if is_standard else 'ERROR')
        col.label(text="Raytracing", icon='CHECKMARK' if is_rt else 'ERROR')

        if not render_ok:
            box.operator("scene.setup_render_prereqs", text="Réparer Rendu & RT", icon='TOOL_SETTINGS')

        # --- BLOC 2 : CIEL ---
        world_ok = False
        if scene.world and scene.world.use_nodes:
            node_types = [n.type for n in scene.world.node_tree.nodes]
            world_ok = "LIGHT_PATH" in node_types and node_types.count("BACKGROUND") >= 2
        
        box = layout.box()
        box.label(text="Environnement Ciel", icon='WORLD')
        if world_ok:
            box.label(text="Shader Ciel : OK", icon='CHECKMARK')
            box.prop(scene, "prereq_bg_color", text="Couleur")
        else:
            box.operator("scene.setup_sky_shader", text="Appliquer Shader Ciel", icon='STRANDS')

        # --- BLOC 3 : POST-PROCESS (COMPOSITING BLENDER 5.0) ---
        box = layout.box()
        box.label(text="Post-Process (Style)", icon='NODE_COMPOSITING')

        comp_enabled = False
        nt = None

        # Détection version Blender
        scene = context.scene
        if bpy.app.version >= (5, 0, 0):
            if hasattr(scene, "compositing_node_group"):
                nt = scene.compositing_node_group
        else:
            if scene.use_nodes and hasattr(scene, "node_tree"):
                nt = scene.node_tree

        # Vérification si les nodes de style sont présents dans l'arbre
        if nt and len(nt.nodes) > 0:
            node_types = {n.type for n in nt.nodes}
            if 'KUWAHARA' in node_types or 'FILTER' in node_types:
                comp_enabled = True

        # Toggle ON/OFF pour activer/désactiver le compositing
        row = box.row()
        row.prop(scene, "use_paint_postprocess", text="Activer Post-Process")

        # Si le toggle est activé mais nodes manquants, proposer d'appliquer
        if scene.use_paint_postprocess and not comp_enabled:
            box.operator("scene.setup_compositing_prereqs", text="Créer Post-Process", icon='NODETREE')
            
# ==========================================
# 11. PANEL UI : PAINT ORGANIZED
# ==========================================
class VIEW3D_PT_paint_organized(bpy.types.Panel):
    """Panel pour appliquer, supprimer et contrôler le paint shader"""
    bl_label = "Paint Organized"
    bl_idname = "VIEW3D_PT_paint_organized"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Paint'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if not obj:
            return

        # Vérifie si shader est déjà appliqué
        mod_exists = obj.modifiers.get(f"Paint Shader {obj.name}") is not None
        mat_exists = any(m.name.startswith("Paint_Material_") for m in obj.data.materials)

        if mod_exists or mat_exists:
            op = layout.operator("object.remove_organized_paint", icon='CANCEL')
            op.obj_name = obj.name
        else:
            layout.operator("object.apply_organized_paint", icon='BRUSH_DATA')

        # Affiche sliders geometry nodes si existants
        mod = obj.modifiers.get(f"Paint Shader {obj.name}")
        if mod and mod.node_group:
            box = layout.box()
            box.label(text="Geometry Nodes")
            for item in mod.node_group.interface.items_tree:
                if item.in_out == 'INPUT':
                    name = item.name
                    if name in {"Size X", "Size Y", "Density", "Material", "Translation", "Rotate By"}:
                        try:
                            box.prop(mod, f'["{item.identifier}"]', text=name)
                        except:
                            pass

        # Material / Shader Controls
        mat = obj.active_material
        if mat and mat.use_nodes:
            nodes = mat.node_tree.nodes
            # Cherche le node group Paint_Shader_Group
            for n in nodes:
                if n.type == 'GROUP' and n.node_tree.name == "Paint_Shader_Group":
                    box = layout.box()
                    box.label(text="Paint Shader")
                    box.prop(n.inputs["Base Color"], "default_value", text="Base Color")
                    box.prop(n.inputs["Shadow Color"], "default_value", text="Shadow Color")
                    box.prop(context.scene, "light_blend", slider=True)
                    box.prop(context.scene, "cel_shaded", slider=True)
                    box.prop(context.scene, "light_min", slider=True)
                    box.prop(context.scene, "light_max", slider=True)
                    break

            # HSV Control
            for n in nodes:
                if n.type == 'HUE_SAT':
                    box = layout.box()
                    box.label(text="HSV")
                    row = box.row()
                    row.prop(n.inputs["Fac"], "default_value", text="HSV Factor", slider=True)
                    break

            # Image Texture Control (Sélectionner une texture)
            box = layout.box()
            box.label(text="Texture Brush")
            box.prop(context.scene, "selected_texture", text="Texture")

class PAINTSHADER_OT_import_texture(bpy.types.Operator):
    bl_idname = "paintshader.import_texture"
    bl_label = "Importer Texture"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):

        obj = context.active_object
        if not obj or not obj.active_material:
            return {'CANCELLED'}

        mat = obj.active_material
        nodes = mat.node_tree.nodes

        img = bpy.data.images.load(self.filepath)
        img.pack()

        for n in nodes:
            if n.type == 'TEX_IMAGE':
                n.image = img
                n.image.colorspace_settings.name = 'Non-Color'
                break
            
        scene = context.scene

        # Ajouter à la liste custom si pas déjà présent
        for item in scene.custom_brush_textures:
            if item.path == self.filepath:
                break
        else:
            new_item = scene.custom_brush_textures.add()
            new_item.path = self.filepath

        scene.selected_texture = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class CustomBrush(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty()
    
def toggle_paint_compositing(scene):
    """Active ou mute les nodes de post-process selon le toggle"""
    nt = None
    if bpy.app.version >= (5, 0, 0) and hasattr(scene, "compositing_node_group"):
        nt = scene.compositing_node_group
    elif scene.use_nodes and hasattr(scene, "node_tree"):
        nt = scene.node_tree

    if not nt:
        return

    for n in nt.nodes:
        # Mute tous les nodes de style (Kuwahara / Filter)
        if n.type in {'KUWAHARA', 'FILTER'}:
            n.mute = not scene.use_paint_postprocess

# ==========================================
# 12. ENREGISTREMENT DES CLASSES
# ==========================================
classes = (
    CustomBrush,
    OBJECT_OT_apply_organized_paint,
    OBJECT_OT_remove_organized_paint,
    VIEW3D_PT_paint_organized,
    SCENE_OT_setup_render_prereqs,
    SCENE_OT_setup_sky_shader,
    SCENE_OT_setup_compositing_prereqs,
    VIEW3D_PT_paint_prereqs,
    PAINTSHADER_OT_import_texture
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.selected_texture = bpy.props.EnumProperty(
    name="Sélectionner une texture",
    items=get_texture_choices,
    description="Choisissez une texture par défaut",
    update=update_texture
    )
    
    bpy.types.Scene.use_paint_postprocess = bpy.props.BoolProperty(
    name="Activer Post-Process",
    default=False,
    description="Active ou désactive le compositing Paint",
    update=lambda self, context: toggle_paint_compositing(context.scene)
    )

    bpy.app.handlers.depsgraph_update_post.append(sync_brush_selector)
    bpy.types.Scene.custom_brush_textures = bpy.props.CollectionProperty(type=CustomBrush)

def unregister():
    
    del bpy.types.Scene.selected_texture
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    bpy.app.handlers.depsgraph_update_post.remove(sync_brush_selector)

if __name__ == "__main__":
    register()
