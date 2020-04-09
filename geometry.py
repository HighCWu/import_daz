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

import math
import os
import bpy
from collections import OrderedDict
from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .settings import theSettings
from .node import Node, Instance

#-------------------------------------------------------------
#   Geometry
#-------------------------------------------------------------

class GeoNode(Node):    
    def __init__(self, figure, geo, ref):
        from .asset import normalizeRef
        if figure.caller:
            fileref = figure.caller.fileref
        else:
            fileref = figure.fileref
        Node.__init__(self, fileref)
        self.id = normalizeRef(ref)
        self.data = geo
        self.figure = figure
        self.figureInst = None
        self.verts = None
        self.index = figure.count
        if geo:
            geo.caller = self
            geo.nodes[self.id] = self
        self.modifiers = []
        self.morphsValues = {}
        self.shell = {}


    def __repr__(self):
        return ("<GeoNode %s %d %s>" % (self.id, self.index, self.rna))


    def getCharacterScale(self):
        if self.figureInst:
            return self.figureInst.getCharacterScale()
        else:
            return 1.0


    def preprocess(self, context, inst):
        if self.data:
            self.data.preprocess(context, inst)


    def buildObject(self, context, inst, center):
        Node.buildObject(self, context, inst, center)
        ob = self.rna
        self.storeRna(ob)
        scn = context.scene
        if ob:
            ob.DazUseSSS = scn.DazUseSSS
            ob.DazUseTranslucency = scn.DazUseTranslucency
            ob.DazUseDisplacement = scn.DazUseDisplacement
        if ob and self.data:
            self.data.buildRigidity(ob)


    def buildData(self, context, inst, cscale, center):
        print("BDGN", self)
        print("  ", self.data)
        self.data.buildData(context, self, inst, cscale, center)
        #geonode = self.data.getNode(inst.index)
        ob = self.rna = bpy.data.objects.new(inst.name, self.data.rna)
        print("  ", self.data)
        print("  ", self.rna, ob.type)
        return ob


    def postbuild(self, context):
        if self.rna:
            pruneUvMaps(self.rna)
        return


    def setHideInfo(self, parent):
        par = parent.rna
        if par is None:
            return
        me = self.rna.data
        me.DazVertexCount = self.data.vertex_count
        if self.data.hidden_polys:
            hgroup = me.DazMaskGroup
            for fn in self.data.hidden_polys:
                elt = hgroup.add()
                elt.a = fn
        if self.data.vertex_pairs:
            ggroup = me.DazGraftGroup
            for vn,pvn in self.data.vertex_pairs:
                pair = ggroup.add()
                pair.a = vn
                pair.b = pvn


    def getUsedVerts(self, usedFaces):
        ob = self.rna
        used = dict([(vn,True) for vn in range(len(ob.data.vertices))])
        for f in ob.data.polygons:
            if f.index not in usedFaces:
                for vn in f.vertices:
                    used[vn] = False
        verts = [vn for vn in used.keys() if used[vn]]
        return verts


def isEmpty(vgrp, ob):
    idx = vgrp.index
    for v in ob.data.vertices:
        for g in v.groups:
            if (g.group == idx and
                abs(g.weight-0.5) > 1e-4):
                return False
    return True

#-------------------------------------------------------------
#   Geometry Asset
#-------------------------------------------------------------

