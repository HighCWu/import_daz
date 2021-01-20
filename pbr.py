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
import math
from mathutils import Vector, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .error import *
from .utils import *
from .cycles import CyclesTree

class PbrTree(CyclesTree):
    def __init__(self, pbrmat):
        CyclesTree.__init__(self, pbrmat)
        self.pbr = None
        self.type = 'PBR'


    def __repr__(self):
        return ("<Pbr %s %s %s>" % (self.material.rna, self.nodes, self.links))


    def buildLayer(self):
        self.column = 4
        try:
            self.pbr = self.addNode("ShaderNodeBsdfPrincipled")
            self.ycoords[self.column] -= 500
        except RuntimeError:
            self.pbr = None
            self.type = 'CYCLES'
        if self.pbr is None:
            CyclesTree.buildLayer(self)
            return
        self.cycles = self.eevee = self.pbr
        self.buildBumpNodes()
        self.buildPBRNode()
        self.linkPBRNormal()
        self.postPBR = False
        if self.buildOverlay():
            self.postPBR = True
        if self.material.dualLobeWeight > 0:
            self.buildDualLobe()
            self.pbr.inputs["Specular"].default_value = 0
            self.removeLink(self.pbr, "Specular")
            self.postPBR = True
        if self.material.refractive:
            self.buildRefraction()
        else:
            self.buildEmission()


    def linkPBRNormal(self):
        if self.normal:
            self.links.new(self.normal.outputs["Normal"], self.pbr.inputs["Normal"])
            self.links.new(self.normal.outputs["Normal"], self.pbr.inputs["Clearcoat Normal"])


    def buildCutout(self):
        if "Alpha" in self.pbr.inputs.keys() and not self.postPBR:
            alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1)
            if alpha < 1 or tex:
                self.material.setTransSettings(False, False)
                self.useCutout = True
            self.pbr.inputs["Alpha"].default_value = alpha
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Alpha"])
        else:
            CyclesTree.buildCutout(self)


    def buildVolume(self):
        pass


    def buildEmission(self):
        if not GS.useEmission:
            return
        elif "Emission" in self.pbr.inputs.keys():
            color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
            if color != BLACK:
                self.linkColor(tex, self.pbr, color, "Emission")
        else:
            CyclesTree.buildEmission(self)


    def buildPBRNode(self):
        # Basic
        color,tex = self.getDiffuseColor()
        self.diffuseColor = color
        self.diffuseTex = tex
        self.linkColor(tex, self.pbr, color, "Base Color")

        # Metallic Weight
        metallicity,tex = self.getColorTex(["Metallic Weight"], "NONE", 0.0)
        self.linkScalar(tex, self.pbr, metallicity, "Metallic")
        useTex = not (self.material.shader == 'IRAY' and self.material.basemix == 0 and metallicity > 0.5)

        # Subsurface scattering
        self.checkTranslucency()
        self.buildSSS()

        # Anisotropic
        anisotropy,tex = self.getColorTex(["Glossy Anisotropy"], "NONE", 0)
        if anisotropy > 0:
            self.linkScalar(tex, self.pbr, anisotropy, "Anisotropic")
            anirot,tex = self.getColorTex(["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 0.75 - anirot
            self.linkScalar(tex, self.pbr, value, "Anisotropic Rotation")

        # Roughness
        channel,invert,value,roughness = self.getGlossyRoughness()
        roughness *= (1 + anisotropy)
        self.addSlot(channel, self.pbr, "Roughness", roughness, value, invert)

        # Specular
        strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        if self.material.shader == 'IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl,reftex = self.getColorTex("getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                color,coltex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
                if reftex and coltex:
                    reftex = self.mixTexs('MULTIPLY', coltex, reftex)
                elif coltex:
                    reftex = coltex
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 1.25 * refl * strength
                value = factor * averageColor(color)
            elif self.material.basemix == 1:  # Specular/Glossiness
                # principled specular = iray glossy specular * iray glossy layered weight * 16
                color,reftex = self.getColorTex("getChannelGlossySpecular", "COLOR", WHITE, True, useTex)
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 16 * strength
                value = factor * averageColor(color)
        else:
            color,coltex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, True, useTex)
            tex = self.mixTexs('MULTIPLY', strtex, coltex)
            value = factor = strength * averageColor(color)

        self.pbr.inputs["Specular"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(factor), tex)
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Specular"])

        # Clearcoat
        top,toptex = self.getColorTex(["Top Coat Weight"], "NONE", 1.0, False)
        if self.material.shader == 'IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                refl,reftex = self.getColorTex("getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                tex = self.mixTexs('MULTIPLY', toptex, reftex)
                value = 1.25 * refl * top
            else:
                tex = toptex
                value = top
        else:
            tex = toptex
            value = top
        self.pbr.inputs["Clearcoat"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(value), tex)
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Clearcoat"])

        rough,tex = self.getColorTex(["Top Coat Roughness"], "NONE", 1.45)
        self.linkScalar(tex, self.pbr, rough, "Clearcoat Roughness")

        # Sheen
        if self.material.isActive("Backscattering"):
            sheen,tex = self.getColorTex(["Backscattering Weight"], "NONE", 0.0)
            self.linkScalar(tex, self.pbr, sheen, "Sheen")


    def buildSSS(self):
        if not self.useTranslucency:
            return
        # a 2.5 gamma for the translucency texture is used to avoid the "white skin" effect
        gamma = self.addNode("ShaderNodeGamma", col=3)
        gamma.inputs["Gamma"].default_value = 2.5
        color,coltex = self.getColorTex("getChannelTranslucencyColor", "COLOR", BLACK)
        if isBlack(color):
            return
        wt,wttex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0)
        radius,radtex = self.getSSSRadius(color)
        self.linkColor(coltex, gamma, color, "Color")
        self.links.new(gamma.outputs[0], self.pbr.inputs["Subsurface Color"])
        self.linkScalar(wttex, self.pbr, wt, "Subsurface")
        self.linkColor(radtex, self.pbr, radius, "Subsurface Radius")
        self.endSSS()


    def setPbrSlot(self, slot, value):
        self.pbr.inputs[slot].default_value = value
        self.removeLink(self.pbr, slot)


    def getRefractionWeight(self):
        channel = self.material.getChannelRefractionWeight()
        if channel:
            return self.getColorTex("getChannelRefractionWeight", "NONE", 0.0)
        channel = self.material.getChannelOpacity()
        if channel:
            value,tex = self.getColorTex("getChannelOpacity", "NONE", 1.0)
            invtex = self.fixTex(tex, value, True)
            return 1-value, invtex
        return 1,None


    def buildRefraction(self):
        weight,wttex = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0)
        if weight == 0:
            return
        color,coltex,roughness,roughtex = self.getRefractionColor()
        ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
        self.linkScalar(wttex, self.pbr, weight, "Transmission")

        if self.material.thinWall:
            # if thin walled is on then there's no volume
            # and we use the clearcoat channel for reflections
            #  principled ior = 1
            #  principled roughness = 0
            #  principled clearcoat = (iray refraction index - 1) * 10 * iray glossy layered weight
            #  principled clearcoat roughness = 0
            self.material.setTransSettings(True, False)
            self.setPbrSlot("IOR", 1.0)
            self.setPbrSlot("Roughness", 0.0)
            strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            clearcoat = (ior-1)*10*strength
            self.linkScalar(strtex, self.pbr, clearcoat, "Clearcoat")
            self.setPbrSlot("Clearcoat Roughness", 0)

        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness
            self.material.setTransSettings(True, False)
            transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
            dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
            if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
                coltex = self.mixTexs('MULTIPLY', coltex, transtex)
                color = self.compProd(color, transcolor)
            self.linkScalar(wttex, self.pbr, ior, "IOR")
            self.setPbrSlot("Metallic", 0)
            self.setPbrSlot("Specular", 0.5)
            self.setPbrSlot("IOR", ior)
            self.setRoughness(self.pbr, "Roughness", roughness, roughtex, square=False)
            if not roughtex:
                self.removeLink(self.pbr, "Roughness")

        self.linkColor(coltex, self.pbr, color, slot="Base Color")
        if not coltex:
            self.removeLink(self.pbr, "Base Color")
        self.pbr.inputs["Subsurface"].default_value = 0
        self.removeLink(self.pbr, "Subsurface")
        self.removeLink(self.pbr, "Subsurface Color")
        if self.material.shareGlossy:
            self.pbr.inputs["Specular Tint"].default_value = 1.0


    def mixShaders(self, weight, wttex, node1, node2):
        mix = self.addNode("ShaderNodeMixShader")
        mix.inputs[0].default_value = weight
        if wttex:
            self.links.new(wttex.outputs[0], mix.inputs[0])
        self.links.new(node1.outputs[0], mix.inputs[1])
        self.links.new(node2.outputs[0], mix.inputs[2])
        return mix


    def limitNode(self, tex, op, threshold):
        math = self.addNode("ShaderNodeMath", col = self.column-1)
        math.operation = op
        self.links.new(tex.outputs[0], math.inputs[0])
        math.inputs[1].default_value = threshold
        return math


    def getGlossyRoughness(self):
        # principled roughness = iray glossy roughness = 1 - iray glossiness
        channel,invert = self.material.getChannelGlossiness()
        invert = not invert
        value = clamp(self.material.getChannelValue(channel, 0.5))
        if invert:
            roughness = 1 - value
        else:
            roughness = value
        return channel,invert,value,roughness


    def setPBRValue(self, slot, value, default, maxval=0):
        if isinstance(default, Vector):
            if isinstance(value, float) or isinstance(value, int):
                value = Vector((value,value,value))
            self.pbr.inputs[slot].default_value[0:3] = value
        else:
            value = averageColor(value)
            if maxval and value > maxval:
                value = maxval
            self.pbr.inputs[slot].default_value = value

