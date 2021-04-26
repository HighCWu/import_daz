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
import os
from mathutils import *
from .error import *
from .utils import *
from .driver import DriverUser

#-------------------------------------------------------------
#   Fixer class
#-------------------------------------------------------------

class Fixer(DriverUser):

    def fixPelvis(self, rig):
        bpy.ops.object.mode_set(mode='EDIT')
        hip = rig.data.edit_bones["hip"]
        if hip.tail[2] > hip.head[2]:
            for child in hip.children:
                child.use_connect = False
            head = Vector(hip.head)
            tail = Vector(hip.tail)
            hip.head = Vector((1,2,3))
            hip.tail = head
            hip.head = tail
        if "pelvis" not in rig.data.bones.keys():
            pelvis = rig.data.edit_bones.new("pelvis")
            pelvis.head = hip.head
            pelvis.tail = hip.tail
            pelvis.roll = hip.roll
            pelvis.parent = hip
            lThigh = rig.data.edit_bones["lThigh"]
            rThigh = rig.data.edit_bones["rThigh"]
            lThigh.parent = pelvis
            rThigh.parent = pelvis
        bpy.ops.object.mode_set(mode='OBJECT')


    def fixCustomShape(self, rig, bnames, factor, offset=0):
        for bname in bnames:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                if pb.custom_shape:
                    pb.custom_shape_scale = factor
                    if offset:
                        for v in pb.custom_shape.data.vertices:
                            v.co += offset
                return


    def fixHands(self, rig):
        bpy.ops.object.mode_set(mode='EDIT')
        for suffix in [".L", ".R"]:
            forearm = rig.data.edit_bones["forearm"+suffix]
            hand = rig.data.edit_bones["hand"+suffix]
            hand.head = forearm.tail
            flen = (forearm.tail - forearm.head).length
            vec = hand.tail - hand.head
            hand.tail = hand.head + 0.35*flen/vec.length*vec


    def fixCarpals(self, rig):
        Carpals = {
            "Carpal1" : "Index1",
            "Carpal2" : "Mid1",
            "Carpal3" : "Ring1",
            "Carpal4" : "Pinky1",
        }

        if "lCarpal3" in rig.data.bones.keys():
            return
        bpy.ops.object.mode_set(mode='EDIT')
        for prefix in ["l", "r"]:
            for bname in ["Carpal1", "Carpal2"]:
                if prefix+bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[prefix+bname]
                    rig.data.edit_bones.remove(eb)
            hand = rig.data.edit_bones[prefix+"Hand"]
            hand.tail = 2*hand.tail - hand.head
            for bname,cname in Carpals.items():
                if prefix+cname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones.new(prefix+bname)
                    child = rig.data.edit_bones[prefix+cname]
                    eb.head = hand.head
                    eb.tail = child.head
                    eb.roll = child.roll
                    eb.parent = hand
                    child.parent = eb
                    child.use_connect = True
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in rig.children:
            if ob.type == 'MESH':
                for prefix in ["l", "r"]:
                    for vgrp in ob.vertex_groups:
                        if vgrp.name == prefix+"Carpal2":
                            vgrp.name = prefix+"Carpal4"


    def fixKnees(self, rig):
        from .bone import setRoll
        eps = 0.5
        bpy.ops.object.mode_set(mode='EDIT')
        for thigh,shin,zaxis in self.Knees:
            eb1 = rig.data.edit_bones[thigh]
            eb2 = rig.data.edit_bones[shin]
            hip = eb1.head
            knee = eb2.head
            ankle = eb2.tail
            dankle = ankle-hip
            vec = ankle-hip
            vec.normalize()
            dknee = knee-hip
            dmid = vec.dot(dknee)*vec
            offs = dknee-dmid
            if offs.length/dknee.length < eps:
                knee = hip + dmid + zaxis*offs.length
                xaxis = zaxis.cross(vec)
            else:
                xaxis = vec.cross(dknee)
                xaxis.normalize()

            eb1.tail = eb2.head = knee
            setRoll(eb1, xaxis)
            eb2.roll = eb1.roll


    def fixBoneDrivers(self, rig, assoc0):
        def changeTargets(rna, rig):
            if rna.animation_data:
                drivers = list(rna.animation_data.drivers)
                print("    (%s %d)" % (rna.name, len(drivers)))
                for n,fcu in enumerate(drivers):
                    self.changeTarget(fcu, rna, rig, assoc)

        assoc = dict([(bname,bname) for bname in rig.data.bones.keys()])
        for dname,bname in assoc0.items():
            assoc[dname] = bname
        changeTargets(rig, rig)
        changeTargets(rig.data, rig)
        for ob in rig.children:
            changeTargets(ob, rig)
            if ob.type == 'MESH' and ob.data.shape_keys:
                changeTargets(ob.data.shape_keys, rig)


    def changeTarget(self, fcu, rna, rig, assoc):
        channel = fcu.data_path
        idx = self.getArrayIndex(fcu)
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        success = True
        for var in fcu2.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT':
                    trg.id = rig
                elif trg.id_type == 'ARMATURE':
                    trg.id = rig.data
                if var.type == 'TRANSFORMS':
                    bname = trg.bone_target
                    defbone = "DEF-" + bname
                    if bname in assoc.keys():
                        trg.bone_target = assoc[bname]
                    elif defbone in rig.pose.bones.keys():
                        trg.bone_target = defbone
                    else:
                        success = False
        if success:
            fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
            fcu3.data_path = channel
            if idx >= 0:
                fcu3.array_index = idx
        self.clearTmpDriver(0)


    def changeAllTargets(self, ob, rig, newrig):
        if ob.animation_data:
            for fcu in ob.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.data.animation_data:
            for fcu in ob.data.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.type == 'MESH':
            if ob.data.shape_keys and ob.data.shape_keys.animation_data:
                for fcu in ob.data.shape_keys.animation_data.drivers:
                    self.setId(fcu, rig, newrig)
            for mod in ob.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    mod.object = newrig


    def saveExistingRig(self, context):
        def dazName(string):
            return (string + "_DAZ")

        def dazifyName(ob):
            if ob.name[-4] == "." and ob.name[-3:].isdigit():
                return dazName(ob.name[:-4])
            else:
                return dazName(ob.name)

        def findChildrenRecursive(ob, objects):
            objects.append(ob)
            for child in ob.children:
                if not getHideViewport(child):
                    findChildrenRecursive(child, objects)

        rig = context.object
        scn = context.scene
        activateObject(context, rig)
        objects = []
        findChildrenRecursive(rig, objects)
        for ob in objects:
            ob.select_set(True)
        bpy.ops.object.duplicate()
        coll = bpy.data.collections.new(name=dazName(rig.name))
        mcoll = bpy.data.collections.new(name=dazName(rig.name) + " Meshes")
        scn.collection.children.link(coll)
        coll.children.link(mcoll)

        newObjects = getSelectedObjects(context)
        nrig = None
        for ob in newObjects:
            ob.name = dazifyName(ob)
            if ob.name == dazifyName(rig):
                nrig = ob
            unlinkAll(ob)
            if ob.type == 'MESH':
                mcoll.objects.link(ob)
            else:
                coll.objects.link(ob)
        if nrig:
            for ob in newObjects:
                self.changeAllTargets(ob, rig, nrig)
        activateObject(context, rig)

    #-------------------------------------------------------------
    #   Face Bone
    #-------------------------------------------------------------

    def isFaceBone(self, pb):
        if pb.parent:
            par = pb.parent
            if par.name in ["upperFaceRig", "lowerFaceRig"]:
                return True
            elif (isDrvBone(par.name) and
                  par.parent and
                  par.parent.name in ["upperFaceRig", "lowerFaceRig"]):
                return True
        return False


    def isEyeLid(self, pb):
        return ("eyelid" in pb.name.lower())

