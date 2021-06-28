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
from .material import WHITE, isWhite
from collections import OrderedDict
from .globvars import getMaterialEnums
from .fileutils import SingleFile, ImageFile

#-------------------------------------------------------------
#   Material selector
#-------------------------------------------------------------

def getMaterialSelector():
    global theMaterialSelector
    return theMaterialSelector


def setMaterialSelector(selector):
    global theMaterialSelector
    theMaterialSelector = selector


class DazMaterialGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


class MaterialSelector:
    umats : CollectionProperty(type = DazMaterialGroup)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.active_material)


    def draw(self, context):
        row = self.layout.row()
        row.operator("daz.select_all_materials")
        row.operator("daz.select_no_material")
        row = self.layout.row()
        row.operator("daz.select_skin_materials")
        row.operator("daz.select_skin_red_materials")
        umats = self.umats
        while umats:
            row = self.layout.row()
            row.prop(umats[0], "bool", text=umats[0].name)
            if len(umats) > 1:
                row.prop(umats[1], "bool", text=umats[1].name)
                umats = umats[2:]
            else:
                umats = []


    def setupMaterials(self, ob):
        from .guess import getSkinMaterial
        self.skinColor = WHITE
        for mat in ob.data.materials:
            if getSkinMaterial(mat) == "Skin":
                self.skinColor = mat.diffuse_color[0:3]
                break
        self.umats.clear()
        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isDefaultActive(mat)
        setMaterialSelector(self)


    def useMaterial(self, mat):
        if mat.name in self.umats.keys():
            item = self.umats[mat.name]
            return item.bool
        else:
            return False


    def selectAll(self, context):
        for item in self.umats.values():
            item.bool = True

    def selectNone(self, context):
        for item in self.umats.values():
            item.bool = False

    def selectSkin(self, context):
        ob = context.object
        for mat,item in zip(ob.data.materials, self.umats.values()):
            item.bool = (mat.diffuse_color[0:3] == self.skinColor)

    def selectSkinRed(self, context):
        ob = context.object
        for mat,item in zip(ob.data.materials, self.umats.values()):
            item.bool = self.isSkinRedMaterial(mat)

    def isSkinRedMaterial(self, mat):
        if mat.diffuse_color[0:3] == self.skinColor:
            return True
        from .guess import getSkinMaterial
        return (getSkinMaterial(mat) == "Red")

#-------------------------------------------------------------
#   Select all and none
#-------------------------------------------------------------

