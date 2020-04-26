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
from mathutils import Vector, Matrix
from .error import *
from .utils import *
from .material import WHITE, BLACK
from collections import OrderedDict

# ---------------------------------------------------------------------
#   material.py   
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, # components, comes from)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1, None)),
    ("Bump Distance", ("BUMP", "Distance", None, None, 1, None)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1, None)),

    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", None, None, 4, None)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", None, None, 1, None)),

    ("Glossy Color", ("BSDF_GLOSSY", "Color", None, None, 4, None)),
    ("Glossy Roughness", ("BSDF_GLOSSY", "Roughness", None, None, 1, None)),

    ("Translucency Color", ("BSDF_TRANSLUCENT", "Color", "use_map_translucency", "translucency_factor", 4, None)),
    ("Translucency Strength", ("MIX_SHADER", "Fac", "use_map_translucency", "translucency_factor", 1, "BSDF_TRANSLUCENT")),

    ("Subsurface Color", ("SUBSURFACE_SCATTERING", "Color", None, None, 4, None)),
    ("Subsurface Scale", ("SUBSURFACE_SCATTERING", "Scale", None, None, 1, None)),
    ("Subsurface Radius", ("SUBSURFACE_SCATTERING", "Radius", None, None, 3, None)),

    ("Volume Absorption Color", ("VOLUME_ABSORPTION", "Color", None, None, 4, None)),
    ("Volume Absorption Density", ("VOLUME_ABSORPTION", "Density", None, None, 1, None)),

    ("Volume Scatter Color", ("VOLUME_SCATTER", "Color", None, None, 4, None)),
    ("Volume Scatter Density", ("VOLUME_SCATTER", "Density", None, None, 1, None)),

    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", None, None, 4, None)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", None, None, 1, None)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", None, None, 1, None)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", None, None, 1, None)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", None, None, 4, None)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", None, None, 3, None)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", None, None, 1, None)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", None, None, 1, None)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", None, None, 1, None)),
])
  # ---------------------------------------------------------------------
#   Mini material editor
# ---------------------------------------------------------------------

def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))


