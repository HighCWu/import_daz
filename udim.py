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
from .utils import *


class DazUdimGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


def getTargetMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]


class DAZ_OT_UdimizeMaterials(DazOperator):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    umats : CollectionProperty(type = DazUdimGroup)
    trgmat : EnumProperty(items=getTargetMaterial, name="Active")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazLocalTextures and len(ob.data.materials) > 0)


    def draw(self, context):
        self.layout.prop(self, "trgmat")
        self.layout.label(text="Materials To Merge")
        for umat in self.umats:
            self.layout.prop(umat, "bool", text=umat.name)


    def invoke(self, context, event):
        ob = context.object
        self.umats.clear()
        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isUdimMaterial(mat)
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
#   Normal maps
#----------------------------------------------------------

class NormalMap:
    imageSize : EnumProperty(
        items = [("512", "512 x 512", "512 x 512 pixels"),
                 ("1024", "1024 x 1024", "1024 x 1024 pixels"),
                 ("2048", "2048 x 2048", "2048 x 2048 pixels"),
                 ("4096", "4096 x 4096", "4096 x 4096 pixels"),
                ],
        name = "Image Size",
        description = "Size of the normal map texture image",
        default = "512"
    )


    def getBaseName(self, ob):
        if ob.name[-3:] == "_HD":
            obname = ob.name[:-3]
        else:
            obname = ob.name
        if ob.name[-5:] == " Mesh":
            obname = obname[:-5]
        return bpy.path.clean_name(obname.lower())


    def getImageName(self, basename, tile):
        return ("%s_NM_%d_%s.png" % (basename, tile, self.imageSize))


    def getImagePath(self, basename, imgname, create):
        folder = os.path.dirname(bpy.data.filepath)
        dirpath = os.path.join(folder, "textures", "normals", basename)
        if not os.path.exists(dirpath):
            if create:
                os.makedirs(dirpath)
            else:
                return None
        return os.path.join(dirpath, imgname)


    def getTiles(self, ob):
        tiles = {}
        uvloop = ob.data.uv_layers[0]
        m = 0
        for f in ob.data.polygons:
            n = len(f.vertices)
            rx = sum([uvloop.data[k].uv[0] for k in f.loop_indices])/n
            ry = sum([uvloop.data[k].uv[1] for k in f.loop_indices])/n
            i = max(0, int(round(rx-0.5)))
            j = max(0, int(round(ry-0.5)))
            tile = 1001 + 10*j + i
            if tile not in tiles.keys():
                tiles[tile] = []
            tiles[tile].append(f.index)
            m += n
        return tiles


def getMultires(ob):
    for mod in ob.modifiers:
        if mod.type == 'MULTIRES':
            return mod
    return None


