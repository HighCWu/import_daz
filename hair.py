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
    def __init__(self, key, n, hum, mnum, btn):
        from .channels import Channels
        self.name = ("Hair_%s" % key)
        self.scale = hum.DazScale
        self.button = btn
        self.npoints = n
        self.mnum = mnum
        self.strands = []
        self.useEmitter = True
        self.vertexGroup = None
        self.material = btn.materials[mnum].name


    def setHairSettings(self, psys, ob):
        btn = self.button
        pset = psys.settings
        if hasattr(pset, "cycles_curve_settings"):
            ccset = pset.cycles_curve_settings
        elif hasattr(pset, "cycles"):
            ccset = pset.cycles
        else:
            ccset = pset

        if (self.material and
            self.material in ob.data.materials.keys()):
            pset.material_slot = self.material

        pset.rendered_child_count = btn.nRenderChildren
        pset.child_nbr = btn.nViewChildren
        if hasattr(pset, "display_step"):
            pset.display_step = btn.nViewStep
        else:
            pset.draw_step = btn.nViewStep
        pset.render_step = btn.nRenderStep
        pset.child_length = 1
        psys.child_seed = 0
        pset.child_radius = 0.1*btn.childRadius*self.scale

        if hasattr(ccset, "root_width"):
            ccset.root_width = 0.1*btn.rootRadius
            ccset.tip_width = 0.1*btn.tipRadius
        else:
            ccset.root_radius = 0.1*btn.rootRadius
            ccset.tip_radius = 0.1*btn.tipRadius
        if btn.strandShape == 'SHRINK':
            pset.shape = 0.99
        ccset.radius_scale = self.scale


    def addStrand(self, strand):
        self.strands.append(strand[0])


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
        if len(self.strands) == 0:
            raise DazError("No strands found")
        btn = self.button

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
        if btn.nViewChildren or btn.nRenderChildren:
            pset.child_type = 'SIMPLE'
        else:
            pset.child_type = 'NONE'

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
        pset.use_hair_bspline = True
        if hasattr(pset, "display_step"):
            pset.display_step = 3
        else:
            pset.draw_step = 3
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
        #print("Hair %s: %.3f %.3f %.3f %.3f %.3f" % (self.name, t2-t1, t3-t2, t4-t3, t5-t4, t6-t5))


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
    def unTesselateFaces(self, context, hair, btn):
        self.squashFaces(hair)
        self.removeDoubles(context, hair, btn)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair, btn)


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


    def removeDoubles(self, context, hair, btn):
        activateObject(context, hair)
        threshold = 0.001*btn.scale
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')


    def checkTesselation(self, hair):
        # Check that there are only pure lines
        from .tables import getVertEdges
        vertedges = getVertEdges(hair)
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


    def mergeRemainingFaces(self, hair, btn):
        for f in hair.data.polygons:
            fverts = [hair.data.vertices[vn] for vn in f.vertices]
            r0 = fverts[0].co
            for v in fverts:
                v.co = r0
                v.select = True
        threshold = 0.001*btn.scale
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.object.mode_set(mode='OBJECT')


    def findStrands(self, hair):
        pgs = hair.data.DazMatNums
        if len(pgs) >= len(hair.data.edges):
            edges = [list(e.vertices)+[pgs[e.index].a] for e in hair.data.edges]
        else:
            edges = [list(e.vertices)+[0] for e in hair.data.edges]
        edges.sort()
        plines = []
        v0 = -1
        for v1,v2,mnum in edges:
            if v1 == v0:
                pline.append(v2)
            else:
                pline = [v1,v2]
                plines.append((mnum,pline))
            v0 = v2
        strands = []
        verts = hair.data.vertices
        for mnum,pline in plines:
            strand = [verts[vn].co for vn in pline]
            strands.append((mnum,strand))
        return strands

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

