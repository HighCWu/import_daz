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


    def postbuild(self, context):
        Instance.postbuild(self, context)
        if LS.fitFile:
            self.shiftBones(context, self.rna, self.worldmat.inverted())


    def shiftBones(self, context, rig, mat):
        from .node import isUnitMatrix
        if isUnitMatrix(mat):
            return
        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in rig.data.edit_bones:
            eb.head = Mult2(mat, eb.head)
            eb.tail = Mult2(mat, eb.tail)
        bpy.ops.object.mode_set(mode='OBJECT')


    def finalize(self, context):
        from .finger import getFingeredCharacter
        rig,mesh,char = getFingeredCharacter(self.rna)
        if rig and mesh:
            if mesh.name == self.name:
                mesh.name += " Mesh"
            rig.DazMesh = mesh.DazMesh = char
            self.poseChildren(rig, rig)
        elif mesh:
            mesh.DazMesh = char
        self.rna.name = self.name
        Instance.finalize(self, context)
        if rig and char:
            activateObject(context, rig)
            self.selectChildren(rig)
        if self.hiddenBones:
            for geonode in self.geometries:
                geonode.hideVertexGroups(self.hiddenBones.keys())


    def poseChildren(self, ob, rig):
        from .fix import ConstraintStore
        store = ConstraintStore()
        for child in ob.children:
            if child.type == 'ARMATURE':
                for pb in child.pose.bones:
                    if pb.name in rig.pose.bones.keys():
                        parb = rig.pose.bones[pb.name]
                        pb.matrix_basis = parb.matrix_basis
                        pb.lock_location = parb.lock_location
                        pb.lock_rotation = parb.lock_rotation
                        pb.lock_scale = parb.lock_scale
                        store.storeConstraints(parb.name, parb)
                        store.removeConstraints(pb)
                        store.restoreConstraints(parb.name, pb)
                self.poseChildren(child, rig)


    def selectChildren(self, rig):
        for child in rig.children:
            if child.type == 'ARMATURE':
                setSelected(child, True)
                self.selectChildren(child)


    def poseRig(self, context):
        Instance.poseRig(self, context)
        rig = self.rna
        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='POSE')
        self.poseArmature(rig)
        rig.DazRotLocks = rig.DazHasRotLocks = GS.useLockRot
        rig.DazLocLocks = rig.DazHasLocLocks = GS.useLockLoc
        rig.DazRotLimits = rig.DazHasRotLimits = GS.useLimitRot
        rig.DazLocLimits = rig.DazHasLocLimits = GS.useLimitLoc
        self.fixDependencyLoops(rig)
        self.addCustomShapes(rig, context)
        bpy.ops.object.mode_set(mode='OBJECT')


    def poseArmature(self, rig):
        from .bone import BoneInstance
        tchildren = {}
        missing = []
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(self, False, tchildren, missing)
        if missing and GS.verbosity > 2:
            print("Missing bones when posing %s" % self.name)
            print("  %s" % [inst.node.name for inst in missing])


    def addCustomShapes(self, rig, context):
        from .finger import getFingeredCharacter
        if self.node.rigtype and GS.useCustomShapes:
            for geo in self.geometries:
                if geo.rna:
                    _rig,_mesh,char = getFingeredCharacter(geo.rna, verbose=False)
                    if char:
                        if GS.useCustomShapes:
                            addCustomShapes(rig, context, self.collection)


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
        scn = context.scene

        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.listBones()
        self.rigtype = getRigType1(inst.bones.keys())

        center = d2b(inst.attributes["center_point"])
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

        center = inst.attributes["center_point"]
        inst.setupPlanes()
        activateObject(context, rig)

        bpy.ops.object.mode_set(mode='EDIT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(self, rig, None, center, False)
        rig.DazRig = self.rigtype

        bpy.ops.object.mode_set(mode='OBJECT')
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)

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
        return getRigType1(data.pose.bones.keys())
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

def copyBoneInfo(srcpb, trgpb):
    trgpb.bone.DazOrient = Vector(srcpb.bone.DazOrient)
    trgpb.bone.DazHead = Vector(srcpb.bone.DazHead)
    trgpb.bone.DazTail = Vector(srcpb.bone.DazTail)
    trgpb.bone.DazAngle = srcpb.bone.DazAngle
    trgpb.bone.DazNormal = Vector(srcpb.bone.DazNormal)
    trgpb.DazRotMode = srcpb.DazRotMode