class DAZ_OT_SelectAllMaterials(bpy.types.Operator):
    bl_idname = "daz.select_all_materials"
    bl_label = "All"
    bl_description = "Select all materials"

    def execute(self, context):
        getMaterialSelector().selectAll(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectSkinMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_materials"
    bl_label = "Skin"
    bl_description = "Select skin materials"

    def execute(self, context):
        getMaterialSelector().selectSkin(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectSkinRedMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_red_materials"
    bl_label = "Skin-Lips-Nails"
    bl_description = "Select all skin or red materials"

    def execute(self, context):
        getMaterialSelector().selectSkinRed(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectNoMaterial(bpy.types.Operator):
    bl_idname = "daz.select_no_material"
    bl_label = "None"
    bl_description = "Select no material"

    def execute(self, context):
        getMaterialSelector().selectNone(context)
        return {'PASS_THROUGH'}

# ---------------------------------------------------------------------
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, # components, comes from)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump And Normal", None),
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1, None)),
    ("Bump Distance", ("BUMP", "Distance", 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1, None)),

    ("Diffuse", None),
    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", 4)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", 1)),

    ("Glossy", None),
    ("Glossy Color", ("DAZ Glossy", "Color", 4)),
    ("Glossy Roughness", ("DAZ Glossy", "Roughness", 1)),
    ("Glossy Strength", ("DAZ Glossy", "Fac", 1)),

    ("Fresnel", None),
    ("Fresnel IOR", ("DAZ Fresnel", "IOR", 1)),
    ("Fresnel Roughness", ("DAZ Fresnel", "Roughness", 1)),

    ("Dual Lobe Uber", None),
    ("Dual Lobe Uber Weight", ("DAZ Dual Lobe Uber", "Weight", 1)),
    ("Dual Lobe Uber IOR", ("DAZ Dual Lobe Uber", "IOR", 1)),
    ("Dual Lobe Uber Roughness 1", ("DAZ Dual Lobe Uber", "Roughness 1", 1)),
    ("Dual Lobe Uber Roughness 2", ("DAZ Dual Lobe Uber", "Roughness 2", 1)),
    ("Dual Lobe Uber Strength", ("DAZ Dual Lobe Uber", "Fac", 1)),

    ("Dual Lobe PBR", None),
    ("Dual Lobe PBR Weight", ("DAZ Dual Lobe PBR", "Weight", 1)),
    ("Dual Lobe PBR IOR", ("DAZ Dual Lobe PBR", "IOR", 1)),
    ("Dual Lobe PBR Roughness 1", ("DAZ Dual Lobe PBR", "Roughness 1", 1)),
    ("Dual Lobe PBR Roughness 2", ("DAZ Dual Lobe PBR", "Roughness 2", 1)),
    ("Dual Lobe PBR Strength", ("DAZ Dual Lobe PBR", "Fac", 1)),

    ("Translucency", None),
    ("Translucency Color", ("DAZ Translucent", "Translucent Color", 4)),
    ("SSS Color", ("DAZ Translucent", "SSS Color", 4)),
    ("Translucency Strength", ("DAZ Translucent", "Fac", 1)),
    ("Translucency Scale", ("DAZ Translucent", "Scale", 1)),
    ("Translucency Radius", ("DAZ Translucent", "Radius", 3)),
    ("Cycles Mix Factor", ("DAZ Translucent", "Cycles Mix Factor", 1)),
    ("Eevee Mix Factor", ("DAZ Translucent", "Eevee Mix Factor", 1)),

    ("Principled", None),
    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", 4)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", 1)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", 3)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", 4)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", 1)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", 1)),
    ("Principled Specular Tint", ("BSDF_PRINCIPLED", "Specular Tint", 1)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", 1)),
    ("Principled Anisotropic", ("BSDF_PRINCIPLED", "Anisotropic", 1)),
    ("Principled Anisotropic Rotation", ("BSDF_PRINCIPLED", "Anisotropic Rotation", 1)),
    ("Principled Sheen", ("BSDF_PRINCIPLED", "Sheen", 1)),
    ("Principled Sheen Tint", ("BSDF_PRINCIPLED", "Sheen Tint", 1)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", 1)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", 1)),
    ("Principled IOR", ("BSDF_PRINCIPLED", "IOR", 1)),
    ("Principled Transmission", ("BSDF_PRINCIPLED", "Transmission", 1)),
    ("Principled Transmission Roughness", ("BSDF_PRINCIPLED", "Transmission Roughness", 1)),
    ("Principled Emission", ("BSDF_PRINCIPLED", "Emission", 4)),

    ("Top Coat", None),
    ("Top Coat Color", ("DAZ Top Coat", "Color", 4)),
    ("Top Coat Roughness", ("DAZ Top Coat", "Roughness", 1)),
    ("Top Coat Bump", ("DAZ Top Coat", "Bump", 1)),
    ("Top Coat Distance", ("DAZ Top Coat", "Distance", 1)),

    ("Overlay", None),
    ("Overlay Color", ("DAZ Overlay", "Color", 4)),
    ("Overlay Roughness", ("DAZ Overlay", "Roughness", 1)),
    ("Overlay Strength", ("DAZ Overlay", "Fac", 1)),

    ("Refraction", None),
    ("Refraction Color", ("DAZ Refraction", "Refraction Color", 4)),
    ("Refraction Roughness", ("DAZ Refraction", "Refraction Roughness", 1)),
    ("Refraction IOR", ("DAZ Refraction", "Refraction IOR", 1)),
    ("Ref Fresnel IOR", ("DAZ Refraction", "Fresnel IOR", 1)),
    ("Ref Glossy Color", ("DAZ Refraction", "Glossy Color", 4)),
    ("Ref Glossy Roughness", ("DAZ Refraction", "Glossy Roughness", 1)),
    ("Refraction Strength", ("DAZ Refraction", "Fac", 1)),

    ("Transparent", None),
    ("Transparent Color", ("DAZ Transparent", "Color", 4)),
    ("Transparent Strength", ("DAZ Transparent", "Fac", 1)),

    ("Emission", None),
    ("Emission Color", ("DAZ Emission", "Color", 4)),
    ("Emission Strength", ("DAZ Emission", "Strength", 1)),
    ("Emission Strength", ("DAZ Emission", "Fac", 1)),

    ("Volume", None),
    ("Volume Absorption Color", ("DAZ Volume", "Absorbtion Color", 4)),
    ("Volume Absorption Density", ("DAZ Volume", "Absorbtion Density", 1)),
    ("Volume Scatter Color", ("DAZ Volume", "Scatter Color", 4)),
    ("Volume Scatter Density", ("DAZ Volume", "Scatter Density", 1)),
    ("Volume Scatter Anisotropy", ("DAZ Volume", "Scatter Anisotropy", 1)),

])

