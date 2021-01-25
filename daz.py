# Copyright (c) 2016-2021, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

import os
import bpy
from bpy.props import *
from .error import *
from .utils import *

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(DazOperator, B.DazImageFile, B.SingleFile, B.DazOptions, B.PoleTargets):
    """Import a DAZ DUF/DSF File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ File"
    bl_description = "Import a native DAZ file (*.duf, *.dsf, *.dse)"
    bl_options = {'PRESET', 'UNDO'}

    def run(self, context):
        from .main import getMainAsset
        getMainAsset(self.filepath, context, self)


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def draw(self, context):
        layout = self.layout
        box = self.layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)
        layout.separator()
        box = layout.box()
        box.label(text = "Viewport Color")
        row = box.row()
        row.prop(self, "skinColor")
        row.prop(self, "clothesColor")
        layout.separator()
        box = layout.box()
        box.label(text = "For more options, see Global Settings.")

#-------------------------------------------------------------
#   Silent mode
#-------------------------------------------------------------

class DAZ_OT_SetSilentMode(bpy.types.Operator):
    bl_idname = "daz.set_silent_mode"
    bl_label = "Silent Mode"
    bl_description = "Toggle silent mode on or off (error popups off or on)"

    def execute(self, context):
        from .error import getSilentMode, setSilentMode
        setSilentMode(not getSilentMode())
        return {'FINISHED'}

#-------------------------------------------------------------
#   Settings popup
#-------------------------------------------------------------

class DAZ_OT_AddContentDir(bpy.types.Operator):
    bl_idname = "daz.add_content_dir"
    bl_label = "Add Content Directory"
    bl_description = "Add a content directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazContentDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


class DAZ_OT_AddMDLDir(bpy.types.Operator):
    bl_idname = "daz.add_mdl_dir"
    bl_label = "Add MDL Directory"
    bl_description = "Add an MDL directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazMDLDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


class DAZ_OT_AddCloudDir(bpy.types.Operator):
    bl_idname = "daz.add_cloud_dir"
    bl_label = "Add Cloud Directory"
    bl_description = "Add a cloud directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazCloudDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


class DAZ_OT_SaveSettingsFile(bpy.types.Operator, B.SingleFile, B.JsonExportFile):
    bl_idname = "daz.save_settings_file"
    bl_label = "Save Settings File"
    bl_description = "Save current settings to file"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.fromScene(context.scene)
        GS.save(self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(GS.settingsPath)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAZ_OT_LoadFactorySettings(DazOperator):
    bl_idname = "daz.load_factory_settings"
    bl_label = "Load Factory Settings"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.__init__()
        GS.toScene(context.scene)
        return {'PASS_THROUGH'}


class DAZ_OT_LoadRootPaths(DazOperator, B.SingleFile, B.JsonFile, B.LoadRootPaths):
    bl_idname = "daz.load_root_paths"
    bl_label = "Load Root Paths"
    bl_description = "Load DAZ root paths from file"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "useContent")
        self.layout.prop(self, "useMDL")
        self.layout.prop(self, "useCloud")

    def execute(self, context):
        struct = GS.openFile(self.filepath)
        if struct:
            print("Load root paths from", self.filepath)
            GS.readDazPaths(struct, self)
            GS.toScene(context.scene)
        else:
            print("No root paths found in", self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        #if not self.properties.filepath:
        #    self.properties.filepath = GS.rootPath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAZ_OT_LoadSettingsFile(DazOperator, B.SingleFile, B.JsonFile):
    bl_idname = "daz.load_settings_file"
    bl_label = "Load Settings File"
    bl_description = "Load settings from file"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.load(self.filepath)
        GS.toScene(context.scene)
        print("Settings file %s saved" % self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(GS.settingsPath)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAZ_OT_GlobalSettings(DazOperator):
    bl_idname = "daz.global_settings"
    bl_label = "Global Settings"
    bl_description = "Show or update global settings"

    def draw(self, context):
        from .panel import showBox
        scn = context.scene
        split = splitLayout(self.layout, 0.4)
        col = split.column()
        box = col.box()
        box.label(text = "DAZ Studio Root Directories")
        if showBox(scn, "DazShowContentDirs", box):
            for pg in scn.DazContentDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_content_dir")
        if showBox(scn, "DazShowMDLDirs", box):
            for pg in scn.DazMDLDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_mdl_dir")
        if showBox(scn, "DazShowCloudDirs", box):
            for pg in scn.DazCloudDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_cloud_dir")
        box.label(text = "Path To Output Errors:")
        box.prop(scn, "DazErrorPath", text="")

        col = split.column()
        box = col.box()
        box.label(text = "General")
        box.prop(scn, "DazUnitScale")
        box.prop(scn, "DazVerbosity")
        box.prop(scn, "DazZup")
        box.prop(scn, "DazCaseSensitivePaths")

        box = col.box()
        box.label(text = "Meshes")
        box.prop(scn, "DazBuildHighdef")
        box.prop(scn, "DazMultires")
        box.prop(scn, "DazUseInstancing")

        box = col.box()
        box.label(text = "Properties")
        box.prop(scn, "DazUsePropLimits")
        box.prop(scn, "DazUsePropDefault")
        box.prop(scn, "DazPropMin")
        box.prop(scn, "DazPropMax")

        col = split.column()
        box = col.box()
        box.label(text = "Rigging")
        box.prop(scn, "DazOrientMethod")
        box.prop(scn, "DazUseQuaternions")
        #box.prop(scn, "DazConnectClose")
        box.separator()
        box.prop(scn, "DazUseLockLoc")
        box.prop(scn, "DazUseLimitLoc")
        box.prop(scn, "DazUseLockRot")
        box.prop(scn, "DazUseLimitRot")
        box.prop(scn, "DazUseLegacyLocks")

        box = col.box()
        box.label(text = "Simulation")
        box.prop(scn, "DazInfluence")
        box.prop(scn, "DazSimulation")

        box = split.box()
        box.label(text = "Materials")
        box.prop(scn, "DazMaterialMethod")
        box.prop(scn, "DazRefractiveMethod")
        box.prop(scn, "DazHairMaterialMethod")
        box.separator()
        box.prop(scn, "DazChooseColors")
        box.prop(scn, "DazMergeShells")
        box.prop(scn, "DazThinWall")
        box.prop(scn, "DazPruneNodes")
        box.prop(scn, "DazUseEnvironment")
        box.prop(scn, "DazReuseMaterials")
        box.prop(scn, "DazLimitBump")
        if scn.DazLimitBump:
            box.prop(scn, "DazMaxBump")
        box.prop(scn, "DazHandleRenderSettings")
        box.prop(scn, "DazHandleLightSettings")
        box.separator()
        box.prop(scn, "DazUseDisplacement")
        box.prop(scn, "DazUseEmission")
        box.prop(scn, "DazUseReflection")
        if bpy.app.version < (2,80,0):
            box.separator()
            box.prop(scn, "DazDiffuseShader")
            box.prop(scn, "DazSpecularShader")
            box.prop(scn, "DazDiffuseRoughness")
            box.prop(scn, "DazSpecularRoughness")

        row = self.layout.row()
        row.operator("daz.load_root_paths")
        row.operator("daz.load_factory_settings")
        row.operator("daz.save_settings_file")
        row.operator("daz.load_settings_file")


    def run(self, context):
        GS.fromScene(context.scene)
        GS.saveDefaults()


    def invoke(self, context, event):
        GS.toScene(context.scene)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=1200)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    ImportDAZ,
    DAZ_OT_SetSilentMode,

    DAZ_OT_AddContentDir,
    DAZ_OT_AddMDLDir,
    DAZ_OT_AddCloudDir,
    DAZ_OT_LoadFactorySettings,
    DAZ_OT_LoadRootPaths,
    DAZ_OT_SaveSettingsFile,
    DAZ_OT_LoadSettingsFile,
    DAZ_OT_GlobalSettings,

    ErrorOperator
]


def initialize():

    bpy.types.Scene.DazContentDirs = CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ Content Directories",
        description = "Search paths for DAZ Studio content")

    bpy.types.Scene.DazMDLDirs = CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ MDL Directories",
        description = "Search paths for DAZ Studio MDL")

    bpy.types.Scene.DazCloudDirs = CollectionProperty(
        type = bpy.types.PropertyGroup,
        name = "DAZ Cloud Directories",
        description = "Search paths for DAZ Studio cloud content")

    bpy.types.Scene.DazErrorPath = StringProperty(
        name = "Error Path",
        description = "Path to error report file")

    bpy.types.Scene.DazUnitScale = FloatProperty(
        name = "Unit Scale",
        description = "Scale used to convert between DAZ and Blender units. Default unit meters",
        default = 0.01,
        precision = 3,
        min = 0.001, max = 10.0)

    bpy.types.Scene.DazVerbosity = IntProperty(
        name = "Verbosity",
        description = "Controls the number of warning messages when loading files",
        min=1, max = 5)

    bpy.types.Scene.DazPropMin = FloatProperty(
        name = "Property Minima",
        description = "Minimum value of properties",
        min = -10.0, max = 0.0)

    bpy.types.Scene.DazPropMax = FloatProperty(
        name = "Property Maxima",
        description = "Maximum value of properties",
        min = 0.0, max = 10.0)

    bpy.types.Scene.DazUsePropLimits = BoolProperty(
        name = "DAZ Property Limits",
        description = "Use the minima and maxima from DAZ files if available")

    bpy.types.Scene.DazUsePropDefault = BoolProperty(
        name = "DAZ Property Defaults",
        description = "Use the default values from DAZ files as default slider values.")


    # Object properties

    bpy.types.Object.DazId = StringProperty(
        name = "ID",
        default = "")

    bpy.types.Object.DazUrl = StringProperty(
        name = "URL",
        default = "")

    bpy.types.Object.DazScene = StringProperty(
        name = "Scene",
        default = "")

    bpy.types.Object.DazRig = StringProperty(
        name = "Rig Type",
        default = "")

    bpy.types.Object.DazMesh = StringProperty(
        name = "Mesh Type",
        default = "")

    bpy.types.Object.DazScale = FloatProperty(
        name = "Unit Scale",
        default = 0.01,
        precision = 4)

    bpy.types.Object.DazUnits = StringProperty(default = "")
    bpy.types.Object.DazExpressions = StringProperty(default = "")
    bpy.types.Object.DazVisemes = StringProperty(default = "")
    bpy.types.Object.DazBodies = StringProperty(default = "")
    bpy.types.Object.DazFlexions = StringProperty(default = "")
    bpy.types.Object.DazCorrectives = StringProperty(default = "")

    bpy.types.Object.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.PoseBone.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.PoseBone.DazAltName = StringProperty(default = "")
    bpy.types.Object.DazOrientMethod = StringProperty(name = "Orientation", default = "")
    bpy.types.Object.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazOrient = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazTail = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazAngle = FloatProperty(default=0)
    bpy.types.Object.DazNormal = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazTail = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazAngle = FloatProperty(default=0)
    bpy.types.Bone.DazNormal = FloatVectorProperty(size=3, default=(0,0,0))

    bpy.types.Object.DazRotLocks = BoolProperty(default = True)
    bpy.types.Object.DazLocLocks = BoolProperty(default = True)
    bpy.types.Object.DazRotLimits = BoolProperty(default = False)
    bpy.types.Object.DazLocLimits = BoolProperty(default = False)

    bpy.types.PoseBone.DazRotLocks = BoolVectorProperty(
        name = "Rotation Locks",
        size = 3,
        default = (False,False,False)
    )

    bpy.types.PoseBone.DazLocLocks = BoolVectorProperty(
        name = "Location Locks",
        size = 3,
        default = (False,False,False)
    )

    bpy.types.PoseBone.DazDriven = BoolProperty(default = False)

    bpy.types.Armature.DazExtraFaceBones = BoolProperty(default = False)
    bpy.types.Armature.DazExtraDrivenBones = BoolProperty(default = False)

    bpy.types.Scene.DazShowCorrections = BoolProperty(name = "Corrections", default = False)
    bpy.types.Scene.DazShowMaterials = BoolProperty(name = "Materials", default = False)
    bpy.types.Scene.DazShowMaterials2 = BoolProperty(name = "Materials", default = False)
    bpy.types.Scene.DazShowMorphs = BoolProperty(name = "Morphs", default = False)
    bpy.types.Scene.DazShowFinish = BoolProperty(name = "Finishing", default = False)
    bpy.types.Scene.DazShowRigging = BoolProperty(name = "Rigging", default = False)
    bpy.types.Scene.DazShowLowpoly = BoolProperty(name = "Low-poly Versions", default = False)
    bpy.types.Scene.DazShowVisibility = BoolProperty(name = "Visibility", default = False)
    bpy.types.Scene.DazShowRigging2 = BoolProperty(name = "Rigging", default = False)
    bpy.types.Scene.DazShowMesh = BoolProperty(name = "Mesh", default = False)
    bpy.types.Scene.DazShowMorphs2 = BoolProperty(name = "Morphs", default = False)
    bpy.types.Scene.DazShowHair = BoolProperty(name = "Hair", default = False)
    bpy.types.Scene.DazShowGeneral = BoolProperty(name = "General", default = False)
    bpy.types.Scene.DazShowPaths = BoolProperty(name = "Paths To DAZ Library", default = False)
    bpy.types.Scene.DazShowContentDirs = BoolProperty(name = "Content Directories", default = True)
    bpy.types.Scene.DazShowMDLDirs = BoolProperty(name = "MDL Directories", default = False)
    bpy.types.Scene.DazShowCloudDirs = BoolProperty(name = "Cloud Directories", default = False)


    bpy.types.Scene.DazFilter = StringProperty(
        name = "Filter",
        description = "Filter string",
        default = ""
    )

    bpy.types.Scene.DazMaterialMethod = EnumProperty(
        items = B.enumsMaterials,
        name = "Method",
        description = "Material Method",
        default = 'BSDF')

    bpy.types.Scene.DazRefractiveMethod = EnumProperty(
        items = [('BSDF', "BSDF", "Add BSDF refractive node group"),
                 ('SECOND', "Second Principled", "Add second principled node for refractive part"),
                 ('REUSE', "Reuse Principled",
                    ("Don't add extra nodes for refractive parts, but reuse the\n" +
                     "principled node for both opaque and refractive components.\n" +
                     "Introduces artifacts sometimes"))],
        name = "Refractive Method",
        description = "Method for refractive part of principled materials",
        default = 'BSDF')

    bpy.types.Scene.DazHairMaterialMethod = EnumProperty(
        items = B.enumsHair,
        name = "Hair",
        description = "Method for hair materials",
        default = 'HAIR_BSDF')

    bpy.types.Scene.DazChooseColors = EnumProperty(
        items = [('WHITE', "White", "Default diffuse color"),
                 ('RANDOM', "Random", "Random colors for each object"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Color Choice",
        description = "Method to use object colors")

    bpy.types.Scene.DazUseEnvironment = BoolProperty(
        name = "Environment",
        description = "Load environment")

    bpy.types.Scene.DazReuseMaterials = BoolProperty(
        name = "Reuse Materials",
        description = "Use existing materials if such exists.\nMay lead to incorrect materials")

    bpy.types.Scene.DazConnectClose = BoolProperty(
        name = "Connect Close",
        description = "Connect bones to their parent if the head is close to the parent's tail")

    bpy.types.Scene.DazUseLockLoc = BoolProperty(
        name = "Location Locks",
        description = "Use location locks")

    bpy.types.Scene.DazUseLimitLoc = BoolProperty(
        name = "Location Limits",
        description = "Use location limits")

    bpy.types.Scene.DazUseLockRot = BoolProperty(
        name = "Rotation Locks",
        description = "Use rotation locks")

    bpy.types.Scene.DazUseLimitRot = BoolProperty(
        name = "Rotation Limits",
        description = "Use rotation limits")

    bpy.types.Object.DazHasLocLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasLocLimits = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLimits = BoolProperty(default=False)

    bpy.types.Scene.DazZup = BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention.\nDisable for debugging only",
        default = True)

    bpy.types.Scene.DazOrientMethod = EnumProperty(
        items = [("BLENDER LEGACY", "Blender Legacy", "Legacy bone orientation used in version 1.5.0 and before"),
                 ("DAZ UNFLIPPED", "DAZ Unflipped", "DAZ Studio original bone orientation (for debugging only)"),
                 ("DAZ STUDIO", "DAZ Studio", "DAZ Studio bone orientation with flipped axes"),
                 ],
        name = "Orientation Method",
        description = "Bone orientation method",
        default = 'DAZ STUDIO')

    bpy.types.Scene.DazUseQuaternions = BoolProperty(
        name = "Quaternions",
        description = "Use quaternions for ball-and-socket joints (shoulders and hips)",
        default = False)

    bpy.types.Scene.DazUseLegacyLocks = BoolProperty(
        name = "Legacy Locks",
        description = "Use the simplified locks used by Blender Legacy mode",
        default = False)

    bpy.types.Scene.DazCaseSensitivePaths = BoolProperty(
        name = "Case-Sensitive Paths",
        description = "Convert URLs to lowercase. Works best on Windows.")

    bpy.types.Scene.DazUseInstancing = BoolProperty(
        name = "Use Instancing",
        description = "Use instancing for DAZ instances")

    bpy.types.Scene.DazBuildHighdef = BoolProperty(
        name = "Build HD Meshes",
        description = "Build HD meshes if included in .dbz file")

    bpy.types.Scene.DazMultires = BoolProperty(
        name = "Add Multires",
        description = "Add multires modifier to HD meshes and rebuild lower subdivision levels")

    bpy.types.Scene.DazInfluence = BoolProperty(
        name = "Influence Groups",
        description = "Add influence vertex groups")

    bpy.types.Scene.DazSimulation = BoolProperty(
        name = "Simulation",
        description = "Add simultations")

    bpy.types.Scene.DazMergeShells = BoolProperty(
        name = "Merge Shell Materials",
        description = "Merge shell materials with object materials.\nDisable for debugging only")

    bpy.types.Scene.DazPruneNodes = BoolProperty(
        name = "Prune Node Tree",
        description = "Prune material node-tree.\nDisable for debugging only")

    bpy.types.Scene.DazThinWall = FloatProperty(
        name = "Thin Wall Factor",
        description = "Mix factor between refraction and transparent nodes.\nIncrease this to avoid dark eyes problem for Genesis 8",
        min = 0, max = 1)

    bpy.types.Scene.DazMaxBump = FloatProperty(
        name = "Max Bump Strength",
        description = "Max bump strength",
        min = 0.1, max = 10)

    bpy.types.Scene.DazLimitBump = BoolProperty(
        name = "Limit Bump Strength",
        description = "Limit the bump strength")

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name = "Displacement",
        description = "Use displacement maps. Affects internal renderer only")

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name = "Emission",
        description = "Use emission.")

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name = "Reflection",
        description = "Use reflection maps. Affects internal renderer only")

    bpy.types.Scene.DazDiffuseRoughness = FloatProperty(
        name = "Diffuse Roughness",
        description = "Default diffuse roughness",
        min = 0, max = 1.0)

    bpy.types.Scene.DazSpecularRoughness = FloatProperty(
        name = "Specular Roughness",
        description = "Default specular roughness",
        min = 0, max = 1.0)

    bpy.types.Scene.DazDiffuseShader = EnumProperty(
        items = [
            ('FRESNEL', "Fresnel", ""),
            ('MINNAERT', "Minnaert", ""),
            ('TOON', "Toon", ""),
            ('OREN_NAYAR', "Oren-Nayar", ""),
            ('LAMBERT', "Lambert", "")
        ],
        name = "Diffuse Shader",
        description = "Diffuse shader (Blender Internal)")

    bpy.types.Scene.DazSpecularShader = EnumProperty(
        items = [
            ('WARDISO', "WardIso", ""),
            ('TOON', "Toon", ""),
            ('BLINN', "Blinn", ""),
            ('PHONG', "Phong", ""),
            ('COOKTORR', "CookTorr", "")
        ],
        name = "Specular Shader",
        description = "Specular shader (Blender Internal)")

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')
    bpy.types.Material.DazThinGlass = BoolProperty(default=False)

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

