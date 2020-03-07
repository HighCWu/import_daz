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

#-------------------------------------------------------------
#   animation.py
#-------------------------------------------------------------

from .globvars import theImagedDefaults
from .globvars import theDazDefaults
from .globvars import thePoserDefaults, theImagedPoserDefaults
from .globvars import theRestPoseItems

class ConvertOptions:
    convertPoses = BoolProperty(
        name = "Convert Poses",
        description = "Attempt to convert poses to the current rig.",
        default = False)

    srcCharacter = EnumProperty(
        items = theRestPoseItems,
        name = "Source Character",
        description = "Character this file was made for",
        default = "genesis_3_female")

    trgCharacter = EnumProperty(
        items = theRestPoseItems,
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
    useClearPose = BoolProperty(
        name = "Clear Pose",
        description = "Clear pose before adding new one",
        default = True)

    affectObject = BoolProperty(
        name = "Affect Object",
        description = "Don't ignore global object transformation",
        default = True)

    affectValues = BoolProperty(
        name = "Affect Values",
        description = "Animate properties like facial expressions.",
        default = True)

    reportMissing = BoolProperty(
        name = "Report Missing Morphs",
        description = "Print a list of missing morphs.",
        default = True)

    selectedOnly = BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones.",
        default = False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "useClearPose")
        layout.prop(self, "affectObject")
        layout.prop(self, "affectValues")
        layout.prop(self, "reportMissing")
        layout.prop(self, "selectedOnly")


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
        default = 1.8,
        min = 0.1, max = 10)        

    fitMeshes = EnumProperty(
        items = [('SHARED', "Unmorphed Shared", "Don't fit meshes. All objects share the same mesh."),
             ('UNIQUE', "Unmorped Unique", "Don't fit meshes. Each object has unique mesh instance."),
             ('JSONFILE', "Json File", "Use exported JSON (.json) file to fit meshes. Must exist in same directory."),
            ],
        name = "Mesh Fitting",
        description = "Mesh fitting method",
        default = 'JSONFILE')

    useAutoMaterials = BoolProperty(
        name = "Auto Material Method",
        description = "Use best shaders for material, independent of the settings below",
        default = True)

    handleOpaque = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ('EEVEE', "Eevee", "Simple opaque material that works with Eevee"),
                 ],
        name = "Opaque Materials",
        description = "Default method used for opaque materials.\nIgnored by some materials.",
        default = 'PRINCIPLED')

    handleRefractive = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ('GUESS', "Guess", "Guess material properties, suitable for eyes. Turn on caustics."),
                 ('EEVEE', "Eevee", "Simple transparent material that works with Eevee"),
                 ],
        name = "Refractive Materials",
        description = "Default method used for refractive materials.\nIgnored by some materials.",
        default = 'GUESS')

    handleVolumetric = EnumProperty(
        items = [('VOLUMETRIC', "Volumetric", "Volumetric (Iray)"),
                 ('TRANSLUCENCY', "Translucency", "Translucency only"),
                 ('SSS', "SSS", "Subsurface scattering"),
                 ],
        name = "Skin Options",
        description = "Method for handle volumetric (Iray skin)",
        default = 'VOLUMETRIC')
        
    useEnvironment = BoolProperty(
        name = "Environment",
        description = "Load environment",
        default = True)

    useSimulation = BoolProperty(
        name = "Simulations",
        description = "Load dForce simulations",
        default = False)

#-------------------------------------------------------------
#   material.py
#-------------------------------------------------------------

class SlotString:
    slot = StringProperty()

class UseInternalBool:
    useInternal = BoolProperty(default=True)

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
    color = bpy.props.FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.1, 0.1, 0.5, 1)
    )

from .globvars import TweakableChannels

class LaunchEditor:
    colorFactor = FloatVectorProperty(
        name = "Color Factor/Value",
        subtype = "COLOR",
        size = 4,
        min = 0,
        default = (1, 1, 1, 1)
    )        

    tweakableChannel = EnumProperty(
        items = [(key,key,key) for key in TweakableChannels.keys()],
        name = "Active Channel",
        description = "Active channel to be tweaked",
        default = "Bump Strength")

    factor = FloatProperty(
        name = "Factor/Value",
        description = "Set/Multiply active channel with this factor",
        min = 0,
        default = 1.0)

    useAbsoluteTweak = BoolProperty(
        name = "Absolute Values",
        description = "Tweak channels with absolute values",
        default = False)

    tweakMaterials = EnumProperty(
        items = [("Skin", "Skin", "Skin"),
                 ("Skin-Lips-Nails", "Skin-Lips-Nails", "Skin-Lips-Nails"),
                 ("Opaque", "Opaque", "Opaque"),
                 ("Refractive", "Refractive", "Refractive"),
                 ("All", "All", "All")],
        name = "Material Type",
        description = "Type of materials to tweak",
        default = "Skin")

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

#-------------------------------------------------------------
#   merge.py
#-------------------------------------------------------------

class ClothesLayer:
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

    useDrivers = BoolProperty(
        name = "Use drivers",
        description = "Control morphs with rig properties",
        default = True)


class PoseStrings:
    catname = StringProperty(
        name = "Category",
        default = "Poses")


class MorphTypes:
    units = BoolProperty(name = "Units", default = True)
    expressions = BoolProperty(name = "Expressions", default = True)
    visemes = BoolProperty(name = "Visemes", default = True)
    other = BoolProperty(name = "Other", default = False)    

