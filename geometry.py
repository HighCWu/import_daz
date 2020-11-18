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
from mathutils import Vector, Matrix
import os
import bpy
from collections import OrderedDict
from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .node import Node, Instance

#-------------------------------------------------------------
#   Geonode
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
        self.edges = None
        self.dbzMaterials = None
        self.polylines = None
        self.highdef = None
        self.hdobject = None
        self.pgeonode = None
        self.hairgen = None
        self.dforce = None
        self.index = figure.count
        if geo:
            geo.caller = self
            geo.nodes[self.id] = self
        self.modifiers = {}
        self.morphsValues = {}
        self.shstruct = {}
        self.push = 0


    def __repr__(self):
        return ("<GeoNode %s %d %s %s>" % (self.id, self.index, self.center, self.rna))


    def isVisibleMaterial(self, dmat):
        if self.data:
            return self.data.isVisibleMaterial(dmat)
        return True


    def preprocess(self, context, inst):
        if self.data:
            self.data.preprocess(context, inst)
        elif inst.isStrandHair:
            geo = self.data = Geometry(self.fileref)
            geo.name = inst.name
            geo.isStrandHair = True
            geo.preprocess(context, inst)


    def buildObject(self, context, inst, center):
        Node.buildObject(self, context, inst, center)
        ob = self.rna
        self.storeRna(ob)


    def subtractCenter(self, ob, inst, center):
        if not LS.fitFile:
            ob.location = -center
        inst.center = center


    def arrangeObject(self, ob, inst, context, center):
        Node.arrangeObject(self, ob, inst, context, center)
        if self.edges:
            self.unTesselate(context, ob)
            self.data.findPolyLines(ob)
            if len(self.dbzMaterials) > 0:
                self.data.makeHairMaterial(self.dbzMaterials[0], context)


    def unTesselate(self, context, ob):
        from .tables import getVertEdges, otherEnd

        # Move close points to the same point
        edgeverts,vertedges = getVertEdges(ob)
        verts = ob.data.vertices
        nverts = len(verts)
        for vn in range(nverts):
            ne = len(vertedges[vn])
            if ne >  2:
                v0 = verts[vn]
                r0 = verts[vn].co
                dists = []
                for n,e in enumerate(vertedges[vn]):
                    v = verts[otherEnd(vn, e)]
                    dists.append(((v.co-r0).length, n, v))
                dists.sort()
                for _,_,v in dists[:2-ne]:
                    v.co = r0

        # Remove doubles
        activateObject(context, ob)
        threshold = 0.001*LS.scale
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Check that there are only pure lines
        edgeverts,vertedges = getVertEdges(ob)
        nverts = len(ob.data.vertices)
        print("Check hair", ob.name, nverts)
        deletes = []
        for vn,v in enumerate(ob.data.vertices):
            ne = len(vertedges[vn])
            if ne > 2:
                v.select = True
                deletes.append(vn)
        print("Number of vertices to delete", len(deletes))


    def subdivideObject(self, ob, inst, context):
        if self.highdef:
            me = self.buildHDMesh(ob)
            hdob = bpy.data.objects.new(ob.name + "_HD", me)
            self.hdobject = inst.hdobject = hdob
            self.addHDMaterials(ob.data.materials, "")
            center = Vector((0,0,0))
            self.arrangeObject(hdob, inst, context, center)
            multi = False
            if GS.useMultires:
                multi = addMultires(context, hdob, False)
            if not multi and len(hdob.data.vertices) == len(ob.data.vertices):
                print("HD mesh same as base mesh:", ob.name)
                self.hdobject = inst.hdobject = ob
                deleteObject(context, hdob)
        elif LS.useHDObjects:
            self.hdobject = inst.hdobject = ob

        if ob and self.data:
            self.data.buildRigidity(ob)
            if self.hdobject and self.hdobject != ob:
                self.data.buildRigidity(self.hdobject)

        if (self.type == "subdivision_surface" and
            self.data and
            (self.data.SubDIALevel > 0 or self.data.SubDRenderLevel > 0)):
            mod = ob.modifiers.new(name='SUBSURF', type='SUBSURF')
            mod.render_levels = self.data.SubDIALevel + self.data.SubDRenderLevel
            mod.levels = self.data.SubDIALevel


    def buildHDMesh(self, ob):
        verts = self.highdef.verts
        uvs = self.highdef.uvs
        hdfaces = self.highdef.faces
        faces = self.stripNegatives([f[0] for f in hdfaces])
        uvfaces = self.stripNegatives([f[1] for f in hdfaces])
        mnums = [f[4] for f in hdfaces]
        nverts = len(verts)
        me = bpy.data.meshes.new(ob.data.name + "_HD")
        print("Build HD mesh for %s: %d verts, %d faces" % (ob.name, nverts, len(faces)))
        me.from_pydata(verts, [], faces)
        print("HD mesh %s built" % me.name)
        uvlayers = getUvTextures(ob.data)
        addUvs(me, uvlayers[0].name, uvs, uvfaces)
        for f in me.polygons:
            f.material_index = mnums[f.index]
            f.use_smooth = True
        return me


    def addHDMaterials(self, mats, prefix):
        from .material import getMatKey
        for mat in mats:
            pg = self.hdobject.data.DazHDMaterials.add()
            pg.name = prefix + getMatKey(mat.name)
            pg.text = mat.name
        if self.data and self.data.vertex_pairs:
            # Geograft
            inst = list(self.figure.instances.values())[0]
            par = inst.parent.geometries[0]
            if par and par.hdobject and par.hdobject != par.rna:
                par.addHDMaterials(mats, inst.name + "?" + prefix)


    def stripNegatives(self, faces):
        return [(f if f[-1] >= 0 else f[:-1]) for f in faces]


    def finalize(self, context, inst):
        if self.finishHair(context):
            return
        ob = self.rna
        if ob is None:
            return
        if self.hdobject:
            self.finishHD(context, self.rna, self.hdobject, None)
        if LS.fitFile and ob.type == 'MESH':
            shiftMesh(ob, inst.worldmat.inverted())
            hdob = self.hdobject
            if hdob and hdob != ob:
                shiftMesh(hdob, inst.worldmat.inverted())



    def finishHD(self, context, ob, hdob, inst):
        if LS.hdcollection is None:
            from .main import makeRootCollection
            LS.hdcollection = makeRootCollection(LS.collection.name + "_HD", context)
        if hdob.name in LS.hdcollection.objects:
            print("DUPHD", hdob.name)
            return
        LS.hdcollection.objects.link(hdob)
        if hdob.parent and hdob.parent.name not in LS.hdcollection.objects:
            LS.hdcollection.objects.link(hdob.parent)
        if hdob == ob:
            return
        hdob.parent = ob.parent
        hdob.parent_type = ob.parent_type
        hdob.parent_bone = ob.parent_bone
        setWorldMatrix(hdob, ob.matrix_world)
        if hdob.name in inst.collection.objects:
            inst.collection.objects.unlink(hdob)


    def finishHair(self, context):
        if self.pgeonode and GS.strandsAsHair:
            ob = self.rna
            print("DELETE", ob)
            deleteObject(context, ob)
            if self.parent:
                rig = self.parent.rna
                print("DELETE", rig)
                deleteObject(context, rig)


    def addHairSim(self, mod, extra, pgeonode):
        from .dforce import HairGenerator
        if self.hairgen is None:
            self.hairgen = HairGenerator(mod, self, extra, pgeonode)


    def addDForce(self, mod, extra, pgeonode):
        from .dforce import DForce
        if self.dforce is None:
            self.dforce = DForce(mod, self, extra, pgeonode)


    def postbuild(self, context, inst):
        ob = self.rna
        hdob = self.hdobject
        if ob:
            pruneUvMaps(ob)
        if hdob and hdob != ob:
            self.buildHighDef(context, inst)
        if GS.strandsAsHair:
            if inst.fitTo and inst.fitTo.geometries:
                self.pgeonode = inst.fitTo.geometries[0]
            if self.pgeonode:
                self.data.buildHair(self, context)
        if self.dforce:
            self.dforce.build(context)


    def buildHighDef(self, context, inst):
        from .material import getMatKey
        me = self.hdobject.data
        matgroups = [(mname,mn) for mn,mname in enumerate(self.highdef.matgroups)]
        matnames = [(pg.name,pg.text) for pg in me.DazHDMaterials]
        matgroups.sort()
        matnames.sort()
        diff = len(matnames) - len(matgroups)
        matnums = []
        n = 0
        for mname1,mname in matnames:
            if n >= len(matgroups):
                break
            mname2,mn = matgroups[n]
            ename = mname1.rsplit("?",1)[-1]
            if not mname2.endswith(ename) and diff > 0:
                diff -= 1
            else:
                matnums.append((mn, mname))
                n += 1
        matnums.sort()
        for _,mname in matnums:
            mat = bpy.data.materials[mname]
            me.materials.append(mat)

        inst.parentObject(context, self.hdobject)


    def setHideInfo(self):
        if self.data is None:
            return
        self.setHideInfoMesh(self.rna)
        if self.hdobject and self.hdobject != self.rna:
            self.setHideInfoMesh(self.hdobject)


    def setHideInfoMesh(self, ob):
        if ob.data is None:
            return
        ob.data.DazVertexCount = self.data.vertex_count
        if self.data.hidden_polys:
            hgroup = ob.data.DazMaskGroup
            for fn in self.data.hidden_polys:
                elt = hgroup.add()
                elt.a = fn
        if self.data.vertex_pairs:
            ggroup = ob.data.DazGraftGroup
            for vn,pvn in self.data.vertex_pairs:
                pair = ggroup.add()
                pair.a = vn
                pair.b = pvn


    def hideVertexGroups(self, hidden):
        self.hideVertexGroupsMesh(self.rna, hidden)
        if self.hdobject and self.hdobject != self.rna:
            self.hideVertexGroupsMesh(self.hdobject.rna, hidden)


    def hideVertexGroupsMesh(self, ob, hidden):
        if not (ob and ob.data):
            return
        idxs = []
        for vgrp in ob.vertex_groups:
            if vgrp.name in hidden:
                idxs.append(vgrp.index)
        vgname = "_HIDDEN_"
        vgrp = ob.vertex_groups.new(name=vgname)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group in idxs:
                    vgrp.add([v.index], 1, 'REPLACE')
                    break
        mod = ob.modifiers.new(vgname, 'MASK')
        mod.vertex_group = vgname
        mod.invert_vertex_group = True