# ---------------------------------------------------------------------
#   Mini material editor
# ---------------------------------------------------------------------

class EditSlotGroup(bpy.types.PropertyGroup):
    ncomps : IntProperty(default = 0)

    color : FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (1,1,1,1)
    )

    vector : FloatVectorProperty(
        name = "Vector",
        size = 3,
        min = 0.0,
        max = 1.0,
        default = (0,0,0)
    )

    number : FloatProperty(default = 0.0, precision=4)
    new : BoolProperty()


class ShowGroup(bpy.types.PropertyGroup):
    show : BoolProperty(default = False)


class LaunchEditor:
    shows : CollectionProperty(type = ShowGroup)


def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))

# ---------------------------------------------------------------------
#   Channel setter
# ---------------------------------------------------------------------

def getTweakableChannel(cname):
    data = TweakableChannels[cname]
    if len(data) == 6:
        return data
    else:
        nodeType, slot, ncomps = data
        return (nodeType, slot, None, None, ncomps, None)


class ChannelSetter:
    def setChannelCycles(self, mat, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = getTweakableChannel(item.name)

        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat, fromType):
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, mat, item.name)
                self.setSocket(socket, ncomps, item)
                fromnode,fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        if ncomps == 1:
                            ncomps = 4
                            num = item.number
                            item.color = (num,num,num,1)
                        self.setSocket(fromnode.inputs[1], ncomps, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        self.setSocket(fromnode.inputs[0], 1, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY_ADD':
                        self.setSocket(fromnode.inputs[1], 1, item)
                    elif fromnode.type == "TEX_IMAGE":
                        self.multiplyTex(node, fromsocket, socket, mat.node_tree, item)


    def setSocket(self, socket, ncomps, item):
        if item.ncomps == 1:
            socket.default_value = self.getValue(item.number, ncomps)
        elif item.ncomps == 3:
            socket.default_value = self.getValue(item.vector, ncomps)
        elif item.ncomps == 4:
            socket.default_value = self.getValue(item.color, ncomps)


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
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = getTweakableChannel(key)
        mat = ob.active_material
        if mat.use_nodes:
            return self.getChannelCycles(mat, nodeType, slot, ncomps, fromType)
        else:
            return None,0


    def getChannelCycles(self, mat, nodeType, slot, ncomps, fromType):
        for node in mat.node_tree.nodes.values():
            if (self.matchingNode(node, nodeType, mat, fromType) and
                slot in node.inputs.keys()):
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
#   Launch button
# ---------------------------------------------------------------------

class DAZ_OT_LaunchEditor(DazPropsOperator, MaterialSelector, ChannelSetter, LaunchEditor, IsMesh):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}

    def draw(self, context):
        MaterialSelector.draw(self, context)
        ob = context.object
        self.layout.label(text="Active Material: %s" % ob.active_material.name)
        self.layout.separator()
        showing = False
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                if self.shows[key].show:
                    self.layout.prop(self.shows[key], "show", icon="DOWNARROW_HLT", emboss=False, text=key)
                else:
                    self.layout.prop(self.shows[key], "show", icon="RIGHTARROW", emboss=False, text=key)
                showing = self.shows[key].show
            elif showing and key in ob.DazSlots.keys():
                item = ob.DazSlots[key]
                row = self.layout.row()
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
        self.layout.operator("daz.update_materials")


    def invoke(self, context, event):
        global theMaterialEditor
        theMaterialEditor = self
        ob = context.object
        self.setupMaterials(ob)
        self.shows.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                item = self.shows.add()
                item.name = key
                item.show = False
                continue
        self.addSlots(context)
        wm = context.window_manager
        return wm.invoke_popup(self, width=300)


    def isDefaultActive(self, mat):
        return (mat.diffuse_color[0:3] == self.skinColor)


    def run(self, context):
        for ob in getSelectedMeshes(context):
            for item in ob.DazSlots:
                self.setChannel(ob, item)


    def setChannel(self, ob, item):
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.setChannelCycles(mat, item)


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


    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        from .cycles import XSIZE, YSIZE
        x,y = node.location
        if item.ncomps == 4 and not isWhite(item.color):
            mix = tree.nodes.new(type = "ShaderNodeMixRGB")
            mix.location = (x-XSIZE,y-YSIZE)
            mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            mix.inputs[1].default_value = item.color
            tree.links.new(fromsocket, mix.inputs[2])
            tree.links.new(mix.outputs[0], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type = "ShaderNodeMath")
            mult.location = (x-XSIZE,y-YSIZE)
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.links.new(fromsocket, mult.inputs[1])
            tree.links.new(mult.outputs[0], tosocket)
            return mult


class DAZ_OT_UpdateMaterials(bpy.types.Operator):
    bl_idname = "daz.update_materials"
    bl_label = "Update Materials"
    bl_description = "Update Materials"

    def execute(self, context):
        global theMaterialEditor
        theMaterialEditor.run(context)
        return {'PASS_THROUGH'}

# ---------------------------------------------------------------------
#   Make Decal
# ---------------------------------------------------------------------

class DAZ_OT_MakeDecal(DazOperator, ImageFile, SingleFile, LaunchEditor, IsMesh):
    bl_idname = "daz.make_decal"
    bl_label = "Make Decal"
    bl_description = "Add a decal to the active material"
    bl_options = {'UNDO'}

    channels = {
        "Diffuse Color" : ("DIFFUSE", "Color", "Diffuse"),
        "Glossy Color" : ("DAZ Glossy", "Color", "Glossy"),
        "Translucency Color" : ("DAZ Translucent", "Color", "Translucency"),
        "Subsurface Color" : ("DAZ SSS", "Color", "SSS"),
        "Principled Base Color" : ("BSDF_PRINCIPLED", "Base Color", "Base"),
        "Principled Subsurface Color" : ("BSDF_PRINCIPLED", "Subsurface Color", "SSS"),
        "Bump" : ("BUMP", "Height", "Bump"),
    }

    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text="Material: %s" % mat.name)
        for item in self.shows:
            row = self.layout.row()
            row.prop(item, "show", text="")
            row.label(text=item.name)


    def invoke(self, context, event):
        if len(self.shows) == 0:
            for key in self.channels.keys():
                item = self.shows.add()
                item.name = key
                item.show = False
        return SingleFile.invoke(self, context, event)


    def run(self, context):
        from .cgroup import DecalGroup
        from .cycles import findTree

        img = bpy.data.images.load(self.filepath)
        if img is None:
            raise DazError("Unable to load file %s" % self.filepath)
        if hasattr(img, "colorspace_settings"):
            img.colorspace_settings.name = "Non-Color"
            img.colorspace_settings.name = "sRGB"

        fname = os.path.splitext(os.path.basename(self.filepath))[0]
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        tree = findTree(mat)
        empty = bpy.data.objects.new(fname, None)
        coll = getCollection(ob)
        coll.objects.link(empty)

        for item in self.shows:
            if item.show:
                nodeType,slot,cname = self.channels[item.name]
                fromSocket, toSocket = getFromToSockets(tree, nodeType, slot)
                if toSocket is None:
                    print("Channel %s not found" % item.name)
                    continue
                nname = fname + "_" + cname
                node = tree.addGroup(DecalGroup, nname, col=3, args=[empty, img], force=True)
                node.inputs["Influence"].default_value = 1.0
                if fromSocket:
                    tree.links.new(fromSocket, node.inputs["Color"])
                    tree.links.new(node.outputs["Combined"], toSocket)
                else:
                    tree.links.new(node.outputs["Color"], toSocket)

