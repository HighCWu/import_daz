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
from math import pi
from mathutils import *
from .utils import *
from .transform import Transform
from .error import *
from .node import Node, Instance

#-------------------------------------------------------------
#   Roll correction in DAZ Studio mode
#-------------------------------------------------------------

RollCorrection = {
    "lCollar" : 180,
    "lShldr" : -90,
    "lShldrBend" : -90,
    "lShldrTwist" : -90,
    "lHand" : -90,
    "lThumb1" : 180,
    "lThumb2" : 180,
    "lThumb3" : 180,

    "rCollar" : 180,
    "rShldr" : 90,
    "rShldrBend" : 90,
    "rShldrTwist" : 90,
    "rHand" : 90,
    "rThumb1" : 180,
    "rThumb2" : 180,
    "rThumb3" : 180,

    "lEar" : -90,
    "rEar" : 90,
}

RollCorrectionGenesis = {
    "lEye" : 180,
    "rEye" : 180,
}

SocketBones = [
    "lShldr", "lShldrBend",
    "rShldr", "rShldrBend",
    "lThigh", "lThighBend",
    "rThigh", "rThighBend",
]

RotationModes = {
    "lHand" : "YXZ",
    "rHand" : "YXZ",
}

#-------------------------------------------------------------
#   Roll tables in Legacy mode
#-------------------------------------------------------------

RotateRoll = {
    "lPectoral" : -90,
    "rPectoral" : 90,

    "upperJaw" : 0,
    "lowerJaw" : 0,

    "lFoot" : -90,
    "lMetatarsals" : -90,
    "lToe" : -90,

    "rFoot" : 90,
    "rMetatarsals" : 90,
    "rToe" : 90,

    "lShldr" : 90,
    "lShldrBend" : 90,
    "lShldrTwist" : 90,
    "lForeArm" : 0,
    "lForearmBend" : 90,
    "lForearmTwist" : 90,

    "rShldr" : -90,
    "rShldrBend" : -90,
    "rShldrTwist" : -90,
    "rForeArm" : 0,
    "rForearmBend" : -90,
    "rForearmTwist" : -90,
}

ZPerpendicular = {
    "lShldr" : 2,
    "lShldrBend" : 2,
    "lShldrTwist" : 2,
    "lForeArm" : 2,
    "lForearmBend" : 2,
    "lForearmTwist" : 2,

    "rShldr" : 2,
    "rShldrBend" : 2,
    "rShldrTwist" : 2,
    "rForeArm" : 2,
    "rForearmBend" : 2,
    "rForearmTwist" : 2,

    "lThigh" : 0,
    "lThighBend" : 0,
    "lThighTwist" : 0,
    "lShin" : 0,
    "lFoot" : 0,
    "lMetatarsals" : 0,
    "lToe" : 0,

    "rThigh" : 0,
    "rThighBend" : 0,
    "rThighTwist" : 0,
    "rShin" : 0,
    "rFoot" : 0,
    "rMetatarsals" : 0,
    "rToe" : 0,
}