class DAZ_OT_BakeNormalMaps(DazPropsOperator, NormalMap):
    bl_idname = "daz.bake_normal_maps"
    bl_label = "Bake Normal Maps"
    bl_description = "Bake normal maps for the selected HD meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and ob and getMultires(ob))


    def draw(self, context):
        self.layout.prop(self, "imageSize")


    def prequel(self, context):
        scn = context.scene
        self.engine = scn.render.engine
        scn.render.engine = 'CYCLES'
        self.bake_type = scn.render.bake_type
        self.use_bake_multires = scn.render.use_bake_multires
        self.samples = scn.cycles.samples
        scn.render.bake_type = 'NORMALS'
        scn.render.use_bake_multires = True
        scn.render.bake_margin = 2
        scn.cycles.samples = 512
        self.object = context.view_layer.objects.active


    def sequel(self, context):
        scn = context.scene
        scn.render.use_bake_multires = self.use_bake_multires
        scn.render.bake_type = self.bake_type
        scn.render.engine = self.engine
        scn.cycles.samples = self.samples
        context.view_layer.objects.active = self.object


    def run(self, context):
        for ob in context.view_layer.objects:
            if ob.type == 'MESH' and ob.select_get() and getMultires(ob):
                try:
                    self.storeMaterials(ob)
                    self.bakeObject(context, ob)
                finally:
                    pass
                    self.restoreMaterials(ob)


    def storeMaterials(self, ob):
        self.mnums = [f.material_index for f in ob.data.polygons]
        self.materials = list(ob.data.materials)
        for mat in self.materials:
            ob.data.materials.pop()


    def restoreMaterials(self, ob):
        for mat in list(ob.data.materials):
            ob.data.materials.pop()
        for mat in self.materials:
            ob.data.materials.append(mat)
        for fn,mn in enumerate(self.mnums):
            f = ob.data.polygons[fn]
            f.material_index = mn


    def bakeObject(self, context, ob):
        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.objects.active = ob
        mod = getMultires(ob)
        if mod is None:
            print("Object %s has no multires modifier" % ob.name)
            return
        levels = mod.levels
        mod.levels = 0
        tiles = self.getTiles(ob)
        ntiles = len(tiles)
        startProgress("Baking %s" % ob.name)
        for n,data in enumerate(tiles.items()):
            showProgress(n, ntiles)
            tile,fnums = data
            img = self.makeImage(ob, tile)
            mat = self.makeMaterial(ob, img)
            self.translateTile(ob, fnums, tile, -1)
            self.selectFaces(ob, fnums, tile)
            bpy.ops.object.bake_image()
            img.save()
            print("Saved %s" % img.filepath)
            self.translateTile(ob, fnums, tile, 1)
            ob.data.materials.pop()
        showProgress(ntiles, ntiles)
        endProgress()
        mod.levels = levels


    def makeImage(self, ob, tile):
        basename = self.getBaseName(ob)
        imgname = self.getImageName(basename, tile)
        size = int(self.imageSize)
        img = bpy.data.images.new(imgname, size, size)
        img.colorspace_settings.name = "Non-Color"
        img.filepath = self.getImagePath(basename, imgname, True)
        return img


    def makeMaterial(self, ob, img):
        mat = bpy.data.materials.new(img.name)
        ob.data.materials.append(mat)
        ob.active_material = mat
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        texco = tree.nodes.new(type = "ShaderNodeTexCoord")
        texco.location = (0, 0)
        node = tree.nodes.new(type = "ShaderNodeTexImage")
        node.location = (200,0)
        node.image = img
        node.extension = 'CLIP'
        node.select = True
        tree.nodes.active = node
        tree.links.new(texco.outputs["UV"], node.inputs["Vector"])
        return mat


    def selectFaces(self, ob, fnums, tile):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.select_all(action='DESELECT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for fn in fnums:
            f = ob.data.polygons[fn]
            f.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')


    def translateTile(self, ob, fnums, tile, sign):
        bpy.ops.object.mode_set(mode='OBJECT')
        j = (tile-1001)//10
        i = (tile-1001-10*j)%10
        dx = sign*i
        dy = sign*j
        uvloop = ob.data.uv_layers[0]
        for f in ob.data.polygons:
            for n in f.loop_indices:
                uvloop.data[n].uv[0] += dx
                uvloop.data[n].uv[1] += dy


class DAZ_OT_LoadNormalMaps(DazPropsOperator, NormalMap):
    bl_idname = "daz.load_normal_maps"
    bl_label = "Load Normal Maps"
    bl_description = "Load normal maps for the selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and ob)


    def draw(self, context):
        self.layout.prop(self, "imageSize")


    def run(self, context):
        for ob in context.view_layer.objects:
            if ob.type == 'MESH' and ob.select_get():
                self.loadObjectNormals(ob)


    def loadObjectNormals(self, ob):
        mod = getMultires(ob)
        if mod:
            mod.show_viewport = mod.show_render = False
        tiles = self.getTiles(ob)
        nmaps = {}
        mattiles = dict([(mn,None) for mn in range(len(ob.data.materials))])
        for tile,fnums in tiles.items():
            img = self.loadImage(ob, tile)
            img.colorspace_settings.name = "Non-Color"
            nmaps[tile] = img
            for fn in fnums:
                f = ob.data.polygons[fn]
                mattiles[f.material_index] = tile
        for mn,mat in enumerate(ob.data.materials):
            tile = mattiles[mn]
            if tile:
                self.loadNormalMap(mat, nmaps[tile])
            else:
                print("No matching tile for material %s" % mat.name)


    def loadImage(self, ob, tile):
        basename = self.getBaseName(ob)
        imgname = self.getImageName(basename, tile)
        filepath = self.getImagePath(basename, imgname, False)
        if not filepath:
            raise DazError("No normal maps found for\nobject %s" % ob.name)
        if not os.path.exists(filepath):
            size = int(self.imageSize)
            raise DazError("No %d x %d normal maps found for\nobject %s" % (size, size, ob.name))
        img = bpy.data.images.load(filepath)
        img.filepath = filepath
        return img


    def loadNormalMap(self, mat, img):
        tree = mat.node_tree
        texco = self.findTexco(tree)
        tex = self.addTexture(tree, img)
        tree.links.new(texco.outputs["UV"], tex.inputs["Vector"])
        normal,isnew = self.findNormal(tree)
        normal.inputs["Strength"].default_value = 1
        tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
        if isnew:
            self.linkNormal(tree, normal)


    def findNode(self, tree, type):
        for node in tree.nodes:
            if node.type == type:
                return node
        return None


    def findTexco(self, tree):
        node = self.findNode(tree, 'TEX_COORD')
        if node:
            return node
        node = tree.nodes.new(type="ShaderNodeTexCoord")
        node.location = (-300,0)
        return node


    def findNormal(self, tree):
        node = self.findNode(tree, 'NORMAL_MAP')
        if node:
            return node,False
        node = tree.nodes.new(type="ShaderNodeNormalMap")
        node.location = (-300,500)
        return node,True


    def linkNormal(self, tree, normal):
        for node in tree.nodes:
            if "Normal" in node.inputs.keys():
                tree.links.new(normal.outputs["Normal"], node.inputs["Normal"])


    def addTexture(self, tree, img):
        node = tree.nodes.new(type="ShaderNodeTexImage")
        node.location = (-300,250)
        node.label = img.name
        node.image = img
        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1
        return node

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazUdimGroup,
    DAZ_OT_UdimizeMaterials,
    DAZ_OT_SetUDims,
    DAZ_OT_BakeNormalMaps,
    DAZ_OT_LoadNormalMaps,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)



