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
import math
from mathutils import Vector, Color
from .material import Material, WHITE, GREY, BLACK
from .settings import theSettings
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


    def buildLayer(self, context):
        try:
            self.pbr = self.addNode(4, "ShaderNodeBsdfPrincipled")
            self.ycoords[4] -= 500
        except RuntimeError:
            self.pbr = None
            self.type = 'CYCLES'
        if self.pbr is None:
            CyclesTree.buildLayer(self, context)
            return
        scn = context.scene
        self.active = self.pbr
        self.buildBumpNodes(scn)
        self.buildPBRNode(scn)
        if self.material.thinWalled:
            self.buildTranslucency()        
        if self.material.dualLobeWeight > 0:
            self.buildDualLobe()
            self.links.new(self.active.outputs[0], self.dualLobe.inputs["Shader"])
            self.active = self.dualLobe
            self.pbr.inputs["Specular"].default_value = 0
            self.removeLink(self.pbr, "Specular")
        if self.material.refractive:
            if theSettings.handleRefractive == 'GUESS':
                self.guessGlass()
            else:
                self.buildRefraction()
        else:
            self.buildEmission()
            self.buildOverlay()
        return self.active        
    
    
    def buildCutout(self):
        if "Alpha" in self.pbr.inputs.keys():
            alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1)
            if alpha < 1 or tex:
                self.material.alphaBlend(alpha, tex)
            self.pbr.inputs["Alpha"].default_value = alpha
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Alpha"])
        else:
            CyclesTree.buildCutout(self)


    def buildEmission(self):
        if False and "Emission" in self.pbr.inputs.keys():
            color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
            self.pbr.inputs["Emission"].default_value[0:3] = color
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Emission"])
        else:
            CyclesTree.buildEmission(self)


    def mixGlass(self, scn):
        strength,imgfile,channel = self.getRefraction()
        if strength < 1 or imgfile:
            self.active = self.addMixShader(7, strength, channel, imgfile, None, self.pbr, self.glass)
        else:
            self.active = self.glass
        self.tintSpecular()


    def buildDisplacementNodes(self):
        CyclesTree.buildDisplacementNodes(self)
        if self.normal:
            self.links.new(self.normal.outputs["Normal"], self.pbr.inputs["Normal"])
            self.links.new(self.normal.outputs["Normal"], self.pbr.inputs["Clearcoat Normal"])


    def buildPBRNode(self, scn):
        # Basic
        color,tex = self.getDiffuseColor()
        self.diffuseTex = tex
        self.setPBRValue("Base Color", color, WHITE)
        if tex:
            self.linkColor(tex, self.pbr, color, "Base Color")

        # Metallic Weight
        metallicity,tex = self.getColorTex(["Metallic Weight"], "NONE", 0.0)
        self.setPBRValue("Metallic", metallicity, 0.0)
        if tex and theSettings.useTextures:
            self.linkScalar(tex, self.pbr, metallicity, "Metallic")
        useTex = not (self.material.shader == 'IRAY' and self.material.basemix == 0 and metallicity > 0.5)

        # Subsurface scattering
        if (theSettings.useSSS and
            self.material.sssActive() and
            not self.material.thinWalled and
            not self.material.refractive):

            wt,wttex = self.getColorTex("getChannelSSSAmount", "NONE", 0)
            self.setPBRValue("Subsurface", wt, 0.0)
            if wttex:
                self.linkScalar(wttex, self.pbr, wt, "Base Color")
            
            color,tex = self.getColorTex("getChannelSSSColor", "COLOR", WHITE)
            self.setPBRValue("Subsurface Color", color, WHITE)
            if tex:
                self.linkColor(tex, self.pbr, color, "Subsurface Color")
            elif self.diffuseTex:
                self.linkColor(self.diffuseTex, self.pbr, color, "Subsurface Color")                   

            rad,radtex = self.getColorTex("getChannelSSSRadius", "NONE", WHITE)
            rad *= theSettings.scale
            self.setPBRValue("Subsurface Radius", rad, WHITE)
            if radtex:
                self.linkColor(radtex, self.pbr, rad, "Subsurface Radius")

        # Anisotropic
        anisotropy = self.getValue(["Glossy Anisotropy"], 0)
        if anisotropy > 0:  
            self.setPBRValue("Anisotropic", anisotropy, 0)      
            anirot = self.getValue(["Glossy Anisotropy Rotations"], 0)
            self.setPBRValue("Anisotropic Rotation", 0.75 - anirot, 0)      
            
        # Roughness
        channel,invert,value,roughness = self.getGlossyRoughness()
        roughness *= (1 + anisotropy)
        self.addSlot(channel, self.pbr, "Roughness", roughness, value, invert, theSettings.useTextures)

        # Specular
        strength,strtex = self.getColorTex("getChannelSpecularStrength", "NONE", 1.0, False)
        if self.material.shader == 'IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl,reftex = self.getColorTex("getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                color,coltex = self.getColorTex("getChannelSpecularColor", "COLOR", WHITE, True, useTex)
                if reftex and coltex:
                    reftex = self.multiplyTexs(coltex, reftex)
                elif coltex:
                    reftex = coltex
                tex = self.multiplyTexs(strtex, reftex)
                factor = 1.25 * refl * strength
                value = factor * averageColor(color)
                self.glossyColor, self.glossyTex = color, tex
            elif self.material.basemix == 1:  # Specular/Glossiness
                # principled specular = iray glossy specular * iray glossy layered weight * 16
                color,reftex = self.getColorTex("getChannelGlossySpecular", "COLOR", WHITE, True, useTex)
                tex = self.multiplyTexs(strtex, reftex)
                factor = 16 * strength
                value = factor * averageColor(color)
                self.glossyColor, self.glossyTex = color, tex
        else:
            color,coltex = self.getColorTex("getChannelSpecularColor", "COLOR", WHITE, True, useTex)
            tex = self.multiplyTexs(strtex, coltex)
            value = factor = strength * averageColor(color)

        self.pbr.inputs["Specular"].default_value = clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(clamp(factor), tex)
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Specular"])

        if self.material.thinWalled:
            self.pbr.inputs["IOR"].default_value = 1.0
        else:
            ior,tex = self.getColorTex("getChannelIOR", "NONE", 1.45)
            self.setPBRValue("IOR", ior, 1.45)
            if tex:
                self.linkScalar(tex, self.pbr, ior, "IOR")

        # Clearcoat
        top,toptex = self.getColorTex(["Top Coat Weight"], "NONE", 1.0, False)
        if self.material.shader == 'IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                refl,reftex = self.getColorTex("getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                tex = self.multiplyTexs(toptex, reftex)
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
        self.setPBRValue("Clearcoat Roughness", rough, 1.45)
        if tex and theSettings.useTextures:
            self.linkScalar(tex, self.pbr, rough, "Clearcoat Roughness")

        # Sheen
        if self.material.isActive("Backscattering"):
            sheen,tex = self.getColorTex(["Backscattering Weight"], "NONE", 0.0)
            self.setPBRValue("Sheen", sheen, 0.0)
            if tex and theSettings.useTextures:
                self.linkScalar(tex, self.pbr, sheen, "Sheen")


    def setPbrSlot(self, slot, value):
        self.pbr.inputs[slot].default_value = value
        self.removeLink(self.pbr, slot)


    def buildRefraction(self):
        channel = self.material.getChannelRefractionStrength()
        value = 0
        if channel:
            value,tex = self.getColorTex("getChannelRefractionStrength", "NONE", 0.0)
            self.setPBRValue("Transmission", value, 0.0)
            if tex:
                self.linkScalar(tex, self.pbr, value, "Transmission")
        else:
            channel = self.material.getChannelOpacity()
            if channel:
                value,tex = self.getColorTex("getChannelOpacity", "NONE", 1.0)
                tex = self.fixTex(tex, value, True)
                value = 1-value
                self.setPBRValue("Transmission", value, 0.0)
                if tex:
                    self.linkScalar(tex, self.pbr, value, "Transmission")
        if value > 0:
            self.material.alphaBlend(1-value, tex)
            color,tex,_roughness,_roughtex = self.getRefractionColor()
            self.pbr.inputs["Base Color"].default_value[0:3] = color
            if tex:
                self.links.new(tex.outputs[0], self.pbr.inputs["Base Color"])
            else:
                self.removeLink(self.pbr, "Base Color")
            self.setPbrSlot("Specular", 0.5)
            self.setPbrSlot("Subsurface", 0.0)
            self.removeLink(self.pbr, "Subsurface Color")
            self.tintSpecular()


    def tintSpecular(self):
        if self.material.shareGlossy:
            self.pbr.inputs["Specular Tint"].default_value = 1.0


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


    def guessGlass(self):
        ior = self.getValue("getChannelIOR", 1.45)
        self.pbr.inputs["Transmission"].default_value = 1
        self.removeLink(self.pbr, "Transmission")
        strength = self.getValue("getChannelSpecularStrength", 1.0)
        self.material.alphaBlend(1-strength, None)

        if self.material.thinWalled:
            # principled transmission = 1
            # principled base color = iray glossy color (possibly with texture)
            # principled metallic = (iray refraction index - 1) / 3 * glossy layered weight
            # principled specular = 1
            # principled ior = 1
            # principled roughness = 0

            self.setPbrSlot("Metallic", (ior-1)/3*strength)
            self.setPbrSlot("Specular", 1.0)
            self.setPbrSlot("IOR", 1.0)
            self.setPbrSlot("Roughness", 0.0)

            color,tex = self.getColorTex("getChannelSpecularColor", "COLOR", WHITE)
        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness

            self.setPbrSlot("Metallic", 0)
            self.setPbrSlot("Specular", 0.5)
            self.setPbrSlot("IOR", ior)

            color,tex,roughness,roughtex = self.getRefractionColor()
            self.setRoughness(self.pbr, "Roughness", roughness, roughtex, square=False)
            if not roughtex:
                self.removeLink(self.pbr, "Roughness")

        self.pbr.inputs["Base Color"].default_value[0:3] = color
        if tex:
            self.links.new(tex.outputs[0], self.pbr.inputs["Base Color"])
        else:
            self.removeLink(self.pbr, "Base Color")

        self.pbr.inputs["Subsurface"].default_value = 0
        self.removeLink(self.pbr, "Subsurface")
        self.removeLink(self.pbr, "Subsurface Color")
        self.tintSpecular()


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

