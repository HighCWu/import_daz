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

import os
import bpy

from .error import *
from .utils import *
from .globvars import getMaterialEnums, getShapeEnums, theImageExtensions
from .fileutils import SingleFile, MultiFile, ImageFile
from .cgroup import CyclesGroup

#-------------------------------------------------------------
#   Load HD Vector Displacement Map
#-------------------------------------------------------------

class LoadMaps:
    useShapeDriver : BoolProperty(
        name = "Shapekey Drivers",
        description = "Drive maps with shapekey values",
        default = True)

    tile : IntProperty(
        name = "Tile",
        description = "Only load textures in this tile",
        min = 1001, max = 1009,
        default = 1001)

    usePrune : BoolProperty(
        name = "Prune Node Tree",
        description = "Prune the node tree",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useShapeDriver")
        self.layout.prop(self, "tile")
        self.layout.prop(self, "usePrune")


    def getArgs(self, ob):
        from .fileutils import getMultiFiles
        filepaths = getMultiFiles(self, theImageExtensions)
        skeys = ob.data.shape_keys
        args = []
        if self.useShapeDriver:
            if skeys:
                shapes = dict([(skey.name.lower(), skey) for skey in skeys.key_blocks])
            else:
                raise DazError("No shapekeys found")
            for filepath in filepaths:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                words = fname.rsplit("-", 3)
                if len(words) != 4:
                    print("Wrong file name: %s" % fname)
                elif words[1] != self.type:
                    print("Not a %s file: %s" % (self.type, fname))
                elif not words[2].isdigit() or int(words[2]) != self.tile:
                    print("Wrong tile %s != %d: %s" % (words[2], self.tile, fname))
                else:
                    sname = words[0].rstrip("_dhdm")
                    if sname in shapes.keys():
                        skey = shapes[sname]
                        args.append((ob, skey.name, skey, filepath))
                    else:
                        args.append((ob, sname, None, filepath))
        else:
            for filepath in filepaths:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                args.append((ob, fname, None, filepath))
        for _,sname,_,_ in args:
            print(" *", sname)
        return args

#-------------------------------------------------------------
#   Scalar and Vector Displacement groups
#-------------------------------------------------------------

class DispGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["UV"]
        self.outsockets += ["Displacement"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.outputs.new("NodeSocketVector", "Displacement")


    def addNodes(self, args):
        from .driver import makePropDriver
        last = None
        for ob,sname,skey,filepath in args:
            tex = self.addImageTexNode(filepath, sname, 1)
            self.links.new(self.inputs.outputs["UV"], tex.inputs["Vector"])

            disp = self.addDispNode(sname, tex)
            disp.inputs["Scale"].default_value = ob.DazScale
            if skey:
                path = 'data.shape_keys.key_blocks["%s"].value' % sname
                makePropDriver(path, disp.inputs["Scale"], "default_value", ob, "%g*x" % ob.DazScale)

            if last is None:
                last = disp
            else:
                add = self.addMathNode()
                add.operation = 'ADD'
                self.links.new(last.outputs[0], add.inputs[0])
                self.links.new(disp.outputs[0], add.inputs[1])
                last = add
        if last:
            self.links.new(last.outputs[0], self.outputs.inputs["Displacement"])


class ScalarDispGroup(DispGroup):
    def addDispNode(self, sname, tex):
        disp = self.addNode("ShaderNodeDisplacement", col=2, label=sname)
        disp.inputs["Midlevel"].default_value = 0.5
        self.links.new(tex.outputs["Color"], disp.inputs["Height"])
        return disp

    def addMathNode(self):
        return self.addNode("ShaderNodeVectorMath", col=3)


class VectorDispGroup(DispGroup):
    def addDispNode(self, sname, tex):
        disp = self.addNode("ShaderNodeVectorDisplacement", col=2, label=sname)
        disp.inputs["Midlevel"].default_value = 0.5
        self.links.new(tex.outputs["Color"], disp.inputs["Vector"])
        return disp

    def addMathNode(self):
        return self.addNode("ShaderNodeVectorMath", col=3)


class DispAdder:
    def loadDispMaps(self, mat, args):
        from .cycles import findNodes, findTree, findTexco
        tree = findTree(mat)
        texco = findTexco(tree, 5)
        disp = self.addDispGroup(tree, args)
        tree.links.new(texco.outputs["UV"], disp.inputs["UV"])
        for node in findNodes(tree, "OUTPUT_MATERIAL"):
            tree.links.new(disp.outputs["Displacement"], node.inputs["Displacement"])
        if self.usePrune:
            tree.prune()


class ScalarDispAdder(DispAdder):
    def addDispGroup(self, tree, args):
        return tree.addGroup(ScalarDispGroup, "DAZ Scalar Disp", col=6, args=args, force=True)


class VectorDispAdder(DispAdder):
    def addDispGroup(self, tree, args):
        return tree.addGroup(VectorDispGroup, "DAZ Vector Disp", col=6, args=args, force=True)


class DAZ_OT_LoadVectorDisp(DazOperator, LoadMaps, VectorDispAdder, MultiFile, ImageFile, IsMesh):
    bl_idname = "daz.load_vector_disp"
    bl_label = "Load Vector Disp Maps"
    bl_description = "Load vector displacement map to active material"
    bl_options = {'UNDO'}

    type = "VDISP"

    def run(self, context):
        ob = context.object
        args = self.getArgs(ob)
        mat = ob.data.materials[ob.active_material_index]
        self.loadDispMaps(mat, args)

#-------------------------------------------------------------
#   Load HD Normal Map
#-------------------------------------------------------------

class MixNormalTextureGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Color1", "Color2"]
        self.outsockets += ["Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 8)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketColor", "Color1")
        self.group.inputs.new("NodeSocketColor", "Color2")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addNodes(self, args):
        mix = self.addNode("ShaderNodeMixRGB", 1)
        mix.blend_type = 'OVERLAY'
        self.links.new(self.inputs.outputs["Fac"], mix.inputs["Fac"])
        self.links.new(self.inputs.outputs["Color1"], mix.inputs["Color1"])
        self.links.new(self.inputs.outputs["Color2"], mix.inputs["Color2"])
        self.links.new(mix.outputs["Color"], self.outputs.inputs["Color"])

    # Cannot link dot product to divide. Blender bug?
    def addNodes0(self, args):
        val1 = self.addNode("ShaderNodeValue", 1)
        val1.outputs[0].default_value = 2
        vmult1 = self.addNode("ShaderNodeMixRGB", 2)
        vmult1.blend_type = 'MULTIPLY'
        vmult1.inputs[0].default_value = 1
        self.links.new(val1.outputs[0], vmult1.inputs[1])
        self.links.new(self.inputs.outputs["Color1"], vmult1.inputs[2])

        val2 = self.addNode("ShaderNodeValue", 1)
        val2.outputs[0].default_value = -1
        comb1 = self.addNode("ShaderNodeCombineRGB", 2)
        self.links.new(val2.outputs[0], comb1.inputs[0])
        self.links.new(val2.outputs[0], comb1.inputs[1])
        add1 = self.addNode("ShaderNodeMath", 2)
        add1.operation = 'ADD'
        self.links.new(val2.outputs[0], add1.inputs[0])
        self.links.new(self.inputs.outputs["Fac"], add1.inputs[1])
        self.links.new(add1.outputs[0], comb1.inputs[2])

        val3 = self.addNode("ShaderNodeValue", 1)
        val3.outputs[0].default_value = -2
        val4 = self.addNode("ShaderNodeValue", 1)
        val4.outputs[0].default_value = 2
        comb2 = self.addNode("ShaderNodeCombineRGB", 2)
        self.links.new(val3.outputs[0], comb2.inputs[0])
        self.links.new(val3.outputs[0], comb2.inputs[1])
        self.links.new(val4.outputs[0], comb2.inputs[2])

        val5 = self.addNode("ShaderNodeValue", 1)
        val5.outputs[0].default_value = 1
        val6 = self.addNode("ShaderNodeValue", 1)
        val6.outputs[0].default_value = -1
        comb3 = self.addNode("ShaderNodeCombineRGB", 2)
        self.links.new(val5.outputs[0], comb3.inputs[0])
        self.links.new(val5.outputs[0], comb3.inputs[1])
        self.links.new(val6.outputs[0], comb3.inputs[2])

        vadd1 = self.addNode("ShaderNodeMixRGB", 3)
        vadd1.blend_type = 'ADD'
        vadd1.inputs[0].default_value = 1
        self.links.new(vmult1.outputs[0], vadd1.inputs[1])
        self.links.new(comb1.outputs[0], vadd1.inputs[2])

        vmult2 = self.addNode("ShaderNodeMixRGB", 3)
        vmult2.blend_type = 'MULTIPLY'
        vmult2.inputs[0].default_value = 1
        self.links.new(self.inputs.outputs["Color2"], vmult2.inputs[1])
        self.links.new(comb2.outputs[0], vmult2.inputs[2])

        vadd2 = self.addNode("ShaderNodeMixRGB", 3)
        vadd2.blend_type = 'ADD'
        vadd2.inputs[0].default_value = 1
        self.links.new(vmult2.outputs[0], vadd2.inputs[1])
        self.links.new(comb3.outputs[0], vadd2.inputs[2])

        dot = self.addNode("ShaderNodeVectorMath", 4)
        dot.operation = 'DOT_PRODUCT'
        self.links.new(vadd1.outputs[0], dot.inputs[0])
        self.links.new(vadd2.outputs[0], dot.inputs[1])

        sep1 = self.addNode("ShaderNodeSeparateRGB", 4)
        self.links.new(vadd1.outputs[0], sep1.inputs[0])

        vdiv = self.addNode("ShaderNodeMixRGB", 5)
        vdiv.blend_type = 'DIVIDE'
        vdiv.inputs[0].default_value = 1
        self.links.new(dot.outputs[0], vdiv.inputs[1])
        self.links.new(comb3.outputs[0], vdiv.inputs[2])

        vmult3 = self.addNode("ShaderNodeMixRGB", 5)
        vmult3.blend_type = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Fac"], vmult3.inputs[0])
        self.links.new(vdiv.outputs[0], vmult3.inputs[1])
        self.links.new(sep1.outputs[2], vmult3.inputs[2])

        vsub2 = self.addNode("ShaderNodeMixRGB", 5)
        vsub2.blend_type = 'SUBTRACT'
        self.links.new(self.inputs.outputs["Fac"], vsub2.inputs[0])
        self.links.new(vmult3.outputs[0], vsub2.inputs[1])
        self.links.new(vadd2.outputs[0], vsub2.inputs[2])

        norm = self.addNode("ShaderNodeVectorMath", 6)
        norm.operation = 'NORMALIZE'
        self.links.new(vsub2.outputs[0], norm.inputs[0])

        val7 = self.addNode("ShaderNodeValue", 6)
        val7.outputs[0].default_value = 0.5

        vmult4 = self.addNode("ShaderNodeMixRGB", 7)
        vmult4.blend_type = 'MULTIPLY'
        vmult4.inputs[0].default_value = 1
        self.links.new(norm.outputs[0], vmult4.inputs[1])
        self.links.new(val7.outputs[0], vmult4.inputs[2])

        vadd4 = self.addNode("ShaderNodeMixRGB", 7)
        vadd4.blend_type = 'ADD'
        vadd4.inputs[0].default_value = 1
        self.links.new(vmult4.outputs[0], vadd4.inputs[1])
        self.links.new(val7.outputs[0], vadd4.inputs[2])

        self.links.new(vadd4.outputs[0], self.outputs.inputs["Color"])


class NormalAdder:
    def loadNormalMaps(self, mat, args, row):
        from .driver import makePropDriver
        from .cycles import findTree, findTexco, findNode, findLinksTo, YSIZE
        tree = findTree(mat)
        texco = findTexco(tree, 1)
        tree.ycoords[-1] = tree.ycoords[0] = YSIZE*(2-row)

        normal = findNode(tree, "NORMAL_MAP")
        socket = None
        if normal is None:
            tree.ycoords[1] -= YSIZE
            normal = tree.addNode("ShaderNodeNormalMap", col=1)
        else:
            links = findLinksTo(tree, "NORMAL_MAP")
            if links:
                socket = links[0].from_socket

        bump = findNode(tree, "BUMP")
        if bump:
            tree.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
        else:
            for node in tree.nodes:
                if "Normal" in node.inputs.keys():
                    tree.links.new(normal.outputs["Normal"], node.inputs["Normal"])

        for ob,sname,skey,filepath in args:
            tex = tree.addImageTexNode(filepath, sname, -1)
            tree.links.new(texco.outputs["UV"], tex.inputs["Vector"])

            mix = tree.addGroup(MixNormalTextureGroup, "DAZ Mix Normal Texture", col=0, force=True)
            mix.inputs["Fac"].default_value = 1
            mix.inputs["Color1"].default_value = (0.5,0.5,1,1)
            if socket:
                tree.links.new(socket, mix.inputs["Color1"])
            tree.links.new(tex.outputs["Color"], mix.inputs["Color2"])
            if skey:
                path = 'data.shape_keys.key_blocks["%s"].value' % sname
                makePropDriver(path, mix.inputs["Fac"], "default_value", ob, "x")
            socket = mix.outputs["Color"]
        tree.links.new(socket, normal.inputs["Color"])
        if self.usePrune:
            tree.prune()


class DAZ_OT_LoadNormalMap(DazOperator, LoadMaps, NormalAdder, MultiFile, ImageFile, IsMesh):
    bl_idname = "daz.load_normal_map"
    bl_label = "Load Normal Maps"
    bl_description = "Load normal maps to active material"
    bl_options = {'UNDO'}

    type = "mrNM"

    def run(self, context):
        ob = context.object
        args = self.getArgs(ob)
        mat = ob.data.materials[ob.active_material_index]
        self.loadNormalMaps(mat, args, 1)

#----------------------------------------------------------
#   Baking
#----------------------------------------------------------

class Baker:
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

    bakeType : EnumProperty(
        items = [('NORMALS', "Normals", "Bake normals"),
                 ('DISPLACEMENT', "Displacement", "Bake displacement")],
        name = "Bake Type",
        description = "Bake Type",
        default = 'NORMALS')

    subfolder : StringProperty(
        name = "Subfolder",
        description = "Subfolder for normal/displace maps",
        default = "")

    basename : StringProperty(
        name = "Base Name",
        description = "Name used to construct file names",
        default = "")


    def draw(self, context):
        self.layout.prop(self, "imageSize")
        self.layout.prop(self, "bakeType")
        self.layout.prop(self, "subfolder")
        self.layout.prop(self, "basename")


    storedFolder : StringProperty(default = "")
    storedName : StringProperty(default = "")

    def setDefaultNames(self, context):
        if self.storedName:
            self.basename = self.storedName
        else:
            self.basename = ""
            self.basename = self.getBaseName(context.object)
        if self.storedFolder:
            self.subfolder = self.storedFolder
        else:
            self.subfolder = self.basename


    def storeDefaultNames(self, context):
        if not self.subfolder:
            self.subfolder = self.getBaseName(context.object)
        self.storedFolder = self.subfolder
        self.storedName = self.basename


    def getBaseName(self, ob):
        if self.basename:
            return self.basename
        elif ob.name[-3:] == "_HD":
            obname = ob.name[:-3]
        else:
            obname = ob.name
        if ob.name[-5:] == " Mesh":
            obname = obname[:-5]
        return bpy.path.clean_name(obname.lower())


    def getImageName(self, basename, tile):
        if self.bakeType == 'NORMALS':
            return ("%s_NM_%d_%s.png" % (basename, tile, self.imageSize))
        elif self.bakeType == 'DISPLACEMENT':
            return ("%s_DISP_%d_%s.png" % (basename, tile, self.imageSize))


    def getImagePath(self, imgname, create):
        folder = os.path.dirname(bpy.data.filepath)
        dirpath = os.path.join(folder, "textures", self.bakeType.lower(), self.subfolder)
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

#----------------------------------------------------------
#   Bake maps
#----------------------------------------------------------

class DAZ_OT_BakeMaps(DazPropsOperator, Baker):
    bl_idname = "daz.bake_maps"
    bl_label = "Bake Maps"
    bl_description = "Bake normal/displacement maps for the selected HD meshes"
    bl_options = {'UNDO'}

    useSingleTile : BoolProperty(
        name = "Single Tile",
        description = "Only bake map for a single tile",
        default = False)

    tile : IntProperty(
        name = "Tile",
        description = "Single tile to bake",
        min = 1001, max = 1100,
        default = 1001)

    def draw(self, context):
        Baker.draw(self, context)
        self.layout.prop(self, "useSingleTile")
        if self.useSingleTile:
            self.layout.prop(self, "tile")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and ob and getMultires(ob))


    def prequel(self, context):
        scn = context.scene
        self.engine = scn.render.engine
        scn.render.engine = 'CYCLES'
        self.bake_type = scn.render.bake_type
        self.use_bake_multires = scn.render.use_bake_multires
        self.samples = scn.cycles.samples
        scn.render.bake_type = self.bakeType
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


    def invoke(self, context, event):
        self.setDefaultNames(context)
        return DazPropsOperator.invoke(self, context, event)


    def run(self, context):
        self.storeDefaultNames(context)
        objects = [ob for ob in getSelectedMeshes(context) if getMultires(ob)]
        for ob in objects:
            activateObject(context, ob)
            try:
                self.storeMaterials(ob)
                self.bakeObject(context, ob)
            finally:
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
            tile,fnums = data
            if self.useSingleTile and tile != self.tile:
                continue
            showProgress(n, ntiles)
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
        img.filepath = self.getImagePath(imgname, True)
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

#----------------------------------------------------------
#   Load normal/displacement maps
#----------------------------------------------------------

class DAZ_OT_LoadBakedMaps(DazPropsOperator, Baker, LoadMaps, NormalAdder, ScalarDispAdder, IsMesh):
    bl_idname = "daz.load_baked_maps"
    bl_label = "Load Baked Maps"
    bl_description = "Load baked normal/displacement maps for the selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (bpy.data.filepath and ob)

    dispScale : FloatProperty(
        name = "Displacement Scale",
        description = "Displacement scale",
        min = 0.001, max = 10,
        default = 0.01)

    def draw(self, context):
        Baker.draw(self, context)
        if self.bakeType == 'DISPLACEMENT':
            self.layout.prop(self, "dispScale")
        self.layout.prop(self, "usePrune")

    def invoke(self, context, event):
        self.setDefaultNames(context)
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        self.storeDefaultNames(context)
        for ob in getSelectedMeshes(context):
            activateObject(context, ob)
            self.loadObjectMaps(ob)


    def loadObjectMaps(self, ob):
        mod = getMultires(ob)
        if mod:
            mod.show_viewport = mod.show_render = False
        tiles = self.getTiles(ob)
        mattiles = dict([(mn,None) for mn in range(len(ob.data.materials))])
        for tile,fnums in tiles.items():
            for fn in fnums:
                f = ob.data.polygons[fn]
                mattiles[f.material_index] = tile
        for mn,mat in enumerate(ob.data.materials):
            tile = mattiles[mn]
            if tile is None:
                print("No matching tile for material %s" % mat.name)
            else:
                self.loadMap(ob, mat, tile)


    def loadMap(self, ob, mat, tile):
        basename = self.getBaseName(ob)
        imgname = self.getImageName(basename, tile)
        filepath = self.getImagePath(imgname, False)
        args = [(ob, imgname, None, filepath)]
        if self.bakeType == 'NORMALS':
            self.loadNormalMaps(mat, args, 0)
        elif self.bakeType == 'DISPLACEMENT':
            self.loadDispMaps(mat, args)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_LoadVectorDisp,
    DAZ_OT_LoadNormalMap,
    DAZ_OT_BakeMaps,
    DAZ_OT_LoadBakedMaps,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)