def shiftMesh(ob, mat):
    from .node import isUnitMatrix
    if isUnitMatrix(mat):
        return
    if bpy.app.version < (2,80,0):
        for v in ob.data.vertices:
            v.co = mat * v.co
    else:
        for v in ob.data.vertices:
            v.co = mat @ v.co


def isEmpty(vgrp, ob):
    idx = vgrp.index
    for v in ob.data.vertices:
        for g in v.groups:
            if (g.group == idx and
                abs(g.weight-0.5) > 1e-4):
                return False
    return True

#-------------------------------------------------------------
#   Add multires
#-------------------------------------------------------------

def addMultires(context, hdob, strict):
    if bpy.app.version < (2,90,0):
        print("Cannot rebuild subdiv in Blender %d.%d.%d" % bpy.app.version)
        return False
    activateObject(context, hdob)
    mod = hdob.modifiers.new("Multires", 'MULTIRES')
    try:
        bpy.ops.object.multires_rebuild_subdiv(modifier="Multires")
        msg = None
    except RuntimeError:
        msg = ('Cannot rebuild subdivisions for "%s"' % hdob.name)
    if msg is None:
        hdob.DazMultires = True
        return True
    elif strict:
        raise DazError(msg)
    else:
        reportError(msg, trigger=(2,4))
        hdob.modifiers.remove(mod)
        LS.hdfailures.append(hdob)
        return False


