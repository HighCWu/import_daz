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
import math
from mathutils import *
from .utils import *
from .error import *
from .node import Node, Instance
from .driver import DriverUser

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


    def preprocess(self, struct):
        from .bone import BoneInstance
        Instance.preprocess(self, struct)
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.listBones()


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
            eb.head = mat @ eb.head
            eb.tail = mat @ eb.tail
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
                child.select_set(True)
                self.selectChildren(child)


    def poseRig(self, context):
        from .bone import BoneInstance
        rig = self.rna
        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='POSE')
        self.poseArmature(rig)
        rig.DazRotLocks = rig.DazHasRotLocks = GS.useLockRot
        rig.DazLocLocks = rig.DazHasLocLocks = GS.useLockLoc
        rig.DazRotLimits = rig.DazHasRotLimits = GS.useLimitRot
        rig.DazLocLimits = rig.DazHasLocLimits = GS.useLimitLoc
        self.fixDependencyLoops(rig)
        bpy.ops.object.mode_set(mode='OBJECT')
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, False)


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


    def fixDependencyLoops(self, rig):
        from .driver import getBoneDrivers, getDrivingBone
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
                self.clearBendDrivers(fcus)


    def clearBendDrivers(self, fcus):
        for fcu in fcus:
            if fcu.array_index != 1:
                fcu.driver.expression = "0"
                for var in fcu.driver.variables:
                    fcu.driver.variables.remove(var)


    def addLSRig(self, rig):
        if (LS.rigname is None or
            not isinstance(self.parent, FigureInstance)):
            LS.rigname = rig.name
            LS.rigs[LS.rigname] = []
            LS.meshes[LS.rigname] = []
            LS.objects[LS.rigname] = []
            LS.hairs[LS.rigname] = []
            LS.hdmeshes[LS.rigname] = []
        LS.rigs[LS.rigname].append(rig)


    def setupPlanes(self):
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
        self.classType = Figure
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
        from .asset import Asset
        scn = context.scene

        self.rigtype = getRigType1(inst.bones.keys())
        center = d2b(inst.attributes["center_point"])
        Asset.build(self, context, inst)
        for geo in inst.geometries:
            geo.buildObject(context, inst, center)
            geo.rna.location = Zero
        amt = self.data = bpy.data.armatures.new(inst.name)
        self.buildObject(context, inst, center)
        rig = self.rna
        inst.addLSRig(rig)
        amt.display_type = 'STICK'
        rig.show_in_front = True
        rig.DazOrientMethod = GS.orientMethod
        for geonode in inst.geometries:
            geonode.parent = geonode.figure = self
            geonode.rna.parent = rig
            geonode.addLSMesh(geonode.rna, inst, LS.rigname)

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


class DAZ_OT_RotateBones(DazPropsOperator, IsArmature):
    bl_idname = "daz.rotate_bones"
    bl_label = "Rotate Bones"
    bl_description = "Rotate selected bones the same angle"
    bl_options = {'UNDO'}

    X : FloatProperty(name = "X")
    Y : FloatProperty(name = "Y")
    Z : FloatProperty(name = "Z")

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
    trgpb.rotation_mode = srcpb.rotation_mode
    trgpb.lock_location = srcpb.lock_location
    trgpb.lock_rotation = srcpb.lock_rotation
    trgpb.lock_scale = srcpb.lock_scale
    trgpb.bone.DazOrient = Vector(srcpb.bone.DazOrient)
    trgpb.bone.DazHead = Vector(srcpb.bone.DazHead)
    trgpb.bone.DazTail = Vector(srcpb.bone.DazTail)
    trgpb.bone.DazAngle = srcpb.bone.DazAngle
    trgpb.bone.DazNormal = Vector(srcpb.bone.DazNormal)
    trgpb.DazRotMode = srcpb.DazRotMode
    if "DazAltName" in srcpb.keys():
        trgpb.DazAltName = srcpb.DazAltName


