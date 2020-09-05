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


import bpy
import math
from mathutils import *
from bpy.props import IntProperty
from .asset import *
from .utils import *
from .error import *
from .node import Node, Instance

#-------------------------------------------------------------
#   FigureInstance
#-------------------------------------------------------------

class FigureInstance(Instance):

    def __init__(self, fileref, node, struct):
        for geo in node.geometries:
            geo.figureInst = self
        Instance.__init__(self, fileref, node, struct)
        self.figure = self
        self.planes = {}
        self.bones = {}
        self.hiddenBones = {}


    def __repr__(self):
        return "<FigureInstance %s %d P: %s R: %s>" % (self.node.name, self.index, self.node.parent, self.rna)


    def buildExtra(self, context):
        pass


    def finalize(self, context):
        from .finger import getFingeredCharacter
        Instance.finalize(self, context)
        rig,mesh,char = getFingeredCharacter(self.rna)
        if rig and mesh:
            if mesh.name == self.name:
                mesh.name += " Mesh"
            rig.DazMesh = mesh.DazMesh = char
            activateObject(context, rig)
            self.selectChildren(rig)
        elif mesh:
            mesh.DazMesh = char
        self.rna.name = self.name
        for geonode in self.geometries:
            Instance.finalize(self, context, geonode)
        if self.hiddenBones:
            for geonode in self.geometries:
                geonode.hideVertexGroups(self.hiddenBones.keys())


    def selectChildren(self, rig):            
        for child in rig.children:
            if child.type == 'ARMATURE':
                setSelected(child, True)
                self.selectChildren(child)


    def pose(self, context):
        from .bone import BoneInstance
        Instance.pose(self, context)
        if bpy.app.version >= (2.80,0):
            print("SKIP pose")
            return
        rig = self.rna
        activateObject(context, rig)
        tchildren = {}
        bpy.ops.object.mode_set(mode='POSE')
        missing = []
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(self, False, tchildren, missing)
        if missing and GS.verbosity > 2:
            print("Missing bones when posing %s" % self.name)
            print("  %s" % [inst.node.name for inst in missing])
        rig.DazRotLocks = GS.useLockRot
        rig.DazLocLocks = GS.useLockLoc
        rig.DazRotLimits = GS.useLimitRot
        rig.DazLocLimits = GS.useLimitLoc
        self.fixDependencyLoops(rig)
        bpy.ops.object.mode_set(mode='OBJECT')


    def fixDependencyLoops(self, rig):
        from .driver import getBoneDrivers, getDrivingBone, clearBendDrivers
        needfix = {}
        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
            for fcu in fcus:
                bname = getDrivingBone(fcu, rig)
                if bname:
                    for child in pb.children:
                        if child.name == bname:
                            needfix[pb.name] = (child.name, fcus)

        if needfix:
            if GS.verbosity > 1:
                print("Fix dependency loops:", list(needfix.keys()))
            bpy.ops.object.mode_set(mode = 'EDIT')
            for bname in needfix.keys():
                cname = needfix[bname][0]
                eb = rig.data.edit_bones[bname]
                cb = rig.data.edit_bones[cname]
                eb.use_connect = False
                cb.use_connect = False
                cb.parent = eb.parent
            bpy.ops.object.mode_set(mode = 'POSE')
            for bname in needfix.keys():
                fcus = needfix[bname][1]
                clearBendDrivers(fcus)


    def setupPlanes(self):
        from .bone import BoneInstance
        if self.node.rigtype not in PlanesUsed.keys():
            return
        for pname in PlanesUsed[self.node.rigtype]:
            bone1,bone2,bone3 = PlanePoints[pname]
            try:
                pt1 = d2b(self.bones[bone1].attributes["center_point"])
                pt2 = d2b(self.bones[bone2].attributes["center_point"])
                pt3 = d2b(self.bones[bone3].attributes["end_point"])
            except KeyError:
                continue
            e1 = pt2-pt1
            e2 = pt3-pt1
            n = e1.cross(e2)
            n.normalize()
            self.planes[pname] = n