class Geometry(Asset, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.instances = self.nodes = {}
        self.verts = []
        self.faces = []
        self.materials = {}
        self.material_indices = []
        self.polygon_material_groups = []
        self.vertex_count = 0
        self.poly_count = 0
        self.vertex_pairs = []
        self.hidden_polys = []
        self.uv_set = None
        self.default_uv_set = None
        self.uv_sets = OrderedDict()
        self.rigidity = []
        self.SubDIALevel = 0
        self.SubDRenderLevel = 0
        self.shell = {}
        self.shells = {}


    def __repr__(self):
        return ("<Geometry %s %s>" % (self.id, self.rna))


    def getInstance(self, caller, ref):
        iref = instRef(ref)
        if iref in self.nodes.keys():
            return self.nodes[iref]
        else:
            return None


    def getNode(self, idx):
        for node in self.nodes.values():
            if node.index == idx:
                return node
        return None


    def addUvSet(self, uvstruct):
        uvset = self.getTypedAsset(uvstruct, Uvset)
        if uvset:
            self.uv_sets[uvset.name] = uvset
        return uvset


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)
        if "source" in struct.keys():
            self.copySource(struct["source"])
            
        vdata = struct["vertices"]["values"]
        fdata = struct["polylist"]["values"]
        if theSettings.zup:
            self.verts = [d2b90(v) for v in vdata]
        else:
            self.verts = [d2b00(v) for v in vdata]
        self.faces = [ f[2:] for f in fdata]
        self.material_indices = [f[1] for f in fdata]
        self.polygon_material_groups = struct["polygon_material_groups"]["values"]

        if "default_uv_set" in struct.keys():
            self.default_uv_set = self.addUvSet(struct["default_uv_set"])
        if "uv_set" in struct.keys():
            self.uv_set = self.addUvSet(struct["uv_set"])
        else:
            self.uv_set = self.default_uv_set

        if "graft" in struct.keys():
            for key,data in struct["graft"].items():
                if key == "vertex_count":
                    self.vertex_count = data
                elif key == "poly_count":
                    self.poly_count = data
                elif key == "hidden_polys":
                    self.hidden_polys = data["values"]
                elif key == "vertex_pairs":
                    self.vertex_pairs = data["values"]

        if "rigidity" in struct.keys():
            print("RIGIDITY", self.name)
            self.rigidity = struct["rigidity"]

        if "groups" in struct.keys():
            print("GROUPS", self.name)
            self.groups.append(struct["groups"])

        return self
    

    def update(self, struct):
        Asset.update(self, struct)
        Channels.update(self, struct)
        if "SubDIALevel" in self.channels.keys():
            self.SubDIALevel = getCurrentValue(self.channels["SubDIALevel"], 0)
        if "SubDRenderLevel" in self.channels.keys():
            self.SubDRenderLevel = getCurrentValue(self.channels["SubDRenderLevel"], 0)
        if self.SubDIALevel == 0 and "current_subdivision_level" in struct.keys():
            self.SubDIALevel = struct["current_subdivision_level"]
                    
                    
    def setExtra(self, extra):       
        if extra["type"] == "studio/geometry/shell":
            self.shell = extra
        

    def preprocess(self, context, inst):
        scn = context.scene
        if self.shell:
            node = self.getNode(0)
            for extra in node.extra:
                if "type" not in extra.keys():
                    pass
                elif extra["type"] == "studio/node/shell":
                    if "material_uvs" in extra.keys():
                        uvs = dict(extra["material_uvs"])
                    else:
                        uvs = None

            if scn.DazMergeShells:
                from .figure import FigureInstance
                if inst.node2:
                    missing = []
                    for key,child in inst.node2.children.items():
                        if child.shell:
                            geonode = inst.node2.geometries[0]
                            geo = geonode.data
                            for mname,shellmats in self.materials.items():
                                mat = shellmats[0]
                                if mname in inst.material_group_vis.keys() and not inst.material_group_vis[mname]:
                                    continue
                                uv = uvs[mname]
                                if mname in geo.materials.keys():
                                    mats = geo.materials[mname]
                                    mats[geonode.index].shells.append((mat,uv))
                                    mat.ignore = True
                                    # UVs used in materials for shell in Daz must also exist on underlying geometry in Blender
                                    # so they can be used to define materials assigned to the geometry in Blender.
                                    self.addNewUvset(uv, geo)
                                else:
                                    missing.append((mname,mat,uv))

                    for mname,mat,uv in missing:
                        for key,inst3 in inst.node2.children.items():
                            if not isinstance(inst3, FigureInstance):
                                continue
                            key1 = inst3.node.name
                            if mname[0:len(key)] == key:
                                n = len(key)
                            elif mname[0:len(key1)] == key1:
                                n = len(key1)
                            else:
                                continue 
                            mname = mname[n+1:]
                            geonode = inst3.geometries[0]
                            geo = geonode.data
                            if mname in geo.materials.keys():
                                mats = geo.materials[mname]
                                mats[0].shells.append((mat,uv))
                                mat.ignore = True
                                self.addNewUvset(uv, geo)
                            else:
                                print("  ***", mname, mat)

                                        
    def addNewUvset(self, uv, geo):                                        
        if uv not in geo.uv_sets.keys():
            uvset = self.findUvSet(uv, geo.id)
            if uvset:
                geo.uv_sets[uv] = geo.uv_sets[uvset.name] = uvset


    def findUvSet(self, uv, url):
        from .asset import getDazPath, normalizePath, getRelativeRef
        from .transfer import findFileRecursive
        folder = getDazPath(os.path.dirname(url) + "/UV Sets")
        file = ("%s.dsf" % uv)
        if folder:
            file = findFileRecursive(folder, file)
            if file:
                url = normalizePath("%s#%s" % (file, uv))
                url = getRelativeRef(url)
                asset = self.getAsset(url)
                if asset:
                    print("Found UV set '%s' in '%s'" % (uv, normalizePath(url)))
                    self.uv_sets[uv] = asset
                return asset
        return None


    def addShell(self, inst, longname, mname, uvs, scn):
        if isinstance(inst, Instance):
            geo = inst.geometries[0]
        geo.data.shells[self.id] = self
        if scn.DazMergeShells:
            if mname in geo.data.materials.keys():
                mat = geo.data.materials[mname][0]
                mat.shells += [(shmat,uvs) for shmat in self.materials[longname]]


    def buildData(self, context, node, inst, cscale, center):
        if (self.rna and not theSettings.singleUser):
            return

        name = self.getName()
        me = self.rna = bpy.data.meshes.new(name)

        if isinstance(node, GeoNode) and node.verts:
            verts = node.verts
        else:
            verts = self.verts

        if not verts:
            for mats in self.materials.values():
                mat = mats[0]
                me.materials.append(mat.rna)
            return

        me.from_pydata([cscale*vco-center for vco in verts], [], self.faces)

        for fn,mn in enumerate(self.material_indices):
            p = me.polygons[fn]
            p.material_index = mn
            p.use_smooth = True

        for mn,mname in enumerate(self.polygon_material_groups):
            if mname in self.materials.keys():
                mats = self.materials[mname]
                if (isinstance(node, GeoNode) and
                    node.index < len(mats)):
                    mat = mats[node.index]
                elif inst and inst.index < len(mats):
                    mat = mats[inst.index]
                else:
                    mat = mats[0]
                    print("KK", self, node, inst, mats)
            else:
                mat = None
                print("\nMaterial \"%s\" not found in %s" % (mname, self))
                print("Existing materials:\n  %s" % self.materials.keys())
            if mat:
                if mat.rna is None:
                    msg = ("Material without rna:\n  %s" % self)
                    reportError(msg, trigger=(2,3))
                    return None
                me.materials.append(mat.rna)
                if mat.uv_set and mat.uv_set.checkSize(me):
                    self.uv_set = mat.uv_set

        for key,uvset in self.uv_sets.items():
            self.buildUVSet(context, uvset, me, False)

        self.buildUVSet(context, self.uv_set, me, True)
        if self.shells and self.uv_set != self.default_uv_set:
            self.buildUVSet(context, self.default_uv_set, me, False)


    def buildUVSet(self, context, uv_set, me, setActive):
        if uv_set:
            if uv_set.checkSize(me):
                uv_set.build(context, me, self, setActive)
            else:
                msg = ("Incompatible UV set\n  %s\n  %s" % (me, uv_set))
                reportError(msg, trigger=(2,3))


    def buildRigidity(self, ob):
        from .modifier import buildVertexGroup
        if self.rigidity:
            if "weights" in self.rigidity.keys():
                buildVertexGroup(ob, "Rigidity", self.rigidity["weights"])
            if "groups" not in self.rigidity.keys():
                return
            for group in self.rigidity["groups"]:
                rgroup = ob.data.DazRigidityGroups.add()
                rgroup.id = group["id"]
                rgroup.rotation_mode = group["rotation_mode"]
                rgroup.scale_modes = " ".join(group["scale_modes"])
                for vn in group["reference_vertices"]["values"]:
                    vert = rgroup.reference_vertices.add()
                    vert.a = vn
                for vn in group["mask_vertices"]["values"]:
                    vert = rgroup.mask_vertices.add()
                    vert.a = vn