#-------------------------------------------------------------
#   Gizmos (custom shapes)
#-------------------------------------------------------------

class GizmoUser:
    def startGizmos(self, context):
        self.gizmos = {}
        self.hidden = createHiddenCollection(context, None)


    def makeGizmos(self, gnames):
        self.makeEmptyGizmo("GZM_Circle", 'CIRCLE')
        self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        self.makeEmptyGizmo("GZM_Cone", 'CONE')

        from .load_json import loadJson
        folder = os.path.dirname(__file__)
        filepath = os.path.join(folder, "data", "gizmos.json")
        struct = loadJson(filepath)
        if gnames is None:
            gnames = struct.keys()
        for gname in gnames:
            gizmo = struct[gname]
            me = bpy.data.meshes.new(gname)
            me.from_pydata(gizmo["verts"], gizmo["edges"], [])
            ob = self.makeGizmo(gname, me)
            if gizmo["subsurf"]:
                ob.modifiers.new('SUBSURF', 'SUBSURF')


    def makeGizmo(self, gname, me, parent=None):
        ob = bpy.data.objects.new(gname, me)
        self.hidden.objects.link(ob)
        ob.parent = parent
        putOnHiddenLayer(ob)
        self.gizmos[gname] = ob
        return ob


    def makeEmptyGizmo(self, gname, dtype):
        empty = self.makeGizmo(gname, None)
        empty.empty_display_type = dtype
        return empty


    def addGizmo(self, pb, gname, scale, blen=None):
        gizmo = self.gizmos[gname]
        pb.custom_shape = gizmo
        pb.bone.show_wire = True
        if blen:
            pb.custom_shape_scale = blen/pb.bone.length
        else:
            pb.custom_shape_scale = scale


    def renameFaceBones(self, rig):

        def renameFaceBone(bone):
            bname = bone.name
            if isDrvBone(bname) or isFinal(bname):
                return
            if len(bname) >= 2 and bname[1].isupper():
                if bname[0] == "r":
                    newname = bname[1].lower() + bname[2:] + ".R"
                    renamed[bname] = newname
                    bone.name = newname
                elif bname[0] == "l":
                    newname = bname[1].lower() + bname[2:] + ".L"
                    renamed[bname] = newname
                    bone.name = newname
            elif bname[0].isupper():
                newname = bname[0].lower() + bname[1:]
                renamed[bname] = newname
                bone.name = newname

        if not self.useRenameFaceBones:
            return
        renamed = {}
        for pb in rig.pose.bones:
            if self.isFaceBone(pb):
                renameFaceBone(pb.bone)
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if (hasattr(cns, "subtarget") and
                    cns.subtarget in renamed.keys()):
                    cns.subtarget = renamed[cns.subtarget]