class ExtraBones:
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


    def addExtraBones(self, rig):
        from .driver import getBoneDrivers, removeDriverBoneSuffix, storeBoneDrivers, restoreBoneDrivers
        from .fix import ConstraintStore
        if getattr(rig.data, self.attr):
            msg = "Rig %s already has extra %s bones" % (rig.name, self.type)
            print(msg)
            #raise DazError(msg)

        if rig.DazRig[0:6] == "rigify":
            raise DazError("Cannot add extra bones to Rigify rig")
        drivenLayers = 31*[False] + [True]

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
            eb.layers = list(par.layers)
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

        store = ConstraintStore()
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
                pb.custom_shape = par.custom_shape
                par.custom_shape = None
                pb.DazRotLocks = par.DazRotLocks
                pb.DazLocLocks = par.DazLocLocks
                copyBoneInfo(par, pb)
                store.storeConstraints(par.name, par)
                store.removeConstraints(par)
                store.restoreConstraints(par.name, pb)


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


class DAZ_OT_SetAddExtraFaceBones(DazOperator, ExtraBones, IsArmature):
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


class DAZ_OT_MakeAllBonesPosable(DazOperator, ExtraBones, IsArmature):
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


class DAZ_OT_ToggleRotLocks(DazOperator, ToggleLocks):
    bl_idname = "daz.toggle_rot_locks"
    bl_label = "Toggle Rotation Locks"
    bl_description = "Toggle rotation locks"
    bl_options = {'UNDO'}

    attr = "DazRotLocks"
    lock = "lock_rotation"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasRotLocks)


class DAZ_OT_ToggleLocLocks(DazOperator, ToggleLocks):
    bl_idname = "daz.toggle_loc_locks"
    bl_label = "Toggle Location Locks"
    bl_description = "Toggle location locks"
    bl_options = {'UNDO'}

    attr = "DazLocLocks"
    lock = "lock_location"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasLocLocks)

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


class DAZ_OT_ToggleRotLimits(DazOperator, ToggleLimits):
    bl_idname = "daz.toggle_rot_limits"
    bl_label = "Toggle Limits"
    bl_description = "Toggle rotation limits"
    bl_options = {'UNDO'}

    type = "LIMIT_ROTATION"
    attr = "DazRotLimits"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasRotLimits)


class DAZ_OT_ToggleLocLimits(DazOperator, ToggleLimits):
    bl_idname = "daz.toggle_loc_limits"
    bl_label = "Toggle Location Limits"
    bl_description = "Toggle location limits"
    bl_options = {'UNDO'}

    type = "LIMIT_LOCATION"
    attr = "DazLocLimits"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasLocLimits)

#-------------------------------------------------------------
#   Simple IK
#-------------------------------------------------------------

from bpy.props import BoolProperty, FloatProperty, StringProperty

class SimpleIK:
    def __init__(self, usePoleTargets=False):
        self.usePoleTargets = usePoleTargets


    G38Arm = ["ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Hand"]
    G38Leg = ["ThighBend", "ThighTwist", "Shin", "Foot"]
    G38Spine = ["hip", "abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G38Neck = ["neckLower", "neckUpper"]
    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["hip", "abdomen", "abdomen2", "spine", "chest"]
    G12Neck = ["neck"]


    def storeProps(self, rig):
        self.ikprops = (rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R)


    def setProps(self, rig, onoff):
        rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = onoff


    def restoreProps(self, rig):
        rig.DazArmIK_L, rig.DazArmIK_R, rig.DazLegIK_L, rig.DazLegIK_R = self.ikprops


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


    def makeBoneGroup(self, rig):
        bpy.ops.object.mode_set(mode='POSE')
        bgrp = rig.pose.bone_groups.active
        if bgrp:
            return bgrp
        bpy.ops.pose.group_add()
        bgrp = rig.pose.bone_groups.active
        bgrp.name = "Simple IK"
        bgrp.color_set = 'THEME01'


    def limitBone(self, pb, twist, rig, prop, stiffness=(0,0,0)):
        from .mhx import addDriver
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
                addDriver(cns, "influence", rig, prop, "1-x")
                break

        if twist:
            pb.use_ik_limit_x = True
            pb.use_ik_limit_z = True
            pb.ik_min_x = 0
            pb.ik_max_x = 0
            pb.ik_min_z = 0
            pb.ik_max_z = 0

#-------------------------------------------------------------
#   Add Simple IK
#-------------------------------------------------------------

class DAZ_OT_AddSimpleIK(DazPropsOperator, B.PoleTargets, IsArmature):
    bl_idname = "daz.add_simple_ik"
    bl_label = "Add Simple IK"
    bl_description = "Add Simple IK constraints to the active rig"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "usePoleTargets")

    def run(self, context):
        addSimpleIK(context.object, SimpleIK(self.usePoleTargets))