PlanesUsed = {
    "genesis1" : [
        "lArm", "lHand", "lThumb", "lIndex", "lMid", "lRing", "lPinky",
        "rArm", "rHand", "rThumb", "rIndex", "rMid", "rRing", "rPinky",
    ],
    "genesis2" : [
        "lArm", "lHand", "lThumb", "lIndex", "lMid", "lRing", "lPinky",
        "rArm", "rHand", "rThumb", "rIndex", "rMid", "rRing", "rPinky",
    ],
    "genesis3" : [
        "lArm", "lThumb", "lHand",
        "rArm", "rThumb", "rHand",
    ],
    "genesis8" : [
        "lArm", "lLeg", "lThumb", "lHand",
        "rArm", "rLeg", "rThumb", "rHand",
    ],
}

PlanePoints = {
    "lArm" : ["lShldr", "lForeArm", "lForeArm"],
    "lLeg" : ["lThigh", "lShin", "lShin"],
    "lThumb" : ["lThumb1", "lThumb2", "lThumb2"],
    "lIndex" : ["lIndex1", "lIndex2", "lIndex3"],
    "lMid" : ["lMid1", "lMid2", "lMid3"],
    "lRing" : ["lRing1", "lRing2", "lRing3"],
    "lPinky" : ["lPinky1", "lPinky2", "lPinky3"],
    "lHand" : ["lIndex3", "lMid1", "lPinky2"],

    "rArm" : ["rShldr", "rForeArm", "rForeArm"],
    "rLeg" : ["rThigh", "rShin", "rShin"],
    "rThumb" : ["rThumb1", "rThumb2", "rThumb2"],
    "rIndex" : ["rIndex1", "rIndex2", "rIndex3"],
    "rMid" : ["rMid1", "rMid2", "rMid3"],
    "rRing" : ["rRing1", "rRing2", "rRing3"],
    "rPinky" : ["rPinky1", "rPinky2", "rPinky3"],
    "rHand" : ["rMid1", "rIndex3", "rPinky2"],
}

#-------------------------------------------------------------
#   Figure
#-------------------------------------------------------------

