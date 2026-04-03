import bpy
import bmesh
from mathutils import Vector
import math

bl_info = {
    "name": "Collider Generator with Preview",
    "author": "pf.me", #and ai 
    "version": (1, 3),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Collider",
    "description": "Generate collision meshes from selected objects with live preview",
    "category": "Object",
}

# --- HELPER FUNCTIONS ---
def get_combined_bbox(objects):
    """Get bounding box that encompasses all selected objects"""
    all_corners = []
    for obj in objects:
        if obj.type == 'MESH':
            bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            all_corners.extend(bbox_corners)
    
    if not all_corners:
        return None, None, None
    
    min_co = Vector((min(v.x for v in all_corners),
                    min(v.y for v in all_corners),
                    min(v.z for v in all_corners)))
    max_co = Vector((max(v.x for v in all_corners),
                    max(v.y for v in all_corners),
                    max(v.z for v in all_corners)))
    
    dimensions = max_co - min_co
    center = (min_co + max_co) / 2
    
    return center, dimensions, (min_co, max_co)

def clean_mesh_data(obj):
    """Cleans UVs, materials, and vertex colors from target object"""
    obj.data.materials.clear()
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])
    
    # Check for vertex colors based on API version
    if hasattr(obj.data, "vertex_colors"):
        while obj.data.vertex_colors:
            obj.data.vertex_colors.remove(obj.data.vertex_colors[0])
    elif hasattr(obj.data, "color_attributes"):
        while obj.data.color_attributes:
            obj.data.color_attributes.remove(obj.data.color_attributes[0])


# --- LIVE PREVIEW CALLBACKS ---
def update_convex_preview(self, context):
    """Callback when Convex Hull properties change"""
    scene = context.scene
    preview_obj = bpy.data.objects.get("PREVIEW_ConvexHullCollider")
    
    if preview_obj:
        decimate_mod = preview_obj.modifiers.get("Preview_Decimate")
        if decimate_mod:
            decimate_mod.ratio = scene.collider_convex_decimate

def update_simplified_preview(self, context):
    """Callback when Simplified Mesh properties change"""
    scene = context.scene
    preview_obj = bpy.data.objects.get("PREVIEW_SimplifiedCollider")
    
    if preview_obj:
        decimate_mod = preview_obj.modifiers.get("Preview_Decimate")
        if decimate_mod:
            decimate_mod.ratio = scene.collider_simplified_ratio


# --- OPERATORS ---
class OBJECT_OT_generate_box_collider(bpy.types.Operator):
    bl_idname = "object.generate_box_collider"
    bl_label = "Box Collider"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        center, dimensions, _ = get_combined_bbox(selected)
        if center is None:
            self.report({'ERROR'}, "Could not calculate bounding box")
            return {'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        collider = context.active_object
        collider.scale = dimensions / 2
        
        collider.name = f"{selected[0].name}_BoxCollider" if len(selected) == 1 else "Combined_BoxCollider"
        
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        clean_mesh_data(collider)
        
        self.report({'INFO'}, f"Box collider created from {len(selected)} object(s)")
        return {'FINISHED'}


class OBJECT_OT_generate_sphere_collider(bpy.types.Operator):
    bl_idname = "object.generate_sphere_collider"
    bl_label = "Sphere Collider"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected: return {'CANCELLED'}
        
        center, dimensions, _ = get_combined_bbox(selected)
        radius = max(dimensions) / 2
        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=center, segments=16, ring_count=8)
        collider = context.active_object
        collider.name = f"{selected[0].name}_SphereCollider" if len(selected) == 1 else "Combined_SphereCollider"
        clean_mesh_data(collider)
        
        return {'FINISHED'}


class OBJECT_OT_generate_capsule_collider(bpy.types.Operator):
    bl_idname = "object.generate_capsule_collider"
    bl_label = "Capsule Collider"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected: return {'CANCELLED'}
        
        center, dimensions, _ = get_combined_bbox(selected)
        height = max(dimensions)
        radius = (sum(dimensions) - height) / 4
        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, location=center, vertices=12)
        collider = context.active_object
        
        if dimensions.x == height: collider.rotation_euler = (0, math.radians(90), 0)
        elif dimensions.y == height: collider.rotation_euler = (math.radians(90), 0, 0)
            
        collider.name = f"{selected[0].name}_CapsuleCollider" if len(selected) == 1 else "Combined_CapsuleCollider"
        clean_mesh_data(collider)
        return {'FINISHED'}