class DAZ_OT_MakeMultires(DazOperator, IsMesh):
    bl_idname = "daz.make_multires"
    bl_label = "Make Multires"
    bl_description = "Convert HD mesh into mesh with multires modifier, and add vertex groups"
    bl_options = {'UNDO'}

    def run(self, context):
        from .modifier import makeArmatureModifier, copyVertexGroups
        hdob = context.object
        baseob = None
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob) and ob != hdob:
                if len(hdob.data.vertices) > len(ob.data.vertices):
                    baseob = ob
                else:
                    hdob = ob
                    baseob = context.object
                break
        if baseob is None:
            raise DazError("Two meshes must be selected, \none subdivided and one at base resolution.")
        addMultires(context, hdob, True)
        rig = baseob.parent
        if not (rig and rig.type == 'ARMATURE'):
            return
        hdob.parent = rig
        makeArmatureModifier(rig.name, context, hdob, rig)
        copyVertexGroups(baseob, hdob)

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
        self.polylines = []
        self.strands = []
        self.materials = {}
        self.polygon_indices = []
        self.material_indices = []
        self.polygon_material_groups = []
        self.polygon_groups = []
        self.material_group_vis = {}

        self.material_selection_sets = []
        self.type = None
        self.isStrandHair = False
        self.vertex_count = 0
        self.poly_count = 0
        self.vertex_pairs = []

        self.hidden_polys = []
        self.uv_set = None
        self.default_uv_set = None
        self.uv_sets = OrderedDict()
        self.rigidity = []

        self.root_region = None
        self.SubDIALevel = 0
        self.SubDRenderLevel = 0
        self.shstruct = {}
        self.shells = {}


    def __repr__(self):
        return ("<Geometry %s %s %s>" % (self.id, self.name, self.rna))


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
            uvset.name = uvset.getLabel()
            self.uv_sets[uvset.name] = uvset
        return uvset


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)

        vdata = struct["vertices"]["values"]
        if GS.zup:
            self.verts = [d2b90(v) for v in vdata]
        else:
            self.verts = [d2b00(v) for v in vdata]

        if "polyline_list" in struct.keys():
            self.polylines = struct["polyline_list"]["values"]

        fdata = struct["polylist"]["values"]
        self.faces = [ f[2:] for f in fdata]
        self.polygon_indices = [f[0] for f in fdata]
        self.polygon_groups = struct["polygon_groups"]["values"]
        self.material_indices = [f[1] for f in fdata]
        self.polygon_material_groups = struct["polygon_material_groups"]["values"]

        for key,data in struct.items():
            if key == "default_uv_set":
                self.default_uv_set = self.addUvSet(data)
            elif key == "uv_set":
                self.uv_set = self.addUvSet(data)
            elif key == "graft":
                for key1,data1 in data.items():
                    if key1 == "vertex_count":
                        self.vertex_count = data1
                    elif key1 == "poly_count":
                        self.poly_count = data1
                    elif key1 == "hidden_polys":
                        self.hidden_polys = data1["values"]
                    elif key1 == "vertex_pairs":
                        self.vertex_pairs = data1["values"]
            elif key == "rigidity":
                self.rigidity = data
            elif key == "groups":
                self.groups.append(data)
            elif key == "root_region":
                self.root_region = data
            elif key == "type":
                self.type = data

        if self.uv_set is None:
            self.uv_set = self.default_uv_set

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
            self.shstruct = extra
        elif extra["type"] == "material_selection_sets":
            self.material_selection_sets = extra["material_selection_sets"]


    def isVisibleMaterial(self, dmat):
        if not self.material_group_vis.keys():
            return True
        label = dmat.name.rsplit("-", 1)[0]
        if label in self.material_group_vis.keys():
            return self.material_group_vis[label]
        else:
            return True


    def preprocess(self, context, inst):
        scn = context.scene
        if self.shstruct:
            node = self.getNode(0)
            self.uvs = None
            for extra in node.extra:
                if "type" not in extra.keys():
                    pass
                elif extra["type"] == "studio/node/shell":
                    if "material_uvs" in extra.keys():
                        self.uvs = dict(extra["material_uvs"])

            if GS.mergeShells:
                if inst.node2:
                    missing = self.addUvSets(inst.node2, inst.name, self.material_group_vis)
                    for mname,shmat,uv,idx in missing:
                        msg = ("Missing shell material\n" +
                               "Material: %s\n" % mname +
                               "Node: %s\n" % node.name +
                               "Inst: %s\n" % inst.name +
                               "Index: %d\n" % idx +
                               "Node2: %s\n" % inst.node2.name +
                               "UV set: %s\n" % uv)
                        reportError(msg, trigger=(2,4))


    def addUvSets(self, inst, shname, vis):
        missing = []
        for key,child in inst.children.items():
            if child.shstruct:
                geonode = inst.geometries[0]
                geo = geonode.data
                for mname,shellmats in self.materials.items():
                    if mname in vis.keys():
                        if not vis[mname]:
                            continue
                    else:
                        print("Warning: no visibility for material %s" % mname)
                    shmat = shellmats[0]
                    if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
                        shmat.getValue("getChannelOpacity", 1) == 0):
                        continue
                    uv = self.uvs[mname]
                    if mname in geo.materials.keys():
                        dmats = geo.materials[mname]
                        mshells = dmats[geonode.index].shells
                        if shname not in mshells.keys():
                            mshells[shname] = self.addShell(shname, shmat, uv)
                        shmat.ignore = True
                        # UVs used in materials for shell in Daz must also exist on underlying geometry in Blender
                        # so they can be used to define materials assigned to the geometry in Blender.
                        self.addNewUvset(uv, geo)
                    else:
                        missing.append((mname,shmat,uv,geonode.index))

        self.matused = []
        for mname,shmat,uv,idx in missing:
            for key,child in inst.children.items():
                self.addMoreUvSets(child, mname, shname, shmat, uv, idx, "")
        return [miss for miss in missing if miss[0] not in self.matused]


    def addMoreUvSets(self, inst, mname, shname, shmat, uv, idx, pprefix):
        from .figure import FigureInstance
        if not isinstance(inst, FigureInstance):
            return
        if mname in self.matused:
            return
        geonode = inst.geometries[0]
        geo = geonode.data
        prefix = pprefix + inst.node.name + "_"
        n = len(prefix)
        if mname[0:n] == prefix:
            mname1 = mname[n:]
        else:
            mname1 = None
        if mname1 and mname1 in geo.materials.keys():
            dmats = geo.materials[mname1]
            mshells = dmats[idx].shells
            if shname not in mshells.keys():
                mshells[shname] = self.addShell(shname, shmat, uv)
            shmat.ignore = True
            self.addNewUvset(uv, geo)
            self.matused.append(mname)
        else:
            for key,child in inst.children.items():
                self.addMoreUvSets(child, mname, shname, shmat, uv, idx, prefix)


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


    def buildData(self, context, node, inst, center):
        if (self.rna and not LS.singleUser):
            return

        if self.sourcing:
            # This does not seem to be good for anything
            # asset = self.sourcing
            pass

        name = self.getName()
        me = self.rna = bpy.data.meshes.new(name)

        verts = self.verts
        edges = []
        faces = self.faces
        if isinstance(node, GeoNode) and node.verts:
            if node.edges:
                verts = node.verts
                edges = node.edges
            elif self.polylines:
                verts = node.verts
            elif len(node.verts) == len(verts):
                verts = node.verts

        if not verts:
            self.addAllMaterials(me)
            return None

        if self.polylines:
            faces = []
            for pline in self.polylines:
                edges += [(pline[i-1],pline[i]) for i in range(3,len(pline))]
                pn = pline[0]
                mn = pline[1]
                lverts = [verts[vn] for vn in pline[2:]]
                self.strands.append((pn,mn,lverts))

        if LS.fitFile:
            me.from_pydata(verts, edges, faces)
        else:
            me.from_pydata([vco-center for vco in verts], edges, faces)

        if len(faces) != len(me.polygons):
            msg = ("Not all faces were created:\n" +
                   "Geometry: '%s'\n" % self.name +
                   "\# DAZ faces: %d\n" % len(faces) +
                   "\# Blender polygons: %d\n" % len(me.polygons))
            reportError(msg, trigger=(2,3))

        for fn,mn in enumerate(self.material_indices):
            f = me.polygons[fn]
            f.material_index = mn
            f.use_smooth = True

        hasShells = False
        for mn,mname in enumerate(self.polygon_material_groups):
            if mname in self.materials.keys():
                dmats = self.materials[mname]
                if (isinstance(node, GeoNode) and
                    node.index < len(dmats)):
                    dmat = dmats[node.index]
                elif inst and inst.index < len(dmats):
                    dmat = dmats[inst.index]
                else:
                    dmat = dmats[0]
            else:
                dmat = None
                print("\nMaterial \"%s\" not found in %s" % (mname, self))
                print("Existing materials:\n  %s" % self.materials.keys())
            if dmat:
                if dmat.rna is None:
                    msg = ("Material without rna:\n  %s" % self)
                    reportError(msg, trigger=(2,3))
                    return None
                me.materials.append(dmat.rna)
                if dmat.shells:
                    hasShells = True
                if dmat.uv_set and dmat.uv_set.checkSize(me):
                    self.uv_set = dmat.uv_set
                me.use_auto_smooth = dmat.getValue(["Smooth On"], False)
                me.auto_smooth_angle = dmat.getValue(["Smooth Angle"], 89.9)*D

        for key,uvset in self.uv_sets.items():
            self.buildUVSet(context, uvset, me, False)
        self.buildUVSet(context, self.uv_set, me, True)
        if self.shells and self.uv_set != self.default_uv_set:
            self.buildUVSet(context, self.default_uv_set, me, False)

        for struct in self.material_selection_sets:
            if "materials" in struct.keys() and "name" in struct.keys():
                if struct["name"][0:8] == "Template":
                    continue
                items = me.DazMaterialSets.add()
                items.name = struct["name"]
                for mname in struct["materials"]:
                    item = items.names.add()
                    item.name = mname

        ob = bpy.data.objects.new(inst.name, me)
        if hasShells:
            ob.DazVisibilityDrivers = True
        return ob


    def addAllMaterials(self, me):
        for dmats in self.materials.values():
            mat = dmats[0].rna
            if mat:
                me.materials.append(mat)


    def buildUVSet(self, context, uv_set, me, setActive):
        if uv_set:
            if uv_set.checkSize(me):
                uv_set.build(context, me, self, setActive)
            else:
                msg = ("Incompatible UV set\n  %s\n  %s" % (me, uv_set))
                reportError(msg, trigger=(2,3))


    def findPolyLines(self, ob):
        plines = []
        v0 = -1
        pline = None
        edges = [list(e.vertices) for e in ob.data.edges]
        edges.sort()
        for v1,v2 in edges:
            if v1 == v0:
                pline.append(v2)
            else:
                pline = [v1,v2]
                plines.append(pline)
            v0 = v2
        pnum = 0
        mnum = 0
        self.strands = []
        verts = ob.data.vertices
        for pline in plines:
            strand = [verts[vn].co for vn in pline]
            self.strands.append((pnum,mnum,strand))


    def makeHairMaterial(self, dbzmat, context):
        from .hair import HairMaterial
        mname = "Hair"
        props = dbzmat["properties"]
        if "Hair Root Color" in props.keys():
            color = props["Hair Root Color"]
        else:
            color = (1,1,1)
        hmat = HairMaterial(mname, color)
        self.polygon_material_groups = [mname]
        self.materials[mname] = [hmat]
        for key,value in props.items():
            hmat.channels[key] = {"id" : key, "current_value" : value}
        hmat.build(context, color)
        self.addAllMaterials(self.rna)


    def buildRigidity(self, ob):
        from .modifier import buildVertexGroup
        if self.rigidity:
            if "weights" in self.rigidity.keys():
                buildVertexGroup(ob, "Rigidity", self.rigidity["weights"]["values"])
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


    def buildHair(self, geonode, context):
        ob = geonode.pgeonode.rna
        if not self.strands:
            print("No strands", ob)
            return

        if not self.polygon_material_groups:
            pass
        elif GS.multipleHairMaterials:
            for mname in self.polygon_material_groups:
                hmat = self.materials[mname][0]
                ob.data.materials.append(hmat.rna)
        else:
            mname = self.polygon_material_groups[0]
            hmat = self.materials[mname][0]
            ob.data.materials.append(hmat.rna)

        if GS.postponeHair:
            self.storeHairSystems(ob)
        else:
            self.buildHairSystems(ob, geonode, context)


    def storeHairSystems(self, ob):
        for pnum,mnum,strand in self.strands:
            matname,hmat = self.getHairMaterial(mnum)
            pgs = ob.DazStrands.add()
            pgs.name = matname
            for vn in strand:
                pg = pgs.strand.add()
                pg.a = vn


    def buildHairSystems(self, ob, geonode, context):
        from .hair import HairSystem, createSkullGroup
        hsystems = {}
        vgrp = None
        for pnum,mnum,strand in self.strands:
            n = len(strand)
            matname,hmat = self.getHairMaterial(mnum)
            hname = ("%s-%02d" % (matname, n))
            if hname not in hsystems.keys():
                hsys = hsystems[hname] = HairSystem(hname, n, geonode=geonode)
                hsys.material = matname
                if GS.useSkullGroup:
                    if vgrp is None:
                        vgrp = createSkullGroup(ob, 'TOP')
                    hsys.vertexGroup = vgrp.name
            hsystems[hname].strands.append(strand)
        activateObject(context, ob)
        for hsys in hsystems.values():
            hsys.build(context, ob)


    def getHairMaterial(self, mnum):
        if self.polygon_material_groups:
            idx = (mnum if GS.multipleHairMaterials else 0)
            mname = self.polygon_material_groups[idx]
            hmat = self.materials[mname][0]
            return hmat.rna.name, hmat
        else:
            #return None, None
            return "Hair", None


    def addShell(self, shname, shmat, uv):
        first = False
        if shname not in self.shells.keys():
            first = True
            self.shells[shname] = []
        match = None
        for shell in self.shells[shname]:
            if shmat.equalChannels(shell.material):
                if uv == shell.uv:
                    return shell
                else:
                    match = shell
        if not match:
            for shell in self.shells[shname]:
                shell.single = False
        shell = Shell(shname, shmat, uv, self, first, match)
        self.shells[shname].append(shell)
        return shell