class Figure(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.restPose = False
        self.bones = {}
        self.presentation = None
        self.figure = self
        self.rigtype = "Unknown"


    def __repr__(self):
        return ("<Figure %s %d %s>" % (self.id, self.count, self.rna))


    def makeInstance(self, fileref, struct):
        return FigureInstance(fileref, self, struct)


    def parse(self, struct):
        Node.parse(self, struct)
        if "presentation" in struct.keys():
            self.presentation = struct["presentation"]


    def build(self, context, inst):
        from .bone import BoneInstance
        from .finger import getFingeredCharacter
        scn = context.scene

        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.listBones()
        self.rigtype = getRigType1(inst.bones.keys())

        center = d2b(inst.attributes["center_point"])
        cscale = inst.getCharacterScale()
        Asset.build(self, context, inst)
        for geo in inst.geometries:
            geo.buildObject(context, inst, center)
            geo.rna.location = Vector((0,0,0))
        amt = self.data = bpy.data.armatures.new(inst.name)
        self.buildObject(context, inst, center)
        rig = self.rna
        setattr(amt, DrawType, 'STICK')
        setattr(rig, ShowXRay, True)
        rig.DazOrientMethod = GS.orientMethod
        for geo in inst.geometries:
            geo.parent = geo.figure = self
            geo.rna.parent = rig

        cscale = inst.getCharacterScale()
        center = inst.attributes["center_point"]
        inst.setupPlanes()
        activateObject(context, rig)

        bpy.ops.object.mode_set(mode='EDIT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(self, rig, None, cscale, center, False)
        rig.DazCharacterScale = cscale
        rig.DazRig = self.rigtype

        bpy.ops.object.mode_set(mode='OBJECT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, cscale, center)

        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, False)


def getModifierPath(moddir, folder, tfile):
    try:
        files = list(os.listdir(moddir+folder))
    except FileNotFoundError:
        files = []
    for file in files:
        file = tolower(file)
        if file == tfile:
            return folder+"/"+tfile
        elif os.path.isdir(moddir+folder+"/"+file):
            path = getModifierPath(moddir, folder+"/"+file, tfile)
            if path:
                return path
    return None


def getRigType(data):
    if isinstance(data, bpy.types.Object):
        return getRigType(data.pose.bones.keys())
    else:
        return getRigType1(data)


def getRigType1(bones):
    if match(["abdomenLower", "lShldrBend", "rShldrBend"], bones):
        if "lHeel" in bones:
            return "genesis3"
        else:
            return "genesis8"
    elif match(["abdomenLower", "lShldrBend", "lJawClench"], bones):
        return "genesis8"
    elif match(["abdomen", "lShldr", "rShldr"], bones):
        if "lSmallToe1" in bones:
            return "genesis2"
        else:
            return "genesis1"
    elif "ball.marker.L" in bones:
        return "mhx"
    else:
        return ""
        print("No rigtype:")
        bones.sort()
        print(bones)
        return ""


class LegacyFigure(Figure):

    def __init__(self, fileref):
        Figure.__init__(self, fileref)


    def __repr__(self):
        return ("<LegacyFigure %s>" % (self.id))


#-------------------------------------------------------------
#   Print bone matrix
#-------------------------------------------------------------

class DAZ_OT_PrintMatrix(DazOperator, IsArmature):
    bl_idname = "daz.print_matrix"
    bl_label = "Print Bone Matrix"
    bl_options = {'UNDO'}

    def run(self, context):
        pb = context.active_pose_bone
        print(pb.name)
        mat = pb.bone.matrix_local
        euler = mat.to_3x3().to_euler('XYZ')
        print(euler)
        print(Vector(euler)/D)
        print(mat)


class DAZ_OT_RotateBones(DazPropsOperator, B.XYZ, IsArmature):
    bl_idname = "daz.rotate_bones"
    bl_label = "Rotate Bones"
    bl_description = "Rotate selected bones the same angle"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "X")
        self.layout.prop(self, "Y")
        self.layout.prop(self, "Z")

    def run(self, context):
        rig = context.object
        rot = Vector((self.X, self.Y, self.Z))*D
        quat = Euler(rot).to_quaternion()
        for pb in rig.pose.bones:
            if pb.bone.select:
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_quaternion = quat
                else:
                    pb.rotation_euler = rot

#-------------------------------------------------------------
#   Add extra face bones
#-------------------------------------------------------------

def copyBoneInfo(srcbone, trgbone):
    trgbone.DazOrient = Vector(srcbone.DazOrient)
    trgbone.DazHead = Vector(srcbone.DazHead)
    trgbone.DazTail = Vector(srcbone.DazTail)
    trgbone.DazAngle = srcbone.DazAngle
    trgbone.DazNormal = Vector(srcbone.DazNormal)


class ExtraBones(B.BoneLayers):
    def draw(self, context):
        self.layout.prop(self, "poseLayer")
        self.layout.prop(self, "drivenLayer")


    def run(self, context):
        rig = context.object
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        try:
            self.addExtraBones(rig)
            success = True
        finally:
            rig.data.layers = oldvis
            if success:
                rig.data.layers[self.poseLayer-1] = True
                rig.data.layers[self.drivenLayer-1] = False
            

    def addExtraBones(self, rig):
        from .driver import getBoneDrivers, removeDriverBoneSuffix, storeBoneDrivers, restoreBoneDrivers
        if getattr(rig.data, self.attr):
            msg = "Rig %s already has extra %s bones" % (rig.name, self.type)
            print(msg)
            #raise DazError(msg)

        if rig.DazRig[0:6] == "rigify":
            raise DazError("Cannot add extra bones to Rigify rig")
        elif rig.DazRig == "mhx":
            raise DazError("Cannot add extra bones to MHX rig")
        poseLayers = (self.poseLayer-1)*[False] + [True] + (32-self.poseLayer)*[False]
        drivenLayers = (self.drivenLayer-1)*[False] + [True] + (32-self.drivenLayer)*[False]

        bones = self.getBoneNames(rig)
        drivers = storeBoneDrivers(rig, bones)
        bpy.ops.object.mode_set(mode='EDIT')
        for bname in bones:
            eb = rig.data.edit_bones[bname]
            eb.name = bname+"Drv"
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.mode_set(mode='EDIT')
        for bname in bones:
            eb = rig.data.edit_bones.new(bname)
            par = rig.data.edit_bones[bname+"Drv"]
            eb.head = par.head
            eb.tail = par.tail
            eb.roll = par.roll
            eb.parent = par
            eb.layers = poseLayers
            par.layers = drivenLayers
            eb.use_deform = True
            par.use_deform = False
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.mode_set(mode='EDIT')
        for bname in bones:
            if bname+"Drv" in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bname+"Drv"]
                for cb in eb.children:
                    if cb.name != bname:
                        cb.parent = rig.data.edit_bones[bname]

        bpy.ops.object.mode_set(mode='POSE')
        for bname in bones:
            if (bname in rig.pose.bones.keys() and
                bname+"Drv" in rig.pose.bones.keys()):
                pb = rig.pose.bones[bname]
                par = rig.pose.bones[bname+"Drv"]
                pb.rotation_mode = par.rotation_mode
                pb.lock_location = par.lock_location
                pb.lock_rotation = par.lock_rotation
                pb.lock_scale = par.lock_scale
                pb.DazRotLocks = par.DazRotLocks
                pb.DazLocLocks = par.DazLocLocks
                copyBoneInfo(par.bone, pb.bone)

        restoreBoneDrivers(rig, drivers, "Drv")

        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
            if fcus:
                for fcu in fcus:
                    removeDriverBoneSuffix(fcu, "Drv")

        setattr(rig.data, self.attr, True)
        updateDrivers(rig)

        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in rig.children:
            if ob.type == 'MESH':
                for vgrp in ob.vertex_groups:
                    if (vgrp.name[-3:] == "Drv" and
                        vgrp.name[:-3] in bones):
                        vgrp.name = vgrp.name[:-3]


