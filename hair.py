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

import sys
import bpy
from bpy.props import *
from mathutils import Vector
from math import floor
from .error import *
from .utils import *
from .material import WHITE, GREY, BLACK, isWhite, isBlack
from .cycles import CyclesMaterial, CyclesTree

#-------------------------------------------------------------
#   Hair system class
#-------------------------------------------------------------

class HairSystem:
    def __init__(self, name, n, geonode=None, object=None):
        if name is None:
            self.name = ("Hair%02d" % n)
        else:
            self.name = name
        if object:
            self.scale = object.DazScale
        else:
            self.scale = LS.scale
        self.geonode = geonode
        self.hairgen = None
        if geonode:
            self.hairgen = geonode.hairgen
        self.modifier = self.getModifier(geonode)
        self.npoints = n
        self.strands = []
        self.useEmitter = True
        self.vertexGroup = None
        self.material = None


    def getModifier(self, geonode):
        from .channels import Channels
        if geonode is None:
            return Channels()
        for key in geonode.modifiers.keys():
            if (key[0:8] == "DZ__SPS_" and
                self.name.startswith(key[8:])):
                return geonode.modifiers[key]
        print("No modifier found")
        return geonode


    def getDensity(self, mod, channels, default):
        from .material import Map
        for channel in channels:
            val,url = mod.getValueImage([channel], 0)
            if val:
                if url:
                    map = Map({}, False)
                    map.url = url
                    map.build()
                    tex = map.getTexture()
                    tex.buildInternal()
                    return val,tex.rna
                else:
                    return val,None
        return default,None


    def addTexture(self, tex, pset, ob, use, factor):
        ptex = pset.texture_slots.add()
        ptex.texture = tex
        setattr(ptex, use, True)
        setattr(ptex, factor, 1)
        ptex.use_map_time = False
        ptex.texture_coords = 'UV'
        if ob and ob.data.uv_layers.active:
            ptex.uv_layer = ob.data.uv_layers.active.name


    def getTexDensity(self, mod, channels, default, attr, pset, ob, use, factor, cond=True):
        val,tex = self.getDensity(mod, channels, default)
        setattr(pset, attr, val)
        if tex and cond:
            self.addTexture(tex, pset, ob, use, factor)
        return val,tex


    def setHairSettings(self, psys, ob):
        mod = self.modifier
        pset = psys.settings
        if hasattr(pset, "cycles_curve_settings"):
            ccset = pset.cycles_curve_settings
        elif hasattr(pset, "cycles"):
            ccset = pset.cycles
        else:
            ccset = pset

        channels = ["PreRender Hairs Density", "PreSim Hairs Per Guide"]
        val,rdtex = self.getTexDensity(mod, channels, LS.nRenderChildren, "rendered_child_count", pset, ob, "use_map_density", "density_factor")

        channels = ["PreSim Hairs Density", "PreRender Hairs Per Guide"]
        self.getTexDensity(mod, channels, LS.nViewChildren, "child_nbr", pset, ob, "use_map_density", "density_factor", cond=(not rdtex))

        if (self.material and
            self.material in ob.data.materials.keys()):
            pset.material_slot = self.material

        rootrad = mod.getValue(["Line Start Width"], 0.1)
        tiprad = mod.getValue(["Line End Width"], 0)
        if hasattr(ccset, "root_width"):
            ccset.root_width = rootrad
            ccset.tip_width = tiprad
        else:
            ccset.root_radius = rootrad
            ccset.tip_radius = tiprad
        ccset.radius_scale = self.scale * mod.getValue(["PreRender Hair Distribution Radius"], 1)

        channels = ["PreRender Generated Hair Scale", "PreSim Generated Hair Scale"]
        self.getTexDensity(mod, channels, 1, "child_length", pset, ob, "use_map_length", "length_factor")

        psys.child_seed = mod.getValue(["PreRender Hair Seed"], 0)
        pset.child_radius = mod.getValue(["PreRender Hair Distribution Radius"], 1) * self.scale

        channels = ["PreRender Clumping 1 Curves Density"]
        self.getTexDensity(mod, channels, 0, "clump_factor", pset, ob, "use_map_clump", "clump_factor")

        pset.clump_shape = mod.getValue(["PreRender Clumpiness 1"], 0)

        channels = ["PreRender Scraggliness 1"]
        val,tex = self.getTexDensity(mod, channels, 0, "kink_amplitude", pset, ob, "use_map_kink_amp", "kink_amp_factor")
        if val:
            pset.kink = 'CURL'

        channels = ["PreRender Scraggle 1 Frequency "]
        self.getTexDensity(mod, channels, 0, "kink_frequency", pset, ob, "use_map_kink_freq", "kink_freq_factor")

        if hasattr(pset, "twist"):
            channels = ["PreRender Frizz Tip Amount", "PreRender Frizz Base Amount"]
            self.getTexDensity(mod, channels, 0, "twist", pset, ob, "use_map_twist", "twist_factor")


    def addStrand(self, strand):
        self.strands.append(strand)


    def resize(self, size):
        nstrands = []
        for strand in self.strands:
            nstrand = self.resizeStrand(strand, size)
            nstrands.append(nstrand)
        return nstrands


    def resizeBlock(self):
        n = 10*((self.npoints+5)//10)
        if n < 10:
            n = 10
        return n, self.resize(n)


    def resizeStrand(self, strand, n):
        m = len(strand)
        step = (m-1)/(n-1)
        nstrand = []
        for i in range(n-1):
            j = floor(i*step + 1e-4)
            x = strand[j]
            y = strand[j+1]
            eps = i*step - j
            z = eps*y + (1-eps)*x
            nstrand.append(z)
        nstrand.append(strand[m-1])
        return nstrand


    def build(self, context, ob):
        import time
        t1 = time.perf_counter()
        print("Build hair", self.name)
        if len(self.strands) == 0:
            raise DazError("No strands found")

        hlen = int(len(self.strands[0]))
        if hlen < 3:
            return
        bpy.ops.object.particle_system_add()
        psys = ob.particle_systems.active
        psys.name = self.name

        if self.vertexGroup:
            psys.vertex_group_density = self.vertexGroup
        elif bpy.app.version < (2,80,0):
            vgrp = createSkullGroup(ob, 'TOP')
            psys.vertex_group_density = vgrp.name

        pset = psys.settings
        pset.type = 'HAIR'
        pset.use_strand_primitive = True
        if hasattr(pset, "use_render_emitter"):
            pset.use_render_emitter = self.useEmitter
        elif hasattr(ob, "show_instancer_for_render"):
            ob.show_instancer_for_render = self.useEmitter
        pset.render_type = 'PATH'
        if LS.nViewChildren or LS.nRenderChildren:
            pset.child_type = 'SIMPLE'
        else:
            pset.child_type = 'NONE'

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
        pset.use_hair_bspline = True
        pset.display_step = 3
        self.setHairSettings(psys, ob)

        psys.use_hair_dynamics = False

        t2 = time.perf_counter()
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)
        psys = updateHair(context, ob, psys)
        t3 = time.perf_counter()
        self.buildStrands(psys)
        t4 = time.perf_counter()
        psys = updateHair(context, ob, psys)
        t5 = time.perf_counter()
        self.buildFinish(context, psys, ob)
        t6 = time.perf_counter()
        bpy.ops.object.mode_set(mode='OBJECT')
        print("Hair %s: %.3f %.3f %.3f %.3f %.3f" % (self.name, t2-t1, t3-t2, t4-t3, t5-t4, t6-t5))


    def buildStrands(self, psys):
        for m,hair in enumerate(psys.particles):
            verts = self.strands[m]
            hair.location = verts[0]
            if len(verts) < len(hair.hair_keys):
                continue
            for n,v in enumerate(hair.hair_keys):
                v.co = verts[n]


    def buildFinish(self, context, psys, hum):
        scn = context.scene
        #activateObject(context, hum)
        bpy.ops.object.mode_set(mode='PARTICLE_EDIT')
        pedit = scn.tool_settings.particle_edit
        pedit.use_emitter_deflect = False
        pedit.use_preserve_length = False
        pedit.use_preserve_root = False
        hum.data.use_mirror_x = False
        pedit.select_mode = 'POINT'
        bpy.ops.transform.translate()
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)


    def addHairDynamics(self, psys, hum):
        psys.use_hair_dynamics = True
        cset = psys.cloth.settings
        cset.pin_stiffness = 1.0
        cset.mass = 0.05
        deflector = findDeflector(hum)

