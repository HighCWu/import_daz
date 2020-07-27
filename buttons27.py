# Copyright (c) 2016-2020, Thomas Larsson
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
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import globvars as G

#-------------------------------------------------------------
#   animation.py
#-------------------------------------------------------------

class ConvertOptions:
    convertPoses = BoolProperty(
        name = "Convert Poses",
        description = "Attempt to convert poses to the current rig.",
        default = False)

    srcCharacter = EnumProperty(
        items = G.theRestPoseItems,
        name = "Source Character",
        description = "Character this file was made for",
        default = "genesis_3_female")

    trgCharacter = EnumProperty(
        items = G.theRestPoseItems,
        name = "Target Character",
        description = "Active character",
        default = "genesis_3_female")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "convertPoses")
        if self.convertPoses:
            layout.prop(self, "srcCharacter")
            #layout.prop(self, "trgCharacter")


class AffectOptions:
    clearBones = BoolProperty(
        name = "Clear Bones",
        description = "Clear bones pose before adding new one",
        default = True)

    clearMorphs = BoolProperty(
        name = "Clear Morphs",
        description = "Clear morph pose before adding new one",
        default = True)

    clearObject = BoolProperty(
        name = "Clear Object",
        description = "Clear object pose before adding new one",
        default = True)

    affectBones = BoolProperty(
        name = "Affect Bones",
        description = "Animate bones.",
        default = True)

    affectMorphs = BoolProperty(
        name = "Affect Morphs",
        description = "Animate morph properties.",
        default = True)

    affectObject = BoolProperty(
        name = "Affect Object",
        description = "Animate global object transformation",
        default = True)

    reportMissingMorphs = BoolProperty(
        name = "Report Missing Morphs",
        description = "Print a list of missing morphs.",
        default = False)

    affectSelectedOnly = BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones.",
        default = False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clearBones")
        layout.prop(self, "clearObject")
        layout.prop(self, "clearMorphs")
        layout.prop(self, "affectBones")
        if self.affectBones:
            layout.prop(self, "affectSelectedOnly")
        layout.prop(self, "affectObject")
        layout.prop(self, "affectMorphs")
        if self.affectMorphs:
            layout.prop(self, "reportMissingMorphs")


class ActionOptions:
    makeNewAction = BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName = StringProperty(
        name = "Action Name",
        description = "Name of loaded action",
        default = "Action")

    fps = FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in Daz Studio",
        default = 30)

    integerFrames = BoolProperty(
        name = "Integer Frames",
        description = "Round all keyframes to intergers",
        default = True)

    useAction = True
    usePoseLib = False
    useDrivers = False
    useTranslations = True
    useRotations = True
    useScale = True
    useGeneral = True

    def draw(self, context):
        layout = self.layout
        layout.separator()
        layout.prop(self, "makeNewAction")
        layout.prop(self, "actionName")
        layout.prop(self, "fps")
        layout.prop(self, "integerFrames")


class PoseLibOptions:
    makeNewPoseLib = BoolProperty(
        name = "New Pose Library",
        description = "Unlink current pose library and make a new one",
        default = True)

    poseLibName = StringProperty(
        name = "Pose Library Name",
        description = "Name of loaded pose library",
        default = "PoseLib")

    useAction = False
    usePoseLib = True
    useDrivers = False
    useTranslations = True
    useRotations = True
    useScale = True
    useGeneral = True

    def draw(self, context):
        layout = self.layout
        layout.separator()
        layout.prop(self, "makeNewPoseLib")
        layout.prop(self, "poseLibName")

#-------------------------------------------------------------
#   daz.py
#-------------------------------------------------------------

