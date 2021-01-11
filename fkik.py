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
#   FK-IK snapping.
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


def matchPoseTranslation(pb, src, auto, rig):
    pmat = getPoseMatrix(src.matrix, pb)
    insertLocation(pb, pmat, auto, rig)


def insertLocation(pb, mat, auto, rig):
    pb.location = mat.to_translation()
    if auto or isKeyed(rig, pb, "location"):
        pb.keyframe_insert("location", group=pb.name)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def matchPoseRotation(pb, src, auto, rig):
    pmat = getPoseMatrix(src.matrix, pb)
    insertRotation(pb, pmat, auto, rig)


def printMatrix(string,mat):
    print(string)
    for i in range(4):
        print("    %.4g %.4g %.4g %.4g" % tuple(mat[i]))


def insertRotation(pb, mat, auto, rig):
    quat = mat.to_quaternion()
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = quat
        if auto or isKeyed(rig, pb, "rotation_quaternion"):
            pb.keyframe_insert("rotation_quaternion", group=pb.name)
    else:
        pb.rotation_euler = quat.to_euler(pb.rotation_mode)
        if auto or isKeyed(rig, pb, "rotation_euler"):
            pb.keyframe_insert("rotation_euler", group=pb.name)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def matchPoseTwist(pb, src, auto, rig):
    pmat0 = src.matrix_basis
    euler = pmat0.to_3x3().to_euler('YZX')
    euler.z = 0
    pmat = euler.to_matrix().to_4x4()
    pmat.col[3] = pmat0.col[3]
    insertRotation(pb, pmat, auto, rig)


def matchIkLeg(legIk, toeFk, mBall, mToe, mHeel, auto, rig):
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

    insertLocation(legIk, pmat, auto, rig)
    insertRotation(legIk, pmat, auto, rig)


def matchPoleTarget(pb, above, below, auto, rig):
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
    insertLocation(pb, pmat, auto, rig)


def matchPoseReverse(pb, src, auto, rig):
    gmat = src.matrix
    tail = gmat.col[3] + src.length * gmat.col[1]
    rmat = Matrix((gmat.col[0], -gmat.col[1], -gmat.col[2], tail))
    rmat.transpose()
    pmat = getPoseMatrix(rmat, pb)
    pb.matrix_basis = pmat
    insertRotation(pb, pmat, auto, rig)


def matchPoseScale(pb, src, auto, rig):
    pmat = getPoseMatrix(src.matrix, pb)
    pb.scale = pmat.to_scale()
    if auto or isKeyed(rig, pb, "scale"):
        pb.keyframe_insert("scale", group=pb.name)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def snapFkArm(context, data):
    rig = context.object
    prop,old,suffix = setSnapProp(rig, data, 1.0, context, False)
    auto = context.scene.tool_settings.use_keyframe_insert_auto

    print("Snap FK Arm%s" % suffix)
    snapFk,cnsFk = getSnapBones(rig, "ArmFK", suffix)
    (uparmFk, loarmFk, handFk) = snapFk
    muteConstraints(cnsFk, True)
    snapIk,cnsIk = getSnapBones(rig, "ArmIK", suffix)
    (uparmIk, loarmIk, elbow, elbowPt, handIk) = snapIk

    matchPoseRotation(uparmFk, uparmIk, auto, rig)
    matchPoseScale(uparmFk, uparmIk, auto, rig)

    matchPoseRotation(loarmFk, loarmIk, auto, rig)
    matchPoseScale(loarmFk, loarmIk, auto, rig)

    restoreSnapProp(rig, prop, old, context)

    try:
        matchHand = rig["MhaHandFollowsWrist" + suffix]
    except KeyError:
        matchHand = True
    if matchHand:
        matchPoseRotation(handFk, handIk, auto, rig)
        matchPoseScale(handFk, handIk, auto, rig)

    muteConstraints(cnsFk, False)
    setattr(rig, prop, 0)


