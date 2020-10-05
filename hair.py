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
        val,rdtex = self.getTexDensity(mod, channels, 100, "rendered_child_count", pset, ob, "use_map_density", "density_factor")

        channels = ["PreSim Hairs Density", "PreRender Hairs Per Guide"]
        self.getTexDensity(mod, channels, 10, "child_nbr", pset, ob, "use_map_density", "density_factor", cond=(not rdtex))

        if self.material:
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
        #print("Build hair", self.name)

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
        pset.child_type = 'SIMPLE'

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
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
#   Make Strand Hair
#-------------------------------------------------------------

class DAZ_OT_MakeStrandHair(DazOperator):
    bl_idname = "daz.make_strand_hair"
    bl_label = "Make Strand Hair"
    bl_description = "Make particle hair from stored strand-based hair"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.DazStrands)

    def run(self, context):
        hsystems = {}
        vgrp = None
        ob = context.object
        for pgs in ob.DazStrands:
            matname = pgs.name
            strand = [pg.a for pg in pgs.strand]
            n = len(strand)
            hname = ("%s-%02d" % (matname, n))
            if hname not in hsystems.keys():
                hsys = hsystems[hname] = HairSystem(hname, n, object=ob)
                hsys.material = matname
                if GS.useSkullGroup:
                    if vgrp is None:
                        vgrp = createSkullGroup(ob, 'TOP')
                    hsys.vertexGroup = vgrp.name
            hsystems[hname].strands.append(strand)

        activateObject(context, ob)
        for hsys in hsystems.values():
            hsys.build(context, ob)
        ob.DazStrands.clear()

#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

def getHairAndHuman(context, strict):
    hum = context.object
    hair = None
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'MESH' and ob != hum:
            hair = ob
            break
    if strict and hair is None:
        raise DazError("Select hair and human")
    return hair,hum


class DAZ_OT_MakeHair(DazPropsOperator, IsMesh, B.Hair):
    bl_idname = "daz.make_hair"
    bl_label = "Make Hair"
    bl_description = "Make particle hair from mesh hair"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "color")
        self.layout.prop(self, "useVertexGroup")
        self.layout.separator()
        self.layout.prop(self, "resizeHair")
        self.layout.prop(self, "size")
        self.layout.prop(self, "resizeInBlocks")
        self.layout.prop(self, "sparsity")


    def run(self, context):
        from .tables import getVertFaces, findNeighbors, findTexVerts
        self.nonquads = []
        scn = context.scene

        hair,hum = getHairAndHuman(context, True)
        setActiveObject(context, hum)
        self.clearHair(hum, hair, self.color, context)
        hsystems = {}

        setActiveObject(context, hair)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        print("Find neighbors")
        faceverts,vertfaces = getVertFaces(hair)
        nfaces = len(hair.data.polygons)
        neighbors = findNeighbors(range(nfaces), faceverts, vertfaces)
        centers,uvcenters = self.findCenters(hair)

        print("Collect rects")
        ordfaces = [(f.index,f.vertices) for f in hair.data.polygons]
        rects1,_,_ = self.collectRects(ordfaces, neighbors)

        print("Find texverts")
        texverts,texfaces = findTexVerts(hair, vertfaces)
        print("Find tex neighbors", len(texverts), nfaces, len(texfaces))
        # Improve
        _,texvertfaces = getVertFaces(hair, texverts, None, texfaces)
        neighbors = findNeighbors(range(nfaces), texfaces, texvertfaces)

        rects = []
        print("Collect texrects")
        for verts1,faces1 in rects1:
            texfaces1 = [(fn,texfaces[fn]) for fn in faces1]
            nn = [(fn,neighbors[fn]) for fn in faces1]
            rects2,clusters,fclusters = self.collectRects(texfaces1, neighbors, True)
            for rect in rects2:
                rects.append(rect)

        print("Sort columns")
        haircount = -1
        setActiveObject(context, hair)
        verts = range(len(hair.data.vertices))
        count = 0
        for _,faces in rects:
            if count % 10 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
            count += 1
            if not self.quadsOnly(hair, faces):
                continue
            _,vertfaces = getVertFaces(None, verts, faces, faceverts)
            neighbors = findNeighbors(faces, faceverts, vertfaces)
            if neighbors is None:
                continue
            first, corner, boundary, bulk = self.findStartingPoint(hair, neighbors, uvcenters)
            if first is None:
                continue
            self.selectFaces(hair, faces)
            columns = self.sortColumns(first, corner, boundary, bulk, neighbors, uvcenters)
            if columns:
                strands = self.getColumnCoords(columns, centers)
                for strand in strands:
                    haircount += 1
                    if haircount % self.sparsity != 0:
                        continue
                    n = len(strand)
                    if n not in hsystems.keys():
                        hsystems[n] = HairSystem(None, n, object=hum)
                    hsystems[n].strands.append(strand)

        print("Total number of strands: %d" % (haircount+1))

        if self.resizeInBlocks:
            print("Resize hair in blocks of ten")
            nsystems = {}
            for hsys in hsystems.values():
                n,nstrands = hsys.resizeBlock()
                if n not in nsystems.keys():
                    nsystems[n] = HairSystem(None, n, object=hum)
                nsystems[n].strands += nstrands
            hsystems = nsystems

        elif self.resizeHair:
            print("Resize hair")
            nsystem = HairSystem(None, self.size, object=hum)
            for hsys in hsystems.values():
                nstrands = hsys.resize(self.size)
                nsystem.strands += nstrands
            hsystems = {self.size: nsystem}

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

        if self.nonquads:
            print("Ignored %d non-quad faces out of %d faces" % (len(self.nonquads), len(hair.data.polygons)))

    #-------------------------------------------------------------
    #   Collect rectangles
    #-------------------------------------------------------------

    def collectRects(self, faceverts, neighbors, test=False):
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

    def clearHair(self, hum, hair, color, context):
        nsys = len(hum.particle_systems)
        for n in range(nsys):
            bpy.ops.object.particle_system_remove()
        mat = buildHairMaterial("Hair", color, context)
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
                mat = buildHairMaterial(mname, self.color, context)
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