# --- COMPLEX OPERATORS WITH PREVIEW LOGIC ---

class OBJECT_OT_preview_convex_hull(bpy.types.Operator):
    """Toggle a live preview of the Convex Hull"""
    bl_idname = "object.preview_convex_hull"
    bl_label = "Toggle Convex Hull Preview"
    
    def execute(self, context):
        scene = context.scene
        preview_name = "PREVIEW_ConvexHullCollider"
        preview_obj = bpy.data.objects.get(preview_name)
        
        # If preview is already on and the object exists, turn it off.
        if scene.collider_convex_show_preview and preview_obj:
            bpy.data.objects.remove(preview_obj, do_unlink=True)
            scene.collider_convex_show_preview = False
            return {'FINISHED'}
            
        # Otherwise, turn it ON
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "No mesh objects selected")
            scene.collider_convex_show_preview = False
            return {'CANCELLED'}
        
        # Create duplicate
        bpy.ops.object.duplicate()
        duplicates = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not duplicates:
            return {'CANCELLED'}
            
        # Join duplicates if there are multiple
        context.view_layer.objects.active = duplicates[0]
        if len(duplicates) > 1:
            bpy.ops.object.join()
        
        preview_obj = context.active_object
        preview_obj.name = preview_name
        
        # Generate Convex Hull in Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.convex_hull()
        if scene.collider_convex_merge > 0:
            bpy.ops.mesh.remove_doubles(threshold=scene.collider_convex_merge)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Setup modifier for live update
        dec_mod = preview_obj.modifiers.new(name="Preview_Decimate", type='DECIMATE')
        dec_mod.ratio = scene.collider_convex_decimate
        
        # Display as Wireframe
        preview_obj.display_type = 'WIRE'
        
        scene.collider_convex_show_preview = True
        return {'FINISHED'}


class OBJECT_OT_generate_convex_hull_collider(bpy.types.Operator):
    """Bake and finalize the convex hull collider"""
    bl_idname = "object.generate_convex_hull_collider"
    bl_label = "Generate Convex Hull"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        preview_name = "PREVIEW_ConvexHullCollider"
        preview_obj = bpy.data.objects.get(preview_name)
        
        if preview_obj:
            preview_obj.name = "Combined_ConvexHullCollider"
            preview_obj.display_type = 'TEXTURED'
            
            context.view_layer.objects.active = preview_obj
            bpy.ops.object.convert(target='MESH')
            
            clean_mesh_data(preview_obj)
            
            scene.collider_convex_show_preview = False
            self.report({'INFO'}, "Convex Hull Collider generated successfully!")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Preview object missing. Please restart preview.")
            scene.collider_convex_show_preview = False
            return {'CANCELLED'}


# --- SIMPLIFIED MESH OPERATORS ---

class OBJECT_OT_preview_simplified(bpy.types.Operator):
    """Toggle a live preview of the Decimated Mesh"""
    bl_idname = "object.preview_simplified"
    bl_label = "Toggle Simplified Preview"
    
    def execute(self, context):
        scene = context.scene
        preview_name = "PREVIEW_SimplifiedCollider"
        preview_obj = bpy.data.objects.get(preview_name)
        
        if scene.collider_simplified_show_preview and preview_obj:
            bpy.data.objects.remove(preview_obj, do_unlink=True)
            scene.collider_simplified_show_preview = False
            return {'FINISHED'}
            
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "No mesh objects selected")
            scene.collider_simplified_show_preview = False
            return {'CANCELLED'}
        
        bpy.ops.object.duplicate()
        duplicates = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        context.view_layer.objects.active = duplicates[0]
        if len(duplicates) > 1:
            bpy.ops.object.join()
        
        preview_obj = context.active_object
        preview_obj.name = preview_name
        
        dec_mod = preview_obj.modifiers.new(name="Preview_Decimate", type='DECIMATE')
        dec_mod.ratio = scene.collider_simplified_ratio
        
        preview_obj.display_type = 'WIRE'
        scene.collider_simplified_show_preview = True
        return {'FINISHED'}