# ---------------------------------------------------------------------
#   Utilities
# ---------------------------------------------------------------------

def getFromToSockets(tree, nodeType, slot):
    from .cycles import findNodes
    for link in tree.links.values():
        if link.to_node and link.to_node.type == nodeType:
            if link.to_socket == link.to_node.inputs[slot]:
                return link.from_socket, link.to_socket
    nodes = findNodes(tree, nodeType)
    if nodes:
        return None, nodes[0].inputs[slot]
    return None, None

# ---------------------------------------------------------------------
#   Reset button
# ---------------------------------------------------------------------

class DAZ_OT_ResetMaterial(DazOperator, ChannelSetter, IsMesh):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            self.resetObject(ob)


    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                for item in mat.DazSlots:
                    self.setChannelCycles(mat, item)
                    item.new = True
                mat.DazSlots.clear()


    def setOriginal(self, socket, ncomps, item, key):
        pass

    def useMaterial(self, mat):
        return True

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        pass


def getTweakMaterials(scn, context):
    ob = context.object
    default = [("Opaque", "Opaque", "Opaque"),
               ("Refractive", "Refractive", "Refractive"),
               ("All", "All", "All"),
               ("None", "None", "None")
              ]
    if ob.data.DazMaterialSets:
        return default + [(key,key,key) for key in ob.data.DazMaterialSets.keys()]
    else:
        return default + [
                ("Skin", "Skin", "Skin"),
                ("Skin-Lips-Nails", "Skin-Lips-Nails", "Skin-Lips-Nails"),
                ]

