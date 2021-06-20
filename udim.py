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

import bpy
import os
from .error import *
from .utils import *
from .fileutils import MultiFile, ImageFile

class DazUdimGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


def getTargetMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]


class MaterialSelector:
    umats : CollectionProperty(type = DazUdimGroup)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.data.materials) > 0)


    def draw(self, context):
        for umat in self.umats:
            self.layout.prop(umat, "bool", text=umat.name)


    def isUdimMaterial(self, mat, color):
        if mat.diffuse_color[0:3] == color:
            return True
        from .guess import getSkinMaterial
        return (getSkinMaterial(mat) in ["Red", "Teeth"])


    def shiftUVs(self, mat, mn, ob, tile):
        ushift = tile - mat.DazUDim
        print(" Shift", mat.name, mn, ushift)
        uvloop = ob.data.uv_layers.active
        m = 0
        for fn,f in enumerate(ob.data.polygons):
            if f.material_index == mn:
                for n in range(len(f.vertices)):
                    uvloop.data[m].uv[0] += ushift
                    m += 1
            else:
                m += len(f.vertices)


class DAZ_OT_UdimizeMaterials(DazOperator, MaterialSelector):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    trgmat : EnumProperty(items=getTargetMaterial, name="Active")

    useFixTiles : BoolProperty(
        name = "Fix UV tiles",
        description =  "Move UV vertices to the right tile automatically",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useFixTiles")
        self.layout.prop(self, "trgmat")
        self.layout.label(text="Materials To Merge")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        ob = context.object
        if not ob.DazLocalTextures:
            from .error import invokeErrorMessage
            invokeErrorMessage("Save local textures first")
            return {'CANCELLED'}
        self.collectMaterials(ob)
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def collectMaterials(self, ob):
        from .guess import getSkinMaterial
        from .material import WHITE
        color = WHITE
        for mat in ob.data.materials:
            if getSkinMaterial(mat) == "Skin":
                color = mat.diffuse_color[0:3]
                break
        self.umats.clear()
        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isUdimMaterial(mat, color)


    def run(self, context):
        from shutil import copyfile

        ob = context.object
        mats = []
        mnums = []
        amat = None
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                mnums.append(mn)
                if amat is None or mat.name == self.trgmat:
                    amat = mat
                    amnum = mn
                    atile = 1001 + mat.DazUDim

        if amat is None:
            raise DazError("No materials selected")

        self.nodes = {}
        for mat in mats:
            self.nodes[mat.name] = self.getChannels(mat)

        if self.useFixTiles:
            for f in ob.data.polygons:
                f.select = False
            for mn,mat in zip(mnums, mats):
                self.fixTiles(mat, mn, ob)

        for key,anode in self.nodes[amat.name].items():
            anode.image.source = "TILED"
            anode.extension = "CLIP"
            basename = "T_" + self.getBaseName(anode.name, amat.DazUDim)
            udims = {}
            for mat in mats:
                nodes = self.nodes[mat.name]
                if key in nodes.keys():
                    img = nodes[key].image
                    self.updateImage(img, basename, mat.DazUDim)
                    if mat.DazUDim not in udims.keys():
                        udims[mat.DazUDim] = mat.name
                    if mat == amat:
                        img.name = "%s%d%s" % (basename, atile, os.path.splitext(img.name)[1])

            img = anode.image
            tile0 = img.tiles[0]
            for udim,mname in udims.items():
                if udim == 0:
                    tile0.number = 1001
                    tile0.label = mname
                else:
                    img.tiles.new(tile_number=1001+udim, label=mname)

        for f in ob.data.polygons:
            if f.material_index in mnums:
                f.material_index = amnum

        mnums.reverse()
        for mn in mnums:
            if mn != amnum:
                ob.data.materials.pop(index=mn)


    def fixTiles(self, mat, mn, ob):
        for node in self.nodes[mat.name].values():
            if node.image:
                imgname = node.image.name
                if imgname[-4:].isdigit():
                    tile = int(imgname[-4:]) - 1001
                elif (imgname[-8:-4].isdigit() and
                      imgname[-4] == "." and
                      imgname[-3:].isdigit()):
                    tile = int(imgname[-8:-4]) - 1001
                else:
                    continue
                if mat.DazUDim != tile:
                    self.shiftUVs(mat, mn, ob, tile)
                return


    def getChannels(self, mat):
        channels = {}
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                channel = self.getChannel(node, mat.node_tree.links)
                channels[channel] = node
        return channels


    def getChannel(self, node, links):
        for link in links:
            if link.from_node == node:
                if link.to_node.type in ["MIX_RGB", "MATH"]:
                    return self.getChannel(link.to_node, links)
                elif link.to_node.type == "BSDF_PRINCIPLED":
                    return ("PBR_%s" % link.to_socket.name)
                else:
                    return link.to_node.type
        return None


    def getBaseName(self, string, udim):
        du = str(1001 + udim)
        if string[-4:] == du:
            return string[:-4]
        else:
            return string


    def updateImage(self, img, basename, udim):
        from shutil import copyfile
        du = str(1001 + udim)
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        folder = os.path.dirname(src)
        fname,ext = os.path.splitext(bpy.path.basename(src))
        trg = os.path.join(folder, basename + du + ext)
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)


#----------------------------------------------------------
#   Set Udims to given tile
#----------------------------------------------------------

class DAZ_OT_SetUDims(DazOperator, MaterialSelector):
    bl_idname = "daz.set_udims"
    bl_label = "Set UDIM Tile"
    bl_description = "Move all UV coordinates of selected materials to specified UV tile"
    bl_options = {'UNDO'}

    tile : IntProperty(name="Tile", min=1001, max=1100, default=1001)

    def draw(self, context):
        self.layout.prop(self, "tile")
        MaterialSelector.draw(self, context)


    def invoke(self, context, event):
        self.umats.clear()
        for mat in context.object.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = False
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        from .material import addUdim
        ob = context.object
        vdim = (self.tile - 1001)//10
        udim = self.tile - 10*vdim
        tile = self.tile - 1001
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                self.shiftUVs(mat, mn, ob, tile)
                addUdim(mat, udim - mat.DazUDim, vdim - mat.DazVDim)
                mat.DazUDim = udim
                mat.DazVDim = vdim

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazUdimGroup,
    DAZ_OT_UdimizeMaterials,
    DAZ_OT_SetUDims,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)



