# Copyright (c) 2016, Thomas Larsson
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
import bpy
import numpy as np
from .error import *
from .utils import *
from .morphing import JCMSelector
from .driver import DriverUser


class FastMatcher:
    def checkTransforms(self, ob):
        if hasObjectTransforms(ob):
            raise DazError("Apply object transformations to %s first" % ob.name)


    def prepare(self, context, src, triangulate):
        mod = getModifier(src, 'ARMATURE')
        if mod:
            rig = mod.object
        else:
            rig = None
        if rig:
            self.checkTransforms(rig)
            rig.data.pose_position = 'REST'

        ob = self.trihuman = None
        if triangulate:
            ob = bpy.data.objects.new("_TRIHUMAN", src.data.copy())
            context.scene.collection.objects.link(ob)
            activateObject(context, ob)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
            bpy.ops.object.mode_set(mode='OBJECT')
            self.trihuman = ob
        return (ob, rig)


    def restore(self, context, data):
        ob,rig = data
        if rig:
            rig.data.pose_position = 'POSE'
        if ob:
            deleteObjects(context, [ob])


    def getTargets(self, src, context):
        self.checkTransforms(src)
        objects = []
        for ob in getSelectedMeshes(context):
            if ob != src:
                objects.append(ob)
                self.checkTransforms(ob)
        if not objects:
            raise DazError("No target meshes selected")
        return objects


    def findTriangles(self, ob):
        self.verts = np.array([list(v.co) for v in ob.data.vertices])
        tris = [f.vertices for f in ob.data.polygons]
        self.tris = np.array(tris)


    def findMatchNearest(self, src, trg):
        closest = [(v.co, src.closest_point_on_mesh(v.co)) for v in trg.data.vertices]
        # (result, location, normal, index)
        cverts = np.array([list(x) for x,data in closest if data[0]])
        offsets = np.array([list(x-data[1]) for x,data in closest if data[0]])
        fnums = [data[3] for x,data in closest if data[0]]
        tris = self.tris[fnums]
        tverts = self.verts[tris]
        A = np.transpose(tverts, axes=(0,2,1))
        B = cverts - offsets
        w = np.linalg.solve(A, B)
        self.match = (tris, w, offsets)

#----------------------------------------------------------
#   Threshold
#----------------------------------------------------------

class ThresholdFloat:
    threshold : FloatProperty(
        name = "Threshold",
        description = "Minimum vertex weight to keep",
        min = 0.0, max = 1.0,
        precision = 4,
        default = 1e-3)

#----------------------------------------------------------
#   Vertex group transfer
#----------------------------------------------------------

class DAZ_OT_TransferVertexGroups(DazPropsOperator, FastMatcher, IsMesh, ThresholdFloat):
    bl_idname = "daz.transfer_vertex_groups"
    bl_label = "Transfer Vertex Groups"
    bl_description = "Transfer vertex groups from active to selected"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "threshold")

    def run(self, context):
        src = context.object
        if not src.vertex_groups:
            raise DazError("Source mesh %s         \nhas no vertex groups" % src.name)
        import time
        t1 = time.perf_counter()
        targets = []
        for trg in self.getTargets(src, context):
            targets.append(trg.name)
            trg.vertex_groups.clear()
        print("Copy vertex groups from %s to %s" % (src.name, targets))
        bpy.ops.object.data_transfer(
            data_type = "VGROUP_WEIGHTS",
            vert_mapping = 'NEAREST',
            layers_select_src = 'ALL',
            layers_select_dst = 'NAME')
        t2 = time.perf_counter()
        print("Vertex groups transferred in %.1f seconds" % (t2-t1))


class DAZ_OT_CopyVertexGroupsByNumber(DazOperator, IsMesh):
    bl_idname = "daz.copy_vertex_groups_by_number"
    bl_label = "Copy Vertex Groups By Number"
    bl_description = "Copy vertex groups from active to selected meshes with the same number of vertices"
    bl_options = {'UNDO'}

    def run(self, context):
        from .finger import getFingerPrint
        from .modifier import copyVertexGroups
        src = context.object
        if not src.vertex_groups:
            raise DazError("Source mesh %s         \nhas no vertex groups" % src.name)
        srcfinger = getFingerPrint(src)
        for trg in getSelectedMeshes(context):
            if trg != src:
                trgfinger = getFingerPrint(trg)
                if trgfinger != srcfinger:
                    msg = ("Cannot copy vertex groups between meshes with different topology:\n" +
                           "Source: %s %s\n" % (srcfinger, src.name) +
                           "Target: %s %s" % (trgfinger, trg.name))
                    raise DazError(msg)
                copyVertexGroups(src, trg)