def addSimpleIK(rig, IK):
    from .mhx import makeBone, getBoneCopy, ikConstraint, copyRotation, stretchTo
    if rig.DazSimpleIK:
        raise DazError("The rig %s already has simple IK" % rig.name)

    genesis = IK.getGenesisType(rig)
    if not genesis:
        raise DazError("Cannot create simple IK for the rig %s" % rig.name)

    rig.DazSimpleIK = True
    rig.DazArmIK_L = rig.DazArmIK_R = rig.DazLegIK_L = rig.DazLegIK_R = 0.0

    if IK.usePoleTargets:
        csCube = makeCustomShape("CS_Cube", "Cube", scale=1/2)

    bpy.ops.object.mode_set(mode='EDIT')
    ebones = rig.data.edit_bones
    for prefix in ["l", "r"]:
        hand = ebones[prefix+"Hand"]
        handIK = makeBone(prefix+"HandIK", rig, hand.head, hand.tail, hand.roll, 0, None)
        foot = ebones[prefix+"Foot"]
        handIK = makeBone(prefix+"FootIK", rig, foot.head, foot.tail, foot.roll, 0, None)
        forearm = ebones[prefix+"ForearmBend"]
        collar = ebones[prefix+"Collar"]
        shin = ebones[prefix+"Shin"]
        hip = ebones["hip"]
        if IK.usePoleTargets:
            elbow = makePole(prefix+"Elbow", rig, forearm, collar)
            knee = makePole(prefix+"Knee", rig, shin, hip)

    bgrp = IK.makeBoneGroup(rig)
    rpbs = rig.pose.bones
    for prefix in ["l", "r"]:
        suffix = prefix.upper()
        armProp = "DazArmIK_" + suffix
        hand = rpbs[prefix+"Hand"]
        driveConstraint(hand, 'LIMIT_ROTATION', rig, armProp, "1-x")
        handIK = getBoneCopy(prefix+"HandIK", hand, rpbs)
        copyRotation(hand, handIK, (True,True,True), rig, space='WORLD', prop=armProp)
        handIK.custom_shape = hand.custom_shape
        handIK.custom_shape_scale = 1.8
        handIK.bone_group = bgrp
        addToLayer(handIK, "IK Arm")

        legProp = "DazLegIK_" + suffix
        foot = rpbs[prefix+"Foot"]
        driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp, "1-x")
        footIK = getBoneCopy(prefix+"FootIK", foot, rpbs)
        copyRotation(foot, footIK, (True,True,True), rig, space='WORLD', prop=legProp)
        footIK.custom_shape = foot.custom_shape
        footIK.custom_shape_scale = 1.8
        footIK.bone_group = bgrp
        addToLayer(footIK, "IK Leg")

        if genesis == "G38":
            shldrBend = rpbs[prefix+"ShldrBend"]
            IK.limitBone(shldrBend, False, rig, armProp)
            shldrTwist = rpbs[prefix+"ShldrTwist"]
            IK.limitBone(shldrTwist, True, rig, armProp)
            forearmBend = rpbs[prefix+"ForearmBend"]
            IK.limitBone(forearmBend, False, rig, armProp)
            forearmTwist = rpbs[prefix+"ForearmTwist"]
            IK.limitBone(forearmTwist, True, rig, armProp)
            if IK.usePoleTargets:
                elbow = rpbs[prefix+"Elbow"]
                elbow.lock_rotation = (True,True,True)
                elbow.custom_shape = csCube
                addToLayer(elbow, "IK Arm")
                stretch = rpbs[stretchName(elbow.name)]
                stretchTo(stretch, elbow, rig)
                addToLayer(stretch, "IK Arm")
            else:
                elbow = None
            ikConstraint(forearmTwist, handIK, elbow, -90, 4, rig, prop=armProp)

            thighBend = rpbs[prefix+"ThighBend"]
            IK.limitBone(thighBend, False, rig, legProp, stiffness=(0,0,0.326))
            thighTwist = rpbs[prefix+"ThighTwist"]
            IK.limitBone(thighTwist, True, rig, legProp, stiffness=(0,0.160,0))
            shin = rpbs[prefix+"Shin"]
            IK.limitBone(shin, False, rig, legProp, stiffness=(0.068,0,0.517))
            if IK.usePoleTargets:
                knee = rpbs[prefix+"Knee"]
                knee.lock_rotation = (True,True,True)
                knee.custom_shape = csCube
                addToLayer(knee, "IK Leg")
                stretch = rpbs[stretchName(knee.name)]
                stretchTo(stretch, knee, rig)
                addToLayer(stretch, "IK Leg")
            else:
                knee = None
            ikConstraint(shin, footIK, knee, -90, 3, rig, prop=legProp)

        elif genesis == "G12":
            shldr = rpbs[prefix+"Shldr"]
            IK.limitBone(shldr, False, rig, armProp)
            forearm = rpbs[prefix+"ForeArm"]
            IK.limitBone(forearm, False, rig, armProp)
            ikConstraint(forearm, handIK, None, 0, 2, rig, prop=armProp)

            thigh = rpbs[prefix+"Thigh"]
            IK.limitBone(thigh, False, rig, legProp)
            shin = rpbs[prefix+"Shin"]
            IK.limitBone(shin, False, rig, legProp)
            ikConstraint(shin, footIK, None, 0, 2, rig, prop=legProp)


