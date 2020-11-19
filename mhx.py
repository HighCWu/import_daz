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
from bpy.props import *
import math
import os
from mathutils import *
from .error import *
from .utils import *
from .globvars import NewFaceLayer

#-------------------------------------------------------------
#   Bone layers
#-------------------------------------------------------------

L_MAIN =    0
L_SPINE = 1

L_LARMIK =  2
L_LARMFK =  3
L_LLEGIK =  4
L_LLEGFK =  5
L_LHAND = 6
L_LFINGER = 7
L_LEXTRA =  12
L_LTOE = 13

L_RARMIK =  18
L_RARMFK =  19
L_RLEGIK =  20
L_RLEGFK =  21
L_RHAND = 22
L_RFINGER = 23
L_REXTRA =  28
L_RTOE = 29

L_FACE =   8
L_TWEAK =   9
L_HEAD =    10
L_CLOTHES = 16

L_HELP =    14
L_HELP2 =   15
L_DEF =     31


def fkLayers():
    return [L_MAIN, L_SPINE, L_HEAD,
            L_LARMFK, L_LLEGFK, L_LHAND, L_LFINGER,
            L_RARMFK, L_RLEGFK, L_RHAND, L_RFINGER]

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def setLayer(bname, rig, layer):
    eb = rig.data.edit_bones[bname]
    eb.layers = layer*[False] + [True] + (31-layer)*[False]
    return eb


def getBoneCopy(bname, model, rpbs):
    pb = rpbs[bname]
    pb.DazRotMode = model.DazRotMode
    pb.rotation_mode = model.rotation_mode
    return pb


def deriveBone(bname, eb0, rig, layer, parent):
    return makeBone(bname, rig, eb0.head, eb0.tail, eb0.roll, layer, parent)


def makeBone(bname, rig, head, tail, roll, layer, parent):
    eb = rig.data.edit_bones.new(bname)
    eb.head = head
    eb.tail = tail
    eb.roll = normalizeRoll(roll)
    eb.use_connect = False
    eb.parent = parent
    eb.use_deform = False
    eb.layers = layer*[False] + [True] + (31-layer)*[False]
    return eb


def normalizeRoll(roll):
    if roll > 180*D:
        return roll - 360*D
    elif roll < -180*D:
        return roll + 360*D
    else:
        return roll

#-------------------------------------------------------------
#   Constraints
#-------------------------------------------------------------

def copyTransform(bone, boneFk, boneIk, rig, prop=None, expr="x"):
    if boneFk is not None:
        cnsFk = bone.constraints.new('COPY_TRANSFORMS')
        cnsFk.name = "FK"
        cnsFk.target = rig
        cnsFk.subtarget = boneFk.name
        cnsFk.influence = 1.0

    if boneIk is not None:
        cnsIk = bone.constraints.new('COPY_TRANSFORMS')
        cnsIk.name = "IK"
        cnsIk.target = rig
        cnsIk.subtarget = boneIk.name
        cnsIk.influence = 0.0
        if prop is not None:
            addDriver(cnsIk, "influence", rig, prop, expr)


def copyLocation(bone, target, rig, prop=None, expr="x"):
    cns = bone.constraints.new('COPY_LOCATION')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def copyRotation(bone, target, use, rig, prop=None, expr="x", space='LOCAL'):
    cns = bone.constraints.new('COPY_ROTATION')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.use_x,cns.use_y,cns.use_z = use
    cns.owner_space = space
    cns.target_space = space
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def copyScale(bone, target, use, rig, prop=None, expr="x"):
    cns = bone.constraints.new('COPY_SCALE')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.use_x,cns.use_y,cns.use_z = use
    cns.owner_space = 'LOCAL'
    cns.target_space = 'LOCAL'
    if prop is not None:
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def hintRotation(bone):
    pos = (18*D,0,0)
    neg = (-18*D,0,0)
    hints = {
        "forearm.ik.L" : pos,
        "forearm.ik.R" : pos,
        "shin.ik.L" : pos,
        "shin.ik.R" : pos,
        }
    hint = hints[bone.name]
    limitRotation(bone, hint, hint, (True,False,False))


def limitRotation(bone, min, max, use):
    cns = bone.constraints.new('LIMIT_ROTATION')
    cns.name = "Hint"
    cns.min_x, cns.min_y, cns.min_z = min
    cns.max_x, cns.max_y, cns.max_z = max
    cns.use_limit_x, cns.use_limit_y, cns.use_limit_z = use
    cns.owner_space = 'LOCAL'
    return cns


def ikConstraint(last, target, pole, angle, count, rig, prop=None, expr="x"):
    cns = last.constraints.new('IK')
    cns.name = "IK"
    cns.target = rig
    cns.subtarget = target.name
    if pole:
        cns.pole_target = rig
        cns.pole_subtarget = pole.name
        cns.pole_angle = angle*D
    cns.chain_count = count
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def stretchTo(pb, target, rig):
    cns = pb.constraints.new('STRETCH_TO')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    #pb.bone.hide_select = True
    return cns