# ---------------------------------------------------------------------
#   Set Shell Visibility
# ---------------------------------------------------------------------

class DAZ_OT_SetShellVisibility(DazPropsOperator, IsMesh):
    bl_idname = "daz.set_shell_visibility"
    bl_label = "Set Shell Visibility"
    bl_description = "Control the visility of geometry shells"
    bl_options = {'UNDO'}

    def draw(self, context):
        for item in context.scene.DazFloats:
            self.layout.prop(item, "f", text=item.name)

    def run(self, context):
        for item in context.scene.DazFloats:
            for node in self.shells[item.name]:
                node.inputs["Influence"].default_value = item.f

    def invoke(self, context, event):
        self.shells = {}
        scn = context.scene
        scn.DazFloats.clear()
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if (node.type == 'GROUP' and
                            "Influence" in node.inputs.keys()):
                            key = node.label
                            if key not in self.shells.keys():
                               self.shells[key] = []
                               item = scn.DazFloats.add()
                               item.name = key
                               item.f = node.inputs["Influence"].default_value
                            self.shells[key].append(node)
        return DazPropsOperator.invoke(self, context, event)

# ---------------------------------------------------------------------
#   Remove shells from materials
# ---------------------------------------------------------------------

from .morphing import Selector

class ShellRemover:
    def getShells(self, context):
        ob = context.object
        self.shells = {}
        for mat in ob.data.materials:
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP':
                        self.addShell(mat, node, node.node_tree)


    def addShell(self, mat, shell, tree):
        for node in tree.nodes:
            if node.name == "Shell Influence":
                data = (mat,shell)
                if tree.name in self.shells.keys():
                    struct = self.shells[tree.name]
                    if mat.name in struct.keys():
                        struct[mat.name].append(data)
                    else:
                        struct[mat.name] = [data]
                else:
                    self.shells[tree.name] = {mat.name : [data]}
                return


    def deleteNodes(self, mat, shell):
        print("Delete shell '%s' from material '%s'" % (shell.name, mat.name))
        linkFrom = {}
        linkTo = {}
        tree = mat.node_tree
        for link in tree.links:
            if link.to_node == shell:
                linkFrom[link.to_socket.name] = link.from_socket
            if link.from_node == shell:
                linkTo[link.from_socket.name] = link.to_socket
        for key in linkFrom.keys():
            if key in linkTo.keys():
                tree.links.new(linkFrom[key], linkTo[key])
        tree.nodes.remove(shell)