class DAZ_OT_SetAddExtraFaceBones(DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.add_extra_face_bones"
    bl_label = "Add Extra Face Bones"
    bl_description = "Add an extra layer of face bones, which can be both driven and posed"
    bl_options = {'UNDO'}

    type =  "face"
    attr = "DazExtraFaceBones"

    def getBoneNames(self, rig):
        from .driver import isBoneDriven
        inface = [
            "lEye", "rEye",
            "lowerJaw", "upperTeeth", "lowerTeeth", "lowerFaceRig",
            "tongue01", "tongue02", "tongue03", "tongue04",
            "tongue05", "tongue06", "tongueBase", "tongueTip",
        ]
        keys = rig.pose.bones.keys()
        facebones = [bname for bname in inface
            if bname in keys and bname+"Drv" not in keys]
        if "upperFaceRig" in keys:
            facebones += [pb.name for pb in rig.pose.bones
                if pb.name+"Drv" not in keys and
                    pb.name[-3:] != "Drv" and
                    pb.parent and
                    pb.parent.name == "upperFaceRig" and
                    not isBoneDriven(rig, pb)]
        if "lowerFaceRig" in keys:
            facebones += [pb.name for pb in rig.pose.bones
                if pb.name+"Drv" not in keys and
                    pb.name[-3:] != "Drv" and
                    pb.parent and
                    pb.parent.name == "lowerFaceRig"]
        return facebones


class DAZ_OT_MakeAllBonesPosable(DazPropsOperator, ExtraBones, IsArmature):
    bl_idname = "daz.make_all_bones_posable"
    bl_label = "Make All Bones Posable"
    bl_description = "Add an extra layer of driven bones, to make them posable"
    bl_options = {'UNDO'}

    type =  "driven"
    attr = "DazExtraDrivenBones"

    def getBoneNames(self, rig):
        from .driver import isBoneDriven
        exclude = ["lMetatarsals", "rMetatarsals"]
        return [pb.name for pb in rig.pose.bones
                if isBoneDriven(rig, pb) and
                pb.name[-3:] != "Drv" and
                pb.name+"Drv" not in rig.pose.bones.keys() and
                pb.name not in exclude]
    
#-------------------------------------------------------------
#   Toggle locks and constraints
#-------------------------------------------------------------

def getRnaName(string):
    if len(string) > 4 and string[-4] == ".":
        return string[:-4]
    else:
        return string

#----------------------------------------------------------
#   Toggle locks
#----------------------------------------------------------

class ToggleLocks:
    def run(self, context):
        rig = context.object
        if getattr(rig, self.attr):
            for pb in rig.pose.bones:
                setattr(pb, self.attr, getattr(pb, self.lock))
                setattr(pb, self.lock, (False,False,False))
            setattr(rig, self.attr, False)
        else:
            for pb in rig.pose.bones:
                setattr(pb, self.lock, getattr(pb, self.attr))
            setattr(rig, self.attr, True)


class DAZ_OT_ToggleRotLocks(DazOperator, ToggleLocks, IsArmature):
    bl_idname = "daz.toggle_rot_locks"
    bl_label = "Toggle Rotation Locks"
    bl_description = "Toggle rotation locks"
    bl_options = {'UNDO'}

    attr = "DazRotLocks"
    lock = "lock_rotation"


class DAZ_OT_ToggleLocLocks(DazOperator, ToggleLocks, IsArmature):
    bl_idname = "daz.toggle_loc_locks"
    bl_label = "Toggle Location Locks"
    bl_description = "Toggle location locks"
    bl_options = {'UNDO'}

    attr = "DazLocLocks"
    lock = "lock_location"

#----------------------------------------------------------
#   Toggle Limits
#----------------------------------------------------------

class ToggleLimits:
    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == self.type:
                    cns.mute = getattr(rig, self.attr)
        setattr(rig, self.attr, not getattr(rig, self.attr))


class DAZ_OT_ToggleRotLimits(DazOperator, ToggleLimits, IsArmature):
    bl_idname = "daz.toggle_rot_limits"
    bl_label = "Toggle Limits"
    bl_description = "Toggle rotation limits"
    bl_options = {'UNDO'}

    type = "LIMIT_ROTATION"
    attr = "DazRotLimits"
    
    
class DAZ_OT_ToggleLocLimits(DazOperator, ToggleLimits, IsArmature):
    bl_idname = "daz.toggle_loc_limits"
    bl_label = "Toggle Location Limits"
    bl_description = "Toggle location limits"
    bl_options = {'UNDO'}

    type = "LIMIT_LOCATION"
    attr = "DazLocLimits"
    
#-------------------------------------------------------------
#   Simple IK
#-------------------------------------------------------------

from bpy.props import BoolProperty, FloatProperty, StringProperty

class SimpleIK:
    prefix = None
    type = None

    G38Arm = ["ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Hand"]
    G38Leg = ["ThighBend", "ThighTwist", "Shin", "Foot"]
    G38Spine = ["hip", "abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["hip", "abdomen", "abdomen2", "chest"]
    
    Circle = {
        "name" : "Circle",
        "verts" : [[0, 0.59721, 0], [-0.11651, 0.585734, 0], [-0.228542, 0.55175, 0], [-0.331792, 0.496562, 0], [-0.422291, 0.422291, 0], [-0.496562, 0.331792, 0], [-0.55175, 0.228542, 0], [-0.585735, 0.11651, 0], [-0.59721, -1.23623e-07, 0], [-0.585735, -0.11651, 0], [-0.55175, -0.228542, 0], [-0.496562, -0.331792, 0], [-0.422291, -0.422291, 0], [-0.331792, -0.496562, 0], [-0.228542, -0.55175, 0], [-0.11651, -0.585735, 0], [2.5826e-07, -0.59721, 0], [0.11651, -0.585735, 0], [0.228543, -0.55175, 0], [0.331792, -0.496562, 0], [0.422292, -0.422291, 0], [0.496562, -0.331792, 0], [0.55175, -0.228542, 0], [0.585735, -0.11651, 0], [0.59721, 4.07954e-07, 0], [0.585735, 0.11651, 0], [0.55175, 0.228543, 0], [0.496562, 0.331793, 0], [0.422291, 0.422292, 0], [0.331791, 0.496562, 0], [0.228542, 0.55175, 0], [0.116509, 0.585735, 0]],
        "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
    }    
    
    def storeProps(self, rig):
        self.ikprops = (rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R)
        

    def setProps(self, rig, onoff):        
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = onoff
        updateScene(bpy.context, updateDepsGraph=True)


    def restoreProps(self, rig):
        rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R = self.ikprops
        updateScene(bpy.context, updateDepsGraph=True)


    def getIKProp(self, prefix, type):   
        return "Daz" + type + "IK_" + prefix.upper()

    
    def getGenesisType(self, rig):
        if (self.hasAllBones(rig, self.G38Arm+self.G38Leg, "l") and
            self.hasAllBones(rig, self.G38Arm+self.G38Leg, "r") and
            self.hasAllBones(rig, self.G38Spine, "")):
            return "G38"
        if (self.hasAllBones(rig, self.G12Arm+self.G12Leg, "l") and
            self.hasAllBones(rig, self.G12Arm+self.G12Leg, "r") and
            self.hasAllBones(rig, self.G12Spine, "")):
            return "G12"
        return None            
    

    def hasAllBones(self, rig, bnames, prefix):
        bnames = [prefix+bname for bname in bnames]
        for bname in bnames:
            if bname not in rig.data.bones.keys():
                print("Miss", bname)
                return False
        return True

        
    def getLimbBoneNames(self, rig, prefix, type):        
        genesis = self.getGenesisType(rig)
        if not genesis:
            return None
        table = getattr(self, genesis+type)
        return [prefix+bname for bname in table]
        

    def insertIKKeys(self, rig, frame):
        for bname in ["lHandIK", "rHandIK", "lFootIK", "rFootIK"]:
            pb = rig.pose.bones[bname]
            pb.keyframe_insert("location", frame=frame, group=bname)
            pb.keyframe_insert("rotation_euler", frame=frame, group=bname)
        

class DAZ_OT_AddSimpleIK(DazOperator, SimpleIK, IsArmature):
    bl_idname = "daz.add_simple_ik"
    bl_label = "Add Simple IK"
    bl_description = "Add Simple IK constraints to the active rig"
    bl_options = {'UNDO'}
    
    def run(self, context):
        from .mhx import makeBone, getBoneCopy, ikConstraint, copyRotation
        rig = context.object        
        if rig.DazSimpleIK:
            raise DazError("The rig %s already has simple IK" % rig.name)

        genesis = self.getGenesisType(rig)
        if not genesis:
            raise DazError("Cannot create simple IK for the rig %s" % rig.name)        

        rig.DazSimpleIK = True
        rig.DazArmIK_L = rig.DazArmIK_R = True
        rig.DazLegIK_L = rig.DazLegIK_R = True
        
        circle = self.makeGizmo(self.Circle)    
    
        bpy.ops.object.mode_set(mode='EDIT')
        ebones = rig.data.edit_bones
        for prefix in ["l", "r"]:
            hand = ebones[prefix+"Hand"]
            handIK = makeBone(prefix+"HandIK", rig, hand.head, hand.tail, hand.roll, 0, None)
            foot = ebones[prefix+"Foot"]
            handIK = makeBone(prefix+"FootIK", rig, foot.head, foot.tail, foot.roll, 0, None)
    
        bpy.ops.object.mode_set(mode='POSE')    
        rpbs = rig.pose.bones
        hip = rpbs["hip"]
        hip.custom_shape = circle
        
        for prefix in ["l", "r"]:
            suffix = prefix.upper()
            armProp = "DazArmIK_" + suffix
            legProp = "DazLegIK_" + suffix
            
            hand = rpbs[prefix+"Hand"]
            foot = rpbs[prefix+"Foot"]
            handIK = getBoneCopy(prefix+"HandIK", hand, rpbs)
            footIK = getBoneCopy(prefix+"FootIK", foot, rpbs)
            copyRotation(hand, handIK, (True,True,True), rig, space='WORLD', prop=armProp)
            copyRotation(foot, footIK, (True,True,True), rig, space='WORLD', prop=legProp)
            handIK.custom_shape = circle
            footIK.custom_shape = circle
            #hand.custom_shape = circle
            #foot.custom_shape = circle
            
            if genesis == "G38":
                footIK.custom_shape_scale = 2.0
                shldrBend = rpbs[prefix+"ShldrBend"]
                self.limitBone(shldrBend, False)
                shldrTwist = rpbs[prefix+"ShldrTwist"]
                self.limitBone(shldrTwist, True)
                forearmBend = rpbs[prefix+"ForearmBend"]
                self.limitBone(forearmBend, False)
                forearmTwist = rpbs[prefix+"ForearmTwist"]
                self.limitBone(forearmTwist, True)
                ikConstraint(forearmTwist, handIK, None, 0, 4, rig, prop=armProp)
                
                thighBend = rpbs[prefix+"ThighBend"]
                self.limitBone(thighBend, False, stiffness=(0,0,0.326))
                thighTwist = rpbs[prefix+"ThighTwist"]
                self.limitBone(thighTwist, True, stiffness=(0,0.160,0))
                shin = rpbs[prefix+"Shin"]
                self.limitBone(shin, False, stiffness=(0.068,0,0.517))
                ikConstraint(shin, footIK, None, 0, 3, rig, prop=legProp)
    
            elif genesis == "G12":
                handIK.custom_shape_scale = 2.0
                shldr = rpbs[prefix+"Shldr"]
                self.limitBone(shldr, False)
                forearm = rpbs[prefix+"ForeArm"]
                self.limitBone(forearm, False)
                ikConstraint(forearm, handIK, None, 0, 2, rig, prop=armProp)
                
                thigh = rpbs[prefix+"Thigh"]
                self.limitBone(thigh, False)
                shin = rpbs[prefix+"Shin"]
                self.limitBone(shin, False)
                ikConstraint(shin, footIK, None, 0, 2, rig, prop=legProp)
                
    
    def limitBone(self, pb, twist, stiffness=(0,0,0)):
        pb.lock_ik_x = pb.lock_rotation[0]
        pb.lock_ik_y = pb.lock_rotation[1]
        pb.lock_ik_z = pb.lock_rotation[2]
        
        pb.ik_stiffness_x = stiffness[0]
        pb.ik_stiffness_y = stiffness[1]
        pb.ik_stiffness_z = stiffness[2]
        
        for cns in pb.constraints:
            if cns.type == 'LIMIT_ROTATION':
                pb.use_ik_limit_x = cns.use_limit_x
                pb.use_ik_limit_y = cns.use_limit_y
                pb.use_ik_limit_z = cns.use_limit_z
                pb.ik_min_x = cns.min_x
                pb.ik_max_x = cns.max_x
                pb.ik_min_y = cns.min_y
                pb.ik_max_y = cns.max_y
                pb.ik_min_z = cns.min_z
                pb.ik_max_z = cns.max_z
                cns.influence = 0
                break
    
        if twist:
            pb.use_ik_limit_x = True
            pb.use_ik_limit_z = True
            pb.ik_min_x = 0
            pb.ik_max_x = 0
            pb.ik_min_z = 0
            pb.ik_max_z = 0    
    
        
    def makeGizmo(self, struct):
        me = bpy.data.meshes.new(struct["name"])
        me.from_pydata(struct["verts"], struct["edges"], [])
        ob = bpy.data.objects.new(struct["name"], me)
        return ob

#----------------------------------------------------------
#   FK Snap
#----------------------------------------------------------

def snapSimpleFK(rig, bnames, prop):        
    mats = []      
    for bname in bnames:
        pb = rig.pose.bones[bname]
        mats.append((pb, pb.matrix.copy()))
    setattr(rig, prop, False)    
    for pb,mat in mats:
        pb.matrix = mat   
            

class DAZ_OT_SnapSimpleFK(DazOperator, SimpleIK, B.PrefixString, B.TypeString):
    bl_idname = "daz.snap_simple_fk"
    bl_label = "Snap FK"
    bl_description = "Snap FK bones to IK bones"
    bl_options = {'UNDO'}
    
    def run(self, context):
        rig = context.object
        bnames = self.getLimbBoneNames(rig, self.prefix, self.type)
        if bnames:
            prop = self.getIKProp(self.prefix, self.type)
            snapSimpleFK(rig, bnames, prop)
        
#----------------------------------------------------------
#   IK Snap
#----------------------------------------------------------
    
class DAZ_OT_SnapSimpleIK(DazOperator, SimpleIK, B.PrefixString, B.TypeString):
    bl_idname = "daz.snap_simple_ik"
    bl_label = "Snap IK"
    bl_description = "Snap IK bones to FK bones"
    bl_options = {'UNDO'}
    
    def run(self, context):
        rig = context.object
        bnames = self.getLimbBoneNames(rig, self.prefix, self.type)
        if bnames:
            prop = self.getIKProp(self.prefix, self.type)
            snapSimpleIK(rig, bnames, prop)


def snapSimpleIK(rig, bnames, prop):   
    mats = []
    for bname in bnames[:-1]:
        pb = rig.pose.bones[bname]
        mats.append((pb, pb.matrix.copy()))
    hand = bnames[-1]  
    handfk = rig.pose.bones[hand]
    mat = handfk.matrix.copy()
    handik = rig.pose.bones[hand+"IK"]
    setattr(rig, prop, True)            
    handik.matrix = mat
    return mats
      
#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PrintMatrix,
    DAZ_OT_RotateBones,
    DAZ_OT_SetAddExtraFaceBones,
    DAZ_OT_MakeAllBonesPosable,
    DAZ_OT_ToggleRotLocks,
    DAZ_OT_ToggleLocLocks,
    DAZ_OT_ToggleRotLimits,
    DAZ_OT_ToggleLocLimits,
    DAZ_OT_AddSimpleIK,
    DAZ_OT_SnapSimpleFK,
    DAZ_OT_SnapSimpleIK,
]

def initialize():
    bpy.types.Object.DazSimpleIK = BoolProperty(default=False)
    
    bpy.types.Object.DazArmIK_L = FloatProperty(name="Left Arm IK", default=1.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazArmIK_R = FloatProperty(name="Right Arm IK", default=1.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_L = FloatProperty(name="Left Leg IK", default=1.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_R = FloatProperty(name="Right Leg IK", default=1.0, precision=3, min=0.0, max=1.0)
    

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