#-------------------------------------------------------------
#   Tesselator class
#-------------------------------------------------------------

class Tesselator:
    def unTesselateEdges(self, context, hair, nsides):
        if nsides == 1:
            pass
        elif nsides == 2:
            self.combinePoints(1, hair)
        elif nsides == 3:
            self.combinePoints(2, hair)
        else:
            raise DazError("Cannot untesselate hair.\nRender Line Tessellation Sides > 3")
        self.removeDoubles(context, hair)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair)


    def unTesselateFaces(self, context, hair):
        self.squashFaces(hair)
        self.removeDoubles(context, hair)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair)


    def combinePoints(self, m, hair):
        from .tables import getVertEdges, otherEnd
        edgeverts,vertedges = getVertEdges(hair)
        verts = hair.data.vertices
        nverts = len(verts)
        for vn in range(nverts):
            ne = len(vertedges[vn])
            if ne >  m:
                v0 = verts[vn]
                r0 = verts[vn].co
                dists = []
                for n,e in enumerate(vertedges[vn]):
                    v = verts[otherEnd(vn, e)]
                    dists.append(((v.co-r0).length, n, v))
                dists.sort()
                for _,_,v in dists[:m-ne]:
                    v.co = r0


    def squashFaces(self, hair):
        verts = hair.data.vertices
        for f in hair.data.polygons:
            fverts = [verts[vn] for vn in f.vertices]
            if len(fverts) == 4:
                v1,v2,v3,v4 = fverts
                if (v1.co-v2.co).length < (v2.co-v3.co).length:
                    v2.co = v1.co
                    v4.co = v3.co
                else:
                    v3.co = v2.co
                    v4.co = v1.co


    def removeDoubles(self, context, hair):
        activateObject(context, hair)
        threshold = 0.001*LS.scale
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')


    def checkTesselation(self, hair):
        # Check that there are only pure lines
        from .tables import getVertEdges
        edgeverts,vertedges = getVertEdges(hair)
        nverts = len(hair.data.vertices)
        print("Check hair", hair.name, nverts)
        deletes = []
        for vn,v in enumerate(hair.data.vertices):
            ne = len(vertedges[vn])
            if ne > 2:
                #v.select = True
                deletes.append(vn)
        print("Number of vertices to delete", len(deletes))
        return deletes


    def mergeRemainingFaces(self, hair):
        for f in hair.data.polygons:
            fverts = [hair.data.vertices[vn] for vn in f.vertices]
            r0 = fverts[0].co
            for v in fverts:
                v.co = r0
                v.select = True
        threshold = 0.001*LS.scale
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.object.mode_set(mode='OBJECT')


    def findStrands(self, hair):
        plines = []
        v0 = -1
        pline = None
        edges = [list(e.vertices) for e in hair.data.edges]
        edges.sort()
        for v1,v2 in edges:
            if v1 == v0:
                pline.append(v2)
            else:
                pline = [v1,v2]
                plines.append(pline)
            v0 = v2
        strands = []
        verts = hair.data.vertices
        for pline in plines:
            strand = [verts[vn].co for vn in pline]
            strands.append(strand)
        return strands

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