class DAZ_OT_RemoveShells(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.remove_shells"
    bl_label = "Remove Shells"
    bl_description = "Remove selected shells from active object"
    bl_options = {'UNDO'}

    columnWidth = 350

    def run(self, context):
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat,node in data:
                    self.deleteNodes(mat, node)


    def invoke(self, context, event):
        self.getShells(context)
        self.selection.clear()
        for name,nodes in self.shells.items():
                item = self.selection.add()
                item.name = name
                item.text = name
                item.select = False
        return self.invokeDialog(context)


class DAZ_OT_ReplaceShells(DazPropsOperator, ShellRemover, IsMesh):
    bl_idname = "daz.replace_shells"
    bl_label = "Replace Shells"
    bl_description = "Display shell node groups so they can be displaced."
    bl_options = {'UNDO'}

    dialogWidth = 800

    def draw(self, context):
        rows = []
        n = 0
        for tname,struct in self.shells.items():
            for mname,data in struct.items():
                for mat,node in data:
                    rows.append((node.name, n, node))
                    n += 1
        rows.sort()
        for nname,n,node in rows:
            row = self.layout.row()
            row.label(text=nname)
            row.prop(node, "node_tree")


    def run(self, context):
        pass


    def invoke(self, context, event):
        self.getShells(context)
        return DazPropsOperator.invoke(self, context, event)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazMaterialGroup,
    EditSlotGroup,
    ShowGroup,
    DAZ_OT_SelectAllMaterials,
    DAZ_OT_SelectNoMaterial,
    DAZ_OT_SelectSkinMaterials,
    DAZ_OT_SelectSkinRedMaterials,
    DAZ_OT_LaunchEditor,
    DAZ_OT_UpdateMaterials,
    DAZ_OT_ResetMaterial,
    DAZ_OT_MakeDecal,
    DAZ_OT_SetShellVisibility,
    DAZ_OT_RemoveShells,
    DAZ_OT_ReplaceShells,
]

def register():
    from .propgroups import DazFloatGroup
    from .morphing import DazActiveGroup

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Material.DazSlots = CollectionProperty(type = EditSlotGroup)
    bpy.types.Object.DazSlots = CollectionProperty(type = EditSlotGroup)
    bpy.types.Scene.DazFloats = CollectionProperty(type = DazFloatGroup)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