def getHairAndHuman(context, strict):
    hair = context.object
    hum = None
    for ob in getSelectedMeshes(context):
        if ob != hair:
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
        multimat = True
        if self.strandType == 'SHEET':
            box.prop(self, "strandOrientation")
        elif self.strandType == 'TUBE':
            multimat = False
        box.prop(self, "keepMesh")
        box.prop(self, "removeOldHairs")
        box.separator()
        box.prop(self, "resizeHair")
        box.prop(self, "size")
        box.prop(self, "resizeInBlocks")
        box.prop(self, "sparsity")

        col = row.column()
        box = col.box()
        box.label(text="Material")
        if multimat:
            box.prop(self, "multiMaterials")
        box.prop(self, "keepMaterial")
        if self.keepMaterial:
            if not (multimat and self.multiMaterials):
                box.prop(self, "activeMaterial")
        else:
            box.prop(self, "hairMaterialMethod")
            if (multimat and self.multiMaterials):
                for item in self.colors:
                    row2 = box.row()
                    row2.label(text=item.name)
                    row2.prop(item, "color", text="")
            else:
                box.prop(self, "color")

        col = row.column()
        box = col.box()
        box.label(text="Settings")
        box.prop(self, "nViewChildren")
        box.prop(self, "nRenderChildren")
        box.prop(self, "nViewStep")
        box.prop(self, "nRenderStep")
        box.prop(self, "childRadius")
        if bpy.app.version >= (2,80,0):
            box.prop(self, "strandShape")
        box.prop(self, "rootRadius")
        box.prop(self, "tipRadius")


    def invoke(self, context, event):
        ob = context.object
        self.strandType = ob.data.DazHairType
        self.colors.clear()
        for mat in ob.data.materials:
            item = self.colors.add()
            item.name = mat.name
            item.color = colorToVector(mat.diffuse_color)
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        import time
        t1 = time.perf_counter()
        self.clocks = []
        hair,hum = getHairAndHuman(context, True)
        if hasObjectTransforms(hair):
            raise DazError("Apply object transformations to %s first" % hair.name)
        if hasObjectTransforms(hum):
            raise DazError("Apply object transformations to %s first" % hum.name)

        if self.strandType == 'SHEET':
            if not hair.data.uv_layers.active:
                raise DazError("Hair object has no active UV layer.\nConsider using Line or Tube strand types instead")
        elif self.strandType == 'LINE':
            if hair.data.polygons:
                raise DazError("Cannot use Line strand type for hair mesh with faces")
        elif self.strandType == 'TUBE':
            self.multiMaterials = False

        self.scale = hair.DazScale
        LS.hairMaterialMethod = self.hairMaterialMethod

        self.nonquads = []
        scn = context.scene
        # Build hair material while hair is still active
        self.buildHairMaterials(hum, hair, context)
        activateObject(context, hum)
        if self.removeOldHairs:
            self.clearHair(hum)

        activateObject(context, hair)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')

        t2 = time.perf_counter()
        self.clocks.append(("Initialize", t2-t1))
        hsystems = {}
        if self.strandType == 'SHEET':
            hairs = []
            bpy.ops.mesh.separate(type='LOOSE')
            bpy.ops.object.mode_set(mode='OBJECT')
            hname = hair.name
            if (len(hname) >= 4 and hname[-4] == "." and hname[-3:].isdigit()):
                hname = hname[:-4]
            haircount = 0
            hairs = [hair for hair in getSelectedMeshes(context)
                     if (hair.name.startswith(hname) and
                         hair != hum)]
            count = 0
            for hair in hairs:
                count += 1
                if count % self.sparsity != 0:
                    continue
                hsyss,hcount = self.makeHairSystems(context, hum, hair)
                haircount += hcount
                self.combineHairSystems(hsystems, hsyss)
                if count % 10 == 0:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            t5 = time.perf_counter()
            self.clocks.append(("Make hair systems", t5-t2))
        else:
            hairs = [hair]
            bpy.ops.object.mode_set(mode='OBJECT')
            tess = Tesselator()
            if self.strandType == 'LINE':
                pass
            elif self.strandType == 'TUBE':
                tess.unTesselateFaces(context, hair, self)
            strands = tess.findStrands(hair)
            haircount = self.addStrands(hum, hair, strands, hsystems, -1)
            t5 = time.perf_counter()
            self.clocks.append(("Make hair systems", t5-t2))
        haircount += 1
        print("\nTotal number of strands: %d" % haircount)
        if haircount == 0:
            raise DazError("Conversion failed.\nNo hair strands created")

        if self.resizeInBlocks:
            hsystems = self.blockResize(hsystems, hum)
        elif self.resizeHair:
            hsystems = self.hairResize(hsystems, hum)
        t6 = time.perf_counter()
        self.clocks.append(("Resize", t6-t5))
        self.makeHairs(context, hsystems, hum)
        t7 = time.perf_counter()
        self.clocks.append(("Make Hair", t7-t6))
        if self.keepMesh:
            if self.strandType == 'SHEET':
                activateObject(context, hair)
                selectObjects(context, hairs)
                bpy.ops.object.join()
                activateObject(context, hum)
                t8 = time.perf_counter()
                self.clocks.append(("Rejoined mesh hairs", t8-t7))
            else:
                t8 = t7
        else:
            deleteObjects(context, hairs)
            t8 = time.perf_counter()
            self.clocks.append(("Deleted mesh hairs", t8-t7))
        if self.nonquads:
            print("Ignored %d non-quad faces out of %d faces" % (len(self.nonquads), len(hair.data.polygons)))
        print("Hair converted in %.2f seconds" % (t8-t1))
        for hdr,t in self.clocks:
            print("  %s: %2f s" % (hdr, t))


    def makeHairs(self, context, hsystems, hum):
        print("Make particle hair")
        vgname = None
        if False:
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
        #print("Find neighbors")
        self.faceverts, self.vertfaces = getVertFaces(hair)
        self.nfaces = len(hair.data.polygons)
        if not self.nfaces:
            raise DazError("Hair has no faces")
        mneighbors = findNeighbors(range(self.nfaces), self.faceverts, self.vertfaces)
        self.centers, self.uvcenters = self.findCenters(hair)

        #print("Collect rects")
        mfaces = [(f.index,f.vertices) for f in hair.data.polygons]
        mrects,_,_ = self.collectRects(mfaces, mneighbors)
        return mrects


    def findTexRects(self, hair, mrects):
        from .tables import getVertFaces, findNeighbors, findTexVerts
        #print("Find texverts")
        self.texverts, self.texfaces = findTexVerts(hair, self.vertfaces)
        #print("Find tex neighbors", len(self.texverts), self.nfaces, len(self.texfaces))
        # Improve
        _,self.texvertfaces = getVertFaces(hair, self.texverts, None, self.texfaces)
        tneighbors = findNeighbors(range(self.nfaces), self.texfaces, self.texvertfaces)

        rects = []
        #print("Collect texrects")
        for mverts,mfaces in mrects:
            texfaces = [(fn,self.texfaces[fn]) for fn in mfaces]
            nn = [(fn,tneighbors[fn]) for fn in mfaces]
            rects2,clusters,fclusters = self.collectRects(texfaces, tneighbors)
            for rect in rects2:
                rects.append(rect)
        return rects


    def makeHairSystems(self, context, hum, hair):
        from .tables import getVertFaces, findNeighbors
        if len(hair.data.polygons) > 0:
            mnum = hair.data.polygons[0].material_index
        else:
            mnum = 0
        mrects = self.findMeshRects(hair)
        trects = self.findTexRects(hair, mrects)
        #print("Sort columns")
        haircount = -1
        setActiveObject(context, hair)
        hsystems = {}
        verts = range(len(hair.data.vertices))
        for _,tfaces in trects:
            if not self.quadsOnly(hair, tfaces):
                continue
            _,vertfaces = getVertFaces(None, verts, tfaces, self.faceverts)
            neighbors = findNeighbors(tfaces, self.faceverts, vertfaces)
            if neighbors is None:
                continue
            first, corner, boundary, bulk = self.findStartingPoint(hair, neighbors, self.uvcenters)
            if first is None:
                continue
            self.selectFaces(hair, tfaces)
            columns = self.sortColumns(first, corner, boundary, bulk, neighbors, self.uvcenters)
            if columns:
                coords = self.getColumnCoords(columns, self.centers)
                strands = [(mnum,strand) for strand in coords]
                haircount = self.addStrands(hum, hair, strands, hsystems, haircount)
        return hsystems, haircount


    def getStrand(self, strand):
        return strand[0], len(strand[1]), strand[1]


    def getKey(self, n, mnum):
        if self.multiMaterials:
            mat = self.materials[mnum]
            return ("%d_%s" % (n, mat.name)), mnum
        else:
            return str(n),0


    def addStrands(self, hum, hair, strands, hsystems, haircount):
        for strand in strands:
            mnum,n,strand = self.getStrand(strand)
            key,mnum = self.getKey(n, mnum)
            if key not in hsystems.keys():
                hsystems[key] = HairSystem(key, n, hum, mnum, self)
            hsystems[key].strands.append(strand)
        return len(strands)


    def combineHairSystems(self, hsystems, hsyss):
        for key,hsys in hsyss.items():
            if key in hsystems.keys():
                hsystems[key].strands += hsys.strands
            else:
                hsystems[key] = hsys


    def blockResize(self, hsystems, hum):
        print("Resize hair in blocks of ten")
        nsystems = {}
        for hsys in hsystems.values():
            n,nstrands = hsys.resizeBlock()
            key,mnum = self.getKey(n, hsys.mnum)
            if key not in nsystems.keys():
                nsystems[key] = HairSystem(key, n, hum, hsys.mnum, self)
            nsystems[key].strands += nstrands
        return nsystems


    def hairResize(self, hsystems, hum):
        print("Resize hair")
        nsystems = {}
        for hsys in hsystems.values():
            key,mnum = self.getKey(self.size, hsys.mnum)
            if key not in nsystems.keys():
                nsystems[key] = HairSystem(key, self.size, hum, hsys.mnum, self)
            nstrands = hsys.resize(self.size)
            nsystems[key].strands += nstrands
        return nsystems

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
        if self.strandOrientation == 'TOP':
            pass
        elif self.strandOrientation == 'BOTTOM':
            uvcenters = dict([(fn,Vector((u[0], -u[1]))) for fn,u in uvcenters.items()])
        elif self.strandOrientation == 'LEFT':
            uvcenters = dict([(fn,Vector((-u[1], -u[0]))) for fn,u in uvcenters.items()])
        elif self.strandOrientation == 'RIGHT':
            uvcenters = dict([(fn,Vector((u[1], u[0]))) for fn,u in uvcenters.items()])
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

    def clearHair(self, hum):
        nsys = len(hum.particle_systems)
        for n in range(nsys):
            bpy.ops.object.particle_system_remove()


    def buildHairMaterials(self, hum, hair, context):
        self.materials = []
        fade = (self.strandShape == 'ROOTS')
        if self.multiMaterials:
            if self.keepMaterial:
                mats = hair.data.materials
            else:
                mats = []
                for item in self.colors:
                    mname = "H" + item.name
                    mat = buildHairMaterial(mname, item.color, context, force=True)
                    if fade:
                        addFade(mat)
                    mats.append(mat)
            for mat in mats:
                hum.data.materials.append(mat)
                self.materials.append(mat)
        else:
            mname = self.activeMaterial
            if self.keepMaterial:
                mat = hair.data.materials[mname]
            else:
                mat = buildHairMaterial("Hair", self.color, context, force=True)
            if fade:
                addFade(mat)
            hum.data.materials.append(mat)
            self.materials = [mat]


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