def trackTo(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('TRACK_TO')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    cns.track_axis = 'TRACK_Y'
    cns.up_axis = 'UP_X'
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def childOf(pb, target, rig, prop=None, expr="x"):
    cns = pb.constraints.new('CHILD_OF')
    #cns.name = target.name
    cns.target = rig
    cns.subtarget = target.name
    if prop is not None:
        cns.influence = 0.0
        addDriver(cns, "influence", rig, prop, expr)
    return cns


def addDriver(rna, channel, rig, prop, expr):
    from .driver import addDriverVar
    fcu = rna.driver_add(channel)
    fcu.driver.type = 'SCRIPTED'
    if isinstance(prop, str):
        fcu.driver.expression = expr
        addDriverVar(fcu, "x", prop, rig)
    else:
        prop1,prop2 = prop
        fcu.driver.expression = expr
        addDriverVar(fcu, "x1", prop1, rig)
        addDriverVar(fcu, "x2", prop2, rig)


def getPropString(prop, x):
    if isinstance(prop, tuple):
        return prop[1], ("(1-%s)" % (x))
    else:
        return prop, x

#-------------------------------------------------------------
#   Bone children
#-------------------------------------------------------------

def unhideAllObjects(context, rig):
    for key in rig.keys():
        if key[0:3] == "Mhh":
            rig[key] = True
    updateScene(context)


def applyBoneChildren(context, rig):
    from .node import clearParent
    unhideAllObjects(context, rig)
    bchildren = []
    for ob in rig.children:
        if ob.parent_type == 'BONE':
            bchildren.append((ob, ob.parent_bone))
            clearParent(ob)
    return bchildren

#-------------------------------------------------------------
#   Convert to MHX button
#-------------------------------------------------------------

from .fix import ConstraintStore, BendTwists, Fixer

class DAZ_OT_ConvertToMhx(DazPropsOperator, ConstraintStore, BendTwists, Fixer, B.MHX, IsArmature):
    bl_idname = "daz.convert_mhx"
    bl_label = "Convert To MHX"
    bl_description = "Convert rig to MHX"
    bl_options = {'UNDO'}

    BendTwists = [
        ("thigh.L", "shin.L"),
        ("forearm.L", "hand.L"),
        ("upper_arm.L", "forearm.L"),
        ("thigh.R", "shin.R"),
        ("forearm.R", "hand.R"),
        ("upper_arm.R", "forearm.R"),
        ]

    Knees = [
        ("thigh.L", "shin.L", Vector((0,-1,0))),
        ("thigh.R", "shin.R", Vector((0,-1,0))),
        ("upper_arm.L", "forearm.L", Vector((0,1,0))),
        ("upper_arm.R", "forearm.R", Vector((0,1,0))),
    ]

    Correctives = [
        ("upper_arm-1.L", "upper_armBend.L"),
        ("forearm-1.L", "forearmBend.L"),
        ("thigh-1.L", "thighBend.L"),
        ("upper_arm-1.R", "upper_armBend.R"),
        ("forearm-1.R", "forearmBend.R"),
        ("thigh-1.R", "thighBend.R"),
    ]

    BreastBones = [
        ("breast.L", "lPectoral", L_LEXTRA),
        ("breast.R", "rPectoral", L_REXTRA),
    ]

    DrivenParents = {
        "lowerFaceRig" :    "lowerJaw",
        "lowerTeethDrv" :   "lowerJaw",
        "tongue01Drv" :     "lowerTeeth",
    }

    LegacyNames = {
        "hip" : "root",
        "pelvis" : "hips"
    }

    def draw(self, context):
        self.layout.prop(self, "addTweakBones")
        self.layout.prop(self, "useLegacy")


    def run(self, context):
        from .merge import reparentToes
        rig = context.object
        scn = context.scene
        gen2 = None
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'ARMATURE' and ob != rig:
                gen2 = ob
                break

        #-------------------------------------------------------------
        #   Legacy bone names
        #-------------------------------------------------------------

        if self.useLegacy:
            self.hip = "root"
            self.pelvis = "hips"
        else:
            self.hip = "hip"
            self.pelvis = "pelvis"
            rig.DazMhxLegacy = False

        #-------------------------------------------------------------
        #   MHX skeleton
        #   (mhx, genesis, layer)
        #-------------------------------------------------------------

        self.skeleton = [
            (self.hip, "hip", L_MAIN),
            (self.pelvis, "pelvis", L_SPINE),

            ("thigh.L", "lThigh", L_LLEGFK),
            ("thighBend.L", "lThighBend", L_LLEGFK),
            ("thighTwist.L", "lThighTwist", L_LLEGFK),
            ("shin.L", "lShin", L_LLEGFK),
            ("foot.L", "lFoot", L_LLEGFK),
            ("toe.L", "lToe", L_LLEGFK),
            ("heel.L", "lHeel", L_HELP),
            ("tarsal.L", "lMetatarsals", L_HELP),

            ("thigh.R", "rThigh", L_RLEGFK),
            ("thighBend.R", "rThighBend", L_RLEGFK),
            ("thighTwist.R", "rThighTwist", L_RLEGFK),
            ("shin.R", "rShin", L_RLEGFK),
            ("foot.R", "rFoot", L_RLEGFK),
            ("toe.R", "rToe", L_RLEGFK),
            ("heel.R", "rHeel", L_HELP),
            ("tarsal.R", "rMetatarsals", L_HELP),

            ("spine", "abdomenLower", L_SPINE),
            ("spine", "abdomen", L_SPINE),
            ("spine-1", "abdomenUpper", L_SPINE),
            ("spine-1", "abdomen2", L_SPINE),
            ("chest", "chest", L_SPINE),
            ("chest", "chestLower", L_SPINE),
            ("chest-1", "chestUpper", L_SPINE),
            ("neck", "neck", L_SPINE),
            ("neck", "neckLower", L_SPINE),
            ("neck-1", "neckUpper", L_SPINE),
            ("head", "head", L_SPINE),

            ("lEye", "lEye", L_FACE),
            ("rEye", "rEye", L_FACE),
            ("upperJaw", "upperJaw", L_FACE),
            ("lowerJaw", "lowerJaw", L_FACE),

            ("clavicle.L", "lCollar", L_LARMFK),
            ("upper_arm.L", "lShldr", L_LARMFK),
            ("upper_armBend.L", "lShldrBend", L_LARMFK),
            ("upper_armTwist.L", "lShldrTwist", L_LARMFK),
            ("forearm.L", "lForeArm", L_LARMFK),
            ("forearmBend.L", "lForearmBend", L_LARMFK),
            ("forearmTwist.L", "lForearmTwist", L_LARMFK),
            ("hand.L", "lHand", L_LARMFK),
            ("palm_index.L", "lCarpal1", L_LFINGER),
            ("palm_middle.L", "lCarpal2", L_LFINGER),
            ("palm_ring.L", "lCarpal3", L_LFINGER),
            ("palm_pinky.L", "lCarpal4", L_LFINGER),

            ("clavicle.R", "rCollar", L_RARMFK),
            ("upper_arm.R", "rShldr", L_RARMFK),
            ("upper_armBend.R", "rShldrBend", L_RARMFK),
            ("upper_armTwist.R", "rShldrTwist", L_RARMFK),
            ("forearm.R", "rForeArm", L_RARMFK),
            ("forearmBend.R", "rForearmBend", L_RARMFK),
            ("forearmTwist.R", "rForearmTwist", L_RARMFK),
            ("hand.R", "rHand", L_RARMFK),
            ("palm_index.R", "rCarpal1", L_RFINGER),
            ("palm_middle.R", "rCarpal2", L_RFINGER),
            ("palm_ring.R", "rCarpal3", L_RFINGER),
            ("palm_pinky.R", "rCarpal4", L_RFINGER),

            ("thumb.01.L", "lThumb1", L_LFINGER),
            ("thumb.02.L", "lThumb2", L_LFINGER),
            ("thumb.03.L", "lThumb3", L_LFINGER),
            ("f_index.01.L", "lIndex1", L_LFINGER),
            ("f_index.02.L", "lIndex2", L_LFINGER),
            ("f_index.03.L", "lIndex3", L_LFINGER),
            ("f_middle.01.L", "lMid1", L_LFINGER),
            ("f_middle.02.L", "lMid2", L_LFINGER),
            ("f_middle.03.L", "lMid3", L_LFINGER),
            ("f_ring.01.L", "lRing1", L_LFINGER),
            ("f_ring.02.L", "lRing2", L_LFINGER),
            ("f_ring.03.L", "lRing3", L_LFINGER),
            ("f_pinky.01.L", "lPinky1", L_LFINGER),
            ("f_pinky.02.L", "lPinky2", L_LFINGER),
            ("f_pinky.03.L", "lPinky3", L_LFINGER),

            ("thumb.01.R", "rThumb1", L_RFINGER),
            ("thumb.02.R", "rThumb2", L_RFINGER),
            ("thumb.03.R", "rThumb3", L_RFINGER),
            ("f_index.01.R", "rIndex1", L_RFINGER),
            ("f_index.02.R", "rIndex2", L_RFINGER),
            ("f_index.03.R", "rIndex3", L_RFINGER),
            ("f_middle.01.R", "rMid1", L_RFINGER),
            ("f_middle.02.R", "rMid2", L_RFINGER),
            ("f_middle.03.R", "rMid3", L_RFINGER),
            ("f_ring.01.R", "rRing1", L_RFINGER),
            ("f_ring.02.R", "rRing2", L_RFINGER),
            ("f_ring.03.R", "rRing3", L_RFINGER),
            ("f_pinky.01.R", "rPinky1", L_RFINGER),
            ("f_pinky.02.R", "rPinky2", L_RFINGER),
            ("f_pinky.03.R", "rPinky3", L_RFINGER),

            ("big_toe.01.L", "lBigToe", L_LTOE),
            ("small_toe_1.01.L", "lSmallToe1", L_LTOE),
            ("small_toe_2.01.L", "lSmallToe2", L_LTOE),
            ("small_toe_3.01.L", "lSmallToe3", L_LTOE),
            ("small_toe_4.01.L", "lSmallToe4", L_LTOE),
            ("big_toe.02.L", "lBigToe_2", L_LTOE),
            ("small_toe_1.02.L", "lSmallToe1_2", L_LTOE),
            ("small_toe_2.02.L", "lSmallToe2_2", L_LTOE),
            ("small_toe_3.02.L", "lSmallToe3_2", L_LTOE),
            ("small_toe_4.02.L", "lSmallToe4_2", L_LTOE),

            ("big_toe.01.R", "rBigToe", L_RTOE),
            ("small_toe_1.01.R", "rSmallToe1", L_RTOE),
            ("small_toe_2.01.R", "rSmallToe2", L_RTOE),
            ("small_toe_3.01.R", "rSmallToe3", L_RTOE),
            ("small_toe_4.01.R", "rSmallToe4", L_RTOE),
            ("big_toe.02.R", "rBigToe_2", L_RTOE),
            ("small_toe_1.02.R", "rSmallToe1_2", L_RTOE),
            ("small_toe_2.02.R", "rSmallToe2_2", L_RTOE),
            ("small_toe_3.02.R", "rSmallToe3_2", L_RTOE),
            ("small_toe_4.02.R", "rSmallToe4_2", L_RTOE),
        ]

        if rig.data.DazExtraDrivenBones:
            self.skeleton += self.BreastBones

        self.sacred = ["root", "hips", "spine"]

        #-------------------------------------------------------------
        #   Fix and rename bones of the genesis rig
        #-------------------------------------------------------------

        self.constraints = {}
        rig.data.layers = 32*[True]
        bchildren = applyBoneChildren(context, rig)
        if rig.DazRig in ["genesis3", "genesis8"]:
            connectToParent(rig)
            reparentToes(rig, context)
            self.rename2Mhx(rig)
            self.joinBendTwists(rig, {}, False)
            self.fixKnees(rig)
            self.fixHands(rig)
            self.storeAllConstraints(rig)
            self.createBendTwists(rig)
            self.fixCorrectives(rig, self.Correctives)
        elif rig.DazRig in ["genesis1", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            connectToParent(rig)
            reparentToes(rig, context)
            self.rename2Mhx(rig)
            self.fixGenesis2Problems(rig)
            self.fixKnees(rig)
            self.fixHands(rig)
            self.storeAllConstraints(rig)
            self.createBendTwists(rig)
            self.fixCorrectives(rig, self.Correctives)
        else:
            raise DazError("Cannot convert %s to Mhx" % rig.name)

        #-------------------------------------------------------------
        #   Add MHX stuff
        #-------------------------------------------------------------

        self.constrainBendTwists(rig)
        self.addLongFingers(rig)
        self.addTweaks(rig)
        self.addBack(rig)
        self.setupFkIk(rig)
        self.addLayers(rig)
        self.addMarkers(rig)
        self.addMaster(rig)
        self.addGizmos(rig, context)
        self.restoreAllConstraints(rig)
        self.fixHandConstraints(rig)
        if rig.DazRig in ["genesis3", "genesis8"]:
            self.fixCustomShape(rig, ["head"], 4)
        self.collectDeformBones(rig)
        bpy.ops.object.mode_set(mode='POSE')
        self.addBoneGroups(rig)
        rig["MhxRig"] = "MHX"
        setattr(rig.data, DrawType, 'STICK')
        T = True
        F = False
        rig.data.layers = [T,T,F,T, F,T,T,F, F,F,F,F, F,F,F,F,
                           F,F,F,T, F,T,T,F, F,F,F,F, F,F,F,F]
        rig.DazRig = "mhx"

        for pb in rig.pose.bones:
            pb.bone.select = False
            if pb.custom_shape:
                pb.bone.show_wire = True

        self.restoreBoneChildren(bchildren, context, rig)
        self.checkCorrectives(rig)
        updateScene(context)
        updateDrivers(rig)


    def fixGenesis2Problems(self, rig):
        bpy.ops.object.mode_set(mode = 'EDIT')
        rebs = rig.data.edit_bones
        for suffix in [".L", ".R"]:
            foot = rebs["foot"+suffix]
            toe = rebs["toe"+suffix]
            heel = rebs.new("heel"+suffix)
            heel.parent = foot.parent
            heel.head = foot.head
            heel.tail = (toe.head[0], 1.5*foot.head[1]-0.5*toe.head[1], toe.head[2])
            heel.layers = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]

    #-------------------------------------------------------------
    #   Rename bones
    #-------------------------------------------------------------

    def rename2Mhx(self, rig):
        from .driver import isBoneDriven
        fixed = []
        faceLayer = L_FACE*[False] + [True] + (31-L_FACE)*[False]
        clothesLayer = L_CLOTHES*[False] + [True] + (31-L_CLOTHES)*[False]
        helpLayer = L_HELP*[False] + [True] + (31-L_HELP)*[False]
        deformLayer = 31*[False] + [True]

        bpy.ops.object.mode_set(mode='EDIT')
        for bname,pname in self.DrivenParents.items():
            if (bname in rig.data.edit_bones.keys() and
                pname in rig.data.edit_bones.keys()):
                eb = rig.data.edit_bones[bname]
                parb = rig.data.edit_bones[pname]
                eb.parent = parb
                eb.layers = helpLayer
                fixed.append(bname)

        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in rig.data.bones:
            if bone.name in self.sacred:
                bone.name = bone.name + ".1"

        for mname,dname,layer in self.skeleton:
            if dname in rig.data.bones.keys():
                bone = rig.data.bones[dname]
                if dname != mname:
                    bone.name = mname
                bone.layers = layer*[False] + [True] + (31-layer)*[False]
                fixed.append(mname)

        for pb in rig.pose.bones:
            bname = pb.name
            lname = bname.lower()
            if bname in fixed:
                pass
            elif bname[-3:] == "Drv" or isBoneDriven(rig, pb):
                pb.bone.layers = helpLayer
            elif (pb.parent and
                  pb.parent.name[-3:] == "Drv"):
                pb.bone.layers = faceLayer
                pb.lock_location = (False,False,False)
            elif ("tongue" in lname):
                pb.bone.layers = faceLayer
            elif not (pb.bone.layers[L_LEXTRA] or pb.bone.layers[L_REXTRA]):
                mname = bname[0].lower() + bname[1:]
                if len(bname) > 1 and bname[1].isupper():
                    if bname[0] == "l":
                        mname = bname[1].lower() + bname[2:] + ".L"
                    elif bname[0] == "r":
                        mname = bname[1].lower() + bname[2:] + ".R"
                if pb.bone.layers[NewFaceLayer-1]:
                    pb.bone.layers = faceLayer
                else:
                    pb.bone.layers = clothesLayer
                pb.lock_location = (False,False,False)


    def restoreBoneChildren(self, bchildren, context, rig):
        from .node import setParent
        layers = list(rig.data.layers)
        rig.data.layers = 32*[True]
        for (ob, bname) in bchildren:
            bone = self.getMhxBone(rig, bname)
            if bone:
                setParent(context, ob, rig, bone.name)
            else:
                print("Could not restore bone parent for %s", ob.name)
        rig.data.layers = layers


    def getMhxBone(self, rig, bname):
        if bname in rig.data.bones.keys():
            return rig.data.bones[bname]
        for mname,dname,_ in self.skeleton:
            if dname == bname:
                if mname[-2] == ".":
                    if mname[-6:-2] == "Bend":
                        mname = mname[:-6] + "-1" + mname[-2:]
                    elif mname[-7:-2] == "Twist":
                        mname = mname[:-7] + "-2" + mname[-2:]
                if mname in rig.data.bones.keys():
                    return rig.data.bones[mname]
                else:
                    print("Missing MHX bone:", bname, mname)
        return None

    #-------------------------------------------------------------
    #   Gizmos
    #-------------------------------------------------------------

    def addGizmos(self, rig, context):
        hidden = createHiddenCollection(context, None)
        bpy.ops.object.mode_set(mode='OBJECT')
        empty = bpy.data.objects.new("Gizmos", None)
        hidden.objects.link(empty)
        empty.parent = rig
        putOnHiddenLayer(empty)
        self.gizmos = makeGizmos(None, empty, hidden)
        for pb in rig.pose.bones:
            if pb.name in Gizmos.keys():
                self.addGizmo(pb, Gizmos[pb.name])
            else:
                for pname in ["thumb", "f_index", "f_ring", "f_middle", "f_pinky",
                              "big_toe", "small_toe"]:
                    if pname in pb.name.lower():
                        self.addGizmo(pb, "GZM_Circle025", blen=3*rig.DazScale)
                if pb.name[0:4] == "palm":
                    self.addGizmo(pb, "GZM_Ellipse")
            if pb.name in self.tweakBones:
                gizmo = "GZM_Ball025"
                if pb.name == self.pelvis:
                    gizmo = "GZM_Ball025End"
                tb = rig.pose.bones[self.getTweakBoneName(pb.name)]
                self.addGizmo(tb, gizmo, blen=10*rig.DazScale)


    def addGizmo(self, pb, gname, blen=None):
        gizmo = self.gizmos[gname]
        pb.custom_shape = gizmo
        pb.bone.show_wire = True
        if blen:
            pb.custom_shape_scale = blen/pb.bone.length

    #-------------------------------------------------------------
    #   Bone groups
    #-------------------------------------------------------------

    def addBoneGroups(self, rig):
        boneGroups = [
            ('Spine', 'THEME01', L_SPINE),
            ('ArmFK.L', 'THEME02', L_LARMFK),
            ('ArmFK.R', 'THEME03', L_RARMFK),
            ('ArmIK.L', 'THEME04', L_LARMIK),
            ('ArmIK.R', 'THEME05', L_RARMIK),
            ('LegFK.L', 'THEME06', L_LLEGFK),
            ('LegFK.R', 'THEME07', L_RLEGFK),
            ('LegIK.L', 'THEME14', L_LLEGIK),
            ('LegIK.R', 'THEME09', L_RLEGIK),
            ]

        for bgname,theme,layer in boneGroups:
            bpy.ops.pose.group_add()
            bgrp = rig.pose.bone_groups.active
            bgrp.name = bgname
            bgrp.color_set = theme
            for pb in rig.pose.bones.values():
                if pb.bone.layers[layer]:
                    pb.bone_group = bgrp

    #-------------------------------------------------------------
    #   Backbone
    #-------------------------------------------------------------

    BackBones = ["spine", "spine-1", "chest", "chest-1"]

    def addBack(self, rig):
        bpy.ops.object.mode_set(mode='EDIT')
        spine = rig.data.edit_bones["spine"]
        chest = rig.data.edit_bones["chest"]
        makeBone("back", rig, spine.head, chest.tail, 0, L_MAIN, spine.parent)

        bpy.ops.object.mode_set(mode='POSE')
        back = rig.pose.bones["back"]
        back.rotation_mode = 'YZX'
        for bname in self.BackBones:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                cns = copyRotation(pb, back, (True,True,True), rig)
                cns.use_offset = True

    #-------------------------------------------------------------
    #   Spine tweaks
    #-------------------------------------------------------------

    def addTweaks(self, rig):
        if not self.addTweakBones:
            self.tweakBones = []
            return

        self.tweakBones = [
            None, "spine", "spine-1", "chest", "chest-1",
            None, "neck", "neck-1",
            None, self.pelvis,
            None, "forearm.L", None, "shin.L",
            None, "forearm.R", None, "shin.R"]

        self.noTweakParents = [
            "spine", "spine-1", "chest", "chest-1", "neck", "neck-1", "head",
            "clavicle.L", "hand.L", "thigh.L", "shin.L", "foot.L",
            "clavicle.R", "hand.R", "thigh.R", "shin.R", "foot.R",
        ]

        bpy.ops.object.mode_set(mode='EDIT')
        tweakLayers = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]
        for bname in self.tweakBones:
            if bname is None:
                sb = None
            elif bname in rig.data.edit_bones.keys():
                tb = rig.data.edit_bones[bname]
                tb.name = self.getTweakBoneName(bname)
                conn = tb.use_connect
                tb.use_connect = False
                tb.layers = tweakLayers
                if sb is None:
                    sb = tb.parent
                sb = deriveBone(bname, tb, rig, L_SPINE, sb)
                sb.use_connect = conn
                tb.parent = sb
                for eb in tb.children:
                    if eb.name in self.noTweakParents:
                        eb.parent = sb

        from .figure import copyBoneInfo
        bpy.ops.object.mode_set(mode='POSE')
        rpbs = rig.pose.bones
        tweakCorrectives = []
        for bname in self.tweakBones:
            if bname and bname in rpbs.keys():
                tname = self.getTweakBoneName(bname)
                tweakCorrectives.append((bname, tname))
                tb = rpbs[tname]
                pb = getBoneCopy(bname, tb, rpbs)
                copyBoneInfo(tb, pb)
                tb.lock_location = tb.lock_rotation = tb.lock_scale = (False,False,False)

        bpy.ops.object.mode_set(mode='OBJECT')
        self.fixCorrectives(rig, tweakCorrectives)


    def getTweakBoneName(self, bname):
        if bname[-2] == ".":
            return bname[:-2] + "Twk" + bname[-2:]
        else:
            return bname + "Twk"

    #-------------------------------------------------------------
    #   Fingers
    #-------------------------------------------------------------

    FingerNames = ["thumb", "index", "middle", "ring", "pinky"]
    PalmNames = ["thumb", "index", "index", "middle", "middle"]

    def linkName(self, m, n, suffix):
        if m == 0:
            fname = "thumb"
        else:
            fname = "f_" + self.FingerNames[m]
        return ("%s.0%d%s" % (fname, n+1, suffix))


    def longName(self, m, suffix):
        return ("%s%s" % (self.FingerNames[m], suffix))


    def palmName(self, m, suffix):
        return ("palm_%s%s" % (self.PalmNames[m], suffix))


    def addLongFingers(self, rig):
        for suffix,dlayer in [(".L",0), (".R",16)]:
            prop = "MhaFingerControl_" + suffix[1]
            setattr(rig, prop, 1.0)

            bpy.ops.object.mode_set(mode='EDIT')
            for m in range(5):
                if m == 0:
                    fing1 = rig.data.edit_bones[self.linkName(0, 1, suffix)]
                    palm = rig.data.edit_bones[self.linkName(0, 0, suffix)]
                else:
                    fing1 = rig.data.edit_bones[self.linkName(m, 0, suffix)]
                    palm = rig.data.edit_bones[self.palmName(m, suffix)]
                fing3 = rig.data.edit_bones[self.linkName(m, 2, suffix)]
                makeBone(self.longName(m, suffix), rig, fing1.head, fing3.tail, fing1.roll, L_LHAND+dlayer, palm)

            bpy.ops.object.mode_set(mode='POSE')
            thumb1 = rig.data.bones[self.linkName(0, 0, suffix)]
            thumb1.layers[L_LHAND+dlayer] = True
            for m in range(5):
                if m == 0:
                    n0 = 1
                else:
                    n0 = 0
                long = rig.pose.bones[self.longName(m, suffix)]
                long.lock_location = (True,True,True)
                long.lock_rotation = (False,True,False)
                fing = rig.pose.bones[self.linkName(m, n0, suffix)]
                fing.lock_rotation = (False,True,False)
                long.rotation_mode = fing.rotation_mode
                cns = copyRotation(fing, long, (True,False,True), rig, prop)
                cns.use_offset = True
                for n in range(n0+1,3):
                    fing = rig.pose.bones[self.linkName(m, n, suffix)]
                    fing.lock_rotation = (False,True,True)
                    cns = copyRotation(fing, long, (True,False,False), rig, prop)
                    cns.use_offset = True

    #-------------------------------------------------------------
    #   FK/IK
    #-------------------------------------------------------------

    FkIk = {
        ("thigh.L", "shin.L", "foot.L"),
        ("upper_arm.L", "forearm.L", "toe.L"),
        ("thigh.R", "shin.R", "foot.R"),
        ("upper_arm.R", "forearm.R", "toe.R"),
    }

    def setupFkIk(self, rig):
        bpy.ops.object.mode_set(mode='EDIT')
        root = rig.data.edit_bones[self.hip]
        head = rig.data.edit_bones["head"]
        for suffix,dlayer in [(".L",0), (".R",16)]:
            upper_arm = setLayer("upper_arm"+suffix, rig, L_HELP)
            forearm = setLayer("forearm"+suffix, rig, L_HELP)
            hand0 = setLayer("hand"+suffix, rig, L_DEF)
            hand0.name = "hand0"+suffix
            vec = forearm.tail - forearm.head
            vec.normalize()
            tail = hand0.head + vec*hand0.length
            roll = normalizeRoll(forearm.roll + 90*D)
            if abs(roll - hand0.roll) > 180*D:
                roll = normalizeRoll(roll + 180*D)
            hand = makeBone("hand"+suffix, rig, hand0.head, tail, roll, L_HELP, forearm)
            handconn = hand0.use_connect
            hand0.use_connect = False
            hand0.parent = hand

            size = 10*rig.DazScale
            armSocket = makeBone("shoulderTwk"+suffix, rig, upper_arm.head, upper_arm.head+Vector((0,0,size)), 0, L_TWEAK, upper_arm.parent)
            armParent = deriveBone("arm_parent"+suffix, armSocket, rig, L_HELP, root)
            upper_arm.parent = armParent
            rig.data.edit_bones["upper_arm-1"+suffix].parent = armParent

            upper_armFk = deriveBone("upper_arm.fk"+suffix, upper_arm, rig, L_LARMFK+dlayer, armParent)
            forearmFk = deriveBone("forearm.fk"+suffix, forearm, rig, L_LARMFK+dlayer, upper_armFk)
            forearmFk.use_connect = forearm.use_connect
            handFk = deriveBone("hand.fk"+suffix, hand, rig, L_LARMFK+dlayer, forearmFk)
            handFk.use_connect = handconn
            upper_armIk = deriveBone("upper_arm.ik"+suffix, upper_arm, rig, L_HELP2, armParent)
            forearmIk = deriveBone("forearm.ik"+suffix, forearm, rig, L_HELP2, upper_armIk)
            forearmIk.use_connect = forearm.use_connect
            handIk = deriveBone("hand.ik"+suffix, hand, rig, L_LARMIK+dlayer, None)
            hand0Ik = deriveBone("hand0.ik"+suffix, hand, rig, L_HELP2, forearmIk)

            size = 5*rig.DazScale
            vec = upper_arm.matrix.to_3x3().col[2]
            vec.normalize()
            locElbowPt = forearm.head - 15*rig.DazScale*vec
            elbowPt = makeBone("elbow.pt.ik"+suffix, rig, locElbowPt, locElbowPt+Vector((0,0,size)), 0, L_LARMIK+dlayer, upper_arm.parent)
            elbowLink = makeBone("elbow.link"+suffix, rig, forearm.head, locElbowPt, 0, L_LARMIK+dlayer, upper_armIk)
            elbowLink.hide_select = True

            thigh = setLayer("thigh"+suffix, rig, L_HELP)
            shin = setLayer("shin"+suffix, rig, L_HELP)
            foot = setLayer("foot"+suffix, rig, L_HELP)
            toe = setLayer("toe"+suffix, rig, L_HELP)
            foot.tail = toe.head

            size = 10*rig.DazScale
            legSocket = makeBone("thighTwk"+suffix, rig, thigh.head, thigh.head+Vector((0,0,size)), 0, L_TWEAK, thigh.parent)
            legParent = deriveBone("leg_parent"+suffix, legSocket, rig, L_HELP, root)
            thigh.parent = legParent
            rig.data.edit_bones["thigh-1"+suffix].parent = legParent

            thighFk = deriveBone("thigh.fk"+suffix, thigh, rig, L_LLEGFK+dlayer, thigh.parent)
            shinFk = deriveBone("shin.fk"+suffix, shin, rig, L_LLEGFK+dlayer, thighFk)
            shinFk.use_connect = shin.use_connect
            footFk = deriveBone("foot.fk"+suffix, foot, rig, L_LLEGFK+dlayer, shinFk)
            footFk.use_connect = foot.use_connect
            footFk.layers[L_LEXTRA+dlayer] = True
            toeFk = deriveBone("toe.fk"+suffix, toe, rig, L_LLEGFK+dlayer, footFk)
            toeFk.layers[L_LEXTRA+dlayer] = True
            thighIk = deriveBone("thigh.ik"+suffix, thigh, rig, L_HELP2, thigh.parent)
            shinIk = deriveBone("shin.ik"+suffix, shin, rig, L_HELP2, thighIk)
            shinIk.use_connect = shin.use_connect

            if "heel"+suffix in rig.data.edit_bones.keys():
                heel = rig.data.edit_bones["heel"+suffix]
                locFootIk = (foot.head[0], heel.tail[1], toe.tail[2])
            else:
                locFootIk = (foot.head[0], foot.head[1], toe.tail[2])
            footIk = makeBone("foot.ik"+suffix, rig, locFootIk, toe.tail, 0, L_LLEGIK+dlayer, None)
            toeRev = makeBone("toe.rev"+suffix, rig, toe.tail, toe.head, 0, L_LLEGIK+dlayer, footIk)
            footRev = makeBone("foot.rev"+suffix, rig, toe.head, foot.head, 0, L_LLEGIK+dlayer, toeRev)
            locAnkle = foot.head + Vector((0,size,0))
            ankle = makeBone("ankle"+suffix, rig, foot.head, locAnkle, 0, L_LEXTRA+dlayer, None)
            ankleIk = makeBone("ankle.ik"+suffix, rig, foot.head, locAnkle, 0, L_HELP2, footRev)

            vec = thigh.matrix.to_3x3().col[2]
            vec.normalize()
            locKneePt = shin.head - 15*rig.DazScale*vec
            kneePt = makeBone("knee.pt.ik"+suffix, rig, locKneePt, locKneePt+Vector((0,0,size)), 0, L_LLEGIK+dlayer, ankleIk)
            kneePt.layers[L_LEXTRA+dlayer] = True
            kneeLink = makeBone("knee.link"+suffix, rig, shin.head, locKneePt, 0, L_LLEGIK+dlayer, thighIk)
            kneeLink.layers[L_LEXTRA+dlayer] = True
            kneeLink.hide_select = True

            footInv = deriveBone("foot.inv.ik"+suffix, foot, rig, L_HELP2, footRev)
            toeInv = deriveBone("toe.inv.ik"+suffix, toe, rig, L_HELP2, toeRev)

            prefix = suffix[1].lower()
            eye = rig.data.edit_bones[prefix + "Eye"]
            vec = eye.tail-eye.head
            vec.normalize()
            loc = eye.head + vec*rig.DazScale*30
            gaze = makeBone("gaze"+suffix, rig, loc, loc+Vector((0,5*rig.DazScale,0)), 0, L_HEAD, None)

        lgaze = rig.data.edit_bones["gaze.L"]
        rgaze = rig.data.edit_bones["gaze.R"]
        loc = (lgaze.head + rgaze.head)/2
        gaze0 = makeBone("gaze0", rig, loc, loc+Vector((0,15*rig.DazScale,0)), 0, L_HELP, head)
        gaze1 = deriveBone("gaze1", gaze0, rig, L_HELP, None)
        gaze = deriveBone("gaze", gaze0, rig, L_HEAD, gaze1)
        lgaze.parent = gaze
        rgaze.parent = gaze

        from .figure import copyBoneInfo
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')
        for suffix in [".L", ".R"]:
            for bname in ["upper_arm", "forearm", "hand",
                          "thigh", "shin", "foot", "toe"]:
                bone = rig.pose.bones[bname+suffix]
                fkbone = rig.pose.bones[bname+".fk"+suffix]
                copyBoneInfo(bone, fkbone)

        rpbs = rig.pose.bones
        for bname in [self.hip, self.pelvis]:
            pb = rpbs[bname]
            pb.rotation_mode = 'YZX'

        rotmodes = {
            'YZX': ["shin", "shin.fk", "shin.ik",
                    "forearm", "forearm.fk", "forearm.ik",
                    "foot", "foot.fk", "toe", "toe.fk",
                    "foot.rev", "toe.rev",
                    "breast",
                   ],
            'YXZ' : ["hand", "hand.fk", "hand.ik"],
        }
        for suffix in [".L", ".R"]:
            for rmode,bnames in rotmodes.items():
                for bname in bnames:
                    if bname+suffix in rpbs.keys():
                        pb = rpbs[bname+suffix]
                        pb.rotation_mode = rmode

            armSocket = rpbs["shoulderTwk"+suffix]
            armParent = rpbs["arm_parent"+suffix]
            upper_arm = rpbs["upper_arm"+suffix]
            forearm = rpbs["forearm"+suffix]
            hand = rpbs["hand"+suffix]
            upper_armFk = getBoneCopy("upper_arm.fk"+suffix, upper_arm, rpbs)
            forearmFk = getBoneCopy("forearm.fk"+suffix, forearm, rpbs)
            handFk = getBoneCopy("hand.fk"+suffix, hand, rpbs)
            upper_armIk = rpbs["upper_arm.ik"+suffix]
            forearmIk = rpbs["forearm.ik"+suffix]
            handIk = rpbs["hand.ik"+suffix]
            hand0Ik = rpbs["hand0.ik"+suffix]
            elbowPt = rpbs["elbow.pt.ik"+suffix]
            elbowLink = rpbs["elbow.link"+suffix]

            prop = "MhaArmHinge_" + suffix[1]
            setattr(rig, prop, 0.0)
            copyTransform(armParent, None, armSocket, rig, prop, "1-x")
            copyLocation(armParent, armSocket, rig, prop, "x")

            prop = "MhaArmIk_"+suffix[1]
            setattr(rig, prop, 0.0)
            copyTransform(upper_arm, upper_armFk, upper_armIk, rig, prop)
            copyTransform(forearm, forearmFk, forearmIk, rig, prop)
            copyTransform(hand, handFk, hand0Ik, rig, prop)
            copyTransform(hand0Ik, handIk, None, rig, prop)
            hintRotation(forearmIk)
            ikConstraint(forearmIk, handIk, elbowPt, -90, 2, rig)
            stretchTo(elbowLink, elbowPt, rig)

            yTrue = (False,True,False)
            copyRotation(forearm, handFk, yTrue, rig)
            copyRotation(forearm, hand0Ik, yTrue, rig, prop)
            forearmFk.lock_rotation = yTrue

            legSocket = rpbs["thighTwk"+suffix]
            legParent = rpbs["leg_parent"+suffix]
            thigh = rpbs["thigh"+suffix]
            shin = rpbs["shin"+suffix]
            foot = rpbs["foot"+suffix]
            toe = rpbs["toe"+suffix]
            ankle = rpbs["ankle"+suffix]
            ankleIk = rpbs["ankle.ik"+suffix]
            thighFk = getBoneCopy("thigh.fk"+suffix, thigh, rpbs)
            shinFk = getBoneCopy("shin.fk"+suffix, shin, rpbs)
            footFk = getBoneCopy("foot.fk"+suffix, foot, rpbs)
            toeFk = getBoneCopy("toe.fk"+suffix, toe, rpbs)
            thighIk = rpbs["thigh.ik"+suffix]
            shinIk = rpbs["shin.ik"+suffix]
            kneePt = rpbs["knee.pt.ik"+suffix]
            kneeLink = rpbs["knee.link"+suffix]
            footIk = rpbs["foot.ik"+suffix]
            toeRev = rpbs["toe.rev"+suffix]
            footRev = rpbs["foot.rev"+suffix]
            footInv = rpbs["foot.inv.ik"+suffix]
            toeInv = rpbs["toe.inv.ik"+suffix]

            prop = "MhaLegHinge_" + suffix[1]
            setattr(rig, prop, 0.0)
            copyTransform(legParent, None, legSocket, rig, prop, "1-x")
            copyLocation(legParent, legSocket, rig, prop, "x")

            prop1 = "MhaLegIk_"+suffix[1]
            setattr(rig, prop1, 0.0)
            prop2 = "MhaLegIkToAnkle_"+suffix[1]
            setattr(rig, prop2, False)

            footRev.lock_rotation = (False,True,True)

            copyTransform(thigh, thighFk, thighIk, rig, prop1)
            copyTransform(shin, shinFk, shinIk, rig, prop1)
            copyTransform(foot, footFk, footInv, rig, (prop1,prop2), "x1*(1-x2)")
            copyTransform(toe, toeFk, toeInv, rig, (prop1,prop2), "x1*(1-x2)")
            hintRotation(shinIk)
            ikConstraint(shinIk, ankleIk, kneePt, -90, 2, rig)
            stretchTo(kneeLink, kneePt, rig)
            cns = copyLocation(footFk, ankleIk, rig, (prop1,prop2), "x1*x2")
            cns.influence = 0
            cns = copyLocation(ankleIk, ankle, rig, prop2)
            cns.influence = 0

            prop = "MhaGaze_" + suffix[1]
            setattr(rig, prop, False)
            prefix = suffix[1].lower()
            eye = rpbs[prefix+"Eye"]
            gaze = rpbs["gaze"+suffix]
            trackTo(eye, gaze, rig, prop)

            self.lockLocations([
                upper_armFk, forearmFk, handFk,
                upper_armIk, forearmIk, elbowLink,
                thighFk, shinFk, footFk, toeFk,
                thighIk, shinIk, kneeLink, footRev, toeRev,
            ])

        prop = "DazGazeFollowsHead"
        setattr(rig, prop, 0.0)
        gaze0 = rpbs["gaze0"]
        gaze1 = rpbs["gaze1"]
        copyTransform(gaze1, None, gaze0, rig, prop)


    def lockLocations(self, bones):
        for pb in bones:
            lock = (not pb.bone.use_connect)
            pb.lock_location = (lock,lock,lock)


    #-------------------------------------------------------------
    #   Fix hand constraints -
    #-------------------------------------------------------------

    def fixHandConstraints(self, rig):
        for suffix in [".L", ".R"]:
            pb = rig.pose.bones["hand.fk" + suffix]
            for cns in pb.constraints:
                if cns.type == 'LIMIT_ROTATION':
                    cns.use_limit_y = False
                    minx = cns.min_x
                    maxx = cns.max_x
                    if suffix == ".L":
                        cns.min_x = -cns.max_z
                        cns.max_x = -cns.min_z
                    else:
                        cns.min_x = cns.min_z
                        cns.max_x = cns.max_z
                    cns.min_z = minx
                    cns.max_z = maxx

    #-------------------------------------------------------------
    #   Markers
    #-------------------------------------------------------------

    def addMarkers(self, rig):
        for suffix,dlayer in [(".L",0), (".R",16)]:
            bpy.ops.object.mode_set(mode='EDIT')
            foot = rig.data.edit_bones["foot"+suffix]
            toe = rig.data.edit_bones["toe"+suffix]
            offs = Vector((0, 0, 0.5*toe.length))
            if "heel"+suffix in rig.data.edit_bones.keys():
                heelTail = rig.data.edit_bones["heel"+suffix].tail
            else:
                heelTail = Vector((foot.head[0], foot.head[1], toe.head[2]))

            ballLoc = Vector((toe.head[0], toe.head[1], heelTail[2]))
            mBall = makeBone("ball.marker"+suffix, rig, ballLoc, ballLoc+offs, 0, L_LEXTRA+dlayer, foot)
            toeLoc = Vector((toe.tail[0], toe.tail[1], heelTail[2]))
            mToe = makeBone("toe.marker"+suffix, rig, toeLoc, toeLoc+offs, 0, L_LEXTRA+dlayer, toe)
            mHeel = makeBone("heel.marker"+suffix, rig, heelTail, heelTail+offs, 0, L_LEXTRA+dlayer, foot)

    #-------------------------------------------------------------
    #   Master bone
    #-------------------------------------------------------------

    def addMaster(self, rig):
        bpy.ops.object.mode_set(mode='EDIT')
        root = rig.data.edit_bones[self.hip]
        master = makeBone("master", rig, (0,0,0), (0,root.head[2]/5,0), 0, L_MAIN, None)
        for eb in rig.data.edit_bones:
            if eb.parent is None and eb != master:
                eb.parent = master

    #-------------------------------------------------------------
    #   Move all deform bones to layer 31
    #-------------------------------------------------------------

    def collectDeformBones(self, rig):
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in rig.data.bones:
            if bone.use_deform:
                bone.layers[L_DEF] = True


    def addLayers(self, rig):
        bpy.ops.object.mode_set(mode='OBJECT')
        for suffix,dlayer in [(".L",0), (".R",16)]:
            clavicle = rig.data.bones["clavicle"+suffix]
            clavicle.layers[L_SPINE] = True
            clavicle.layers[L_LARMIK+dlayer] = True


