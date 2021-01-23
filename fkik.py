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
from bpy.props import StringProperty
from mathutils import *
from .error import *
from .utils import *

#------------------------------------------------------------------
#   Get pose matrix
#------------------------------------------------------------------

def getPoseMatrix(gmat, pb):
    restInv = pb.bone.matrix_local.inverted()
    if pb.parent:
        parInv = pb.parent.matrix.inverted()
        parRest = pb.parent.bone.matrix_local
        return Mult4(restInv, parRest, parInv, gmat)
    else:
        return Mult2(restInv, gmat)


def getGlobalMatrix(mat, pb):
    gmat = Mult2(pb.bone.matrix_local, mat)
    if pb.parent:
        parMat = pb.parent.matrix
        parRest = pb.parent.bone.matrix_local
        return Mult3(parMat, parRest.inverted(), gmat)
    else:
        return gmat


def printMatrix(string,mat):
    print(string)
    for i in range(4):
        print("    %.4g %.4g %.4g %.4g" % tuple(mat[i]))


def muteConstraints(constraints, value):
    for cns in constraints:
        cns.mute = value


def updatePose():
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')

#------------------------------------------------------------------
#   Snapper class
#------------------------------------------------------------------

class Snapper:

    def matchPoseTranslation(self, pb, src):
        pmat = getPoseMatrix(src.matrix, pb)
        self.insertLocation(pb, pmat)


    def insertLocation(self, pb, mat):
        pb.location = mat.to_translation()
        if self.auto or self.isKeyed(pb, "location"):
            pb.keyframe_insert("location", group=pb.name)


    def matchPoseRotation(self, pb, src):
        pmat = getPoseMatrix(src.matrix, pb)
        self.insertRotation(pb, pmat)


    def insertRotation(self, pb, mat):
        quat = mat.to_quaternion()
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = quat
            if self.auto or self.isKeyed(pb, "rotation_quaternion"):
                pb.keyframe_insert("rotation_quaternion", group=pb.name)
        else:
            pb.rotation_euler = quat.to_euler(pb.rotation_mode)
            if self.auto or self.isKeyed(pb, "rotation_euler"):
                pb.keyframe_insert("rotation_euler", group=pb.name)


    def matchPoseTwist(self, pb, src):
        pmat0 = src.matrix_basis
        euler = pmat0.to_3x3().to_euler('YZX')
        euler.z = 0
        pmat = euler.to_matrix().to_4x4()
        pmat.col[3] = pmat0.col[3]
        self.insertRotation(pb, pmat)


    def matchIkLeg(self, legIk, toeFk, mBall, mToe, mHeel):
        rmat = toeFk.matrix.to_3x3()
        tHead = Vector(toeFk.matrix.col[3][:3])
        ty = rmat.col[1]
        tail = tHead + ty * toeFk.bone.length

        try:
            zBall = mBall.matrix.col[3][2]
        except AttributeError:
            return
        zToe = mToe.matrix.col[3][2]
        zHeel = mHeel.matrix.col[3][2]

        x = Vector(rmat.col[0])
        y = Vector(rmat.col[1])
        z = Vector(rmat.col[2])

        if zHeel > zBall and zHeel > zToe:
            # 1. foot.ik is flat
            if abs(y[2]) > abs(z[2]):
                y = -z
            y[2] = 0
        else:
            # 2. foot.ik starts at heel
            hHead = Vector(mHeel.matrix.col[3][:3])
            y = tail - hHead

        y.normalize()
        x -= x.dot(y)*y
        x.normalize()
        z = x.cross(y)
        head = tail - y * legIk.bone.length

        # Create matrix
        gmat = Matrix()
        gmat.col[0][:3] = x
        gmat.col[1][:3] = y
        gmat.col[2][:3] = z
        gmat.col[3][:3] = head
        pmat = getPoseMatrix(gmat, legIk)

        self.insertLocation(legIk, pmat)
        self.insertRotation(legIk, pmat)


    def matchPoleTarget(self, pb, above, below):
        ay = Vector(above.matrix.col[1][:3])
        by = Vector(below.matrix.col[1][:3])
        az = Vector(above.matrix.col[2][:3])
        bz = Vector(below.matrix.col[2][:3])
        p0 = Vector(below.matrix.col[3][:3])
        n = ay.cross(by)
        if abs(n.length) > 1e-4:
            d = ay - by
            n.normalize()
            d -= d.dot(n)*n
            d.normalize()
            if d.dot(az) > 0:
                d = -d
            p = p0 + 6*pb.bone.length*d
        else:
            p = p0
        gmat = Matrix.Translation(p)
        pmat = getPoseMatrix(gmat, pb)
        self.insertLocation(pb, pmat)


    def matchPoseReverse(self, pb, src):
        gmat = src.matrix
        tail = gmat.col[3] + src.length * gmat.col[1]
        rmat = Matrix((gmat.col[0], -gmat.col[1], -gmat.col[2], tail))
        rmat.transpose()
        pmat = getPoseMatrix(rmat, pb)
        pb.matrix_basis = pmat
        self.insertRotation(pb, pmat)


    def matchPoseScale(self, pb, src):
        pmat = getPoseMatrix(src.matrix, pb)
        pb.scale = pmat.to_scale()
        if self.auto or self.isKeyed(pb, "scale"):
            pb.keyframe_insert("scale", group=pb.name)


    def isKeyed(self, pb, path):
        if self.rig.animation_data:
            act = self.rig.animation_data.action
            if act:
                if pb:
                    path = ('pose.bones["%s"].%s' % (pb.name, path))
                for fcu in act.fcurves:
                    if fcu.data_path == path:
                        return True
        return False


    def getSnapBones(self, key, suffix):
        try:
            self.rig.pose.bones["thigh.fk.L"]
            names = SnapBonesAlpha8[key]
            suffix = '.' + suffix[1:]
        except KeyError:
            names = None

        if not names:
            raise DazError("Not an mhx armature")

        pbones = []
        constraints = []
        for name in names:
            if name:
                try:
                    pb = self.rig.pose.bones[name+suffix]
                except KeyError:
                    pb = None
                pbones.append(pb)
                if pb is not None:
                    for cns in pb.constraints:
                        if cns.type == 'LIMIT_ROTATION' and not cns.mute:
                            constraints.append(cns)
            else:
                pbones.append(None)
        return tuple(pbones),constraints


    def setSnapProp(self, value, context, isIk):
        words = self.data.split()
        prop = words[0]
        oldValue = getattrOVR(self.rig, prop)
        self.rig[prop] = value
        ik = int(words[1])
        fk = int(words[2])
        extra = int(words[3])
        oldIk = self.rig.data.layers[ik]
        oldFk = self.rig.data.layers[fk]
        oldExtra = self.rig.data.layers[extra]
        self.rig.data.layers[ik] = True
        self.rig.data.layers[fk] = True
        self.rig.data.layers[extra] = True
        updatePose()
        if isIk:
            oldValue = 1.0
            oldIk = True
            oldFk = False
        else:
            oldValue = 0.0
            oldIk = False
            oldFk = True
            oldExtra = False
        return (prop, (oldValue, ik, fk, extra, oldIk, oldFk, oldExtra), prop[-2:])


    def restoreSnapProp(self, prop, old, context):
        (oldValue, ik, fk, extra, oldIk, oldFk, oldExtra) = old
        self.rig[prop] = oldValue
        self.rig.data.layers[ik] = oldIk
        self.rig.data.layers[fk] = oldFk
        self.rig.data.layers[extra] = oldExtra
        updatePose()


