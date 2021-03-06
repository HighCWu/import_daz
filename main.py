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
from .fileutils import SingleFile, MultiFile, DazFile, DazImageFile

#------------------------------------------------------------------
#   DAZ options
#------------------------------------------------------------------

class DazOptions(DazImageFile):

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

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(DazOperator, DazOptions, MultiFile):
    """Load a DAZ File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ"
    bl_description = "Load a native DAZ file"
    bl_options = {'PRESET', 'UNDO'}

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        box = self.layout.box()
        box.label(text = "For more options, see Global Settings.")

    def storeState(self, context):
        pass

    def restoreState(self, context):
        pass

    def run(self, context):
        from time import perf_counter
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        elif len(filepaths) > 1:
            t1 = perf_counter()
        LS.forImport(self)
        for filepath in filepaths:
            self.loadDazFile(filepath, context)
        if LS.render:
            LS.render.build(context)
        if GS.useDump:
            from .error import dumpErrors
            dumpErrors(filepath)
        if len(filepaths) > 1:
            t2 = perf_counter()
            print("Total load time: %.3f seconds" % (t2-t1))

        msg = ""
        if LS.missingAssets:
            msg = ("Some assets were not found.\n" +
                   "Check that all Daz paths have been set up correctly.        \n" +
                   "For details see\n'%s'" % getErrorPath())
        else:
            if LS.hdFailures:
                msg += "Could not rebuild subdivisions for the following HD objects:       \n"
                for hdname in LS.hdFailures:
                    msg += ("  %s\n" % hdname)
            if LS.hdWeights:
                msg += "Could not copy vertex weights to the following HD objects:         \n"
                for hdname in LS.hdWeights:
                    msg += ("  %s\n" % hdname)
            if LS.hdUvMissing:
                msg += "HD objects missing UV layers:\n"
                for hdname in LS.hdUvMissing:
                    msg += ("  %s\n" % hdname)
                msg += "Export from DAZ Studio with Multires disabled.        \n"
        if msg:
            clearErrorMessage()
            handleDazError(context, warning=True, dump=True)
            print(msg)
            LS.warning = True
            raise DazError(msg, warning=True)

        from .material import checkRenderSettings
        msg = checkRenderSettings(context, False)
        if msg:
            LS.warning = True
            raise DazError(msg, warning=True)
        LS.reset()


    def loadDazFile(self, filepath, context):
        from time import perf_counter
        from .objfile import getFitFile, fitToFile

        LS.scene = filepath
        t1 = perf_counter()
        startProgress("\nLoading %s" % filepath)
        if LS.fitFile:
            getFitFile(filepath)

        from .load_json import loadJson
        struct = loadJson(filepath)
        showProgress(10, 100)

        grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
        LS.collection = makeRootCollection(grpname, context)

        print("Parsing data")
        from .files import parseAssetFile
        main = parseAssetFile(struct, toplevel=True)
        if main is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)
        showProgress(20, 100)

        print("Preprocessing...")
        for asset,inst in main.nodes:
            inst.preprocess(context)

        if LS.fitFile:
            fitToFile(filepath, main.nodes)
        showProgress(30, 100)

        for asset,inst in main.nodes:
            inst.preprocess2(context)
        for asset,inst in main.modifiers:
            asset.preprocess(inst)

        print("Building objects...")
        for asset in main.materials:
            asset.build(context)
        showProgress(50, 100)

        nnodes = len(main.nodes)
        idx = 0
        for asset,inst in main.nodes:
            showProgress(50 + int(idx*30/nnodes), 100)
            idx += 1
            asset.build(context, inst)      # Builds armature
        showProgress(80, 100)

        nmods = len(main.modifiers)
        idx = 0
        for asset,inst in main.modifiers:
            showProgress(80 + int(idx*10/nmods), 100)
            idx += 1
            asset.build(context, inst)      # Builds morphs 1
        showProgress(90, 100)

        for _,inst in main.nodes:
            inst.poseRig(context)
        for asset,inst in main.nodes:
            inst.postbuild(context)

        # Need to update scene before calculating object areas
        updateScene(context)
        for asset in main.materials:
            asset.postbuild()

        print("Postprocessing...")
        for asset,inst in main.modifiers:
            asset.postbuild(context, inst)
        for _,inst in main.nodes:
            inst.buildInstance(context)
        for _,inst in main.nodes:
            inst.finalize(context)

        from .node import transformDuplis
        transformDuplis(context)

        t2 = perf_counter()
        print('File "%s" loaded in %.3f seconds' % (filepath, t2-t1))

#------------------------------------------------------------------
#   MorphTypeOptions
#   Also used in morphing.py
#------------------------------------------------------------------

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

    useMhxOnly : BoolProperty(
        name = "MHX Compatible Only",
        description = "Only import MHX compatible body morphs",
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
        if self.body:
            self.subprop("useMhxOnly")
        self.layout.prop(self, "jcms")
        self.layout.prop(self, "flexions")

    def subprop(self, prop):
        split = self.layout.split(factor=0.05)
        split.label(text="")
        split.prop(self, prop)

#------------------------------------------------------------------
#   Easy Import
#------------------------------------------------------------------

class EasyImportDAZ(DazOperator, DazOptions, MorphTypeOptions, MultiFile):
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

    useEliminateEmpties : BoolProperty(
        name = "Eliminate Empties",
        description = "Delete non-hidden empties, parenting its children to its parent instead",
        default = True)

    useMergeRigs : BoolProperty(
        name = "Merge Rigs",
        description = "Merge all rigs to the main character rig",
        default = True)

    useCreateDuplicates : BoolProperty(
        name = "Create Duplicate Bones",
        description = "Create separate bones if several bones with the same name are found",
        default = False)

    useMergeMaterials : BoolProperty(
        name = "Merge Materials",
        description = "Merge identical materials",
        default = True)

    useMergeToes : BoolProperty(
        name = "Merge Toes",
        description = "Merge separate toes into a single toe bone",
        default = False)

    useTransferShapes : BoolProperty(
        name = "Transfer Shapekeys",
        description = "Transfer shapekeys from character to clothes",
        default = True)

    useMergeGeografts : BoolProperty(
        name = "Merge Geografts",
        description = "Merge selected geografts to active object.\nDoes not work with nested geografts.\nShapekeys are always transferred first",
        default = False)

    useMergeLashes : BoolProperty(
        name = "Merge Lashes",
        description = "Merge separate eyelash mesh to character.\nShapekeys are always transferred first",
        default = False)

    useConvertWidgets : BoolProperty(
        name = "Convert To Widgets",
        description = "Convert widget mesh to bone custom shapes",
        default = False)

    useMakeAllBonesPoseable : BoolProperty(
        name = "Make All Bones Poseable",
        description = "Add an extra layer of driven bones, to make them poseable",
        default = False)

    useFavoMorphs : BoolProperty(
        name = "Use Favorite Morphs",
        description = "Load a favorite morphs instead of loading standard morphs",
        default = False)

    favoPath : StringProperty(
        name = "Favorite Morphs",
        description = "Path to favorite morphs")

    useConvertHair : BoolProperty(
        name = "Convert Hair",
        description = "Convert strand-based hair to particle hair",
        default = False)

    addTweakBones : BoolProperty(
        name = "Tweak Bones",
        description = "Add tweak bones",
        default = True
    )

    useFingerIk : BoolProperty(
        name = "Finger IK",
        description = "Generate IK controls for fingers",
        default = False)

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "useEliminateEmpties")
        self.layout.prop(self, "useMergeRigs")
        if self.useMergeRigs:
            self.subprop("useCreateDuplicates")
        self.layout.prop(self, "useMergeToes")
        self.layout.prop(self, "useFavoMorphs")
        if self.useFavoMorphs:
            self.layout.prop(self, "favoPath")
        MorphTypeOptions.draw(self, context)
        if self.useFavoMorphs or self.jcms or self.flexions:
            self.layout.prop(self, "useTransferShapes")
        self.layout.prop(self, "useMergeGeografts")
        self.layout.prop(self, "useMergeLashes")
        self.layout.prop(self, "useConvertWidgets")
        self.layout.prop(self, "useMakeAllBonesPoseable")
        self.layout.prop(self, "useConvertHair")
        self.layout.prop(self, "rigType")
        if self.rigType == 'MHX':
            self.subprop("addTweakBones")
            self.subprop("useFingerIk")
        elif self.rigType == 'RIGIFY':
            self.subprop("useFingerIk")
        self.layout.prop(self, "mannequinType")

    def invoke(self, context, event):
        self.favoPath = context.scene.DazFavoPath
        return MultiFile.invoke(self, context, event)

    def storeState(self, context):
        pass

    def restoreState(self, context):
        pass


    def run(self, context):
        from .fileutils import getExistingFilePath
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:
            raise DazError("No valid files selected")
        if self.useFavoMorphs:
            self.favoPath = getExistingFilePath(self.favoPath, ".json")
        for filepath in filepaths:
            try:
                self.easyImport(context, filepath)
            except DazError as msg:
                raise DazError(msg)


    def easyImport(self, context, filepath):
        from time import perf_counter
        time1 = perf_counter()
        G.theFilePaths = [filepath]
        bpy.ops.daz.import_daz(
            skinColor = self.skinColor,
            clothesColor = self.clothesColor,
            fitMeshes = self.fitMeshes)

        if not LS.objects:
            raise DazError("No objects found")
        G.theSilentMode = True
        visibles = getVisibleObjects(context)
        self.rigs = self.getTypedObjects(visibles, LS.rigs)
        self.meshes = self.getTypedObjects(visibles, LS.meshes)
        self.objects = self.getTypedObjects(visibles, LS.objects)
        self.hdmeshes = self.getTypedObjects(visibles, LS.hdmeshes)
        self.hairs = self.getTypedObjects(visibles, LS.hairs)

        if self.useEliminateEmpties:
            bpy.ops.object.select_all(action='DESELECT')
            for objects in LS.objects.values():
                for ob in objects:
                    selectSet(ob, True)
            bpy.ops.daz.eliminate_empties()

        for rigname in self.rigs.keys():
            self.treatRig(context, rigname)
        G.theSilentMode = False
        context.scene.DazFavoPath = self.favoPath
        time2 = perf_counter()
        print("File %s loaded in %.3f seconds" % (self.filepath, time2-time1))


    def getTypedObjects(self, visibles, struct):
        nstruct = {}
        for key,objects in struct.items():
            nstruct[key] = [ob for ob in objects if (ob and ob in visibles)]
        return nstruct


    def treatRig(self, context, rigname):
        from .finger import isCharacter, getFingerPrint
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
            mainChar = isCharacter(mainRig)
        else:
            mainChar = None
        if mainChar:
            print("Main character:", mainChar)
        elif mainMesh:
            print("Did not recognize main character", mainMesh.name)

        geografts = {}
        lashes = []
        clothes = []
        widgetMesh = None
        if mainMesh and mainRig:
            lmeshes = self.getLashes(mainRig, mainMesh)
            for ob in meshes[1:]:
                finger = getFingerPrint(ob)
                if ob.data.DazGraftGroup:
                    cob = self.getGraftParent(ob, meshes)
                    if cob:
                        if cob.name not in geografts.keys():
                            geografts[cob.name] = ([], cob)
                        geografts[cob.name][0].append(ob)
                    else:
                        clothes.append(ob)
                elif self.useConvertWidgets and finger == "1778-3059-1366":
                    widgetMesh = ob
                elif ob in lmeshes:
                    lashes.append(ob)
                else:
                    clothes.append(ob)

        if mainRig and activateObject(context, mainRig):
            # Merge rigs
            for rig in rigs[1:]:
                selectSet(rig, True)
            if self.useMergeRigs and len(rigs) > 1:
                print("Merge rigs")
                bpy.ops.daz.merge_rigs(useCreateDuplicates=self.useCreateDuplicates)
                mainRig = context.object
                rigs = [mainRig]

            # Merge toes
            if activateObject(context, mainRig):
                if self.useMergeToes:
                    print("Merge toes")
                    bpy.ops.daz.merge_toes()

        if mainMesh and activateObject(context, mainMesh):
            # Merge materials
            for ob in meshes[1:]:
                selectSet(ob, True)
            print("Merge materials")
            bpy.ops.daz.merge_materials()

        if mainChar and mainRig and mainMesh:
            if self.useFavoMorphs:
                if activateObject(context, mainRig) and self.favoPath:
                    bpy.ops.daz.load_favo_morphs(filepath = self.favoPath)
            if (self.units or
                  self.expressions or
                  self.visemes or
                  self.facs or
                  self.facsexpr or
                  self.body or
                  self.jcms or
                  self.flexions):
                if activateObject(context, mainRig):
                    bpy.ops.daz.import_standard_morphs(
                        units = self.units,
                        expressions = self.expressions,
                        visemes = self.visemes,
                        facs = self.facs,
                        facsexpr = self.facsexpr,
                        body = self.body,
                        useMhxOnly = self.useMhxOnly,
                        jcms = self.jcms,
                        flexions = self.flexions)


        # Merge geografts
        if geografts:
            if self.useTransferShapes or self.useMergeGeografts:
                for aobs,cob in geografts.values():
                    if cob == mainMesh:
                        self.transferShapes(context, cob, aobs, self.useMergeGeografts, "Body")
                for aobs,cob in geografts.values():
                    if cob != mainMesh:
                        self.transferShapes(context, cob, aobs, self.useMergeGeografts, "All")
            if self.useMergeGeografts and activateObject(context, mainMesh):
                for aobs,cob in geografts.values():
                    for aob in aobs:
                        selectSet(aob, True)
                print("Merge geografts")
                bpy.ops.daz.merge_geografts()
                if GS.viewportColors == 'GUESS':
                    from .guess import guessMaterialColor
                    LS.skinColor = self.skinColor
                    for mat in mainMesh.data.materials:
                        guessMaterialColor(mat, 'GUESS', True, LS.skinColor)

        # Merge lashes
        if lashes:
            if self.useTransferShapes or self.useMergeLashes:
                self.transferShapes(context, mainMesh, lashes, self.useMergeLashes, "Face")
            if self.useMergeLashes and activateObject(context, mainMesh):
                for ob in lashes:
                    selectSet(ob, True)
                print("Merge lashes")
                self.mergeLashes(mainMesh)

        # Transfer shapekeys to clothes
        if self.useTransferShapes:
            self.transferShapes(context, mainMesh, clothes, False, "Body")

        # Convert widget mesh to widgets
        if widgetMesh and mainRig and activateObject(context, widgetMesh):
            print("Convert to widgets")
            bpy.ops.daz.convert_widgets()

        if mainRig and activateObject(context, mainRig):
            # Make all bones poseable
            if self.useMakeAllBonesPoseable:
                print("Make all bones poseable")
                bpy.ops.daz.make_all_bones_poseable()

        # Convert hairs
        if (hairs and
            mainMesh and
            self.useConvertHair and
            activateObject(context, mainMesh)):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            for hair in hairs:
                if activateObject(context, hair):
                    selectSet(mainMesh, True)
                    bpy.ops.daz.make_hair(strandType='TUBE')

        # Change rig
        if mainRig and activateObject(context, mainRig):
            if self.rigType == 'CUSTOM':
                print("Add custom shapes")
                bpy.ops.daz.add_custom_shapes()
            elif self.rigType == 'MHX':
                print("Convert to MHX")
                bpy.ops.daz.convert_to_mhx(
                    addTweakBones = self.addTweakBones,
                    useFingerIk = self.useFingerIk,
                )
            elif self.rigType == 'RIGIFY':
                bpy.ops.daz.convert_to_rigify(
                    useDeleteMeta = True,
                    useFingerIk = self.useFingerIk)
                mainRig = context.object

        # Make mannequin
        if (mainRig and
            mainMesh and
            self.mannequinType != 'NONE' and
            activateObject(context, mainMesh)):
            if self.mannequinType == 'ALL':
                for ob in clothes:
                    selectSet(ob, True)
            print("Make mannequin")
            bpy.ops.daz.add_mannequin(useGroup=True, group="%s Mannequin" % mainRig.name)

        if mainMesh:
            mainMesh.update_tag()
        if mainRig:
            mainRig.update_tag()
            activateObject(context, mainRig)


    def getGraftParent(self, ob, meshes):
        for cob in meshes:
            if len(cob.data.vertices) == ob.data.DazVertexCount:
                return cob
        return None


    def transferShapes(self, context, ob, meshes, skipDrivers, bodypart):
        if not (ob and meshes):
            return
        from .morphing import classifyShapekeys
        skeys = ob.data.shape_keys
        if skeys:
            bodyparts = classifyShapekeys(ob, skeys)
            if bodypart == "All":
                snames = [sname for sname,bpart in bodyparts.items()]
            else:
                snames = [sname for sname,bpart in bodyparts.items() if bpart in [bodypart, "All"]]
            if not snames:
                return
            activateObject(context, ob)
            selected = False
            for mesh in meshes:
                if self.useTransferTo(mesh):
                    selectSet(mesh, True)
                    selected = True
            if not selected:
                return
            G.theFilePaths = snames
            bpy.ops.daz.transfer_shapekeys(useDrivers=(not skipDrivers))


    def useTransferTo(self, mesh):
        if not getModifier(mesh, 'ARMATURE'):
            return False
        ishair = ("head" in mesh.vertex_groups.keys() and
                  "lSldrBend" not in mesh.vertex_groups.keys())
        return not ishair


    def mergeLashes(self, ob):
        from .merge import mergeUvLayers
        nlayers = len(ob.data.uv_layers)
        bpy.ops.object.join()
        idxs = list(range(nlayers, len(ob.data.uv_layers)))
        idxs.reverse()
        for idx in idxs:
            mergeUvLayers(ob.data, 0, idx)
        setMode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        setMode('OBJECT')
        print("Lashes merged")


    def getLashes(self, rig, ob):
        meshes = []
        for mesh in getMeshChildren(rig):
            if mesh != ob:
                isLash = False
                for vgname in mesh.vertex_groups.keys():
                    if vgname[1:7] == "Eyelid":
                        isLash = True
                    elif vgname in ["lEye", "head"]:
                        isLash = False
                        break
                if isLash:
                    meshes.append(mesh)
        return meshes

#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def makeRootCollection(grpname, context):
    root = bpy.data.collections.new(name=grpname)
    context.scene.collection.children.link(root)
    return root

#------------------------------------------------------------------
#   Decode file
#------------------------------------------------------------------

class DAZ_OT_DecodeFile(DazOperator, DazFile, SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf, *.dbz) to a text file"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        import gzip
        from .asset import getDazPath
        from .fileutils import safeOpen

        print("Decode",  self.filepath)
        try:
            with gzip.open(self.filepath, 'rb') as fp:
                bytes = fp.read()
        except IOError as err:
            msg = ("Cannot decode:\n%s" % self.filepath +
                   "Error: %s" % err)
            print(msg)
            raise DazError(msg)

        try:
            string = bytes.decode("utf_8_sig")
        except UnicodeDecodeError as err:
            msg = ('Unicode error while reading zipped file\n"%s"\n%s' % (self.filepath, err))
            print(msg)
            raise DazError(msg)

        newfile = self.filepath + ".txt"
        with safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)

#------------------------------------------------------------------
#   Launch quoter
#------------------------------------------------------------------

class DAZ_OT_Quote(DazOperator):
    bl_idname = "daz.quote"
    bl_label = "Quote"

    def execute(self, context):
        from .asset import normalizeRef
        global theQuoter
        theQuoter.Text = normalizeRef(theQuoter.Text)
        return {'PASS_THROUGH'}


class DAZ_OT_Unquote(DazOperator):
    bl_idname = "daz.unquote"
    bl_label = "Unquote"

    def execute(self, context):
        global theQuoter
        theQuoter.Text = unquote(theQuoter.Text)
        return {'PASS_THROUGH'}


class DAZ_OT_QuoteUnquote(bpy.types.Operator):
    bl_idname = "daz.quote_unquote"
    bl_label = "Quote/Unquote"
    bl_description = "Quote or unquote specified text"

    Text : StringProperty(description = "Type text to quote or unquote")

    def draw(self, context):
        self.layout.prop(self, "Text", text="")
        row = self.layout.row()
        row.operator("daz.quote")
        row.operator("daz.unquote")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        global theQuoter
        theQuoter = self
        wm = context.window_manager
        return wm.invoke_popup(self, width=800)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

def menu_func_import(self, context):
    self.layout.operator(ImportDAZ.bl_idname, text="DAZ (.duf, .dsf)")
    self.layout.operator(EasyImportDAZ.bl_idname, text="Easy DAZ (.duf, .dsf)")


classes = [
    ImportDAZ,
    EasyImportDAZ,
    DAZ_OT_DecodeFile,
    DAZ_OT_Quote,
    DAZ_OT_Unquote,
    DAZ_OT_QuoteUnquote,
]

def register():
    bpy.types.Scene.DazFavoPath = StringProperty(
        name = "Favorite Morphs",
        description = "Path to favorite morphs",
        subtype = 'FILE_PATH',
        default = "")

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