class DazOptions:
    unitScale = FloatProperty(
        name = "Unit Scale",
        description = "Scale used to convert between DAZ and Blender units. Default unit meters",
        default = 0.01,
        precision = 3,
        min = 0.001, max = 10.0)

    skinColor = FloatVectorProperty(
        name = "Skin Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.6, 0.4, 0.25, 1.0)
    )

    clothesColor = FloatVectorProperty(
        name = "Clothes Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.09, 0.01, 0.015, 1.0)
    )

    brightenEyes = FloatProperty(
        name = "Brighten Eyes",
        description = "Brighten eye textures with this factor\nto avoid dark eyes problem for Genesis 8",
        default = 1.0,
        min = 0.1, max = 10)

    fitMeshes = EnumProperty(
    items = [('SHARED', "Unmorphed Shared", "Don't fit meshes. All objects share the same mesh."),
             ('UNIQUE', "Unmorped Unique", "Don't fit meshes. Each object has unique mesh instance."),
             ('DBZFILE', "DBZ (JSON) File", "Use exported .dbz (.json) file to fit meshes. Must exist in same directory."),
            ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'DBZFILE')

    useDazBones = BoolProperty(
        name = "Daz Bones",
        description = "Match bones exactly with Daz Studio",
        default = False)

    useDazOrientation = BoolProperty(
        name = "Daz Orientation",
        description = "Orient bones as in Daz Studio",
        default = False)

    useAutoMaterials = BoolProperty(
        name = "Auto Material Method",
        description = "Use best shaders for material, independent of the settings below",
        default = True)

    methodOpaque = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ],
        name = "Opaque Method",
        description = "Default method used for opaque materials.\nIgnored by some materials.",
        default = 'BSDF')

    methodRefractive = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ],
        name = "Refractive Method",
        description = "Default method used for refractive materials.\nIgnored by some materials.",
        default = 'PRINCIPLED')

    methodVolumetric = EnumProperty(
        items = [('VOLUMETRIC', "Volumetric", "Volumetric (Iray)"),
                 ('TRANSLUCENCY', "Translucency Only", "Translucency only"),
                 ('SSS', "SSS", "Subsurface scattering"),
                 ],
        name = "Volumetric Method",
        description = "Method for handle volumetric (Iray skin)",
        default = 'VOLUMETRIC')

    useEnvironment = BoolProperty(
        name = "Environment",
        description = "Load environment",
        default = True)

#-------------------------------------------------------------
#   material.py
#-------------------------------------------------------------

class SlotString:
    slot = StringProperty()

class UseInternalBool:
    useInternal = BoolProperty(default=True)


class CopyMaterials:
    useMatchNames = BoolProperty(
        name = "Match Names",
        description = "Match materials based on names rather than material number",
        default = False)

    errorMismatch = BoolProperty(
        name = "Error On Mismatch",
        description = "Raise an error if the number of source and target materials are different",
        default = True)


class ResizeOptions:
    steps = IntProperty(
        name = "Steps",
        description = "Resize original images with this number of steps",
        min = 0, max = 8,
        default = 2)

    overwrite = BoolProperty(
        name = "Overwrite Files",
        description = "Overwrite the original image files.",
        default = False)


class ColorProp:
    color = FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.1, 0.1, 0.5, 1)
    )

#-------------------------------------------------------------
#   matedit.py
#-------------------------------------------------------------

class EditSlotGroup(bpy.types.PropertyGroup):
    ncomps = IntProperty(default = 0)

    color = FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (1,1,1,1)
    )

    vector = FloatVectorProperty(
        name = "Vector",
        size = 3,
        min = 0.0,
        max = 1.0,
        default = (0,0,0)
    )

    number = FloatProperty(default = 0.0)
    new = BoolProperty()


class ShowGroup(bpy.types.PropertyGroup):
    show = BoolProperty(default = False)

class LaunchEditor:
    shows = CollectionProperty(type = ShowGroup)

#-------------------------------------------------------------
#   figure.py
#-------------------------------------------------------------

class BoneLayers:
    poseLayer = IntProperty(
        name = "Posable Bone Layer",
        description = "Put the posable bones on this layer.",
        min = 1, max = 32,
        default = 8)

    drivenLayer = IntProperty(
        name = "Driven Bone Layer",
        description = "Put the driven bones on this layer.",
        min = 1, max = 32,
        default = 32)

class XYZ:
    X = FloatProperty(name = "X")
    Y = FloatProperty(name = "Y")
    Z = FloatProperty(name = "Z")

#-------------------------------------------------------------
#   merge.py
#-------------------------------------------------------------