def makePole(bname, rig, eb, parent):
    from .mhx import makeBone
    mat = eb.matrix.to_3x3()
    xaxis = mat.col[0]
    zaxis = mat.col[2]
    size = 10*rig.DazScale
    head = eb.head - size*zaxis
    tail = head + size*Vector((0,0,1))
    makeBone(bname, rig, head, tail, 0, 0, parent)
    strname = stretchName(bname)
    makeBone(strname, rig, eb.head, head, 0, 0, eb)


def stretchName(bname):
    return (bname+"_STR")


def driveConstraint(pb, type, rig, prop, expr):
    from .mhx import addDriver
    for cns in pb.constraints:
        if cns.type == type:
            addDriver(cns, "influence", rig, prop, expr)

#----------------------------------------------------------
#   Connect bones in IK chains
#----------------------------------------------------------

class DAZ_OT_ConnectIKChains(DazPropsOperator, SimpleIK, B.ConnectIK, IsArmature):
    bl_idname = "daz.connect_ik_chains"
    bl_label = "Connect IK Chains"
    bl_description = "Connect all bones in IK chains to their parents"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "type")
        self.layout.prop(self, "location")
        self.layout.prop(self, "unlock")


    def run(self, context):
        rig = context.object
        self.getBoneNames(rig)
        bpy.ops.object.mode_set(mode="EDIT")
        for chain in self.chains:
            parb = rig.data.edit_bones[chain[0]]
            for child in chain[1:]:
                eb = rig.data.edit_bones[child]
                self.relocate(parb, eb)
                eb.use_connect = True
                parb = eb
        if self.unlock:
            bpy.ops.object.mode_set(mode="EDIT")
            for chain in self.chains:
                pb = rig.pose.bones[chain[-1]]
                pb.lock_location = (False,False,False)


    def relocate(self, parb, eb):
        if self.location == 'TAIL':
            eb.head = parb.tail
        elif self.location == 'HEAD':
            parb.tail = eb.head
        elif self.location == 'CENTER':
            center = (eb.head + parb.tail)/2
            parb.tail = eb.head = center


    def getBoneNames(self, rig):
        self.chains = []
        if self.type == 'ARMS':
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Arm")
                self.chains.append(chain)
        elif self.type == 'LEGS':
            for prefix in ["l", "r"]:
                chain = self.getLimbBoneNames(rig, prefix, "Leg")
                self.chains.append(chain)
        elif self.type == 'ARMSLEGS':
            for prefix in ["l", "r"]:
                for type in ["Arm", "Leg"]:
                    chain = self.getLimbBoneNames(rig, prefix, type)
                    self.chains.append(chain)
        elif self.type == 'SELECTED':
            roots = []
            for bone in rig.data.bones:
                if bone.parent is None:
                    roots.append(bone)
            for root in roots:
                self.getChildNames(rig, root)
        return self.chains


    def getChildNames(self, rig, bone):
        if bone.select:
            self.chain = []
            self.getChainNames(rig, bone)
            self.chains.append(self.chain)
        else:
            for child in bone.children:
                self.getChildNames(rig, child)


    def getChainNames(self, rig, bone):
        if bone.select:
            self.chain.append(bone.name)
            for child in bone.children:
                self.getChainNames(rig, child)