def getHairAndHuman(context, strict):
    hair = context.object
    hum = None
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'MESH' and ob != hair:
            hum = ob
            break
    if strict and hum is None:
        raise DazError("Select hair and human")
    return hair,hum


class DAZ_OT_MakeHair(DazPropsOperator, IsMesh, B.Hair):
    bl_idname = "daz.make_hair"
    bl_label = "Make Hair"
    bl_description = "Make particle hair from mesh hair"
    bl_options = {'UNDO'}

    dialogWidth = 600

    def draw(self, context):
        row = self.layout.row()
        col = row.column()
        box = col.box()
        box.label(text="Create")
        box.prop(self, "strandType", expand=True)
        box.separator()
        box.prop(self, "resizeHair")
        box.prop(self, "size")
        box.prop(self, "resizeInBlocks")
        box.prop(self, "sparsity")

        col = row.column()
        box = col.box()
        box.label(text="Material")
        box.prop(self, "keepMaterial")
        if self.keepMaterial:
            box.prop(self, "activeMaterial")
        else:
            box.prop(self, "color")
            box.prop(self, "useRootTransparency")

        col = row.column()
        box = col.box()
        box.label(text="Settings")
        box.prop(self, "useVertexGroup")
        box.prop(self, "nViewChildren")
        box.prop(self, "nRenderChildren")


    def run(self, context):
        hair,hum = getHairAndHuman(context, True)
        if self.strandType == 'SHEET':
            if not hair.data.uv_layers.active:
                raise DazError("Hair object has no active UV layer.\nConsider using Line or Tube strand types instead")
        elif self.strandType == 'LINE':
            if hair.data.polygons:
                raise DazError("Cannot use Line strand type for hair mesh with faces")

        LS.scale = hair.DazScale
        LS.nViewChildren = self.nViewChildren
        LS.nRenderChildren = self.nRenderChildren
        LS.useRootTransparency = self.useRootTransparency

        self.nonquads = []
        scn = context.scene
        mname = self.activeMaterial
        setActiveObject(context, hum)
        self.clearHair(hum, hair, mname, self.color, context)

        setActiveObject(context, hair)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        if self.strandType == 'SHEET':
            mrects = self.findMeshRects(hair)
            trects = self.findTexRects(hair, mrects)
            hsystems,haircount = self.makeHairSystems(context, hum, hair, trects)
        else:
            tess = Tesselator()
            if self.strandType == 'LINE':
                pass
            elif self.strandType == 'TUBE':
                tess.unTesselateFaces(context, hair)
            strands = tess.findStrands(hair)
            hsystems = {}
            haircount = self.addStrands(hum, strands, hsystems, -1)
        haircount += 1
        print("\nTotal number of strands: %d" % haircount)
        if haircount == 0:
            raise DazError("Conversion failed.\nNo hair strands created")

        if self.resizeInBlocks:
            hsystems = self.blockResize(hsystems, hum)
        elif self.resizeHair:
            hsystems = self.hairResize(hsystems, hum)
        self.makeHairs(context, hsystems, hum)

        if self.nonquads:
            print("Ignored %d non-quad faces out of %d faces" % (len(self.nonquads), len(hair.data.polygons)))


    def makeHairs(self, context, hsystems, hum):
        print("Make particle hair")
        vgname = None
        if self.useVertexGroup:
            vgrp = createSkullGroup(hum, 'TOP')
            vgname = vgrp.name

        activateObject(context, hum)
        for hsys in hsystems.values():
            hsys.useEmitter = True
            hsys.vertexGroup = vgname
            hsys.build(context, hum)
        print("Done")


    def findMeshRects(self, hair):
        from .tables import getVertFaces, findNeighbors
        print("Find neighbors")
        self.faceverts, self.vertfaces = getVertFaces(hair)
        self.nfaces = len(hair.data.polygons)
        if not self.nfaces:
            raise DazError("Hair has no faces")
        mneighbors = findNeighbors(range(self.nfaces), self.faceverts, self.vertfaces)
        self.centers, self.uvcenters = self.findCenters(hair)

        print("Collect rects")
        mfaces = [(f.index,f.vertices) for f in hair.data.polygons]
        mrects,_,_ = self.collectRects(mfaces, mneighbors)
        return mrects


    def findTexRects(self, hair, mrects):
        from .tables import getVertFaces, findNeighbors, findTexVerts
        print("Find texverts")
        self.texverts, self.texfaces = findTexVerts(hair, self.vertfaces)
        print("Find tex neighbors", len(self.texverts), self.nfaces, len(self.texfaces))
        # Improve
        _,self.texvertfaces = getVertFaces(hair, self.texverts, None, self.texfaces)
        tneighbors = findNeighbors(range(self.nfaces), self.texfaces, self.texvertfaces)

        rects = []
        print("Collect texrects")
        for mverts,mfaces in mrects:
            texfaces = [(fn,self.texfaces[fn]) for fn in mfaces]
            nn = [(fn,tneighbors[fn]) for fn in mfaces]
            rects2,clusters,fclusters = self.collectRects(texfaces, tneighbors)
            for rect in rects2:
                rects.append(rect)
        return rects


    def makeHairSystems(self, context, hum, hair, rects):
        from .tables import getVertFaces, findNeighbors
        print("Sort columns")
        haircount = -1
        setActiveObject(context, hair)
        hsystems = {}
        verts = range(len(hair.data.vertices))
        count = 0
        for _,faces in rects:
            if count % 10 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
            count += 1
            if not self.quadsOnly(hair, faces):
                continue
            _,vertfaces = getVertFaces(None, verts, faces, self.faceverts)
            neighbors = findNeighbors(faces, self.faceverts, vertfaces)
            if neighbors is None:
                continue
            first, corner, boundary, bulk = self.findStartingPoint(hair, neighbors, self.uvcenters)
            if first is None:
                continue
            self.selectFaces(hair, faces)
            columns = self.sortColumns(first, corner, boundary, bulk, neighbors, self.uvcenters)
            if columns:
                strands = self.getColumnCoords(columns, self.centers)
                haircount = self.addStrands(hum, strands, hsystems, haircount)
        return hsystems, haircount


    def addStrands(self, hum, strands, hsystems, haircount):
        for strand in strands:
            haircount += 1
            if haircount % self.sparsity != 0:
                continue
            n = len(strand)
            if n not in hsystems.keys():
                hsystems[n] = self.makeHairSystem(n, hum)
            hsystems[n].strands.append(strand)
        return haircount


    def blockResize(self, hsystems, hum):
        print("Resize hair in blocks of ten")
        nsystems = {}
        for hsys in hsystems.values():
            n,nstrands = hsys.resizeBlock()
            if n not in nsystems.keys():
                nsystems[n] = self.makeHairSystem(n, hum)
            nsystems[n].strands += nstrands
        return nsystems


    def hairResize(self, hsystems, hum):
        print("Resize hair")
        nsystem = self.makeHairSystem(self.size, hum)
        for hsys in hsystems.values():
            nstrands = hsys.resize(self.size)
            nsystem.strands += nstrands
        hsystems = {self.size: nsystem}
        return hsystems


    def makeHairSystem(self, n, hum):
        hsys = HairSystem(None, n, object=hum)
        hsys.material = self.material.name
        return hsys

    #-------------------------------------------------------------
    #   Collect rectangles
    #-------------------------------------------------------------

    def collectRects(self, faceverts, neighbors):
        #fclusters = dict([(fn,-1) for fn,_ in faceverts])
        fclusters = {}
        for fn,_ in faceverts:
            fclusters[fn] = -1
            for nn in neighbors[fn]:
                fclusters[nn] = -1
        clusters = {-1 : -1}
        nclusters = 0

        for fn,_ in faceverts:
            fncl = [self.deref(nn, fclusters, clusters) for nn in neighbors[fn] if nn < fn]
            if fncl == []:
                cn = clusters[cn] = nclusters
                nclusters += 1
            else:
                cn = min(fncl)
                for cn1 in fncl:
                    clusters[cn1] = cn
            fclusters[fn] = cn

        for fn,_ in faceverts:
            fclusters[fn] = self.deref(fn, fclusters, clusters)

        rects = []
        for cn in clusters.keys():
            if cn == clusters[cn]:
                faces = [fn for fn,_ in faceverts if fclusters[fn] == cn]
                vertsraw = [vs for fn,vs in faceverts if fclusters[fn] == cn]
                vstruct = {}
                for vlist in vertsraw:
                    for vn in vlist:
                        vstruct[vn] = True
                verts = list(vstruct.keys())
                verts.sort()
                rects.append((verts, faces))
                if len(rects) > 1000:
                    print("Too many rects")
                    return rects, clusters, fclusters

        return rects, clusters, fclusters


    def deref(self, fn, fclusters, clusters):
        cn = fclusters[fn]
        updates = []
        while cn != clusters[cn]:
            updates.append(cn)
            cn = clusters[cn]
        for nn in updates:
            clusters[nn] = cn
        fclusters[fn] = cn
        return cn

    #-------------------------------------------------------------
    #   Find centers
    #-------------------------------------------------------------

    def findCenters(self, ob):
        vs = ob.data.vertices
        uvs = ob.data.uv_layers.active.data
        centers = {}
        uvcenters = {}
        m = 0
        for f in ob.data.polygons:
            f.select = True
            fn = f.index
            if len(f.vertices) == 4:
                vn0,vn1,vn2,vn3 = f.vertices
                centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co+vs[vn3].co)/4
                uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv+uvs[m+3].uv)/4
                m += 4
            else:
                vn0,vn1,vn2 = f.vertices
                centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co)/4
                uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv)/4
                m += 3
            f.select = False
        return centers, uvcenters

    #-------------------------------------------------------------
    #   Find starting point
    #-------------------------------------------------------------

    def findStartingPoint(self, ob, neighbors, uvcenters):
        types = dict([(n,[]) for n in range(1,5)])
        for fn,neighs in neighbors.items():
            nneighs = len(neighs)
            if nneighs == 0:
                return None,None,None,None
            elif nneighs >= 5:
                print("  Face %d has %d neighbors" % (fn, nneighs))
                #self.selectFaces(ob, [fn]+neighs)
                return None,None,None,None
            types[nneighs].append(fn)

        singlets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[1]]
        singlets.sort()
        if len(singlets) > 0:
            if len(singlets) != 2:
                print("  Has %d singlets" % len(singlets))
                return None,None,None,None
            if (types[3] != [] or types[4] != []):
                print("  Has 2 singlets, %d triplets and %d quadruplets" % (len(types[3]), len(types[4])))
                return None,None,None,None
            first = singlets[0][1]
            corner = types[1]
            boundary = types[2]
            bulk = types[3]
        else:
            doublets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[2]]
            doublets.sort()
            if len(doublets) > 4:
                print("  Has %d doublets" % len(doublets))
                self.selectFaces(ob, [fn for _,fn in doublets])
                return None,None,None,None
            if len(doublets) < 4:
                if len(doublets) == 2:
                    print("  Has %d doublets" % len(doublets))
                    self.selectFaces(ob, neighbors.keys())
                return None,None,None,None
            first = doublets[0][1]
            corner = types[2]
            boundary = types[3]
            bulk = types[4]

        return first, corner, boundary, bulk

    #-------------------------------------------------------------
    #   Sort columns
    #-------------------------------------------------------------

    def sortColumns(self, first, corner, boundary, bulk, neighbors, uvcenters):
        column = self.getDown(first, neighbors, corner, boundary, uvcenters)
        columns = [column]
        if len(corner) <= 2:
            return columns
        fn = first
        n = 0
        while (True):
            n += 1
            horizontal = [(uvcenters[nb][0], nb) for nb in neighbors[fn]]
            horizontal.sort()
            fn = horizontal[-1][1]
            if n > 50:
                return columns
            elif fn in corner:
                column = self.getDown(fn, neighbors, corner, boundary, uvcenters)
                columns.append(column)
                return columns
            elif fn in boundary:
                column = self.getDown(fn, neighbors, boundary, bulk, uvcenters)
                columns.append(column)
            else:
                print("Hair bug", fn)
                return None
                raise DazError("Hair bug")
        print("Sorted")


    def getDown(self, top, neighbors, boundary, bulk, uvcenters):
        column = [top]
        fn = top
        n = 0
        while (True):
            n += 1
            vertical = [(uvcenters[nb][1], nb) for nb in neighbors[fn]]
            vertical.sort()
            fn = vertical[-1][1]
            if fn in boundary or n > 500:
                column.append(fn)
                column.reverse()
                return column
            else:
                column.append(fn)

    #-------------------------------------------------------------
    #   Get column coords
    #-------------------------------------------------------------

    def getColumnCoords(self, columns, centers):
        #print("Get column coords")
        length = len(columns[0])
        hcoords = []
        short = False
        for column in columns:
            if len(column) < length:
                length = len(column)
                short = True
            hcoord = [centers[fn] for fn in column]
            hcoords.append(hcoord)
        if short:
            hcoords = [hcoord[0:length] for hcoord in hcoords]
        return hcoords

    #-------------------------------------------------------------
    #   Clear hair
    #-------------------------------------------------------------

    def clearHair(self, hum, hair, mname, color, context):
        nsys = len(hum.particle_systems)
        for n in range(nsys):
            bpy.ops.object.particle_system_remove()
        print("CLR", hair, self.keepMaterial)
        if self.keepMaterial:
            mat = hair.data.materials[mname]
        else:
            print("CLRNEW")
            mat = buildHairMaterial("Hair", color, context, force=True)
        self.material = mat
        hum.data.materials.append(mat)


    def quadsOnly(self, ob, faces):
        for fn in faces:
            f = ob.data.polygons[fn]
            if len(f.vertices) != 4:
                #print("  Face %d has %s corners" % (fn, len(f.vertices)))
                self.nonquads.append(fn)
                return False
        return True


    def selectFaces(self, ob, faces):
        for fn in faces:
            ob.data.polygons[fn].select = True

# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------

def createSkullGroup(hum, skullType):
    if skullType == 'TOP':
        maxheight = -1e4
        for v in hum.data.vertices:
            if v.co[2] > maxheight:
                maxheight = v.co[2]
                top = v.index
        vgrp = hum.vertex_groups.new(name="Skull")
        vgrp.add([top], 1.0, 'REPLACE')
        return vgrp
    elif skullType == 'ALL':
        vgrp = hum.vertex_groups.new(name="Skull")
        for vn in range(len(hum.data.vertices)):
            vgrp.add([vn], 1.0, 'REPLACE')
        return vgrp
    else:
        return None


def updateHair(context, ob, psys):
    if bpy.app.version < (2,80,0):
        bpy.ops.object.mode_set(mode='PARTICLE_EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')
        return psys
    else:
        dg = context.evaluated_depsgraph_get()
        return ob.evaluated_get(dg).particle_systems.active


def updateHairs(context, ob):
    if bpy.app.version < (2,80,0):
        bpy.ops.object.mode_set(mode='PARTICLE_EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')
        return psys
    else:
        dg = context.evaluated_depsgraph_get()
        return ob.evaluated_get(dg).particle_systems

#------------------------------------------------------------------------
#   Deflector
#------------------------------------------------------------------------

def makeDeflector(pair, rig, bnames, cfg):
    _,ob = pair

    shiftToCenter(ob)
    if rig:
        for bname in bnames:
            if bname in cfg.bones.keys():
                bname = cfg.bones[bname]
            if bname in rig.pose.bones.keys():
                ob.parent = rig
                ob.parent_type = 'BONE'
                ob.parent_bone = bname
                pb = rig.pose.bones[bname]
                ob.matrix_basis = Mult2(pb.matrix.inverted(), ob.matrix_basis)
                ob.matrix_basis.col[3] -= Vector((0,pb.bone.length,0,0))
                break

    ob.draw_type = 'WIRE'
    ob.field.type = 'FORCE'
    ob.field.shape = 'SURFACE'
    ob.field.strength = 240.0
    ob.field.falloff_type = 'SPHERE'
    ob.field.z_direction = 'POSITIVE'
    ob.field.falloff_power = 2.0
    ob.field.use_max_distance = True
    ob.field.distance_max = 0.125*ob.DazScale