class MergeRigs:
    clothesLayer = IntProperty(
        name = "Clothes Layer",
        description = "Bone layer used for extra bones when merging clothes",
        min = 1, max = 32,
        default = 3)

#-------------------------------------------------------------
#   morphing.py
#-------------------------------------------------------------

class MorphStrings:
    catname = StringProperty(
        name = "Category",
        default = "Shapes")

    usePropDrivers = BoolProperty(
        name = "Use drivers",
        description = "Control morphs with rig properties",
        default = True)


class CategoryString:
    category = StringProperty(
        name = "Category",
        description = "Add morphs to this category of custom morphs",
        default = "Shapes"
        )

class CustomEnums:
    custom = EnumProperty(
        items = G.getActiveCategories,
        name = "Category")

class StandardEnums:
    type = EnumProperty(
        morphset = [("Units", "Units", "Units"),
                 ("Expressions", "Expressions", "Expressions"),
                 ("Visemes", "Visemes", "Visemes"),
                 ("Body", "Body", "Body"),
                ],
        name = "Type",
        default = "Units")

class StandardAllEnums:
    type = EnumProperty(
        morphset = [("All", "All", "All"),
                 ("Units", "Units", "Units"),
                 ("Expressions", "Expressions", "Expressions"),
                 ("Visemes", "Visemes", "Visemes"),
                 ("Body", "Body", "Body"),
                ],
        name = "Type",
        default = "All")

class DeleteShapekeysBool:
    deleteShapekeys = BoolProperty(
        name = "Delete Shapekeys",
        description = "Delete both drivers and shapekeys",
        default = True
    )


class DazSelectGroup(bpy.types.PropertyGroup):
    text = StringProperty()
    category = StringProperty()
    index = IntProperty()
    select = BoolProperty()

    def __lt__(self, other):
        return (self.text < other.text)


class Selection:
    selection = CollectionProperty(type = DazSelectGroup)

    filter = StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
        )

class MorphSets:
    useStandard = BoolProperty(
        name = "Standard Morphs",
        description = "Remove drivers to all standard morphs",
        default = True)

    useCustom = BoolProperty(
        name = "Custom Morphs",
        description = "Remove drivers to all custom morphs",
        default = True)

    useJCM = BoolProperty(
        name = "JCMs",
        description = "Remove drivers to all JCMs",
        default = False)

#-------------------------------------------------------------
#   convert.py
#-------------------------------------------------------------

class NewRig:
    newRig = EnumProperty(
        items = G.theRestPoseItems,
        name = "New Rig",
        description = "Convert active rig to this",
        default = "genesis_3_female")

#-------------------------------------------------------------
#   hide.py
#-------------------------------------------------------------

class HideOnlyMasked:
    hideOnlyMasked = BoolProperty(
        name = "Hide Only Masked",
        description = "Create visibility drivers only for masked meshes",
        default = False)

#-------------------------------------------------------------
#   proxy.py
#-------------------------------------------------------------

class FractionFloat:
    fraction = FloatProperty(
        name = "Keep Fraction",
        description = "Fraction of strands to keep",
        min = 0.0, max = 1.0,
        default = 0.5)

class IterationsInt:
    iterations = IntProperty(
        name = "Iterations",
        description = "Number of iterations when ",
        min = 0, max = 10,
        default = 2)

class Mannequin:
    headType = EnumProperty(
        items = [('SOLID', "Solid", "Solid head"),
                 ('JAW', "Jaw", "Head with jaws and eyes"),
                 ('FULL', "Full", "Head with all face bones"),
                 ],
        name = "Head Type",
        description = "How to make the mannequin head",
        default = 'JAW')

    useGroup = BoolProperty(
        name = "Add To Collection",
        description = "Add mannequin to collection",
        default = True)

    group = StringProperty(
        name = "Collection",
        description = "Add mannequin to this collection",
        default = "Mannequin")


#-------------------------------------------------------------
#   hair.py
#-------------------------------------------------------------