#----------------------------------------------------------
#   Morphs transfer
#----------------------------------------------------------

class DAZ_OT_TransferShapekeys(DazOperator, JCMSelector, FastMatcher, DriverUser):
    bl_idname = "daz.transfer_shapekeys"
    bl_label = "Transfer Shapekeys"
    bl_description = "Transfer shapekeys from active mesh to selected meshes"
    bl_options = {'UNDO'}

    usePropDriver = True
    defaultSelect = True

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)

    transferMethod : EnumProperty(
        items = [('NEAREST', "Nearest Face", "Transfer morphs from nearest source face.\nUse to transfer shapekeys to clothes"),
                 ('BODY', "Body", "Only transfer vertices as long as they match exactly.\nUse to transfer shapekeys from body to merged mesh"),
                 ('GEOGRAFT', "Geograft", "Transfer morphs to nearest target vertex.\nUse to transfer shapekeys from geograft to merged mesh"),
                 ('LEGACY', "Legacy", "Transfer using Blender's data transfer modifier.\nVery slow but works in general")],
        name = "Transfer Method",
        description = "Method used to transfer morphs",
        default = 'NEAREST')

    useDrivers : BoolProperty(
        name = "Transfer Drivers",
        description = "Transfer both shapekeys and drivers",
        default = True)

    useVendorMorphs : BoolProperty(
        name = "Use Vendor Morphs",
        description = "Use customized morphs provided by vendor,\notherwise always auto-transfer morphs",
        default = True)

    useOverwrite : BoolProperty(
        name = "Overwrite Existing Shapekeys",
        description = "Overwrite existing shapekeys or create new ones",
        default = True)

    useSelectedOnly : BoolProperty(
        name = "Selected Verts Only",
        description = "Only copy to selected vertices",
        default = False)

    ignoreRigidity : BoolProperty(
        name = "Ignore Rigidity Groups",
        description = "Ignore rigidity groups when auto-transfer morphs.\nMorphs may differ from DAZ Studio.",
        default = False)


    def draw(self, context):
        self.layout.prop(self, "transferMethod", expand=True)
        self.layout.prop(self, "useDrivers")
        self.layout.prop(self, "useVendorMorphs")
        self.layout.prop(self, "useOverwrite")
        self.layout.prop(self, "useSelectedOnly")
        self.layout.prop(self, "ignoreRigidity")
        JCMSelector.draw(self, context)


    def run(self, context):
        import time
        t1 = time.perf_counter()
        src = context.object
        if not src.data.shape_keys:
            raise DazError("Cannot transfer because object    \n%s has no shapekeys   " % (src.name))
        targets = self.getTargets(src, context)
        data = self.prepare(context, src, (self.transferMethod == 'NEAREST'))
        self.createTmp()
        try:
            failed = self.transferAllMorphs(context, src, targets)
        finally:
            self.deleteTmp()
            self.restore(context, data)
        t2 = time.perf_counter()
        print("Morphs transferred in %.1f seconds" % (t2-t1))
        if failed:
            msg = ("Morph transfer to the following meshes\nfailed due to insufficient memory:")
            for trg in failed:
                msg += ("\n    %s" % trg.name)
            msg += "\nTry the General transfer method instead.       "
            raise DazError(msg)


    def transferAllMorphs(self, context, src, targets):
        if self.transferMethod == 'NEAREST':
            self.findTriangles(self.trihuman)
        failed = []
        for trg in targets:
            if not self.transferMorphs(src, trg, context):
                failed.append(trg)
        return failed


    def transferMorphs(self, src, trg, context):
        from .driver import getShapekeyDriver
        from .asset import setDazPaths

        startProgress("Transfer morphs %s => %s" %(src.name, trg.name))
        scn = context.scene
        setDazPaths(scn)
        activateObject(context, src)
        if not self.findMatch(src, trg):
            return False
        trg.select_set(True)
        if not trg.data.shape_keys:
            basic = trg.shape_key_add(name="Basic")
        else:
            basic = None
        hskeys = src.data.shape_keys
        cskeys = trg.data.shape_keys
        if src.active_shape_key_index < 0:
            src.active_shape_key_index = 0
        trg.active_shape_key_index = 0

        snames = self.getSelectedProps()
        nskeys = len(snames)
        for idx,sname in enumerate(snames):
            showProgress(idx, nskeys)
            if sname not in hskeys.key_blocks.keys():
                print(" ? ", sname)
                continue
            hskey = hskeys.key_blocks[sname]

            if self.useDrivers:
                fcu = getShapekeyDriver(hskeys, sname)
            else:
                fcu = None

            if self.ignoreMorph(src, trg, hskey):
                print(" 0", sname)
                continue

            if sname in cskeys.key_blocks.keys():
                if self.useOverwrite:
                    cskey = cskeys.key_blocks[sname]
                    trg.shape_key_remove(cskey)

            cskey = None
            filepath = None
            if self.useVendorMorphs:
                filepath = getMorphPath(sname, trg, scn)
            if filepath is not None:
                cskey = self.loadMorph(filepath, trg, scn)
            if cskey:
                print(" *", sname)
            elif self.autoTransfer(src, trg, hskey):
                cskey = cskeys.key_blocks[sname]
                print(" +", sname)
                if cskey and not self.ignoreRigidity:
                    self.correctForRigidity(trg, cskey)

            if cskey:
                cskey.slider_min = hskey.slider_min
                cskey.slider_max = hskey.slider_max
                cskey.value = hskey.value
                if fcu is not None:
                    self.copyDriver(fcu, cskeys)
            else:
                print(" -", sname)

        if (basic and
            len(trg.data.shape_keys.key_blocks) == 1 and
            trg.data.shape_keys.key_blocks[0] == basic):
            print("No shapekeys transferred to %s" % trg.name)
            trg.shape_key_remove(basic)
        return True


    def loadMorph(self, filepath, ob, scn):
        from .load_json import loadJson
        from .files import parseAssetFile
        from .modifier import Morph
        LS.forMorphLoad(ob, scn)
        struct = loadJson(filepath)
        asset = parseAssetFile(struct)
        if (not isinstance(asset, Morph) or
            len(ob.data.vertices) != asset.vertex_count):
            return None
        asset.buildMorph(ob, useBuild=True)
        if asset.rna:
            skey,_,_ = asset.rna
            return skey
        else:
            return None


    def correctForRigidity(self, ob, skey):
        from mathutils import Matrix

        if "Rigidity" in ob.vertex_groups.keys():
            idx = ob.vertex_groups["Rigidity"].index
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == idx:
                        x = skey.data[v.index]
                        x.co = v.co + (1 - g.weight)*(x.co - v.co)

        for rgroup in ob.data.DazRigidityGroups:
            rotmode = rgroup.rotation_mode
            scalemodes = rgroup.scale_modes.split(" ")
            maskverts = [elt.a for elt in rgroup.mask_vertices]
            refverts = [elt.a for elt in rgroup.reference_vertices]
            nrefverts = len(refverts)
            if nrefverts == 0:
                continue

            if rotmode != "none":
                raise RuntimeError("Not yet implemented: Rigidity rotmode = %s" % rotmode)

            xcoords = [ob.data.vertices[vn].co for vn in refverts]
            ycoords = [skey.data[vn].co for vn in refverts]
            xsum = Vector((0,0,0))
            ysum = Vector((0,0,0))
            for co in xcoords:
                xsum += co
            for co in ycoords:
                ysum += co
            xcenter = xsum/nrefverts
            ycenter = ysum/nrefverts

            xdim = ydim = 0
            for n in range(3):
                xs = [abs(co[n]-xcenter[n]) for co in xcoords]
                ys = [abs(co[n]-ycenter[n]) for co in ycoords]
                xdim += sum(xs)
                ydim += sum(ys)

            scale = ydim/xdim
            smat = Matrix.Identity(3)
            for n,smode in enumerate(scalemodes):
                if smode == "primary":
                    smat[n][n] = scale

            for n,vn in enumerate(maskverts):
                skey.data[vn].co = smat @ (ob.data.vertices[vn].co - xcenter) + ycenter


    def ignoreMorph(self, src, trg, hskey):
        eps = 0.01 * src.DazScale   # 0.1 mm
        hverts = [v.index for v in src.data.vertices if (hskey.data[v.index].co - v.co).length > eps]
        for j in range(3):
            xclo = [v.co[j] for v in trg.data.vertices]
            # xkey = [hskey.data[vn].co[j] for vn in hverts]
            xkey = [src.data.vertices[vn].co[j] for vn in hverts]
            if xclo and xkey:
                minclo = min(xclo)
                maxclo = max(xclo)
                minkey = min(xkey)
                maxkey = max(xkey)
                if minclo > maxkey or maxclo < minkey:
                    return True
        return False


    def findMatch(self, src, trg):
        import time
        t1 = time.perf_counter()
        if self.transferMethod == 'LEGACY':
            return True
        elif self.transferMethod == 'BODY':
            self.findMatchExact(src, trg)
        elif self.transferMethod == 'NEAREST':
            self.findMatchNearest(self.trihuman, trg)
        elif self.transferMethod == 'GEOGRAFT':
            self.findMatchGeograft(src, trg)
        t2 = time.perf_counter()
        print("Matching table created in %.1f seconds" % (t2-t1))
        return True


    def autoTransfer(self, src, trg, hskey):
        if self.transferMethod == 'LEGACY':
            return self.autoTransferSlow(src, trg, hskey)
        elif self.transferMethod == 'BODY':
            return self.autoTransferExact(src, trg, hskey)
        elif self.transferMethod == 'NEAREST':
            return self.autoTransferFace(src, trg, hskey)
        elif self.transferMethod == 'GEOGRAFT':
            return self.autoTransferExact(src, trg, hskey)

    #----------------------------------------------------------
    #   Slow transfer
    #----------------------------------------------------------

    def autoTransferSlow(self, src, trg, hskey):
        hverts = src.data.vertices
        cverts = trg.data.vertices
        eps = 1e-4
        facs = {0:1.0, 1:1.0, 2:1.0}
        offsets = {0:0.0, 1:0.0, 2:0.0}
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            coord = [data.co[n] - hverts[j].co[n] for j,data in enumerate(hskey.data)]
            if min(coord) == max(coord):
                fac = 1.0
            else:
                fac = 1.0/(max(coord)-min(coord))
            facs[n] = fac
            offs = offsets[n] = min(coord)
            weights = [fac*(co-offs) for co in coord]

            vgrp = src.vertex_groups.new(name=vgname)
            for vn,w in enumerate(weights):
                vgrp.add([vn], w, 'REPLACE')
            bpy.ops.object.data_transfer(
                data_type = "VGROUP_WEIGHTS",
                vert_mapping = 'POLYINTERP_NEAREST',
                layers_select_src = 'ACTIVE',
                layers_select_dst = 'NAME')
            src.vertex_groups.remove(vgrp)

        coords = []
        isZero = True
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            vgrp = trg.vertex_groups[vgname]
            weights = [[g.weight for g in v.groups if g.group == vgrp.index][0] for v in trg.data.vertices]
            fac = facs[n]
            offs = offsets[n]
            coord = [cverts[j].co[n] + w/fac + offs for j,w in enumerate(weights)]
            coords.append(coord)
            wmax = max(weights)/fac + offs
            wmin = min(weights)/fac + offs
            if abs(wmax) > eps or abs(wmin) > eps:
                isZero = False
            trg.vertex_groups.remove(vgrp)

        if isZero:
            return False

        cskey = trg.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            verts = trg.data.vertices
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    if verts[j].select:
                        cskey.data[j].co[n] = x
        else:
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    cskey.data[j].co[n] = x

        return True

    #----------------------------------------------------------
    #   Exact
    #----------------------------------------------------------

    def findMatchExact(self, src, trg):
        hverts = src.data.vertices
        eps = 0.01*src.DazScale
        self.match = []
        nhverts = len(hverts)
        hvn = 0
        for cvn,cv in enumerate(trg.data.vertices):
            hv = hverts[hvn]
            while (hv.co - cv.co).length > eps:
                hvn += 1
                if hvn < nhverts:
                    hv = hverts[hvn]
                else:
                    print("Matched %d vertices" % cvn)
                    return
            self.match.append((cvn, hvn, cv.co - hv.co))


    def autoTransferExact(self, src, trg, hskey):
        cverts = trg.data.vertices
        hverts = src.data.vertices
        cskey = trg.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            for cvn,hvn,offset in self.match:
                if cverts[cvn].select:
                    cskey.data[cvn].co = hskey.data[hvn].co + offset
        else:
            for cvn,hvn,offset in self.match:
                cskey.data[cvn].co = hskey.data[hvn].co + offset
        return True

    #----------------------------------------------------------
    #   Nearest vertex and face matching
    #----------------------------------------------------------

    def nearestNeighbor(self, hvn, hverts, cverts):
        diff = cverts - hverts[hvn]
        dists = np.sum(np.abs(diff), axis=1)
        cvn = np.argmin(dists, axis=0)
        return cvn, hvn, Vector(cverts[cvn]-hverts[hvn])


    def findMatchGeograft(self, src, trg):
        hverts = np.array([list(v.co) for v in src.data.vertices])
        cverts = np.array([list(v.co) for v in trg.data.vertices])
        nhverts = len(hverts)
        self.match = [self.nearestNeighbor(hvn, hverts, cverts) for hvn in range(nhverts)]


    def autoTransferFace(self, src, trg, hskey):
        cskey = trg.shape_key_add(name=hskey.name)
        hcos = np.array([list(data.co) for data in hskey.data])
        tris, w, offsets = self.match
        tcos = hcos[tris]
        ccos = np.sum(tcos * w[:,:,None], axis=1) + offsets
        if self.useSelectedOnly:
            for cvn,co in enumerate(ccos):
                if cverts[cvn].select:
                    cskey.data[cvn].co = co
        else:
            for cvn,co in enumerate(ccos):
                cskey.data[cvn].co = co
        return True

