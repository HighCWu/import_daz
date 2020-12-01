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
from .error import *
from .utils import *
from .morphing import Selector


class MorphTransferer(Selector, B.TransferOptions):
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


    def draw(self, context):
        self.layout.prop(self, "useDriver")
        self.layout.prop(self, "useOverwrite")
        self.layout.prop(self, "useSelectedOnly")
        self.layout.prop(self, "ignoreRigidity")
        Selector.draw(self, context)


    def run(self, context):
        import time
        t1 = time.perf_counter()
        hum = context.object
        if not hum.data.shape_keys:
            raise DazError("Cannot transfer because object    \n%s has no shapekeys   " % (hum.name))
        for clo in self.getClothes(hum, context):
            self.transferMorphs(hum, clo, context)
        t2 = time.perf_counter()
        print("Morphs transferred in %.1f seconds" % (t2-t1))


    def transferMorphs(self, hum, clo, context):
        from .driver import getShapekeyDriver, copyDriver
        from .asset import setDazPaths

        if (hum.location != clo.location or
            hum.rotation_euler != clo.rotation_euler or
            hum.scale != clo.scale):
            msg = "Cannot transfer morphs between meshes       \nwith different object transformations."
            raise DazError(msg)
        startProgress("Transfer morphs %s => %s" %(hum.name, clo.name))
        scn = context.scene
        setDazPaths(scn)
        setActiveObject(context, clo)
        if not clo.data.shape_keys:
            basic = clo.shape_key_add(name="Basic")
        else:
            basic = None
        hskeys = hum.data.shape_keys
        if hum.active_shape_key_index < 0:
            hum.active_shape_key_index = 0
        clo.active_shape_key_index = 0

        snames = self.getSelectedProps(scn)
        nskeys = len(snames)
        for idx,sname in enumerate(snames):
            showProgress(idx, nskeys)
            hskey = hskeys.key_blocks[sname]

            if self.useDriver:
                fcu = getShapekeyDriver(hskeys, sname)
            else:
                fcu = None

            if self.ignoreMorph(hum, clo, hskey):
                print(" 0", sname)
                continue

            if sname in clo.data.shape_keys.key_blocks.keys():
                if self.useOverwrite:
                    cskey = clo.data.shape_keys.key_blocks[sname]
                    clo.shape_key_remove(cskey)

            cskey = None
            path = self.getMorphPath(sname, clo, scn)
            if path is not None:
                from .morphing import LoadShapekey
                loader = LoadShapekey(mesh=clo)
                LS.forMorphLoad(clo, scn)
                loader.errors = {}
                loader.getSingleMorph(sname, path, scn)
                if sname in clo.data.shape_keys.key_blocks.keys():
                    cskey = clo.data.shape_keys.key_blocks[sname]

            if cskey:
                print(" *", sname)
            elif self.autoTransfer(hum, clo, hskey):
                cskey = clo.data.shape_keys.key_blocks[sname]
                print(" +", sname)
                if cskey and not self.ignoreRigidity:
                    correctForRigidity(clo, cskey)

            if cskey:
                cskey.slider_min = hskey.slider_min
                cskey.slider_max = hskey.slider_max
                cskey.value = hskey.value
                if fcu is not None:
                    copyDriver(fcu, cskey)
            else:
                print(" -", sname)

        if (basic and
            len(clo.data.shape_keys.key_blocks) == 1 and
            clo.data.shape_keys.key_blocks[0] == basic):
            print("No shapekeys transferred to %s" % clo.name)
            clo.shape_key_remove(basic)


    def autoTransfer(self, hum, clo, hskey):
        hverts = hum.data.vertices
        cverts = clo.data.vertices
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

            vgrp = hum.vertex_groups.new(name=vgname)
            for vn,w in enumerate(weights):
                vgrp.add([vn], w, 'REPLACE')

            mod = clo.modifiers.new(vgname, 'DATA_TRANSFER')
            for i in range(len(clo.modifiers)-1):
                bpy.ops.object.modifier_move_up(modifier=mod.name)
            mod.object = hum
            mod.use_vert_data = True
            #'TOPOLOGY', 'NEAREST', 'EDGE_NEAREST', 'EDGEINTERP_NEAREST',
            # 'POLY_NEAREST', 'POLYINTERP_NEAREST', 'POLYINTERP_VNORPROJ'
            mod.vert_mapping = 'POLYINTERP_NEAREST'
            mod.data_types_verts = {'VGROUP_WEIGHTS'}
            mod.layers_vgroup_select_src = vgname
            mod.mix_mode = 'REPLACE'
            bpy.ops.object.datalayout_transfer(modifier=mod.name)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            hum.vertex_groups.remove(vgrp)

        coords = []
        isZero = True
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            vgrp = clo.vertex_groups[vgname]
            weights = [[g.weight for g in v.groups if g.group == vgrp.index][0] for v in clo.data.vertices]
            fac = facs[n]
            offs = offsets[n]
            coord = [cverts[j].co[n] + w/fac + offs for j,w in enumerate(weights)]
            coords.append(coord)
            wmax = max(weights)/fac + offs
            wmin = min(weights)/fac + offs
            if abs(wmax) > eps or abs(wmin) > eps:
                isZero = False
            clo.vertex_groups.remove(vgrp)

        if isZero:
            return False

        cskey = clo.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            verts = clo.data.vertices
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    if verts[j].select:
                        cskey.data[j].co[n] = x
        else:
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    cskey.data[j].co[n] = x

        return True


    def ignoreMorph(self, hum, clo, hskey):
        eps = 0.01 * hum.DazScale   # 0.1 mm
        hverts = [v.index for v in hum.data.vertices if (hskey.data[v.index].co - v.co).length > eps]
        for j in range(3):
            xclo = [v.co[j] for v in clo.data.vertices]
            # xkey = [hskey.data[vn].co[j] for vn in hverts]
            xkey = [hum.data.vertices[vn].co[j] for vn in hverts]
            if xclo and xkey:
                minclo = min(xclo)
                maxclo = max(xclo)
                minkey = min(xkey)
                maxkey = max(xkey)
                if minclo > maxkey or maxclo < minkey:
                    return True
        return False


    def getClothes(self, hum, context):
        objects = []
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob != hum and ob.type == 'MESH':
                objects.append(ob)
        return objects


    def getMorphPath(self, sname, ob, scn):
        from .fileutils import getFolder
        file = sname + ".dsf"
        folder = getFolder(ob, scn, ["Morphs/"])
        if folder:
            return findFileRecursive(folder, file)
        else:
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