class DAZ_OT_UpdateHair(DazPropsOperator, B.AffectMaterial, IsHair):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Change settings for particle hair"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "affectMaterial")


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
                key in ["count"] or
                (key in ["material", "material_slot"] and
                 not self.affectMaterial)):
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
        fade = False
        mats = {}
        for mat in hum.data.materials:
            mats[mat.name] = (mat, True)
        for psys in hum.particle_systems:
            pset = psys.settings
            mname = pset.material_slot
            if mname in mats.keys() and mats[mname][1]:
                mat = buildHairMaterial(mname, self.color, context, force=True)
                if fade:
                    addFade(mat)
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
    if LS.hairMaterialMethod == 'INTERNAL':
        return buildHairMaterialInternal(mname, list(color[0:3]), force)
    else:
        return buildHairMaterialCycles(mname, list(color[0:3]), context, force)

# ---------------------------------------------------------------------
#   Blender Internal
# ---------------------------------------------------------------------

def buildHairMaterialInternal(mname, rgb, force):
    mat = bpy.data.materials.new(mname)

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
    hmat = HairMaterial(mname, color)
    hmat.force = force
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
        self.tree = getHairTree(self, color)
        self.tree.build()
        self.rna.diffuse_color[0:3] = self.color


def getHairTree(dmat, color=BLACK):
    print("Creating %s hair material" % LS.hairMaterialMethod)
    if LS.hairMaterialMethod == 'HAIR_PRINCIPLED':
        return HairPBRTree(dmat, color)
    elif LS.hairMaterialMethod == 'PRINCIPLED':
        return HairEeveeTree(dmat, color)
    else:
        return HairBSDFTree(dmat, color)

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat, color):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = color
        self.root = Vector(color)
        self.tip = Vector(color)
        self.roottex = None
        self.tiptex = None


    def build(self):
        self.makeTree()
        self.buildLayer()
        self.prune()


    def initLayer(self):
        self.column = 4
        self.active = None
        self.buildBump()


    def addTexco(self, slot):
        CyclesTree.addTexco(self, slot)
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        #self.texco = self.info.outputs["Intercept"]


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


    def addRamp(self, node, label, root, tip, endpos=1, slot="Color"):
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
            node.inputs[slot].default_value[0:3] == root
        return ramp


    def readColor(self, factor):
        root, self.roottex = self.getColorTex(["Hair Root Color"], "COLOR", self.color, useFactor=False)
        tip, self.tiptex = self.getColorTex(["Hair Tip Color"], "COLOR", self.color, useFactor=False)
        self.material.rna.diffuse_color[0:3] = root
        self.root = factor * Vector(root)
        self.tip = factor * Vector(tip)


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


    def mixSockets(self, socket1, socket2, weight):
        mix = self.addNode('ShaderNodeMixShader')
        mix.inputs[0].default_value = weight
        self.links.new(socket1, mix.inputs[1])
        self.links.new(socket2, mix.inputs[2])
        return mix


    def mixShaders(self, node1, node2, weight):
        return self.mixSockets(node1.outputs[0], node2.outputs[0], weight)


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
        self.readColor(0.5)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        self.column += 1
        if trans and refl:
            #weight = self.getValue(["Highlight Weight"], 0.11)
            weight = self.getValue(["Glossy Layer Weight"], 0.5)
            self.active = self.mixShaders(trans, refl, weight)
        #self.buildAnisotropic()
        self.buildCutout()
        self.buildOutput()


    def buildTransmission(self):
        root, roottex = self.getColorTex(["Root Transmission Color"], "COLOR", self.color, useFactor=False)
        tip, tiptex = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color, useFactor=False)
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 1
        trans.inputs["RoughnessV"].default_value = 1
        ramp = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, [roottex, tiptex], trans, "Color")
        #self.linkTangent(trans)
        self.active = trans
        return trans


    def buildHighlight(self):
        refl = self.addNode('ShaderNodeBsdfHair')
        refl.component = 'Reflection'
        refl.inputs['Offset'].default_value = 0
        refl.inputs["RoughnessU"].default_value = 0.02
        refl.inputs["RoughnessV"].default_value = 1.0
        ramp = self.addRamp(refl, "Reflection", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], refl, "Color")
        self.active = refl
        return refl


    def buildAnisotropic(self):
        # Anisotropic
        aniso = self.getValue(["Anisotropy"], 0)
        if aniso:
            if aniso > 0.2:
                aniso = 0.2
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.rootramp.outputs[0], node.inputs["Color"])
            node.inputs["Anisotropy"].default_value = aniso
            arots = self.getValue(["Anisotropy Rotations"], 0)
            node.inputs["Rotation"].default_value = arots
            self.linkTangent(node)
            self.linkNormal(node)
            self.column += 1
            self.active = self.addShaders(self.active, node)


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
#   Hair tree for adding root transparency to existing material
#-------------------------------------------------------------