#-------------------------------------------------------------
#   connectToParent used by Rigify
#-------------------------------------------------------------

def connectToParent(rig):
    bpy.ops.object.mode_set(mode='EDIT')
    for bname in [
        "abdomenUpper", "chestLower", "chestUpper", "neckLower", "neckUpper",
        "lShldrTwist", "lForeArm", "lForearmBend", "lForearmTwist", "lHand",
        "rShldrTwist", "rForeArm", "rForearmBend", "rForearmTwist", "rHand",
        "lThumb2", "lThumb3",
        "lIndex1", "lIndex2", "lIndex3",
        "lMid1", "lMid2", "lMid3",
        "lRing1", "lRing2", "lRing3",
        "lPinky1", "lPinky2", "lPinky3",
        "rThumb2", "rThumb3",
        "rIndex1", "rIndex2", "rIndex3",
        "rMid1", "rMid2", "rMid3",
        "rRing1", "rRing2", "rRing3",
        "rPinky1", "rPinky2", "rPinky3",
        "lThighTwist", "lShin", "lFoot", "lToe",
        "rThighTwist", "rShin", "rFoot", "rToe",
        ]:
        if bname in rig.data.edit_bones.keys():
            eb = rig.data.edit_bones[bname]
            eb.parent.tail = eb.head
            eb.use_connect = True

