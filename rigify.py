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



"""
Abstract

Postprocessing of rigify rig

"""

import bpy
import os
from collections import OrderedDict
from mathutils import Vector

from .error import *
from .utils import *
from .fix import Fixer, BendTwists

R_FACE = 1
R_DETAIL = 2
R_CUSTOM = 19
R_DEFORM = 29
R_HELP = 30

def setupTables(meta):
    global MetaBones, MetaParents, MetaDisconnect, RigifyParams
    global RigifySkeleton, GenesisCarpals, GenesisSpine
    global Genesis3Spine, Genesis3Mergers, Genesis3Parents
    global Genesis3Toes, Genesis3Renames
    global DeformBones, MhxRigifyLayer

    from .mhx import L_HELP, L_FACE, L_HEAD, L_CUSTOM
    MhxRigifyLayer = {
        L_HELP : R_HELP,
        L_FACE : R_DETAIL,
        L_HEAD : R_FACE,
        L_CUSTOM : R_CUSTOM
    }

    if meta.DazPre278:
        hips = "hips"
        spine = "spine"
        spine1 = "spine-1"
        chest = "chest"
        chest1 = "chest-1"
        neck = "neck"
        head = "head"
        rigtype = "rigify"

        MetaBones = {
            "spine" : spine,
            "spine-1" : spine1,
            "chest" : chest,
            "chest-1" : chest1,
            "chestUpper" : chest1,
            "neck" : neck,
            "head" : head,
        }

        RigifyParams = {}

        DeformBones = {
            "neckLower" : "DEF-neck",
            "neckUpper" : "DEF-neck",
            "ShldrBend" : "DEF-upper_arm.01.%s",
            "ForearmBend" : "DEF-forearm.01.%s",
            "ThighBend" : "DEF-thigh.01.%s",
            "ShldrTwist" : "DEF-upper_arm.02.%s",
            "ForearmTwist" : "DEF-forearm.02.%s",
            "ThighTwist" : "DEF-thigh.02.%s",
            "Shin" : "DEF-shin.02.%s",
        }

    else:
        hips = "spine"
        spine = "spine.001"
        spine1 = "spine.002"
        chest = "spine.003"
        chest1 = "spine.004"
        neck = "spine.005"
        if meta.DazUseSplitNeck:
            neck1= "spine.006"
            head = "spine.007"
        else:
            head = "spine.006"
        rigtype = "rigify2"
        bpy.ops.object.mode_set(mode='EDIT')
        eb = meta.data.edit_bones[head]
        deleteChildren(eb, meta)
        bpy.ops.object.mode_set(mode='OBJECT')

        MetaBones = {
            "spine" : hips,
            "spine-1" : spine1,
            "chest" : chest,
            "chest-1" : chest1,
            "chestUpper" : chest1,
            "neck" : neck,
            "head" : head,
        }

        RigifyParams = {
            ("spine", "neck_pos", 6),
            ("spine", "pivot_pos", 1),
        }

        DeformBones = {
            "neckLower" : "DEF-spine.005",
            "neckUpper" : "DEF-spine.006",
            "ShldrBend" : "DEF-upper_arm.%s",
            "ForearmBend" : "DEF-forearm.%s",
            "ThighBend" : "DEF-thigh.%s",
            "ShldrTwist" : "DEF-upper_arm.%s.001",
            "ForearmTwist" : "DEF-forearm.%s.001",
            "ThighTwist" : "DEF-thigh.%s.001",
            "Shin" : "DEF-shin.%s.001",
        }


    MetaDisconnect = [hips, neck]

    MetaParents = {
        "breast.L" : chest,
        "breast.R" : chest,
        "shoulder.L" : chest1,
        "shoulder.R" : chest1,
    }

    RigifySkeleton = {
    hips :            ("hip", ["hip", "pelvis"]),

    "thigh.L" :         "lThigh",
    "shin.L" :          "lShin",
    "foot.L" :          "lFoot",
    "toe.L" :           "lToe",

    "thigh.R" :         "rThigh",
    "shin.R" :          "rShin",
    "foot.R" :          "rFoot",
    "toe.R" :           "rToe",

    "abdomen" :         "abdomen",
    "chest" :           "chest",
    "neck" :            "neck",
    "head" :            "head",

    "shoulder.L" :      "lCollar",
    "upper_arm.L" :     "lShldr",
    "forearm.L" :       "lForeArm",
    "hand.L" :          "lHand",

    "shoulder.R" :      "rCollar",
    "upper_arm.R" :     "rShldr",
    "forearm.R" :       "rForeArm",
    "hand.R" :          "rHand",

    "thumb.01.L" :       "lThumb1",
    "thumb.02.L" :       "lThumb2",
    "thumb.03.L" :       "lThumb3",
    "f_index.01.L" :     "lIndex1",
    "f_index.02.L" :     "lIndex2",
    "f_index.03.L" :     "lIndex3",
    "f_middle.01.L" :    "lMid1",
    "f_middle.02.L" :    "lMid2",
    "f_middle.03.L" :    "lMid3",
    "f_ring.01.L" :      "lRing1",
    "f_ring.02.L" :      "lRing2",
    "f_ring.03.L" :      "lRing3",
    "f_pinky.01.L" :     "lPinky1",
    "f_pinky.02.L" :     "lPinky2",
    "f_pinky.03.L" :     "lPinky3",

    "thumb.01.R" :       "rThumb1",
    "thumb.02.R" :       "rThumb2",
    "thumb.03.R" :       "rThumb3",
    "f_index.01.R" :     "rIndex1",
    "f_index.02.R" :     "rIndex2",
    "f_index.03.R" :     "rIndex3",
    "f_middle.01.R" :    "rMid1",
    "f_middle.02.R" :    "rMid2",
    "f_middle.03.R" :    "rMid3",
    "f_ring.01.R" :      "rRing1",
    "f_ring.02.R" :      "rRing2",
    "f_ring.03.R" :      "rRing3",
    "f_pinky.01.R" :     "rPinky1",
    "f_pinky.02.R" :     "rPinky2",
    "f_pinky.03.R" :     "rPinky3",

    "palm.01.L" :       "lCarpal1",
    "palm.02.L" :       "lCarpal2",
    "palm.03.L" :       "lCarpal3",
    "palm.04.L" :       "lCarpal4",

    "palm.01.R" :       "rCarpal1",
    "palm.02.R" :       "rCarpal2",
    "palm.03.R" :       "rCarpal3",
    "palm.04.R" :       "rCarpal4",
    }

    BreastBones = {
    "breast.L" :        "lPectoral",
    "breast.R" :        "rPectoral",
    }
    if meta.DazUseBreasts:
        RigifySkeleton = addDicts([RigifySkeleton, BreastBones])


    GenesisCarpals = {
    "palm.01.L" :        (("lCarpal1", "lIndex1"), ["lCarpal1"]),
    "palm.02.L" :        (("lCarpal1", "lMid1"), []),
    "palm.03.L" :        (("lCarpal2", "lRing1"), ["lCarpal2"]),
    "palm.04.L" :        (("lCarpal2", "lPinky1"), []),

    "palm.01.R" :        (("rCarpal1", "rIndex1"), ["rCarpal1"]),
    "palm.02.R" :        (("rCarpal1", "rMid1"), []),
    "palm.03.R" :        (("rCarpal2", "rRing1"), ["rCarpal2"]),
    "palm.04.R" :        (("rCarpal2", "rPinky1"), []),

    }

    GenesisSpine = [
    ("abdomen", spine, hips),
    ("abdomen2", spine1, spine),
    ("chest", chest, spine1),
    ("neck", neck, chest),
    ("head", head, neck),
    ]

    Genesis3Spine = [
    ("abdomen", spine, hips),
    ("abdomen2", spine1, spine),
    ("chest", chest, spine1),
    ("chestUpper", chest1, chest),
    ("neck", neck, chest1),
    ]
    if meta.DazUseSplitNeck:
        Genesis3Spine += [
            ("neckUpper", neck1, neck),
            ("head", head, neck1)]
    else:
        Genesis3Spine.append(("head", head, neck))

    Genesis3Mergers = {
    "lShldrBend" : ["lShldrTwist"],
    "lForearmBend" : ["lForearmTwist"],
    "lThighBend" : ["lThighTwist"],
    "lFoot" : ["lMetatarsals"],

    "rShldrBend" : ["rShldrTwist"],
    "rForearmBend" : ["rForearmTwist"],
    "rThighBend" : ["rThighTwist"],
    "rFoot" : ["rMetatarsals"],
    }
    if not meta.DazUseSplitNeck:
        Genesis3Mergers["neckLower"] = ["neckUpper"]

    Genesis3Parents = {
    "neckLower" : "chestUpper",
    "chestUpper" : "chestLower",
    "chestLower" : "abdomenUpper",
    "abdomenUpper" : "abdomenLower",
    "lForearmBend" : "lShldrBend",
    "lHand" : "lForearmBend",
    "lShin" : "lThighBend",
    "lToe" : "lFoot",
    "rForearmBend" : "rShldrBend",
    "rHand" : "rForearmBend",
    "rShin" : "rThighBend",
    "rToe" : "rFoot",
    }
    if meta.DazUseSplitNeck:
        Genesis3Parents["head"] = "neckUpper"
        Genesis3Parents["neckUpper"] = "neckLower"
    else:
        Genesis3Parents["head"] = "neckLower"

    Genesis3Toes = {
    "lBigToe" : "lToe",
    "lSmallToe1" : "lToe",
    "lSmallToe2" : "lToe",
    "lSmallToe3" : "lToe",
    "lSmallToe4" : "lToe",
    "rBigToe" : "rToe",
    "rSmallToe1" : "rToe",
    "rSmallToe2" : "rToe",
    "rSmallToe3" : "rToe",
    "rSmallToe4" : "rToe",
    }

    Genesis3Renames = {
    "abdomenLower" : "abdomen",
    "abdomenUpper" : "abdomen2",
    "chestLower" : "chest",
    "neckLower" : "neck",
    "lShldrBend" : "lShldr",
    "lForearmBend" : "lForeArm",
    "lThighBend" : "lThigh",
    "rShldrBend" : "rShldr",
    "rForearmBend" : "rForeArm",
    "rThighBend" : "rThigh",
    }

    return rigtype, hips, head