SnapBonesAlpha8 = {
    "Arm"   : ["upper_arm", "forearm", "hand"],
    "ArmFK" : ["upper_arm.fk", "forearm.fk", "hand.fk"],
    "ArmIK" : ["upper_arm.ik", "forearm.ik", None, "elbow.pt.ik", "hand.ik"],
    "Leg"   : ["thigh", "shin", "foot", "toe"],
    "LegFK" : ["thigh.fk", "shin.fk", "foot.fk", "toe.fk"],
    "LegIK" : ["thigh.ik", "shin.ik", "knee.pt.ik", "ankle", "ankle.ik", "foot.ik", "foot.rev", "toe.rev", "ball.marker", "toe.marker", "heel.marker"],
}


class DAZ_OT_MhxSnapFk2Ik(DazOperator, Snapper, B.DataString):
    bl_idname = "daz.snap_fk_ik"
    bl_label = "Snap FK"
    bl_options = {'UNDO'}

    def run(self, context):
        bpy.ops.object.mode_set(mode='POSE')
        self.rig = context.object
        self.auto = context.scene.tool_settings.use_keyframe_insert_auto
        if self.data[:6] == "MhaArm":
            self.snapFkArm(context)
        elif self.data[:6] == "MhaLeg":
            self.snapFkLeg(context)


    def snapFkArm(self, context):
        prop,old,suffix = self.setSnapProp(1.0, context, False)
        print("Snap FK Arm%s" % suffix)
        snapFk,cnsFk = self.getSnapBones("ArmFK", suffix)
        (uparmFk, loarmFk, handFk) = snapFk
        muteConstraints(cnsFk, True)
        snapIk,cnsIk = self.getSnapBones("ArmIK", suffix)
        (uparmIk, loarmIk, elbow, elbowPt, handIk) = snapIk

        self.matchPoseRotation(uparmFk, uparmIk)
        self.matchPoseScale(uparmFk, uparmIk)
        updatePose()
        self.matchPoseRotation(loarmFk, loarmIk)
        self.matchPoseScale(loarmFk, loarmIk)
        updatePose()

        try:
            matchHand = self.rig["MhaHandFollowsWrist" + suffix]
        except KeyError:
            matchHand = True
        if matchHand:
            self.matchPoseRotation(handFk, handIk)
            self.matchPoseScale(handFk, handIk)
            updatePose()

        self.restoreSnapProp(prop, old, context)
        muteConstraints(cnsFk, False)
        self.rig[prop] = 0.0


    def snapFkLeg(self, context):
        prop,old,suffix = self.setSnapProp(1.0, context, False)
        print("Snap FK Leg%s" % suffix)
        snap,_ = self.getSnapBones("Leg", suffix)
        (upleg, loleg, foot, toe) = snap
        snapIk,cnsIk = self.getSnapBones("LegIK", suffix)
        (uplegIk, lolegIk, kneePt, ankle, ankleIk, legIk, footRev, toeRev, mBall, mToe, mHeel) = snapIk
        snapFk,cnsFk = self.getSnapBones("LegFK", suffix)
        (uplegFk, lolegFk, footFk, toeFk) = snapFk
        muteConstraints(cnsFk, True)

        self.matchPoseRotation(uplegFk, uplegIk)
        self.matchPoseScale(uplegFk, uplegIk)
        updatePose()
        self.matchPoseRotation(lolegFk, lolegIk)
        self.matchPoseScale(lolegFk, lolegIk)
        updatePose()
        if not getattrOVR(self.rig, "MhaLegIkToAnkle" + suffix):
            self.matchPoseReverse(footFk, footRev)
            updatePose()
            self.matchPoseReverse(toeFk, toeRev)
            updatePose()

        self.restoreSnapProp(prop, old, context)
        muteConstraints(cnsFk, False)
        self.rig[prop] = 0.0


