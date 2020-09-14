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
from .error import *
from .utils import *

#-------------------------------------------------------------
#   Fixer class
#-------------------------------------------------------------

class Fixer:

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


    def fixCorrectives(self, rig):
        from .driver import getShapekeyDriver, replaceDriverBone
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys:
                skeys = ob.data.shape_keys
                for skey in skeys.key_blocks[1:]:
                    if getShapekeyDriver(skeys, skey.name):
                        replaceDriverBone(self.Correctives, skeys, 'key_blocks["%s"].value' % (skey.name))


    def checkCorrectives(self, rig):
        from .driver import getShapekeyDriver, checkDriverBone
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys:
                skeys = ob.data.shape_keys
                for skey in skeys.key_blocks[1:]:
                    if getShapekeyDriver(skeys, skey.name):
                        checkDriverBone(rig, skeys, 'key_blocks["%s"].value' % (skey.name))

#-------------------------------------------------------------
#   Constraints class
#-------------------------------------------------------------

class ConstraintStore:
    Attributes = [
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

    def __init__(self):
        self.constraints = {}


    def untouchable(self, cns):
        return (cns.name == "Do Not Touch")


    def storeConstraints(self, key, pb):
        clist = []
        for cns in pb.constraints:
            if self.untouchable(cns):
                continue
            struct = {}
            for attr in self.Attributes:
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
            if not self.untouchable(cns):
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
            srcbone = rig.data.bones[bendname]
            trgbone = rig.data.bones[bname]
            copyBoneInfo(srcbone, trgbone)
            srcpb = rig.pose.bones[bendname]
            trgpb = rig.pose.bones[bname]
            trgpb.rotation_mode = srcpb.rotation_mode

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
        bname1 = base + "-1." + suffix
        bname2 = base + "-2." + suffix
        return bname1,bname2


    def createBendTwists(self, rig):
        hiddenLayer = 31*[False] + [True]
        bpy.ops.object.mode_set(mode='EDIT')

        for bname,_ in self.BendTwists:
            eb = rig.data.edit_bones[bname]
            vec = eb.tail - eb.head
            bname1,bname2 = self.getSubBoneNames(bname)
            eb1 = rig.data.edit_bones.new(bname1)
            eb2 = rig.data.edit_bones.new(bname2)
            eb1.head = eb.head
            eb1.tail = eb2.head = eb.head+vec/2
            eb2.tail = eb.tail
            eb1.roll = eb2.roll = eb.roll
            eb1.parent = eb.parent
            eb2.parent = eb1
            eb1.use_connect = eb.use_connect
            eb2.use_connect = True
            eb.use_deform = False
            eb1.use_deform = eb2.use_deform = True
            eb1.layers = eb2.layers = hiddenLayer

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
        bname1,bname2 = self.getSubBoneNames(bname)
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
            bname1,bname2 = self.getSubBoneNames(bname)
            if not hasPoseBones(rig, [bname, bname1, bname2]):
                continue
            pb = rig.pose.bones[bname]
            pb1 = rig.pose.bones[bname1]
            pb2 = rig.pose.bones[bname2]

            cns1 = pb1.constraints.new('IK')
            cns1.target = rig
            cns1.subtarget = tname
            cns1.chain_count = 1

            cns2 = pb2.constraints.new('COPY_ROTATION')
            cns2.target = rig
            cns2.subtarget = bname
            cns2.target_space = 'WORLD'
            cns2.owner_space = 'WORLD'

#-------------------------------------------------------------
#   Prune vertex groups
#-------------------------------------------------------------

class DAZ_OT_PruneVertexGroups(DazPropsOperator, B.ThresholdFloat, IsMesh):
    bl_idname = "daz.prune_vertex_groups"
    bl_label = "Prune Vertex Groups"
    bl_description = "Remove vertices and groups with weights below threshold"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "threshold")

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                self.pruneVertexGroups(ob)

    def pruneVertexGroups(self, ob):
        keep = {}
        removes = {}
        vgroups = {}
        for vgrp in ob.vertex_groups:
            keep[vgrp.index] = False
            removes[vgrp.index] = []
            vgroups[vgrp.index] = vgrp
        for v in ob.data.vertices:
            for g in v.groups:
                if g.weight > self.threshold:
                    keep[g.group] = True
                else:
                    removes[g.group].append(v.index)
        for gn,vgrp in vgroups.items():
            if not keep[gn]:
                ob.vertex_groups.remove(vgrp)
            else:
                for vn in removes[gn]:
                    vgrp.remove([vn])