class ExtraBones(DriverUser):
    def run(self, context):
        from time import perf_counter
        t1 = perf_counter()
        rig = context.object
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        self.createTmp()
        try:
            self.addExtraBones(rig)
            success = True
        finally:
            self.deleteTmp()
            rig.data.layers = oldvis
        t2 = perf_counter()
        print("%s completed in %.1f seconds" % (self.button, t2-t1))


    def correctDriver(self, fcu, rig):
        varnames = dict([(var.name,True) for var in fcu.driver.variables])
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.bone_target:
                    self.combineDrvFinBone(fcu, rig, var, trg, varnames)
                if trg.data_path:
                    trg.data_path = self.replaceDataPathDrv(trg.data_path)


    def replaceDataPathDrv(self, string):
        words = string.split('"')
        if words[0] == "pose.bones[":
            bname = words[1]
            if isDrvBone(bname):
                return string
            elif bname in self.bnames:
                return string.replace(propRef(bname), propRef(drvBone(bname)))
        return string


    def combineDrvFinBone(self, fcu, rig, var, trg, varnames):
        if trg.transform_type[0:3] == "ROT":
            bname = baseBone(trg.bone_target)
            if finBone(bname) in rig.pose.bones.keys():
                trg.bone_target = finBone(bname)
            elif drvBone(bname) in rig.pose.bones.keys():
                trg.bone_target = drvBone(bname)
        else:
            self.combineDrvSimple(fcu, var, trg, varnames)


    def combineDrvSimple(self, fcu, var, trg, varnames):
        from .driver import Target
        vname2 = var.name+"2"
        if vname2 in varnames.keys():
            return
        var2 = fcu.driver.variables.new()
        var2.name = vname2
        var2.type = var.type
        target2 = Target(trg)
        trg2 = var2.targets[0]
        target2.create(trg2)
        trg2.bone_target = baseBone(trg.bone_target)
        expr = fcu.driver.expression.replace(var.name, "(%s+%s)" % (var.name, var2.name))
        fcu.driver.expression = expr


    def addFinBone(self, rig, bname):
        from .driver import addTransformVar
        pb = rig.pose.bones[bname]
        fb = rig.pose.bones[finBone(bname)]
        cns = fb.constraints.new('COPY_ROTATION')
        cns.target = rig
        cns.subtarget = bname
        if pb.parent.rotation_mode != 'QUATERNION':
            cns.euler_order = pb.parent.rotation_mode
        cns.target_space = 'POSE'
        cns.owner_space = 'POSE'
        cns.influence = 1.0


    def updateScriptedDrivers(self, rna):
        if rna.animation_data:
            fcus = [fcu for fcu in rna.animation_data.drivers
                    if fcu.driver.type == 'SCRIPTED']
            for fcu in fcus:
                for btarget in self.getBoneTargets(fcu):
                    bname = baseBone(btarget[1])
                    if bname and bname in self.bnames:
                        channel = fcu.data_path
                        fcu2 = self.getTmpDriver(0)
                        self.copyFcurve(fcu, fcu2)
                        rna.driver_remove(channel)
                        self.setBoneTarget(fcu2, finBone(bname))
                        fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
                        fcu3.data_path = channel
                        self.clearTmpDriver(0)


    def storeRemoveBoneSumDrivers(self, rig):
        def store(fcus, rig):
            from .driver import Driver
            drivers = {}
            for bname in fcus.keys():
                drivers[bname] = []
                for fcu in fcus[bname]:
                    drivers[bname].append(Driver(fcu, True))
            return drivers

        from .driver import removeDriverFCurves, getAllBoneSumDrivers
        boneFcus, sumFcus = getAllBoneSumDrivers(rig, self.bnames)
        boneDrivers = store(boneFcus, rig)
        sumDrivers = store(sumFcus, rig)
        removeDriverFCurves(boneFcus.values(), rig)
        removeDriverFCurves(sumFcus.values(), rig)
        return boneDrivers, sumDrivers


    def restoreBoneSumDrivers(self, rig, drivers, fixDrv):
        for bname,bdrivers in drivers.items():
            pb = rig.pose.bones[drvBone(bname)]
            for driver in bdrivers:
                fcu = self.getTmpDriver(0)
                driver.fill(fcu)
                self.correctDriver(fcu, rig)
                fcu2 = rig.animation_data.drivers.from_existing(src_driver=fcu)
                fcu2.data_path = driver.data_path.replace(propRef(bname), propRef(drvBone(bname)))
                fcu2.array_index = driver.array_index
                self.clearTmpDriver(0)


    def addExtraBones(self, rig):
        def copyEditBone(db, rig, bname):
            eb = rig.data.edit_bones.new(bname)
            eb.head = db.head
            eb.tail = db.tail
            eb.roll = db.roll
            eb.layers = list(db.layers)
            eb.use_deform = db.use_deform
            return eb


        def copyPoseBone(db, pb):
            pb.rotation_mode = db.rotation_mode
            pb.lock_location = db.lock_location
            pb.lock_rotation = db.lock_rotation
            pb.lock_scale = db.lock_scale
            pb.custom_shape = db.custom_shape
            pb.DazRotLocks = db.DazRotLocks
            pb.DazLocLocks = db.DazLocLocks


        from .driver import getBoneDrivers, getPropDrivers, getShapekeyDriver, removeDriverFCurves
        from .fix import ConstraintStore
        if getattr(rig.data, self.attr):
            msg = "Rig %s already has extra %s bones" % (rig.name, self.type)
            print(msg)
            #raise DazError(msg)

        if rig.DazRig[0:6] == "rigify":
            raise DazError("Cannot add extra bones to Rigify rig")
        drivenLayers = 31*[False] + [True]
        finalLayers = 30*[False] + [True,False]

        print("  Rename bones")
        self.bnames = self.getBoneNames(rig)
        boneDrivers, sumDrivers = self.storeRemoveBoneSumDrivers(rig)
        bpy.ops.object.mode_set(mode='EDIT')
        for bname in self.bnames:
            eb = rig.data.edit_bones[bname]
            eb.name = drvBone(bname)
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.mode_set(mode='EDIT')
        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            eb = copyEditBone(db, rig, bname)
            eb.parent = db
            fb = copyEditBone(db, rig, finBone(bname))
            fb.parent = db.parent
            fb.layers = finalLayers
            fb.use_deform = False
            db.layers = drivenLayers
            db.use_deform = False
        bpy.ops.object.mode_set(mode='OBJECT')

        for bname in self.bnames:
            if (bname not in rig.pose.bones.keys() or
                drvBone(bname) not in rig.pose.bones.keys()):
                del self.bnames[bname]

        bpy.ops.object.mode_set(mode='EDIT')
        for bname in self.bnames:
            db = rig.data.edit_bones[drvBone(bname)]
            for cb in db.children:
                if cb.name != bname:
                    cb.parent = rig.data.edit_bones[bname]

        print("  Change constraints")
        bpy.ops.object.mode_set(mode='POSE')
        store = ConstraintStore()
        for bname in self.bnames:
            pb = rig.pose.bones[bname]
            db = rig.pose.bones[drvBone(bname)]
            fb = rig.pose.bones[finBone(bname)]
            copyPoseBone(db, pb)
            copyPoseBone(db, fb)
            db.custom_shape = None
            copyBoneInfo(db, pb)
            store.storeConstraints(db.name, db)
            store.removeConstraints(db)
            store.restoreConstraints(db.name, pb)

        print("  Add fin bone drivers")
        for bname in self.bnames:
            self.addFinBone(rig, bname)
        print("  Restore bone drivers")
        self.restoreBoneSumDrivers(rig, boneDrivers, False)
        print("  Restore sum drivers")
        self.restoreBoneSumDrivers(rig, sumDrivers, True)
        print("  Update scripted drivers")
        self.updateScriptedDrivers(rig.data)
        print("  Update drivers")
        setattr(rig.data, self.attr, True)
        updateDrivers(rig)

        print("  Update vertex groups")
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in rig.children:
            if ob.type == 'MESH':
                for vgrp in ob.vertex_groups:
                    if isDrvBone(vgrp.name):
                        vgname = baseBone(vgrp.name)
                        if vgname in self.bnames:
                            vgrp.name = vgname

        print("  Update shapekeys")
        for ob in rig.children:
            if ob.type == 'MESH':
                skeys = ob.data.shape_keys
                if skeys:
                    for skey in skeys.key_blocks[1:]:
                        fcu = getShapekeyDriver(skeys, skey.name)
                        if fcu:
                            self.correctDriver(fcu, rig)
            updateDrivers(ob)


