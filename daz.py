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

from .error import *
from .utils import *
from .fileutils import SingleFile, JsonFile, JsonExportFile, DazImageFile

#------------------------------------------------------------------
#   Classes
#------------------------------------------------------------------

EnumsMaterials = [('BSDF', "BSDF", "BSDF (Cycles, full IRAY materials)"),
                  ('PRINCIPLED', "Principled", "Principled (Eevee and Cycles)")]

EnumsHair = [('HAIR_BSDF', "Hair BSDF", "Hair BSDF (Cycles)"),
             ('HAIR_PRINCIPLED', "Hair Principled", "Hair Principled (Cycles)"),
             ('PRINCIPLED', "Principled", "Principled (Eevee and Cycles)")]

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class DazOptions(DazImageFile, SingleFile):

    skinColor : FloatVectorProperty(
        name = "Skin",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.6, 0.4, 0.25, 1.0)
    )

    clothesColor : FloatVectorProperty(
        name = "Clothes",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.09, 0.01, 0.015, 1.0)
    )

    fitMeshes : EnumProperty(
        items = [('SHARED', "Unmorphed Shared (Environments)", "Don't fit meshes. All objects share the same mesh.\nFor environments with identical objects like leaves"),
                 ('UNIQUE', "Unmorped Unique (Environments)", "Don't fit meshes. Each object has unique mesh instance.\nFor environments with objects with same mesh but different materials, like paintings"),
                 ('MORPHED', "Morphed (Characters)", "Don't fit meshes, but load shapekeys.\nNot all shapekeys are found.\nShapekeys are not transferred to clothes"),
                 ('DBZFILE', "DBZ File (Characters)", "Use exported .dbz (.json) file to fit meshes. Must exist in same directory.\nFor characters and other objects with morphs"),
                ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'DBZFILE')

    morphStrength : FloatProperty(
        name = "Morph Strength",
        description = "Morph strength",
        default = 1.0)

    def draw(self, context):
        box = self.layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)
        if self.fitMeshes == 'MORPHED':
            box.prop(self, "morphStrength")
        self.layout.separator()
        box = self.layout.box()
        box.label(text = "Viewport Color")
        if GS.viewportColors == 'GUESS':
            row = box.row()
            row.prop(self, "skinColor")
            row.prop(self, "clothesColor")
        else:
            box.label(text = GS.viewportColors)