from .cgroup import MaterialGroup

class FadeGroup(MaterialGroup, HairTree):
    def __init__(self):
        MaterialGroup.__init__(self)
        self.insockets += ["Shader", "Intercept", "Random"]
        self.outsockets += ["Shader"]


    def create(self, node, name, parent):
        HairTree.__init__(self, parent.material, BLACK)
        MaterialGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketFloat", "Intercept")
        self.group.inputs.new("NodeSocketFloat", "Random")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        self.column = 3
        self.info = self.inputs
        ramp = self.addRamp(None, "Root Transparency", (1,1,1,0), (1,1,1,1), endpos=0.15)
        maprange = self.addNode('ShaderNodeMapRange', col=1)
        maprange.inputs["From Min"].default_value = 0
        maprange.inputs["From Max"].default_value = 1
        maprange.inputs["To Min"].default_value = -0.1
        maprange.inputs["To Max"].default_value = 0.4
        self.links.new(self.inputs.outputs["Random"], maprange.inputs["Value"])
        add = self.addSockets(ramp.outputs["Alpha"], maprange.outputs["Result"], col=2)
        transp = self.addNode('ShaderNodeBsdfTransparent', col=2)
        transp.inputs["Color"].default_value[0:3] = WHITE
        mix = self.mixSockets(transp.outputs[0], self.inputs.outputs["Shader"], 1)
        self.links.new(add.outputs[0], mix.inputs[0])
        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])


    def addSockets(self, socket1, socket2, col=None):
        node = self.addNode("ShaderNodeMath", col=col)
        math.operation = 'ADD'
        self.links.new(socket1, node.inputs[0])
        self.links.new(socket2, node.inputs[1])
        return node


