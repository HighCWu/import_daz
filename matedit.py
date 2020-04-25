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
from bpy.props import *
import os
import math
from collections import OrderedDict

from .asset import Asset
from .channels import Channels
from .utils import *
from .settings import theSettings
from .error import *
from .globvars import TweakableChannels

from mathutils import Vector, Matrix

# ---------------------------------------------------------------------
#   Mini material editor
# ---------------------------------------------------------------------

def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))


def isRefractive(mat):
    if mat.use_nodes:
        for node in mat.node_tree.nodes.values():
            if node.type in ["BSDF_TRANSPARENT", "BSDF_REFRACTION"]:
                return True
            elif node.type == "BSDF_PRINCIPLED":
                if (inputDiffers(node, "Alpha", 1) or
                    inputDiffers(node, "Transmission", 0)):
                    return True
        return False
                
                
def inputDiffers(node, slot, value):
    if slot in node.inputs.keys():
        if node.inputs[slot].default_value != value:
            return True
    return False                


class ChannelChanger:
    def setChannel(self, ob, key, item):
        nodetype, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[key]
        for mat in ob.data.materials:            
            if mat and mat.use_nodes:
                if self.skipMaterial(mat):
                    continue
                for node in mat.node_tree.nodes.values():
                    if node.type == nodetype:
                        if not self.comesFrom(node, mat, fromType):
                            continue
                        socket = node.inputs[slot]
                        self.setOriginal(socket, ncomps, item)
                        self.setSocket(socket, ncomps, item)
                        fromnode = None
                        for link in mat.node_tree.links.values():
                            if link.to_node == node and link.to_socket == socket:
                                fromnode = link.from_node
                                fromsocket = link.from_socket
                                break
                        if fromnode:
                            if fromnode.type == "MIX_RGB":
                                self.setSocket(fromnode.inputs[1], ncomps, item)
                            elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                                self.setSocket(fromnode.inputs[0], 1, items)
                            elif fromnode.type == "TEX_IMAGE":
                                mix = self.addMixRGB(fromsocket, socket, mat.node_tree)
            elif mat and useAttr:
                self.setChannelInternal(mat, useAttr, factorAttr)

                
    def comesFrom(self, node, mat, fromType):
        if fromType is None:
            return True                            
        for link in mat.node_tree.links.values():
            if link.to_node == node and link.from_node.type == fromType:
                return True
        return False                


    def setChannelInternal(self, mat, useAttr, factorAttr):                 
        for mtex in mat.texture_slots:
            if mtex and getattr(mtex, useAttr):
                value = getattr(mtex, factorAttr)
                setattr(mtex, factorAttr, self.factor*value)
               
            
class DAZ_OT_LaunchEditor(DazPropsOperator, ChannelChanger, B.LaunchEditor, B.SlotString, B.UseInternalBool, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}


    def draw(self, context):
        self.layout.prop(self, "tweakableChannel")
        self.layout.prop(self, "factor")
        self.layout.prop(self, "colorFactor")
        self.layout.prop(self, "useAbsoluteTweak")
        self.layout.prop(self, "tweakMaterials")


    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                key = self.tweakableChannel
                item = self.getNewChannelFactor(ob, key)
                self.setChannel(ob, key, item)


    def getNewChannelFactor(self, ob, key):
        for item in ob.DazChannelFactors:
            if item.key == key:
                return item
        item = ob.DazChannelFactors.add()
        item.key = key
        item.new = True
        return item
   

    def skipMaterial(self, mat):
        from .guess import getSkinMaterial
        if isRefractive(mat):
            return (self.tweakMaterials not in ["Refractive", "All"])
        mattype = getSkinMaterial(mat)
        if self.tweakMaterials == "Skin":
            return (mattype != "Skin")
        elif self.tweakMaterials == "Skin-Lips-Nails":
            return (mattype not in ["Skin", "Red"])
        return False            


    def setOriginal(self, socket, ncomps, item):
        if item.new:
            x = socket.default_value
            if ncomps == 1:
                item.value = x
                item.color = (x,x,x,1)

            else:
                item.value = x[0]
                for n in range(ncomps):
                    item.color[n] = x[n]
            item.new = False
            

    def setSocket(self, socket, ncomps, item):
        fac = self.factor
        if self.useAbsoluteTweak:
            if ncomps == 1:
                socket.default_value = fac
            elif ncomps == 3:
                socket.default_value = (fac,fac,fac)
            else:
                for n in range(ncomps):
                    socket.default_value[n] = self.colorFactor[n]
        else:
            if ncomps == 1:
                socket.default_value *= fac
            elif ncomps == 3:
                for n in range(ncomps):
                    socket.default_value[n] *= fac
            else:
                for n in range(ncomps):
                    socket.default_value[n] *= self.colorFactor[n]

    def addMixRGB(self, fromsocket, tosocket, tree):
        mix = tree.nodes.new(type = "ShaderNodeMixRGB")
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value = self.colorFactor
        tree.links.new(fromsocket, mix.inputs[2])
        tree.links.new(mix.outputs[0], tosocket)
        return mix
                    

class DAZ_OT_ResetMaterial(DazOperator, ChannelChanger, IsMesh):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for item in list(ob.DazChannelFactors):
                    self.setChannel(ob, item.key, item)
                    item.new = True


    def setSocket(self, socket, ncomps, item):
        if ncomps == 1:
            socket.default_value = item.value
        else:
            for n in range(ncomps):
                socket.default_value[n] = item.color[n]        


    def setOriginal(self, socket, ncomps, item):
        pass

    def skipMaterial(self, mat):
        return False

    def addMixRGB(self, fromsocket, tosocket, tree):
        pass

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_LaunchEditor,
    DAZ_OT_ResetMaterial,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Object.DazChannelFactors = CollectionProperty(type = B.DazChannelFactor)
    bpy.types.Object.DazChannelValues = CollectionProperty(type = B.DazChannelFactor)
    bpy.types.Object.DazLocalTextures = BoolProperty(default = False)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