def correctForRigidity(ob, skey):
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
            skey.data[vn].co = Mult2(smat, (ob.data.vertices[vn].co - xcenter)) + ycenter


def findVertsInGroup(ob, vgrp):
    idx = vgrp.index
    verts = []
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group == idx:
                verts.append(v.index)
    return verts


class DAZ_OT_TransferOtherMorphs(DazOperator, MorphTransferer):
    bl_idname = "daz.transfer_other_morphs"
    bl_label = "Transfer Other Morphs"
    bl_description = "Transfer all shapekeys except JCMs (bone driven) with drivers from active to selected"
    bl_options = {'UNDO'}

    useBoneDriver = False
    usePropDriver = True
    useCorrectives = False
    defaultSelect = True

    def getKeys(self, rig, ob):
        from .morphing import getMorphList, theJCMMorphSets
        jcms = [item.name for item in getMorphList(ob, theJCMMorphSets)]
        keys = []
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if skey.name not in jcms:
                keys.append((skey.name, skey.name, "All"))
        return keys


class DAZ_OT_TransferCorrectives(DazOperator, MorphTransferer):
    bl_idname = "daz.transfer_jcms"
    bl_label = "Transfer JCMs"
    bl_description = "Transfer JCMs (joint corrective shapekeys) and drivers from active to selected"
    bl_options = {'UNDO'}

    useBoneDriver = True
    usePropDriver = False
    useCorrectives = True
    defaultSelect = True

    def getKeys(self, rig, ob):
        from .morphing import getMorphList, theJCMMorphSets
        jcms = [item.name for item in getMorphList(ob, theJCMMorphSets)]
        keys = []
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if skey.name in jcms:
                keys.append((skey.name, skey.name, "All"))
        return keys

#----------------------------------------------------------
#   Mix Shapekeys
#----------------------------------------------------------

class DAZ_OT_MixShapekeys(DazOperator, B.MixShapekeysOptions):
    bl_idname = "daz.mix_shapekeys"
    bl_label = "Mix Shapekeys"
    bl_description = "Mix shapekeys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "allSimilar")
        row.prop(self, "overwrite")
        row.prop(self, "delete")
        row = splitLayout(self.layout, 0.2)
        row.label(text="")
        row.label(text="First")
        row.label(text="Second")
        if self.allSimilar:
            row = splitLayout(self.layout, 0.2)
            row.label(text="Factor")
            row.prop(self, "factor1", text="")
            row.prop(self, "factor2", text="")
            return
        row = splitLayout(self.layout, 0.2)
        row.label(text="")
        row.prop(self, "filter1", icon='VIEWZOOM', text="")
        row.prop(self, "filter2", icon='VIEWZOOM', text="")
        row = splitLayout(self.layout, 0.2)
        row.label(text="Factor")
        row.prop(self, "factor1", text="")
        row.prop(self, "factor2", text="")
        row = splitLayout(self.layout, 0.2)
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

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TransferCorrectives,
    DAZ_OT_TransferOtherMorphs,
    DAZ_OT_MixShapekeys,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