class Hair:
    color = FloatVectorProperty(
        name = "Hair Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.5, 0.05, 0.1, 1)
    )

    sparsity = IntProperty(
        name = "Sparsity",
        min = 1,
        max = 50,
        default = 1,
        description = "Only use every n:th hair"
    )

    size = IntProperty(
        name = "Hair Length",
        min = 5,
        max = 100,
        default = 20,
        description = "Hair length"
    )

    resizeHair = BoolProperty(
        name = "Resize Hair",
        default = False,
        description = "Resize hair afterwards"
    )

    resizeInBlocks = BoolProperty(
        name = "Resize In Blocks",
        default = False,
        description = "Resize hair in blocks of ten afterwards"
    )

    skullType = EnumProperty(
        items = [('NONE', "None", "No Skull group"),
                 ('TOP', "Top", "Assign only top vertex to Skull group"),
                 ('ALL', "All", "Assign all vertices to Skull group"),
                 ],
        name = "Skull Group",
        description = "Vertex group to control hair density",
        default = 'TOP')


class Pinning:
    pinningX0 = FloatProperty(
        name = "Pin X0",
        min = 0.0,
        max = 1.0,
        default = 0.25,
        precision = 3,
        description = ""
    )

    pinningX1 = FloatProperty(
        name = "Pin X1",
        min = 0.0,
        max = 1.0,
        default = 0.75,
        precision = 3,
        description = ""
    )

    pinningW0 = FloatProperty(
        name = "Pin W0",
        min = 0.0,
        max = 1.0,
        default = 1.0,
        precision = 3,
        description = ""
    )

    pinningW1 = FloatProperty(
        name = "Pin W1",
        min = 0.0,
        max = 1.0,
        default = 0.0,
        precision = 3,
        description = ""
    )

#-------------------------------------------------------------
#   transfer.py
#-------------------------------------------------------------

class TransferOptions:

    useDriver = BoolProperty(
        name = "Use Driver",
        description = "Transfer both shapekeys and drivers",
        default = True)

    useSelectedOnly = BoolProperty(
        name = "Selected Verts Only",
        description = "Only copy to selected vertices",
        default = False)

    ignoreRigidity = BoolProperty(
        name = "Ignore Rigidity Groups",
        description = "Ignore rigidity groups when auto-transfer morphs.\nMorphs may differ from DAZ Studio.",
        default = False)


class MixShapekeysOptions:
    shape1 = EnumProperty(
        items = G.shapekeyItems1,
        name = "Shapekey 1",
        description = "First shapekey")

    shape2 = EnumProperty(
        items = G.shapekeyItems2,
        name = "Shapekey 2",
        description = "Second shapekey")

    factor1 = FloatProperty(
        name = "Factor 1",
        description = "First factor",
        default = 1.0)

    factor2 = FloatProperty(
        name = "Factor 2",
        description = "Second factor",
        default = 1.0)

    overwrite = BoolProperty(
        name = "Overwrite First",
        description = "Overwrite the first shapekey",
        default = True)

    delete = BoolProperty(
        name = "Delete Merged",
        description = "Delete unused shapekeys after merge",
        default = True)

    newName = StringProperty(
        name = "New shapekey",
        description = "Name of new shapekey",
        default = "Shapekey")

    filter1 = StringProperty(
        name = "Filter 1",
        description = "Show only items containing this string",
        default = ""
        )

    filter2 = StringProperty(
        name = "Filter 2",
        description = "Show only items containing this string",
        default = ""
        )

#-------------------------------------------------------------
#   String properties
#-------------------------------------------------------------

class DataString:
    data = StringProperty()

class ToggleString:
    toggle = StringProperty()

class PrefixString:
    prefix = StringProperty()

class TypeString:
    type = StringProperty()

class ValueBool:
    value = BoolProperty()

class KeyString:
    key = StringProperty()

class NameString:
    name = StringProperty()

class ActionString:
    action = StringProperty()

class MorphsetString:
    morphset = StringProperty(default = "")
    prefix = StringProperty(default = "")

class UseOpenBool:
    useOpen = BoolProperty()

class UseAllBool:
    useAll = BoolProperty()

