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
from .error import *
from .utils import B

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(DazOperator, B.DazImageFile, B.SingleFile, B.DazOptions):
    """Import a DAZ DUF/DSF File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ File"
    bl_description = "Import a native DAZ file (*.duf, *.dsf, *.dse)"
    bl_options = {'PRESET', 'UNDO'}

    def run(self, context):
        from .main import getMainAsset
        self.useSimulation = False
        getMainAsset(self.filepath, context, self)


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def draw(self, context):
        layout = self.layout
        scn = context.scene
        layout.prop(self, "unitScale")
        layout.separator()

        box = layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)

        layout.separator()
        layout.prop(self, "skinColor")
        layout.prop(self, "clothesColor")
        layout.prop(self, "brightenEyes")
        layout.separator()
        layout.prop(self, "useAutoMaterials")
        layout.prop(self, "handleOpaque")
        layout.prop(self, "handleRefractive")
        layout.prop(self, "handleVolumetric")
        layout.prop(self, "useEnvironment")
        #layout.prop(self, "useSimulation")

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

class DazMorphGroup(bpy.types.PropertyGroup, B.DazMorphGroupProps):
    def __repr__(self):
        return "<MorphGroup %d %s %f %f>" % (self.index, self.prop, self.factor, self.default)

    def eval(self, rig):
        if self.simple:
            return self.factor*(rig[self.name]-self.default) 
        else:
            value = rig[self.name]-self.default
            return (self.factor*(value > 0) + self.factor2*(value < 0))*value

    def display(self):
        return ("MG %d %-25s %10.6f %10.6f %10.2f" % (self.index, self.name, self.factor, self.factor2, self.default))

    def init(self, prop, idx, default, factor, factor2):
        self.name = prop
        self.index = idx
        self.factor = factor        
        self.default = default
        if factor2 is None:
            self.factor2 = 0
            self.simple = True
        else:
            self.factor2 = factor2
            self.simple = False

    def __lt__(self,other):
        if self.name == other.name:
            return (self.index < other.index)
        else:
            return (self.name < other.name)


# Old style evalMorphs, for backward compatibility
def evalMorphs(pb, idx, key):
    rig = pb.constraints[0].target
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.factor*(rig[pg.prop]-pg.default) for pg in props if pg.index == idx])


# New style evalMorphs
def evalMorphs2(pb, idx, key):
    rig = pb.constraints[0].target
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.eval(rig) for pg in props if pg.index == idx])


def hasSelfRef(pb):
    return (pb.constraints and
            pb.constraints[0].name == "Do Not Touch")


def addSelfRef(rig, pb):
    if pb.constraints:
        cns = pb.constraints[0]
        if cns.name == "Do Not Touch":
            return
        else:
            raise DazError("Inconsistent self reference constraint\n for bone '%s'" % pb.name)
    cns = pb.constraints.new('COPY_LOCATION')
    cns.name = "Do Not Touch"
    cns.target = rig
    cns.mute = True

        
def copyPropGroups(rig1, rig2, pb2):
    if pb2.name not in rig1.pose.bones.keys():
        return
    pb1 = rig1.pose.bones[pb2.name]
    if not (pb1.DazLocProps or pb1.DazRotProps or pb1.DazScaleProps):
        return
    addSelfRef(rig2, pb2)
    for props1,props2 in [
        (pb1.DazLocProps, pb2.DazLocProps),
        (pb1.DazRotProps, pb2.DazRotProps),
        (pb1.DazScaleProps, pb2.DazScaleProps)
        ]:
        for pg1 in props1:
            pg2 = props2.add()
            pg2.name = pg1.name
            pg2.index = pg1.index
            pg2.prop = pg1.prop
            pg2.factor = pg1.factor
            pg2.default = pg1.default


class DAZ_OT_InspectPropGroups(DazOperator, IsArmature):
    bl_idname = "daz.inspect_prop_groups"
    bl_label = "Inspect Prop Groups"
    bl_description = "Show the property groups for the selected posebones."

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            if pb.bone.select:
                print("\n", pb.name)
                for key,props in [("Loc",pb.DazLocProps),
                                  ("Rot",pb.DazRotProps),
                                  ("Sca",pb.DazScaleProps)
                                  ]:
                    print("  ", key)
                    props = list(props)
                    props.sort()
                    for pg in props:
                        print("    ", pg.display())

#-------------------------------------------------------------
#   Dependencies
#   For debugging
#-------------------------------------------------------------

def clearDependecies():
    global theDependecies
    theDependecies = {}
    
clearDependecies()
    
    
def addDependency(key, prop, factor):
    global theDependecies
    if key not in theDependecies.keys():
        deps = theDependecies[key] = []
    else:
        deps = theDependecies[key]
    deps.append((prop,factor))
        

class DAZ_OT_InspectPropDependencies(DazOperator, IsArmature):
    bl_idname = "daz.inspect_prop_dependencies"
    bl_label = "Inspect Prop Dependencies"
    bl_description = "List properties depending on other properties"

    def run(self, context):
        global theDependecies
        print("--- Property dependencies from latest load ---")
        deps = list(theDependecies.items())
        deps.sort()
        for key,dep in deps:
            if len(dep) > 0:
                prop,val = dep[0]
                print("  %-24s: %6.4f %-24s" % (key, val, prop))
            for prop,val in dep[1:]:
                print("  %-24s: %6.4f %-24s" % ("", val, prop))

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

from bpy.app.handlers import persistent

@persistent
def updateHandler(scn):
    global evalMorphs, evalMorphs2
    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.driver_namespace["evalMorphs2"] = evalMorphs2


classes = [
    ImportDAZ,
    DazMorphGroup,
    B.DazStringGroup,
    DAZ_OT_InspectPropGroups,
    DAZ_OT_InspectPropDependencies,
]

def initialize():

    bpy.types.Scene.DazChooseColors = EnumProperty(
        items = [('WHITE', "White", "Default diffuse color"),
                 ('RANDOM', "Random", "Random colors for each object"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Color Choice",
        description = "Method to use object colors",
        default = 'GUESS')

    bpy.types.Scene.DazUseHidden = BoolProperty(
        name = "Hidden Features",
        description = "Use hidden and undocumented experimental features",
        default = False)

    bpy.types.Scene.DazUseLockRot = BoolProperty(
        name = "Rotation Locks",
        description = "Use rotation locks",
        default = True)

    bpy.types.Scene.DazUseLockLoc = BoolProperty(
        name = "Location Locks",
        description = "Use location locks",
        default = True)

    bpy.types.Scene.DazUseLimitRot = BoolProperty(
        name = "Limit Rotation",
        description = "Create Limit Rotation constraints",
        default = False)

    bpy.types.Scene.DazUseLimitLoc = BoolProperty(
        name = "Limit Location",
        description = "Create Limit Location constraints",
        default = False)

    bpy.types.Scene.DazZup = BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention",
        default = True)

    bpy.types.Scene.DazOrientation = BoolProperty(
        name = "DAZ Orientation",
        description = "Treat bones as nodes with same orientation as in Daz Studio",
        default = False)

    bpy.types.Scene.DazBestOrientation = BoolProperty(
        name = "DAZ Best Orientation",
        description = "Treat bones as nodes with same orientation as in Daz Studio,\nbut flip axes to make Y point along bone as well as possible.",
        default = False)

    from sys import platform
    bpy.types.Scene.DazCaseSensitivePaths = BoolProperty(
        name = "Case-Sensitive Paths",
        description = "Convert URLs to lowercase. Works best on Windows.",
        default = (platform != 'win32'))

    bpy.types.Scene.DazRename = BoolProperty(
        name = "Rename",
        description = "Rename all imported objects based on file name",
        default = False)

    bpy.types.Scene.DazUseGroup = BoolProperty(
        name = "Create Group",
        description = "Add all objects to the same group",
        default = True)

    bpy.types.Scene.DazAddFaceDrivers = BoolProperty(
        name = "Add Face Drivers",
        description = "Add drivers to facial morphs. Only for Genesis 1 and 2.",
        default = True)

    bpy.types.Scene.DazMakeDrivers = EnumProperty(
        items = [('NONE', "None", "Never make drivers"),
                 ('PROPS', "Props", "Make drivers for props"),
                 ('PEOPLE', "People", "Make drivers for people"),
                 ('ALL', "All", "Make drivers for all figures"),
                 ],
        name = "Make Drivers",
        description = "Make drivers for formulas",
        default = 'PROPS')

    bpy.types.Scene.DazMergeShells = BoolProperty(
        name = "Merge Shells",
        description = "Merge shell materials with object material",
        default = True)

    bpy.types.Scene.DazMaxBump = FloatProperty(
        name = "Max Bump Strength",
        description = "Max bump strength",
        default = 2.0,
        min = 0.1, max = 10)

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name = "Displacement",
        description = "Use displacement maps. Affects internal renderer only",
        default = True)

    bpy.types.Object.DazUseDisplacement = BoolProperty(default=True)
    bpy.types.Material.DazUseDisplacement = BoolProperty(default=False)

    bpy.types.Scene.DazUseTranslucency = BoolProperty(
        name = "Translucency",
        description = "Use translucency.",
        default = True)

    bpy.types.Scene.DazUseSSS = BoolProperty(
        name = "SSS",
        description = "Use subsurface scattering.",
        default = True)

    bpy.types.Object.DazUseSSS = BoolProperty(default=True)
    bpy.types.Material.DazUseSSS = BoolProperty(default=False)

    bpy.types.Scene.DazUseNormal = BoolProperty(
        name = "Normal",
        description = "Use normal maps.",
        default = True)

    bpy.types.Object.DazUseNormal = BoolProperty(default=True)
    bpy.types.Material.DazUseNormal = BoolProperty(default=False)

    bpy.types.Scene.DazUseBump = BoolProperty(
        name = "Bump",
        description = "Use bump maps.",
        default = True)

    bpy.types.Object.DazUseBump = BoolProperty(default=True)
    bpy.types.Material.DazUseBump = BoolProperty(default=False)

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name = "Emission",
        description = "Use emission.",
        default = True)

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name = "Reflection",
        description = "Use reflection maps. Affects internal renderer only",
        default = True)

    bpy.types.Scene.DazDiffuseRoughness = FloatProperty(
        name = "Diffuse Roughness",
        description = "Default diffuse roughness",
        default = 0.3,
        min = 0, max = 1.0)

    bpy.types.Scene.DazSpecularRoughness = FloatProperty(
        name = "Specular Roughness",
        description = "Default specular roughness",
        default = 0.3,
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
        description = "Diffuse shader (Blender Internal)",
        default = 'OREN_NAYAR')

    bpy.types.Scene.DazSpecularShader = EnumProperty(
        items = [
            ('WARDISO', "WardIso", ""),
            ('TOON', "Toon", ""),
            ('BLINN', "Blinn", ""),
            ('PHONG', "Phong", ""),
            ('COOKTORR', "CookTorr", "")
        ],
        name = "Specular Shader",
        description = "Specular shader (Blender Internal)",
        default = 'BLINN')

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')
    bpy.types.Material.DazThinGlass = BoolProperty(default=False)

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.PoseBone.DazLocProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaleProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.Object.DazHiddenProps = CollectionProperty(type = B.DazStringGroup)

    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.driver_namespace["evalMorphs2"] = evalMorphs2
    bpy.app.handlers.load_post.append(updateHandler)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