#-------------------------------------------------------------
#   Gizmos used by winders
#-------------------------------------------------------------

Gizmos = {
    "master" :          "GZM_Master",
    "back" :            "GZM_Knuckle",

    #Spine
    "root" :            "GZM_CrownHips",
    "hip" :             "GZM_CrownHips",
    "hips" :            "GZM_CircleHips",
    "pelvis" :          "GZM_CircleHips",
    "spine" :           "GZM_CircleSpine",
    "spine-1" :         "GZM_CircleSpine",
    "chest" :           "GZM_CircleChest",
    "chest-1" :         "GZM_CircleChest",
    "neck" :            "GZM_Neck",
    "neck-1" :          "GZM_Neck",
    "head" :            "GZM_Head",
    #"breast.L" :        "GZM_Breast_L",
    #"breast.R" :        "GZM_Breast_R",

    # Head

    "lowerJaw" :        "GZM_Jaw",
    "rEye" :            "GZM_Circle025",
    "lEye" :            "GZM_Circle025",
    "gaze" :            "GZM_Gaze",
    "gaze.L" :          "GZM_Circle025",
    "gaze.R" :          "GZM_Circle025",

    "uplid.L" :         "GZM_UpLid",
    "uplid.R" :         "GZM_UpLid",
    "lolid.L" :         "GZM_LoLid",
    "lolid.R" :         "GZM_LoLid",

    "tongue_base" :     "GZM_Tongue",
    "tongue_mid" :      "GZM_Tongue",
    "tongue_tip" :      "GZM_Tongue",

    # Leg

    "thigh.fk.L" :      "GZM_Circle025",
    "thigh.fk.R" :      "GZM_Circle025",
    "shin.fk.L" :       "GZM_Circle025",
    "shin.fk.R" :       "GZM_Circle025",
    "foot.fk.L" :       "GZM_Foot_L",
    "foot.fk.R" :       "GZM_Foot_R",
    "toe.fk.L" :        "GZM_Toe_L",
    "toe.fk.R" :        "GZM_Toe_R",
    "thighTwk.L" :      "GZM_Ball025",
    "thighTwk.R" :      "GZM_Ball025",
    "foot.rev.L" :      "GZM_RevFoot",
    "foot.rev.R" :      "GZM_RevFoot",
    "foot.ik.L" :       "GZM_FootIK",
    "foot.ik.R" :       "GZM_FootIK",
    "toe.rev.L" :       "GZM_RevToe",
    "toe.rev.R" :       "GZM_RevToe",
    "ankle.L" :         "GZM_Ball025",
    "ankle.R" :         "GZM_Ball025",
    "knee.pt.ik.L" :    "GZM_Cube025",
    "knee.pt.ik.R" :    "GZM_Cube025",

    "toe.marker.L" :     "GZM_Ball025",
    "ball.marker.L" :    "GZM_Ball025",
    "heel.marker.L" :    "GZM_Ball025",
    "toe.marker.R" :     "GZM_Ball025",
    "ball.marker.R" :    "GZM_Ball025",
    "heel.marker.R" :    "GZM_Ball025",


    # Arm

    "clavicle.L" :      "GZM_Shoulder",
    "clavicle.R" :      "GZM_Shoulder",
    "upper_arm.fk.L" :  "GZM_Circle025",
    "upper_arm.fk.R" :  "GZM_Circle025",
    "forearm.fk.L" :    "GZM_Circle025",
    "forearm.fk.R" :    "GZM_Circle025",
    "hand.fk.L" :       "GZM_Hand",
    "hand.fk.R" :       "GZM_Hand",
    "shoulderTwk.L" :   "GZM_Ball025",
    "shoulderTwk.R" :   "GZM_Ball025",
    "hand.ik.L" :       "GZM_HandIK",
    "hand.ik.R" :       "GZM_HandIK",
    "elbow.pt.ik.L" :   "GZM_Cube025",
    "elbow.pt.ik.R" :   "GZM_Cube025",

    # Finger

    "thumb.L" :         "GZM_Knuckle",
    "index.L" :         "GZM_Knuckle",
    "middle.L" :        "GZM_Knuckle",
    "ring.L" :          "GZM_Knuckle",
    "pinky.L" :         "GZM_Knuckle",

    "thumb.R" :         "GZM_Knuckle",
    "index.R" :         "GZM_Knuckle",
    "middle.R" :        "GZM_Knuckle",
    "ring.R" :          "GZM_Knuckle",
    "pinky.R" :         "GZM_Knuckle",
    }