#-------------------------------------------------------------
#   Shell
#-------------------------------------------------------------

class Shell:
    def __init__(self, shname, shmat, uv, geo, first, match):
        self.name = shname
        self.material = shmat
        self.uv = uv
        self.geometry = geo
        self.single = first
        self.match = match
        self.tree = None


    def __repr__(self):
        return ("<Shell %s %s %s>" % (self.name, self.material.name, self.single))

#-------------------------------------------------------------
#   UV Asset
#-------------------------------------------------------------

class Uvset(Asset):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.material = None
        self.built = []


    def __repr__(self):
        return ("<Uvset %s '%s' %d %d %s>" % (self.id, self.name, len(self.uvs), len(self.polyverts), self.material))


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


    def checkPolyverts(self, me, polyverts, error):
        uvnums = []
        for fverts in polyverts.values():
            uvnums += fverts
        if uvnums:
            uvmin = min(uvnums)
            uvmax = max(uvnums) + 1
        else:
            uvmin = uvmax = -1
        if (uvmin != 0 or uvmax != len(self.uvs)):
                msg = ("Vertex number mismatch.\n" +
                       "Expected mesh with %d UV vertices        \n" % len(self.uvs) +
                       "but %s has %d UV vertices." % (me.name, uvmax))
                if error:
                    raise DazError(msg)
                else:
                    print(msg)


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

        if geo.polylines:
            return

        polyverts = self.getPolyVerts(me)
        self.checkPolyverts(me, polyverts, False)
        uvloop = makeNewUvloop(me, self.getLabel(), setActive)

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
                    if GS.verbosity > 2:
                        print("UV coordinate difference %f - %f > 1" % (umax, umin))
                key = geo.polygon_material_groups[mn]
                if key in geo.materials.keys():
                    for dmat in geo.materials[key]:
                        dmat.fixUdim(context, udim)
                else:
                    print("Material \"%s\" not found" % key)

        self.built.append(me)