class DAZ_OT_SetAddExtraFaceBones(DazOperator, ExtraBones, IsArmature):
    bl_idname = "daz.add_extra_face_bones"
    bl_label = "Add Extra Face Bones"
    bl_description = "Add an extra layer of face bones, which can be both driven and posed"
    bl_options = {'UNDO'}

    type =  "face"
    attr = "DazExtraFaceBones"
    button = "Add Extra Face Bones"

    def getBoneNames(self, rig):
        inface = [
            "lEye", "rEye",
            "lowerJaw", "upperTeeth", "lowerTeeth", "lowerFaceRig",
            "tongue01", "tongue02", "tongue03", "tongue04",
            "tongue05", "tongue06", "tongueBase", "tongueTip",
        ]
        keys = rig.pose.bones.keys()
        bnames = [bname for bname in inface
                  if bname in keys and drvBone(bname) not in keys]
        bnames += getAnchoredBoneNames(rig, ["upperFaceRig", "lowerFaceRig"])
        return bnames


def getAnchoredBoneNames(rig, anchors):
    from .driver import isBoneDriven
    bnames = []
    keys = rig.pose.bones.keys()
    for anchor in anchors:
        if anchor in keys:
            for pb in rig.pose.bones:
                if (not isDrvBone(pb.name) and
                    drvBone(pb.name) not in keys and
                    pb.parent and
                    pb.parent.name == anchor):
                    bnames.append(pb.name)
    return bnames


