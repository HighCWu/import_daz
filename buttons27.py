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


class AffectOptions:
    affectBones = BoolProperty(
        name = "Affect Bones",
        description = "Animate bones.",
        default = True)

    affectMorphs = BoolProperty(
        name = "Affect Morphs",
        description = "Animate morph properties.",
        default = True)

    affectObject = EnumProperty(
        items = [('OBJECT', "Object", "Animate global object transformation"),
                 ('MASTER', "Master Bone", "Object transformations affect master/root bone instead of object.\nOnly for MHX and Rigify"),
                 ('NONE', "None", "Don't animate global object transformations"),
                ],
        name = "Affect Object",
        description = "How to animate global object transformation",
        default = 'OBJECT')

    reportMissingMorphs = BoolProperty(
        name = "Report Missing Morphs",
        description = "Print a list of missing morphs.",
        default = False)

    affectSelectedOnly = BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones.",
        default = False)

    ignoreLimits = BoolProperty(
        name = "Ignore Limits",
        description = "Set pose even if outside limit constraints",
        default = True)

    ignoreLocks = BoolProperty(
        name = "Ignore Locks",
        description = "Set pose even for locked bones",
        default = False)


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

    atFrameOne = BoolProperty(
        name = "Start At Frame 1",
        description = "Always start actions at frame 1",
        default = False)

    firstFrame = IntProperty(
        name = "First Frame",
        description = "Start import with this frame",
        default = 1)

    lastFrame = IntProperty(
        name = "Last Frame",
        description = "Finish import with this frame",
        default = 250)


class PoseLibOptions:
    makeNewPoseLib = BoolProperty(
        name = "New Pose Library",
        description = "Unlink current pose library and make a new one",
        default = True)

    poseLibName = StringProperty(
        name = "Pose Library Name",
        description = "Name of loaded pose library",
        default = "PoseLib")

#-------------------------------------------------------------
#   daz.py
#-------------------------------------------------------------

class DazOptions:
    skinColor = FloatVectorProperty(
        name = "Skin",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.6, 0.4, 0.25, 1.0)
    )

    clothesColor = FloatVectorProperty(
        name = "Clothes",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.09, 0.01, 0.015, 1.0)
    )

    fitMeshes = EnumProperty(
        items = [('SHARED', "Unmorphed Shared (Environments)", "Don't fit meshes. All objects share the same mesh.\nFor environments with identical objects like leaves"),
                 ('UNIQUE', "Unmorped Unique (Environments)", "Don't fit meshes. Each object has unique mesh instance.\nFor environments with objects with same mesh but different materials, like paintings"),
                 ('DBZFILE', "DBZ File (Characters)", "Use exported .dbz (.json) file to fit meshes. Must exist in same directory.\nFor characters and other objects with morphs"),
                ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'DBZFILE')


class LoadRootPaths:
    useContent = BoolProperty(
        name = "Load Content Directories",
        default = True)

    useMDL = BoolProperty(
        name = "Load MDL Directories",
        default = True)

    useCloud = BoolProperty(
        name = "Load Cloud Directories",
        default = False)

#-------------------------------------------------------------
#   material.py
#-------------------------------------------------------------

class SlotString:
    slot = StringProperty()

class UseInternalBool:
    useInternal = BoolProperty(default=True)

class KeepDirsBool:
    keepdirs = BoolProperty(
        name = "Keep Directories",
        description = "Keep the directory tree from Daz Studio, otherwise flatten the directory structure",
        default = True)


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

    resizeAll = BoolProperty(
        name = "Resize All",
        description = "Resize all textures of the selected meshes",
        default = True)

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

class XYZ:
    X = FloatProperty(name = "X")
    Y = FloatProperty(name = "Y")
    Z = FloatProperty(name = "Z")

class PoleTargets:
    usePoleTargets = BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains.\nPoses will not be loaded correctly.",
        default = False)