#-------------------------------------------------------------
#   Add IK goals
#-------------------------------------------------------------

def addIkGoals(rig):
    ikgoals = []
    for pb in rig.pose.bones:
        if pb.bone.select and not pb.children:
            clen = 0
            par = pb
            while par and par.bone.select:
                pb.ik_stiffness_x = 0.5
                pb.ik_stiffness_y = 0.5
                pb.ik_stiffness_z = 0.5
                clen += 1
                par = par.parent
            if clen > 2:
                ikgoals.append((pb.name, par.name, clen))

    bpy.ops.object.mode_set(mode='EDIT')
    for bname, pname, clen in ikgoals:
        eb = rig.data.edit_bones[bname]
        gb = rig.data.edit_bones.new(bname+"Goal")
        gb.head = eb.tail
        gb.tail = 2*eb.tail - eb.head

    bpy.ops.object.mode_set(mode='POSE')
    for bname, pname, clen in ikgoals:
        if bname not in rig.pose.bones.keys():
            continue
        pb = rig.pose.bones[bname]
        cns = pb.constraints.new('IK')
        cns.name = "IK"
        cns.target = rig
        cns.subtarget = bname+"Goal"
        cns.chain_count = clen
        cns.use_location = True
        cns.use_rotation = True


class DAZ_OT_AddIkGoals(DazOperator, IsArmature):
    bl_idname = "daz.add_ik_goals"
    bl_label = "Add IK goals"
    bl_description = "Add IK goals"
    bl_options = {'UNDO'}

    def run(self, context):
        addIkGoals(context.object)

#-------------------------------------------------------------
#   Add Winder
#-------------------------------------------------------------

def findChild(oname, rig):
    for child in rig.children:
        if child.name == oname:
            return child
        ob = findChild(oname, child)
        if ob:
            return ob
    return None


def addWinder(context):
    from .mhx import copyRotation, copyScale, makeGizmos
    rig = context.object
    pb = context.active_pose_bone
    bname = pb.name
    wname = "Wind"+bname
    gizmo = findChild("GZM_Knuckle", rig)
    if gizmo is None:
        hidden = createHiddenCollection(context)
        gizmos = makeGizmos(["GZM_Knuckle"], rig, hidden)
        gizmo = gizmos["GZM_Knuckle"]

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
        #cns2 = copyScale(pb, target, (True,True,True), rig)
        #cns2.use_offset = True
        #cns2.influence = infl


class DAZ_OT_AddWinder(DazOperator, IsArmature):
    bl_idname = "daz.add_winder"
    bl_label = "Add Winder"
    bl_description = "Add winder to active posebone"
    bl_options = {'UNDO'}

    def run(self, context):
        addWinder(context)

#-------------------------------------------------------------
#   Add To Group
#-------------------------------------------------------------

class DAZ_OT_AddToGroup(DazPropsOperator, B.NameString):
    bl_idname = "daz.add_to_group"
    bl_label = "Add To Group"
    bl_description = "Add all selected objects to group"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "name", text="Group")

    def run(self, context):
        if self.name in bpy.data.groups.keys():
            group = bpy.data.groups[self.name]
        else:
            group = bpy.data.groups.new(self.name)
        for ob in getSceneObjects(context):
            if (getSelected(ob) and
                ob.name not in group.objects.keys()):
                group.objects.link(ob)

#-------------------------------------------------------------
#   Remove from groups
#-------------------------------------------------------------

class DAZ_OT_RemoveFromGroups(DazPropsOperator, B.NameString):
    bl_idname = "daz.remove_from_groups"
    bl_label = "Remove From Group(s)"
    bl_description = "Remove selected objects from group (or all groups if none given)"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "name", text="Group")

    def run(self, context):
        if self.name in bpy.data.groups.keys():
            groups = [bpy.data.groups[self.name]]
        elif self.name == "":
            groups = list(bpy.data.groups.values())
        else:
            groups = []
        for group in groups:
            for ob in getSceneObjects(context):
                if (getSelected(ob) and
                    ob.name in group.objects.keys()):
                    group.objects.unlink(ob)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PruneVertexGroups,
    DAZ_OT_AddIkGoals,
    DAZ_OT_AddWinder,
    DAZ_OT_AddToGroup,
    DAZ_OT_RemoveFromGroups,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

