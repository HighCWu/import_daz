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

import bpy
from .utils import *
from .error import *

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

#-------------------------------------------------------------
#   Old style evalMorphs, for backward compatibility
#-------------------------------------------------------------

def evalMorphs(pb, idx, key):
    rig = pb.id_data
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.factor*(rig[pg.prop]-pg.default) for pg in props if pg.index == idx])

#-------------------------------------------------------------
#   New style evalMorphs
#-------------------------------------------------------------

def evalMorphs2(pb, idx, key):
    rig = pb.id_data
    pgs = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.eval(rig) for pg in pgs if pg.index == idx])

#-------------------------------------------------------------
#   Separate Loc, Rot, Sca
#-------------------------------------------------------------

def evalMorphsLoc(pb, idx):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazLocProps if pg.index == idx])

def evalMorphsRot(pb, idx):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazRotProps if pg.index == idx])

def evalMorphsSca(pb, idx):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazScaleProps if pg.index == idx])

#-------------------------------------------------------------
#   Separate Loc, Rot, Sca and separate components
#-------------------------------------------------------------

def evalMorphsLoc0(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazLocProps0])

def evalMorphsLoc1(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazLocProps1])

def evalMorphsLoc2(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazLocProps2])

def evalMorphsRot0(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazRotProps0])

def evalMorphsRot1(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazRotProps1])

def evalMorphsRot2(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazRotProps2])

def evalMorphsRot3(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazRotProps3])

def evalMorphsSca0(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazScaProps0])

def evalMorphsSca1(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazScaProps1])

def evalMorphsSca2(pb):
    rig = pb.id_data
    return sum([pg.eval(rig) for pg in pb.DazScaProps2])


#-------------------------------------------------------------
#   Copy prop groups
#-------------------------------------------------------------

def getPropGroups(pb, key, idx):
    #return (pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps)
    return getattr(pb, "Daz%sProps%d" % (key, idx))


def hasPropGroups(pb):
    #return (pb.DazLocProps or pb.DazRotProps or pb.DazScaleProps)
    return (pb.DazLocProps or pb.DazLocProps0 or pb.DazLocProps1 or pb.DazLocProps2 or
            pb.DazRotProps or pb.DazRotProps0 or pb.DazRotProps1 or pb.DazRotProps2 or pb.DazRotProps3 or
            pb.DazScaleProps or pb.DazScaProps0 or pb.DazScaProps1 or pb.DazScaProps2)


def getLocPropGroups(pb):
    return [pb.DazLocProps, pb.DazLocProps0, pb.DazLocProps1, pb.DazLocProps2]

def getRotPropGroups(pb):
    return [pb.DazRotProps, pb.DazRotProps0, pb.DazRotProps1, pb.DazRotProps2, pb.DazRotProps3]

def getScalePropGroups(pb):
    return [pb.DazScaleProps, pb.DazScaProps0, pb.DazScaProps1, pb.DazScaProps2]

def getLocProps(pb):
    return getAllProps(getLocPropGroups(pb))

def getRotProps(pb):
    return getAllProps(getRotPropGroups(pb))

def getScaleProps(pb):
    return getAllProps(getScalePropGroups(pb))

def getAllPropGroups(pb):
    return (getLocPropGroups(pb) + getRotPropGroups(pb) + getScalePropGroups(pb))


def getAllProps(pglist):
    allpgs = []
    for pgs in pglist:
        allpgs += list(pgs)
    return allpgs

#-------------------------------------------------------------
#   Copy prop groups
#-------------------------------------------------------------

def copyPropGroups(rig1, rig2, pb2):
    if pb2.name not in rig1.pose.bones.keys():
        return
    pb1 = rig1.pose.bones[pb2.name]
    pgs1 = getAllPropGroups(pb1)
    if not pgs1:
        return
    pgs2 = getAllPropGroups(pb2)
    pb2.DazDriven = True
    for props1,props2 in zip(pgs1, pgs2):
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
                for key,proplist in [
                    ("Loc", getLocPropGroups(pb)),
                    ("Rot", getRotPropGroups(pb)),
                    ("Sca", getScalePropGroups(pb))]:
                    for n, props in enumerate(proplist):
                        if len(props) == 0:
                            continue
                        print("  %s %d:" % (key, n-1))
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


class DAZ_OT_InspectWorldMatrix(DazOperator, IsObject):
    bl_idname = "daz.inspect_world_matrix"
    bl_label = "Inspect World Matrix"
    bl_description = "List world matrix of active object"

    def run(self, context):
        ob = context.object
        print("World Matrix", ob.name)
        print(ob.matrix_world)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

from bpy.app.handlers import persistent

@persistent
def updateHandler(scn):
    global evalMorphs, evalMorphs2
    global evalMorphsLoc, evalMorphsLoc0, evalMorphsLoc1, evalMorphsLoc2
    global evalMorphsRot, evalMorphsRot0, evalMorphsRot1, evalMorphsRot2, evalMorphsRot3
    global evalMorphsSca, evalMorphsSca0, evalMorphsSca1, evalMorphsSca2
    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.driver_namespace["evalMorphs2"] = evalMorphs2
    bpy.app.driver_namespace["evalMorphsLoc"] = evalMorphsLoc
    bpy.app.driver_namespace["evalMorphsLoc0"] = evalMorphsLoc0
    bpy.app.driver_namespace["evalMorphsLoc1"] = evalMorphsLoc1
    bpy.app.driver_namespace["evalMorphsLoc2"] = evalMorphsLoc2
    bpy.app.driver_namespace["evalMorphsRot"] = evalMorphsRot
    bpy.app.driver_namespace["evalMorphsRot0"] = evalMorphsRot0
    bpy.app.driver_namespace["evalMorphsRot1"] = evalMorphsRot1
    bpy.app.driver_namespace["evalMorphsRot2"] = evalMorphsRot2
    bpy.app.driver_namespace["evalMorphsRot3"] = evalMorphsRot3
    bpy.app.driver_namespace["evalMorphsSca"] = evalMorphsSca
    bpy.app.driver_namespace["evalMorphsSca0"] = evalMorphsSca0
    bpy.app.driver_namespace["evalMorphsSca1"] = evalMorphsSca1
    bpy.app.driver_namespace["evalMorphsSca2"] = evalMorphsSca2


classes = [
    DazMorphGroup,
    DAZ_OT_InspectPropGroups,
    DAZ_OT_InspectPropDependencies,
    DAZ_OT_InspectWorldMatrix,
    ]

def initialize():
    from bpy.props import CollectionProperty
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.PoseBone.DazLocProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazLocProps0 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazLocProps1 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazLocProps2 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps0 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps1 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps2 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps3 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaleProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaProps0 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaProps1 = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaProps2 = CollectionProperty(type = DazMorphGroup)

    updateHandler(None)
    bpy.app.handlers.load_post.append(updateHandler)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