class DAZ_OT_MhxSnapIk2Fk(DazOperator, Snapper, B.DataString):
    bl_idname = "daz.snap_ik_fk"
    bl_label = "Snap IK"
    bl_options = {'UNDO'}

    def run(self, context):
        bpy.ops.object.mode_set(mode='POSE')
        self.rig = context.object
        self.auto = context.scene.tool_settings.use_keyframe_insert_auto
        if self.data[:6] == "MhaArm":
            self.snapIkArm(context)
        elif self.data[:6] == "MhaLeg":
            self.snapIkLeg(context)


    def snapIkArm(self, context):
        prop,old,suffix = self.setSnapProp(0.0, context, True)
        print("Snap IK Arm%s" % suffix)
        snapIk,cnsIk = self.getSnapBones("ArmIK", suffix)
        (uparmIk, loarmIk, elbow, elbowPt, handIk) = snapIk
        snapFk,cnsFk = self.getSnapBones("ArmFK", suffix)
        (uparmFk, loarmFk, handFk) = snapFk
        muteConstraints(cnsIk, True)

        self.matchPoseTranslation(handIk, handFk)
        self.matchPoseRotation(handIk, handFk)
        updatePose()
        self.matchPoleTarget(elbowPt, uparmFk, loarmFk)
        updatePose()

        self.restoreSnapProp(prop, old, context)
        muteConstraints(cnsIk, False)
        self.rig[prop] = 1.0


    def snapIkLeg(self, context):
        prop,old,suffix = self.setSnapProp(0.0, context, True)
        print("Snap IK Leg%s" % suffix)
        snapIk,cnsIk = self.getSnapBones("LegIK", suffix)
        (uplegIk, lolegIk, kneePt, ankle, ankleIk, legIk, footRev, toeRev, mBall, mToe, mHeel) = snapIk
        snapFk,cnsFk = self.getSnapBones("LegFK", suffix)
        (uplegFk, lolegFk, footFk, toeFk) = snapFk
        muteConstraints(cnsIk, True)

        self.matchPoseTranslation(ankle, footFk)
        updatePose()
        self.matchIkLeg(legIk, toeFk, mBall, mToe, mHeel)
        updatePose()
        self.matchPoseReverse(toeRev, toeFk)
        updatePose()
        self.matchPoseReverse(footRev, footFk)
        updatePose()
        self.matchPoseTranslation(ankleIk, footFk)
        updatePose()
        self.matchPoleTarget(kneePt, uplegFk, lolegFk)
        updatePose()

        self.restoreSnapProp(prop, old, context)
        muteConstraints(cnsIk, False)
        self.rig[prop] = 1.0