class DAZ_OT_MakeAllBonesPoseable(DazOperator, ExtraBones, IsArmature):
    bl_idname = "daz.make_all_bones_poseable"
    bl_label = "Make All Bones Poseable"
    bl_description = "Add an extra layer of driven bones, to make them poseable"
    bl_options = {'UNDO'}

    type =  "driven"
    attr = "DazExtraDrivenBones"
    button = "Make All Bones Poseable"

    def getBoneNames(self, rig):
        from .driver import isBoneDriven
        exclude = ["lMetatarsals", "rMetatarsals"]
        return [pb.name for pb in rig.pose.bones
                if not isDrvBone(pb.name) and
                isBoneDriven(rig, pb) and
                drvBone(pb.name) not in rig.pose.bones.keys() and
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
    bl_label = "Rotation Locks"
    bl_description = "Toggle rotation locks"
    bl_options = {'UNDO'}

    attr = "DazRotLocks"
    lock = "lock_rotation"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasRotLocks)


class DAZ_OT_ToggleLocLocks(DazOperator, ToggleLocks):
    bl_idname = "daz.toggle_loc_locks"
    bl_label = "Location Locks"
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
    bl_label = "Rotation Limits"
    bl_description = "Toggle rotation limits"
    bl_options = {'UNDO'}

    type = "LIMIT_ROTATION"
    attr = "DazRotLimits"

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazHasRotLimits)


class DAZ_OT_ToggleLocLimits(DazOperator, ToggleLimits):
    bl_idname = "daz.toggle_loc_limits"
    bl_label = "Location Limits"
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