class ImportDAZ(DazOperator, DazOptions):
    """Load a DAZ File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ"
    bl_description = "Load a native DAZ file"
    bl_options = {'PRESET', 'UNDO'}

    def run(self, context):
        from .main import getMainAsset
        getMainAsset(self.filepath, context, self)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        box = self.layout.box()
        box.label(text = "For more options, see Global Settings.")


class MorphTypeOptions:
    units : BoolProperty(
        name = "Face Units",
        description = "Import all face units",
        default = False)

    expressions : BoolProperty(
        name = "Expressions",
        description = "Import all expressions",
        default = False)

    visemes : BoolProperty(
        name = "Visemes",
        description = "Import all visemes",
        default = False)

    facs : BoolProperty(
        name = "FACS",
        description = "Import all FACS units",
        default = False)

    facsexpr : BoolProperty(
        name = "FACS Expressions",
        description = "Import all FACS expressions",
        default = False)

    body : BoolProperty(
        name = "Body",
        description = "Import all body morphs",
        default = False)

    jcms : BoolProperty(
        name = "JCMs",
        description = "Import all JCMs",
        default = False)

    flexions : BoolProperty(
        name = "Flexions",
        description = "Import all flexions",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "units")
        self.layout.prop(self, "expressions")
        self.layout.prop(self, "visemes")
        self.layout.prop(self, "facs")
        self.layout.prop(self, "facsexpr")
        self.layout.prop(self, "body")
        self.layout.prop(self, "jcms")
        self.layout.prop(self, "flexions")


class EasyImportDAZ(DazOperator, DazOptions, MorphTypeOptions):
    """Load a DAZ File and perform the most common opertations"""
    bl_idname = "daz.easy_import_daz"
    bl_label = "Easy Import DAZ"
    bl_description = "Load a native DAZ file and perform the most common operations"
    bl_options = {'UNDO'}

    rigType : EnumProperty(
        items = [('DAZ', "DAZ", "Original DAZ rig"),
                 ('CUSTOM', "Custom Shapes", "Original DAZ rig with custom shapes"),
                 ('MHX', "MHX", "MHX rig"),
                 ('RIGIFY', "Rigify", "Rigify")],
        name = "Rig Type",
        description = "Convert the main rig to a more animator-friendly rig",
        default = 'DAZ')

    mannequinType : EnumProperty(
        items = [('NONE', "None", "Don't make mannequins"),
                 ('NUDE', "Nude", "Make mannequin for main mesh only"),
                 ('ALL', "All", "Make mannequin from all meshes")],
        name = "Mannequin Type",
        description = "Add mannequin to meshes of this type",
        default = 'NONE')

    useMergeRigs : BoolProperty(
        name = "Merge Rigs",
        description = "Merge all rigs to the main character rig",
        default = True)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge identical materials",
        default = True)

    useMergeToes : BoolProperty(
        name = "Merge Toes",
        description = "Merge separate toes into a single toe bone",
        default = False)

    useTransferJCMs : BoolProperty(
        name = "Transfer JCMs",
        description = "Transfer JCMs and flexions from character to clothes",
        default = True)

    useMergeGeografts : BoolProperty(
        name = "Merge Geografts",
        description = "Merge selected geografts to active object.\nDoes not work with nested geografts.\nShapekeys are always transferred first",
        default = False)

    useMergeLashes : BoolProperty(
        name = "Merge Lashes",
        description = "Merge separate eyelash mesh to character.\nShapekeys are always transferred first",
        default = False)

    useExtraFaceBones : BoolProperty(
        name = "Extra Face Bones",
        description = "Add an extra layer of face bones, which can be both driven and posed",
        default = True)

    useMakeAllBonesPoseable : BoolProperty(
        name = "Make All Bones Poseable",
        description = "Add an extra layer of driven bones, to make them poseable",
        default = False)

    useConvertHair : BoolProperty(
        name = "Convert Hair",
        description = "Convert strand-based hair to particle hair",
        default = False)

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "rigType")
        self.layout.prop(self, "mannequinType")
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "useMergeRigs")
        self.layout.prop(self, "useMergeToes")
        self.layout.prop(self, "useMergeGeografts")
        self.layout.prop(self, "useMergeLashes")
        self.layout.prop(self, "useExtraFaceBones")
        self.layout.prop(self, "useMakeAllBonesPoseable")
        self.layout.prop(self, "useConvertHair")
        MorphTypeOptions.draw(self, context)
        if self.jcms or self.flexions:
            self.layout.prop(self, "useTransferJCMs")


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        from .error import setSilentMode
        from time import perf_counter
        time1 = perf_counter()
        try:
            bpy.ops.daz.import_daz(
                filepath = self.filepath,
                skinColor = self.skinColor,
                clothesColor = self.clothesColor,
                fitMeshes = self.fitMeshes)
        except:
            if LS.warning:
                print("Warning:", LS.warning)
            else:
                raise DazError("Import failed")

        if not LS.objects:
            raise DazError("No objects found")
        setSilentMode(True)
        self.rigs = LS.rigs
        self.meshes = LS.meshes
        self.objects = LS.objects
        self.hdmeshes = LS.hdmeshes
        self.hairs = LS.hairs
        for rigname in self.rigs.keys():
            self.treatRig(context, rigname)
        setSilentMode(False)
        time2 = perf_counter()
        print("File %s loaded in %.3f seconds" % (self.filepath, time2-time1))


    def treatRig(self, context, rigname):
        rigs = self.rigs[rigname]
        meshes = self.meshes[rigname]
        objects = self.objects[rigname]
        hdmeshes = self.hdmeshes[rigname]
        hairs = self.hairs[rigname]
        if len(rigs) > 0:
            mainRig = rigs[0]
        else:
            mainRig = None
        if len(meshes) > 0:
            mainMesh = meshes[0]
        else:
            mainMesh = None
        if mainRig:
            from .finger import getFingeredCharacter
            _,_,mainChar = getFingeredCharacter(mainRig)
        else:
            mainChar = None
        if mainChar:
            print("Main character:", mainChar)
        else:
            print("Did not recognize main character", mainMesh)

        empties = []
        for ob in objects:
            if ob.type == None:
                empties.append(ob)

        geografts = []
        lashes = []
        if mainMesh and mainRig:
            nmeshes = [mainMesh]
            lmeshes = self.getLashes(mainRig, mainMesh)
            for ob in meshes[1:]:
                if ob.data.DazGraftGroup and self.useMergeGeografts:
                    geografts.append(ob)
                elif ob in lmeshes and self.useMergeLashes:
                    lashes.append(ob)
                else:
                    nmeshes.append(ob)
            meshes = nmeshes

        if mainRig:
            # Merge rigs
            activateObject(context, mainRig)
            for rig in rigs[1:]:
                rig.select_set(True)
            if self.useMergeRigs and len(rigs) > 1:
                print("Merge rigs")
                bpy.ops.daz.merge_rigs()
                mainRig = context.object
                rigs = [mainRig]

            # Eliminate empties
            activateObject(context, mainRig)
            bpy.ops.daz.eliminate_empties()

            # Merge toes
            if self.useMergeToes:
                print("Merge toes")
                bpy.ops.daz.merge_toes()

            # Add extra face bones
            if self.useExtraFaceBones:
                print("Add extra face bones")
                bpy.ops.daz.add_extra_face_bones()

        if mainMesh:
            # Merge materials
            activateObject(context, mainMesh)
            for ob in meshes[1:]:
                ob.select_set(True)
            print("Merge materials")
            bpy.ops.daz.merge_materials()

        if mainChar and mainRig and mainMesh:
            if (self.units or
                self.expressions or
                self.visemes or
                self.facs or
                self.facsexpr or
                self.body or
                self.jcms or
                self.flexions):
                activateObject(context, mainRig)
                bpy.ops.daz.import_standard_morphs(
                    units = self.units,
                    expressions = self.expressions,
                    visemes = self.visemes,
                    facs = self.facs,
                    facsexpr = self.facsexpr,
                    body = self.body,
                    jcms = self.jcms,
                    flexions = self.flexions)


        # Merge geografts
        if geografts:
            self.transferShapes(context, mainMesh, geografts, False, "Body")
            activateObject(context, mainMesh)
            for ob in geografts:
                ob.select_set(True)
            print("Merge geografts")
            bpy.ops.daz.merge_geografts()

        # Merge lashes
        if lashes:
            self.transferShapes(context, mainMesh, lashes, False, "Face")
            activateObject(context, mainMesh)
            for ob in lashes:
                ob.select_set(True)
            print("Merge lashes")
            self.mergeLashes(mainMesh)

        # Transfer shapekeys to clothes
        self.transferShapes(context, mainMesh, meshes[1:], True, "Body")

        if mainRig:
            activateObject(context, mainRig)
            # Make all bones poseable
            if self.useMakeAllBonesPoseable:
                print("Make all bones poseable")
                bpy.ops.daz.make_all_bones_poseable()

        # Convert hairs
        if hairs and mainMesh and self.useConvertHair:
            activateObject(context, mainMesh)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            for hair in hairs:
                activateObject(context, hair)
                mainMesh.select_set(True)
                bpy.ops.daz.make_hair(strandType='TUBE')

        # Change rig
        if mainRig:
            activateObject(context, mainRig)
            if self.rigType == 'CUSTOM':
                print("Add custom shapes")
                bpy.ops.daz.add_custom_shapes()
            elif self.rigType == 'MHX':
                print("Convert to MHX")
                bpy.ops.daz.convert_to_mhx()
            elif self.rigType == 'RIGIFY':
                bpy.ops.daz.convert_to_rigify(useDeleteMeta=True)
                mainRig = context.object

        # Make mannequin
        if mainRig and mainMesh and self.mannequinType != 'NONE':
            activateObject(context, mainMesh)
            if self.mannequinType == 'ALL':
                for ob in meshes:
                    ob.select_set(True)
            print("Make mannequin")
            bpy.ops.daz.add_mannequin(useGroup=True, group="%s Mannequin" % mainRig.name)

        if mainMesh:
            mainMesh.update_tag()
        if mainRig:
            mainRig.update_tag()
            activateObject(context, mainRig)



    def transferShapes(self, context, ob, meshes, useDrivers, bodypart):
        if not (self.useTransferJCMs and (self.jcms or self.flexions)):
            return
        if not (ob and meshes):
            return

        from .fileutils import setSelection
        from .morphing import classifyShapekeys
        skeys = ob.data.shape_keys
        if skeys:
            bodyparts = classifyShapekeys(ob, skeys)
            snames = [sname for sname,bpart in bodyparts.items() if bpart == bodypart]
            if not snames:
                return
            activateObject(context, ob)
            selected = False
            for mesh in meshes:
                if self.useTransferTo(mesh):
                    mesh.select_set(True)
                    selected = True
            if not selected:
                return
            setSelection(snames)
            if not useDrivers:
                bpy.ops.daz.transfer_shapekeys(useDrivers=False)
            else:
                bpy.ops.daz.transfer_shapekeys(useDrivers=True)


    def useTransferTo(self, mesh):
        if not getModifier(mesh, 'ARMATURE'):
            return False
        ishair = ("head" in mesh.vertex_groups.keys() and
                  "lSldrBend" not in mesh.vertex_groups.keys())
        return not ishair


    def mergeLashes(self, ob):
        from .merge import mergeUVLayers
        nlayers = len(ob.data.uv_layers)
        bpy.ops.object.join()
        idxs = list(range(nlayers, len(ob.data.uv_layers)))
        idxs.reverse()
        for idx in idxs:
            mergeUVLayers(ob.data, 0, idx)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        print("Lashes merged")


    def getLashes(self, rig, ob):
        meshes = []
        for mesh in getMeshChildren(rig):
            if mesh != ob:
                for vgname in mesh.vertex_groups.keys():
                    if vgname[1:7] == "Eyelid":
                        meshes.append(mesh)
                        break
        return meshes

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


class DAZ_OT_SaveSettingsFile(bpy.types.Operator, SingleFile, JsonExportFile):
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
    bl_description = "Restore all global settings to factory defaults"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.__init__()
        GS.toScene(context.scene)
        return {'PASS_THROUGH'}


class DAZ_OT_LoadRootPaths(DazOperator, SingleFile, JsonFile):
    bl_idname = "daz.load_root_paths"
    bl_label = "Load Root Paths"
    bl_description = "Load DAZ root paths from file"
    bl_options = {'UNDO'}

    useContent : BoolProperty(
        name = "Load Content Directories",
        default = True)

    useMDL : BoolProperty(
        name = "Load MDL Directories",
        default = True)

    useCloud : BoolProperty(
        name = "Load Cloud Directories",
        default = False)


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


class DAZ_OT_LoadSettingsFile(DazOperator, SingleFile, JsonFile):
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
        split = self.layout.split(factor=0.4)
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
        box.prop(scn, "DazCaseSensitivePaths")

        box = col.box()
        box.label(text = "Debugging")
        box.prop(scn, "DazZup")
        box.prop(scn, "DazDump")
        box.prop(scn, "DazMakeHiddenSliders")
        box.prop(scn, "DazPruneNodes")
        box.prop(scn, "DazMergeShells")

        box = col.box()
        box.label(text = "Sliders")
        box.prop(scn, "DazFinalLimits")
        box.prop(scn, "DazRawLimits")
        box.prop(scn, "DazCustomMin")
        box.prop(scn, "DazCustomMax")
        box.prop(scn, "DazShowFinalProps")

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
        box.label(text = "Meshes")
        box.prop(scn, "DazBuildHighdef")
        box.prop(scn, "DazMultires")
        box.prop(scn, "DazUseInstancing")

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
        box.prop(scn, "DazViewportColor")
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
    EasyImportDAZ,
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


def register():

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
        subtype="DIR_PATH",
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

    bpy.types.Scene.DazCustomMin = FloatProperty(
        name = "Custom Min",
        description = "Custom minimum",
        default = -2.0,
        min = -10.0, max = 0.0)

    bpy.types.Scene.DazCustomMax = FloatProperty(
        name = "Custom Max",
        description = "Custom maximum",
        default = 2.0,
        min = 0.0, max = 10.0)

    enums = [('DAZ', "DAZ", "Use min and max values from DAZ files if available"),
             ('CUSTOM', "Custom", "Use min and max values from custom sliders"),
             ('NONE', "None", "Don't limit sliders")]

    bpy.types.Scene.DazFinalLimits = EnumProperty(
        items = enums,
        name = "Final Limits",
        description = "Min and max values for \"final\" sliders")

    bpy.types.Scene.DazRawLimits = EnumProperty(
        items = enums,
        name = "Raw Limits",
        description = "Min and max values for \"raw\" sliders")

    bpy.types.Scene.DazShowFinalProps = BoolProperty(
        name = "Show Final Sliders",
        description = "Display the \"final\" slider values")

    bpy.types.Scene.DazMakeHiddenSliders = BoolProperty(
        name = "Make Hidden Sliders",
        description = "Create properties for hidden morphs,\nso they can be displayed in the UI",
        default = False)

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
        items = EnumsMaterials,
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
        items = EnumsHair,
        name = "Hair",
        description = "Method for hair materials",
        default = 'HAIR_BSDF')

    bpy.types.Scene.DazViewportColor = EnumProperty(
        items = [('ORIGINAL', "Original", "Original diffuse color"),
                 ('RANDOM', "Random", "Random colors for each material"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Viewport Color",
        description = "Method to display object in viewport")

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

    bpy.types.Scene.DazDump = BoolProperty(
        name = "Dump Debug Info",
        description = "Dump debug info in the file\ndaz_importer_errors.text after loading file")

    bpy.types.Scene.DazZup = BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention.\nDisable for debugging only")

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
        description = "Use quaternions for ball-and-socket joints (shoulders and hips)")

    bpy.types.Scene.DazUseLegacyLocks = BoolProperty(
        name = "Legacy Locks",
        description = "Use the simplified locks used by Blender Legacy mode")

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

    bpy.types.Scene.DazMaxBump = FloatProperty(
        name = "Max Bump Strength",
        description = "Max bump strength",
        min = 0.1, max = 10)

    bpy.types.Scene.DazLimitBump = BoolProperty(
        name = "Limit Bump Strength",
        description = "Limit the bump strength")

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name = "Displacement",
        description = "Use displacement maps")

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name = "Emission",
        description = "Use emission.")

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name = "Reflection",
        description = "Use reflection maps")

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