class DAZ_OT_MhxToggleFkIk(DazOperator, Snapper, B.ToggleString):
    bl_idname = "daz.toggle_fk_ik"
    bl_label = "FK - IK"
    bl_options = {'UNDO'}

    def run(self, context):
        words = self.toggle.split()
        self.rig = context.object
        scn = context.scene
        prop = words[0]
        value = float(words[1])
        onLayer = int(words[2])
        offLayer = int(words[3])
        self.rig.data.layers[onLayer] = True
        self.rig.data.layers[offLayer] = False
        self.rig[prop] = value
        path = ('["%s"]' % prop)
        if self.isKeyed(None, path):
            self.rig.keyframe_insert(path, frame=scn.frame_current)
        updatePose()


class DAZ_OT_MhxToggleHints(DazOperator):
    bl_idname = "daz.toggle_hints"
    bl_label = "Toggle Hints"
    bl_description = "Toggle hints for elbow and knee bending. It may be necessary to turn these off for correct FK->IK snapping."

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if cns.type == 'LIMIT_ROTATION' and cns.name == "Hint":
                    cns.mute = not cns.mute
        rig["DazHintsOn"] = not getattrOVR(rig, "DazHintsOn")
        updatePose()

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MhxSnapFk2Ik,
    DAZ_OT_MhxSnapIk2Fk,
    DAZ_OT_MhxToggleFkIk,
    DAZ_OT_MhxToggleHints,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

