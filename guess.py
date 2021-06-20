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
from random import random
from .utils import *
from .error import *

SkinMaterials = {
    "eyelash" : ("Black", ),
    "eyelashes" : ("Black", ),
    "eyemoisture" : ("Invis", ),
    "lacrimal" : ("Invis", ),
    "lacrimals" : ("Invis", ),
    "cornea" : ("Invis", ),
    "tear" : ("Invis", ),
    "eyereflection" : ("Invis", ),

    "fingernail" : ("Red", ),
    "fingernails" : ("Red", ),
    "toenail" : ("Red", ),
    "toenails" : ("Red", ),
    "lip" : ("Red", ),
    "lips" : ("Red", ),
    "mouth" : ("Red", ),
    "tongue" : ("Red", ),
    "innermouth" : ("Red", ),
    "gums" : ("Red", ),
    "teeth" : ("Teeth", ),
    "pupil" : ("Black", ),
    "pupils" : ("Black", ),
    "sclera" : ("White", ),
    "iris" : ("Blue", ),
    "irises" : ("Blue", ),

    "skinface" : ("Skin", ),
    "face" : ("Skin", ),
    "nostril" : ("Skin", ),
    "nostrils" : ("Skin", ),
    "skinhead" : ("Skin", ),
    "eyebrow" : ("Skin", ),
    "head" : ("Skin", ),
    "ears" : ("Skin", ),
    "skinleg" : ("Skin", ),
    "legs" : ("Skin", ),
    "skintorso" : ("Skin", ),
    "torso" : ("Skin", ),
    "body" : ("Skin", ),
    "eyesocket" : ("Skin", ),
    "skinarm" : ("Skin", ),
    "arms" : ("Skin", ),
    "skinneck" : ("Skin", ),
    "neck" : ("Skin", ),
    "nipple" : ("Skin", ),
    "nipples" : ("Skin", ),
    "skinforearm" : ("Skin", ),
    "forearms" : ("Skin", ),
    "skinfoot" : ("Skin", ),
    "feet" : ("Skin", ),
    "skinhip" : ("Skin", ),
    "hips" : ("Skin", ),
    "shoulders" : ("Skin", ),
    "skinhand" : ("Skin", ),
    "hands" : ("Skin", ),

    "genitalia" : ("Skin", ),
    "labia" : ("Skin", ),
    "anus" : ("Skin", ),
    "vagina" : ("Skin", ),
    "rectum" : ("Skin", ),
    "gp_torso_back" : ("Skin", ),
}

def getSkinMaterial(mat):
    mname = mat.name.lower().split("-")[0].split(".")[0].split(" ")[0].split("&")[0]
    if mname in SkinMaterials.keys():
        return SkinMaterials[mname][0]
    mname2 = mname.rsplit("_", 2)[-1]
    if mname2 in SkinMaterials.keys():
        return SkinMaterials[mname2][0]
    return None


def setDiffuse(mat, color):
    mat.diffuse_color[0:3] = color[0:3]


def guessMaterialColor(mat, choose, enforce, default):
    from random import random
    if (mat is None or
        not hasDiffuseTexture(mat, enforce)):
        return

    elif choose == 'RANDOM':
        color = (random(), random(), random(), 1)
        setDiffuse(mat, color)

    elif choose == 'GUESS':
        color = getSkinMaterial(mat)
        if mat.diffuse_color[3] < 1.0:
            pass
        elif color is not None:
            if color == "Skin":
                setDiffuse(mat, LS.skinColor)
            elif color == "Red":
                setDiffuse(mat, (1,0,0,1))
            elif color == "Blue":
                setDiffuse(mat, (0,0,1,1))
            elif color == "Teeth":
                setDiffuse(mat, (1,1,1,1))
            elif color == "White":
                setDiffuse(mat, (1,1,1,1))
            elif color == "Black":
                setDiffuse(mat, (0,0,0,1))
            elif color == "Invis":
                setDiffuse(mat, (0.5,0.5,0.5,0))
        else:
            setDiffuse(mat, default)


def hasDiffuseTexture(mat, enforce):
    from .material import isWhite
    if mat.node_tree:
        color = (1,1,1,1)
        node = None
        for node1 in mat.node_tree.nodes.values():
            if node1.type == "BSDF_DIFFUSE":
                node = node1
                name = "Color"
            elif node1.type == "BSDF_PRINCIPLED":
                node = node1
                name = "Base Color"
            elif node1.type in ["HAIR_INFO", "BSDF_HAIR", "BSDF_HAIR_PRINCIPLED"]:
                return False
        if node is None:
            return True
        color = node.inputs[name].default_value
        for link in mat.node_tree.links:
            if (link.to_node == node and
                link.to_socket.name == name):
                return True
        setDiffuse(mat, color)
        return False
    else:
        if not isWhite(mat.diffuse_color) and not enforce:
            return False
        for mtex in mat.texture_slots:
            if mtex and mtex.use_map_color_diffuse:
                return True
        return False

#-------------------------------------------------------------
#   Change colors
#-------------------------------------------------------------

class ColorProp:
    color : FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.1, 0.1, 0.5, 1)
    )

    def draw(self, context):
        self.layout.prop(self, "color")


class DAZ_OT_ChangeColors(DazPropsOperator, ColorProp, IsMesh):
    bl_idname = "daz.change_colors"
    bl_label = "Change Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                setDiffuse(mat, self.color)


class DAZ_OT_ChangeSkinColor(DazPropsOperator, ColorProp, IsMesh):
    bl_idname = "daz.change_skin_color"
    bl_label = "Change Skin Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    def run(self, context):
        LS.skinColor = self.color
        LS.clothesColor = self.color
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                guessMaterialColor(mat, 'GUESS', True, self.color)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangeColors,
    DAZ_OT_ChangeSkinColor,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