def deleteChildren(eb, meta):
    for child in eb.children:
        deleteChildren(child, meta)
        meta.data.edit_bones.remove(child)


class DazBone:
    def __init__(self, eb):
        from .fix import ConstraintStore
        self.name = eb.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = None
        self.use_deform = eb.use_deform
        self.rotation_mode = None
        self.store = ConstraintStore()


    def getPose(self, pb):
        self.rotation_mode = pb.rotation_mode
        self.lock_location = pb.lock_location
        self.lock_rotation = pb.lock_rotation
        self.lock_scale = pb.lock_scale
        self.store.storeConstraints(pb.name, pb)


    def setPose(self, pb):
        pb.rotation_mode = self.rotation_mode
        pb.lock_location = self.lock_location
        pb.lock_rotation = self.lock_rotation
        pb.lock_scale = self.lock_scale
        self.store.restoreConstraints(pb.name, pb)


def addDicts(structs):
    joined = {}
    for struct in structs:
        for key,value in struct.items():
            joined[key] = value
    return joined


class Rigify:
    useAutoAlign : BoolProperty(
        name = "Auto Align Hand/Foot",
        description = "Auto align hand and foot (Rigify parameter)",
        default = False
    )

    useCustomLayers : BoolProperty(
        name = "Custom Layers",
        description = "Display layers for face and custom bones.\nNot for Rigify legacy",
        default = True
    )

    useKeepRig : BoolProperty(
        name = "Keep DAZ Rig",
        description = "Keep existing armature and meshes in a new collection",
        default = False
    )

    GroupBones = [("Face ", R_FACE, 2, 6),
                  ("Face (detail) ", R_DETAIL, 2, 3),
                  ("Custom ", R_CUSTOM, 13, 6)]

    def setupDazSkeleton(self, meta):
        rigifySkel = RigifySkeleton
        if meta.DazRigifyType in ["genesis1", "genesis2"]:
            rigifySkel["chestUpper"] = "chestUpper"
            rigifySkel["abdomen2"] = "abdomen2"
            spineBones = Genesis3Spine
        elif meta.DazRigifyType in ["genesis3", "genesis8"]:
            spineBones = Genesis3Spine

        dazskel = {}
        for rbone, dbone in rigifySkel.items():
            if isinstance(dbone, tuple):
                dbone = dbone[0]
            if isinstance(dbone, str):
                dazskel[dbone] = rbone
        return rigifySkel, spineBones, dazskel


    def renameBones(self, rig, bones):
        bpy.ops.object.mode_set(mode='EDIT')
        for dname,rname in bones.items():
            if dname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[dname]
                eb.name = rname
            else:
                raise DazError("Did not find bone %s     " % dname)
        bpy.ops.object.mode_set(mode='OBJECT')


    def fitToDaz(self, meta, rigifySkel, dazBones):
        for eb in meta.data.edit_bones:
            eb.use_connect = False

        for eb in meta.data.edit_bones:
            try:
                dname = rigifySkel[eb.name]
            except KeyError:
                dname = None
            if isinstance(dname, tuple):
                dname,_vgrps = dname
            if isinstance(dname, str):
                if dname in dazBones.keys():
                    dbone = dazBones[dname]
                    eb.head = dbone.head
                    eb.tail = dbone.tail
                    eb.roll = dbone.roll
            elif isinstance(dname, tuple):
                if (dname[0] in dazBones.keys() and
                    dname[1] in dazBones.keys()):
                    dbone1 = dazBones[dname[0]]
                    dbone2 = dazBones[dname[1]]
                    eb.head = dbone1.head
                    eb.tail = dbone2.head


    def fitHip(self, meta, hips, dazBones):
        hip = meta.data.edit_bones[hips]
        dbone = dazBones["hip"]
        hip.tail = Vector((1,2,3))
        hip.head = dbone.tail
        hip.tail = dbone.head
        return hip


    def fitLimbs(self, meta, hip):
        for suffix in [".L", ".R"]:
            shoulder = meta.data.edit_bones["shoulder"+suffix]
            upperarm = meta.data.edit_bones["upper_arm"+suffix]
            shin = meta.data.edit_bones["shin"+suffix]
            foot = meta.data.edit_bones["foot"+suffix]
            toe = meta.data.edit_bones["toe"+suffix]

            vec = shoulder.tail - shoulder.head
            if (upperarm.head - shoulder.tail).length < 0.02*vec.length:
                shoulder.tail -= 0.02*vec

            if "pelvis"+suffix in meta.data.edit_bones.keys():
                thigh = meta.data.edit_bones["thigh"+suffix]
                pelvis = meta.data.edit_bones["pelvis"+suffix]
                pelvis.head = hip.head
                pelvis.tail = thigh.head

            #if "breast"+suffix in meta.data.edit_bones.keys():
            #    breast = meta.data.edit_bones["breast"+suffix]
            #    breast.head[0] = breast.tail[0]
            #    breast.head[2] = breast.tail[2]

            foot.head = shin.tail
            toe.head = foot.tail
            xa,ya,za = foot.head
            xb,yb,zb = toe.head

            heelhead = foot.head
            heeltail = Vector((xa, yb-1.3*(yb-ya), zb))
            mid = (toe.head + heeltail)/2
            r = Vector((yb-ya,0,0))
            if xa > 0:
                fac = 0.3
            else:
                fac = -0.3
            heel02head = mid + fac*r
            heel02tail = mid - fac*r

            if "heel"+suffix in meta.data.edit_bones.keys():
                heel = meta.data.edit_bones["heel"+suffix]
                heel.head = heelhead
                heel.tail = heeltail
            if "heel.02"+suffix in meta.data.edit_bones.keys():
                heel02 = meta.data.edit_bones["heel.02"+suffix]
                heel02.head = heel02head
                heel02.tail = heel02tail


    def fitSpine(self, meta, spineBones, dazBones):
        mbones = meta.data.edit_bones
        for dname,rname,pname in spineBones:
            if dname not in dazBones.keys():
                continue
            dbone = dazBones[dname]
            if rname in mbones.keys():
                eb = mbones[rname]
            else:
                eb = mbones.new(dname)
                eb.name = rname
            eb.use_connect = False
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.parent = mbones[pname]
            eb.use_connect = True
            eb.layers = list(eb.parent.layers)


    def reparentBones(self, rig, parents):
        bpy.ops.object.mode_set(mode='EDIT')
        for bname,pname in parents.items():
            if (pname in rig.data.edit_bones.keys() and
                bname in rig.data.edit_bones.keys()):
                eb = rig.data.edit_bones[bname]
                parb = rig.data.edit_bones[pname]
                eb.use_connect = False
                eb.parent = parb
        bpy.ops.object.mode_set(mode='OBJECT')


    def addRigifyProps(self, meta):
        # Add rigify properties to spine bones
        bpy.ops.object.mode_set(mode='OBJECT')
        disconnect = []
        connect = []
        for pb in meta.pose.bones:
            if "rigify_type" in pb.keys():
                if pb["rigify_type"] == "":
                    pass
                elif pb["rigify_type"] == "spines.super_head":
                    disconnect.append(pb.name)
                elif pb["rigify_type"] == "limbs.super_finger":
                    connect += self.getChildren(pb)
                    pb.rigify_parameters.primary_rotation_axis = 'X'
                elif pb["rigify_type"] == "limbs.super_limb":
                    pb.rigify_parameters.rotation_axis = 'x'
                    pb.rigify_parameters.auto_align_extremity = self.useAutoAlign
                elif pb["rigify_type"] in [
                    "spines.super_spine",
                    "spines.basic_spine",
                    "basic.super_copy",
                    "limbs.super_palm",
                    "limbs.simple_tentacle"]:
                    pass
                else:
                    pass
                    #print("RIGIFYTYPE %s: %s" % (pb.name, pb["rigify_type"]))
        for rname,prop,value in RigifyParams:
            if rname in meta.pose.bones:
                pb = meta.pose.bones[rname]
                setattr(pb.rigify_parameters, prop, value)
        return connect, disconnect


    def addGroupBones(self, meta, rig):
        tail = (0,0,10*rig.DazScale)
        for bname,layer,row,group in self.GroupBones:
            eb = meta.data.edit_bones.new(bname)
            eb.head = (0,0,0)
            eb.tail = tail
            eb.layers = layer*[False] + [True] + (31-layer)*[False]


    def setupGroupBones(self, meta):
        for bname,layer,row,group in self.GroupBones:
            pb = meta.pose.bones[bname]
            pb["rigify_type"] = "basic.pivot"
            meta.data.layers[layer] = True
            rlayer = meta.data.rigify_layers[layer]
            rlayer.name = bname
            rlayer.row = row
            rlayer.group = group
        meta.data.layers[0] = False
        rlayer = meta.data.rigify_layers[0]
        rlayer.name = ""
        rlayer.group = 6


    def setConnected(self, meta, connect, disconnect):
        # Connect and disconnect bones that have to be so
        for rname in disconnect:
            eb = meta.data.edit_bones[rname]
            eb.use_connect = False
        for rname in connect:
            eb = meta.data.edit_bones[rname]
            eb.use_connect = True


    def recalcRoll(self, meta):
        # https://bitbucket.org/Diffeomorphic/import_daz/issues/199/rigi-fy-thigh_ik_targetl-and
        for eb in meta.data.edit_bones:
            eb.select = False
        for rname in ["thigh.L", "thigh.R", "shin.L", "shin.R"]:
            eb = meta.data.edit_bones[rname]
            eb.select = True
        bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y')


    def setupExtras(self, rig, rigifySkel, spineBones):
        extras = OrderedDict()
        taken = []
        for dbone,_rbone,_pbone in spineBones:
            taken.append(dbone)
        for _rbone, dbone in rigifySkel.items():
            if isinstance(dbone, tuple):
                dbone = dbone[0]
                if isinstance(dbone, tuple):
                    dbone = dbone[0]
            taken.append(dbone)
        for ob in rig.children:
            for vgrp in ob.vertex_groups:
                if (vgrp.name not in taken and
                    vgrp.name in rig.data.bones.keys()):
                    extras[vgrp.name] = vgrp.name
        for dbone in list(extras.keys()):
            bone = rig.data.bones[dbone]
            while bone.parent:
                pname = bone.parent.name
                if pname in extras.keys() or pname in taken:
                    break
                extras[pname] = pname
                bone = bone.parent
        return extras


    def splitBone(self, rig, bname, upname):
        if upname in rig.data.bones.keys():
            return
        bpy.ops.object.mode_set(mode='EDIT')
        eblow = rig.data.edit_bones[bname]
        vec = eblow.tail - eblow.head
        mid = eblow.head + vec/2
        ebup = rig.data.edit_bones.new(upname)
        for eb in eblow.children:
            eb.parent = ebup
        ebup.head = mid
        ebup.tail = eblow.tail
        ebup.parent = eblow
        ebup.roll = eblow.roll
        eblow.tail = mid
        bpy.ops.object.mode_set(mode='OBJECT')


    def splitNeck(self, meta):
        bpy.ops.object.mode_set(mode='EDIT')
        spine = meta.data.edit_bones["spine"]
        spine3 = meta.data.edit_bones["spine.003"]
        bonelist={}
        bpy.ops.armature.select_all(action='DESELECT')
        spine3.select = True
        bpy.ops.armature.subdivide()
        spinebones = spine.children_recursive_basename
        chainlength = len(spinebones)
        for x in range(chainlength):
            y = str(x)
            spinebones[x].name = "spine" + "." + y
        for x in range(chainlength):
            y = str(x+1)
            spinebones[x].name = "spine" + ".00" + y
        bpy.ops.armature.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')


    def deleteIfNotExist(self, bnames, rig, meta, context):
        setActiveObject(context, meta)
        bpy.ops.object.mode_set(mode='EDIT')
        for dname,mname in bnames:
            if (dname not in rig.data.bones.keys() and
                mname in meta.data.edit_bones.keys()):
                eb = meta.data.edit_bones[mname]
                meta.data.edit_bones.remove(eb)
        bpy.ops.object.mode_set(mode='OBJECT')
        setActiveObject(context, rig)


    def checkRigifyEnabled(self, context):
        for addon in context.user_preferences.addons:
            if addon.module == "rigify":
                return True
        return False


    def getRigifyBone(self, bname, dazSkel, extras, spineBones):
        global DeformBones
        if bname in DeformBones:
            return DeformBones[bname]
        if bname[1:] in DeformBones:
            prefix = bname[0]
            return (DeformBones[bname[1:]] % prefix.upper())
        if bname in dazSkel.keys():
            rname = dazSkel[bname]
            if rname in MetaBones.keys():
                return "DEF-" + MetaBones[rname]
            else:
                return "DEF-" + rname
        elif bname in extras.keys():
            return extras[bname]
        else:
            for dname,rname,pname in spineBones:
                if dname == bname:
                    return "DEF-" + rname
        print("MISS", bname)
        return None


    def getDazBones(self, rig):
        # Setup info about DAZ bones
        dazBones = OrderedDict()
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in rig.data.edit_bones:
            dazBones[eb.name] = DazBone(eb)
        bpy.ops.object.mode_set(mode='POSE')
        for pb in rig.pose.bones:
            dazBones[pb.name].getPose(pb)

        bpy.ops.object.mode_set(mode='OBJECT')
        return dazBones


    def createMeta(self, context):
        from collections import OrderedDict
        from .mhx import connectToParent, unhideAllObjects
        from .figure import getRigType
        from .merge import mergeBonesAndVgroups

        print("Create metarig")
        rig = context.object
        scale = rig.DazScale
        scn = context.scene
        if not(rig and rig.type == 'ARMATURE'):
            raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)

        unhideAllObjects(context, rig)

        # Create metarig
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            bpy.ops.object.armature_human_metarig_add()
        except AttributeError:
            raise DazError("The Rigify add-on is not enabled. It is found under rigging.")
        bpy.ops.object.location_clear()
        bpy.ops.object.rotation_clear()
        bpy.ops.object.scale_clear()
        bpy.ops.transform.resize(value=(100*scale, 100*scale, 100*scale))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        print("  Fix metarig")
        meta = context.object
        cns = meta.constraints.new('COPY_SCALE')
        cns.name = "Rigify Source"
        cns.target = rig
        cns.mute = True

        meta.DazPre278 = ("hips" in meta.data.bones.keys())
        meta.DazRigifyType = getRigType(rig)
        meta.DazUseBreasts = (not meta.DazPre278 and rig.data.DazExtraDrivenBones)
        meta.DazUseSplitNeck = (not meta.DazPre278 and meta.DazRigifyType in ["genesis3", "genesis8"])
        if meta.DazUseSplitNeck:
            self.splitNeck(meta)
        meta.DazRigType,hips,head = setupTables(meta)

        activateObject(context, rig)
        rig.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        print("  Fix bones")
        if meta.DazRigifyType in ["genesis1", "genesis2"]:
            self.fixPelvis(rig)
            self.fixCarpals(rig)
            self.splitBone(rig, "chest", "chestUpper")
            self.splitBone(rig, "abdomen", "abdomen2")
            delbones = [
                ("lPectoral", "breast.L"),
                ("rPectoral", "breast.R"),
            ]
            self.deleteIfNotExist(delbones, rig, meta, context)
        elif meta.DazRigifyType in ["genesis3", "genesis8"]:
            mergeBonesAndVgroups(rig, Genesis3Mergers, Genesis3Parents, context)
            self.reparentBones(rig, Genesis3Toes)
            self.renameBones(rig, Genesis3Renames)
        else:
            activateObject(context, meta)
            deleteObjects(context, [meta])
            raise DazError("Cannot rigify %s %s" % (meta.DazRigifyType, rig.name))

        print("  Connect to parent")
        connectToParent(rig)
        print("  Setup DAZ skeleton")
        rigifySkel, spineBones, dazSkel = self.setupDazSkeleton(meta)
        dazBones = self.getDazBones(rig)

        # Fit metarig to default DAZ rig
        print("  Fit to DAZ")
        #setActiveObject(context, meta)
        meta.select_set(True)
        activateObject(context, meta)
        bpy.ops.object.mode_set(mode='EDIT')
        self.fitToDaz(meta, rigifySkel, dazBones)
        hip = self.fitHip(meta, hips, dazBones)

        if meta.DazRigifyType in ["genesis3", "genesis8"]:
            eb = meta.data.edit_bones[head]
            eb.tail = eb.head + 1.0*(eb.tail - eb.head)

        self.fixHands(meta)
        self.fitLimbs(meta, hip)
        if self.useCustomLayers:
            self.addGroupBones(meta, rig)

        for eb in meta.data.edit_bones:
            if (eb.parent and
                eb.head == eb.parent.tail and
                eb.name not in MetaDisconnect):
                eb.use_connect = True

        self.fitSpine(meta, spineBones, dazBones)
        print("  Reparent bones")
        self.reparentBones(meta, MetaParents)
        print("  Add props to rigify")
        connect,disconnect = self.addRigifyProps(meta)
        if self.useCustomLayers:
            self.setupGroupBones(meta)

        print("  Set connected")
        bpy.ops.object.mode_set(mode='EDIT')
        self.setConnected(meta, connect, disconnect)
        self.recalcRoll(meta)
        bpy.ops.object.mode_set(mode='OBJECT')

        print("Metarig created")
        return meta


    def rigifyMeta(self, context):
        self.createTmp()
        try:
            self.rigifyMeta1(context)
        finally:
            self.deleteTmp()


    def rigifyMeta1(self, context):
        from .driver import getBoneDrivers, getPropDrivers
        from .node import setParent, clearParent
        from .propgroups import copyPropGroups
        from .mhx import unhideAllObjects, getBoneLayer
        from .hide import getRigCollection

        print("Rigify metarig")
        meta = context.object
        rig = None
        for cns in meta.constraints:
            if cns.type == 'COPY_SCALE' and cns.name == "Rigify Source":
                rig = cns.target

        if rig is None:
            raise DazError("Original rig not found")
        unhideAllObjects(context, rig)
        if not inSceneLayer(context, rig):
            context.collection.objects.link(rig)

        bpy.ops.object.mode_set(mode='POSE')
        for pb in meta.pose.bones:
            if hasattr(pb, "rigify_parameters"):
                if hasattr (pb.rigify_parameters, "roll_alignment"):
                    pb.rigify_parameters.roll_alignment = "manual"

        try:
            bpy.ops.pose.rigify_generate()
        except:
            raise DazError("Cannot rigify %s rig %s    " % (meta.DazRigifyType, rig.name))

        scn = context.scene
        gen = context.object
        coll = context.collection
        print("Fix generated rig", gen.name)

        print("  Setup DAZ Skeleton")
        setActiveObject(context, rig)
        rigifySkel, spineBones, dazSkel = self.setupDazSkeleton(meta)
        dazBones = self.getDazBones(rig)

        print("  Parent widgets")
        empty = bpy.data.objects.new("Widgets", None)
        coll.objects.link(empty)
        empty.parent = gen
        for ob in scn.collection.all_objects:
            if ob.parent is None and ob.name[0:4] == "WGT-":
                ob.parent = empty

        print("  Setup extras")
        extras = self.setupExtras(rig, rigifySkel, spineBones)
        if meta.DazUseBreasts:
            for prefix in ["l", "r"]:
                dname = drvBone(prefix+"Pectoral")
                extras[dname] = dname

        print("  Get driven bones")
        driven = {}
        for pb in rig.pose.bones:
            fcus = getBoneDrivers(rig, pb)
            if fcus:
                driven[pb.name] = fcus

        # Add extra bones to generated rig
        print("  Add extra bones")
        faceLayers = R_FACE*[False] + [True] + (31-R_FACE)*[False]
        helpLayers = R_HELP*[False] + [True] + (31-R_HELP)*[False]
        setActiveObject(context, gen)
        bpy.ops.object.mode_set(mode='EDIT')
        for dname,rname in extras.items():
            if dname not in dazBones.keys():
                continue
            dbone = dazBones[dname]
            eb = gen.data.edit_bones.new(rname)
            eb.head = dbone.head
            eb.tail = dbone.tail
            eb.roll = dbone.roll
            eb.use_deform = dbone.use_deform
            if eb.use_deform:
                eb.layers = faceLayers
                eb.layers[R_DEFORM] = True
            else:
                eb.layers = helpLayers
            if dname in driven.keys():
                eb.layers = helpLayers

        # Group bones
        print("  Create group bones")
        if self.useCustomLayers:
            for data in self.GroupBones:
                eb = gen.data.edit_bones[data[0]]
                eb.layers = helpLayers

        # Add parents to extra bones
        print("  Add parents to extra bones")
        for dname,rname in extras.items():
            if dname not in dazBones.keys():
                continue
            dbone = dazBones[dname]
            eb = gen.data.edit_bones[rname]
            if dbone.parent:
                pname = self.getRigifyBone(dbone.parent, dazSkel, extras, spineBones)
                if (pname in gen.data.edit_bones.keys()):
                    eb.parent = gen.data.edit_bones[pname]
                    eb.use_connect = (eb.parent != None and eb.parent.tail == eb.head)
                else:
                    print("No parent", dbone.name, dbone.parent, pname)
                    bones = list(dazSkel.keys())
                    bones.sort()
                    print("Bones:", bones)
                    msg = ("Bone %s has no parent %s" % (dbone.name, dbone.parent))
                    raise DazError(msg)

        if meta.DazUseBreasts:
            for prefix,suffix in [("l", ".L"), ("r", ".R")]:
                db = gen.data.edit_bones[drvBone(prefix + "Pectoral")]
                eb = gen.data.edit_bones["breast" + suffix]
                db.parent = eb.parent
                eb.parent = db

        bpy.ops.object.mode_set(mode='POSE')

        # Lock extras
        print("  Lock extras")
        for dname,rname in extras.items():
            if dname not in dazBones.keys():
                continue
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                dazBones[dname].setPose(pb)
                mhxlayer,unlock = getBoneLayer(pb, gen)
                layer = MhxRigifyLayer[mhxlayer]
                pb.bone.layers = layer*[False] + [True] + (31-layer)*[False]
                if unlock:
                    pb.lock_location = (False, False, False)
                self.copyBoneInfo(dname, rname, rig, gen)

        print("  Fix custom shapes")
        # Remove breast custom shapes, because they are placed differently in Daz
        for rname in ["breast.L", "breast.R"]:
            if rname in gen.pose.bones.keys():
                pb = gen.pose.bones[rname]
                pb.custom_shape = None

        # Rescale custom shapes
        if meta.DazRigifyType in ["genesis3", "genesis8"]:
            self.fixCustomShape(gen, ["head", "spine_fk.007"], 4)
        if bpy.app.version >= (2,82,0):
            self.fixCustomShape(gen, ["chest"], 1, Vector((0,-100*rig.DazScale,0)))

        # Add DAZ properties
        print("  Add DAZ properties")
        for key in rig.keys():
            self.copyProp(key, rig, gen)
        for key in rig.data.keys():
            self.copyProp(key, rig.data, gen.data)

        # Some more bones
        from .convert import getConverterEntry
        conv = getConverterEntry("genesis-" + meta.DazRigType)
        for srcname,trgname in conv.items():
            self.copyBoneInfo(srcname, trgname, rig, gen)

        # Handle bone parents
        print("  Handle bone parents")
        boneParents = []
        for ob in rig.children:
            if ob.parent_type == 'BONE':
                boneParents.append((ob, ob.parent_bone))
                clearParent(ob)

        for ob,dname in boneParents:
            rname = self.getRigifyBone(dname, dazSkel, extras, spineBones)
            if rname and rname in gen.data.bones.keys():
                print("Parent %s to bone %s" % (ob.name, rname))
                bone = gen.data.bones[rname]
                setParent(context, ob, gen, bone.name)
            else:
                print("Did not find bone parent %s %s" %(dname, rname))
                setParent(context, ob, gen, None)

        # Change vertex groups
        print("  Change vertex groups")
        activateObject(context, gen)
        for ob in rig.children:
            if ob.type == 'MESH':
                ob.parent = gen

                for dname,rname,_pname in spineBones:
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = "DEF-" + rname

                for rname,dname in rigifySkel.items():
                    if dname[1:] in ["Thigh", "Shin", "Shldr", "ForeArm"]:
                        self.rigifySplitGroup(rname, dname, ob, rig, True, meta)
                    elif (meta.DazPre278 and
                          dname[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]):
                        self.rigifySplitGroup(rname, dname, ob, rig, False, meta)
                    elif isinstance(dname, str):
                        if dname in ob.vertex_groups.keys():
                            vgrp = ob.vertex_groups[dname]
                            vgrp.name = "DEF-" + rname
                    else:
                        self.mergeVertexGroups(rname, dname[1], ob)

                for dname,rname in extras.items():
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = rname

                self.changeAllTargets(ob, rig, gen)

        # Fix drivers
        print("  Fix drivers")
        assoc = dict([(bname,bname) for bname in rig.data.bones.keys()])
        for daz,rigi,_ in Genesis3Spine:
            assoc[daz] = rigi
        for rigi,daz in RigifySkeleton.items():
            if isinstance(daz, tuple):
                daz = daz[0]
            assoc[daz] = rigi
        for fcu in getPropDrivers(rig):
            fcu2 = self.copyDriver(fcu, gen, old=rig, new=gen)
        for fcu in getPropDrivers(rig.data):
            fcu2 = self.copyDriver(fcu, gen.data, old=rig, new=gen)
        for bname, fcus in driven.items():
            if bname in gen.pose.bones.keys():
                pb = gen.pose.bones[bname]
                copyPropGroups(rig, gen, pb)
                for fcu in fcus:
                    self.copyBoneProp(fcu, rig, gen, pb)
                for fcu in fcus:
                    fcu2 = self.copyDriver(fcu, gen, old=rig, new=gen, assoc=assoc)

        # Fix correctives
        print("  Fix correctives")
        correctives = {}
        for dname,rname in assoc.items():
            if self.isCopyTransformed("ORG-"+rname, gen):
                correctives[dname] = "ORG-"+rname
            elif self.isCopyTransformed("DEF-"+rname, gen):
                correctives[dname] = "DEF-"+rname
            else:
                correctives[dname] = "ORG-"+rname
        self.fixBoneDrivers(gen, correctives)

        #Clean up
        print("  Clean up")
        setattr(gen.data, DrawType, 'STICK')
        setattr(gen, ShowXRay, True)
        gen.DazRig = meta.DazRigType
        name = rig.name
        coll = getRigCollection(rig)
        if coll:
            coll.objects.link(gen)
            coll.objects.link(meta)
            if gen.name in scn.collection.objects:
                scn.collection.objects.unlink(gen)
                scn.collection.objects.unlink(meta)
        activateObject(context, rig)
        deleteObjects(context, [rig])
        if self.useDeleteMeta:
            activateObject(context, meta)
            deleteObjects(context, [meta])
        activateObject(context, gen)
        gen.name = name
        bpy.ops.object.mode_set(mode='POSE')
        print("Rigify created")
        return gen


    def copyBoneProp(self, fcu, rig, gen, pb):
        bname = prop = None
        words = fcu.data_path.split('"')
        if words[0] == "pose.bones[" and words[2] == "][":
            bname = words[1]
            prop = words[3]
            if bname in rig.pose.bones.keys():
                self.copyProp(prop, rig.pose.bones[bname], pb)


    def copyBoneInfo(self, srcname, trgname, rig, gen):
        from .figure import copyBoneInfo
        if (srcname in rig.pose.bones.keys() and
            trgname in gen.pose.bones.keys()):
            srcpb = rig.pose.bones[srcname]
            trgpb = gen.pose.bones[trgname]
            copyBoneInfo(srcpb, trgpb)


    def copyProp(self, prop, src, trg):
        trg[prop] = src[prop]
        if prop[0:3] not in ["Daz", "_RN"]:
            setOverridable(trg, prop)


    def isCopyTransformed(self, bname, rig):
        if bname not in rig.pose.bones.keys():
            return False
        pb = rig.pose.bones[bname]
        for cns in pb.constraints:
            if cns.type == 'COPY_TRANSFORMS':
                return True
        return False


    def getChildren(self, pb):
        chlist = []
        for child in pb.children:
            chlist.append(child.name)
            chlist += self.getChildren(child)
        return chlist


    def rigifySplitGroup(self, rname, dname, ob, rig, before, meta):
        if dname not in ob.vertex_groups.keys():
            return
        bone = rig.data.bones[dname]
        if before:
            if meta.DazPre278:
                bendname = "DEF-" + rname[:-2] + ".01" + rname[-2:]
                twistname = "DEF-" + rname[:-2] + ".02" + rname[-2:]
            else:
                bendname = "DEF-" + rname
                twistname = "DEF-" + rname + ".001"
        else:
            bendname = "DEF-" + rname + ".01"
            twistname = "DEF-" + rname + ".02"
        self.splitVertexGroup(ob, dname, bendname, twistname, bone.head_local, bone.tail_local)


    def mergeVertexGroups(self, rname, dnames, ob):
        if not (dnames and
                dnames[0] in ob.vertex_groups.keys()):
            return
        vgrp = ob.vertex_groups[dnames[0]]
        vgrp.name = "DEF-" + rname


    def setBoneName(self, bone, gen):
        fkname = bone.name.replace(".", ".fk.")
        if fkname in gen.data.bones.keys():
            gen.data.bones[fkname]
            bone.fkname = fkname
            bone.ikname = fkname.replace(".fk.", ".ik")

        defname = "DEF-" + bone.name
        if defname in gen.data.bones.keys():
            gen.data.bones[defname]
            bone.realname = defname
            return

        defname1 = "DEF-" + bone.name + ".01"
        if defname in gen.data.bones.keys():
            gen.data.bones[defname1]
            bone.realname1 = defname1
            bone.realname2 = defname1.replace(".01.", ".02.")
            return

        defname1 = "DEF-" + bone.name.replace(".", ".01.")
        if defname in gen.data.bones.keys():
            gen.data.bones[defname1]
            bone.realname1 = defname1
            bone.realname2 = defname1.replace(".01.", ".02")
            return

        if bone.name in gen.data.bones.keys():
            gen.data.edit_bones[bone.name]
            bone.realname = bone.name

