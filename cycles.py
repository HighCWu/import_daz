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
import os
from mathutils import Vector, Matrix, Color
from .material import Material, WHITE, GREY, BLACK, isWhite, isBlack
from .settings import theSettings
from .error import DazError
from .utils import *

#-------------------------------------------------------------
#   Cycles material
#-------------------------------------------------------------

class CyclesMaterial(Material):

    def __init__(self, fileref):
        Material.__init__(self, fileref)
        self.tree = None
        self.eevee = False


    def __repr__(self):
        if self.tree:
            type = self.tree.type
        else:
            type = None
        return ("<%sMaterial %s r: %s i:%s t:%s>" % (type, self.id, self.rna, self.ignore, self.hasAnyTexture()))


    def build(self, context):
        if self.ignore:
            return
        Material.build(self, context)

        from .pbr import PbrTree
        if bpy.app.version >= (2, 78, 0):
            if not theSettings.autoMaterials:
                if ((self.refractive and theSettings.handleRefractive == 'EEVEE') or
                    (not self.refractive and theSettings.handleOpaque == 'EEVEE')):
                    self.tree = PbrTree(self)
                    self.eevee = True
                elif ((self.refractive and theSettings.handleRefractive in ['PRINCIPLED', 'GUESS']) or
                      (not self.refractive and theSettings.handleOpaque == 'PRINCIPLED')):
                    self.tree = PbrTree(self)
                else:
                    self.tree = CyclesTree(self)
            elif theSettings.renderMethod == 'BLENDER_EEVEE':
                self.tree = PbrTree(self)
                self.eevee = True
            elif (self.dualLobeWeight or
                  (self.thinWalled and self.translucent)):
                self.tree = CyclesTree(self)                
            elif self.metallic:
                self.tree = PbrTree(self)
            elif self.refractive:
                if theSettings.handleRefractive in ['PRINCIPLED', 'GUESS']:
                    self.tree = PbrTree(self)
                else:
                    self.tree = CyclesTree(self)
            elif theSettings.handleOpaque == 'PRINCIPLED':
                self.tree = PbrTree(self)
            else:
                self.tree = CyclesTree(self)
        else:
            self.tree = CyclesTree(self)
        self.tree.build(context)


    def postbuild(self, context):
        geo = self.geometry
        scn = context.scene
        if ((self.geosockets or self.hideMaterial)
            and geo and geo.rna):
            me = geo.rna
            mnum = 0
            for mn,mat in enumerate(me.materials):
                if mat == self.rna:
                    mnum = mn
                    break

            nodes = list(geo.nodes.values())
            if self.geosockets:
                self.correctArea(nodes, me, mnum)
            if self.hideMaterial:
                self.hideVerts(nodes, me, mnum)


    def hideVerts(self, nodes, me, mnum):
        ob = nodes[0].rna
        hname = "HiddenEevee"
        if hname in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[hname]
        else:
            vgrp = ob.vertex_groups.new(name=hname)

        nverts = len(ob.data.vertices)
        hide = dict([(vn,False) for vn in range(nverts)])
        for f in me.polygons:
            if f.material_index == mnum:
                for vn in f.vertices:
                    hide[vn] = True
        for f in me.polygons:
            if f.material_index != mnum:
                for vn in f.vertices:
                    hide[vn] = False
        for vn in range(nverts):
            if hide[vn]:
                vgrp.add([vn], 1.0, 'REPLACE')

        for node in nodes:
            ob = node.rna
            exists = False
            for mod in ob.modifiers:
                if mod.type == 'MASK' and mod.name == hname:
                    exists = True
                    break
            if not exists:
                mod = ob.modifiers.new(hname, 'MASK')
                mod.vertex_group = hname
                mod.invert_vertex_group = True
                value = (self.scene.render.engine != 'CYCLES')
                setattr(mod, "show_viewport", value)
                setattr(mod, "show_render", value)


    def correctArea(self, nodes, me, mnum):
        ob = nodes[0].rna
        ob.data = me2 = me.copy()
        mat = ob.matrix_world.copy()
        me2.transform(mat)
        ob.matrix_world = Matrix()
        area = sum([f.area for f in me2.polygons if f.material_index == mnum])
        ob.data = me
        ob.matrix_world = mat
        bpy.data.meshes.remove(me2, do_unlink=True)

        area *= 1e-4/(theSettings.scale*theSettings.scale)
        for socket in self.geosockets:
            socket.default_value /= area
            for link in self.tree.links:
                if link.to_socket == socket:
                    node = link.from_node
                    if node.type == 'MATH':
                        node.inputs[0].default_value /= area


    def alphaBlend(self, alpha, tex):
        if bpy.app.version >= (2,80,0):
            if alpha == 1 and tex is None:
                return
            mat = self.rna
            mat.blend_method = 'HASHED'
            mat.use_screen_refraction = True
            if hasattr(mat, "transparent_shadow_method"):
                mat.transparent_shadow_method = 'HASHED'
            else:
                mat.shadow_method = 'HASHED'
            if False and bpy.app.version >= (2,80,0):
                mname = mat.name.split("-")[0].lower()
                if mname in ["cornea", "eyemoisture"]:
                    self.hideMaterial = True
                else:
                    self.hideMaterial = (self.thinWalled and tex is None and value > 0.999)

#-------------------------------------------------------------
#   Cycles node tree
#-------------------------------------------------------------

