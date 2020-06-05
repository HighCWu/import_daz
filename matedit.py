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
from .error import *
from .utils import *
from .material import WHITE, isWhite
from collections import OrderedDict

# ---------------------------------------------------------------------
#   material.py
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, # components, comes from)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump", None),
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1, None)),
    ("Bump Distance", ("BUMP", "Distance", None, None, 1, None)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1, None)),

    ("Diffuse", None),
    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", None, None, 4, None)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", None, None, 1, None)),

    ("Specular", None),
    ("Glossy Color", ("BSDF_GLOSSY", "Color", None, None, 4, None)),
    ("Glossy Roughness", ("BSDF_GLOSSY", "Roughness", None, None, 1, None)),

    ("Dual Lobe", None),
    ("Dual Lobe Weight", ("DAZ Dual Lobe", "Weight", None, None, 1, None)),
    ("Dual Lobe IOR", ("DAZ Dual Lobe", "IOR", None, None, 1, None)),
    ("Dual Lobe Roughness 1", ("DAZ Dual Lobe", "Roughness 1", None, None, 1, None)),
    ("Dual Lobe Roughness 2", ("DAZ Dual Lobe", "Roughness 2", None, None, 1, None)),
    ("Dual Lobe Fac", ("DAZ Dual Lobe", "Fac", None, None, 1, None)),

    ("Translucency", None),
    ("Translucency Color", ("BSDF_TRANSLUCENT", "Color", "use_map_translucency", "translucency_factor", 4, None)),
    ("Translucency Strength", ("MIX_SHADER", "Fac", "use_map_translucency", "translucency_factor", 1, "BSDF_TRANSLUCENT")),

    ("Subsurface", None),
    ("Subsurface Color", ("SUBSURFACE_SCATTERING", "Color", None, None, 4, None)),
    ("Subsurface Scale", ("SUBSURFACE_SCATTERING", "Scale", None, None, 1, None)),
    ("Subsurface Radius", ("SUBSURFACE_SCATTERING", "Radius", None, None, 3, None)),

    ("Principled", None),
    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", None, None, 4, None)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", None, None, 1, None)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", None, None, 3, None)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", None, None, 4, None)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", None, None, 1, None)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", None, None, 1, None)),
    ("Principled Specular Tint", ("BSDF_PRINCIPLED", "Specular Tint", None, None, 1, None)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", None, None, 1, None)),
    ("Principled Anisotropic", ("BSDF_PRINCIPLED", "Anisotropic", None, None, 1, None)),
    ("Principled Anisotropic Rotation", ("BSDF_PRINCIPLED", "Anisotropic Rotation", None, None, 1, None)),
    ("Principled Sheen", ("BSDF_PRINCIPLED", "Sheen", None, None, 1, None)),
    ("Principled Sheen Tint", ("BSDF_PRINCIPLED", "Sheen Tint", None, None, 1, None)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", None, None, 1, None)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", None, None, 1, None)),
    ("Principled IOR", ("BSDF_PRINCIPLED", "IOR", None, None, 1, None)),
    ("Principled Transmission", ("BSDF_PRINCIPLED", "Transmission", None, None, 1, None)),
    ("Principled Transmission Roughness", ("BSDF_PRINCIPLED", "Transmission Roughness", None, None, 1, None)),
    ("Principled Emission", ("BSDF_PRINCIPLED", "Emission", None, None, 4, None)),

    ("Emission", None),
    ("Emission Color", ("EMISSION", "Color", None, None, 4, None)),
    ("Emission Strength", ("EMISSION", "Strength", None, None, 1, None)),

    ("Volume", None),
    ("Volume Absorption Color", ("VOLUME_ABSORPTION", "Color", None, None, 4, None)),
    ("Volume Absorption Density", ("VOLUME_ABSORPTION", "Density", None, None, 1, None)),

    ("Volume Scatter Color", ("VOLUME_SCATTER", "Color", None, None, 4, None)),
    ("Volume Scatter Density", ("VOLUME_SCATTER", "Density", None, None, 1, None)),

])

# ---------------------------------------------------------------------
#   Mini material editor
# ---------------------------------------------------------------------

def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))

# ---------------------------------------------------------------------
#   Channel setter
# ---------------------------------------------------------------------