#-------------------------------------------------------------
#   Constraints class
#-------------------------------------------------------------

ConstraintAttributes = [
    "type", "name", "mute", "target", "subtarget",
    "head_tail", "use_offset", "owner_space", "target_space",
    "use_x", "use_y", "use_z",
    "invert_x", "invert_y", "invert_z",
    "use_limit_x", "use_limit_y", "use_limit_z",
    "use_min_x", "use_min_y", "use_min_z",
    "use_max_x", "use_max_y", "use_max_z",
    "min_x", "min_y", "min_z",
    "max_x", "max_y", "max_z",
]

def copyConstraints(src, trg, rig=None):
    for scns in src.constraints:
        tcns = trg.constraints.new(scns.type)
        for attr in ConstraintAttributes:
            if (hasattr(scns, attr) and attr != "type"):
                setattr(tcns, attr, getattr(scns, attr))
        if rig and hasattr(tcns, "target"):
            tcns.target = rig


class ConstraintStore:
    def __init__(self):
        self.constraints = {}


    def storeConstraints(self, key, pb):
        clist = []
        for cns in pb.constraints:
            struct = {}
            for attr in ConstraintAttributes:
                if hasattr(cns, attr):
                    struct[attr] = getattr(cns, attr)
            clist.append(struct)
        if clist:
            self.constraints[key] = clist


    def storeAllConstraints(self, rig):
        for pb in rig.pose.bones:
            self.storeConstraints(pb.name, pb)
            self.removeConstraints(pb)


    def getFkBone(self, key, rig):
        if key[-2] == ".":
            base, suffix = key[:-2], key[-1]
            bname = base + ".fk." + suffix
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
            bname = base + "_fk." + suffix
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
        if key in rig.pose.bones.keys():
            return rig.pose.bones[key]
        return None


    def restoreAllConstraints(self, rig):
        for key,clist in self.constraints.items():
            pb = self.getFkBone(key, rig)
            if pb is None:
                continue
            for struct in clist:
                self.restoreConstraint(struct, pb)


    def restoreConstraints(self, key, pb):
        if key not in self.constraints.keys():
            return
        clist = self.constraints[key]
        for struct in clist:
            self.restoreConstraint(struct, pb)


    def restoreConstraint(self, struct, pb):
        cns = pb.constraints.new(struct["type"])
        for attr,value in struct.items():
            if attr != "type":
                setattr(cns, attr, value)


    def removeConstraints(self, pb):
        for cns in list(pb.constraints):
            cns.driver_remove("influence")
            cns.driver_remove("mute")
            pb.constraints.remove(cns)

