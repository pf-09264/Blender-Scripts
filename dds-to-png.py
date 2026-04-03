import os
import bpy
from PIL import Image
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper

# ---------------------------------------------------------
# 1. THE CORE CONVERSION LOGIC
# ---------------------------------------------------------
def convert_dds_to_png(folder_path, delete_original=False):
    folder_path = os.path.normpath(folder_path)
    
    if not os.path.exists(folder_path):
        return (False, f"Error: The folder '{folder_path}' does not exist.")

    converted_count = 0
    errors = 0

    # 1. Convert files on disk
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.dds'):
            dds_path = os.path.join(folder_path, filename)
            png_path = os.path.join(folder_path, os.path.splitext(filename)[0] + '.png')
            
            try:
                with Image.open(dds_path) as img:
                    img.convert('RGBA').save(png_path, 'PNG')
                
                converted_count += 1
                
                if delete_original:
                    os.remove(dds_path)
                    
            except Exception as e:
                print(f"Failed to convert {filename}. Error: {e}")
                errors += 1

    # 2. Map the new PNGs to Blender's materials
    for img in bpy.data.images:
        # Check if the image currently uses a filepath ending in .dds
        if img.filepath.lower().endswith('.dds'):
            # Generate the new .png path
            new_path = os.path.splitext(img.filepath)[0] + '.png'
            absolute_png_path = bpy.path.abspath(new_path)
        
            # Check if we actually created that file on the disk
            if os.path.exists(absolute_png_path):
                # Change the filepath
                img.filepath = new_path
                # FORCE Blender to change the source type to image (just in case)
                img.source = 'FILE' 
                
                # This is the magic bullet: reload using the brand new path
                try:
                    img.reload()
                except Exception as e:
                     print(f"Blender failed to reload image {img.name}: {e}")

    return (True, f"Successfully converted {converted_count} files and remapped materials! (Errors: {errors})")


# ---------------------------------------------------------
# 2. THE BLENDER UI OPERATOR
# ---------------------------------------------------------
class OT_DdsToPngConverter(bpy.types.Operator, ImportHelper):
    """Select a folder to convert DDS textures to PNG"""
    bl_idname = "object.convert_dds_folder"
    bl_label = "Convert DDS to PNG"
    
    # This filter forces the file browser to select folders instead of files
    directory: StringProperty(
        name="Texture Folder",
        description="Folder containing the DDS files",
        subtype='DIR_PATH'
    )
    
    delete_originals: BoolProperty(
        name="Delete Original DDS Files",
        description="Be careful! This will remove the source DDS files after conversion.",
        default=False
    )
    
    def execute(self, context):
        # Run the converter function using the chosen directory
        success, message = convert_dds_to_png(self.directory, self.delete_originals)
        
        # Display the result in Blender's info header
        if success:
            self.report({'INFO'}, message)
        else:
            self.report({'ERROR'}, message)
            
        return {'FINISHED'}

    def invoke(self, context, event):
        # Set the default path to where the blend file is saved
        if bpy.data.is_saved:
            blend_dir = os.path.dirname(bpy.data.filepath)
            textures_subfolder = os.path.join(blend_dir, "textures")
            
            # Default to the 'textures' subfolder if it exists, otherwise the blend folder
            if os.path.exists(textures_subfolder):
                self.directory = textures_subfolder + os.sep
            else:
                self.directory = blend_dir + os.sep
        else:
            # Fallback to user home directory if blend isn't saved
            self.directory = os.path.expanduser("~") + os.sep
            
        context.window_manager.fileselect_add(self)
        
        # FIXED: Changed 'RUNNING_RESPONSE' to 'RUNNING_MODAL'
        return {'RUNNING_MODAL'}

# ---------------------------------------------------------
# 3. REGISTRATION
# ---------------------------------------------------------
def register():
    bpy.utils.register_class(OT_DdsToPngConverter)
    
def unregister():
    bpy.utils.unregister_class(OT_DdsToPngConverter)

if __name__ == "__main__":
    register()
    
    # This line automatically triggers the pop-up immediately when you run the script!
    bpy.ops.object.convert_dds_folder('INVOKE_DEFAULT')