def addFade(mat):
    tree = FadeHairTree(mat, mat.diffuse_color[0:3])
    tree.build(mat)


class FadeHairTree(HairTree):

    def build(self, mat):
        from .cycles import findNode, findLinksTo
        if mat.node_tree is None:
            print("Material %s has no nodes" % mat.name)
            return
        elif findNode(mat.node_tree, "TRANSPARENCY"):
            print("Hair material %s already has fading roots" % mat.name)
            return
        self.recoverTree(mat)
        links = findLinksTo(self.tree, "OUTPUT_MATERIAL")
        if links:
            link = links[0]
            fade = self.addGroup(FadeGroup, "DAZ Fade Roots", col=5)
            self.links.new(link.from_node.outputs[0], fade.inputs["Shader"])
            self.links.new(self.info.outputs["Intercept"], fade.inputs["Intercept"])
            self.links.new(self.info.outputs["Random"], fade.inputs["Random"])
            for link in links:
                self.links.new(fade.outputs["Shader"], link.to_socket)


    def recoverTree(self, mat):
        from .cycles import findNode, YSIZE, NCOLUMNS
        self.tree = mat.node_tree
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.info = findNode(self.tree, "HAIR_INFO")
        for col in range(NCOLUMNS):
            self.ycoords[col] -= YSIZE

#-------------------------------------------------------------
#   Hair tree Principled
#-------------------------------------------------------------

class HairPBRTree(HairTree):

    def buildLayer(self):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfHairPrincipled")
        ramp = self.addRamp(pbr, "Color", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Color")
        pbr.inputs["Roughness"].default_value = 0.2
        pbr.inputs["Radial Roughness"].default_value = 0.8
        pbr.inputs["IOR"].default_value = 1.1
        self.buildOutput()

#-------------------------------------------------------------
#   Hair tree Eevee
#-------------------------------------------------------------

class HairEeveeTree(HairTree):

    def buildLayer(self):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfPrincipled")
        self.ycoords[self.column] -= 500
        ramp = self.addRamp(pbr, "Color", self.root, self.tip, slot="Base Color")
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Base Color")
        pbr.inputs["Metallic"].default_value = 0.9
        pbr.inputs["Roughness"].default_value = 0.2
        self.buildOutput()

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
    B.ColorGroup,

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