def shiftToCenter(ob):
    sum = Vector()
    for v in ob.data.vertices:
        sum += v.co
    offset = sum/len(ob.data.vertices)
    for v in ob.data.vertices:
        v.co -= offset
    ob.location = offset


def findDeflector(human):
    rig = human.parent
    if rig:
        children = rig.children
    else:
        children = human.children
    for ob in children:
        if ob.field.type == 'FORCE':
            return ob
    return None

#------------------------------------------------------------------------
#   Buttons
#------------------------------------------------------------------------

class IsHair:
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.particle_systems.active)


class DAZ_OT_UpdateHair(DazOperator, IsHair):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Change settings for particle hair"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        psys0 = hum.particle_systems.active
        idx0 = hum.particle_systems.active_index
        psettings = self.getSettings(psys0.settings)
        hdyn0 = psys0.use_hair_dynamics
        csettings = self.getSettings(psys0.cloth.settings)
        for idx,psys in enumerate(hum.particle_systems):
            if idx == idx0:
                continue
            hum.particle_systems.active_index = idx
            self.setSettings(psys.settings, psettings)
            psys.use_hair_dynamics = hdyn0
            self.setSettings(psys.cloth.settings, csettings)
        hum.particle_systems.active_index = idx0


    def getSettings(self, pset):
        settings = {}
        for key in dir(pset):
            attr = getattr(pset, key)
            if (key[0] == "_" or
                key in ["count"]):
                continue
            if (
                isinstance(attr, int) or
                isinstance(attr, bool) or
                isinstance(attr, float) or
                isinstance(attr, str)
                ):
                settings[key] = attr
        return settings


    def setSettings(self, pset, settings):
        for key,value in settings.items():
            if key in ["use_absolute_path_time"]:
                continue
            try:
                setattr(pset, key, value)
            except AttributeError:
                pass