def makeGizmos(gnames, parent, hidden):
    from .load_json import loadJson
    folder = os.path.dirname(__file__)
    filepath = os.path.join(folder, "data", "gizmos.json")
    struct = loadJson(filepath)
    gizmos = {}
    if gnames is None:
        gnames = struct.keys()
    for gname in gnames:
        gizmo = struct[gname]
        me = bpy.data.meshes.new(gname)
        me.from_pydata(gizmo["verts"], gizmo["edges"], [])
        ob = bpy.data.objects.new(gname, me)
        hidden.objects.link(ob)
        ob.parent = parent
        putOnHiddenLayer(ob)
        if gizmo["subsurf"]:
            ob.modifiers.new('SUBSURF', 'SUBSURF')
        gizmos[gname] = ob
    return gizmos

# ---------------------------------------------------------------------
#   Convert MHX actions from legacy to modern
# ---------------------------------------------------------------------

from .morphing import Selector

class DAZ_OT_ConvertMhxActions(DazOperator, Selector, B.MHXConvertAction):
    bl_idname = "daz.convert_mhx_actions"
    bl_label = "Convert MHX Actions"
    bl_description = "Convert actions between legacy MHX (root/hips) and modern MHX (hip/pelvis)"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "direction")
        Selector.draw(self, context)


    def run(self, context):
        if self.direction == 'MODERN':
            replace = {
                '"root"' : '"hip"',
                '"hips"' : '"pelvis"',
            }
        else:
            replace = {
                '"hip"' : '"root"',
                '"pelvis"' : '"hips"',
            }
        for item in self.getSelectedItems(context.scene):
            act = bpy.data.actions[item.name]
            for fcu in act.fcurves:
                for old,new in replace.items():
                    if old in fcu.data_path:
                        fcu.data_path = fcu.data_path.replace(old, new)


    def invoke(self, context, event):
        self.selection.clear()
        for act in bpy.data.actions:
            item = self.selection.add()
            item.name = act.name
            item.text = act.name
            item.select = False
        return self.invokeDialog(context)

