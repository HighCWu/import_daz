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


import os
import json
import bpy

from .utils import *
from .error import *
from .material import MaterialMerger
from .driver import DriverUser

#-------------------------------------------------------------
#   Merge geografts
#-------------------------------------------------------------

class DAZ_OT_MergeGeografts(DazOperator, MaterialMerger, DriverUser, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    def __init__(self):
        DriverUser.__init__(self)


    def run(self, context):
        cob = context.object
        ncverts = len(cob.data.vertices)

        # Find anatomies and move graft verts into position
        anatomies = []
        for aob in getSelectedMeshes(context):
            if (aob != cob and
                aob.data.DazGraftGroup):
                anatomies.append(aob)
                #self.removeMultires(aob)

        if len(anatomies) < 1:
            raise DazError("At least two meshes must be selected.\nGeografts selected and target active.")

        for aob in anatomies:
            if aob.data.DazVertexCount != ncverts:
                if cob.data.DazVertexCount == len(aob.data.vertices):
                    msg = ("Meshes selected in wrong order.\nGeografts selected and target active.   ")
                else:
                    msg = ("Geograft %s fits mesh with %d vertices,      \nbut %s has %d vertices." %
                        (aob.name, aob.data.DazVertexCount, cob.name, ncverts))
                raise DazError(msg)

        cname = self.getUvName(cob.data)
        drivers = {}

        # Select graft group for each anatomy
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob)
            self.getShapekeyDrivers(aob, drivers)
            self.replaceTexco(aob)

        # For the body, setup mask groups
        activateObject(context, cob)
        nverts = len(cob.data.vertices)
        vfaces = dict([(vn,[]) for vn in range(nverts)])
        for f in cob.data.polygons:
            for vn in f.vertices:
                vfaces[vn].append(f.index)

        nfaces = len(cob.data.polygons)
        fmasked = dict([(fn,False) for fn in range(nfaces)])
        for aob in anatomies:
            for face in aob.data.DazMaskGroup:
                fmasked[face.a] = True

        # If cob is itself a geograft, make sure to keep tbe boundary
        if cob.data.DazGraftGroup:
            cgrafts = [pair.a for pair in cob.data.DazGraftGroup]
        else:
            cgrafts = []

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Select body verts to delete
        vdeleted = dict([(vn,False) for vn in range(nverts)])
        for aob in anatomies:
            paired = [pair.b for pair in aob.data.DazGraftGroup]
            for face in aob.data.DazMaskGroup:
                fverts = cob.data.polygons[face.a].vertices
                vdelete = []
                for vn in fverts:
                    if vn in cgrafts:
                        pass
                    elif vn not in paired:
                        vdelete.append(vn)
                    else:
                        mfaces = [fn for fn in vfaces[vn] if fmasked[fn]]
                        if len(mfaces) == len(vfaces[vn]):
                            vdelete.append(vn)
                for vn in vdelete:
                    cob.data.vertices[vn].select = True
                    vdeleted[vn] = True

        # Build association table between new and old vertex numbers
        assoc = {}
        vn2 = 0
        for vn in range(nverts):
            if not vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        # Delete the masked verts
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # If cob is itself a geograft, store locations
        if cob.data.DazGraftGroup:
            verts = cob.data.vertices
            locations = dict([(pair.a, verts[pair.a].co.copy()) for pair in cob.data.DazGraftGroup])

        # Select nothing
        for aob in anatomies:
            activateObject(context, aob)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
        activateObject(context, cob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Select verts on common boundary
        names = []
        for aob in anatomies:
            aob.select_set(True)
            names.append(aob.name)
            for pair in aob.data.DazGraftGroup:
                aob.data.vertices[pair.a].select = True
                if pair.b in assoc.keys():
                    cvn = assoc[pair.b]
                    cob.data.vertices[cvn].select = True

        # Also select cob graft group. These will not be removed.
        if cob.data.DazGraftGroup:
            for pair in cob.data.DazGraftGroup:
                cvn = assoc[pair.a]
                cob.data.vertices[cvn].select = True

        # Join meshes and remove doubles
        print("Merge %s to %s" % (names, cob.name))
        threshold = 0.001*cob.DazScale
        bpy.ops.object.join()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.object.mode_set(mode='OBJECT')
        selected = dict([(v.index,v.co.copy()) for v in cob.data.vertices if v.select])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Create graft vertex group
        vgrp = cob.vertex_groups.new(name="Graft")
        for vn in selected.keys():
            vgrp.add([vn], 1.0, 'REPLACE')
        mod = getModifier(cob, 'MULTIRES')
        if mod:
            smod = cob.modifiers.new("Graft", 'SMOOTH')
            smod.factor = 1.0
            smod.iterations = 10
            smod.vertex_group = vgrp.name

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        self.copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)


    def replaceTexco(self, ob):
        for uvtex in ob.data.uv_layers:
            if uvtex.active_render:
                uvrender = uvtex
        for mat in ob.data.materials:
            texco = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
            if texco:
                uvmap = mat.node_tree.nodes.new(type="ShaderNodeUVMap")
                uvmap.uv_map = uvrender.name
                uvmap.location = texco.location
                for link in mat.node_tree.links:
                    if link.from_node == texco:
                        mat.node_tree.links.new(uvmap.outputs["UV"], link.to_socket)
                mat.node_tree.nodes.remove(texco)


    def moveGraftVerts(self, aob, cob):
        cvgroups = dict([(vgrp.index, vgrp.name) for vgrp in cob.vertex_groups])
        averts = aob.data.vertices
        cverts = cob.data.vertices
        for pair in aob.data.DazGraftGroup:
            avert = averts[pair.a]
            cvert = cverts[pair.b]
            avert.co = cvert.co
            for cg in cvert.groups:
                vgname = cvgroups[cg.group]
                if vgname in aob.vertex_groups.keys():
                    avgrp = aob.vertex_groups[vgname]
                else:
                    avgrp = aob.vertex_groups.new(name=vgname)
                avgrp.add([pair.a], cg.weight, 'REPLACE')

        askeys = aob.data.shape_keys
        cskeys = cob.data.shape_keys
        if askeys:
            for askey in askeys.key_blocks:
                if cskeys and askey.name in cskeys.key_blocks.keys():
                    cskey = cskeys.key_blocks[askey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co
                else:
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cverts[pair.b].co


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(me.uv_layers[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    me.uv_layers.remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def getUvName(self, me):
        for uvtex in me.uv_layers:
            if uvtex.active_render:
                return uvtex.name
        return None


    def removeMultires(self, ob):
        for mod in ob.modifiers:
            if mod.type == 'MULTIRES':
                ob.modifiers.remove(mod)


def replaceNodeNames(mat, oldname, newname):
    texco = None
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_COORD':
            texco = node
            break

    uvmaps = []
    for node in mat.node_tree.nodes:
        if isinstance(node, bpy.types.ShaderNodeUVMap):
            if node.uv_map == oldname:
                node.uv_map = newname
                uvmaps.append(node)
        elif isinstance(node, bpy.types.ShaderNodeAttribute):
            if node.attribute_name == oldname:
                node.attribute_name = newname
        elif isinstance(node, bpy.types.ShaderNodeNormalMap):
            if node.uv_map == oldname:
                node.uv_map = newname

    if texco and uvmaps:
        fromsocket = texco.outputs["UV"]
        tosockets = []
        for link in mat.node_tree.links:
            if link.from_node in uvmaps:
                tosockets.append(link.to_socket)
        for tosocket in tosockets:
            mat.node_tree.links.new(fromsocket, tosocket)

#-------------------------------------------------------------
#   Create graft and mask vertex groups
#-------------------------------------------------------------

class DAZ_OT_CreateGraftGroups(DazOperator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.DazGraftGroup)

    def run(self, context):
        aob = context.object
        objects = []
        for ob in getSelectedMeshes(context):
            if ob != aob:
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        cob = objects[0]
        gname = "Graft_" + aob.data.name
        mname = "Mask_" + aob.data.name
        self.createVertexGroup(aob, gname, [pair.a for pair in aob.data.DazGraftGroup])
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        self.createVertexGroup(cob, gname, graft)
        mask = {}
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    mask[vn] = True
        self.createVertexGroup(cob, mname, mask.keys())


    def createVertexGroup(self, ob, gname, vnums):
        vgrp = ob.vertex_groups.new(name=gname)
        for vn in vnums:
            vgrp.add([vn], 1, 'REPLACE')
        return vgrp

#-------------------------------------------------------------
#   Merge UV sets
#-------------------------------------------------------------

def getUVLayers(scn, context):
    ob = context.object
    enums = []
    for n,uv in enumerate(ob.data.uv_layers):
        ename = "%s (%d)" % (uv.name, n)
        enums.append((str(n), ename, ename))
    return enums


class DAZ_OT_MergeUVLayers(DazPropsOperator, IsMesh):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = ("Merge an UV layer to the active render layer.\n" +
                      "Merging the active render layer to itself replaces\n" +
                      "any UV map nodes with texture coordinate nodes")
    bl_options = {'UNDO'}

    layer : EnumProperty(
        items = getUVLayers,
        name = "Layer To Merge",
        description = "UV layer that is merged with the active render layer")

    def draw(self, context):
        self.layout.label(text="Active Layer: %s" % self.keepName)
        self.layout.prop(self, "layer")


    def invoke(self, context, event):
        ob = context.object
        self.keepIdx = -1
        self.keepName = "None"
        for idx,uvlayer in enumerate(ob.data.uv_layers):
            if uvlayer.active_render:
                self.keepIdx = idx
                self.keepName = uvlayer.name
                break
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        if self.keepIdx < 0:
            raise DazError("No active UV layer found")
        mergeIdx = int(self.layer)
        mergeUVLayers(context.object.data, self.keepIdx, mergeIdx)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')


def mergeUVLayers(me, keepIdx, mergeIdx):
    def replaceUVMapNodes(me, mergeLayer):
        for mat in me.materials:
            texco = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
            deletes = {}
            for link in mat.node_tree.links:
                node = link.from_node
                if (node.type == 'UVMAP' and
                    node.uv_map == mergeLayer.name):
                    deletes[node.name] = node
                    if texco is None:
                        texco = mat.node_tree.nodes.new(type="ShaderNodeTexCoord")
                        texco.location = node.location
                    mat.node_tree.links.new(texco.outputs["UV"], link.to_socket)
            for node in deletes.values():
                mat.node_tree.nodes.remove(node)

    keepLayer = me.uv_layers[keepIdx]
    mergeLayer = me.uv_layers[mergeIdx]
    if not keepLayer.active_render:
        raise DazError("Only the active render layer may be the layer to keep")
    replaceUVMapNodes(me, mergeLayer)
    if keepIdx == mergeIdx:
        print("UV layer is the same as the active render layer.")
        return
    for n,data in enumerate(mergeLayer.data):
        if data.uv.length > 1e-6:
            keepLayer.data[n].uv = data.uv
    for mat in me.materials:
        if mat.use_nodes:
            replaceNodeNames(mat, mergeLayer.name, keepLayer.name)
    me.uv_layers.active_index = keepIdx
    me.uv_layers.remove(mergeLayer)
    print("UV layers joined")

#-------------------------------------------------------------
#   Get selected rigs
#-------------------------------------------------------------

def getSelectedRigs(context):
    rig = context.object
    if rig:
        bpy.ops.object.mode_set(mode='OBJECT')
    subrigs = []
    for ob in getSelectedArmatures(context):
        if ob != rig:
            subrigs.append(ob)
    return rig, subrigs

#-------------------------------------------------------------
#   Copy poses
#-------------------------------------------------------------

class DAZ_OT_CopyPoses(DazOperator, IsArmature):
    bl_idname = "daz.copy_poses"
    bl_label = "Copy Poses"
    bl_description = "Copy active rig pose to selected rigs"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            print("No poses to copy")
            return
        print("Copy pose to %s:" % rig.name)
        for ob in subrigs:
            print("  ", ob.name)
            copyPose(context, rig, ob)


def copyPose(context, rig, ob):
    if not setActiveObject(context, ob):
        return
    setWorldMatrix(ob, rig.matrix_world.copy())
    for cb in rig.pose.bones:
        if cb.name in ob.pose.bones:
            pb = ob.pose.bones[cb.name]
            pb.matrix_basis = cb.matrix_basis.copy()
    setActiveObject(context, rig)

#-------------------------------------------------------------
#   Eliminate Empties
#-------------------------------------------------------------

class DAZ_OT_EliminateEmpties(DazOperator):
    bl_idname = "daz.eliminate_empties"
    bl_label = "Eliminate Empties"
    bl_description = "Delete non-hidden empties, parenting its children to its parent instead"
    bl_options = {'UNDO'}

    def run(self, context):
        roots = []
        for ob in getSelectedObjects(context):
            if ob.parent is None:
                roots.append(ob)
        for root in roots:
            self.eliminateEmpties(root, context)


    def eliminateEmpties(self, ob, context):
        deletes = []
        for child in ob.children:
            self.eliminateEmpties(child, context)
        if self.doEliminate(ob):
            deletes.append(ob)
            for child in ob.children:
                wmat = child.matrix_world.copy()
                if ob.parent_type == 'OBJECT':
                    child.parent = ob.parent
                    child.parent_type = 'OBJECT'
                    setWorldMatrix(child, wmat)
                elif ob.parent_type == 'BONE':
                    child.parent = ob.parent
                    child.parent_type = 'BONE'
                    child.parent_bone = ob.parent_bone
                    setWorldMatrix(child, wmat)
                else:
                    raise DazError("Unknown parent type: %s %s" % (child.name, ob.parent_type))
        for empty in deletes:
            deleteObjects(context, [empty])


    def doEliminate(self, ob):
        if ob.type != 'EMPTY' or getHideViewport(ob):
            return False
        return (ob.instance_type == 'NONE')

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

class DAZ_OT_MergeRigs(DazPropsOperator, DriverUser, IsArmature):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    clothesLayer : IntProperty(
        name = "Clothes Layer",
        description = "Bone layer used for extra bones when merging clothes",
        min = 1, max = 32,
        default = 3)

    separateCharacters : BoolProperty(
        name = "Separate Characters",
        description = "Don't merge armature that belong to different characters",
        default = False)

    useCreateDuplicates : BoolProperty(
        name = "Create Duplicate Bones",
        description = "Create separate bones if several bones with the same name are found",
        default = False)

    useApplyTransforms : BoolProperty(
        name = "Apply Transforms",
        description = "Apply all object level transforms",
        default = False)

    useMergeBoneParented : BoolProperty(
        name = "Merge Bone Parented Rigs",
        description = "Also merge rigs that are parented to bones",
        default = False)

    createMeshCollection : BoolProperty(
        name = "Create Mesh Collection",
        description = "Create a new collection and move all meshes to it",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "clothesLayer")
        self.layout.prop(self, "separateCharacters")
        self.layout.prop(self, "useCreateDuplicates")
        self.layout.prop(self, "useApplyTransforms")
        self.layout.prop(self, "useMergeBoneParented")
        self.layout.prop(self, "createMeshCollection")

    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        if not self.separateCharacters:
            rig,subrigs = getSelectedRigs(context)
            subrigs,childrigs,meshes = self.getChildren(rig, subrigs)
            self.mergeRigs(context, rig, subrigs, childrigs, meshes)
        else:
            rigs = []
            for rig in getSelectedArmatures(context):
                if rig.parent is None:
                    rigs.append(rig)
            pairs = []
            for rig in rigs:
                subrigs = self.getSubRigs(context, rig)
                subrigs,childrigs,meshes = self.getChildren(rig, subrigs)
                pairs.append((rig,subrigs,childrigs,meshes))
            for rig,subrigs,childrigs,meshes in pairs:
                activateObject(context, rig)
                self.mergeRigs(context, rig, subrigs, childrigs, meshes)


    def getChildren(self, rig, subrigs):
        nsubrigs = []
        childrigs = {}
        meshes = self.addMeshes(rig)
        for subrig in subrigs:
            if subrig.parent and subrig.parent_type == 'BONE':
                childrigs[subrig.name] = (subrig, subrig.parent_bone)
                if self.useMergeBoneParented:
                    nsubrigs.append(subrig)
                    meshes += self.addMeshes(subrig)
            else:
                nsubrigs.append(subrig)
                meshes += self.addMeshes(subrig)
        if self.useMergeBoneParented:
            bpy.ops.object.select_all(action='DESELECT')
            for subrig in subrigs:
                subrig.select_set(True)
            for ob in meshes:
                ob.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        return nsubrigs,childrigs,meshes


    def addMeshes(self, ob):
        meshes = []
        for child in ob.children:
            if getHideViewport(child):
                continue
            elif child.type == 'MESH':
                meshes.append(child)
            elif child.type == 'EMPTY':
                meshes += self.addMeshes(child)
        return meshes


    def applyTransforms(self, rigs, meshes):
        bpy.ops.object.select_all(action='DESELECT')
        for rig in rigs:
            rig.select_set(True)
        for ob in meshes:
            ob.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


    def getSubRigs(self, context, rig):
        subrigs = []
        for ob in rig.children:
            if ob.type == 'ARMATURE' and ob.select_get():
                if not (ob.parent and ob.parent_type == 'BONE'):
                    subrigs.append(ob)
                subrigs += self.getSubRigs(context, ob)
        return subrigs


    def collectChildren(self, subrig, children):
        for ob in subrig.children:
            if ob.type == 'MESH':
                children.append(ob)


    def mergeRigs(self, context, rig, subrigs, childrigs, meshes):
        LS.forAnimation(None, rig)
        if rig is None:
            raise DazError("No rigs to merge")
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        try:
            self.mergeRigs1(rig, subrigs, childrigs, meshes, context)
            success = True
        finally:
            rig.data.layers = oldvis
            if success:
                rig.data.layers[self.clothesLayer-1] = True
            setActiveObject(context, rig)
            updateDrivers(rig)
            updateDrivers(rig.data)


    def mergeRigs1(self, rig, subrigs, childrigs, meshes, context):
        from .proxy import stripName
        from .node import clearParent
        scn = context.scene

        print("Merge rigs to %s:" % rig.name)
        if self.useApplyTransforms:
            self.applyTransforms([rig]+subrigs, meshes)
        for subrig in subrigs:
            copyPose(context, rig, subrig)

        adds, hdadds, removes = self.createNewCollections(rig)

        for ob in meshes:
            self.changeArmatureModifier(ob, rig)
            self.addToCollections(ob, adds, hdadds, removes)

        self.mainBones = [bone.name for bone in rig.data.bones]
        for subrig in subrigs:
            success = True
            if self.useMergeBoneParented and subrig.name in childrigs.keys():
                parbone = childrigs[subrig.name][1]
            else:
                parbone = None

            if success:
                storage = self.addExtraBones(subrig, rig, context, scn, parbone)
                for ob in meshes:
                    self.changeArmatureModifier(ob, rig)
                    self.changeVertexGroupNames(ob, storage)
                    wmat = ob.matrix_world.copy()
                    ob.parent = rig
                    setWorldMatrix(ob, wmat)
                    self.addToCollections(ob, adds, hdadds, removes)
                    ob.name = stripName(ob.name)
                    ob.data.name = stripName(ob.data.name)
                subrig.parent = None
                deleteObjects(context, [subrig])

        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.useApplyTransforms:
            self.applyTransforms([rig], meshes)


    def createNewCollections(self, rig):
        adds = []
        hdadds = []
        removes = []
        if not self.createMeshCollection:
            return adds, hdadds, removes

        mcoll = hdcoll = None
        for coll in bpy.data.collections:
            if rig in coll.objects.values():
                if coll.name.endswith("HD"):
                    if hdcoll is None:
                        hdcoll = bpy.data.collections.new(name= rig.name + " Meshes_HD")
                        hdadds = [hdcoll]
                    coll.children.link(hdcoll)
                else:
                    if mcoll is None:
                        mcoll = bpy.data.collections.new(name= rig.name + " Meshes")
                        adds = [mcoll]
                    coll.children.link(mcoll)
                removes.append(coll)
        return adds, hdadds, removes


    def changeVertexGroupNames(self, ob, storage):
        for bname in storage.keys():
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = storage[bname].realname


    def addToCollections(self, ob, adds, hdadds, removes):
        if not self.createMeshCollection:
            return
        if ob.name.endswith("HD"):
            adders = hdadds
        else:
            adders = adds
        for grp in adders:
            if ob.name not in grp.objects:
                grp.objects.link(ob)
        for grp in removes:
            if ob.name in grp.objects:
                grp.objects.unlink(ob)


    def changeArmatureModifier(self, ob, rig):
        if ob.parent_type != 'BONE':
            mod = getModifier(ob, 'ARMATURE')
            if mod:
                mod.name = rig.name
                mod.object = rig
                return
            if len(ob.vertex_groups) == 0:
                print("Mesh with no vertex groups: %s" % ob.name)
            else:
                mod = ob.modifiers.new(rig.name, "ARMATURE")
                mod.object = rig
                mod.use_deform_preserve_volume = True


    def addExtraBones(self, subrig, rig, context, scn, parbone):
        from .figure import copyBoneInfo
        from .fix import copyConstraints
        extras = []
        for bone in subrig.data.bones:
            if (bone.name not in self.mainBones or
                bone.name not in rig.data.bones.keys()):
                extras.append(bone.name)

        if extras:
            storage = {}
            if activateObject(context, subrig):
                try:
                    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                except RuntimeError:
                    pass

            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = subrig.data.edit_bones[bname]
                storage[bname] = EditBoneStorage(eb, None)
            bpy.ops.object.mode_set(mode='OBJECT')

            for key in subrig.data.keys():
                rig.data[key] = subrig.data[key]
            self.copyDrivers(subrig.data, rig.data, subrig, rig)
            self.copyDrivers(subrig, rig, subrig, rig)

            setActiveObject(context, rig)
            layers = (self.clothesLayer-1)*[False] + [True] + (32-self.clothesLayer)*[False]
            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                if self.useCreateDuplicates or bname not in rig.data.bones.keys():
                    eb = storage[bname].createBone(rig, storage, parbone)
                    eb.layers = layers
                    storage[bname].realname = eb.name
            bpy.ops.object.mode_set(mode='OBJECT')
            for bname in extras:
                pb = rig.pose.bones[bname]
                subpb = subrig.pose.bones[bname]
                copyBoneInfo(subpb, pb)
                copyConstraints(subpb, pb, rig)
                pb.bone.layers[self.clothesLayer-1] = True
            return storage
        else:
            return {}

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

class DAZ_OT_CopyBones(DazOperator, IsArmature):
    bl_idname = "daz.copy_bones"
    bl_label = "Copy Bones"
    bl_description = "Copy selected rig bone locations to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        if rig is None:
            raise DazError("No target armature")
        if not subrigs:
            raise DazError("No source armature")
        copyBones(context, rig, subrigs)


def copyBones(context, rig, subrigs):
    print("Copy bones to %s:" % rig.name)
    ebones = []
    for subrig in subrigs:
        print("  ", subrig.name)
        if not setActiveObject(context, subrig):
            continue
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in subrig.data.edit_bones:
            ebones.append(EditBoneStorage(eb))
        bpy.ops.object.mode_set(mode='OBJECT')

    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for storage in ebones:
        storage.copyBoneLocation(rig)
    bpy.ops.object.mode_set(mode='OBJECT')

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------

class DAZ_OT_ApplyRestPoses(DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):

    def applyLimitConstraints(rig):
        constraints = []
        for pb in rig.pose.bones:
            if pb.rotation_mode != 'QUATERNION':
                x,y,z = pb.rotation_euler
                for cns in pb.constraints:
                    if cns.type == 'LIMIT_ROTATION':
                        constraints.append((cns,cns.mute))
                        cns.mute = True
                        applyLimitComp("min_x", "max_x", "use_limit_x", 0, cns, pb)
                        applyLimitComp("min_y", "max_y", "use_limit_y", 1, cns, pb)
                        applyLimitComp("min_z", "max_z", "use_limit_z", 2, cns, pb)
        return constraints

    def applyLimitComp(min, max, use, idx, cns, pb):
        x = pb.rotation_euler[idx]
        if getattr(cns, use):
            xmax = getattr(cns, max)
            if x > xmax:
                x = pb.rotation_euler[idx] = xmax
            xmax -= x
            if abs(xmax) < 1e-4:
                xmax = 0
            setattr(cns, max, xmax)

            xmin = getattr(cns, min)
            if x < xmin:
                x = pb.rotation_euler[idx] = xmin
            xmin -= x
            if abs(xmin) < 1e-4:
                xmin = 0
            setattr(cns, min, xmin)

    LS.forAnimation(None, rig)
    rigs = [rig] + subrigs
    applyAllObjectTransforms(rigs)
    for subrig in rigs:
        for ob in subrig.children:
            if ob.type == 'MESH':
                setRestPose(ob, subrig, context)
        if not setActiveObject(context, subrig):
            continue
        constraints = applyLimitConstraints(subrig)
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply()
        for cns,mute in constraints:
            cns.mute = mute
    setActiveObject(context, rig)


def applyAllObjectTransforms(rigs):
    bpy.ops.object.select_all(action='DESELECT')
    for rig in rigs:
        rig.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    try:
        for rig in rigs:
            for ob in rig.children:
                if ob.type == 'MESH':
                    ob.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        return True
    except RuntimeError:
        print("Could not apply object transformations to meshes")
        return False


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if LS.fitFile:
        mod = getModifier(ob, 'ARMATURE')
        if mod:
            mod.object = rig
    elif len(ob.vertex_groups) == 0:
        print("Mesh with no vertex groups: %s" % ob.name)
    else:
        try:
            applyArmatureModifier(ob)
            ok = True
        except RuntimeError:
            print("Could not apply armature to %s" % ob.name)
            ok = False
        if ok:
            mod = ob.modifiers.new(rig.name, "ARMATURE")
            mod.object = rig
            mod.use_deform_preserve_volume = True
            nmods = len(ob.modifiers)
            for n in range(nmods-1):
                bpy.ops.object.modifier_move_up(modifier=mod.name)


def applyArmatureModifier(ob):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE':
            mname = mod.name
            if ob.data.shape_keys:
                if bpy.app.version < (2,90,0):
                    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                else:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                bpy.ops.object.modifier_apply(modifier=mname)

#-------------------------------------------------------------
#   Merge toes
#-------------------------------------------------------------

GenesisToes = {
    "lFoot" : ["lMetatarsals"],
    "rFoot" : ["rMetatarsals"],
    "lToe" : ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
              "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
    "rToe" : ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
              "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
}

NewParent = {
    "lToe" : "lFoot",
    "rToe" : "rFoot",
}


def reparentToes(rig, context):
    from .driver import removeBoneSumDrivers
    setActiveObject(context, rig)
    toenames = []
    bpy.ops.object.mode_set(mode='EDIT')
    for parname in ["lToe", "rToe"]:
        if parname in rig.data.edit_bones.keys():
            parb = rig.data.edit_bones[parname]
            for bname in GenesisToes[parname]:
                if bname[-2:] == "_2":
                    continue
                if bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[bname]
                    eb.parent = parb
                    toenames.append(eb.name)
    bpy.ops.object.mode_set(mode='OBJECT')
    removeBoneSumDrivers(rig, toenames)


class DAZ_OT_ReparentToes(DazOperator, IsArmature):
    bl_idname = "daz.reparent_toes"
    bl_label = "Reparent Toes"
    bl_description = "Parent small toes to big toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        reparentToes(context.object, context)


def mergeBonesAndVgroups(rig, mergers, parents, context):
    from .driver import removeBoneSumDrivers

    activateObject(context, rig)

    bpy.ops.object.mode_set(mode='OBJECT')
    for bones in mergers.values():
        removeBoneSumDrivers(rig, bones)

    bpy.ops.object.mode_set(mode='EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    for bones in mergers.values():
        for eb in rig.data.edit_bones:
            if eb.name in bones:
                rig.data.edit_bones.remove(eb)

    bpy.ops.object.mode_set(mode='OBJECT')

    for ob in rig.children:
        if ob.type == 'MESH':
            for toe,subtoes in mergers.items():
                if toe in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[toe]
                else:
                    vgrp = ob.vertex_groups.new(name=toe)
                subgrps = []
                for subtoe in subtoes:
                    if subtoe in ob.vertex_groups.keys():
                        subgrps.append(ob.vertex_groups[subtoe])
                idxs = [vg.index for vg in subgrps]
                idxs.append(vgrp.index)
                weights = dict([(vn,0) for vn in range(len(ob.data.vertices))])
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group in idxs:
                            weights[v.index] += g.weight
                for subgrp in subgrps:
                    ob.vertex_groups.remove(subgrp)
                for vn,w in weights.items():
                    if w > 1e-3:
                        vgrp.add([vn], w, 'REPLACE')

    updateDrivers(rig)
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_MergeToes(DazOperator, IsArmature):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge separate toes into a single toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        mergeBonesAndVgroups(rig, GenesisToes, NewParent, context)

#-------------------------------------------------------------
#   EditBoneStorage
#-------------------------------------------------------------

class EditBoneStorage:
    def __init__(self, eb, pname=None):
        self.name = eb.name
        self.realname = self.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = pname


    def createBone(self, rig, storage, parbone):
        eb = rig.data.edit_bones.new(self.name)
        self.realname = eb.name
        eb.head = self.head
        eb.tail = self.tail
        eb.roll = self.roll
        if storage and self.parent in storage.keys():
            pname = storage[self.parent].realname
        elif self.parent:
            pname = self.parent
        elif parbone:
            pname = parbone
        else:
            pname = None
        if pname is not None:
            eb.parent = rig.data.edit_bones[pname]
        return eb


    def copyBoneLocation(self, rig):
        if self.name in rig.data.edit_bones:
            eb = rig.data.edit_bones[self.name]
            eb.head = self.head
            eb.tail = self.tail
            eb.roll = self.roll

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeGeografts,
    DAZ_OT_CreateGraftGroups,
    DAZ_OT_MergeUVLayers,
    DAZ_OT_CopyPoses,
    DAZ_OT_MergeRigs,
    DAZ_OT_EliminateEmpties,
    DAZ_OT_CopyBones,
    DAZ_OT_ApplyRestPoses,
    DAZ_OT_ReparentToes,
    DAZ_OT_MergeToes,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