def makeNewUvloop(me, name, setActive):
    uvtex = getUvTextures(me).new()
    uvtex.name = name
    uvloop = me.uv_layers[-1]
    if bpy.app.version < (2,80,0):
        uvtex.active_render = setActive
    else:
        uvloop.active_render = setActive
    if setActive:
        me.uv_layers.active_index = len(me.uv_layers) - 1
    return uvloop


def addUvs(me, name, uvs, uvfaces):
    uvloop = makeNewUvloop(me, name, True)
    m = 0
    for f in uvfaces:
        for vn in f:
            uvloop.data[m].uv = uvs[vn]
            m += 1

#-------------------------------------------------------------
#   Prune Uv textures
#-------------------------------------------------------------

def pruneUvMaps(ob):
    if ob.data is None or len(getUvTextures(ob.data)) <= 1:
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
                elif (node.type == "UVMAP" and
                    node.uv_map in uvtexs.keys()):
                    uvtexs[node.uv_map][1] = True
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
    mat = ob.data.materials[0]
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
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                restoreUDims(ob)

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
        from .load_json import loadJson
        from .files import parseAssetFile

        ob = context.object
        me = ob.data
        scn = context.scene
        LS.forUV(ob, scn)
        struct = loadJson(self.filepath)
        asset = parseAssetFile(struct)
        if asset is None or len(asset.uvs) == 0:
            raise DazError ("Not an UV asset:\n  '%s'" % self.filepath)

        for uvset in asset.uvs:
            polyverts = uvset.getPolyVerts(me)
            uvset.checkPolyverts(me, polyverts, True)
            uvloop = makeNewUvloop(me, uvset.getLabel(), False)
            vnmax = len(uvset.uvs)
            m = 0
            for fn,f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvloop.data[m].uv = uv
                    m += 1