class SimpleIK:
    def __init__(self, btn=None):
        if btn:
            self.usePoleTargets = btn.usePoleTargets
            self.useIkLimits = btn.useIkLimits
        else:
            self.usePoleTargets = False
            self.useIkLimits = False


    G38Arm = ["ShldrBend", "ShldrTwist", "ForearmBend", "ForearmTwist", "Hand"]
    G38Leg = ["ThighBend", "ThighTwist", "Shin", "Foot"]
    G38Spine = ["hip", "abdomenLower", "abdomenUpper", "chestLower", "chestUpper"]
    G38Neck = ["neckLower", "neckUpper"]
    G12Arm = ["Shldr", "ForeArm", "Hand"]
    G12Leg = ["Thigh", "Shin", "Foot"]
    G12Spine = ["hip", "abdomen", "abdomen2", "spine", "chest"]
    G12Neck = ["neck"]


    def storeProps(self, rig):
        self.ikprops = (rig.data.DazArmIK_L, rig.data.DazArmIK_R, rig.data.DazLegIK_L, rig.data.DazLegIK_R)


    def setProps(self, rig, onoff):
        rig.data.DazArmIK_L = rig.data.DazArmIK_R = rig.data.DazLegIK_L = rig.data.DazLegIK_R = onoff


    def restoreProps(self, rig):
        rig.data.DazArmIK_L, rig.data.DazArmIK_R, rig.data.DazLegIK_L, rig.data.DazLegIK_R = self.ikprops


    def getIKProp(self, prefix, type):
        return ("Daz%sIK_%s" % (type, prefix.upper()))


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

        if twist:
            pb.use_ik_limit_x = True
            pb.use_ik_limit_z = True
            pb.ik_min_x = 0
            pb.ik_max_x = 0
            pb.ik_min_z = 0
            pb.ik_max_z = 0

        pb.ik_stiffness_x = stiffness[0]
        pb.ik_stiffness_y = stiffness[1]
        pb.ik_stiffness_z = stiffness[2]

        if self.useIkLimits:
            cns = getConstraint(pb, 'LIMIT_ROTATION')
            if cns:
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

#-------------------------------------------------------------
#   Add Simple IK
#-------------------------------------------------------------

class DAZ_OT_AddSimpleIK(DazPropsOperator, IsArmature):
    bl_idname = "daz.add_simple_ik"
    bl_label = "Add Simple IK"
    bl_description = "Add Simple IK constraints to the active rig"
    bl_options = {'UNDO'}

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains.\nPoses will not be loaded correctly.",
        default = False)

    useIkLimits : BoolProperty(
        name = "IK Limits",
        description = "Add rotation limits to IK bones.\nMay prevent FK-IK snapping",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "useIkLimits")


    def run(self, context):
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

        rig = context.object
        if rig.data.DazSimpleIK:
            raise DazError("The rig %s already has simple IK" % rig.name)
        if not rig.DazCustomShapes:
            raise DazError("Make custom shapes first")

        from .mhx import makeBone, getBoneCopy, ikConstraint, copyRotation, stretchTo
        IK = SimpleIK(self)
        genesis = IK.getGenesisType(rig)
        if not genesis:
            raise DazError("Cannot create simple IK for the rig %s" % rig.name)

        rig.data.DazSimpleIK = True
        rig.data.DazArmIK_L = rig.data.DazArmIK_R = rig.data.DazLegIK_L = rig.data.DazLegIK_R = 0.0

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
            copyRotation(hand, handIK, rig, prop=armProp, space='WORLD')
            handIK.custom_shape = hand.custom_shape
            handIK.custom_shape_scale = 1.8
            handIK.bone_group = bgrp
            addToLayer(handIK, "IK Arm")

            legProp = "DazLegIK_" + suffix
            foot = rpbs[prefix+"Foot"]
            driveConstraint(foot, 'LIMIT_ROTATION', rig, legProp, "1-x")
            footIK = getBoneCopy(prefix+"FootIK", foot, rpbs)
            copyRotation(foot, footIK, rig, prop=legProp, space='WORLD')
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

#----------------------------------------------------------
#   Connect bones in IK chains
#----------------------------------------------------------