class CyclesTree:
    def __init__(self, cmat):
        self.type = 'CYCLES'
        self.material = cmat
        self.active = None
        self.ycoords = 10*[500]
        self.texnodes = {}
        self.nodes = None
        self.links = None
        self.groups = {}
        self.liegroups = []

        self.diffuse = None
        self.diffuseTex = None
        self.glossyColor = WHITE
        self.glossyTex = None
        self.glossy = None
        self.fresnel = None
        self.dualLobe = None
        self.normal = None
        self.texco = None
        self.texcos = {}
        self.mapping = None
        self.displacement = None
        self.refraction = None
        self.transmission = None
        self.volume = None
        self.useCutout = False


    def __repr__(self):
        return ("<Cycles %s %s %s>" % (self.material.rna, self.nodes, self.links))


    def getValue(self, channel, default):
        return self.material.getValue(channel, default)


    def getColor(self, channel, default):
        return self.material.getColor(channel, default)


    def addNode(self, n, stype, label=None, parent=None):
        node = self.nodes.new(type = stype)
        node.location = (n*250-500, self.ycoords[n])
        self.ycoords[n] -= 250
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node


    def removeLink(self, node, slot):
        for link in self.links:
            if (link.to_node == node and
                link.to_socket.name == slot):
                self.links.remove(link)
                return


    def recoverYCoords(self):
        hits = 10*[0]
        for node in self.nodes:
            x,y = node.location
            n = int((x+500)/250)
            hits[n] += 1
        for n in range(10):
            self.ycoords[n] -= hits[n]*250


    def getTexco(self, uv):
        key = self.material.getUvKey(uv, self.texcos)
        if key is None:
            return self.texco
        elif key not in self.texcos.keys():
            self.addUvNode(key, key)
        return self.texcos[key]


    def addGroup(self, classdef, name, col, args=[]):
        node = self.addNode(col, "ShaderNodeGroup")
        if name in bpy.data.node_groups.keys():
            node.node_tree = bpy.data.node_groups[name]
        else:
            group = classdef(node, name, self)
            group.addNodes(args)
        return node
        

    def addShellGroup(self, context, shname, shmat):
        from .material import theShellGroups
        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
            shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.material.name))
            return None
        node = self.addNode(7, "ShaderNodeGroup")
        node.name = shname
        for shmat1,group in theShellGroups:
            if shmat.equalChannels(shmat1):
                node.node_tree = group
                return node
        if self.type == 'CYCLES':
            from .cgroup import ShellCyclesGroup
            group = ShellCyclesGroup(node, shname, self)
        elif self.type == 'PBR':
            from .cgroup import ShellPbrGroup
            group = ShellPbrGroup(node, shname, self)
        else:
            raise RuntimeError("Bug Cycles type %s" % self.type)
        group.addNodes(context, shmat)
        theShellGroups.append((shmat, node.node_tree))
        return node
        

    def build(self, context):
        scn = context.scene
        self.makeTree()
        if self.buildEeveeGlass():
            return
        self.buildVolume()
        self.buildLayer(context)
        for shname,shmat,uv in self.material.shells:
            node = self.addShellGroup(context, shname, shmat)
            if node:
                self.links.new(self.active.outputs[0], node.inputs["Shader"])
                self.links.new(self.getTexco(uv), node.inputs["UV"])
                self.active = node
        self.buildCutout()
        self.buildDisplacementNodes(scn)
        self.buildOutput()
        self.prune()


    def buildLayer(self, context):
        scn = context.scene
        self.buildBumpNodes(scn)
        self.buildDiffuse(scn)
        if theSettings.handleVolumetric == "SSS":
            self.buildSubsurface(scn)
        elif (self.material.thinWalled or
            self.volume or
            self.material.translucent):
            self.buildTranslucency(scn)
        else:
            self.buildSubsurface(scn)
        self.buildOverlay()
        if self.material.dualLobeWeight == 1:
            self.buildDualLobe()
        elif self.material.dualLobeWeight == 0:
            self.buildGlossy()
        else:
            self.buildDualLobe()
            self.buildGlossy()
        self.buildRefraction()
        self.linkGlossy()
        self.buildTopCoat()
        self.buildEmission(scn)
        return self.active


    def makeTree(self, slot="UV"):
        mat = self.material.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.addTexco(slot)


    def addTexco(self, slot):
        node = self.addNode(1, "ShaderNodeTexCoord")
        self.texco = node.outputs[slot]

        mat = self.material
        ox = mat.getChannelValue(mat.getChannelHorizontalOffset(), 0)
        oy = mat.getChannelValue(mat.getChannelVerticalOffset(), 0)
        kx = mat.getChannelValue(mat.getChannelHorizontalTiles(), 1)
        ky = mat.getChannelValue(mat.getChannelVerticalTiles(), 1)
        if ox != 0 or oy != 0 or kx != 1 or ky != 1:
            sx = 1/kx
            sy = 1/ky
            dx = -ox/kx
            dy = oy/ky
            self.mapping = self.addMappingNode((dx,dy,sx,sy,0), None)
            if self.mapping:
                self.linkVector(self.texco, self.mapping, 0)
                self.texco = self.mapping

        for key,uvset in self.material.uv_sets.items():
            self.addUvNode(key, uvset.name)
            
            
    def addUvNode(self, key, uvname):
        if True:
            node = self.addNode(1, "ShaderNodeUVMap")
            node.uv_map = uvname
            slot = "UV"
        else:
            node = self.addNode(1, "ShaderNodeAttribute")
            node.attribute_name = uvname
            slot = "Vector"
        self.texcos[key] = node.outputs[slot]


    def addMappingNode(self, data, map):
        dx,dy,sx,sy,rz = data
        if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            mapping = self.addNode(1, "ShaderNodeMapping")
            mapping.vector_type = 'TEXTURE'
            if hasattr(mapping, "translation"):
                mapping.translation = (dx,dy,0)
                mapping.scale = (sx,sy,1)
                if rz != 0:
                    mapping.rotation = (0,0,rz)
            else:
                mapping.inputs['Location'].default_value = (dx,dy,0)
                mapping.inputs['Scale'].default_value = (sx,sy,1)
                if rz != 0:
                    mapping.inputs['Rotation'].default_value = (0,0,rz)            
            if map and not map.invert and hasattr(mapping, "use_min"):
                mapping.use_min = mapping.use_max = 1
            return mapping
        return None


    def prune(self):
        marked = dict([(node.name, False) for node in self.nodes])
        if "Material Output" not in marked.keys():
            print("No output node")
            return
        marked["Material Output"] = True
        nmarked = 0
        n = 1
        while n > nmarked:
            nmarked = n
            n = 1
            for link in self.links:
                if marked[link.to_node.name]:
                    marked[link.from_node.name] = True
                    n += 1

        for node in self.nodes:
            node.select = False
            if not marked[node.name]:
                self.nodes.remove(node)

        if self.diffuseTex and marked[self.diffuseTex.name]:
            self.diffuseTex.select = True
            self.nodes.active = self.diffuseTex