#-------------------------------------------------------------
#   Init MHX props. Same as mhx2 importer
#-------------------------------------------------------------

classes = [
    DAZ_OT_ConvertToMhx,
    DAZ_OT_ConvertMhxActions,
]

def initialize():
    bpy.types.Object.DazMhxLegacy = BoolProperty(default=True)

    # MHX Control properties
    bpy.types.Object.DazHintsOn = BoolProperty(default=True)
    bpy.types.Object.DazGazeFollowsHead = FloatProperty(default=0.0, min=0.0, max=1.0)

    bpy.types.Object.MhaArmHinge_L = BoolProperty(default=False)
    bpy.types.Object.MhaArmIk_L = FloatProperty(default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.MhaFingerControl_L = BoolProperty(default=False)
    bpy.types.Object.MhaGaze_L = BoolProperty(default=False)
    bpy.types.Object.MhaLegHinge_L = BoolProperty(default=False)
    bpy.types.Object.MhaLegIkToAnkle_L = BoolProperty(default=False)
    bpy.types.Object.MhaLegIk_L = FloatProperty(default=0.0, precision=3, min=0.0, max=1.0)

    bpy.types.Object.MhaArmHinge_R = BoolProperty(default=False)
    bpy.types.Object.MhaArmIk_R = FloatProperty(default=0.0, precision=3, min=0.0, max=1.0)
    bpy.types.Object.MhaFingerControl_R = BoolProperty(default=False)
    bpy.types.Object.MhaGaze_R = BoolProperty(default=False)
    bpy.types.Object.MhaLegHinge_R = BoolProperty(default=False)
    bpy.types.Object.MhaLegIkToAnkle_R = BoolProperty(default=False)
    bpy.types.Object.MhaLegIk_R = FloatProperty(default=0.0, precision=3, min=0.0, max=1.0)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