#----------------------------------------------------------
#   Utilities
#----------------------------------------------------------

def getMorphPath(sname, ob, scn):
    from .fileutils import getFolders
    file = sname + ".dsf"
    folders = getFolders(ob, scn, ["Morphs/"])
    for folder in folders:
        path = findFileRecursive(folder, file)
        if path:
            return path
    return None


def findFileRecursive(folder, tfile):
    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        if file == tfile:
            return path
        elif os.path.isdir(path):
            tpath = findFileRecursive(path, tfile)
            if tpath:
                return tpath
    return None


#----------------------------------------------------------
#   Apply all shapekeys
#----------------------------------------------------------

class DAZ_OT_ApplyAllShapekeys(DazOperator, IsMesh):
    bl_idname = "daz.apply_all_shapekeys"
    bl_label = "Apply All Shapekeys"
    bl_description = "Apply all shapekeys to selected meshes"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            skeys = ob.data.shape_keys
            if skeys:
                nverts = len(ob.data.vertices)
                verts = np.array([v.co for v in ob.data.vertices])
                coords = verts.copy()
                for skey in skeys.key_blocks:
                    scoords = np.array([skey.data[n].co for n in range(nverts)])
                    coords += skey.value*(scoords - verts)
                blocks = list(skeys.key_blocks)
                blocks.reverse()
                for skey in blocks:
                    ob.shape_key_remove(skey)
                for v,co in zip(ob.data.vertices, coords):
                    v.co = co