#-------------------------------------------------------------
#  Buttons
#-------------------------------------------------------------

class DAZ_OT_ConvertToRigify(DazPropsOperator, Rigify, Fixer, BendTwists):
    bl_idname = "daz.convert_to_rigify"
    bl_label = "Convert To Rigify"
    bl_description = "Convert active rig to rigify"
    bl_options = {'UNDO'}

    useDeleteMeta : BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = False
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazRigifyType)

    def __init__(self):
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useAutoAlign")
        self.layout.prop(self, "useDeleteMeta")
        self.layout.prop(self, "useCustomLayers")
        self.layout.prop(self, "useKeepRig")

    def run(self, context):
        import time
        t1 = time.perf_counter()
        print("Modifying DAZ rig to Rigify")
        rig = context.object
        rname = rig.name
        if self.useKeepRig:
            from .mhx import saveExistingRig
            saveExistingRig(context)
        self.createMeta(context)
        gen = self.rigifyMeta(context)
        t2 = time.perf_counter()
        print("DAZ rig %s successfully rigified in %.3f seconds" % (rname, t2-t1))


class DAZ_OT_CreateMeta(DazPropsOperator, Rigify, Fixer, BendTwists):
    bl_idname = "daz.create_meta"
    bl_label = "Create Metarig"
    bl_description = "Create a metarig from the active rig"
    bl_options = {'UNDO'}

    useAutoAlign = False
    useDeleteMeta = False

    def __init__(self):
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useCustomLayers")
        self.layout.prop(self, "useKeepRig")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazRigifyType)

    def run(self, context):
        if self.useKeepRig:
            from .mhx import saveExistingRig
            saveExistingRig(context)
        self.createMeta(context)