class SkelPoseBool:
    skeleton = BoolProperty("Skeleton", default=True)
    pose = BoolProperty("Pose", default=True)

#-------------------------------------------------------------
#   Import and Export helpers
#-------------------------------------------------------------

class MultiFile(ImportHelper):
    files = CollectionProperty(
            name = "File Path",
            type = bpy.types.OperatorFileListElement,
            )
    directory = StringProperty(
            subtype='DIR_PATH',
            )


class SingleFile(ImportHelper):
    filepath = StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        default="")


class AnimatorFile:
    filename_ext = ".duf"
    filter_glob = StringProperty(default = G.theDazDefaults + G.theImagedDefaults, options={'HIDDEN'})


class JsonFile:
    filename_ext = ".json"
    filter_glob = StringProperty(default="*.json", options={'HIDDEN'})


class DbzFile:
    filename_ext = ".dbz"
    filter_glob = StringProperty(default="*.dbz;*.json", options={'HIDDEN'})


class JsonExportFile(ExportHelper):
    filename_ext = ".json"
    filter_glob = StringProperty(default="*.json", options={'HIDDEN'})
    filepath = StringProperty(
        name="File Path",
        description="Filepath used for exporting the .json file",
        maxlen=1024,
        default = "")


class ImageFile:
    filename_ext = ".png;.jpeg;.jpg;.bmp;.tif;.tiff"
    filter_glob = StringProperty(default="*.png;*.jpeg;*.jpg;*.bmp;*.tif;*.tiff", options={'HIDDEN'})


class DazImageFile:
    filename_ext = ".duf"
    filter_glob = StringProperty(default="*.duf;*.dsf;*.png;*.jpeg;*.jpg;*.bmp", options={'HIDDEN'})


class DazFile:
    filename_ext = ".dsf;.duf;.dbz"
    filter_glob = StringProperty(default="*.dsf;*.duf;*.dbz", options={'HIDDEN'})


class DatFile:
    filename_ext = ".dat"
    filter_glob = StringProperty(default="*.dat", options={'HIDDEN'})


class TextFile:
    filename_ext = ".txt"
    filter_glob = StringProperty(default="*.txt", options={'HIDDEN'})

#-------------------------------------------------------------
#   Property groups
#-------------------------------------------------------------

class DazMorphGroupProps:
    prop = StringProperty()
    factor = FloatProperty()
    factor2 = FloatProperty()
    index = IntProperty()
    default = FloatProperty()
    simple = BoolProperty(default=True)


class DazIntGroup(bpy.types.PropertyGroup):
    a = IntProperty()

class DazPairGroup(bpy.types.PropertyGroup):
    a = IntProperty()
    b = IntProperty()

class DazStringStringGroup(bpy.types.PropertyGroup):
    names = CollectionProperty(type = bpy.types.PropertyGroup)

class DazDriverGroup(bpy.types.PropertyGroup):
    index = IntProperty()
    expression = StringProperty()
    channel = StringProperty()

class DazStringGroup(bpy.types.PropertyGroup):
    s = StringProperty()

class DazKeys(bpy.types.PropertyGroup):
    keys = CollectionProperty(type = StringProperty)

class DazActiveGroup(bpy.types.PropertyGroup):
    active = BoolProperty(default = True)

class DazTextGroup(bpy.types.PropertyGroup):
    text = StringProperty()

    def __lt__(self, other):
        return (self.text < other.text)

class DazCategory(bpy.types.PropertyGroup):
    custom = StringProperty()
    morphs = CollectionProperty(type = DazTextGroup)
    active = BoolProperty(default=False)

class DazFormula(bpy.types.PropertyGroup):
    prop = StringProperty()
    value = FloatProperty()

#-------------------------------------------------------------
#   Rigidity groups
#-------------------------------------------------------------

class DazRigidityGroup(bpy.types.PropertyGroup):
    id = StringProperty()
    rotation_mode = StringProperty()
    scale_modes = StringProperty()
    reference_vertices = CollectionProperty(type = DazIntGroup)
    mask_vertices = CollectionProperty(type = DazIntGroup)
    use_transform_bones_for_scale = BoolProperty()
