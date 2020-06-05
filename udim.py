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

import bpy
import os
from bpy.props import *
from .error import *


class DazUdimGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


class DAZ_OT_UdimizeMaterials(DazOperator):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    umats : CollectionProperty(type = DazUdimGroup)
    #active : EnumProperty(items=[], name="Active")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazLocalTextures and len(ob.data.materials) > 0)


    def draw(self, context):
        self.layout.label(text="Materials To Merge")
        for umat in self.umats:
            self.layout.prop(umat, "bool", text=umat.name)
        self.layout.separator()
        self.layout.label(text="Target Material: %s" % self.trgmat.name)


    def invoke(self, context, event):
        ob = context.object
        enums = []
        self.trgmat = None
        self.umats.clear()
        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isUdimMaterial(mat)
            if self.trgmat is None and mat.DazUDim == 0:
                self.trgmat = mat
            enums.append((mat.name,mat.name,mat.name))
        if self.trgmat is None:
            self.trgmat = ob.data.materials[0]
        #self.active = EnumProperty(items=enums, name="Active")
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def isUdimMaterial(self, mat):
        from .guess import getSkinMaterial
        return (getSkinMaterial(mat) in ["Skin", "Red", "Teeth"])


    def run(self, context):
        from shutil import copyfile

        ob = context.object
        mats = []
        mnums = []
        amat = None
        tile0 = False
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                if amat is None:
                    amat = mat
                    amnum = mn
                    tile0 = (mat.DazUDim == 0)
                elif not tile0 and mat.DazUDim == 0:
                    mnums.append(amnum)
                    amat = mat
                    amnum = mn
                    tile0 = True
                else:
                    mnums.append(mn)

        if amat is None:
            raise DazError("No materials selected")

        self.nodes = {}
        for mat in mats:
            self.nodes[mat.name] = self.getChannels(mat)

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
                        img.name = basename + "1001" + os.path.splitext(img.name)[1]

            img = anode.image
            tile = img.tiles[0]
            tile.number = 1001 + amat.DazUDim
            tile.label = amat.name
            for udim,mname in udims.items():
                print("  UDIM", udim, mname)
                if udim != amat.DazUDim:
                    tile = img.tiles.new(tile_number=1001+udim, label=mname)


        for f in ob.data.polygons:
            if f.material_index in mnums:
                f.material_index = amnum

        mnums.reverse()
        for mn in mnums:
            if mn != amnum:
                ob.data.materials.pop(index=mn)


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
            #print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)


#----------------------------------------------------------
#   Set Udims to given tile
#----------------------------------------------------------

class DAZ_OT_SetUDims(DazOperator):
    bl_idname = "daz.set_udims"
    bl_label = "Set UDIM Tile"
    bl_description = (
        "Move all UV coordinates to specified UV tile\n" +
        "Do this on geografts before merging.")
    bl_options = {'UNDO'}

    tile : IntProperty(name="Tile", min=1001, max=1100, default=1001)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and not ob.DazUDimsCollapsed)

    def draw(self, context):
        self.layout.prop(self, "tile")

    def run(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in context.view_layer.objects:
            if ob.type == 'MESH' and ob.select_get():
                self.setUDims(ob)

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def setUDims(self, ob):
        from .material import addUdim
        from .geometry import addUdimsToUVs
        vdim = (self.tile - 1001)//10
        udim = self.tile - 1001 - 10*vdim
        addUdimsToUVs(ob, False, udim, vdim)
        for mn,mat in enumerate(ob.data.materials):
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

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)



