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


import os
import json
import bpy
from bpy.props import *
from .utils import *
from .error import *
from .material import MaterialMerger

#-------------------------------------------------------------
#   Merge geografts
#-------------------------------------------------------------

class DAZ_OT_MergeGeografts(DazOperator, MaterialMerger, IsMesh):
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    def run(self, context):
        from .driver import getShapekeyDrivers, copyShapeKeyDrivers

        cob = context.object
        ncverts = len(cob.data.vertices)

        # Find anatomies and move graft verts into position
        anatomies = []
        for aob in getSceneObjects(context):
            if (aob.type == 'MESH' and
                getSelected(aob) and
                aob != cob and
                aob.data.DazGraftGroup):
                anatomies.append(aob)
                self.removeMultires(aob)

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
        anames = []
        drivers = {}

        # Keep extra UVs
        self.keepUv = []
        for ob in [cob] + anatomies:
            for uvtex in getUvTextures(ob.data):
                if not uvtex.active_render:
                    self.keepUv.append(uvtex.name)

        # Select graft group for each anatomy
        for aob in anatomies:
            activateObject(context, aob)
            self.moveGraftVerts(aob, cob)
            getShapekeyDrivers(aob, drivers)
            for uvtex in getUvTextures(aob.data):
                if uvtex.active_render:
                    anames.append(uvtex.name)
                else:
                    self.keepUv.append(uvtex.name)

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
            setSelected(aob, True)
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

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = locations[pair.a]
                dists = [((x-y).length, vn) for vn,y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        self.joinUvTextures(cob.data)

        newname = self.getUvName(cob.data)
        for mat in cob.data.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, cname, newname)
                for aname in anames:
                    replaceNodeNames(mat, aname, newname)

        # Remove unused materials
        #self.mathits = dict([(mn,False) for mn in range(len(cob.data.materials))])
        #for f in cob.data.polygons:
        #    self.mathits[f.material_index] = True
        #self.mergeMaterials(cob)

        copyShapeKeyDrivers(cob, drivers)
        updateDrivers(cob)


    def keepMaterial(self, mn, mat, ob):
        keep = self.mathits[mn]
        if not keep:
            print("Remove material %s" % mat.name)
        return keep


    def moveGraftVerts(self, aob, cob):
        for pair in aob.data.DazGraftGroup:
            aob.data.vertices[pair.a].co = cob.data.vertices[pair.b].co
        if cob.data.shape_keys and aob.data.shape_keys:
            for cskey in cob.data.shape_keys.key_blocks:
                if cskey.name in aob.data.shape_keys.key_blocks.keys():
                    askey = aob.data.shape_keys.key_blocks[cskey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co


    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n,data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(getUvTextures(me)[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    getUvTextures(me).remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)


    def getUvName(self, me):
        for uvtex in getUvTextures(me):
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

    for node in uvmaps:
        mat.node_tree.nodes.remove(node)

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
        for ob in getSceneObjects(context):
            if (ob.type == 'MESH' and
                getSelected(ob) and
                ob != aob):
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

class DAZ_OT_MergeUVLayers(DazPropsOperator, IsMesh, B.MergeUVLayers):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = "Merge two UV layers"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "layer1")
        self.layout.prop(self, "layer2")


    def run(self, context):
        me = context.object.data
        keepIdx = int(self.layer1)
        mergeIdx = int(self.layer2)
        if keepIdx == mergeIdx:
            raise DazError("Keep and merge UV layers are equal")
        keepLayer = me.uv_layers[keepIdx]
        mergeLayer = me.uv_layers[mergeIdx]
        for n,data in enumerate(mergeLayer.data):
            if data.uv.length > 1e-6:
                keepLayer.data[n].uv = data.uv

        for mat in me.materials:
            if mat.use_nodes:
                replaceNodeNames(mat, mergeLayer.name, keepLayer.name)

        if bpy.app.version < (2,80,0):
            me.uv_textures.active_index = keepIdx
            me.uv_textures.remove(me.uv_textures[mergeIdx])
        else:
            me.uv_layers.active_index = keepIdx
            me.uv_layers.remove(mergeLayer)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        print("UV layers joined")

#-------------------------------------------------------------
#   Get selected rigs
#-------------------------------------------------------------

def getSelectedRigs(context):
    rig = context.object
    if rig:
        bpy.ops.object.mode_set(mode='OBJECT')
    subrigs = []
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'ARMATURE' and ob != rig:
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

class DAZ_OT_EliminateEmpties(DazOperator, IsArmature):
    bl_idname = "daz.eliminate_empties"
    bl_label = "Eliminate Empties"
    bl_description = "Delete empties with mesh children, parenting the meshes to the rig instead"
    bl_options = {'UNDO'}

    def run(self, context):
        rig,subrigs = getSelectedRigs(context)
        for rig in [rig]+subrigs:
            self.eliminateEmpties(rig, context)


    def eliminateEmpties(self, rig, context):
        deletes = []
        for empty in rig.children:
            if empty.type == 'EMPTY' and not isDuplicated(empty):
                for ob in empty.children:
                    if ob.type == 'MESH':
                        deletes.append(empty)
                        wmat = ob.matrix_world.copy()
                        if empty.parent_type == 'OBJECT':
                            ob.parent = rig
                            ob.parent_type = 'OBJECT'
                            setWorldMatrix(ob, wmat)
                        elif empty.parent_type == 'BONE':
                            bone = rig.data.bones[empty.parent_bone]
                            ob.parent = rig
                            ob.parent_type = 'BONE'
                            ob.parent_bone = empty.parent_bone
                            setWorldMatrix(ob, wmat)
                        else:
                            raise DazError("Unknown parent type: %s %s" % (ob.name, empty.parent_type))
        for empty in deletes:
            deleteObject(context, empty)


def isDuplicated(ob):
    if bpy.app.version < (2,80,0):
        return (ob.dupli_type != 'NONE')
    else:
        return (ob.instance_type != 'NONE')

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

class DAZ_OT_MergeRigs(DazPropsOperator, IsArmature, B.MergeRigs):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "clothesLayer")
        self.layout.prop(self, "separateCharacters")
        self.layout.prop(self, "useApplyRestPose")
        self.layout.prop(self, "createMeshCollection")


    def run(self, context):
        if not self.separateCharacters:
            rig,subrigs = getSelectedRigs(context)
            self.mergeRigs(context, rig, subrigs)
        else:
            rigs = []
            for ob in getSceneObjects(context):
                if ob.type == 'ARMATURE' and getSelected(ob) and ob.parent is None:
                    rigs.append(ob)
            pairs = []
            for rig in rigs:
                subrigs = self.getSubRigs(context, rig)
                pairs.append((rig,subrigs))
            for rig,subrigs in pairs:
                activateObject(context, rig)
                self.mergeRigs(context, rig, subrigs)


    def getSubRigs(self, context, rig):
        subrigs = []
        for ob in rig.children:
            if ob.type == 'ARMATURE' and getSelected(ob):
                subrigs.append(ob)
                subrigs += self.getSubRigs(context, ob)
        return subrigs


    def mergeRigs(self, context, rig, subrigs):
        LS.forAnimation(None, rig, context.scene)
        if rig is None:
            raise DazError("No rigs to merge")
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        try:
            self.mergeRigs1(rig, subrigs, context)
            success = True
        finally:
            rig.data.layers = oldvis
            if success:
                rig.data.layers[self.clothesLayer-1] = True
            setActiveObject(context, rig)


    def mergeRigs1(self, rig, subrigs, context):
        from .proxy import stripName
        from .node import clearParent, reParent
        scn = context.scene

        print("Merge rigs to %s:" % rig.name)
        bpy.ops.object.mode_set(mode='OBJECT')

        for subrig in subrigs:
            copyPose(context, rig, subrig)

        if self.useApplyRestPose:
            applyRestPoses(context, rig, subrigs)

        adds, hdadds, removes = self.createNewCollections(rig)

        for ob in rig.children:
            if ob.type == 'MESH':
                self.changeArmatureModifier(ob, rig, context)
                self.addToCollections(ob, adds, hdadds, removes)
            elif ob.type == 'EMPTY':
                reParent(context, ob, rig)

        self.mainBones = [bone.name for bone in rig.data.bones]
        for subrig in subrigs:
            success = True
            if (subrig.parent and
                subrig.parent_type == 'BONE'):
                parbone = subrig.parent_bone
                clearParent(subrig)
            else:
                parbone = None

            if success:
                print("  ", subrig.name, parbone)
                storage = self.addExtraBones(subrig, rig, context, scn, parbone)

                meshes = []
                for ob in subrig.children:
                    if ob.type == 'MESH':
                        meshes.append(ob)
                    elif ob.type == 'EMPTY':
                        reParent(context, ob, rig)
                        for child in ob.children:
                            if child.type == 'MESH':
                                meshes.append(child)

                for ob in meshes:
                    self.changeArmatureModifier(ob, rig, context)
                    self.changeVertexGroupNames(ob, storage)
                    self.addToCollections(ob, adds, hdadds, removes)
                    ob.name = stripName(ob.name)
                    ob.data.name = stripName(ob.data.name)
                    wmat = ob.matrix_world.copy()
                    ob.parent = rig
                    setWorldMatrix(ob, wmat)

                subrig.parent = None
                deleteObject(context, subrig)

        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='OBJECT')


    def createNewCollections(self, rig):
        adds = []
        hdadds = []
        removes = []
        if not self.createMeshCollection:
            return adds, hdadds, removes

        mcoll = hdcoll = None
        if bpy.app.version < (2,80,0):
            for grp in bpy.data.groups:
                if rig.name in grp.objects:
                    adds.append(grp)
        else:
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


    def changeArmatureModifier(self, ob, rig, context):
        from .node import reParent
        #reParent(context, ob, rig)
        if ob.parent_type != 'BONE':
            for mod in ob.modifiers:
                if mod.type == "ARMATURE":
                    mod.name = rig.name
                    mod.object = rig
                    return
            if len(ob.vertex_groups) == 0:
                print("Mesh with no vertex groups: %s" % ob.name)
            else:
                mod = ob.modifiers.new(rig.name, "ARMATURE")
                mod.object = rig
                mod.use_deform_preserve_volume = True


    def addExtraBones(self, ob, rig, context, scn, parbone):
        from .figure import copyBoneInfo
        extras = []
        for bone in ob.data.bones:
            if (bone.name not in self.mainBones or
                bone.name not in rig.data.bones.keys()):
                extras.append(bone.name)

        if extras:
            storage = {}
            if activateObject(context, ob):
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = ob.data.edit_bones[bname]
                storage[bname] = EditBoneStorage(eb, None)
            bpy.ops.object.mode_set(mode='OBJECT')

            setActiveObject(context, rig)
            layers = (self.clothesLayer-1)*[False] + [True] + (32-self.clothesLayer)*[False]
            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = storage[bname].createBone(rig, storage, parbone)
                eb.layers = layers
                storage[bname].realname = eb.name
            bpy.ops.object.mode_set(mode='OBJECT')
            for bname in extras:
                pb = rig.pose.bones[bname]
                copyBoneInfo(ob.pose.bones[bname], pb)
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
    for ob in subrigs:
        print("  ", ob.name)
        if not setActiveObject(context, ob):
            continue
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in ob.data.edit_bones:
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
    LS.forAnimation(None, rig, context.scene)
    rigs = [rig] + subrigs
    for subrig in rigs:
        for ob in subrig.children:
            if ob.type == 'MESH':
                setRestPose(ob, subrig, context)
        if not setActiveObject(context, subrig):
            continue
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply()
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='OBJECT')


def setRestPose(ob, rig, context):
    from .node import setParent
    if not setActiveObject(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if LS.fitFile:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
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
    setActiveObject(context, rig)
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
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_ReparentToes(DazOperator, IsArmature):
    bl_idname = "daz.reparent_toes"
    bl_label = "Reparent Toes"
    bl_description = "Parent small toes to big toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        reparentToes(context.object, context)


def mergeBonesAndVgroups(rig, mergers, parents, context):
    from .driver import removeBoneDrivers

    activateObject(context, rig)

    bpy.ops.object.mode_set(mode='OBJECT')
    for bones in mergers.values():
        removeBoneDrivers(rig, bones)

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
    bl_description = "Merge all toes"
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

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