#-------------------------------------------------------------
#   BendTwist class
#-------------------------------------------------------------

class BendTwists:

    def getBendTwistNames(self, bname):
        words = bname.split(".", 1)
        if len(words) == 2:
            bendname = words[0] + "Bend." + words[1]
            twistname = words[0] + "Twist." + words[1]
        else:
            bendname = bname + "Bend"
            twistname = bname + "Twist"
        return bendname, twistname


    def joinBendTwists(self, rig, renames, keep=True):
        hiddenLayer = 31*[False] + [True]

        rotmodes = {}
        bpy.ops.object.mode_set(mode='POSE')
        for bname,tname in self.BendTwists:
            bendname,twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.pose.bones.keys() and
                    twistname in rig.pose.bones.keys()):
                continue
            pb = rig.pose.bones[bendname]
            rotmodes[bname] = pb.DazRotMode
            self.storeConstraints(bname, pb)
            self.removeConstraints(pb)
            pb = rig.pose.bones[twistname]
            self.removeConstraints(pb)

        bpy.ops.object.mode_set(mode='EDIT')
        for bname,tname in self.BendTwists:
            bendname,twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.data.edit_bones.keys() and
                    twistname in rig.data.edit_bones.keys()):
                continue
            eb = rig.data.edit_bones.new(bname)
            bend = rig.data.edit_bones[bendname]
            twist = rig.data.edit_bones[twistname]
            target = rig.data.edit_bones[tname]
            eb.head = bend.head
            bend.tail = twist.head
            eb.tail = twist.tail = target.head
            eb.roll = bend.roll
            eb.parent = bend.parent
            eb.use_deform = False
            eb.use_connect = bend.use_connect
            children = [eb for eb in bend.children if eb != twist] + list(twist.children)
            for child in children:
                child.parent = eb

        for bname3,bname2 in renames.items():
            eb = rig.data.edit_bones[bname3]
            eb.name = bname2

        bpy.ops.object.mode_set(mode='OBJECT')
        for bname,rotmode in rotmodes.items():
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                pb.DazRotMode = rotmode

        from .figure import copyBoneInfo
        for bname,tname in self.BendTwists:
            bendname,twistname = self.getBendTwistNames(bname)
            if not bendname in rig.data.bones.keys():
                continue
            srcbone = rig.pose.bones[bendname]
            trgbone = rig.pose.bones[bname]
            copyBoneInfo(srcbone, trgbone)

        bpy.ops.object.mode_set(mode='EDIT')
        for bname,tname in self.BendTwists:
            bendname,twistname = self.getBendTwistNames(bname)
            if bendname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bendname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)
            if twistname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[twistname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)

        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in rig.children:
            for bname,tname in self.BendTwists:
                bend,twist = self.getBendTwistNames(bname)
                self.joinVertexGroups(ob, bname, bend, twist)


    def joinVertexGroups(self, ob, bname, bend, twist):
        vgbend = vgtwist = None
        if bend in ob.vertex_groups.keys():
            vgbend = ob.vertex_groups[bend]
        if twist in ob.vertex_groups.keys():
            vgtwist = ob.vertex_groups[twist]
        if vgbend is None and vgtwist is None:
            return
        elif vgbend is None:
            vgtwist.name = bname
            return
        elif vgtwist is None:
            vgbend.name = bname
            return

        vgrp = ob.vertex_groups.new(name=bname)
        indices = [vgbend.index, vgtwist.index]
        for v in ob.data.vertices:
            w = 0.0
            for g in v.groups:
                if g.group in indices:
                    w += g.weight
            if w > 1e-4:
                vgrp.add([v.index], w, 'REPLACE')
        ob.vertex_groups.remove(vgbend)
        ob.vertex_groups.remove(vgtwist)


    def getSubBoneNames(self, bname):
        base,suffix = bname.split(".")
        bname0 = base + "-0." + suffix
        bname1 = base + "-1." + suffix
        bname2 = base + "-2." + suffix
        return bname0,bname1,bname2


    def createBendTwists(self, rig):
        hiddenLayer = 31*[False] + [True]
        bpy.ops.object.mode_set(mode='EDIT')

        for bname,_ in self.BendTwists:
            eb = rig.data.edit_bones[bname]
            vec = eb.tail - eb.head
            bname0,bname1,bname2 = self.getSubBoneNames(bname)
            eb0 = rig.data.edit_bones.new(bname0)
            eb1 = rig.data.edit_bones.new(bname1)
            eb2 = rig.data.edit_bones.new(bname2)
            eb0.head = eb1.head = eb.head
            eb0.tail = eb1.tail = eb2.head = eb.head+vec/2
            eb2.tail = eb.tail
            eb0.roll = eb1.roll = eb2.roll = eb.roll
            eb0.parent = eb1.parent = eb.parent
            eb2.parent = eb0
            eb0.use_connect = eb1.use_connect = eb.use_connect
            eb2.use_connect = True
            eb.use_deform = False
            eb0.use_deform = False
            eb1.use_deform = eb2.use_deform = True
            eb0.layers = eb1.layers = eb2.layers = hiddenLayer

            for ob in rig.children:
                if (ob.type == 'MESH' and
                    self.getVertexGroup(ob, bname)):
                    self.splitVertexGroup2(ob, bname, eb.head, eb.tail)


    def getVertexGroup(self, ob, vgname):
        for vgrp in ob.vertex_groups:
            if vgrp.name == vgname:
                return vgrp
        return None


    def splitVertexGroup2(self, ob, bname, head, tail):
        vgrp = self.getVertexGroup(ob, bname)
        bname0,bname1,bname2 = self.getSubBoneNames(bname)
        vgrp1 = ob.vertex_groups.new(name=bname1)
        vgrp2 = ob.vertex_groups.new(name=bname2)
        vec = tail-head
        vec /= vec.dot(vec)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = vec.dot(v.co - head)
                    if x < 0:
                        vgrp1.add([v.index], g.weight, 'REPLACE')
                    elif x < 1:
                        vgrp1.add([v.index], g.weight*(1-x), 'REPLACE')
                        vgrp2.add([v.index], g.weight*(x), 'REPLACE')
                    elif x > 1:
                        vgrp2.add([v.index], g.weight, 'REPLACE')
        ob.vertex_groups.remove(vgrp)


    def splitVertexGroup(self, ob, vgname, bendname, twistname, head, tail):
        vgrp = self.getVertexGroup(ob, vgname)
        bend = ob.vertex_groups.new(name=bendname)
        twist = ob.vertex_groups.new(name=twistname)
        vec = tail-head
        vec /= vec.dot(vec)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = vec.dot(v.co - head)
                    if x < 0:
                        x = 0
                    elif x > 1:
                        x = 1
                    bend.add([v.index], g.weight*(1-x), 'REPLACE')
                    twist.add([v.index], g.weight*x, 'REPLACE')
        ob.vertex_groups.remove(vgrp)


    def constrainBendTwists(self, rig):
        from .utils import hasPoseBones
        bpy.ops.object.mode_set(mode='POSE')

        for bname,tname in self.BendTwists:
            bname0,bname1,bname2 = self.getSubBoneNames(bname)
            if not hasPoseBones(rig, [bname, bname0, bname1, bname2]):
                continue
            pb = rig.pose.bones[bname]
            pb0 = rig.pose.bones[bname0]
            pb1 = rig.pose.bones[bname1]
            pb2 = rig.pose.bones[bname2]
            pb0.lock_ik_y = True
            pb2.lock_ik_x = pb2.lock_ik_z = True

            cns0 = pb0.constraints.new('IK')
            cns0.target = rig
            cns0.subtarget = tname
            cns0.chain_count = 1

            cns1 = pb1.constraints.new('COPY_ROTATION')
            cns1.target = rig
            cns1.subtarget = bname0
            cns1.use_y = False
            cns1.target_space = 'LOCAL_WITH_PARENT'
            cns1.owner_space = 'LOCAL_WITH_PARENT'

            cns2 = pb2.constraints.new('COPY_ROTATION')
            cns2.target = rig
            cns2.subtarget = bname
            cns2.target_space = 'WORLD'
            cns2.owner_space = 'WORLD'

