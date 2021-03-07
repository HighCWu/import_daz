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

class LoadMap:
    shapeFromName : BoolProperty(
        name = "Shapekey From Filename",
        description = "Use the filename to deduce the shapekey",
        default = True)

    tile : IntProperty(
        name = "Tile",
        description = "Only load textures in this tile",
        min = 1001, max = 1009,
        default = 1001)

    shapekey: EnumProperty(
        items = getShapeEnums,
        name = "Shapekey",
        description = "Drive texture with this shapekey")

    material: EnumProperty(
        items = getMaterialEnums,
        name = "Material",
        description = "Material that textures are added to")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)

    def draw(self, context):
        self.layout.prop(self, "material")
        #self.layout.prop(self, "shapeFromName")
        if not self.shapeFromName:
            self.layout.prop(self, "shapekey")
        self.layout.prop(self, "tile")


    def getArgs(self, ob):
        from .fileutils import getMultiFiles
        filepaths = getMultiFiles(self, theImageExtensions)
        skeys = ob.data.shape_keys
        shapes = dict([(skey.name.lower(), skey) for skey in skeys.key_blocks])
        args = []
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
        for _,sname,_,_ in args:
            print(" *", sname)
        return args


    def getTree(self, ob, col):
        from .matedit import getTree
        from .cycles import findNodes
        tree = getTree(ob, self.material)
        nodes = findNodes(tree, "TEX_COORD")
        if nodes:
            texco = nodes[0]
        else:
            texco = tree.addNode("ShaderNodeTexCoord", col=1)
        return tree, texco

#-------------------------------------------------------------
#   Load HD Vector Displacement Map
#-------------------------------------------------------------

class VectorDispGroup(CyclesGroup):

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
        sum = None
        for ob,sname,skey,filepath in args:
            img = bpy.data.images.load(filepath)
            img.name = os.path.splitext(os.path.basename(filepath))[0]
            img.colorspace_settings.name = "Non-Color"
            tex = self.addTextureNode(1, img, sname, "NONE")
            self.links.new(self.inputs.outputs["UV"], tex.inputs["Vector"])

            disp = self.addNode("ShaderNodeVectorDisplacement", col=2, label=skey.name)
            disp.inputs["Midlevel"].default_value = 0.5
            disp.inputs["Scale"].default_value = ob.DazScale
            self.links.new(tex.outputs["Color"], disp.inputs["Vector"])
            if skey:
                path = 'data.shape_keys.key_blocks["%s"].value' % sname
                makePropDriver(path, disp.inputs["Scale"], "default_value", ob, "%g*x" % ob.DazScale)

            if sum is None:
                sum = disp
            else:
                add = self.addNode("ShaderNodeVectorMath", col=3)
                add.operation = 'ADD'
                self.links.new(sum.outputs[0], add.inputs[0])
                self.links.new(disp.outputs[0], add.inputs[1])
                sum = add
        self.links.new(sum.outputs[0], self.outputs.inputs["Displacement"])


class DAZ_OT_LoadHDVectorDisp(DazOperator, LoadMap, MultiFile, ImageFile):
    bl_idname = "daz.load_hd_vector_disp"
    bl_label = "Load HD Morph Vector Disp Maps"
    bl_description = "Load vector displacement map to morph"
    bl_options = {'UNDO'}

    type = "VDISP"

    def run(self, context):
        from .cycles import findNodes
        ob = context.object
        args = self.getArgs(ob)
        tree,texco = self.getTree(ob, 5)
        disp = tree.addGroup(VectorDispGroup, "DAZ HD Vector Disp", col=6, args=args, force=True)
        tree.links.new(texco.outputs["UV"], disp.inputs["UV"])
        for node in findNodes(tree, "OUTPUT_MATERIAL"):
            tree.links.new(disp.outputs["Displacement"], node.inputs["Displacement"])
        if GS.pruneNodes:
            tree.prune()

#-------------------------------------------------------------
#   Load HD Normal Map
#-------------------------------------------------------------

class LocalNormalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Strength", "Color", "Normal"]
        self.outsockets += ["Normal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 2)
        self.group.inputs.new("NodeSocketFloat", "Strength")
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args):
        normal = self.addNode("ShaderNodeNormalMap", col=1)
        normal.space = "TANGENT"
        normal.inputs["Strength"].default_value = 1
        self.links.new(self.inputs.outputs["Strength"], normal.inputs["Strength"])
        self.links.new(self.inputs.outputs["Color"], normal.inputs["Color"])

        sub = self.addNode("ShaderNodeVectorMath", col=1)
        sub.operation = 'SUBTRACT'
        self.links.new(normal.outputs[0], sub.inputs[0])
        self.links.new(self.inputs.outputs["Normal"], sub.inputs[1])

        #scale = self.addNode("ShaderNodeVectorMath", col=1)
        #scale.operation = 'SCALE'
        #self.links.new(sub.outputs[0], scale.inputs[0])
        #self.links.new(self.inputs.outputs["Strength"], scale.inputs[1])

        self.links.new(sub.outputs[0], self.outputs.inputs["Normal"])


class NormalMapGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color", "UV"]
        self.outsockets += ["Normal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.outputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args):
        from .driver import makePropDriver
        sum = self.addNode("ShaderNodeNormalMap", 0)
        sum.space = "TANGENT"
        sum.inputs["Strength"].default_value = 1
        self.links.new(self.inputs.outputs["Color"], sum.inputs["Color"])

        geo = self.addNode("ShaderNodeNewGeometry", 0)

        for ob,sname,skey,filepath in args:
            img = bpy.data.images.load(filepath)
            img.name = os.path.splitext(os.path.basename(filepath))[0]
            img.colorspace_settings.name = "Non-Color"
            tex = self.addTextureNode(1, img, sname, "NONE")
            self.links.new(self.inputs.outputs["UV"], tex.inputs["Vector"])

            normal = self.addGroup(LocalNormalGroup, "DAZ Local Normal", col=2)
            normal.inputs["Strength"].default_value = 1
            self.links.new(tex.outputs["Color"], normal.inputs["Color"])
            self.links.new(geo.outputs["Normal"], normal.inputs["Normal"])
            if skey:
                path = 'data.shape_keys.key_blocks["%s"].value' % sname
                makePropDriver(path, normal.inputs["Strength"], "default_value", ob, "x")

            add = self.addNode("ShaderNodeVectorMath", 3)
            add.operation = 'ADD'
            self.links.new(sum.outputs[0], add.inputs[0])
            self.links.new(normal.outputs[0], add.inputs[1])
            sum = add

        fix = self.addNode("ShaderNodeVectorMath", 4)
        fix.operation = 'NORMALIZE'
        self.links.new(sum.outputs[0], fix.inputs[0])
        self.links.new(fix.outputs[0], self.outputs.inputs["Normal"])


class DAZ_OT_LoadHDNormalMap(DazOperator, LoadMap, MultiFile, ImageFile):
    bl_idname = "daz.load_hd_normal_map"
    bl_label = "Load HD Morph Normal Maps"
    bl_description = "Load normal map to morph"
    bl_options = {'UNDO'}

    type = "mrNM"

    def run(self, context):
        from .cycles import findNode, findNodes
        ob = context.object
        args = self.getArgs(ob)
        tree,texco = self.getTree(ob, 5)
        tolinks = self.getToLinks(tree)
        fromlinks = self.getFromLinks(tree)
        normal = tree.addGroup(NormalMapGroup, "DAZ HD Normal Map", col=0, args=args, force=True)
        normal.inputs["Color"].default_value = (0.5, 0.5, 1, 1)
        tree.links.new(texco.outputs["UV"], normal.inputs["UV"])
        for link in tolinks:
            if link.from_socket.name == "Color":
                tree.links.new(link.from_socket, normal.inputs["Color"])
                break

        if fromlinks:
            for link in fromlinks:
                tree.links.new(normal.outputs["Normal"], link.to_socket)
        else:
            bump = findNode(tree, "BUMP")
            if bump:
                tree.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
            else:
                for node in tree.nodes:
                    if "Normal" in node.inputs.keys():
                        tree.links.new(normal.outputs["Normal"], node.inputs["Normal"])

        if GS.pruneNodes:
            tree.prune()


    def getFromLinks(self, tree):
        from .cycles import findLinksFrom
        fromlinks = []
        for link in findLinksFrom(tree, "NORMAL_MAP"):
            fromlinks.append(link)
        for link in findLinksFrom(tree, "GROUP"):
            if link.from_node.name.startswith("DAZ HD Normal Map"):
                fromlinks.append(link)
        return fromlinks


    def getToLinks(self, tree):
        from .cycles import findLinksTo
        tolinks = []
        for link in findLinksTo(tree, "NORMAL_MAP"):
            tolinks.append(link)
        for link in findLinksTo(tree, "GROUP"):
            if link.to_node.name.startswith("DAZ HD Normal Map"):
                tolinks.append(link)
        return tolinks

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_LoadHDVectorDisp,
    DAZ_OT_LoadHDNormalMap,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)