def snapIkArm(context, data):
    rig = context.object
    prop,old,suffix = setSnapProp(rig, data, 0.0, context, True)
    auto = context.scene.tool_settings.use_keyframe_insert_auto

    print("Snap IK Arm%s" % suffix)
    snapIk,cnsIk = getSnapBones(rig, "ArmIK", suffix)
    (uparmIk, loarmIk, elbow, elbowPt, handIk) = snapIk
    snapFk,cnsFk = getSnapBones(rig, "ArmFK", suffix)
    (uparmFk, loarmFk, handFk) = snapFk
    muteConstraints(cnsIk, True)

    matchPoseTranslation(handIk, handFk, auto, rig)
    matchPoseRotation(handIk, handFk, auto, rig)

    matchPoleTarget(elbowPt, uparmFk, loarmFk, auto, rig)

    matchPoseRotation(uparmIk, uparmFk, auto, rig)
    matchPoseRotation(loarmIk, loarmFk, auto, rig)

    restoreSnapProp(rig, prop, old, context)
    muteConstraints(cnsIk, False)
    setattr(rig, prop, 1)


def snapFkLeg(context, data):
    rig = context.object
    prop,old,suffix = setSnapProp(rig, data, 1.0, context, False)
    auto = context.scene.tool_settings.use_keyframe_insert_auto

    print("Snap FK Leg%s" % suffix)
    snap,_ = getSnapBones(rig, "Leg", suffix)
    (upleg, loleg, foot, toe) = snap
    snapIk,cnsIk = getSnapBones(rig, "LegIK", suffix)
    (uplegIk, lolegIk, kneePt, ankle, ankleIk, legIk, footRev, toeRev, mBall, mToe, mHeel) = snapIk
    snapFk,cnsFk = getSnapBones(rig, "LegFK", suffix)
    (uplegFk, lolegFk, footFk, toeFk) = snapFk
    muteConstraints(cnsFk, True)

    matchPoseRotation(uplegFk, uplegIk, auto, rig)
    matchPoseScale(uplegFk, uplegIk, auto, rig)

    matchPoseRotation(lolegFk, lolegIk, auto, rig)
    matchPoseScale(lolegFk, lolegIk, auto, rig)

    restoreSnapProp(rig, prop, old, context)

    if not getattr(rig, "MhaLegIkToAnkle" + suffix):
        matchPoseReverse(footFk, footRev, auto, rig)
        matchPoseReverse(toeFk, toeRev, auto, rig)

    muteConstraints(cnsFk, False)
    setattr(rig, prop, 0)


def snapIkLeg(context, data):
    rig = context.object
    scn = context.scene
    prop,old,suffix = setSnapProp(rig, data, 0.0, context, True)
    auto = scn.tool_settings.use_keyframe_insert_auto

    print("Snap IK Leg%s" % suffix)
    snapIk,cnsIk = getSnapBones(rig, "LegIK", suffix)
    (uplegIk, lolegIk, kneePt, ankle, ankleIk, legIk, footRev, toeRev, mBall, mToe, mHeel) = snapIk
    snapFk,cnsFk = getSnapBones(rig, "LegFK", suffix)
    (uplegFk, lolegFk, footFk, toeFk) = snapFk
    muteConstraints(cnsIk, True)

    matchPoseTranslation(ankle, footFk, auto, rig)
    matchIkLeg(legIk, toeFk, mBall, mToe, mHeel, auto, rig)

    matchPoseReverse(toeRev, toeFk, auto, rig)
    matchPoseReverse(footRev, footFk, auto, rig)

    matchPoleTarget(kneePt, uplegFk, lolegFk, auto, rig)

    #matchPoseTwist(lolegIk, lolegFk, auto, rig)
    matchPoseRotation(uplegIk, uplegIk, auto, rig)
    matchPoseRotation(lolegIk, lolegIk, auto, rig)

    matchPoseTranslation(ankleIk, footFk, auto, rig)

    restoreSnapProp(rig, prop, old, context)
    muteConstraints(cnsIk, False)
    setattr(rig, prop, 1)


SnapBonesAlpha8 = {
    "Arm"   : ["upper_arm", "forearm", "hand"],
    "ArmFK" : ["upper_arm.fk", "forearm.fk", "hand.fk"],
    "ArmIK" : ["upper_arm.ik", "forearm.ik", None, "elbow.pt.ik", "hand.ik"],
    "Leg"   : ["thigh", "shin", "foot", "toe"],
    "LegFK" : ["thigh.fk", "shin.fk", "foot.fk", "toe.fk"],
    "LegIK" : ["thigh.ik", "shin.ik", "knee.pt.ik", "ankle", "ankle.ik", "foot.ik", "foot.rev", "toe.rev", "ball.marker", "toe.marker", "heel.marker"],
}