#----------------------------------------------------------
#   Custom shapes
#----------------------------------------------------------

BoneLayers = {
    "Spine" : 16,
    "Face" : 17,
    "Left FK Arm" : 18,
    "Right FK Arm" : 19,
    "Left FK Leg" : 20,
    "Right FK Leg" : 21,
    "Left Hand" : 22,
    "Right Hand" : 23,
    "Left Foot" : 24,
    "Right Foot" : 25,
    "Left IK Arm" : 26,
    "Right IK Arm" : 27,
    "Left IK Leg" : 28,
    "Right IK Leg" : 29,
}

def addToLayer(pb, lname):
    if lname in BoneLayers.keys():
        n = BoneLayers[lname]
    elif pb.name[0] == "l" and "Left "+lname in BoneLayers.keys():
        n = BoneLayers["Left "+lname]
    elif pb.name[0] == "r" and "Right "+lname in BoneLayers.keys():
        n = BoneLayers["Right "+lname]
    else:
        print("MISSING LAYER", lname, pb.name)
    pb.bone.layers[n] = True


class DAZ_OT_SelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.select_named_layers"
    bl_label = "All"
    bl_description = "Select all named layers and unselect all unnamed layers"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


class DAZ_OT_UnSelectNamedLayers(DazOperator, IsArmature):
    bl_idname = "daz.unselect_named_layers"
    bl_label = "Only Active"
    bl_description = "Unselect all named and unnamed layers except active"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        m = 16
        bone = rig.data.bones.active
        if bone:
            for n in range(16,30):
                if bone.layers[n]:
                    m = n
                    break
        rig.data.layers = m*[False] + [True] + (31-m)*[False]

#----------------------------------------------------------
#   Custom shapes
#----------------------------------------------------------