class OBJECT_OT_generate_simplified_collider(bpy.types.Operator):
    """Bake and finalize the simplified collider"""
    bl_idname = "object.generate_simplified_collider"
    bl_label = "Generate Decimated Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        preview_name = "PREVIEW_SimplifiedCollider"
        preview_obj = bpy.data.objects.get(preview_name)
        
        if preview_obj:
            preview_obj.name = "Combined_SimplifiedCollider"
            preview_obj.display_type = 'TEXTURED'
            
            context.view_layer.objects.active = preview_obj
            bpy.ops.object.convert(target='MESH')
            
            clean_mesh_data(preview_obj)
            scene.collider_simplified_show_preview = False
            self.report({'INFO'}, "Simplified Collider generated successfully!")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Preview object missing. Please restart preview.")
            scene.collider_simplified_show_preview = False
            return {'CANCELLED'}


# --- UI PANEL ---
class VIEW3D_PT_collider_panel(bpy.types.Panel):
    bl_label = "Collider Generator"
    bl_idname = "VIEW3D_PT_collider_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Collider'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        box = layout.box()
        box.label(text=f"Selected Meshes: {len(selected_meshes)}", icon='OBJECT_DATA')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Basic Colliders:", icon='SHADING_BBOX')
        col.operator("object.generate_box_collider", icon='MESH_CUBE')
        col.operator("object.generate_sphere_collider", icon='MESH_UVSPHERE')
        col.operator("object.generate_capsule_collider", icon='MESH_CAPSULE')
        
        layout.separator()
        
        # Convex Hull UI Section
        box = layout.box()
        box.label(text="Convex Hull Options:", icon='MESH_ICOSPHERE')
        col = box.column(align=True)
        col.prop(scene, "collider_convex_decimate")
        col.prop(scene, "collider_convex_merge")
        
        # Check if the object actually exists to correct any toggling bugs
        preview_hull = bpy.data.objects.get("PREVIEW_ConvexHullCollider")
        preview_hull_on = scene.collider_convex_show_preview and preview_hull
        
        preview_icon = 'RESTRICT_VIEW_OFF' if preview_hull_on else 'RESTRICT_VIEW_ON'
        col.operator("object.preview_convex_hull", text="Live Preview", icon=preview_icon)
        
        gen_col = col.column()
        gen_col.enabled = bool(preview_hull_on)
        gen_col.operator("object.generate_convex_hull_collider", text="Bake Convex Hull")
        
        layout.separator()
        
        # Simplified Collider UI Section
        box = layout.box()
        box.label(text="Advanced Mesh Decimation:", icon='MODIFIER')
        col = box.column(align=True)
        col.prop(scene, "collider_simplified_ratio")
        
        preview_simp = bpy.data.objects.get("PREVIEW_SimplifiedCollider")
        preview_simp_on = scene.collider_simplified_show_preview and preview_simp
        
        preview_icon_simp = 'RESTRICT_VIEW_OFF' if preview_simp_on else 'RESTRICT_VIEW_ON'
        col.operator("object.preview_simplified", text="Live Preview", icon=preview_icon_simp)
        
        gen_col_simp = col.column()
        gen_col_simp.enabled = bool(preview_simp_on)
        gen_col_simp.operator("object.generate_simplified_collider", text="Bake Decimated Mesh", icon='MOD_DECIM')


# --- REGISTRATION ---
classes = (
    OBJECT_OT_generate_box_collider,
    OBJECT_OT_generate_sphere_collider,
    OBJECT_OT_generate_capsule_collider,
    OBJECT_OT_preview_convex_hull,
    OBJECT_OT_generate_convex_hull_collider,
    OBJECT_OT_preview_simplified,
    OBJECT_OT_generate_simplified_collider,
    VIEW3D_PT_collider_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.collider_convex_decimate = bpy.props.FloatProperty(
        name="Simplify",
        description="Reduce polygon count after hull generation",
        default=1.0, min=0.01, max=1.0,
        update=update_convex_preview 
    )
    bpy.types.Scene.collider_convex_merge = bpy.props.FloatProperty(
        name="Merge Distance",
        description="Merge vertices within this distance",
        default=0.001, min=0.0, max=1.0
    )
    bpy.types.Scene.collider_simplified_ratio = bpy.props.FloatProperty(
        name="Decimation Ratio",
        description="Ratio of faces to keep for simplified mesh",
        default=0.1, min=0.01, max=1.0,
        update=update_simplified_preview 
    )
    
    bpy.types.Scene.collider_convex_show_preview = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.collider_simplified_show_preview = bpy.props.BoolProperty(default=False)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.collider_convex_decimate
    del bpy.types.Scene.collider_convex_merge
    del bpy.types.Scene.collider_simplified_ratio
    del bpy.types.Scene.collider_convex_show_preview
    del bpy.types.Scene.collider_simplified_show_preview

if __name__ == "__main__":
    register()