class ConnectIK:
    type = EnumProperty(
        items = [('ARMS', "Arms Only", "Connect arms only"),
                 ('LEGS', "Legs Only", "Connect legs only"),
                 ('ARMSLEGS', "Arms And Legs", "Connect both arms and legs"),
                 ('SELECTED', "Selected", "Connect selected bones")],
        name = "Chain Types",
        description = "Connect the specified types of chains",
        default = 'ARMSLEGS')

    unlock = BoolProperty(
        name = "Unlock Last Bone",
        description = "Remove location locks of the last bone in each chain for use as Auto IK target",
        default = True)

    location = EnumProperty(
        items = [('HEAD', "Child Head", "Connect at the head of the child bone"),
                 ('TAIL', "Parent Tail", "Connect at the tail of the parent bone"),
                 ('CENTER', "Center", "Connect at the midpoint between the parent tail and child head")],
        name = "Location",
        description = "Where to connect parent and child bones",
        default = 'HEAD')

#-------------------------------------------------------------
#   fix.py
#-------------------------------------------------------------

class ThresholdFloat:
    threshold = FloatProperty(
        name = "Threshold",
        description = "Minimum vertex weight to keep",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 1e-3)


class AddIkGoals:
    usePoleTargets = BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains",
        default = False)

    hideBones = BoolProperty(
        name = "Hide Bones",
        description = "Hide all bones in the IK chains",
        default = False)

    lockBones = BoolProperty(
        name = "Lock Bones",
        description = "Lock all bones in the IK chains",
        default = False)

    disableBones = BoolProperty(
        name = "Disable Bones",
        description = "Disable all bones in the IK chains",
        default = False)

#-------------------------------------------------------------
#   merge.py
#-------------------------------------------------------------

class MergeRigs:
    clothesLayer = IntProperty(
        name = "Clothes Layer",
        description = "Bone layer used for extra bones when merging clothes",
        min = 1, max = 32,
        default = 3)

    separateCharacters = BoolProperty(
        name = "Separate Characters",
        description = "Don't merge armature that belong to different characters",
        default = False)

    useApplyRestPose = BoolProperty(
        name = "Apply Rest Pose",
        description = "Apply current pose as rest pose for all armatures",
        default = False)

    createMeshCollection = BoolProperty(
        name = "Create Mesh Collection",
        description = "Create a new collection and move all meshes to it",
        default = True)


def getUVTextures(scn, context):
    ob = context.object
    enums = []
    for n,uv in enumerate(ob.data.uv_textures):
        ename = "%s (%d)" % (uv.name, n)
        enums.append((str(n), ename, ename))
    return enums


class MergeUVLayers:
    layer1 = EnumProperty(
        items = getUVTextures,
        name = "Layer To Keep",
        description = "UV layer that the other layer is merged with")

    layer2 = EnumProperty(
        items = getUVTextures,
        name = "Layer To Merge",
        description = "UV layer that is merged with the other layer")

#-------------------------------------------------------------
#   morphing.py
#-------------------------------------------------------------