def makeCustomShape(csname, gname, offset=(0,0,0), scale=1):
    Gizmos = {
        "CircleX" : {
            "verts" : [[0, 1, 0], [0, 0.9808, 0.1951], [0, 0.9239, 0.3827], [0, 0.8315, 0.5556], [0, 0.7071, 0.7071], [0, 0.5556, 0.8315], [0, 0.3827, 0.9239], [0, 0.1951, 0.9808], [0, 0, 1], [0, -0.1951, 0.9808], [0, -0.3827, 0.9239], [0, -0.5556, 0.8315], [0, -0.7071, 0.7071], [0, -0.8315, 0.5556], [0, -0.9239, 0.3827], [0, -0.9808, 0.1951], [0, -1, 0], [0, -0.9808, -0.1951], [0, -0.9239, -0.3827], [0, -0.8315, -0.5556], [0, -0.7071, -0.7071], [0, -0.5556, -0.8315], [0, -0.3827, -0.9239], [0, -0.1951, -0.9808], [0, 0, -1], [0, 0.1951, -0.9808], [0, 0.3827, -0.9239], [0, 0.5556, -0.8315], [0, 0.7071, -0.7071], [0, 0.8315, -0.5556], [0, 0.9239, -0.3827], [0, 0.9808, -0.1951]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "CircleY" : {
            "verts" : [[1, 0, 0], [0.9808, 0, 0.1951], [0.9239, 0, 0.3827], [0.8315, 0, 0.5556], [0.7071, 0, 0.7071], [0.5556, 0, 0.8315], [0.3827, 0, 0.9239], [0.1951, 0, 0.9808], [0, 0, 1], [-0.1951, 0, 0.9808], [-0.3827, 0, 0.9239], [-0.5556, 0, 0.8315], [-0.7071, 0, 0.7071], [-0.8315, 0, 0.5556], [-0.9239, 0, 0.3827], [-0.9808, 0, 0.1951], [-1, 0, 0], [-0.9808, 0, -0.1951], [-0.9239, 0, -0.3827], [-0.8315, 0, -0.5556], [-0.7071, 0, -0.7071], [-0.5556, 0, -0.8315], [-0.3827, 0, -0.9239], [-0.1951, 0, -0.9808], [0, 0, -1], [0.1951, 0, -0.9808], [0.3827, 0, -0.9239], [0.5556, 0, -0.8315], [0.7071, 0, -0.7071], [0.8315, 0, -0.5556], [0.9239, 0, -0.3827], [0.9808, 0, -0.1951]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "CircleZ" : {
            "verts" : [[0, 1, 0], [-0.1951, 0.9808, 0], [-0.3827, 0.9239, 0], [-0.5556, 0.8315, 0], [-0.7071, 0.7071, 0], [-0.8315, 0.5556, 0], [-0.9239, 0.3827, 0], [-0.9808, 0.1951, 0], [-1, 0, 0], [-0.9808, -0.1951, 0], [-0.9239, -0.3827, 0], [-0.8315, -0.5556, 0], [-0.7071, -0.7071, 0], [-0.5556, -0.8315, 0], [-0.3827, -0.9239, 0], [-0.1951, -0.9808, 0], [0, -1, 0], [0.1951, -0.9808, 0], [0.3827, -0.9239, 0], [0.5556, -0.8315, 0], [0.7071, -0.7071, 0], [0.8315, -0.5556, 0], [0.9239, -0.3827, 0], [0.9808, -0.1951, 0], [1, 0, 0], [0.9808, 0.1951, 0], [0.9239, 0.3827, 0], [0.8315, 0.5556, 0], [0.7071, 0.7071, 0], [0.5556, 0.8315, 0], [0.3827, 0.9239, 0], [0.1951, 0.9808, 0]],
            "edges" : [[1, 0], [2, 1], [3, 2], [4, 3], [5, 4], [6, 5], [7, 6], [8, 7], [9, 8], [10, 9], [11, 10], [12, 11], [13, 12], [14, 13], [15, 14], [16, 15], [17, 16], [18, 17], [19, 18], [20, 19], [21, 20], [22, 21], [23, 22], [24, 23], [25, 24], [26, 25], [27, 26], [28, 27], [29, 28], [30, 29], [31, 30], [0, 31]]
        },
        "Cube" : {
            "verts" : [[-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, 0.5, 0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5]],
            "edges" : [[2, 0], [0, 1], [1, 3], [3, 2], [6, 2], [3, 7], [7, 6], [4, 6], [7, 5], [5, 4], [0, 4], [5, 1]]
        }
    }
    me = bpy.data.meshes.new(csname)
    struct = Gizmos[gname]
    verts = struct["verts"]
    u,v,w = offset
    if isinstance(scale, tuple):
        a,b,c = scale
    else:
        a,b,c = scale,scale,scale
    verts = [(a*(x+u), b*(y+v), c*(z+w)) for x,y,z in struct["verts"]]
    me.from_pydata(verts, struct["edges"], [])
    ob = bpy.data.objects.new(csname, me)
    LS.customShapes.append(ob)
    return ob


class DAZ_OT_AddCustomShapes(DazOperator, IsArmature):
    bl_idname = "daz.add_custom_shapes"
    bl_label = "Add Custom Shapes"
    bl_description = "Add custom shapes to the bones of the active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        addCustomShapes(context.object, context, context.collection)


def addCustomShapes(rig, context, coll):
    LS.customShapes = []
    IK = SimpleIK()

    csCollar = makeCustomShape("CS_Collar", "CircleX", (0,1,0), (0,0.5,0.1))
    csHand = makeCustomShape("CS_Hand", "CircleX", (0,1,0), (0,0.6,0.5))
    csCarpal = makeCustomShape("CS_Carpal", "CircleZ", (0,1,0), (0.1,0.5,0))
    csTongue = makeCustomShape("CS_Tongue", "CircleZ", (0,1,0), (1.5,0.5,0))
    circleY2 = makeCustomShape("CS_CircleY2", "CircleY", scale=1/3)
    csLimb = makeCustomShape("CS_Limb", "CircleY", (0,2,0), scale=1/4)
    csBend = makeCustomShape("CS_Bend", "CircleY", (0,1,0), scale=1/2)
    csFace = makeCustomShape("CS_Face", "CircleY", scale=1/5)
    csCube = makeCustomShape("CS_Cube", "Cube", scale=1/2)

    spineWidth = 1
    if "lCollar" in rig.data.bones.keys() and "rCollar" in rig.data.bones.keys():
        lCollar = rig.data.bones["lCollar"]
        rCollar = rig.data.bones["rCollar"]
        spineWidth = 0.5*(lCollar.tail_local[0] - rCollar.tail_local[0])

    csFoot = None
    csToe = None
    if "lFoot" in rig.data.bones.keys() and "lToe" in rig.data.bones.keys():
        lFoot = rig.data.bones["lFoot"]
        lToe = rig.data.bones["lToe"]
        footFactor = (lToe.head_local[1] - lFoot.head_local[1])/(lFoot.tail_local[1] - lFoot.head_local[1])
        csFoot = makeCustomShape("CS_Foot", "CircleZ", (0,1,0), (0.8,0.5*footFactor,0))
        csToe = makeCustomShape("CS_Toe", "CircleZ", (0,1,0), (1,0.5,0))

    for bname in ["upperFaceRig", "lowerFaceRig", "lMetatarsals", "rMetatarsals", "upperTeeth", "lowerTeeth"]:
        if bname in rig.data.bones.keys():
            bone = rig.data.bones[bname]
            bone.layers = [False] + [True] + 30*[False]

    bgrp = IK.makeBoneGroup(rig)
    for pb in rig.pose.bones:
        if not pb.bone.layers[0]:
            pass
        elif pb.parent and pb.parent.name in ["lowerFaceRig", "upperFaceRig"]:
            pb.custom_shape = csFace
            addToLayer(pb, "Face")
        elif pb.name == "lowerJaw":
            pb.custom_shape = csCollar
            addToLayer(pb, "Spine")
        elif pb.name.startswith("tongue"):
            pb.custom_shape = csTongue
            addToLayer(pb, "Face")
        elif pb.name.endswith("Hand"):
            pb.custom_shape = csHand
            addToLayer(pb, "FK Arm")
        elif pb.name.endswith("HandIK"):
            pb.custom_shape = csHand
            pb.custom_shape_scale = 1.8
            pb.bone_group = bgrp
            addToLayer(pb, "IK Arm")
        elif pb.name[1:7] == "Carpal":
            pb.custom_shape = csCarpal
            addToLayer(pb, "Hand")
        elif pb.name.endswith("Collar"):
            pb.custom_shape = csCollar
            addToLayer(pb, "Spine")
        elif pb.name.endswith("Foot"):
            pb.custom_shape = csFoot
            addToLayer(pb, "FK Leg")
        elif pb.name.endswith("FootIK"):
            pb.custom_shape = csFoot
            pb.custom_shape_scale = 1.8
            pb.bone_group = bgrp
            addToLayer(pb, "IK Leg")
        elif pb.name[1:4] == "Toe":
            pb.custom_shape = csToe
            addToLayer(pb, "FK Leg")
            addToLayer(pb, "IK Leg")
            addToLayer(pb, "Foot")
        elif pb.name[1:] in IK.G12Arm:
            pb.custom_shape = csLimb
            addToLayer(pb, "FK Arm")
        elif pb.name[1:] in IK.G12Leg:
            pb.custom_shape = csLimb
            addToLayer(pb, "FK Leg")
        elif pb.name[1:] in IK.G38Arm:
            pb.custom_shape = csBend
            addToLayer(pb, "FK Arm")
        elif pb.name[1:] in IK.G38Leg:
            pb.custom_shape = csBend
            addToLayer(pb, "FK Leg")
        elif pb.name[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]:
            pb.custom_shape = csLimb
            addToLayer(pb, "Hand")
        elif pb.name == "hip":
            makeSpine(pb, 2*spineWidth)
            pb.bone_group = bgrp
            addToLayer(pb, "Spine")
        elif pb.name == "pelvis":
            makeSpine(pb, 1.5*spineWidth, 0.5)
            addToLayer(pb, "Spine")
        elif pb.name in IK.G38Spine + IK.G12Spine:
            makeSpine(pb, spineWidth)
            addToLayer(pb, "Spine")
        elif pb.name in IK.G38Neck + IK.G12Neck:
            makeSpine(pb, 0.5*spineWidth)
            addToLayer(pb, "Spine")
        elif pb.name == "head":
            makeSpine(pb, 0.7*spineWidth, 1)
            addToLayer(pb, "Spine")
            addToLayer(pb, "Face")
        elif "Toe" in pb.name:
            pb.custom_shape = circleY2
            addToLayer(pb, "Foot")
        elif pb.name[1:4] in ["Thu", "Ind", "Mid", "Rin", "Pin"]:
            pb.custom_shape = circleY2
            addToLayer(pb, "Hand")
        elif pb.name[1:4] in ["Eye", "Ear"]:
            pb.custom_shape = circleY2
            addToLayer(pb, "Face")
        elif "Elbow" in pb.name:
            if not pb.name.endswith("STR"):
                pb.custom_shape = csCube
            addToLayer(pb, "IK Arm")
        elif "Knee" in pb.name:
            if not pb.name.endswith("STR"):
                pb.custom_shape = csCube
            addToLayer(pb, "IK Leg")
        else:
            pb.custom_shape = circleY2
            print("Unknown bone:", pb.name)

    hideCustomShapes(rig, context, coll)


def hideCustomShapes(rig, context, coll):
    hidden = createHiddenCollection(context, coll)
    empty = bpy.data.objects.new("Custom Shapes", None)
    hidden.objects.link(empty)
    empty.parent = rig
    putOnHiddenLayer(empty)
    for ob in LS.customShapes:
        hidden.objects.link(ob)
        ob.parent = empty
        putOnHiddenLayer(ob)


def makeSpine(pb, width, tail=0.5):
    s = width/pb.bone.length
    circle = makeCustomShape("CS_" + pb.name, "CircleY", (0,tail/s,0))
    pb.custom_shape = circle
    pb.custom_shape_scale = s


class DAZ_OT_RemoveCustomShapes(DazOperator, IsArmature):
    bl_idname = "daz.remove_custom_shapes"
    bl_label = "Remove Custom Shapes"
    bl_description = "Remove custom shapes from the bones of the active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            pb.custom_shape = None

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
            toggleLayer(rig, "FK", self.prefix, self.type, True)
            toggleLayer(rig, "IK", self.prefix, self.type, False)

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
            toggleLayer(rig, "FK", self.prefix, self.type, False)
            toggleLayer(rig, "IK", self.prefix, self.type, True)


def snapSimpleIK(rig, bnames, prop):
    hand = bnames[-1]
    handfk = rig.pose.bones[hand]
    mat = handfk.matrix.copy()
    handik = rig.pose.bones[hand+"IK"]
    setattr(rig, prop, True)
    handik.matrix = mat


def toggleLayer(rig, fk, prefix, type, on):
    side = {"l" : "Left", "r" : "Right"}
    lname = ("%s %s %s" % (side[prefix], fk, type))
    layer = BoneLayers[lname]
    rig.data.layers[layer] = on

#----------------------------------------------------------
#   Update for 1.5
#----------------------------------------------------------

class DAZ_OT_UpdateRigVersion(DazOperator, IsArmature):
    bl_idname = "daz.update_rig_version"
    bl_label = "Update Rig For Version 1.5"
    bl_description = "Use this if you have problems with posing old characters"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for bone in rig.data.bones:
            if "DazOrientation" in bone.keys():
                bone.DazOrient = list(bone["DazOrientation"])


class DAZ_OT_CopyDazProps(DazOperator, IsObject):
    bl_idname = "daz.copy_daz_props"
    bl_label = "Copy DAZ Properties"
    bl_description = ("Copy DAZ properties from active object to selected objects.\n" +
                      "Only properties that are not already set")
    bl_options = {'UNDO'}

    def run(self, context):
        src = context.object
        for trg in getSceneObjects(context):
            if getSelected(trg) and trg.type == src.type and trg != src:
                self.copyObjectProps(src, trg)
                print("DAZ properties copied from %s to %s" % (src.name, trg.name))


    def copyObjectProps(self, src, trg):
        self.copyInfo(src, trg)
        if src.type == 'ARMATURE':
            for srcpb in src.pose.bones:
                if srcpb.name in trg.pose.bones.keys():
                    trgpb = trg.pose.bones[srcpb.name]
                    copyBoneInfo(srcpb, trgpb)


    def copyInfo(self, src, trg):
        for key,value in src.items():
            if key[0:3] == "Daz" and key not in trg.keys():
                trg[key] = value

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
    DAZ_OT_ConnectIKChains,
    DAZ_OT_SelectNamedLayers,
    DAZ_OT_UnSelectNamedLayers,
    DAZ_OT_AddCustomShapes,
    DAZ_OT_RemoveCustomShapes,
    DAZ_OT_AddSimpleIK,
    DAZ_OT_SnapSimpleFK,
    DAZ_OT_SnapSimpleIK,
    DAZ_OT_UpdateRigVersion,
    DAZ_OT_CopyDazProps,
]

def initialize():
    bpy.types.Object.DazSimpleIK = BoolProperty(default=False)
    bpy.types.Object.DazArmIK_L = FloatProperty(name="Left Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazArmIK_R = FloatProperty(name="Right Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_L = FloatProperty(name="Left Leg IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.DazLegIK_R = FloatProperty(name="Right Leg IK", default=0.0, precision=3, min=0.0, max=1.0)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