class ChannelSetter:
    def setChannelCycles(self, mat, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[item.name]
        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat, fromType):
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, mat, item.name)
                self.setSocket(socket, ncomps, item)
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        self.setSocket(fromnode.inputs[1], ncomps, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        self.setSocket(fromnode.inputs[0], 1, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY_ADD':
                        self.setSocket(fromnode.inputs[1], 1, item)
                    elif fromnode.type == "TEX_IMAGE":
                        self.multiplyTex(fromsocket, socket, mat.node_tree, item)


    def setSocket(self, socket, ncomps, item):
        if item.ncomps == 1:
            socket.default_value = self.getValue(item.number, ncomps)
        elif item.ncomps == 3:
            socket.default_value = self.getValue(item.vector, ncomps)
        elif item.ncomps == 4:
            socket.default_value = self.getValue(item.color, ncomps)


    def setChannelInternal(self, mat, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[item.name]
        if not useAttr:
            return
        for mtex in mat.texture_slots:
            if mtex and getattr(mtex, useAttr):
                value = getattr(mtex, factorAttr)
                setattr(mtex, factorAttr, self.factor*value)


    def addSlots(self, context):
        ob = context.object
        ob.DazSlots.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                continue
            value,ncomps = self.getChannel(ob, key)
            if ncomps == 0:
                continue
            item = ob.DazSlots.add()
            item.name = key
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)


    def getChannel(self, ob, key):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels[key]
        mat = ob.data.materials[ob.DazActiveMaterial]
        if mat.use_nodes:
            return self.getChannelCycles(mat, nodeType, slot, ncomps, fromType)
        elif useAttr:
            return self.getChannelInternal(mat, useAttr, factorAttr)
        return None,0


    def skipMaterial(self, mat, ob):
        item = ob.DazAffectedMaterials[mat.name]
        return (not item.active)


    def getAffectedMaterials(self, context):
        ob = context.object
        ob.DazAffectedMaterials.clear()
        for mat in ob.data.materials:
            item = ob.DazAffectedMaterials.add()
            item.name = mat.name
            item.active = self.isAffected(ob, mat)


    def getChannelCycles(self, mat, nodeType, slot, ncomps, fromType):
        from .cgroup import DualLobeGroup
        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat, fromType):
                socket = node.inputs[slot]
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        return fromnode.inputs[1].default_value, ncomps
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "TEX_IMAGE":
                        return WHITE, ncomps
                else:
                    return socket.default_value, ncomps
        return None,0


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


    def isAffected(self, ob, mat):
        if ob.data.DazMaterialSets:
            if ob.DazTweakMaterials in ob.data.DazMaterialSets.keys():
                items = ob.data.DazMaterialSets[ob.DazTweakMaterials]
                mname = mat.name.split(".",1)[0].split("-",1)[0]
                return (mname in items.names.keys())

        from .guess import getSkinMaterial
        if self.isRefractive(mat):
            return (ob.DazTweakMaterials in ["Refractive", "All"])
        mattype = getSkinMaterial(mat)
        if ob.DazTweakMaterials == "Skin":
            return (mattype == "Skin")
        elif ob.DazTweakMaterials == "Skin-Lips-Nails":
            return (mattype in ["Skin", "Red"])
        else:
            return (ob.DazTweakMaterials != "Refractive")


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


    def matchingNode(self, node, nodeType, mat, fromType):
        if node.type == nodeType:
            if fromType is None:
                return True
            for link in mat.node_tree.links.values():
                if link.to_node == node and link.from_node.type == fromType:
                    return True
            return False
        elif (node.type == "GROUP" and
            nodeType in bpy.data.node_groups.keys()):
            return (node.node_tree == bpy.data.node_groups[nodeType])
        return False

# ---------------------------------------------------------------------
#   Update button
# ---------------------------------------------------------------------

class DAZ_OT_ChangeTweakType(bpy.types.Operator, ChannelSetter):
    bl_idname = "daz.change_tweak_type"
    bl_label = "Change Material Selection"
    bl_description = "Change the selection of materials to tweak"

    def draw(self, context):
        ob = context.object
        self.layout.prop(ob, "DazTweakMaterials")
        self.layout.prop(ob, "DazActiveMaterial")

    def execute(self, context):
        self.addSlots(context)
        self.getAffectedMaterials(context)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

# ---------------------------------------------------------------------
#   Launch button
# ---------------------------------------------------------------------

class DAZ_OT_LaunchEditor(DazOperator, ChannelSetter, B.LaunchEditor, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        ob = context.object
        layout = self.layout
        affmats = list(ob.DazAffectedMaterials.items())
        while affmats:
            row = layout.row()
            for mname,item in affmats[0:3]:
                row.prop(item, "active", text="")
                row.label(text=mname)
            affmats = affmats[3:]
        layout.operator("daz.change_tweak_type")
        layout.label(text = "Active material: %s" % ob.DazActiveMaterial)

        layout.separator()
        showing = False
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                if self.shows[key].show:
                    layout.prop(self.shows[key], "show", icon="DOWNARROW_HLT", emboss=False, text=key)
                else:
                    layout.prop(self.shows[key], "show", icon="RIGHTARROW", emboss=False, text=key)
                showing = self.shows[key].show
            elif showing and key in ob.DazSlots.keys():
                item = ob.DazSlots[key]
                row = layout.row()
                if key[0:11] == "Principled ":
                    text = item.name[11:]
                else:
                    text = item.name
                row.label(text=text)
                if item.ncomps == 4:
                    row.prop(item, "color", text="")
                elif item.ncomps == 1:
                    row.prop(item, "number", text="")
                elif item.ncomps == 3:
                    row.prop(item, "vector", text="")
                else:
                    print("WAHT")


    def invoke(self, context, event):
        self.shows.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                item = self.shows.add()
                item.name = key
                item.show = False
                continue
        self.getAffectedMaterials(context)
        self.addSlots(context)
        wm = context.window_manager
        wm.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for item in ob.DazSlots:
                    self.setChannel(ob, item)


    def setChannel(self, ob, item):
        for mat in ob.data.materials:
            if mat:
                if self.skipMaterial(mat, ob):
                    continue
                elif mat.use_nodes:
                    self.setChannelCycles(mat, item)
                else:
                    self.setChannelInternal(mat, item)


    def getObjectSlot(self, mat, key):
        for item in mat.DazSlots:
            if item.name == key:
                return item
        item = mat.DazSlots.add()
        item.name = key
        item.new = True
        return item


    def setOriginal(self, socket, ncomps, mat, key):
        item = self.getObjectSlot(mat, key)
        if item.new:
            value = socket.default_value
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            item.new = False


    def multiplyTex(self, fromsocket, tosocket, tree, item):
        if item.ncomps == 4 and not isWhite(item.color):
            mix = tree.nodes.new(type = "ShaderNodeMixRGB")
            mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            mix.inputs[1].default_value = item.color
            tree.links.new(fromsocket, mix.inputs[2])
            tree.links.new(mix.outputs[0], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type = "ShaderNodeMath")
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.links.new(fromsocket, mult.inputs[1])
            tree.links.new(mult.outputs[0], tosocket)
            return mult


# ---------------------------------------------------------------------
#   Reset button
# ---------------------------------------------------------------------

class DAZ_OT_ResetMaterial(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                self.resetObject(ob)


    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                if mat.use_nodes:
                    for item in mat.DazSlots:
                        self.setChannelCycles(mat, item)
                        item.new = True
                    mat.DazSlots.clear()
                else:
                    for item in mat.DazSlots:
                        self.setChannelInternal(mat, item)
                        item.new = True
                    mat.DazSlots.clear()


    def setOriginal(self, socket, ncomps, item, key):
        pass

    def skipMaterial(self, mat, ob):
        return False

    def multiplyTex(self, fromsocket, tosocket, tree, item):
        pass


def getTweakMaterials(scn, context):
    ob = context.object
    if ob.data.DazMaterialSets:
        return [(key,key,key) for key in ob.data.DazMaterialSets.keys()]
    else:
        return [("Opaque", "Opaque", "Opaque"),
                ("Refractive", "Refractive", "Refractive"),
                ("All", "All", "All"),
                ("Skin", "Skin", "Skin"),
                ("Skin-Lips-Nails", "Skin-Lips-Nails", "Skin-Lips-Nails"),
                ]

def getActiveMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    B.DazActiveGroup,
    B.EditSlotGroup,
    B.ShowGroup,
    DAZ_OT_LaunchEditor,
    DAZ_OT_ChangeTweakType,
    DAZ_OT_ResetMaterial,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Material.DazSlots = CollectionProperty(type = B.EditSlotGroup)
    bpy.types.Object.DazSlots = CollectionProperty(type = B.EditSlotGroup)
    bpy.types.Object.DazAffectedMaterials = CollectionProperty(type = B.DazActiveGroup)

    bpy.types.Object.DazActiveMaterial = EnumProperty(
        items = getActiveMaterial,
        name = "Active Material",
        description = "Material actually being edited")

    bpy.types.Object.DazTweakMaterials = EnumProperty(
        items = getTweakMaterials,
        name = "Material Type",
        description = "Type of materials to tweak")


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