#----------------------------------------------------------
#   Mix Shapekeys
#----------------------------------------------------------

class DAZ_OT_MixShapekeys(DazOperator):
    bl_idname = "daz.mix_shapekeys"
    bl_label = "Mix Shapekeys"
    bl_description = "Mix shapekeys"
    bl_options = {'UNDO'}

    shape1 : EnumProperty(
        items = G.shapekeyItems1,
        name = "Shapekey 1",
        description = "First shapekey")

    shape2 : EnumProperty(
        items = G.shapekeyItems2,
        name = "Shapekey 2",
        description = "Second shapekey")

    factor1 : FloatProperty(
        name = "Factor 1",
        description = "First factor",
        default = 1.0)

    factor2 : FloatProperty(
        name = "Factor 2",
        description = "Second factor",
        default = 1.0)

    allSimilar : BoolProperty(
        name = "Mix All Similar",
        description = "Mix all shapekeys with similar names",
        default = False)

    overwrite : BoolProperty(
        name = "Overwrite First",
        description = "Overwrite the first shapekey",
        default = True)

    delete : BoolProperty(
        name = "Delete Merged",
        description = "Delete unused shapekeys after merge",
        default = True)

    newName : StringProperty(
        name = "New shapekey",
        description = "Name of new shapekey",
        default = "Shapekey")

    filter1 : StringProperty(
        name = "Filter 1",
        description = "Show only items containing this string",
        default = ""
        )

    filter2 : StringProperty(
        name = "Filter 2",
        description = "Show only items containing this string",
        default = ""
        )

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "allSimilar")
        row.prop(self, "overwrite")
        row.prop(self, "delete")
        row = self.layout.split(factor=0.2)
        row.label(text="")
        row.label(text="First")
        row.label(text="Second")
        if self.allSimilar:
            row = self.layout.split(factor=0.2)
            row.label(text="Factor")
            row.prop(self, "factor1", text="")
            row.prop(self, "factor2", text="")
            return
        row = self.layout.split(factor=0.2)
        row.label(text="")
        row.prop(self, "filter1", icon='VIEWZOOM', text="")
        row.prop(self, "filter2", icon='VIEWZOOM', text="")
        row = self.layout.split(factor=0.2)
        row.label(text="Factor")
        row.prop(self, "factor1", text="")
        row.prop(self, "factor2", text="")
        row = self.layout.split(factor=0.2)
        row.label(text="Shapekey")
        row.prop(self, "shape1", text="")
        row.prop(self, "shape2", text="")
        if not self.overwrite:
            self.layout.prop(self, "newName")


    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self, width=500)
        return {'RUNNING_MODAL'}


    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if self.allSimilar:
            shapes = self.findSimilar(ob, skeys)
            for shape1,shape2 in shapes:
                print("Mix", shape1, shape2)
                self.mixShapekeys(ob, skeys, shape1, shape2)
        else:
            self.mixShapekeys(ob, skeys, self.shape1, self.shape2)


    def findSimilar(self, ob, skeys):
        slist = list(skeys.key_blocks.keys())
        slist.sort()
        shapes = []
        for n in range(len(slist)-1):
            shape1 = slist[n]
            shape2 = slist[n+1]
            words = shape2.rsplit(".",1)
            if (len(words) == 2 and
                words[0] == shape1):
                shapes.append((shape1,shape2))
        return shapes


    def mixShapekeys(self, ob, skeys, shape1, shape2):
        if shape1 == shape2:
            raise DazError("Cannot merge shapekey to itself")
        skey1 = skeys.key_blocks[shape1]
        if shape2 == "-":
            skey2 = None
            factor = self.factor1 - 1
            coords = [(self.factor1 * skey1.data[n].co - factor * v.co)
                       for n,v in enumerate(ob.data.vertices)]
        else:
            skey2 = skeys.key_blocks[shape2]
            factor = self.factor1 + self.factor2 - 1
            coords = [(self.factor1 * skey1.data[n].co +
                       self.factor2 * skey2.data[n].co - factor * v.co)
                       for n,v in enumerate(ob.data.vertices)]
        if self.overwrite:
            skey = skey1
        else:
            skey = ob.shape_key_add(name=self.newName)
        for n,co in enumerate(coords):
            skey.data[n].co = co
        if self.delete:
            if skey2:
                self.deleteShape(ob, skeys, shape2)
            if not self.overwrite:
                self.deleteShape(ob, skeys, shape1)


    def deleteShape(self, ob, skeys, sname):
        if skeys.animation_data:
            path = 'key_blocks["%s"].value' % sname
            skeys.driver_remove(path)
        updateDrivers(skeys)
        idx = skeys.key_blocks.keys().index(sname)
        ob.active_shape_key_index = idx
        bpy.ops.object.shape_key_remove()