class ChannelSetter:                    
    def setChannel(self, ob, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[item.name]
        for mat in ob.data.materials:            
            if mat:
                if self.skipMaterial(mat):
                    continue
                elif mat.use_nodes:
                    self.setChannelCycles(ob, mat, nodeType, slot, ncomps, fromType, item)
                elif useAttr:
                    self.setChannelInternal(ob, mat, useAttr, factorAttr, item)
                    

    def setChannelCycles(self, ob, mat, nodeType, slot, ncomps, fromType, item):                                    
        for node in mat.node_tree.nodes.values():
            if node.type == nodeType:
                if not self.comesFrom(node, mat, fromType):
                    continue
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, ob, item.name)
                self.setSocket(socket, ncomps, item)
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        self.setSocket(fromnode.inputs[1], ncomps, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        self.setSocket(fromnode.inputs[0], 1, item)
                    elif fromnode.type == "TEX_IMAGE":
                        mix = self.addMixRGB(fromsocket, socket, mat.node_tree, item)
            

    def setSocket(self, socket, ncomps, item):
        if item.ncomps == 1:
            socket.default_value = self.getValue(item.number, ncomps)
        elif item.ncomps == 3:
            socket.default_value = self.getValue(item.vector, ncomps)
        elif item.ncomps == 4:
            socket.default_value = self.getValue(item.color, ncomps)


    def getValue(self, value, ncomps):
        if ncomps == 1:
            if isinstance(value, float):
                return value
            else:
                return value[0]
        elif ncomps == 3:
            if isinstance(value, float):
                return (value,value,value)
            elif len(value) == 3:
                return value
            elif len(value) == 4:
                return value[0:3]
        elif ncomps == 4:
            if isinstance(value, float):
                return (value,value,value,1)
            elif len(value) == 3:
                return (value[0],value[1],value[2],1)
            elif len(value) == 4:
                return value


    def setChannelInternal(self, ob, mat, useAttr, factorAttr):                 
        for mtex in mat.texture_slots:
            if mtex and getattr(mtex, useAttr):
                value = getattr(mtex, factorAttr)
                setattr(mtex, factorAttr, self.factor*value)


    def skipMaterial(self, mat):
        from .guess import getSkinMaterial
        if self.isRefractive(mat):
            return (self.tweakMaterials not in ["Refractive", "All"])
        mattype = getSkinMaterial(mat)
        if self.tweakMaterials == "Skin":
            return (mattype != "Skin")
        elif self.tweakMaterials == "Skin-Lips-Nails":
            return (mattype not in ["Skin", "Red"])
        return False            


    def isRefractive(self, mat):
        if mat.use_nodes:
            for node in mat.node_tree.nodes.values():
                if node.type in ["BSDF_TRANSPARENT", "BSDF_REFRACTION"]:
                    return True
                elif node.type == "BSDF_PRINCIPLED":
                    if (self.inputDiffers(node, "Alpha", 1) or
                        self.inputDiffers(node, "Transmission", 0)):
                        return True
            return False
                
                
    def inputDiffers(self, node, slot, value):
        if slot in node.inputs.keys():
            if node.inputs[slot].default_value != value:
                return True
        return False                


    def getFromNode(self, mat, node, socket):
        for link in mat.node_tree.links.values():
            if link.to_node == node and link.to_socket == socket:
                return (link.from_node, link.from_socket)
        return None,None    

                
    def comesFrom(self, node, mat, fromType):
        if fromType is None:
            return True                            
        for link in mat.node_tree.links.values():
            if link.to_node == node and link.from_node.type == fromType:
                return True
        return False                


class DAZ_OT_LaunchEditor(DazOperator, ChannelSetter, B.LaunchEditor, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "tweakMaterials")
        self.layout.separator()
        for item in self.slots:
            row = self.layout.row()
            row.label(text=item.name)
            if item.ncomps == 4:
                row.prop(item, "color", text="")
            elif item.ncomps == 1:
                row.prop(item, "number", text="")
            elif item.ncomps == 3:
                row.prop(item, "vector", text="")
            else:
                print("WAHT")


    def invoke(self, context, event):
        scn = context.scene
        self.slots.clear()
        ob = context.object
        for key in TweakableChannels.keys():
            value,ncomps = self.getChannel(ob, key)
            if ncomps == 0:
                continue            
            print("KK", key, value, ncomps)
            item = self.slots.add()
            item.name = key
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            
        wm = context.window_manager
        wm.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for item in self.slots:
                    self.setChannel(ob, item)


    def getChannel(self, ob, key):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[key]
        for mat in ob.data.materials:            
            if mat:
                if self.skipMaterial(mat):
                    continue
                elif mat.use_nodes:
                    return self.getChannelCycles(mat, nodeType, slot, ncomps, fromType)
                elif useAttr:
                    return self.getChannelInternal(mat, useAttr, factorAttr)
        return None,0
                            
                    
    def getChannelCycles(self, mat, nodeType, slot, ncomps, fromType):                                    
        for node in mat.node_tree.nodes.values():
            if node.type == nodeType:
                if not self.comesFrom(node, mat, fromType):
                    continue
                socket = node.inputs[slot]
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        return fromnode.inputs[1].default_value, ncomps
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "TEX_IMAGE":
                        return WHITE, 4
                else:
                    return socket.default_value, ncomps
        return None,0
        

    def getObjectSlot(self, ob, key):
        for item in ob.DazSlots:
            if item.name == key:
                return item
        item = ob.DazSlots.add()
        item.name = key
        item.new = True
        return item
   

    def setOriginal(self, socket, ncomps, ob, key):
        item = self.getObjectSlot(ob, key)
        if item.new:
            value = socket.default_value
            print("ORIG", key, value)
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            item.new = False


    def addMixRGB(self, fromsocket, tosocket, tree, item):
        if item.ncomps != 4:
            return
        mix = tree.nodes.new(type = "ShaderNodeMixRGB")
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value = item.color
        tree.links.new(fromsocket, mix.inputs[2])
        tree.links.new(mix.outputs[0], tosocket)
        return mix
                    

class DAZ_OT_ResetMaterial(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for item in list(ob.DazSlots):
                    self.setChannel(ob, item)
                    item.new = True
                ob.DazSlots.clear()

    def setOriginal(self, socket, ncomps, item, key):
        pass

    def skipMaterial(self, mat):
        return False

    def addMixRGB(self, fromsocket, tosocket, tree, item):
        pass

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    B.EditSlotGroup,
    DAZ_OT_LaunchEditor,
    DAZ_OT_ResetMaterial,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.DazSlots = CollectionProperty(type = B.EditSlotGroup)
    bpy.types.Object.DazSlots = CollectionProperty(type = B.EditSlotGroup)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
