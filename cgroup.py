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

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE
from .utils import LS, GS
from .error import reportError

# ---------------------------------------------------------------------
#   CyclesGroup
# ---------------------------------------------------------------------

class MaterialGroup:
    def __init__(self):
        self.insockets = []
        self.outsockets = []


    def create(self, node, name, parent, ncols):
        self.group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        node.name = name
        node.node_tree = self.group
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode("NodeGroupInput", 0)
        self.outputs = self.addNode("NodeGroupOutput", ncols)
        self.parent = parent
        self.ncols = ncols


    def checkSockets(self, tree):
        for socket in self.insockets:
            if socket not in tree.inputs.keys():
                print("Missing insocket: %s" % socket)
                return False
        for socket in self.outsockets:
            if socket not in tree.outputs.keys():
                print("Missing outsocket: %s" % socket)
                return False
        return True


class CyclesGroup(MaterialGroup, CyclesTree):
    def create(self, node, name, parent, ncols):
        CyclesTree.__init__(self, parent.material)
        MaterialGroup.create(self, node, name, parent, ncols)

    def __repr__(self):
        return ("<NodeGroup %s>" % self.group)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(MaterialGroup):

    def __init__(self, push):
        MaterialGroup.__init__(self)
        self.push = push
        self.insockets += ["Cycles", "Eevee", "Displacement", "UV"]
        self.outsockets += ["Cycles", "Eevee", "Displacement"]


    def create(self, node, name, parent):
        MaterialGroup.create(self, node, name, parent, 8)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketVector", "Displacement")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketVector", "Displacement")


    def addNodes(self, shell):
        shell.rna = self.parent.material.rna
        self.material = shell
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer()
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        mult = self.addMult("Shell Influence", 6, 1.0, alpha, tex)
        self.addOutput(alpha, mult, self.getCyclesSocket(), "Cycles")
        self.addOutput(alpha, mult, self.getEeveeSocket(), "Eevee")
        if self.push > 0:
            push = self.push * LS.scale
            disp = self.addMult("Displacement", 6, push, alpha, tex)
            add = self.addNode("ShaderNodeMath", 7)
            self.links.new(disp.outputs[0], add.inputs[0])
            self.links.new(self.inputs.outputs["Displacement"], add.inputs[1])
            self.links.new(add.outputs[0], self.outputs.inputs["Displacement"])
        else:
            self.links.new(self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])


    def addMult(self, name, col, value, alpha, tex):
        mult = self.addNode("ShaderNodeMath", col)
        mult.name = mult.label = name
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        mult.inputs[1].default_value = alpha
        if tex:
            self.links.new(tex.outputs[0], mult.inputs[1])
        return mult



    def addOutput(self, alpha, tex, socket, slot):
        mix = self.addNode("ShaderNodeMixShader", 7)
        mix.inputs[0].default_value = alpha
        if tex:
            self.links.new(tex.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(socket, mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class ShellCyclesGroup(ShellGroup, CyclesTree):
    def create(self, node, shell, parent):
        CyclesTree.__init__(self, parent.material)
        ShellGroup.create(self, node, shell, parent)


class ShellPbrGroup(ShellGroup, PbrTree):
    def create(self, node, shell, parent):
        PbrTree.__init__(self, parent.material)
        ShellGroup.create(self, node, shell, parent)


# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class FresnelGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["IOR", "Roughness", "Normal"]
        self.outsockets += ["Fac"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketFloat", "Fac")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 0)

        divide = self.addNode("ShaderNodeMath", 1)
        divide.operation = 'DIVIDE'
        divide.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["IOR"], divide.inputs[1])

        bump = self.addNode("ShaderNodeBump", 1)
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.links.new(self.inputs.outputs["IOR"], mix1.inputs[1])
        self.links.new(divide.outputs["Value"], mix1.inputs[2])

        mix2 = self.addNode("ShaderNodeMixRGB", 2)
        self.links.new(self.inputs.outputs["Roughness"], mix2.inputs["Fac"])
        self.links.new(bump.outputs[0], mix2.inputs[1])
        self.links.new(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel = self.addNode("ShaderNodeFresnel", 3)
        self.links.new(mix1.outputs[0], fresnel.inputs["IOR"])
        self.links.new(mix2.outputs[0], fresnel.inputs["Normal"])
        self.links.new(fresnel.outputs["Fac"], self.outputs.inputs["Fac"])

# ---------------------------------------------------------------------
#   Mix Group. Mixes Cycles and Eevee
# ---------------------------------------------------------------------

class MixGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Fac", "Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.mix1 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix1.label = "Cycles"
        self.mix2 = self.addNode("ShaderNodeMixShader", self.ncols-1)
        self.mix2.label = "Eevee"
        self.links.new(self.inputs.outputs["Fac"], self.mix1.inputs[0])
        self.links.new(self.inputs.outputs["Fac"], self.mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[1])
        self.links.new(self.mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.mix2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Add Group. Adds to Cycles and Eevee
# ---------------------------------------------------------------------

class AddGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent, ncols):
        CyclesGroup.create(self, node, name, parent, ncols)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        self.add1 = self.addNode("ShaderNodeAddShader", 2)
        self.add2 = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(self.inputs.outputs["Cycles"], self.add1.inputs[0])
        self.links.new(self.inputs.outputs["Eevee"], self.add2.inputs[0])
        self.links.new(self.add1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(self.add2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Emission Group
# ---------------------------------------------------------------------

class EmissionGroup(AddGroup):

    def __init__(self):
        AddGroup.__init__(self)
        self.insockets += ["Color", "Strength"]


    def create(self, node, name, parent):
        AddGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Strength")


    def addNodes(self, args=None):
        AddGroup.addNodes(self, args)
        node = self.addNode("ShaderNodeEmission", 1)
        self.links.new(self.inputs.outputs["Color"], node.inputs["Color"])
        self.links.new(self.inputs.outputs["Strength"], node.inputs["Strength"])
        self.links.new(node.outputs[0], self.add1.inputs[1])
        self.links.new(node.outputs[0], self.add2.inputs[1])


class OneSidedGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Cycles", "Eevee"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")


    def addNodes(self, args=None):
        geo = self.addNode("ShaderNodeNewGeometry", 1)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        mix1 = self.addNode("ShaderNodeMixShader", 2)
        mix2 = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(geo.outputs["Backfacing"], mix1.inputs[0])
        self.links.new(geo.outputs["Backfacing"], mix2.inputs[0])
        self.links.new(self.inputs.outputs["Cycles"], mix1.inputs[1])
        self.links.new(self.inputs.outputs["Eevee"], mix2.inputs[1])
        self.links.new(trans.outputs[0], mix1.inputs[2])
        self.links.new(trans.outputs[0], mix2.inputs[2])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.links.new(mix1.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Diffuse Group
# ---------------------------------------------------------------------

class DiffuseGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        diffuse = self.addNode("ShaderNodeBsdfDiffuse", 1)
        self.links.new(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.links.new(diffuse.outputs[0], self.mix1.inputs[2])
        self.links.new(diffuse.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Glossy Group
# ---------------------------------------------------------------------

class GlossyGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        self.links.new(glossy.outputs[0], self.mix1.inputs[2])
        self.links.new(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Top Coat Group
# ---------------------------------------------------------------------

class TopCoatGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Roughness", "Normal", "Bump"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.inputs.new("NodeSocketFloat", "Bump")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.links.new(glossy.outputs[0], self.mix1.inputs[2])
        self.links.new(glossy.outputs[0], self.mix2.inputs[2])

        mult = self.addNode("ShaderNodeVectorMath", 1)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Normal"], mult.inputs[0])
        self.links.new(self.inputs.outputs["Bump"], mult.inputs[1])
        self.links.new(mult.outputs[0], glossy.inputs["Normal"])

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------

class RefractionGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += [
            "Thin Wall",
            "Refraction Color", "Refraction Roughness", "Refraction IOR",
            "Glossy Color", "Glossy Roughness", "Fresnel IOR", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketFloat", "Thin Wall")
        self.group.inputs.new("NodeSocketColor", "Refraction Color")
        self.group.inputs.new("NodeSocketFloat", "Refraction Roughness")
        self.group.inputs.new("NodeSocketFloat", "Refraction IOR")
        self.group.inputs.new("NodeSocketFloat", "Fresnel IOR")
        self.group.inputs.new("NodeSocketColor", "Glossy Color")
        self.group.inputs.new("NodeSocketFloat", "Glossy Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        refr = self.addNode("ShaderNodeBsdfRefraction", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], refr.inputs["Color"])
        self.links.new(self.inputs.outputs["Refraction Roughness"], refr.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Refraction IOR"], refr.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refr.inputs["Normal"])

        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Refraction Color"], trans.inputs["Color"])

        thin = self.addNode("ShaderNodeMixShader", 2)
        thin.label = "Thin Wall"
        thin.inputs["Fac"].default_value = GS.thinWall
        self.links.new(self.inputs.outputs["Thin Wall"], thin.inputs["Fac"])
        self.links.new(refr.outputs[0], thin.inputs[1])
        self.links.new(trans.outputs[0], thin.inputs[2])

        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 2)
        self.links.new(self.inputs.outputs["Fresnel IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        glossy = self.addNode("ShaderNodeBsdfGlossy", 2)
        self.links.new(self.inputs.outputs["Glossy Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs["Glossy Roughness"], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(thin.outputs[0], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])

        self.links.new(mix.outputs[0], self.mix1.inputs[2])
        self.links.new(mix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Transparent Group
# ---------------------------------------------------------------------

class TransparentGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTransparent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        # Flip
        self.links.new(self.inputs.outputs["Cycles"], self.mix1.inputs[2])
        self.links.new(self.inputs.outputs["Eevee"], self.mix2.inputs[2])
        self.links.new(trans.outputs[0], self.mix1.inputs[1])
        self.links.new(trans.outputs[0], self.mix2.inputs[1])

# ---------------------------------------------------------------------
#   Translucent Group
# ---------------------------------------------------------------------

class TranslucentGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Scale", "Radius", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        trans = self.addNode("ShaderNodeBsdfTranslucent", 1)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])
        self.links.new(self.inputs.outputs["Normal"], trans.inputs["Normal"])

        gamma = self.addNode("ShaderNodeGamma", 1)
        self.links.new(self.inputs.outputs["Color"], gamma.inputs["Color"])
        gamma.inputs["Gamma"].default_value = 2.5

        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        self.links.new(gamma.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])

        self.links.new(trans.outputs[0], self.mix1.inputs[2])
        self.links.new(sss.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   SSS Group
# ---------------------------------------------------------------------

class SSSGroup(MixGroup):

    def __init__(self):
        MixGroup.__init__(self)
        self.insockets += ["Color", "Scale", "Radius", "Normal"]


    def create(self, node, name, parent):
        MixGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Scale")
        self.group.inputs.new("NodeSocketVector", "Radius")
        self.group.inputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args=None):
        MixGroup.addNodes(self, args)
        sss = self.addNode("ShaderNodeSubsurfaceScattering", 1)
        self.links.new(self.inputs.outputs["Color"], sss.inputs["Color"])
        self.links.new(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.links.new(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.links.new(self.inputs.outputs["Normal"], sss.inputs["Normal"])
        self.links.new(sss.outputs[0], self.mix1.inputs[2])
        self.links.new(sss.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Ray Clip Group
# ---------------------------------------------------------------------

class RayClipGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Shader", "Color"]
        self.outsockets += ["Shader"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, args=None):
        lpath = self.addNode("ShaderNodeLightPath", 1)

        max = self.addNode("ShaderNodeMath", 2)
        max.operation = 'MAXIMUM'
        self.links.new(lpath.outputs["Is Shadow Ray"], max.inputs[0])
        self.links.new(lpath.outputs["Is Reflection Ray"], max.inputs[1])

        trans = self.addNode("ShaderNodeBsdfTransparent", 2)
        self.links.new(self.inputs.outputs["Color"], trans.inputs["Color"])

        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(max.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Shader"], mix.inputs[1])
        self.links.new(trans.outputs[0], mix.inputs[2])

        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])

# ---------------------------------------------------------------------
#   Dual Lobe Group
# ---------------------------------------------------------------------

class DualLobeGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += [
            "Fac", "Cycles", "Eevee", "Weight", "IOR",
            "Roughness 1", "Roughness 2"]
        self.outsockets += ["Cycles", "Eevee"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketShader", "Cycles")
        self.group.inputs.new("NodeSocketShader", "Eevee")
        self.group.inputs.new("NodeSocketFloat", "Weight")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketShader", "Cycles")
        self.group.outputs.new("NodeSocketShader", "Eevee")



    def addNodes(self, args=None):
        fresnel1 = self.addFresnel(True, "Roughness 1")
        glossy1 = self.addGlossy("Roughness 1", self.lobe1Normal)
        cycles1 = self.mixGlossy(fresnel1, glossy1, "Cycles")
        eevee1 = self.mixGlossy(fresnel1, glossy1, "Eevee")
        fresnel2 = self.addFresnel(False, "Roughness 2")
        glossy2 = self.addGlossy("Roughness 2", self.lobe2Normal)
        cycles2 = self.mixGlossy(fresnel2, glossy2, "Cycles")
        eevee2 = self.mixGlossy(fresnel2, glossy2, "Eevee")
        self.mixOutput(cycles1, cycles2, "Cycles")
        self.mixOutput(eevee1, eevee2, "Eevee")


    def addGlossy(self, roughness, useNormal):
        glossy = self.addNode("ShaderNodeBsdfGlossy", 1)
        self.links.new(self.inputs.outputs["Weight"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy


    def mixGlossy(self, fresnel, glossy, slot):
        mix = self.addNode("ShaderNodeMixShader", 2)
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs[slot], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])
        return mix


    def mixOutput(self, node1, node2, slot):
        mix = self.addNode("ShaderNodeMixShader", 3)
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[2])
        self.links.new(node2.outputs[0], mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs[slot])


class DualLobeGroupUberIray(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = False

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addNode("ShaderNodeFresnel", 1)
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        if useNormal:
            self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel


class DualLobeGroupPBRSkin(DualLobeGroup):
    lobe1Normal = True
    lobe2Normal = True

    def addFresnel(self, useNormal, roughness):
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 1)
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel

# ---------------------------------------------------------------------
#   Volume Group
# ---------------------------------------------------------------------

class VolumeGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += [
            "Absorbtion Color", "Absorbtion Density", "Scatter Color",
            "Scatter Density", "Scatter Anisotropy"]
        self.outsockets += ["Volume"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 3)
        self.group.inputs.new("NodeSocketColor", "Absorbtion Color")
        self.group.inputs.new("NodeSocketFloat", "Absorbtion Density")
        self.group.inputs.new("NodeSocketColor", "Scatter Color")
        self.group.inputs.new("NodeSocketFloat", "Scatter Density")
        self.group.inputs.new("NodeSocketFloat", "Scatter Anisotropy")
        self.group.outputs.new("NodeSocketShader", "Volume")


    def addNodes(self, args=None):
        absorb = self.addNode("ShaderNodeVolumeAbsorption", 1)
        self.links.new(self.inputs.outputs["Absorbtion Color"], absorb.inputs["Color"])
        self.links.new(self.inputs.outputs["Absorbtion Density"], absorb.inputs["Density"])

        scatter = self.addNode("ShaderNodeVolumeScatter", 1)
        self.links.new(self.inputs.outputs["Scatter Color"], scatter.inputs["Color"])
        self.links.new(self.inputs.outputs["Scatter Density"], scatter.inputs["Density"])
        self.links.new(self.inputs.outputs["Scatter Anisotropy"], scatter.inputs["Anisotropy"])

        volume = self.addNode("ShaderNodeAddShader", 2)
        self.links.new(absorb.outputs[0], volume.inputs[0])
        self.links.new(scatter.outputs[0], volume.inputs[1])
        self.links.new(volume.outputs[0], self.outputs.inputs["Volume"])

# ---------------------------------------------------------------------
#   Normal Group
#
#   https://blenderartists.org/t/way-faster-normal-map-node-for-realtime-animation-playback-with-tangent-space-normals/1175379
# ---------------------------------------------------------------------

class NormalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Strength", "Color"]
        self.outsockets += ["Normal"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 8)

        strength = self.group.inputs.new("NodeSocketFloat", "Strength")
        strength.default_value = 1.0
        strength.min_value = 0.0
        strength.max_value = 1.0

        color = self.group.inputs.new("NodeSocketColor", "Color")
        color.default_value = ((0.5, 0.5, 1.0, 1.0))

        self.group.outputs.new("NodeSocketVector", "Normal")


    def addNodes(self, args):
        # Generate TBN from Bump Node
        frame = self.nodes.new("NodeFrame")
        frame.label = "Generate TBN from Bump Node"

        uvmap = self.addNode("ShaderNodeUVMap", 1, parent=frame)
        if args[0]:
            uvmap.uv_map = args[0]

        uvgrads = self.addNode("ShaderNodeSeparateXYZ", 2, label="UV Gradients", parent=frame)
        self.links.new(uvmap.outputs["UV"], uvgrads.inputs[0])

        tangent = self.addNode("ShaderNodeBump", 3, label="Tangent", parent=frame)
        tangent.invert = True
        tangent.inputs["Distance"].default_value = 1
        self.links.new(uvgrads.outputs[0], tangent.inputs["Height"])

        bitangent = self.addNode("ShaderNodeBump", 3, label="Bi-Tangent", parent=frame)
        bitangent.invert = True
        bitangent.inputs["Distance"].default_value = 1000
        self.links.new(uvgrads.outputs[1], bitangent.inputs["Height"])

        geo = self.addNode("ShaderNodeNewGeometry", 3, label="Normal", parent=frame)

        # Transpose Matrix
        frame = self.nodes.new("NodeFrame")
        frame.label = "Transpose Matrix"

        sep1 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(tangent.outputs["Normal"], sep1.inputs[0])

        sep2 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(bitangent.outputs["Normal"], sep2.inputs[0])

        sep3 = self.addNode("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.links.new(geo.outputs["Normal"], sep3.inputs[0])

        comb1 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[0], comb1.inputs[0])
        self.links.new(sep2.outputs[0], comb1.inputs[1])
        self.links.new(sep3.outputs[0], comb1.inputs[2])

        comb2 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[1], comb2.inputs[0])
        self.links.new(sep2.outputs[1], comb2.inputs[1])
        self.links.new(sep3.outputs[1], comb2.inputs[2])

        comb3 = self.addNode("ShaderNodeCombineXYZ", 5, parent=frame)
        self.links.new(sep1.outputs[2], comb3.inputs[0])
        self.links.new(sep2.outputs[2], comb3.inputs[1])
        self.links.new(sep3.outputs[2], comb3.inputs[2])

        # Normal Map Processing
        frame = self.nodes.new("NodeFrame")
        frame.label = "Normal Map Processing"

        rgb = self.addNode("ShaderNodeMixRGB", 3, parent=frame)
        self.links.new(self.inputs.outputs["Strength"], rgb.inputs[0])
        rgb.inputs[1].default_value = (0.5, 0.5, 1.0, 1.0)
        self.links.new(self.inputs.outputs["Color"], rgb.inputs[2])

        sub = self.addNode("ShaderNodeVectorMath", 4, parent=frame)
        sub.operation = 'SUBTRACT'
        self.links.new(rgb.outputs["Color"], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.5)

        add = self.addNode("ShaderNodeVectorMath", 5, parent=frame)
        add.operation = 'ADD'
        self.links.new(sub.outputs[0], add.inputs[0])
        self.links.new(sub.outputs[0], add.inputs[1])

        # Matrix * Normal Map
        frame = self.nodes.new("NodeFrame")
        frame.label = "Matrix * Normal Map"

        dot1 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot1.operation = 'DOT_PRODUCT'
        self.links.new(comb1.outputs[0], dot1.inputs[0])
        self.links.new(add.outputs[0], dot1.inputs[1])

        dot2 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot2.operation = 'DOT_PRODUCT'
        self.links.new(comb2.outputs[0], dot2.inputs[0])
        self.links.new(add.outputs[0], dot2.inputs[1])

        dot3 = self.addNode("ShaderNodeVectorMath", 6, parent=frame)
        dot3.operation = 'DOT_PRODUCT'
        self.links.new(comb3.outputs[0], dot3.inputs[0])
        self.links.new(add.outputs[0], dot3.inputs[1])

        comb = self.addNode("ShaderNodeCombineXYZ", 7, parent=frame)
        self.links.new(dot1.outputs["Value"], comb.inputs[0])
        self.links.new(dot2.outputs["Value"], comb.inputs[1])
        self.links.new(dot3.outputs["Value"], comb.inputs[2])

        self.links.new(comb.outputs[0], self.outputs.inputs["Normal"])

# ---------------------------------------------------------------------
#   Displacement Group
# ---------------------------------------------------------------------

class DisplacementGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Texture", "Strength", "Difference", "Min"]
        self.outsockets += ["Displacement"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Texture")
        self.group.inputs.new("NodeSocketFloat", "Strength")
        self.group.inputs.new("NodeSocketFloat", "Difference")
        self.group.inputs.new("NodeSocketFloat", "Min")
        self.group.outputs.new("NodeSocketFloat", "Displacement")


    def addNodes(self, args=None):
        mult1 = self.addNode("ShaderNodeMath", 1)
        mult1.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Texture"], mult1.inputs[0])
        self.links.new(self.inputs.outputs["Difference"], mult1.inputs[1])

        add = self.addNode("ShaderNodeMath", 2)
        add.operation = 'ADD'
        self.links.new(mult1.outputs[0], add.inputs[0])
        self.links.new(self.inputs.outputs["Min"], add.inputs[1])

        mult2 = self.addNode("ShaderNodeMath", 3)
        mult2.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Strength"], mult2.inputs[0])
        self.links.new(add.outputs[0], mult2.inputs[1])

        self.links.new(mult2.outputs[0], self.outputs.inputs["Displacement"])

# ---------------------------------------------------------------------
#   Decal Group
# ---------------------------------------------------------------------

class DecalGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color", "Influence"]
        self.outsockets += ["Color", "Alpha", "Combined"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 5)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "Influence")
        self.group.outputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Alpha")
        self.group.outputs.new("NodeSocketColor", "Combined")


    def addNodes(self, args):
        empty,img = args

        texco = self.addNode("ShaderNodeTexCoord", 0)
        texco.object = empty

        mapping = self.addNode("ShaderNodeMapping", 1)
        mapping.vector_type = 'POINT'
        mapping.inputs["Location"].default_value = (0.5, 0.5, 0)
        self.links.new(texco.outputs["Object"], mapping.inputs["Vector"])

        tex = self.addNode("ShaderNodeTexImage", 2)
        tex.image = img
        tex.extension = 'CLIP'
        self.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])

        mult = self.addNode("ShaderNodeMath", 3)
        mult.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Influence"], mult.inputs[0])
        self.links.new(tex.outputs["Alpha"], mult.inputs[1])

        mix = self.addNode("ShaderNodeMixRGB", 4)
        mix.blend_type = 'MULTIPLY'
        self.links.new(mult.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Color"], mix.inputs[1])
        self.links.new(tex.outputs["Color"], mix.inputs[2])

        self.links.new(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.links.new(mult.outputs[0], self.outputs.inputs["Alpha"])
        self.links.new(mix.outputs[0], self.outputs.inputs["Combined"])

# ---------------------------------------------------------------------
#   LIE Group
# ---------------------------------------------------------------------

class LieGroup(CyclesGroup):

    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Vector", "Alpha"]
        self.outsockets += ["Color"]


    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketVector", "Vector")
        self.texco = self.inputs.outputs[0]
        self.group.inputs.new("NodeSocketFloat", "Alpha")
        self.group.outputs.new("NodeSocketColor", "Color")


    def addTextureNodes(self, assets, maps, colorSpace):
        texnodes = []
        for idx,asset in enumerate(assets):
            texnode,isnew = self.addSingleTexture(3, asset, maps[idx], colorSpace)
            if isnew:
                innode = texnode
                mapping = self.mapTexture(asset, maps[idx])
                if mapping:
                    texnode.extension = 'CLIP'
                    self.links.new(mapping.outputs["Vector"], texnode.inputs["Vector"])
                    innode = mapping
                else:
                    img = asset.images[colorSpace]
                    if img:
                        self.setTexNode(img.name, texnode, colorSpace)
                    else:
                        msg = ("Missing image: %s" % asset.getName())
                        reportError(msg, trigger=(3,5))
                self.links.new(self.inputs.outputs["Vector"], innode.inputs["Vector"])
            texnodes.append([texnode])

        if texnodes:
            nassets = len(assets)
            for idx in range(1, nassets):
                map = maps[idx]
                if map.invert:
                    inv = self.addNode("ShaderNodeInvert", 4)
                    node = texnodes[idx][0]
                    self.links.new(node.outputs[0], inv.inputs["Color"])
                    texnodes[idx].append(inv)

            texnode = texnodes[0][-1]
            alphamix = self.addNode("ShaderNodeMixRGB", 6)
            alphamix.blend_type = 'MIX'
            alphamix.inputs[0].default_value = 1.0
            self.links.new(self.inputs.outputs["Alpha"], alphamix.inputs[0])
            self.links.new(texnode.outputs["Color"], alphamix.inputs[1])

            masked = False
            for idx in range(1, nassets):
                map = maps[idx]
                if map.ismask:
                    if idx == nassets-1:
                        continue
                    mix = self.addNode("ShaderNodeMixRGB", 5)    # ShaderNodeMixRGB
                    mix.blend_type = 'MULTIPLY'
                    mix.use_alpha = False
                    mask = texnodes[idx][-1]
                    self.setColorSpace(mask, 'NONE')
                    self.links.new(mask.outputs["Color"], mix.inputs[0])
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx+1][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = True
                elif not masked:
                    mix = self.addNode("ShaderNodeMixRGB", 5)
                    alpha = setMixOperation(mix, map)
                    mix.inputs[0].default_value = alpha
                    node = texnodes[idx][-1]
                    base = texnodes[idx][0]
                    if alpha != 1:
                        node = self.multiplyScalarTex(alpha, base, 4, "Alpha")
                        self.links.new(node.outputs[0], mix.inputs[0])
                    elif "Alpha" in base.outputs.keys():
                        self.links.new(base.outputs["Alpha"], mix.inputs[0])
                    else:
                        print("No LIE alpha:", base)
                        mix.inputs[0].default_value = alpha
                    mix.use_alpha = True
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = False
                else:
                    masked = False

            self.links.new(texnode.outputs[0], alphamix.inputs[2])
            self.links.new(alphamix.outputs[0], self.outputs.inputs["Color"])


    def mapTexture(self, asset, map):
        if asset.hasMapping(map):
            data = asset.getMapping(self.material, map)
            return self.addMappingNode(data, map)


def setMixOperation(mix, map):
    alpha = 1
    op = map.operation
    alpha = map.transparency
    if op == "multiply":
        mix.blend_type = 'MULTIPLY'
        useAlpha = True
    elif op == "add":
        mix.blend_type = 'ADD'
        useAlpha = False
    elif op == "subtract":
        mix.blend_type = 'SUBTRACT'
        useAlpha = False
    elif op == "alpha_blend":
        mix.blend_type = 'MIX'
        useAlpha = True
    else:
        print("MIX", asset, map.operation)
    return alpha