BoneAlternatives = {
    "abdomen" : "abdomenLower",
    "abdomen2" : "abdomenUpper",
    "chest" : "chestLower",
    "chest_2" : "chestUpper",
    "neck" : "neckLower",
    "neck_2" : "neckUpper",

    "lShldr" : "lShldrBend",
    "lForeArm" : "lForearmBend",
    "lWrist" : "lForearmTwist",
    "lCarpal2-1" : "lCarpal2",
    "lCarpal2" : "lCarpal4",

    "rShldr" : "rShldrBend",
    "rForeArm" : "rForearmBend",
    "rWrist" : "rForearmTwist",
    "rCarpal2-1" : "rCarpal2",
    "rCarpal2" : "rCarpal4",

    "upperJaw" : "upperTeeth",
    "tongueBase" : "tongue01",
    "tongue01" : "tongue02",
    "tongue02" : "tongue03",
    "tongue03" : "tongue04",
    "MidBrowUpper" : "CenterBrow",

    "lLipCorver" : "lLipCorner",
    "lCheekLowerInner" : "lCheekLower",
    "lCheekUpperInner" : "lCheekUpper",
    "lEyelidTop" : "lEyelidUpper",
    "lEyelidLower_2" : "lEyelidLowerInner",
    "lNoseBirdge" : "lNasolabialUpper",

    "rCheekLowerInner" : "rCheekLower",
    "rCheekUpperInner" : "rCheekUpper",

    "lThigh" : "lThighBend",
    "lBigToe2" : "lBigToe_2",

    "rThigh" : "rThighBend",
    "rBigToe2" : "rBigToe_2",

    "Shaft 1" : "shaft1",
    "Shaft 2" : "shaft2",
    "Shaft 3" : "shaft3",
    "Shaft 4" : "shaft4",
    "Shaft 5" : "shaft5",
    "Shaft5" : "shaft5",
    "Shaft 6" : "shaft6",
    "Shaft 7" : "shaft7",
    "Left Testicle" : "lTesticle",
    "Right Testicle" : "rTesticle",
    "Scortum" : "scrotum",
    "Legs Crease" : "legsCrease",
    "Rectum" : "rectum1",
    "Rectum 1" : "rectum1",
    "Rectum 2" : "rectum2",
    "Colon" : "colon",
    "Root" : "shaftRoot",
    "root" : "shaftRoot",
}


ArmBones = [
    "lShldr", "lShldrBend", "lShldrTwist",
    "lForeArm", "lForearmBend", "lForearmTwist",

    "rShldr", "rShldrBend", "rShldrTwist",
    "rForeArm", "rForearmBend", "rForearmTwist",
]

LegBones = [
    "lThigh", "lThighBend", "lThighTwist",
    "lShin", "lFoot", "lMetatarsals", "lToe",

    "rThigh", "rThighBend", "rThighTwist",
    "rShin", "rFoot", "rMetatarsals", "rToe",
]

FingerBones = [
    "lHand",
    "lCarpal1", "lCarpal2", "lCarpal3", "lCarpal4",
    "lIndex1", "lIndex2", "lIndex3",
    "lMid1", "lMid2", "lMid3",
    "lRing1", "lRing2", "lRing3",
    "lPinky1", "lPinky2", "lPinky3",

    "rHand",
    "rCarpal1", "rCarpal2", "rCarpal3", "rCarpal4",
    "rIndex1", "rIndex2", "rIndex3",
    "rMid1", "rMid2", "rMid3",
    "rRing1", "rRing2", "rRing3",
    "rPinky1", "rPinky2", "rPinky3",
]

ToeBones = [
    "lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
    "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2",

    "rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
    "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2",
]

Planes = {
    "lShldr" : ("lArm", ""),
    "lForeArm" : ("lArm", ""),
    "lHand" : ("", "lHand"),
    "lCarpal1" : ("", "lHand"),
    "lCarpal2" : ("", "lHand"),
    "lCarpal3" : ("", "lHand"),
    "lCarpal4" : ("", "lHand"),
    "lThumb1" : ("lThumb", ""),
    "lThumb2" : ("lThumb", ""),
    "lThumb3" : ("lThumb", ""),
    "lIndex1" : ("lIndex", "lHand"),
    "lIndex2" : ("lIndex", "lHand"),
    "lIndex3" : ("lIndex", "lHand"),
    "lMid1" : ("lMid", "lHand"),
    "lMid2" : ("lMid", "lHand"),
    "lMid3" : ("lMid", "lHand"),
    "lRing1" : ("lRing", "lHand"),
    "lRing2" : ("lRing", "lHand"),
    "lRing3" : ("lRing", "lHand"),
    "lPinky1" : ("lPinky", "lHand"),
    "lPinky2" : ("lPinky", "lHand"),
    "lPinky3" : ("lPinky", "lHand"),

    "rShldr" : ("rArm", ""),
    "rForeArm" : ("rArm", ""),
    "rHand" : ("", "rHand"),
    "rCarpal1" : ("", "rHand"),
    "rCarpal2" : ("", "rHand"),
    "rCarpal3" : ("", "rHand"),
    "rCarpal4" : ("", "rHand"),
    "rThumb1" : ("rThumb", ""),
    "rThumb2" : ("rThumb", ""),
    "rThumb3" : ("rThumb", ""),
    "rIndex1" : ("rIndex", "rHand"),
    "rIndex2" : ("rIndex", "rHand"),
    "rIndex3" : ("rIndex", "rHand"),
    "rMid1" : ("rMid", "rHand"),
    "rMid2" : ("rMid", "rHand"),
    "rMid3" : ("rMid", "rHand"),
    "rRing1" : ("rRing", "rHand"),
    "rRing2" : ("rRing", "rHand"),
    "rRing3" : ("rRing", "rHand"),
    "rPinky1" : ("rPinky", "rHand"),
    "rPinky2" : ("rPinky", "rHand"),
    "rPinky3" : ("rPinky", "rHand"),
}