class DAZ_OT_ColorHair(DazPropsOperator, IsHair, B.ColorProp):
    bl_idname = "daz.color_hair"
    bl_label = "Color Hair"
    bl_description = "Change particle hair color"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        hum = context.object
        mats = {}
        for mat in hum.data.materials:
            mats[mat.name] = (mat, True)
        for psys in hum.particle_systems:
            pset = psys.settings
            mname = pset.material_slot
            if mname in mats.keys() and mats[mname][1]:
                mat = buildHairMaterial(mname, self.color, context, force=True)
                mats[mname] = (mat, False)

        for _,keep in mats.values():
            if not keep:
                hum.data.materials.pop()
        for mat,keep in mats.values():
            if not keep:
                hum.data.materials.append(mat)


class DAZ_OT_ConnectHair(DazOperator, IsHair):
    bl_idname = "daz.connect_hair"
    bl_label = "Connect Hair"
    bl_description = "(Re)connect hair"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        for mod in hum.modifiers:
            if isinstance(mod, bpy.types.ParticleSystemModifier):
                print(mod)

        nparticles = len(hum.particle_systems)
        for n in range(nparticles):
            hum.particle_systems.active_index = n
            print(hum.particle_systems.active_index, hum.particle_systems.active)
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.disconnect_hair()
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.connect_hair()
            bpy.ops.particle.particle_edit_toggle()

#------------------------------------------------------------------------
#   Materials
#------------------------------------------------------------------------

def buildHairMaterial(mname, color, context, force=False):
    if GS.materialMethod == 'INTERNAL':
        return buildHairMaterialInternal(mname, list(color[0:3]), force)
    else:
        return buildHairMaterialCycles(mname, list(color[0:3]), context, force)

# ---------------------------------------------------------------------
#   Blender Internal
# ---------------------------------------------------------------------

def buildHairMaterialInternal(mname, rgb, force):
    mat = bpy.data.materials.new("Hair")

    mat.diffuse_color = rgb
    mat.diffuse_intensity = 0.1
    mat.specular_color = rgb

    mat.use_transparency = True
    mat.transparency_method = 'MASK'
    mat.alpha = 1.0
    mat.specular_alpha = 0.0

    mat.use_diffuse_ramp = True
    mat.diffuse_ramp_blend = 'MIX'
    mat.diffuse_ramp_factor = 1
    mat.diffuse_ramp_input = 'SHADER'

    mat.use_specular_ramp = True
    mat.specular_ramp_blend = 'MIX'
    mat.specular_ramp_factor = 1
    mat.specular_ramp_input = 'SHADER'

    defaultRamp(mat.diffuse_ramp, rgb)
    defaultRamp(mat.specular_ramp, rgb)

    mat.strand.root_size = 2
    mat.strand.tip_size = 1
    mat.strand.width_fade = 1
    return mat


def defaultRamp(ramp, rgb):
    ramp.interpolation = 'LINEAR'
    ramp.elements.new(0.1)
    ramp.elements.new(0.2)
    for n,data in enumerate([
        (0, rgb+[0]),
        (0.07, rgb+[1]),
        (0.6, rgb+[1]),
        (1.0, rgb+[0])
        ]):
        elt = ramp.elements[n]
        elt.position, elt.color = data

#-------------------------------------------------------------
#   Hair material
#-------------------------------------------------------------

def buildHairMaterialCycles(mname, color, context, force):
    hmat = HairMaterial("Hair", color)
    hmat.force = force
    print("Creating CYCLES HAIR material")
    hmat.build(context, color)
    return hmat.rna


