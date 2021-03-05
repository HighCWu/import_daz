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
from .globvars import getMaterialEnums, getShapeEnums
from .fileutils import SingleFile, ImageFile

#-------------------------------------------------------------
#   Load HD Vector Displacement Map
#-------------------------------------------------------------

class LoadMap:
    shapekey: EnumProperty(
        items = getShapeEnums,
        name = "Shapekey",
        description = "Drive texture with this shapekey")

    material: EnumProperty(
        items = getMaterialEnums,
        name = "Material",
        description = "Material that texture is added to")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)

    def draw(self, context):
        self.layout.prop(self, "shapekey")
        self.layout.prop(self, "material")

    def getTexture(self, ob, col):
        from .matedit import getTree
        img = bpy.data.images.load(self.filepath)
        img.name = os.path.splitext(os.path.basename(self.filepath))[0]
        img.colorspace_settings.name = "Non-Color"
        tree = getTree(ob, self.material)
        nodes = tree.getNodes("TEX_COORD")
        if nodes:
            texco = nodes[0]
        else:
            texco = tree.addNode("ShaderNodeTexCoord", col=1)
        tex = tree.addTextureNode(col, img, img.name, "NONE")
        tree.links.new(texco.outputs["UV"], tex.inputs["Vector"])
        return tree, tex

#-------------------------------------------------------------
#   Load HD Vector Displacement Map
#-------------------------------------------------------------

class DAZ_OT_LoadHDVectorDisp(DazOperator, LoadMap, SingleFile, ImageFile):
    bl_idname = "daz.load_hd_vector_disp"
    bl_label = "Load HD Vector Disp"
    bl_description = "Load vector displacement map to morph"
    bl_options = {'UNDO'}

    def run(self, context):
        from .driver import makePropDriver
        ob = context.object
        tree,tex = self.getTexture(ob, 5)

        disp = tree.addNode("ShaderNodeVectorDisplacement", col=6, label=self.shapekey)
        disp.inputs["Midlevel"].default_value = 0.5
        disp.inputs["Scale"].default_value = ob.DazScale
        tree.links.new(tex.outputs["Color"], disp.inputs["Vector"])
        path = 'data.shape_keys.key_blocks["%s"].value' % self.shapekey
        makePropDriver(path, disp.inputs["Scale"], "default_value", ob, "%g*x" % ob.DazScale)

        for node in tree.getNodes("OUTPUT_MATERIAL"):
            tree.links.new(disp.outputs["Displacement"], node.inputs["Displacement"])

#-------------------------------------------------------------
#   Load HD Normal Map
#-------------------------------------------------------------

class DAZ_OT_LoadHDNormalMap(DazOperator, LoadMap, SingleFile, ImageFile):
    bl_idname = "daz.load_hd_normal_map"
    bl_label = "Load HD Normal Map"
    bl_description = "Load normal map to morph"
    bl_options = {'UNDO'}

    def run(self, context):
        from .driver import makePropDriver
        ob = context.object
        tree,tex = self.getTexture(ob, -1)

        normal = tree.addNode("ShaderNodeNormalMap", col=0, label=self.shapekey)
        normal.space = "TANGENT"
        normal.inputs["Strength"].default_value = 1
        tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
        path = 'data.shape_keys.key_blocks["%s"].value' % self.shapekey
        makePropDriver(path, normal.inputs["Strength"], "default_value", ob, "x")

        nodes = tree.getNodes("BUMP")
        if nodes:
            bump = nodes[0]
            tree.links.new(normal.outputs["Normal"], bump.inputs["Normal"])
        else:
            for node in tree.nodes:
                if "Normal" in node.inputs.keys():
                    tree.links.new(normal.outputs["Normal"], normal.inputs["Normal"])

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