def getTargetName(bname, rig):
    from .fix import getSuffixName
    bname = unquote(bname)
    if bname in rig.pose.bones.keys():
        return bname
    altnames = dict([(pb.DazAltName, pb.name) for pb in rig.pose.bones])
    if bname in altnames.keys():
        return altnames[bname]
    elif (bname in BoneAlternatives.keys() and
          BoneAlternatives[bname] in rig.pose.bones.keys()):
        return BoneAlternatives[bname]
    sufname = getSuffixName(bname)
    if sufname and sufname in rig.pose.bones.keys():
        return sufname
    return None

#-------------------------------------------------------------
#   BoneInstance
#-------------------------------------------------------------

class BoneInstance(Instance):

    def __init__(self, fileref, node, struct):
        from .figure import FigureInstance
        Instance.__init__(self, fileref, node, struct)
        if isinstance(self.parent, FigureInstance):
            self.figure = self.parent
        elif isinstance(self.parent, BoneInstance):
            self.figure = self.parent.figure
        self.translation = node.translation
        self.rotation = node.rotation
        self.scale = node.scale
        node.translation = []
        node.rotation = []
        node.scale = []
        self.name = self.node.name
        self.roll = 0.0
        self.useRoll = False
        self.axes = [0,1,2]
        self.flipped = [False,False,False]
        self.flopped = [False,False,False]
        self.isPosed = False
        self.isBuilt = False
        self.test = (self.name in [])


    def testPrint(self, hdr):
        if self.test:
            print(hdr, self.name, self.rotation_order, self.axes, self.flipped)


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        fname = (self.figure.name if self.figure else None)
        return "<BoneInst %s N: %s F: %s T: %s P: %s R:%s>" % (self.id, self.node.name, fname, self.target, pname, self.rna)


    def parentObject(self, context, ob):
        pass


    def buildExtra(self, context):
        pass


    def finalize(self, context):
        pass


    def getHeadTail(self, center, mayfit=True):
        if mayfit and self.restdata:
            head,tail,orient,xyz,origin,wsmat = self.restdata
            #head = (cp - center)
            #tail = (ep - center)
            if orient:
                x,y,z,w = orient
                orient = Quaternion((-w,x,y,z)).to_euler()
            else:
                orient = Euler(self.attributes["orientation"]*D)
                xyz = self.rotation_order
        else:
            head = (self.attributes["center_point"] - center)
            tail = (self.attributes["end_point"] - center)
            orient = Euler(self.attributes["orientation"]*D)
            xyz = self.rotation_order
            wsmat = self.U3
        if (tail-head).length < 0.1:
            tail = head + Vector((0,1,0))
        return head,tail,orient,xyz,wsmat

    RX = Matrix.Rotation(pi/2, 4, 'X')
    FX = Matrix.Rotation(pi, 4, 'X')
    FZ = Matrix.Rotation(pi, 4, 'Z')

    def buildEdit(self, figure, figinst, rig, parent, center, isFace):
        self.makeNameUnique(rig.data.edit_bones)
        head,tail,orient,xyz,wsmat = self.getHeadTail(center)
        eb = rig.data.edit_bones.new(self.name)
        figure.bones[self.name] = eb.name
        figinst.bones[self.name] = self
        if (head-tail).length < 1e-5:
            raise RuntimeError("BUG: buildEdit %s %s %s" % (self.name, head, tail))
        eb.parent = parent
        eb.head = head = d2b(head)
        eb.tail = tail = d2b(tail)
        length = (head-tail).length
        omat = orient.to_matrix()
        lsmat = self.getLocalMatrix(wsmat, omat)
        if not eulerIsZero(lsmat.to_euler()):
            self.isPosed = True
        omat = omat.to_4x4()
        if GS.zup:
            omat = self.RX @ omat
        flip = self.FX
        if not GS.unflipped:
            omat,flip = self.flipAxes(omat, xyz)

        #  engetudouiti's fix for posed bones
        rmat = wsmat.to_4x4()
        if GS.zup:
            rmat = self.RX @ rmat @ self.RX.inverted()
        if rmat.determinant() > 1e-4:
            omat = rmat.inverted() @ omat

        if GS.unflipped:
            omat.col[3][0:3] = head
            eb.matrix = omat
        else:
            omat = self.flipBone(omat, head, tail, flip)
            self.testPrint("FBONE")
            omat.col[3][0:3] = head
            eb.matrix = omat
            self.correctRoll(eb, figure)
        self.correctLength(eb, length)

        if GS.useConnectClose and parent:
            dist = parent.tail - eb.head
            if dist.length < 1e-4*LS.scale:
                eb.use_connect = True

        if self.name in ["upperFaceRig", "lowerFaceRig"]:
            isFace = True
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildEdit(figure, figinst, rig, eb, center, isFace)
        self.isBuilt = True


    def makeNameUnique(self, ebones):
        if self.name not in ebones.keys():
            return
        orig = self.name
        if len(self.name) < 2:
            self.name = "%s-1" % self.name
        while self.name in ebones.keys():
            if self.name[-2] == "-" and self.name[-1].isdigit():
                self.name = "%s-%d" % (self.name[:-2], 1+int(self.name[-1]))
            else:
                self.name = "%s-1" % self.name
        print("Bone name made unique: %s => %s" % (orig, self.name))


    def flipAxes(self, omat, xyz):
        if xyz == 'YZX':    #
            # Blender orientation: Y = twist, X = bend
            euler = Euler((0,0,0))
            flip = self.FX
            self.axes = [0,1,2]
            self.flipped = [False,False,False]
            self.flopped = [False,True,True]
        elif xyz == 'YXZ':
            # Apparently not used
            euler = Euler((0, pi/2, 0))
            flip = self.FZ
            self.axes = [2,1,0]
            self.flipped = [False,False,False]
            self.flopped = [False,False,False]
        elif xyz == 'ZYX':  #
            euler = Euler((pi/2, 0, 0))
            flip = self.FX
            self.axes = [0,2,1]
            self.flipped = [False,True,False]
            self.flopped = [False,False,False]
        elif xyz == 'XZY':  #
            euler = Euler((0, 0, pi/2))
            flip = self.FZ
            self.axes = [1,0,2]
            self.flipped = [False,False,False]
            self.flopped = [False,True,False]
        elif xyz == 'ZXY':
            # Eyes and eyelids
            euler = Euler((pi/2, 0, 0))
            flip = self.FZ
            self.axes = [0,2,1]
            self.flipped = [False,True,False]
            self.flopped = [False,False,False]
        elif xyz == 'XYZ':  #
            euler = Euler((pi/2, pi/2, 0))
            flip = self.FZ
            self.axes = [1,2,0]
            self.flipped = [True,True,True]
            self.flopped = [True,True,False]

        if self.test:
            print("AXES", self.name, xyz, self.axes)
        rmat = euler.to_matrix().to_4x4()
        omat = omat @ rmat
        return omat, flip


    def flipBone(self, omat, head, tail, flip):
        vec = tail-head
        yaxis = Vector(omat.col[1][0:3])
        if vec.dot(yaxis) < 0:
            if self.test:
                print("FLOP", self.name)
            self.flipped = self.flopped
            return omat @ flip
        else:
            return omat


    def correctRoll(self, eb, figure):
        if eb.name in RollCorrection.keys():
            offset = RollCorrection[eb.name]
        elif (figure.rigtype in ["genesis1", "genesis2"] and
              eb.name in RollCorrectionGenesis.keys()):
            offset = RollCorrectionGenesis[eb.name]
        else:
            return

        roll = eb.roll + offset*D
        if roll > pi:
            roll -= 2*pi
        elif roll < -pi:
            roll += 2*pi
        eb.roll = roll

        a = self.axes
        f = self.flipped
        i = a.index(0)
        j = a.index(1)
        k = a.index(2)
        if offset == 90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == -90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == 180:
            f[i] = not f[i]
            f[k] = not f[k]


    def correctLength(self, eb, length):
        vec = (eb.tail - eb.head).normalized()
        eb.tail = eb.head + length*vec


    def buildBoneProps(self, rig, center):
        if self.name not in rig.data.bones.keys():
            return
        bone = rig.data.bones[self.name]
        bone.use_inherit_scale = True
        bone.DazOrient = self.attributes["orientation"]

        head,tail,orient,xyz,wsmat = self.getHeadTail(center)
        head0,tail0,orient0,xyz0,wsmat0 = self.getHeadTail(center, False)
        bone.DazHead = head
        bone.DazTail = tail
        bone.DazAngle = 0

        vec = d2b00(tail) - d2b00(head)
        vec0 = d2b00(tail0) - d2b00(head0)
        if vec.length > 0 and vec0.length > 0:
            vec /= vec.length
            vec0 /= vec0.length
            sprod = vec.dot(vec0)
            if sprod < 0.99:
                bone.DazAngle = math.acos(sprod)
                bone.DazNormal = vec.cross(vec0)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)


    def buildFormulas(self, rig, hide):
        from .load_morph import buildBoneFormula
        if (self.node.formulas and
            self.name in rig.pose.bones.keys()):
            pb = rig.pose.bones[self.name]
            pb.rotation_mode = self.getRotationMode(pb, self.isRotMorph(self.node.formulas))
            errors = []
            buildBoneFormula(self.node, rig, errors)
        if hide or not self.getValue(["Visible"], True):
            self.figure.hiddenBones[self.name] = True
            bone = rig.data.bones[self.name]
            bone.hide = True
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, hide)


    def isRotMorph(self, formulas):
        for formula in formulas:
            if ("output" in formula.keys() and
                "?rotation" in formula["output"]):
                return True
        return False


    def findRoll(self, eb, figure, isFace):
        from .merge import GenesisToes
        if (self.getRollFromPlane(eb, figure)):
            return

        if self.name in RotateRoll.keys():
            rr = RotateRoll[self.name]
        elif isFace or self.name in ["lEye", "rEye"]:
            self.fixEye(eb)
            rr = -90
        elif self.name in GenesisToes["lToe"]:
            rr = -90
        elif self.name in GenesisToes["rToe"]:
            rr = 90
        elif self.name in FingerBones:
            if figure.rigtype == "genesis8":
                if self.name[0] == "l":
                    rr = 90
                else:
                    rr = -90
            else:
                rr = 180
        else:
            rr = 0

        nz = -1
        if self.name in ArmBones:
            nz = 2
        elif self.name in LegBones+ToeBones+FingerBones:
            nz = 0

        eb.roll = rr*D
        if nz >= 0:
            mat = eb.matrix.copy()
            mat[nz][2] = 0
            mat.normalize()
            eb.matrix = mat


    def fixEye(self, eb):
        vec = eb.tail - eb.head
        y = Vector((0,-1,0))
        if vec.dot(y) > 0.99*eb.length:
            eb.tail = eb.head + eb.length*y


    def getRollFromPlane(self, eb, figure):
        try:
            xplane,zplane = Planes[eb.name]
        except KeyError:
            return False
        if (zplane and
            zplane in self.figure.planes.keys() and
            (figure.rigtype in ["genesis3", "genesis8"] or
             not xplane)):
            zaxis = self.figure.planes[zplane]
            setRoll(eb, zaxis)
            eb.roll += pi/2
            if eb.roll > pi:
                eb.roll -= 2*pi
            return True
        elif (xplane and
              xplane in self.figure.planes.keys()):
            xaxis = self.figure.planes[xplane]
            setRoll(eb, xaxis)
            return True
        else:
            return False


    def getRotationMode(self, pb, useEulers):
        if GS.unflipped:
            return self.rotation_order
        elif useEulers:
            return self.getDefaultMode(pb)
        elif GS.useQuaternions and pb.name in SocketBones:
            return 'QUATERNION'
        else:
            return self.getDefaultMode(pb)


    def getDefaultMode(self, pb):
        if pb.name in RotationModes.keys():
            return RotationModes[pb.name]
        else:
            return 'YZX'


    def buildPose(self, figure, inFace, targets, missing):
        from .driver import isBoneDriven
        node = self.node
        rig = figure.rna
        if node.name not in rig.pose.bones.keys():
            return
        pb = rig.pose.bones[node.name]
        self.rna = pb
        if self.name != node.getName():
            pb.DazAltName = node.getName()
        if isBoneDriven(rig, pb):
            pb.rotation_mode = self.getRotationMode(pb, True)
            pb.bone.layers = [False,True] + 30*[False]
        else:
            pb.rotation_mode = self.getRotationMode(pb, False)
        pb.DazRotMode = self.rotation_order
        #pb.DazHeadLocal = pb.bone.head_local
        #pb.DazTailLocal = pb.bone.tail_local

        tchildren = self.targetTransform(pb, node, targets, rig)
        self.setRotationLockDaz(pb)
        self.setLocationLockDaz(pb)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(figure, inFace, tchildren, missing)


    def targetTransform(self, pb, node, targets, rig):
        from .node import setBoneTransform
        if LS.fitFile:
            return {}
        tname = getTargetName(node.name, rig)
        if tname and tname in targets.keys():
            tinst = targets[tname]
            tfm = Transform(
                trans = tinst.attributes["translation"],
                rot = tinst.attributes["rotation"])
            tchildren = tinst.children
        else:
            tinst = None
            tfm = Transform(
                trans = self.attributes["translation"],
                rot = self.attributes["rotation"])
            tchildren = {}
        setBoneTransform(tfm, pb)
        return tchildren


    def formulate(self, key, value):
        from .node import setBoneTransform
        if self.figure is None:
            return
        channel,comp = key.split("/")
        self.attributes[channel][getIndex(comp)] = value
        pb = self.rna
        node = self.node
        tfm = Transform(
            trans=self.attributes["translation"],
            rot=self.attributes["rotation"])
        setBoneTransform(tfm, pb)


    def getLocksLimits(self, pb, structs):
        locks = [False, False, False]
        limits = [None, None, None]
        useLimits = False
        for idx,comp in enumerate(structs):
            if "locked" in comp.keys() and comp["locked"]:
                locks[idx] = True
            elif "clamped"in comp.keys() and comp["clamped"]:
                if comp["min"] == 0 and comp["max"] == 0:
                    locks[idx] = True
                else:
                    limits[idx] = (comp["min"], comp["max"])
                    if comp["min"] != -180 or comp["max"] != 180:
                        useLimits = True
        return locks,limits,useLimits


    IndexComp = { 0 : "x", 1 : "y", 2 : "z" }

    def setRotationLockDaz(self, pb):
        locks,limits,useLimits = self.getLocksLimits(pb, self.rotation)
        if pb.rotation_mode == 'QUATERNION':
            return
        if GS.useLockRot:
            # DazRotLocks used to update lock_rotation
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.DazRotLocks[idx] = lock
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_rotation[idx] = lock
        if GS.useLimitRot and useLimits and not self.isPosed:
            cns = pb.constraints.new('LIMIT_ROTATION')
            cns.owner_space = 'LOCAL'
            for n,limit in enumerate(limits):
                idx = self.axes[n]
                if limit is not None:
                    mind, maxd = limit
                    minr = mind*D
                    if abs(minr) < 1e-4:
                        minr = 0
                    maxr = maxd*D
                    if abs(maxr) < 1e-4:
                        maxr = 0
                    if self.flipped[n]:
                        tmp = minr
                        minr = -maxr
                        maxr = -tmp
                    xyz = self.IndexComp[idx]
                    if self.test:
                        print("RRR", pb.name, n, limit, self.flipped[n], xyz, minr, maxr)
                    setattr(cns, "use_limit_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, minr)
                    setattr(cns, "max_%s" % xyz, maxr)
                    if GS.displayLimitRot:
                        setattr(pb, "use_ik_limit_%s" % xyz, True)
                        setattr(pb, "ik_min_%s" % xyz, minr)
                        setattr(pb, "ik_max_%s" % xyz, maxr)


    def setLocationLockDaz(self, pb):
        locks,limits,useLimits = self.getLocksLimits(pb, self.translation)
        if GS.useLockLoc:
            # DazLocLocks used to update lock_location
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.DazLocLocks[idx] = lock
            for n,lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_location[idx] = lock
        if GS.useLimitLoc and useLimits:
            cns = pb.constraints.new('LIMIT_LOCATION')
            cns.owner_space = 'LOCAL'
            for n,limit in enumerate(limits):
                idx = self.axes[n]
                if limit is not None:
                    mind, maxd = limit
                    if self.flipped[n]:
                        tmp = mind
                        mind = -maxd
                        maxd = -tmp
                    xyz = self.IndexComp[idx]
                    if self.test:
                        print("LLL", pb.name, n, self.axes, limit, self.flipped[n], xyz, mind, maxd)
                    setattr(cns, "use_min_%s" % xyz, True)
                    setattr(cns, "use_max_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, mind*LS.scale)
                    setattr(cns, "max_%s" % xyz, maxd*LS.scale)

#-------------------------------------------------------------
#   Bone
#-------------------------------------------------------------

def eulerIsZero(euler):
    vals = [abs(x) for x in euler]
    return (max(vals) < 1e-4)


def setRoll(eb, xaxis):
    yaxis = eb.tail - eb.head
    yaxis.normalize()
    xaxis -= yaxis.dot(xaxis)*yaxis
    xaxis.normalize()
    zaxis = xaxis.cross(yaxis)
    zaxis.normalize()
    eb.roll = getRoll(xaxis, yaxis, zaxis)


def getRoll(xaxis, yaxis, zaxis):
    mat = Matrix().to_3x3()
    mat.col[0] = xaxis
    mat.col[1] = yaxis
    mat.col[2] = zaxis
    return getRollFromQuat(mat.to_quaternion())


def getRollFromQuat(quat):
    if abs(quat.w) < 1e-4:
        roll = pi
    else:
        roll = 2*math.atan(quat.y/quat.w)
    return roll

#-------------------------------------------------------------
#   Bone
#-------------------------------------------------------------

class Bone(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.classType = Bone
        self.translation = []
        self.rotation = []
        self.scale = []


    def __repr__(self):
        return ("<Bone %s %s>" % (self.id, self.rna))


    def getSelfId(self):
        return self.node.name


    def makeInstance(self, fileref, struct):
        return BoneInstance(fileref, self, struct)


    def getInstance(self, ref, caller=None):
        iref = instRef(ref)
        if iref in self.instances.keys():
            return self.instances[iref]
        iref = unquote(iref)
        if iref in self.instances.keys():
            return self.instances[iref]
        try:
            return self.instances[BoneAlternatives[iref]]
        except KeyError:
            pass
        trgfig = self.figure.sourcing
        if trgfig:
            struct = {
                "id" : iref,
                "url" : self.url,
                "target" : trgfig,
            }
            inst = self.makeInstance(self.fileref, struct)
            self.instances[iref] = inst
            print("Creating reference to target figure:\n", inst)
            return inst
        if (GS.verbosity <= 2 and
            len(self.instances.values()) > 0):
            return list(self.instances.values())[0]
        msg = ("Bone: Did not find instance %s in %s" % (iref, list(self.instances.keys())))
        reportError(msg, trigger=(2,3))
        return None


    def parse(self, struct):
        from .figure import Figure
        Node.parse(self, struct)
        for channel,data in struct.items():
            if channel == "rotation":
                self.rotation = data
            elif channel == "translation":
                self.translation = data
            elif channel == "scale":
                self.scale = data
        if isinstance(self.parent, Figure):
            self.figure = self.parent
        elif isinstance(self.parent, Bone):
            self.figure = self.parent.figure


    def build(self, context, inst=None):
        pass


    def preprocess(self, context, inst):
        pass


    def preprocess2(self, context, inst):
        pass


    def poseRig(self, context, inst):
        pass