#-------------------------------------------------------------
#   convert.py
#-------------------------------------------------------------

class NewRig:
    newRig = EnumProperty(
        items = theRestPoseItems,
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
        name = "Add To Group",
        description = "Add mannequin to group",
        default = True)

    group = StringProperty(
        name = "Group",
        description = "Add mannequin to this group",
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
#   poser.py
#-------------------------------------------------------------

class ScaleLock:
    unitScale = FloatProperty(
        name = "Unit Scale",
        description = "Scale used to convert between DAZ and Blender units. Default unit meters",
        default = 0.01,
        precision = 3,
        min = 0.001, max = 10.0)

    lockMeshes = BoolProperty(
        name = "Lock Meshes",
        description = "Lock meshes with armature modifier",
        default = True)

#-------------------------------------------------------------
#   transfer.py
#-------------------------------------------------------------

class TransferOptions:
    transferMethod = EnumProperty(
        items = [('AUTO', "Auto", "Only auto-transfer morphs, never use morph files"),
                 ('FILES', "Files", "Only use morph files, never auto-transfer"),
                 ('BOTH', "Both", "Use morph file if found, otherwise auto-transfer"),
        ],
        name = "Transfer Method",
        description = "How to transfer morphs to target mesh",
        default = 'BOTH')

    searchMethod = EnumProperty(
        items = [('AUTO', "Auto", "Search for files automatically"),
                 ('CURRENT', "Current", "Search in current directory"),
                 ('SUBDIR', "Subdirs", "Search in current directory and subdirectories"),
        ],
        name = "File Search Method",
        description = "How to search for morph files",
        default = 'AUTO')

    useDriver = BoolProperty(
        name = "Use Driver",
        description = "Transfer both shapekeys and drivers",
        default = True)

    useActiveOnly = BoolProperty(
        name = "Use Active Shapekey Only",
        description = "Only transfer the active shapekey",
        default = False)

    startsWith = StringProperty(
        name = "Starts with",
        description = "Only transfer shapekeys that start with this",
        default = "")

    useSelectedOnly = BoolProperty(
        name = "Selected Verts Only",
        description = "Only copy to selected vertices",
        default = False)

    ignoreRigidity = BoolProperty(
        name = "Ignore Rigidity Groups",
        description = "Ignore rigidity groups when auto-transfer morphs.\nMorphs may differ from DAZ Studio.",
        default = False)


def shapekeyItems(self, context):
    return [(sname,sname,sname) for sname in context.object.data.shape_keys.key_blocks.keys()[1:]]

class MergeShapekeysOptions:
    shape1 = EnumProperty(
        items = shapekeyItems,
        name = "Shapekey 1",
        description = "Shapekey to keep")

    shape2 = EnumProperty(
        items = shapekeyItems,
        name = "Shapekey 2",
        description = "Shapekey to merge")

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

class CatGroupString:
    catgroup = StringProperty()

class ActionString:
    action = StringProperty()

class TypePrefixCat:
    type = StringProperty(default = "")
    prefix = StringProperty(default = "")
    catgroup = StringProperty(default = "")

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
    filter_glob = StringProperty(default = theDazDefaults + theImagedDefaults + thePoserDefaults, options={'HIDDEN'})


class JsonFile:
    filename_ext = ".json"
    filter_glob = StringProperty(default="*.json", options={'HIDDEN'})


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
    filename_ext = ".dsf;.duf"
    filter_glob = StringProperty(default="*.dsf;*.duf", options={'HIDDEN'})


class DatFile:
    filename_ext = ".dat"
    filter_glob = StringProperty(default="*.dat", options={'HIDDEN'})


class PoserFile:
    filename_ext = ".pz2"
    filter_glob = StringProperty(default=theImagedPoserDefaults, options={'HIDDEN'})


class TextFile:
    filename_ext = ".txt"
    filter_glob = StringProperty(default="*.txt", options={'HIDDEN'})

#-------------------------------------------------------------
#   Property groups
#-------------------------------------------------------------

class DazPropGroup(bpy.types.PropertyGroup):
    index = IntProperty()
    prop = StringProperty()
    factor = FloatProperty()
    default = FloatProperty()

    def __repr__(self):
        return "<PropGroup %d %s %f %f>" % (self.index, self.prop, self.factor, self.default)

class DazIntGroup(bpy.types.PropertyGroup):
    a = IntProperty()

class DazPairGroup(bpy.types.PropertyGroup):
    a = IntProperty()
    b = IntProperty()

class DazStringGroup(bpy.types.PropertyGroup):
    s = StringProperty()

class DazCustomGroup(bpy.types.PropertyGroup):
    name = StringProperty()
    prop = StringProperty()

class DazCategory(bpy.types.PropertyGroup):
    name = StringProperty()
    custom = StringProperty()
    morphs = CollectionProperty(type = DazCustomGroup)

class DazFormula(bpy.types.PropertyGroup):
    key = StringProperty()
    prop = StringProperty()
    value = FloatProperty()

class DazChannelFactor(bpy.types.PropertyGroup):
    key = StringProperty()
    value = FloatProperty()
    color = FloatVectorProperty(subtype='COLOR', size=4, default=(1,1,1,1))
    new = BoolProperty()

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