#----------------------------------------------------------
#   Prune vertex groups
#----------------------------------------------------------

class DAZ_OT_LimitVertexGroups(DazPropsOperator, IsMesh, B.LimitInt):
    bl_idname = "daz.limit_vertex_groups"
    bl_label = "Limit Vertex Groups"
    bl_description = "Limit the number of vertex groups per vertex"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "limit")

    def run(self, context):
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                self.limitVertexGroups(ob)

    def limitVertexGroups(self, ob):
        deletes = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        weights = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        for v in ob.data.vertices:
            data = [(g.weight, g.group) for g in v.groups]
            if len(data) > self.limit:
                data.sort()
                vnmin = len(data) - self.limit
                for w,gn in data[0:vnmin]:
                    deletes[gn].append(v.index)
                wsum = sum([w for w,gn in data[vnmin:]])
                for w,gn in data[vnmin:]:
                    weights[gn].append((v.index, w/wsum))
        for vgrp in ob.vertex_groups:
            vnums = deletes[vgrp.index]
            if vnums:
                vgrp.remove(vnums)
            for vn,w in weights[vgrp.index]:
                vgrp.add([vn], w, 'REPLACE')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_PruneUvMaps,
    DAZ_OT_MakeMultires,
    DAZ_OT_CollapseUDims,
    DAZ_OT_RestoreUDims,
    DAZ_OT_LoadUV,
    DAZ_OT_LimitVertexGroups,
    B.DazIntGroup,
    B.DazPairGroup,
    B.DazRigidityGroup,
    B.DazStringStringGroup,
    B.DazTextGroup,
    B.DazVectorGroup,
    B.DazStrandGroup,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

    from bpy.props import CollectionProperty, IntProperty, BoolProperty
    bpy.types.Mesh.DazRigidityGroups = CollectionProperty(type = B.DazRigidityGroup)
    bpy.types.Mesh.DazGraftGroup = CollectionProperty(type = B.DazPairGroup)
    bpy.types.Mesh.DazMaskGroup = CollectionProperty(type = B.DazIntGroup)
    bpy.types.Mesh.DazVertexCount = IntProperty(default=0)
    bpy.types.Mesh.DazMaterialSets = CollectionProperty(type = B.DazStringStringGroup)
    bpy.types.Mesh.DazHDMaterials = CollectionProperty(type = B.DazTextGroup)
    bpy.types.Object.DazStrands = CollectionProperty(type = B.DazStrandGroup)
    bpy.types.Object.DazMultires = BoolProperty(default=False)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