#-------------------------------------------------------------
#   Add IK goals
#-------------------------------------------------------------

class DAZ_OT_AddIkGoals(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_ik_goals"
    bl_label = "Add IK goals"
    bl_description = "Add IK goals"
    bl_options = {'UNDO'}

    usePoleTargets : BoolProperty(
        name = "Pole Targets",
        description = "Add pole targets to the IK chains",
        default = False)

    hideBones : BoolProperty(
        name = "Hide Bones",
        description = "Hide all bones in the IK chains",
        default = False)

    lockBones : BoolProperty(
        name = "Lock Bones",
        description = "Lock all bones in the IK chains",
        default = False)

    disableBones : BoolProperty(
        name = "Disable Bones",
        description = "Disable all bones in the IK chains",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "hideBones")
        self.layout.prop(self, "lockBones")
        self.layout.prop(self, "disableBones")

    def run(self, context):
        rig = context.object
        ikgoals = []
        for pb in rig.pose.bones:
            if pb.bone.select and not pb.children:
                clen = 0
                par = pb
                pbones = []
                while par and par.bone.select:
                    pbones.append(par)
                    clen += 1
                    par = par.parent
                if clen > 2:
                    root = pbones[-1]
                    pbones = pbones[:-1]
                    ikgoals.append((pb.name, clen-1, pbones, root))

        bpy.ops.object.mode_set(mode='EDIT')
        for bname, clen, pbones, root in ikgoals:
            eb = rig.data.edit_bones[bname]
            goal = rig.data.edit_bones.new(bname+"Goal")
            goalname = goal.name
            goal.head = eb.tail
            goal.tail = 2*eb.tail - eb.head
            goal.roll = eb.roll
            if self.usePoleTargets:
                for n in range(clen//2):
                    eb = eb.parent
                pole = rig.data.edit_bones.new(bname+"Pole")
                polename = pole.name
                pole.head = eb.head + eb.length * eb.x_axis
                pole.tail = eb.tail + eb.length * eb.x_axis
                pole.roll = eb.roll

        bpy.ops.object.mode_set(mode='OBJECT')
        self.startGizmos(context)
        gzmBall = self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        gzmCube = self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        gzmCone = self.makeEmptyGizmo("GZM_Cone", 'CONE')

        bpy.ops.object.mode_set(mode='POSE')
        for bname, clen, pbones, root in ikgoals:
            if bname not in rig.pose.bones.keys():
                continue
            pb = rig.pose.bones[bname]
            rmat = pb.bone.matrix_local
            root.custom_shape = gzmCube

            goal = rig.pose.bones[bname+"Goal"]
            goal.rotation_mode = pb.rotation_mode
            goal.bone.use_local_location = True
            goal.matrix_basis = rmat.inverted() @ pb.matrix
            goal.custom_shape = gzmBall

            if self.usePoleTargets:
                pole = rig.pose.bones[polename]
                pole.rotation_mode = pb.rotation_mode
                pole.bone.use_local_location = True
                pole.matrix_basis = rmat.inverted() @ pb.matrix
                pole.custom_shape = gzmCone

            cns = getConstraint(pb, 'IK')
            if cns:
                pb.constraints.remove(cns)
            cns = pb.constraints.new('IK')
            cns.name = "IK"
            cns.target = rig
            cns.subtarget = goalname
            cns.chain_count = clen
            cns.use_location = True
            if self.usePoleTargets:
                cns.pole_target = rig
                cns.pole_subtarget = polename
                cns.pole_angle = 0*D
                cns.use_rotation = False
            else:
                cns.use_rotation = True

            if self.hideBones:
                for pb in pbones:
                    pb.bone.hide = True
            if self.lockBones:
                for pb in pbones:
                    pb.lock_location = (True, True, True)
                    pb.lock_rotation = (True, True, True)
                    pb.lock_scale = (True, True, True)
            if self.disableBones:
                for pb in pbones:
                    pb.bone.hide_select = True

#-------------------------------------------------------------
#   Add Winder
#-------------------------------------------------------------

class DAZ_OT_AddWinder(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_winder"
    bl_label = "Add Winder"
    bl_description = "Add winder to active posebone"
    bl_options = {'UNDO'}

    def run(self, context):
        from .mhx import copyRotation, copyScale
        bpy.ops.object.mode_set(mode='POSE')
        rig = context.object
        pb = bpy.context.active_pose_bone
        if pb is None:
            raise DazError("No active posebone")
        bname = pb.name
        wname = "Wind"+bname
        self.startGizmos(context)
        self.makeGizmos(["GZM_Knuckle"])
        gizmo = self.gizmos["GZM_Knuckle"]

        bpy.ops.object.mode_set(mode='EDIT')
        eb = rig.data.edit_bones[bname]
        tarb = rig.data.edit_bones.new(wname)
        tarb.head = eb.head
        tarb.tail = eb.tail
        tarb.roll = eb.roll
        tarb.parent = eb.parent
        n = 1
        length = eb.length
        while eb.children and len(eb.children) == 1:
            eb = eb.children[0]
            tarb.tail = eb.tail
            n += 1
            length += eb.length

        bpy.ops.object.mode_set(mode='POSE')
        target = rig.pose.bones[wname]
        target.custom_shape = gizmo
        target.bone.show_wire = True
        target.rotation_mode = pb.rotation_mode
        target.matrix_basis = pb.matrix_basis

        infl = 2*pb.bone.length/length
        cns1 = copyRotation(pb, target, (True,True,True), rig)
        cns1.influence = infl
        cns2 = copyScale(pb, target, (True,True,True), rig)
        cns2.influence = infl
        while pb.children and len(pb.children) == 1:
            pb = pb.children[0]
            infl = 2*pb.bone.length/length
            cns1 = copyRotation(pb, target, (True,True,True), rig)
            cns1.use_offset = True
            cns1.influence = infl

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddIkGoals,
    DAZ_OT_AddWinder,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