#-------------------------------------------------------------
#   Bump
#-------------------------------------------------------------

    def buildBumpNodes(self, scn):
        # Column 3: Normal, Bump and Displacement

        # Normal map
        channel = self.material.getChannelNormal()
        if channel and self.material.isActive("Normal"):
            tex = self.addTexImageNode(channel, "NONE")
            #_,tex = self.getColorTex("getChannelNormal", "NONE", BLACK)
            if self.material.uv_set:
                uvname = self.material.uv_set.name
            else:
                uvname = ""
            if tex:
                if self.material.eevee:
                    from .cgroup import NormalGroup
                    self.normal = self.addGroup(NormalGroup, "DAZ Normal", 3, args=[uvname])
                else:
                    self.normal = self.addNode(3, "ShaderNodeNormalMap")
                    self.normal.space = "TANGENT"
                    if uvname:
                        self.normal.uv_map = uvname
                self.normal.inputs["Strength"].default_value = self.material.getChannelValue(channel, 1.0, warn=False)
                self.links.new(tex.outputs[0], self.normal.inputs["Color"])

        # Bump map
        channel = self.material.getChannelBump()
        if channel and self.material.isActive("Bump"):
            #tex = self.addTexImageNode(channel, "NONE")
            _,tex = self.getColorTex("getChannelBump", "NONE", 0, False)
            if tex:
                bump = self.addNode(3, "ShaderNodeBump")  
                strength = self.material.getChannelValue(channel, 1.0)
                if scn.DazLimitBump and strength > scn.DazMaxBump:
                    strength = scn.DazMaxBump
                bump.inputs["Strength"].default_value = strength
                bumpmin = self.material.getChannelValue(self.material.getChannelBumpMin(), -0.025)
                bumpmax = self.material.getChannelValue(self.material.getChannelBumpMax(), 0.025)
                bump.inputs["Distance"].default_value = (bumpmax-bumpmin) * theSettings.scale
                self.links.new(tex.outputs[0], bump.inputs["Height"])
                self.linkNormal(bump)
                self.normal = bump

    def linkNormal(self, node):
        if self.normal:
            self.links.new(self.normal.outputs["Normal"], node.inputs["Normal"])
    