class HairMaterial(CyclesMaterial):

    def __init__(self, name, color):
        CyclesMaterial.__init__(self, name)
        self.name = name
        self.color = color


    def guessColor(self):
        if self.rna:
            self.rna.diffuse_color = self.color


    def build(self, context, color):
        from .material import Material
        if self.dontBuild():
            return
        Material.build(self, context)
        self.tree = HairBSDFTree(self)
        self.tree.color = color
        self.tree.dark = Vector(color)*GREY
        self.tree.build()
        self.rna.diffuse_color[0:3] = self.color

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = GREY
        self.dark = BLACK


    def build(self):
        self.makeTree()
        self.buildLayer()
        self.prune()


    def initLayer(self):
        self.column = 4
        self.active = None
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        self.buildBump()


    #def linkVector(self, texco, node, slot="Vector"):
    #    self.links.new(self.info.outputs["Intercept"], node.inputs[slot])


    def buildOutput(self):
        self.column += 1
        output = self.addNode('ShaderNodeOutputMaterial')
        self.links.new(self.active.outputs[0], output.inputs['Surface'])


    def buildBump(self):
        strength = self.getValue(["Bump Strength"], 1)
        if False and strength:
            bump = self.addNode("ShaderNodeBump", col=2)
            bump.inputs["Strength"].default_value = strength
            bump.inputs["Distance"].default_value = 0.1 * LS.scale
            bump.inputs["Height"].default_value = 1
            self.normal = bump


    def linkTangent(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Tangent"])


    def linkNormal(self, node):
        self.links.new(self.info.outputs["Tangent Normal"], node.inputs["Normal"])


    def addRamp(self, node, label, root, tip, endpos=1):
        ramp = self.addNode('ShaderNodeValToRGB', col=self.column-2)
        ramp.label = label
        self.links.new(self.info.outputs["Intercept"], ramp.inputs['Fac'])
        ramp.color_ramp.interpolation = 'LINEAR'
        colramp = ramp.color_ramp
        elt = colramp.elements[0]
        elt.position = 0
        if len(root) == 3:
            elt.color = list(root) + [1]
        else:
            elt.color = root
        elt = colramp.elements[1]
        elt.position = endpos
        if len(tip) == 3:
            elt.color = list(tip) + [0]
        else:
            elt.color = tip
        if node:
            node.inputs["Color"].default_value[0:3] == root
        return ramp


    def buildDiffuse(self, diffuse):
        # Color => diffuse
        color,colortex = self.getColorTex("getChannelDiffuse", "COLOR", self.color)
        if not isBlack(color):
            self.color = color
            self.dark = self.compProd(color, GREY)
        root,roottex = self.getColorTex(["Hair Root Color"], "COLOR", self.dark)
        tip,tiptex = self.getColorTex(["Hair Tip Color"], "COLOR", self.color)
        rough = self.getValue(["base_roughness"], 0.2)
        self.setRoughness(diffuse, rough)
        diffuse.inputs["Color"].default_value[0:3] = color
        ramp = self.addRamp(diffuse, "Color", root, tip)
        self.colorramp = self.linkRamp(ramp, [roottex, tiptex], diffuse, "Color")
        #self.linkNormal(diffuse)
        self.material.rna.diffuse_color[0:3] = color


    def linkRamp(self, ramp, texs, node, slot):
        src = ramp
        for tex in texs:
            if tex:
                mix = self.addNode("ShaderNodeMixRGB", col=self.column-1)
                mix.blend_type = 'MULTIPLY'
                mix.inputs[0].default_value = 1.0
                self.links.new(tex.outputs[0], mix.inputs[1])
                self.links.new(ramp.outputs[0], mix.inputs[2])
                src = mix
                break
        self.links.new(src.outputs[0], node.inputs[slot])
        return src


    def setRoughness(self, diffuse, rough):
        diffuse.inputs["Roughness"].default_value = rough


    def mixShaders(self, node1, node2, weight):
        mix = self.addNode('ShaderNodeMixShader')
        mix.inputs[0].default_value = weight
        self.links.new(node1.outputs[0], mix.inputs[1])
        self.links.new(node2.outputs[0], mix.inputs[2])
        return mix


    def addShaders(self, node1, node2):
        add = self.addNode('ShaderNodeAddShader')
        self.links.new(node1.outputs[0], add.inputs[0])
        self.links.new(node2.outputs[0], add.inputs[1])
        return add

#-------------------------------------------------------------
#   Hair tree BSDF
#-------------------------------------------------------------

class HairBSDFTree(HairTree):

    def buildLayer(self):
        self.initLayer()
        diffuse = self.addNode('ShaderNodeBsdfDiffuse')
        self.buildDiffuse(diffuse)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        self.column += 1
        print("BLL", diffuse, trans, refl)
        self.mixBasic(trans, refl, diffuse)
        self.buildAnisotropic()
        if LS.useRootTransparency:
            self.buildRootTransparency()
        self.buildCutout()
        self.buildOutput()


    def buildTransmission(self):
        # Transmission => Transmission
        root,roottex = self.getColorTex(["Root Transmission Color"], "COLOR", self.dark)
        tip,tiptex = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color)
        if isBlack(root) and isBlack(tip):
            color,tex = self.getColorTex(["Translucency Color"], "COLOR", self.color)
            weight = self.getValue(["Translucency Weight"], 0)
            #root = tip = color
            if isBlack(root):
                return None
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 0
        trans.inputs["RoughnessV"].default_value = 0
        ramp = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, [roottex, tiptex], trans, "Color")
        self.linkTangent(trans)
        self.active = trans
        return trans


    def buildHighlight(self):
        # Highlight => Reflection
        root,roottex = self.getColorTex(["Highlight Root Color"], "COLOR", WHITE)
        tip,tiptex = self.getColorTex(["Tip Highlight Color"], "COLOR", WHITE)
        rough = self.getValue(["highlight_roughness"], 0.5)
        if isBlack(root) and isBlack(tip):
            refl = None
        else:
            refl = self.addNode('ShaderNodeBsdfHair')
            refl.component = 'Reflection'
            refl.inputs['Offset'].default_value = 0
            refl.inputs["RoughnessU"].default_value = rough
            refl.inputs["RoughnessV"].default_value = rough
            ramp = self.addRamp(refl, "Highlight", root, tip)
            self.linkRamp(ramp, [roottex, tiptex], refl, "Color")
            self.linkTangent(refl)
            self.active = refl
        return refl


    def mixBasic(self, trans, refl, diffuse):
        # Mix
        if trans and refl:
            weight = self.getValue(["Highlight Weight"], 0.11)
            self.active = self.mixShaders(trans, refl, weight)
        if self.active:
            weight = self.getValue(["Glossy Layer Weight"], 0.75)
            self.active = self.mixShaders(diffuse, self.active, weight)
        else:
            self.active = diffuse


    def buildAnisotropic(self):
        # Anisotropic
        aniso = self.getValue(["Anisotropy"], 0)
        if aniso:
            if aniso > 0.2:
                aniso = 0.2
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.colorramp.outputs[0], node.inputs["Color"])
            node.inputs["Anisotropy"].default_value = aniso
            arots = self.getValue(["Anisotropy Rotations"], 0)
            node.inputs["Rotation"].default_value = arots
            self.linkTangent(node)
            self.linkNormal(node)
            self.column += 1
            self.active = self.addShaders(self.active, node)


    def buildRootTransparency(self):
        ramp = self.addRamp(None, "Root Transparency", (1,1,1,0), (1,1,1,1), endpos=0.15)
        maprange = self.addNode('ShaderNodeMapRange', col=self.column-1)
        maprange.inputs["From Min"].default_value = 0
        maprange.inputs["From Max"].default_value = 1
        maprange.inputs["To Min"].default_value = -0.1
        maprange.inputs["To Max"].default_value = 0.4
        self.links.new(self.info.outputs["Random"], maprange.inputs["Value"])
        add = self.addSockets(ramp.outputs["Alpha"], maprange.outputs["Result"])
        transp = self.addNode('ShaderNodeBsdfTransparent')
        transp.inputs["Color"].default_value[0:3] = WHITE
        self.column += 1
        mix = self.mixShaders(transp, self.active, 1)
        self.links.new(add.outputs[0], mix.inputs[0])
        self.active = mix


    def addSockets(self, socket1, socket2):
        node = self.addNode("ShaderNodeMath")
        math.operation = 'ADD'
        self.links.new(socket1, node.inputs[0])
        self.links.new(socket2, node.inputs[1])
        return node


    def buildCutout(self):
        # Cutout
        alpha = self.getValue(["Cutout Opacity"], 1)
        if alpha < 1:
            transp = self.addNode("ShaderNodeBsdfTransparent")
            transp.inputs["Color"].default_value[0:3] = WHITE
            self.column += 1
            self.active = self.mixShaders(transp, self.active, weight)
            self.material.alphaBlend(alpha, None)
            LS.usedFeatures["Transparent"] = True