#-------------------------------------------------------------
#   Prune vertex groups
#-------------------------------------------------------------

def findVertexGroups(ob):
    nverts = len(ob.data.vertices)
    nvgrps = len(ob.vertex_groups)
    vnames = [vgrp.name for vgrp in ob.vertex_groups]
    weights = dict([(gn, np.zeros(nverts, dtype=np.float)) for gn in range(nvgrps)])
    for v in ob.data.vertices:
        for g in v.groups:
            weights[g.group][v.index] = g.weight
    return vnames,weights


class DAZ_OT_PruneVertexGroups(DazPropsOperator, ThresholdFloat, IsMesh):
    bl_idname = "daz.prune_vertex_groups"
    bl_label = "Prune Vertex Groups"
    bl_description = "Remove vertices and groups with weights below threshold"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "threshold")

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.pruneVertexGroups(ob)

    def pruneVertexGroups(self, ob):
        vnames,weights = findVertexGroups(ob)
        for vgrp in list(ob.vertex_groups):
            ob.vertex_groups.remove(vgrp)
        for gn,vname in enumerate(vnames):
            cweights = weights[gn]
            cweights[cweights > 1] = 1
            cweights[cweights < self.threshold] = 0
            nonzero = np.nonzero(cweights)[0].astype(int)
            if len(nonzero) > 0:
                vgrp = ob.vertex_groups.new(name=vname)
                for vn in nonzero:
                    vgrp.add([int(vn)], cweights[vn], 'REPLACE')
                print("  * %s" % vname)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TransferVertexGroups,
    DAZ_OT_CopyVertexGroupsByNumber,
    DAZ_OT_TransferShapekeys,
    DAZ_OT_PruneVertexGroups,
    DAZ_OT_ApplyAllShapekeys,
    DAZ_OT_MixShapekeys,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