#-------------------------------------------------------------
#   Diffuse and Diffuse Overlay
#-------------------------------------------------------------

    def getDiffuseColor(self):
        color,tex = self.getColorTex("getChannelDiffuse", "COLOR", WHITE)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect > 0:  # Scatter Transmit, Scatter Transmit Intensity
            tint = self.getColor(["SSS Reflectance Tint"], WHITE)
            color = compProd(color, tint)
        return color,tex

    
    def buildDiffuse(self, scn):
        channel = self.material.getChannelDiffuse()
        if channel:
            color,tex = self.getDiffuseColor()
            self.diffuseTex = tex
            self.diffuse = self.active = self.addNode(5, "ShaderNodeBsdfDiffuse")
            self.linkColor(tex, self.diffuse, color, "Color")
            roughness = clamp( self.getValue(["Diffuse Roughness"], scn.DazDiffuseRoughness) )
            self.addSlot(channel, self.diffuse, "Roughness", roughness, roughness, False)
            self.linkNormal(self.diffuse)
            theSettings.usedFeatures["Diffuse"] = True


    def buildOverlay(self):
        if self.getValue(["Diffuse Overlay Weight"], 0):
            weight,wttex = self.getColorTex(["Diffuse Overlay Weight"], "NONE", 0)
            if self.getValue(["Diffuse Overlay Weight Squared"], False):
                power = 4
            else:
                power = 2
            if wttex:
                if wttex.type == 'TEX_IMAGE':
                    img = wttex.image                    
                    useAlpha = (img.file_format in ['PNG'])
                else:
                    useAlpha = False
                wttex = self.raiseToPower(wttex, power, 3, useAlpha=useAlpha)
            color,tex = self.getColorTex(["Diffuse Overlay Color"], "COLOR", WHITE)
            node = self.addNode(5, "ShaderNodeBsdfDiffuse")
            self.linkColor(tex, node, color, "Color")
            roughness,roughtex = self.getColorTex(["Diffuse Overlay Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkNormal(node)
            self.mixWithActive(weight**power, wttex, node, col=6)


    def raiseToPower(self, tex, power, col, useAlpha=True):
        node = self.addNode(col, "ShaderNodeMath")
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if useAlpha and "Alpha" in tex.outputs.keys():
            slot = "Alpha"
        else:
            slot = 0
        self.links.new(tex.outputs[slot], node.inputs[0])
        return node


    def getColorTex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None):
        channel = self.material.getChannel(attr)
        if channel is None:
            return default,None
        if isinstance(channel, tuple):
            channel = channel[0]
        if useTex:
            tex = self.addTexImageNode(channel, colorSpace)
        else:
            tex = None
        if value is not None:
            pass
        elif colorSpace == "COLOR":
            value = self.material.getChannelColor(channel, default)
        else:
            value = self.material.getChannelValue(channel, default)
            if value < 0:
                return 0,None
        if useFactor:
            value,tex = self.multiplyTex(value, tex)
        if isVector(value) and not isVector(default):
            value = (value[0] + value[1] + value[2])/3
        if not isVector(value) and maxval and value > maxval:
            value = maxval
        return value,tex

#-------------------------------------------------------------
#   Glossiness
#   https://bitbucket.org/Diffeomorphic/import-daz-archive/issues/134/ultimate-specularity-matching-fresnel
#-------------------------------------------------------------

    def getGlossyColor(self):
        if not isWhite(self.glossyColor) or self.glossyTex:
            return self.glossyColor, self.glossyTex

        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength,strtex = self.getColorTex("getChannelSpecularStrength", "NONE", 1.0, False)
        color,tex = self.getColorTex("getChannelSpecularColor", "COLOR", WHITE, False)
        color = strength*color
        if tex and strtex:
            tex = self.multiplyTexs(tex, strtex)
        elif strtex:
            tex = strtex
        if tex:
            tex = self.multiplyVectorTex(color, tex)
        self.glossyColor,self.glossyTex = color,tex
        return color,tex


    def buildDualLobe(self):
        from .cgroup import DualLobeGroup
        self.dualLobe = self.addGroup(DualLobeGroup, "DAZ Dual Lobe", 7)

        value,tex = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 0.5, False)
        self.dualLobe.inputs["Weight"].default_value = value
        if tex:
            wttex = self.multiplyScalarTex(value, tex)
            if wttex:
                self.links.new(wttex.outputs[0], self.dualLobe.inputs["Weight"])

        value,tex = self.getColorTex(["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        self.dualLobe.inputs["IOR"].default_value = 1.1 + 0.7*value
        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.links.new(iortex.outputs[0], self.dualLobe.inputs["IOR"])

        value,tex = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
        self.setRoughness(self.dualLobe, "Roughness 1", value, tex)

        value,tex = self.getColorTex(["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
        self.setRoughness(self.dualLobe, "Roughness 2", value, tex)

        fac = self.getValue(["Dual Lobe Specular Ratio"], 1.0)
        self.dualLobe.inputs["Fac"].default_value = fac

        self.linkNormal(self.dualLobe)
        theSettings.usedFeatures["Glossy"] = True


    def buildGlossy(self):
        color,tex = self.getGlossyColor()
        if isBlack(color):
            return
        self.glossy = self.addNode(5, "ShaderNodeBsdfGlossy")
        self.glossy.inputs["Color"].default_value[0:3] = color
        if tex:
            self.links.new(tex.outputs[0], self.glossy.inputs[0])

        #   self.glossy bsdf roughness = iray self.glossy roughness ^ 2
        channel,invert = self.material.getChannelGlossiness()
        invert = not invert             # roughness = invert glossiness
        value = clamp( self.material.getChannelValue(channel, 0.0) )
        if invert:
            roughness = (1-value)
        else:
            roughness = value
        fnroughness = roughness**2
        if bpy.app.version < (2,80):
            roughness = roughness**2
            value = value**2
        roughtex = self.addSlot(channel, self.glossy, "Roughness", roughness, value, invert)
        self.linkNormal(self.glossy)

        from .cgroup import FresnelGroup
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel", 5)
        ior,iortex = self.getFresnelIOR()
        fresnel.inputs["IOR"].default_value = ior
        fresnel.inputs["Roughness"].default_value = fnroughness
        if iortex:
            self.links.new(iortex.outputs[0], fresnel.inputs["IOR"])
        if roughtex:
            self.links.new(roughtex.outputs[0], fresnel.inputs["Roughness"])
        self.linkNormal(fresnel)
        self.fresnel = fresnel
        theSettings.usedFeatures["Glossy"] = True


    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray self.glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray self.glossy specular / 0.078
        ior = 1.45
        iortex = None
        if self.material.shader == 'IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                value,tex = self.getColorTex("getChannelGlossyReflectivity", "NONE", 0, False)
                factor = 0.7 * value
            elif self.material.basemix == 1:  # Specular/Glossiness
                color,tex = self.getColorTex("getChannelGlossySpecular", "COLOR", WHITE, False)
                factor = 0.7 * averageColor(color) / 0.078
            ior = 1.1 + factor
            if tex:
                iortex = self.multiplyAddScalarTex(factor, 1.1, tex)
        return ior, iortex


    def linkGlossy(self):
        if self.dualLobe:
            self.links.new(self.active.outputs[0], self.dualLobe.inputs["Shader"])
            if self.glossy:
                mix = self.addMixShader(6, 0.5, None, None, self.fresnel, self.active, self.glossy)
                self.active = self.addMixShader(6, self.material.dualLobeWeight, None, None, None, mix, self.dualLobe)
            else:
                self.active = self.dualLobe
            return

        if self.active and self.refraction:
            channel = self.material.getChannelRefractionStrength()
            strength = self.material.getChannelValue(channel, 0.0)
            imgfile = self.material.getImageFile(channel)
            node = self.addMixShader(6, strength, channel, imgfile, None, self.active, self.refraction)
        elif self.active:
            node = self.active
        elif self.refraction:
            node = self.refraction
        else:
            print("No node")
            print(self.material)
            node = None
        self.active = self.addMixShader(6, 0.5, None, None, self.fresnel, node, self.glossy)

#-------------------------------------------------------------
#   Top Coat
#-------------------------------------------------------------

    def buildTopCoat(self):
        topweight = self.getValue(["Top Coat Weight"], 0)
        if topweight == 0:
            return
        _,weighttex = self.getColorTex(["Top Coat Weight"], "NONE", 0, value=0.1*topweight)
        color,tex = self.getColorTex(["Top Coat Color"], "COLOR", WHITE)
        roughness,roughtex = self.getColorTex(["Top Coat Roughness"], "NONE", 0)
        if roughness == 0:
            glossiness,glosstex = self.getColorTex(["Top Coat Glossiness"], "NONE", 1)
            roughness = 1-glossiness
            roughtex = self.invertTex(glosstex, 5)
        
        top = self.addNode(6, "ShaderNodeBsdfGlossy")
        self.linkColor(tex, top, color, "Color") 
        self.linkScalar(roughtex, top, roughness, "Roughness")
        self.linkNormal(top)
        self.mixWithActive(0.1*topweight, weighttex, top, col=7)

#-------------------------------------------------------------
#   Translucency
#-------------------------------------------------------------

    def buildTranslucency(self, scn):
        if (self.material.refractive or
            not self.material.translucent or
            theSettings.handleVolumetric == "SSS"):
            return
        mat = self.material.rna
        color,tex = self.getColorTex("getChannelTranslucencyColor", "COLOR", WHITE)
        luc = self.addNode(5, "ShaderNodeBsdfTranslucent")
        luc.inputs["Color"].default_value[0:3] = color
        if tex:
            self.links.new(tex.outputs[0], luc.inputs[0])
        self.linkNormal(luc)
        fac,factex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect == 1: # Scatter and transmit
            fac = 0.5 + fac/2
            self.setMultiplier(factex, fac)
        self.mixWithActive(fac, factex, luc)
        theSettings.usedFeatures["Transparent"] = True


    def setMultiplier(self, node, fac):
        if node and node.type == 'MATH':
            node.inputs[0].default_value = fac
        
#-------------------------------------------------------------
#   Subsurface
#-------------------------------------------------------------

    def buildSubsurface(self, scn):
        if not self.material.sssActive(scn):
            return
        wt,wttex = self.getColorTex("getChannelSSSAmount", "NONE", 0)
        if wt > 0:
            sss = self.addNode(5, "ShaderNodeSubsurfaceScattering")
            color,tex = self.getColorTex("getChannelSSSColor", "COLOR", WHITE)
            if tex:
                self.linkColor(tex, sss, color, "Color")
            elif self.diffuseTex:
                self.linkColor(self.diffuseTex, sss, color, "Color")
            else:
                sss.inputs["Color"].default_value[0:3] = Vector(color)
            radius = self.getValue("getChannelSSSRadius", 1.0) * theSettings.scale
            sss.inputs["Radius"].default_value = (radius,radius,radius)
            scale = self.getValue("getChannelSSSScale", 1.0)
            sss.inputs["Scale"].default_value = scale * 0.1 * theSettings.scale
            self.linkNormal(sss)
            fac = clamp(wt/(1+wt))
            self.mixWithActive(wt, wttex, sss)
            theSettings.usedFeatures["Transparent"] = True

#-------------------------------------------------------------
#   Transparency
#-------------------------------------------------------------

    def multiplyColors(self, color, tex, color2, tex2):
        color = compProd(color, color2)
        if tex and tex2:
            tex = self.multiplyTexs(tex, tex2)
        elif tex2:
            tex = tex2
        return color,tex


    def getRefractionColor(self):
        if self.material.shareGlossy:
            color,tex = self.getColorTex("getChannelSpecularColor", "COLOR", WHITE)
            roughness, roughtex = self.getColorTex("getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        else:
            color,tex = self.getColorTex("getChannelRefractionColor", "COLOR", WHITE)
            roughness,roughtex = self.getColorTex(["Refraction Roughness"], "NONE", 0, False, maxval=1)
        return color, tex, roughness, roughtex


    def addInput(self, node, channel, slot, colorSpace, default, maxval=0):
        value,tex = self.getColorTex(channel, colorSpace, default, maxval=maxval)
        if isVector(default):
            node.inputs[slot].default_value[0:3] = value
        else:
            node.inputs[slot].default_value = value
        if tex:
            self.links.new(tex.outputs[0], node.inputs[slot])
        return value,tex


    def buildEeveeGlass(self):
        if theSettings.handleRefractive != 'EEVEE':
            return False
        mat = self.material
        if (not mat.refractive or
            (mat.shader == 'IRAY' and not mat.thinWalled)):
            return False
        strength,imgfile,channel = self.getRefraction()
        if strength > 0 or imgfile:
            self.material.alphaBlend(1-strength, imgfile)
            fresnel = self.addNode(3, "ShaderNodeFresnel")
            ior,iortex = self.getFresnelIOR()
            fresnel.inputs["IOR"].default_value = ior
            transp = self.addNode(3, "ShaderNodeBsdfTransparent")
            glossy = self.addNode(3, "ShaderNodeBsdfGlossy")
            glossy.inputs["Color"].default_value[0:3] = WHITE
            glossy.inputs["Roughness"].default_value = 0.05
            alpha = 0.05
            self.active = self.addMixShader(4, alpha, channel, None, fresnel, transp, glossy)
            self.buildOutput()
            self.prune()
            theSettings.usedFeatures["Transparent"] = True
            return True
        else:
            return False


    def getRefraction(self):
        channel = self.material.getChannelRefractionStrength()
        if channel:
            strength = self.material.getChannelValue(channel, 0.0)
            imgfile = self.material.getImageFile(channel)
        else:
            strength = 0
            imgfile = None
        return strength,imgfile,channel


    def setRoughness(self, node, channel, roughness, roughtex, square=True):
        if square and bpy.app.version < (2,80,0):
            roughness = roughness * roughness
        node.inputs[channel].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[channel])


    def buildRefraction(self):
        strength,imgfile,channel = self.getRefraction()
        if strength > 0 or imgfile:
            node = self.addNode(5, "ShaderNodeBsdfRefraction")
            self.material.alphaBlend(1-strength, imgfile)
            color,tex,roughness,roughtex = self.getRefractionColor()
            node.inputs["Color"].default_value[0:3] = color
            if tex:
                self.links.new(tex.outputs[0], node.inputs["Color"])

            if self.material.thinWalled:
                roughness = 0
                roughtex = None
            self.setRoughness(node, "Roughness", roughness, roughtex)

            ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
            if self.material.thinWalled:
                node.inputs["IOR"].default_value = 1.0
            else:
                node.inputs["IOR"].default_value = ior
                if iortex:
                    self.links.new(iortex.outputs[0], node.inputs["IOR"])

            if self.fresnel:
                self.fresnel.inputs["IOR"].default_value = ior
                if iortex:
                    self.links.new(iortex.outputs[0], self.fresnel.inputs["IOR"])
                else:
                    self.removeLink(self.fresnel, "IOR")

            self.linkNormal(node)
            self.refraction = node
            theSettings.usedFeatures["Transparent"] = True


    def buildCutout(self):
        channel = self.material.getChannelCutoutOpacity()
        if channel:
            alpha = self.material.getChannelValue(channel, 1.0)
            imgfile = self.material.getImageFile(channel)
            if imgfile or alpha < 1:
                self.useCutout = True
                node = self.addNode(3, "ShaderNodeBsdfTransparent")
                self.material.alphaBlend(alpha, imgfile)
                #node.inputs["Color"].default_value[0:3] = (value,value,value)
                self.active = self.addMixShader(5, alpha, channel, imgfile, None, node, self.active)
                theSettings.usedFeatures["Transparent"] = True

#-------------------------------------------------------------
#   Emission
#-------------------------------------------------------------

    def buildEmission(self, scn):
        if not scn.DazUseEmission:
            return
        color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
        if (color != BLACK): 
            emit = self.addNode(6, "ShaderNodeEmission")
            emit.inputs["Color"].default_value[0:3] = color
            if tex:
                self.linkColor(tex, emit, color)
            else:
                channel = self.material.getChannel(["Luminance"])
                if channel:
                    tex = self.addTexImageNode(channel, "COLOR")
                    self.linkColor(tex, emit, color)

            lum = self.getValue(["Luminance"], 1500)
            # "cd/m^2", "kcd/m^2", "cd/ft^2", "cd/cm^2", "lm", "W"
            units = self.getValue(["Luminance Units"], 3)
            factors = [1, 1000, 10.764, 10000, 1, 1]
            strength = lum/2 * factors[units] / 15000
            if units >= 4:
                self.material.geosockets.append(emit.inputs["Strength"])
                if units == 5:
                    strength *= self.getValue(["Luminous Efficacy"], 1)
            emit.inputs["Strength"].default_value = strength

            twosided = self.getValue(["Two Sided Light"], False)
            if not twosided:
                geo = self.addNode(6, "ShaderNodeNewGeometry")
                trans = self.addNode(6, "ShaderNodeBsdfTransparent")
                mix = self.addNode(7, "ShaderNodeMixShader")
                self.links.new(geo.outputs["Backfacing"], mix.inputs[0])
                self.links.new(emit.outputs[0], mix.inputs[1])
                self.links.new(trans.outputs[0], mix.inputs[2])
                emit = mix
            self.addToActive(emit, 8)


    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)


    def buildVolume(self):
        if (self.material.thinWalled or 
            self.material.eevee or
            theSettings.handleVolumetric != "VOLUMETRIC"):
            return

        transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            ssscolor,ssstex = self.getColorTex(["SSS Color", "Subsurface Color"], "COLOR", BLACK)
            # https://bitbucket.org/Diffeomorphic/import-daz/issues/27/better-volumes-minor-but-important-fixes
            switch = (transcolor[1] == 0 or ssscolor[1] == 0)
        else:
            switch = False

        absorb = None
        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
        if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
            if switch:
                color,tex = self.invertColor(transcolor, transtex, 6)
            else:
                color,tex = transcolor,transtex
            absorb = self.addNode(6, "ShaderNodeVolumeAbsorption")
            absorb.inputs["Density"].default_value = 200/dist
            self.linkColor(tex, absorb, color, "Color") 

        scatter = None
        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue(["Scattering Measurement Distance"], 0.0)
        if not (sssmode == 0 or isBlack(ssscolor) or isWhite(ssscolor) or dist == 0.0):
            if switch:
                color,tex = ssscolor,ssstex
            else:
                color,tex = self.invertColor(ssscolor, ssstex, 6)
            scatter = self.addNode(6, "ShaderNodeVolumeScatter")
            self.linkColor(tex, scatter, color, "Color")            
            scatter.inputs["Density"].default_value = 100/dist
            scatter.inputs["Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            scatter = self.addNode(6, "ShaderNodeVolumeScatter")
            sss,tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            color = (sss,sss,sss)
            self.linkColor(tex, scatter, color, "Color")
            scatter.inputs["Density"].default_value = 100/dist
            scatter.inputs["Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)

        if absorb and scatter:
            self.volume = self.addNode(7, "ShaderNodeAddShader")
            self.links.new(absorb.outputs[0], self.volume.inputs[0])
            self.links.new(scatter.outputs[0], self.volume.inputs[1])
        elif absorb:
            self.volume = absorb
        elif scatter:
            self.volume = scatter  
        theSettings.usedFeatures["Volume"] = True
            

    def buildOutput(self):
        output = self.addNode(8, "ShaderNodeOutputMaterial")
        if self.active:
            self.links.new(self.active.outputs[0], output.inputs["Surface"])
        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])
        if self.displacement:
            self.links.new(self.displacement.outputs[0], output.inputs["Displacement"])
        if self.liegroups:
            node = self.addNode(1, "ShaderNodeValue")
            node.outputs[0].default_value = 1.0
            for lie in self.liegroups:
                self.links.new(node.outputs[0], lie.inputs["Alpha"])


    def buildDisplacementNodes(self, scn):
        channel = self.material.getChannelDisplacement()
        if not( channel and
                self.material.isActive("Displacement") and
                scn.DazUseDisplacement):
            return
        tex = self.addTexImageNode(channel, "NONE")
        if tex:
            strength = self.material.getChannelValue(channel, 1)
            dmin = self.getValue("getChannelDispMin", -0.05)
            dmax = self.getValue("getChannelDispMax", 0.05)
            if strength == 0:
                return
            
            from .cgroup import DisplacementGroup
            node = self.addGroup(DisplacementGroup, "DAZ Displacement", 7)
            self.links.new(tex.outputs[0], node.inputs["Texture"])
            node.inputs["Strength"].default_value = theSettings.scale * strength
            node.inputs["Difference"].default_value = dmax - dmin
            node.inputs["Min"].default_value = dmin
            self.displacement = node


    def addMixShader(self, column, fac, channel, imgfile, slot0, slot1, slot2):
        if slot1 is None:
            return slot2
        elif slot2 is None:
            return slot1
        elif not (imgfile or slot0):
            if fac == 0:
                return slot1
            elif fac == 1:
                return slot2
        mix = self.addNode(column, "ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = fac
        if imgfile:
            tex = self.addTexImageNode(channel, "NONE")
            self.links.new(tex.outputs[0], mix.inputs["Fac"])
        elif slot0:
            self.links.new(slot0.outputs[0], mix.inputs["Fac"])
        self.links.new(slot1.outputs[0], mix.inputs[1])
        self.links.new(slot2.outputs[0], mix.inputs[2])
        return mix


    def getLinkFrom(self, node, name):
        mat = self.material.rna
        for link in mat.node_tree.links:
            if (link.to_node == node and
                link.to_socket.name == name):
                return link.from_node
        return None


    def getLinkTo(self, node, name):
        mat = self.material.rna
        for link in mat.node_tree.links:
            if (link.from_node == node and
                link.from_socket.name == name):
                return link.to_node
        return None


    def addSingleTexture(self, col, asset, map, colorSpace):
        isnew = False
        img = asset.buildCycles(colorSpace)
        if img:
            key = img.name
            hasMap = asset.hasMapping(map)
            texnode = self.getTexNode(key, colorSpace)
            if not hasMap and texnode:
                return texnode, False
            else:
                texnode = self.addNode(col, "ShaderNodeTexImage")
                texnode.image = img
                self.setColorSpace(texnode, colorSpace)
                texnode.name = img.name
                isnew = True
                if not hasMap:
                    self.setTexNode(key, texnode, colorSpace)
        else:
            texnode = self.addNode(col, "ShaderNodeRGB")
            texnode.outputs["Color"].default_value[0:3] = asset.map.color
        return texnode, isnew


    def setColorSpace(self, node, colorSpace):
        if hasattr(node, "color_space"):
            node.color_space = colorSpace


    def getTexNode(self, key, colorSpace):
        if key in self.texnodes.keys():
            for texnode,colorSpace1 in self.texnodes[key]:
                if colorSpace1 == colorSpace:
                    return texnode
        return None


    def setTexNode(self, key, texnode, colorSpace):
        if key not in self.texnodes.keys():
            self.texnodes[key] = []
        self.texnodes[key].append((texnode, colorSpace))


    def linkVector(self, texco, node, slot="Vector"):
        if isinstance(texco, bpy.types.NodeSocketVector):
            self.links.new(texco, node.inputs[slot])
            return
        if "Vector" in texco.outputs.keys():
            self.links.new(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.links.new(texco.outputs["UV"], node.inputs[slot])


    def addTexImageNode(self, channel, colorSpace):
        assets,maps = self.material.getTextures(channel)
        if len(assets) != len(maps):
            print(assets)
            print(maps)
            raise DazError("Bug: Num assets != num maps")
        elif len(assets) == 0:
            return None
        elif len(assets) == 1:
            texnode,isnew = self.addSingleTexture(2, assets[0], maps[0], colorSpace)
            if isnew:
                self.linkVector(self.texco, texnode)
            return texnode

        from .cgroup import LieGroup
        node = self.addNode(2, "ShaderNodeGroup")
        try:
            name = os.path.basename(assets[0].map.url)
        except:
            name = "Group"
        group = LieGroup(node, name, self)
        self.linkVector(self.texco, node)        
        group.addTextureNodes(assets, maps, colorSpace)
        node.inputs["Alpha"].default_value = 1
        self.liegroups.append(node)
        return node


    def multiplyTexs(self, tex1, tex2, slot1=0, slot2=0, col=3):
        if tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1
        mix = self.addNode(col, "ShaderNodeMixRGB")
        mix.blend_type = 'MULTIPLY'
        mix.use_alpha = False
        mix.inputs[0].default_value = 1.0
        self.links.new(tex1.outputs[slot1], mix.inputs[1])
        self.links.new(tex2.outputs[slot2], mix.inputs[2])
        return mix


    def addToActive(self, shader, col=6):
        if self.active:
            if shader:
                add = self.addNode(col, "ShaderNodeAddShader")
                self.links.new(self.active.outputs[0], add.inputs[0])
                self.links.new(shader.outputs[0], add.inputs[1])
                self.active = add
        else:
            self.active = shader


    def mixWithActive(self, fac, tex, shader, col=6, useAlpha=True):
        if fac == 0:
            return
        elif fac == 1 and tex is None:
            self.active = shader
            return
        if self.active:
            mix = self.addNode(col, "ShaderNodeMixShader")
            mix.inputs[0].default_value = fac
            if tex:
                if useAlpha and "Alpha" in tex.outputs.keys():
                    slot = "Alpha"
                else:
                    slot = 0
                self.links.new(tex.outputs[slot], mix.inputs[0])
            self.links.new(self.active.outputs[0], mix.inputs[1])
            self.links.new(shader.outputs[0], mix.inputs[2])
            self.active = mix
        else:
            self.active = shader


    def linkColor(self, tex, node, color, slot=0):
        node.inputs[slot].default_value[0:3] = color
        if tex:
            tex = self.multiplyVectorTex(color, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def linkScalar(self, tex, node, value, slot):
        node.inputs[slot].default_value = value
        if tex:
            tex = self.multiplyScalarTex(value, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def addSlot(self, channel, node, slot, value, value0, invert):
        node.inputs[slot].default_value = value
        tex = self.addTexImageNode(channel, "NONE")
        if tex:
            tex = self.fixTex(tex, value0, invert)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex


    def fixTex(self, tex, value, invert):
        _,tex = self.multiplyTex(value, tex)
        if invert:
            return self.invertTex(tex, 3)
        else:
            return tex


    def invertTex(self, tex, col):
        if tex:
            inv = self.addNode(col, "ShaderNodeInvert")
            self.links.new(tex.outputs[0], inv.inputs["Color"])
            return inv
        else:
            return None
    

    def multiplyTex(self, value, tex, col=3):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, col)
        elif tex:
            tex = self.multiplyVectorTex(value, tex, col)
        return value,tex


    def multiplyVectorTex(self, color, tex, col=3):
        if isWhite(color):
            return tex
        elif isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        mix = self.addNode(col, "ShaderNodeMixRGB")
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value[0:3] = color
        self.links.new(tex.outputs[0], mix.inputs[2])
        return mix


    def multiplyScalarTex(self, value, tex, col=3, slot=0):
        if value == 1:
            return tex
        elif value == 0:
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        mult = self.addNode(col, "ShaderNodeMath")
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.links.new(tex.outputs[slot], mult.inputs[1])
        return mult


    def addScalarTex(self, value, tex, col=4):
        if value == 0:
            return tex
        add = self.addNode(col, "ShaderNodeMath")
        add.operation = 'ADD'
        add.inputs[0].default_value = value
        if tex:
            self.links.new(tex.outputs[0], add.inputs[1])
        return add


    def multiplyAddScalarTex(self, factor, term, tex, col=3, slot=0):
        mult = self.addNode(col, "ShaderNodeMath")   
        try:
            mult.operation = 'MULTIPLY_ADD'        
            ok = True
        except TypeError:
            ok = False
        if ok:
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            mult.inputs[2].default_value = term
            return mult
        else:
            mult.operation = 'MULTIPLY'
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            add = self.addNode(col+1, "ShaderNodeMath")       
            add.operation = 'ADD'
            self.links.new(mult.outputs[slot], add.inputs[0])
            return add


def isEyeMaterial(mat):
    mname = mat.name.lower()
    for string in ["sclera"]:
        if string in mname:
            return True
    return False


def areEqualTexs(tex1, tex2):
    if tex1 == tex2:
        return True
    if tex1.type == 'TEX_IMAGE' and tex2.type == 'TEX_IMAGE':
        return (tex1.image == tex2.image)
    return False


def compProd(x, y):
    return (x[0]*y[0], x[1]*y[1], x[2]*y[2])