#-------------------------------------------------------------
#   UV Asset
#-------------------------------------------------------------

class Uvset(Asset):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.material = None
        self.built = []


    def __repr__(self):
        return ("<Uvset %s '%s' %d %d %s>" % (self.id, self.getName(), len(self.uvs), len(self.polyverts), self.material))


    def parse(self, struct):
        Asset.parse(self, struct)
        self.type = "uv_set"
        self.uvs = struct["uvs"]["values"]
        self.polyverts = struct["polygon_vertex_indices"]
        return self


    def checkSize(self, me):
        if not self.polyverts:
            return True
        fnums = [pvi[0] for pvi in self.polyverts]
        fnums.sort()
        return (len(me.polygons) >= fnums[-1])


    def getPolyVerts(self, me):
        polyverts = dict([(f.index, list(f.vertices)) for f in me.polygons])
        if self.polyverts:
            for fn,vn,uv in self.polyverts:
                f = me.polygons[fn]
                for n,vn1 in enumerate(f.vertices):
                    if vn1 == vn:
                        polyverts[fn][n] = uv
        return polyverts


    def build(self, context, me, geo, setActive):
        if self.name is None or me in self.built:
            return

        polyverts = self.getPolyVerts(me)
        uvloop = makeNewUvloop(me, self.name, setActive)

        m = 0
        vnmax = len(self.uvs)
        nmats = len(geo.polygon_material_groups)
        ucoords = [[] for n in range(nmats)]
        for fn,f in enumerate(me.polygons):
            mn = geo.material_indices[fn]
            for n in range(len(f.vertices)):
                vn = polyverts[f.index][n]
                if vn < vnmax:
                    uv = self.uvs[vn]
                    uvloop.data[m].uv = uv
                    ucoords[mn].append(uv[0])
                m += 1

        for mn in range(nmats):
            if len(ucoords[mn]) > 0:
                umin = min(ucoords[mn])
                umax = max(ucoords[mn])
                if umax-umin <= 1:
                    udim = math.floor((umin+umax)/2)
                else:
                    udim = 0
                    print("UV coordinate difference %f - %f > 1" % (umax, umin))
                key = geo.polygon_material_groups[mn]
                if key in geo.materials.keys():
                    for mat in geo.materials[key]:
                        mat.fixUdim(context, udim)
                else:
                    print("Material \"%s\" not found" % key)

        self.built.append(me)