def buildHairMaterial(mname, color, context):
    scn = context.scene
    if scn.render.engine in ['BLENDER_RENDER', 'BLENDER_GAME']:
        return buildHairMaterialInternal(mname, list(color[0:3]))
    else:
        return buildHairMaterialCycles(mname, list(color[0:3]), context)

# ---------------------------------------------------------------------
#   Blender Internal
# ---------------------------------------------------------------------

def buildHairMaterialInternal(mname, rgb):
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

def buildHairMaterialCycles(mname, color, context):
    hmat = HairMaterial("Hair")
    hmat.name = mname
    print("Creating CYCLES HAIR material")
    hmat.build(context, color)
    return hmat.rna


class HairMaterial(CyclesMaterial):
    def build(self, context, color):
        from .material import Material
        Material.build(self, context)
        self.tree = HairBSDFTree(self)
        self.tree.color = color
        self.tree.dark = Vector(color)*GREY
        self.tree.build(context)

#-------------------------------------------------------------
#   Hair tree base
#-------------------------------------------------------------

class HairTree(CyclesTree):
    def __init__(self, hmat):
        CyclesTree.__init__(self, hmat)
        self.type = 'HAIR'
        self.color = GREY
        self.dark = BLACK


    def build(self, context):
        scn = context.scene
        self.makeTree()
        self.buildLayer(context)
        #self.prune()


    def initLayer(self, context):
        scn = context.scene
        self.column = 4
        self.active = None
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        self.buildBump()


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


    def addRamp(self, node, label, root, tip):
        ramp = self.addNode('ShaderNodeValToRGB', col=self.column-2)
        ramp.label = label
        self.links.new(self.info.outputs['Intercept'], ramp.inputs['Fac'])
        ramp.color_ramp.interpolation = 'LINEAR'
        colramp = ramp.color_ramp
        elt = colramp.elements[0]
        elt.position = 0
        elt.color = list(root) + [1]
        elt = colramp.elements[1]
        elt.position = 1
        elt.color = list(tip) + [0]
        node.inputs["Color"].default_value[0:3] == root
        return ramp


    def buildDiffuse(self, diffuse):
        # Color => diffuse
        color,colortex = self.getColorTex("getChannelDiffuse", "COLOR", self.color)
        root,roottex = self.getColorTex(["Hair Root Color"], "COLOR", self.dark)
        tip,tiptex = self.getColorTex(["Hair Tip Color"], "COLOR", self.color)
        rough = self.getValue(["base_roughness"], 0.2)
        self.setRoughness(diffuse, rough)
        diffuse.inputs["Color"].default_value[0:3] = color
        ramp = self.addRamp(diffuse, "Color", root, tip)
        self.colorramp = self.linkRamp(ramp, [roottex, tiptex], diffuse, "Color")
        #self.linkNormal(diffuse)
        self.material.rna.diffuse_color[0:3] = color
        self.column += 1


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

    def buildLayer(self, context):
        self.initLayer(context)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        diffuse = self.addNode('ShaderNodeBsdfDiffuse')
        self.buildDiffuse(diffuse)
        self.mixBasic(trans, refl, diffuse)
        self.buildAnisotropic()
        self.buildCutout()
        self.buildOutput()


    def buildTransmission(self):
        # Transmission => Transmission
        root,roottex = self.getColorTex(["Root Transmission Color"], "COLOR", self.dark)
        tip,tiptex = self.getColorTex(["Tip Transmission Color"], "COLOR", self.color)
        if isBlack(root) and isBlack(tip):
            trans = None
        else:
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
        aniso = self.getValue(["Anisotropy"], 1)
        if aniso:
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.colorramp.outputs[0], node.inputs["Color"])
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
#   Hair tree Principled
#-------------------------------------------------------------

class HairPBRTree(HairTree):

    def buildLayer(self, context):
        self.initLayer(context)
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
    DAZ_OT_MakeStrandHair,
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