class MorphStrength:
    strength = FloatProperty(
        name = "Strength",
        description = "Strength of the morphs.\nOnly applies to shapekeys",
        default = 1.0
    )

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
    morphset = EnumProperty(
        items = [("All", "All", "All"),
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
#   geometry.py
#-------------------------------------------------------------

class LimitInt:
    limit = IntProperty(
        name = "Limit",
        description = "Max number of vertex group per vertex",
        default = 4,
        min = 1, max = 10
    )

#-------------------------------------------------------------
#   mhx.py
#-------------------------------------------------------------

class MHX:
    addTweakBones = BoolProperty(
        name = "Tweak Bones",
        description = "Add tweak bones",
        default = True
    )

    useLegacy = BoolProperty(
        name = "Legacy Bone Names",
        description = "Use root/hips rather than hip/pelvis",
        default = False
    )

class MHXConvertAction:
    direction = EnumProperty(
        items = [
            ('MODERN', "Legacy => Modern", "Convert from legacy MHX (root/hips) to modern MHX (hip/pelvis)"),
            ('LEGACY', "Modern => Legacy", "Convert from modern MHX (hip/pelvis) to legacy MHX (root/hips)"),
        ],
        name = "Direction",
        default = 'MODERN'
    )

#-------------------------------------------------------------
#   rigify.py
#-------------------------------------------------------------

class Rigify:
    deleteMeta = BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = False
    )

class Meta:
    useAutoAlign = BoolProperty(
        name = "Auto Align Hand/Foot",
        description = "Auto align hand and foot (Rigify parameter)",
        default = False
    )

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

class SingleGroup:
    singleGroup = BoolProperty(
        name = "Single Group",
        description = "Treat all selected meshes as a single group",
        default = False)

    groupName = StringProperty(
        name = "Group Name",
        description = "Name of the single group",
        default = "All")

class UseCollectionsBool:
    useCollections = False

#-------------------------------------------------------------
#   proxy.py
#-------------------------------------------------------------

class FractionFloat:
    fraction = FloatProperty(
        name = "Fraction",
        description = "Fraction of strands to select",
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

class Offset:
    offset = FloatProperty(
        name = "Offset (mm)",
        description = "Offset the surface from the character mesh",
        default = 5.0)

#-------------------------------------------------------------
#   hair.py
#-------------------------------------------------------------

class Hair:
    # Create

    strandType = EnumProperty(
        items = [('SHEET', "Sheet", "Sheets"),
                 ('LINE', "Line", "Polylines"),
                 ('TUBE', "Tube", "Tubes")],
        name = "Strand Type",
        description = "Mesh hair strand type",
        default = 'SHEET')

    strandOrientation = EnumProperty(
        items = [('TOP', "Top-Down", "Top-Down"),
                 ('BOTTOM', "Bottom-Up", "Bottom-Up"),
                 ('LEFT', "Left-Right", "Left-Right"),
                 ('RIGHT', "Right-Left", "Right-Left")],
        name = "Strand Orientation",
        default = 'TOP',
        description = "How the strands are oriented in UV space"
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
        min = 3,
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

    # Settings

    useVertexGroup = BoolProperty(
        name = "Use Vertex Group",
        description = "Use top vertex vertex group for density",
        default = False)

    nViewChildren = IntProperty(
        name = "Viewport Children",
        description = "Number of hair chilren displayed in viewport",
        min = 0,
        default = 0)

    nRenderChildren = IntProperty(
        name = "Render Children",
        description = "Number of hair chilren displayed in renders",
        min = 0,
        default = 0)

    # Materials

    keepMaterial = BoolProperty(
        name = "Keep Material",
        description = "Use existing material",
        default = True)

    activeMaterial = EnumProperty(
        items = G.getActiveMaterial,
        name = "Material",
        description = "Material to use as hair material")

    color = FloatVectorProperty(
        name = "Hair Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.2, 0.02, 0.01, 1)
    )

    hairMaterialMethod = EnumProperty(
        items = [('BSDF', "BSDF", "BSDF "),
                 ('INTERNAL', "Internal", "Internal")],
        name = "Hair Material Method",
        description = "Type of hair material node tree",
        default = 'BSDF')

    useRootTransparency = BoolProperty(
        name = "Root Transparency",
        description = "Add randomized transparency at the root of the strands",
        default = False)


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

    useOverwrite = BoolProperty(
        name = "Overwrite Existing Shapekeys",
        description = "Overwrite existing shapekeys or create new ones",
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

    allSimilar = BoolProperty(
        name = "Mix All Similar",
        description = "Mix all shapekeys with similar names",
        default = False)

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

class DazVectorGroup(bpy.types.PropertyGroup):
    a = FloatVectorProperty(size=3)

class DazStrandGroup(bpy.types.PropertyGroup):
    strand = CollectionProperty(type = DazVectorGroup)

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