def makeNewUvloop(me, name, setActive):
    uvtex = getUvTextures(me).new()
    uvtex.name = name
    uvloop = me.uv_layers[-1]
    if setActive:
        if bpy.app.version < (2,80,0):
            uvtex.active_render = True
        else:
            uvloop.active_render = True
        me.uv_layers.active_index = len(me.uv_layers) - 1
    return uvloop

#-------------------------------------------------------------
#   Prune Uv textures
#-------------------------------------------------------------

def pruneUvMaps(ob):
    if len(getUvTextures(ob.data)) <= 1:
        return
    print("Pruning UV maps")
    uvtexs = {}
    for uvtex in getUvTextures(ob.data):
        uvtexs[uvtex.name] = [uvtex, uvtex.active_render]
    for mat in ob.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if (node.type == "ATTRIBUTE" and
                    node.attribute_name in uvtexs.keys()):
                    uvtexs[node.attribute_name][1] = True
    for uvtex,used in uvtexs.values():
        if not used:
            getUvTextures(ob.data).remove(uvtex)
            

class DAZ_OT_PruneUvMaps(DazOperator, IsMesh):
    bl_idname = "daz.prune_uv_maps"
    bl_label = "Prune UV Maps"
    bl_description = "Remove unused UV maps"
    bl_options = {'UNDO'}

    def run(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                pruneUvMaps(ob)                    
        
#-------------------------------------------------------------
#   Collaps UDims
#-------------------------------------------------------------

def collapseUDims(ob):
    from .material import addUdim
    if ob.DazUDimsCollapsed:
        return
    ob.DazUDimsCollapsed = True
    addUdimsToUVs(ob, False, 0, 0)
    for mn,mat in enumerate(ob.data.materials):
        if mat.DazUDimsCollapsed:
            continue
        mat.DazUDimsCollapsed = True
        addUdim(mat, -mat.DazUDim, -mat.DazVDim)


def restoreUDims(ob):
    from .material import addUdim
    if not ob.DazUDimsCollapsed:
        return
    ob.DazUDimsCollapsed = False
    addUdimsToUVs(ob, True, 0, 0)
    for mn,mat in enumerate(ob.data.materials):
        if not mat.DazUDimsCollapsed:
            continue
        mat.DazUDimsCollapsed = False
        addUdim(mat, mat.DazUDim, mat.DazVDim)


def addUdimsToUVs(ob, restore, udim, vdim):
    for uvloop in ob.data.uv_layers:
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            mat = ob.data.materials[f.material_index]
            if restore:
                ushift = mat.DazUDim
                vshift = mat.DazVDim
            else:
                ushift = udim - mat.DazUDim
                vshift = vdim - mat.DazVDim            
            for n in range(len(f.vertices)):
                uvloop.data[m].uv[0] += ushift
                uvloop.data[m].uv[1] += vshift
                m += 1


class DAZ_OT_CollapseUDims(DazOperator):
    bl_idname = "daz.collapse_udims"
    bl_label = "Collapse UDIMs"
    bl_description = "Restrict UV coordinates to the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and not ob.DazUDimsCollapsed)

    def run(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                collapseUDims(ob)


class DAZ_OT_RestoreUDims(DazOperator):
    bl_idname = "daz.restore_udims"
    bl_label = "Restore UDIMs"
    bl_description = "Restore original UV coordinates outside the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.DazUDimsCollapsed)

    def run(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                restoreUDims(ob)

#-------------------------------------------------------------
#   Solidify thin walls
#-------------------------------------------------------------

class DAZ_OT_SolidifyThinWalls(DazOperator, IsMesh):
    bl_idname = "daz.solidify_thin_walls"
    bl_label = "Solidify Thin Walls"
    bl_description = "Create solidify modifiers for materials with thin wall refraction"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            setSelected(ob, False)
        ob = context.object
        setSelected(ob, True)
        mnums = []
        mats = []
        for mn,mat in enumerate(ob.data.materials):
            if mat and mat.DazThinGlass:
                mnums.append(mn)
                mat.DazThinGlass = False

        if mnums:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for f in ob.data.polygons:
                if f.material_index in mnums:
                    f.select = True

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            setSelected(ob, False)
            nob = None
            for ob1 in getSceneObjects(context):
                if getSelected(ob1):
                    nob = ob1
            nob.name = ob.name+"Sep"

            mod = nob.modifiers.new("Solidify", 'SOLIDIFY')
            #mod.show_render = mod.show_viewport = False
            mod.thickness = -0.03 * nob.DazScale
            mod.offset = 1
            mod.use_even_offset = True
            mod.use_rim = True

            for mn,mat in enumerate(ob.data.materials):
                if mn in mnums:
                    ob.data.materials[mn] = None
                else:
                    nob.data.materials[mn] = None

            #bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Solidify")
        else:
            msg = ("%s has no\nthin-walled materials that       \ncan be solidified" % ob.name)
            raise DazError(msg)

#-------------------------------------------------------------
#   Load UVs
#-------------------------------------------------------------

class DAZ_OT_LoadUV(DazOperator, B.DazFile, B.SingleFile, IsMesh):
    bl_idname = "daz.load_uv"
    bl_label = "Load UV Set"
    bl_description = "Load a UV set to the active mesh"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        from .fileutils import getFolder
        folder = getFolder(context.object, context.scene, ["UV Sets/", ""])
        if folder is not None:
            self.properties.filepath = folder
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        from .readfile import readDufFile
        from .files import parseAssetFile

        bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.object
        me = ob.data
        scn = context.scene
        theSettings.forUV(ob, scn)
        struct = readDufFile(self.filepath)
        asset = parseAssetFile(struct)
        if asset is None or len(asset.uvs) == 0:
            raise DazError ("Not an UV asset:\n  '%s'" % self.filepath)

        for uvset in asset.uvs:
            polyverts = uvset.getPolyVerts(me)
            uvloop = makeNewUvloop(me, uvset.getName(), True)
            vnmax = len(uvset.uvs)
            m = 0
            for fn,f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvloop.data[m].uv = uv
                    m += 1

#-------------------------------------------------------------
#   Utility to share meshes
#-------------------------------------------------------------

def sameMeshes(mesh1, mesh2, threshold):
    if mesh1 == mesh2:
        return False
    if len(mesh1.vertices) != len(mesh2.vertices):
        return False
    verts1 = mesh1.vertices
    verts2 = mesh2.vertices
    dists = [(verts1[n].co - verts2[n].co).length for n in range(len(verts1))]
    return (max(dists) < threshold)


def shareMyMesh(mesh, context):
    for ob in getSceneObjects(context):
        if (getSelected(ob) and
            ob.type == 'MESH' and
            sameMeshes(ob.data, mesh, scn.DazShareThreshold)):
            print("  ", ob.name)
            ob.data = mesh


class DAZ_OT_ShareMeshes(DazOperator, IsMesh):
    bl_idname = "daz.share_meshes"
    bl_label = "Share Meshes"
    bl_description = "Share meshes of all selected objects to active mesh"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                print("Share with", ob.name)
                shareMyMesh(ob.data, context)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PruneUvMaps,
    DAZ_OT_CollapseUDims,
    DAZ_OT_RestoreUDims,
    DAZ_OT_SolidifyThinWalls,
    DAZ_OT_LoadUV,
    DAZ_OT_ShareMeshes,
    B.DazIntGroup,
    B.DazPairGroup,
    B.DazRigidityGroup,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

    from bpy.props import CollectionProperty, IntProperty    
    bpy.types.Mesh.DazRigidityGroups = CollectionProperty(type = B.DazRigidityGroup)
    bpy.types.Mesh.DazGraftGroup = CollectionProperty(type = B.DazPairGroup)
    bpy.types.Mesh.DazMaskGroup = CollectionProperty(type = B.DazIntGroup)
    bpy.types.Mesh.DazVertexCount = IntProperty(default=0)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