class DAZ_OT_ConnectIKChains(DazPropsOperator, SimpleIK, IsArmature):
    bl_idname = "daz.connect_ik_chains"
    bl_label = "Connect IK Chains"
    bl_description = "Connect all bones in IK chains to their parents"
    bl_options = {'UNDO'}

    type : EnumProperty(
        items = [('ARMS', "Arms Only", "Connect arms only"),
                 ('LEGS', "Legs Only", "Connect legs only"),
                 ('ARMSLEGS', "Arms And Legs", "Connect both arms and legs"),
                 ('SELECTED', "Selected", "Connect selected bones")],
        name = "Chain Types",
        description = "Connect the specified types of chains",
        default = 'ARMSLEGS')

    unlock : BoolProperty(
        name = "Unlock Last Bone",
        description = "Remove location locks of the last bone in each chain for use as Auto IK target",
        default = True)

    location : EnumProperty(
        items = [('HEAD', "Child Head", "Connect at the head of the child bone"),
                 ('TAIL', "Parent Tail", "Connect at the tail of the parent bone"),
                 ('CENTER', "Center", "Connect at the midpoint between the parent tail and child head")],
        name = "Location",
        description = "Where to connect parent and child bones",
        default = 'HEAD')

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
        rig = context.object
        LS.customShapes = []
        IK = SimpleIK()
        coll = context.collection

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
                self.makeSpine(pb, 2*spineWidth)
                pb.bone_group = bgrp
                addToLayer(pb, "Spine")
            elif pb.name == "pelvis":
                self.makeSpine(pb, 1.5*spineWidth, 0.5)
                addToLayer(pb, "Spine")
            elif pb.name in IK.G38Spine + IK.G12Spine:
                self.makeSpine(pb, spineWidth)
                addToLayer(pb, "Spine")
            elif pb.name in IK.G38Neck + IK.G12Neck:
                self.makeSpine(pb, 0.5*spineWidth)
                addToLayer(pb, "Spine")
            elif pb.name == "head":
                self.makeSpine(pb, 0.7*spineWidth, 1)
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

        self.hideCustomShapes(rig, context, coll)
        rig.DazCustomShapes = True
        rig.data.layers = 16*[False] + 14*[True] + 2*[False]


    def hideCustomShapes(self, rig, context, coll):
        hidden = createHiddenCollection(context, coll)
        empty = bpy.data.objects.new("Custom Shapes", None)
        hidden.objects.link(empty)
        empty.parent = rig
        putOnHiddenLayer(empty)
        for ob in LS.customShapes:
            hidden.objects.link(ob)
            ob.parent = empty
            putOnHiddenLayer(ob)


    def makeSpine(self, pb, width, tail=0.5):
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

class DAZ_OT_SnapSimpleFK(DazOperator, SimpleIK):
    bl_idname = "daz.snap_simple_fk"
    bl_label = "Snap FK"
    bl_description = "Snap FK bones to IK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()

    def run(self, context):
        rig = context.object
        bnames = self.getLimbBoneNames(rig, self.prefix, self.type)
        if bnames:
            prop = self.getIKProp(self.prefix, self.type)
            self.snapSimpleFK(rig, bnames, prop)
            toggleLayer(rig, "FK", self.prefix, self.type, True)
            toggleLayer(rig, "IK", self.prefix, self.type, False)

    def snapSimpleFK(self, rig, bnames, prop):
        mats = []
        for bname in bnames:
            pb = rig.pose.bones[bname]
            mats.append((pb, pb.matrix.copy()))
        setattr(rig.data, prop, False)
        for pb,mat in mats:
            pb.matrix = mat

#----------------------------------------------------------
#   IK Snap
#----------------------------------------------------------

class DAZ_OT_SnapSimpleIK(DazOperator, SimpleIK):
    bl_idname = "daz.snap_simple_ik"
    bl_label = "Snap IK"
    bl_description = "Snap IK bones to FK bones"
    bl_options = {'UNDO'}

    prefix : StringProperty()
    type : StringProperty()

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
    setattr(rig.data, prop, True)
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
        for trg in getSelectedObjects(context):
            if trg.type == src.type and trg != src:
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
    DAZ_OT_MakeAllBonesPoseable,
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

def register():
    bpy.types.Object.DazCustomShapes = BoolProperty(default=False)
    bpy.types.Armature.DazSimpleIK = BoolProperty(default=False)
    bpy.types.Armature.DazArmIK_L = FloatProperty(name="Left Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Armature.DazArmIK_R = FloatProperty(name="Right Arm IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Armature.DazLegIK_L = FloatProperty(name="Left Leg IK", default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Armature.DazLegIK_R = FloatProperty(name="Right Leg IK", default=0.0, precision=3, min=0.0, max=1.0)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