class DAZ_OT_RigifyMetaRig(DazPropsOperator, Rigify, Fixer, BendTwists):
    bl_idname = "daz.rigify_meta"
    bl_label = "Rigify Metarig"
    bl_description = "Convert metarig to rigify"
    bl_options = {'UNDO'}

    useKeepRig = False
    useDeleteMeta = False

    def __init__(self):
        Fixer.__init__(self)

    def draw(self, context):
        self.layout.prop(self, "useAutoAlign")
        self.layout.prop(self, "useCustomLayers")

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazRigifyType)

    def run(self, context):
        self.rigifyMeta(context)

#-------------------------------------------------------------
#   Set rigify to FK. For load pose.
#-------------------------------------------------------------

def setToFk1(rig, layers):
    for bname in ["hand.ik.L", "hand.ik.R", "foot.ik.L", "foot.ik.R"]:
        pb = rig.pose.bones[bname]
        pb["ik_fk_switch"] = 0.0
    if "head.001" in rig.pose.bones.keys():
        pb = rig.pose.bones["head.001"]
        pb["neck_follow"] = 0.0
    return layers


def setToFk2(rig, layers):
    for bname in ["upper_arm_parent.L", "upper_arm_parent.R", "thigh_parent.L", "thigh_parent.R"]:
        pb = rig.pose.bones[bname]
        pb["IK_FK"] = 0.0
    if "torso" in rig.pose.bones.keys():
        pb = rig.pose.bones["torso"]
        pb["neck_follow"] = 1.0
        pb["head_follow"] = 1.0
    for n in [8, 11, 14, 17]:
        layers[n] = True
    for n in [7, 10, 13, 16]:
        layers[n] = False
    return layers

#-------------------------------------------------------------
#   List bones
#-------------------------------------------------------------

def listBones(context):
    rig = context.object
    if not (rig and rig.type == 'ARMATURE'):
        msg = ("Not an armature:   \n'%s'       " % rig)
        raise DazError(msg)
    print("Bones in %s:" % rig.name)
    for pb in rig.pose.bones:
        print('    "%s" : ("", "%s"),' % (pb.name, pb.rotation_mode))


class DAZ_OT_ListBones(DazOperator, IsArmature):
    bl_idname = "daz.list_bones"
    bl_label = "List Bones"
    bl_options = {'UNDO'}

    def run(self, context):
        listBones(context)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ConvertToRigify,
    DAZ_OT_CreateMeta,
    DAZ_OT_RigifyMetaRig,
    DAZ_OT_ListBones,
]

def register():
    bpy.types.Object.DazRigifyType = StringProperty(default="")
    bpy.types.Object.DazRigType = StringProperty(default="")
    bpy.types.Object.DazUseBreasts = BoolProperty(default=False)
    bpy.types.Object.DazUseSplitNeck = BoolProperty(default=False)
    bpy.types.Object.DazPre278 = BoolProperty(default=False)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