def getSnapBones(rig, key, suffix):
    try:
        rig.pose.bones["thigh.fk.L"]
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
                pb = rig.pose.bones[name+suffix]
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


def muteConstraints(constraints, value):
    for cns in constraints:
        cns.mute = value


class DAZ_OT_MhxSnapFk2Ik(DazOperator, B.DataString):
    bl_idname = "daz.snap_fk_ik"
    bl_label = "Snap FK"
    bl_options = {'UNDO'}

    def run(self, context):
        bpy.ops.object.mode_set(mode='POSE')
        rig = context.object
        if self.data[:6] == "MhaArm":
            snapFkArm(context, self.data)
        elif self.data[:6] == "MhaLeg":
            snapFkLeg(context, self.data)


class DAZ_OT_MhxSnapIk2Fk(DazOperator, B.DataString):
    bl_idname = "daz.snap_ik_fk"
    bl_label = "Snap IK"
    bl_options = {'UNDO'}

    def run(self, context):
        bpy.ops.object.mode_set(mode='POSE')
        rig = context.object
        if self.data[:6] == "MhaArm":
            snapIkArm(context, self.data)
        elif self.data[:6] == "MhaLeg":
            snapIkLeg(context, self.data)


def setSnapProp(rig, data, value, context, isIk):
    words = data.split()
    prop = words[0]
    oldValue = getattr(rig, prop)
    setattr(rig, prop, value)
    ik = int(words[1])
    fk = int(words[2])
    extra = int(words[3])
    oldIk = rig.data.layers[ik]
    oldFk = rig.data.layers[fk]
    oldExtra = rig.data.layers[extra]
    rig.data.layers[ik] = True
    rig.data.layers[fk] = True
    rig.data.layers[extra] = True
    updatePose(context)
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


def restoreSnapProp(rig, prop, old, context):
    updatePose(context)
    (oldValue, ik, fk, extra, oldIk, oldFk, oldExtra) = old
    setattr(rig, prop,  oldValue)
    rig.data.layers[ik] = oldIk
    rig.data.layers[fk] = oldFk
    rig.data.layers[extra] = oldExtra
    updatePose(context)
    return


class DAZ_OT_MhxToggleFkIk(DazOperator, B.ToggleString):
    bl_idname = "daz.toggle_fk_ik"
    bl_label = "FK - IK"
    bl_options = {'UNDO'}

    def run(self, context):
        words = self.toggle.split()
        rig = context.object
        scn = context.scene
        prop = words[0]
        value = float(words[1])
        onLayer = int(words[2])
        offLayer = int(words[3])
        rig.data.layers[onLayer] = True
        rig.data.layers[offLayer] = False
        setattr(rig, prop, value)
        path = ('["%s"]' % prop)
        if isKeyed(rig, None, path):
            rig.keyframe_insert(path, frame=scn.frame_current)
        updatePose(context)


def isKeyed(rig, pb, path):
    if rig.animation_data:
        act = rig.animation_data.action
        if act:
            if pb:
                path = ('pose.bones["%s"].%s' % (pb.name, path))
            for fcu in act.fcurves:
                if fcu.data_path == path:
                    return True
    return False

#
#   updatePose(context):
#   class DAZ_OT_MhxUpdate(DazOperator):
#

def updatePose(context):
    scn = context.scene
    scn.frame_current = scn.frame_current
    bpy.ops.object.posemode_toggle()
    bpy.ops.object.posemode_toggle()


class DAZ_OT_MhxUpdate(DazOperator):
    bl_idname = "daz.update"
    bl_label = "Update"

    def run(self, context):
        updatePose(context)


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
        rig.DazHintsOn = not rig.DazHintsOn
        updatePose(context)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MhxSnapFk2Ik,
    DAZ_OT_MhxSnapIk2Fk,
    DAZ_OT_MhxToggleFkIk,
    DAZ_OT_MhxUpdate,
    DAZ_OT_MhxToggleHints,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