#-------------------------------------------------------------
#   Hair tree Principled
#-------------------------------------------------------------

class HairPBRTree(HairTree):

    def buildLayer(self):
        self.initLayer()
        pbr = self.active = self.addNode("ShaderNodeBsdfHairPrincipled")
        self.buildDiffuse(pbr)
        self.buildOutput()

    def setRoughness(self, pbr, rough):
        pbr.inputs["Roughness"].default_value = rough
        pbr.inputs["Radial Roughness"].default_value = rough

# ---------------------------------------------------------------------
#   Pinning
# ---------------------------------------------------------------------

class Pinning(B.Pinning):
    def pinCoeffs(self):
        x0 = self.pinningX0
        x1 = self.pinningX1
        w0 = self.pinningW0
        w1 = self.pinningW1
        k = (w1-w0)/(x1-x0)
        return x0,x1,w0,w1,k

    def draw(self, context):
        self.layout.prop(self, "pinningX0")
        self.layout.prop(self, "pinningX1")
        self.layout.prop(self, "pinningW0")
        self.layout.prop(self, "pinningW1")


class DAZ_OT_MeshAddPinning(DazPropsOperator, IsMesh, Pinning):
    bl_idname = "daz.mesh_add_pinning"
    bl_label = "Add Pinning Group"
    bl_description = "Add HairPin group to mesh hair"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        x0,x1,w0,w1,k = self.pinCoeffs()

        if "HairPinning" in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups["HairPinning"]
            ob.vertex_groups.remove(vgrp)

        vgrp = ob.vertex_groups.new(name="HairPinning")
        uvs = ob.data.uv_layers.active.data
        m = 0
        for f in ob.data.polygons:
            for n,vn in enumerate(f.vertices):
                x = 1-uvs[m+n].uv[1]
                if x < x0:  w = w0
                elif x > x1: w = w1
                else: w = w0 + k*(x-x0)
                vgrp.add([vn], w, 'REPLACE')
            m += len(f.vertices)


class DAZ_OT_HairAddPinning(DazPropsOperator, IsMesh, Pinning):
    bl_idname = "daz.hair_add_pinning"
    bl_label = "Hair Add Pinning"
    bl_description = "Add HairPin group to hair strands"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        x0,x1,w0,w1,k = self.pinCoeffs()

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_MakeHair,
    DAZ_OT_UpdateHair,
    DAZ_OT_ColorHair,
    DAZ_OT_ConnectHair,
    DAZ_OT_MeshAddPinning,
    DAZ_OT_HairAddPinning,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
