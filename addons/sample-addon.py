bl_info = {
    "name": "Sample addon for DAZ importer",
    "author": "Thomas Larsson",
    "version": (1, 0, 0),
    "blender": (2, 82, 0),
    "location": "View3D > UI",
    "description": "",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "General"}

import bpy

#----------------------------------------------------------
#   A sample panel
#----------------------------------------------------------

class DAZ_PT_Sample(bpy.types.Panel):
    bl_label = "Sample Addon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sample"

    def draw(self, context):
        self.layout.operator("sample.import_daz_file")

#----------------------------------------------------------
#   A sample button
#----------------------------------------------------------

class SAMPLE_OT_ImportDazFile(bpy.types.Operator):
    bl_idname = "sample.import_daz_file"
    bl_label = "Import DAZ File"
    bl_description = "Invoke the DAZ Importer and import a specific duf file."
    bl_options = {'UNDO'}

    def execute(self, context):
        from ..error import getErrorMessage
        bpy.ops.daz.import_daz(
            filepath = "/home/thomas/Dokument/DAZ 3D/Scenes/base8.duf",
            unitScale = 1/2.54,             # inches
            skinColor = (0.6, 0.4, 0.25, 1.0),
            clothesColor = (0, 0, 1, 1),    # blue clothes
            brightenEyes = 1.5,             # brighter eyes
            fitMeshes = 'UNIQUE',           # Don't fit meshes. Each object has unique mesh instance
            useAutoMaterials = False,       # Don't use best shaders for material, independent of the settings below
            handleOpaque = 'PRINCIPLED',    # Node setup with principled node
            handleRefractive = 'PRINCIPLED',# Node setup with principled node
            handleVolumetric = 'SSS',       # Subsurface scattering
            useEnvironment = False,         # Don't Load environment
            )
        print("Script finished")
        # The error message is the empty string if there are no errors
        msg = getErrorMessage()
        print("Error message: \"%s\"" % msg)
        return {'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_PT_Sample,
    SAMPLE_OT_ImportDazFile,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

