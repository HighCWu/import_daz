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
from .error import DazError
from .utils import *

#-------------------------------------------------------------
#   Cycles material
#-------------------------------------------------------------

class CyclesMaterial(Material):

    def __init__(self, fileref):
        Material.__init__(self, fileref)
        self.tree = None
        self.useEevee = False


    def __repr__(self):
        if self.tree:
            type = self.tree.type
        else:
            type = None
        return ("<%sMaterial %s r:%s g:%s i:%s t:%s>" % (type, self.id, self.rna, self.geometry, self.ignore, self.hasAnyTexture()))


    def build(self, context):
        if self.ignore or self.alreadyBuilt():
            return
        Material.build(self, context)
        self.tree = self.setupTree()
        self.tree.build(context)


    def setupTree(self):
        from .pbr import PbrTree
        if bpy.app.version >= (2, 78, 0):
            if self.geometry and self.geometry.polylines:
                from .hair import HairPBRTree, HairBSDFTree
                if False and LS.materialMethod == 'PRINCIPLED':
                    return HairPBRTree(self)
                else:
                    return HairBSDFTree(self)
            if self.metallic:
                return PbrTree(self)
            elif LS.materialMethod == 'PRINCIPLED':
                return PbrTree(self)
            else:
                return CyclesTree(self)
        else:
            return CyclesTree(self)


    def postbuild(self, context):
        geo = self.geometry
        scn = context.scene
        if (self.geosockets and geo and geo.rna):
            me = geo.rna
            mnum = 0
            for mn,mat in enumerate(me.materials):
                if mat == self.rna:
                    mnum = mn
                    break

            nodes = list(geo.nodes.values())
            if self.geosockets:
                self.correctArea(nodes, me, mnum)


    def correctArea(self, nodes, me, mnum):
        ob = nodes[0].rna
        ob.data = me2 = me.copy()
        wmat = ob.matrix_world.copy()
        me2.transform(mat)
        setWorldMatrix(ob, Matrix())
        area = sum([f.area for f in me2.polygons if f.material_index == mnum])
        ob.data = me
        setWorldMatrix(ob, wmat)
        bpy.data.meshes.remove(me2, do_unlink=True)

        area *= 1e-4/(LS.scale*LS.scale)
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

#-------------------------------------------------------------
#   Cycles node tree
#-------------------------------------------------------------

NCOLUMNS = 20
if bpy.app.version < (2,80,0):
    XSIZE = 250
    YSIZE = 250
else:
    XSIZE = 300
    YSIZE = 250


class CyclesTree:
    def __init__(self, cmat):
        self.type = 'CYCLES'
        self.material = cmat
        self.cycles = None
        self.eevee = None
        self.column = 4
        self.ycoords = NCOLUMNS*[2*YSIZE]
        self.texnodes = {}
        self.nodes = None
        self.links = None
        self.groups = {}
        self.liegroups = []

        self.diffuseTex = None
        self.fresnel = None
        self.normal = None
        self.texco = None
        self.texcos = {}
        self.mapping = None
        self.displacement = None
        self.volume = None
        self.useCutout = False
        self.useTranslucency = False


    def __repr__(self):
        return ("<Cycles %s %s %s>" % (self.material.rna, self.nodes, self.links))


    def getValue(self, channel, default):
        return self.material.getValue(channel, default)


    def getColor(self, channel, default):
        return self.material.getColor(channel, default)


    def addNode(self, stype, col=None, label=None, parent=None):
        if col is None:
            col = self.column
        node = self.nodes.new(type = stype)
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= YSIZE
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


    def getTexco(self, uv):
        key = self.material.getUvKey(uv, self.texcos)
        if key is None:
            return self.texco
        elif key not in self.texcos.keys():
            self.addUvNode(key, key)
        return self.texcos[key]


    def getCyclesSocket(self):
        if "Cycles" in self.cycles.outputs.keys():
            return self.cycles.outputs["Cycles"]
        else:
            return self.cycles.outputs[0]


    def getEeveeSocket(self):
        if "Eevee" in self.eevee.outputs.keys():
            return self.eevee.outputs["Eevee"]
        else:
            return self.eevee.outputs[0]


    def addGroup(self, classdef, name, col=None, size=0, args=[]):
        if col is None:
            col = self.column
        node = self.addNode("ShaderNodeGroup", col)
        if size:
            self.ycoords[col] -= size
        group = classdef()
        if name in bpy.data.node_groups.keys():
            tree = bpy.data.node_groups[name]
            if group.checkSockets(tree):
                node.node_tree = tree
                return node
        group.create(node, name, self)
        group.addNodes(args)
        return node


    def addShellGroup(self, context, shell):
        shmat = shell.material
        shname = shell.name
        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
            shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.material.name))
            return None
        node = self.addNode("ShaderNodeGroup")
        name = ("%s_%s" % (shname, self.material.name))
        node.name = name
        if self.type == 'CYCLES':
            from .cgroup import ShellCyclesGroup
            group = ShellCyclesGroup()
        elif self.type == 'PBR':
            from .cgroup import ShellPbrGroup
            group = ShellPbrGroup()
        else:
            raise RuntimeError("Bug Cycles type %s" % self.type)
        group.create(node, name, self)
        group.addNodes(context, shmat)
        LS.shellGroups.append((shmat, node.node_tree))
        return node


    def build(self, context):
        scn = context.scene
        self.makeTree()
        self.buildLayer(context)
        for shell in self.material.shells:
            node = self.addShellGroup(context, shell)
            if node:
                self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
                self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
                self.links.new(self.getTexco(shell.uv), node.inputs["UV"])
                self.cycles = self.eevee = node
        self.buildCutout()
        self.buildVolume()
        self.buildDisplacementNodes(scn)
        self.buildOutput()
        self.prune()


    def buildLayer(self, context):
        scn = context.scene
        self.buildBumpNodes(scn)
        self.buildDiffuse(scn)
        self.checkTranslucency()
        self.buildTranslucency(scn)
        self.buildOverlay()
        if self.material.dualLobeWeight == 1:
            self.buildDualLobe()
        elif self.material.dualLobeWeight == 0:
            self.buildGlossy()
        else:
            self.buildGlossy()
            self.buildDualLobe()
        if self.material.refractive:
            self.buildRefraction()
        self.buildTopCoat()
        self.buildEmission(scn)
        return self.cycles


    def makeTree(self, slot="UV"):
        mat = self.material.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.addTexco(slot)


    def addTexco(self, slot):
        node = self.addNode("ShaderNodeTexCoord", 1)
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
            node = self.addNode("ShaderNodeUVMap", 1)
            node.uv_map = uvname
            slot = "UV"
        else:
            node = self.addNode("ShaderNodeAttribute", 1)
            node.attribute_name = uvname
            slot = "Vector"
        self.texcos[key] = node.outputs[slot]


    def addMappingNode(self, data, map):
        dx,dy,sx,sy,rz = data
        if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            mapping = self.addNode("ShaderNodeMapping", 1)
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
        marked = {}
        output = False
        for node in self.nodes:
            marked[node.name] = False
            if "Output" in node.name:
                marked[node.name] = True
                output = True
        if not output:
            print("No output node")
            return
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
                if self.material.useEevee:
                    from .cgroup import NormalGroup
                    self.normal = self.addGroup(NormalGroup, "DAZ Normal", col=3, args=[uvname])
                else:
                    self.normal = self.addNode("ShaderNodeNormalMap", col=3)
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
                bump = self.addNode("ShaderNodeBump", col=3)
                strength = self.material.getChannelValue(channel, 1.0)
                if GS.limitBump and strength > GS.maxBump:
                    strength = GS.maxBump
                bump.inputs["Strength"].default_value = strength
                bumpmin = self.material.getChannelValue(self.material.getChannelBumpMin(), -0.01)
                bumpmax = self.material.getChannelValue(self.material.getChannelBumpMax(), 0.01)
                bump.inputs["Distance"].default_value = (bumpmax-bumpmin) * LS.scale
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
            color = self.compProd(color, tint)
        return color,tex


    def compProd(self, x, y):
        return [x[0]*y[0], x[1]*y[1], x[2]*y[2]]


    def buildDiffuse(self, scn):
        channel = self.material.getChannelDiffuse()
        if channel:
            self.column = 4
            color,tex = self.getDiffuseColor()
            self.diffuseTex = tex
            node = self.addNode("ShaderNodeBsdfDiffuse")
            self.cycles = self.eevee = node
            self.linkColor(tex, node, color, "Color")
            roughness = clamp( self.getValue(["Diffuse Roughness"], GS.diffuseRoughness) )
            self.addSlot(channel, node, "Roughness", roughness, roughness, False)
            self.linkNormal(node)
            LS.usedFeatures["Diffuse"] = True


    def buildOverlay(self):
        if self.getValue(["Diffuse Overlay Weight"], 0):
            self.column += 1
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
                wttex = self.raiseToPower(wttex, power, useAlpha=useAlpha)
            color,tex = self.getColorTex(["Diffuse Overlay Color"], "COLOR", WHITE)
            from .cgroup import DiffuseGroup
            node = self.addGroup(DiffuseGroup, "DAZ Overlay")
            self.linkColor(tex, node, color, "Color")
            roughness,roughtex = self.getColorTex(["Diffuse Overlay Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkNormal(node)
            self.mixWithActive(weight**power, wttex, node)
            return True
        else:
            return False


    def raiseToPower(self, tex, power, useAlpha=True):
        node = self.addNode("ShaderNodeMath", col=self.column-1)
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

    def buildDualLobe(self):
        from .cgroup import DualLobeGroup
        self.column += 1
        node = self.addGroup(DualLobeGroup, "DAZ Dual Lobe", size=100)

        value,tex = self.getColorTex(["Dual Lobe Specular Weight"], "NONE", 0.5, False)
        node.inputs["Weight"].default_value = value
        if tex:
            wttex = self.multiplyScalarTex(value, tex)
            if wttex:
                self.links.new(wttex.outputs[0], node.inputs["Weight"])

        value,tex = self.getColorTex(["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        node.inputs["IOR"].default_value = 1.1 + 0.7*value
        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.links.new(iortex.outputs[0], node.inputs["IOR"])

        value,tex = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
        self.setRoughness(node, "Roughness 1", value, tex)

        value,tex = self.getColorTex(["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
        self.setRoughness(node, "Roughness 2", value, tex)

        ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)

        self.linkNormal(node)
        self.mixWithActive(ratio, None, node)
        LS.usedFeatures["Glossy"] = True


    def getGlossyColor(self):
        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, False)
        color = strength*color
        if tex and strtex:
            tex = self.mixTexs('MULTIPLY', tex, strtex)
        elif strtex:
            tex = strtex
        if tex:
            tex = self.multiplyVectorTex(color, tex)
        return color,tex


    def buildGlossy(self):
        color = self.getColor("getChannelGlossyColor", BLACK)
        strength = self.getValue("getChannelGlossyLayeredWeight", 0)
        if isBlack(color) or strength == 0:
            return

        from .cgroup import FresnelGroup
        fresnel = self.addGroup(FresnelGroup, "DAZ Fresnel")
        ior,iortex = self.getFresnelIOR()
        self.linkScalar(iortex, fresnel, ior, "IOR")
        self.linkNormal(fresnel)
        self.fresnel = fresnel

        #   glossy bsdf roughness = iray glossy roughness ^ 2
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

        from .cgroup import GlossyGroup
        self.column += 1
        glossy = self.addGroup(GlossyGroup, "DAZ Glossy", size=100)
        color,tex = self.getGlossyColor()
        self.linkColor(tex, glossy, color, "Color")
        roughtex = self.addSlot(channel, glossy, "Roughness", roughness, value, invert)
        self.linkNormal(glossy)
        self.linkScalar(roughtex, fresnel, fnroughness, "Roughness")

        LS.usedFeatures["Glossy"] = True
        self.mixWithActive(1.0, self.fresnel, glossy, useAlpha=False)


    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
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

        from .cgroup import GlossyGroup
        self.column += 1
        top = self.addGroup(GlossyGroup, "DAZ Top Coat")
        self.linkColor(tex, top, color, "Color")
        self.linkScalar(roughtex, top, roughness, "Roughness")
        self.linkNormal(top)
        self.mixWithActive(0.1*topweight, weighttex, top)

#-------------------------------------------------------------
#   Translucency
#-------------------------------------------------------------

    def checkTranslucency(self):
        if (self.material.thinWalled or
            self.volume or
            self.material.translucent):
            self.useTranslucency = True
        if (self.material.refractive or
            not self.material.translucent):
            self.useTranslucency = False


    def buildTranslucency(self, scn):
        if not self.useTranslucency:
            return
        self.column += 1
        mat = self.material.rna
        color,tex = self.getColorTex("getChannelTranslucencyColor", "COLOR", WHITE)
        from .cgroup import TranslucentGroup
        node = self.addGroup(TranslucentGroup, "DAZ Translucent", size=100)
        self.linkColor(tex, node, color, "Color")
        node.inputs["Scale"].default_value = 1
        radius,radtex = self.getSSSRadius(color)
        self.linkColor(radtex, node, radius, "Radius")
        self.linkNormal(node)
        fac,factex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect == 1: # Scatter and transmit
            fac = 0.5 + fac/2
            self.setMultiplier(factex, fac)
        self.mixWithActive(fac, factex, node)
        LS.usedFeatures["Transparent"] = True
        self.endSSS()


    def setMultiplier(self, node, fac):
        if node and node.type == 'MATH':
            node.inputs[0].default_value = fac

#-------------------------------------------------------------
#   Subsurface
#-------------------------------------------------------------

    def endSSS(self):
        LS.usedFeatures["SSS"] = True
        mat = self.material.rna
        if hasattr(mat, "use_sss_translucency"):
            mat.use_sss_translucency = True


    def getSSSRadius(self, color):
        # if there's no volume we use the sss to make translucency
        # please note that here we only use the iray base translucency color with no textures
        # as for blender 2.8x eevee doesn't support nodes in the radius channel so we deal with it
        if self.material.thinWalled:
            return color,None

        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:    # Chromatic
            sss,ssstex = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            if isWhite(sss):
                sss = BLACK
        elif sssmode == 0:  # Mono
            s,ssstex = self.getColorTex("getChannelSSSAmount", "NONE", 0)
            if s > 1:
                s = 1
            sss = Vector((s,s,s))
        trans,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        if isWhite(trans):
            trans = BLACK

        rad,radtex = self.sumColors(sss, ssstex, trans, transtex)
        radius = rad * 2.0 * LS.scale
        return radius,radtex

#-------------------------------------------------------------
#   Transparency
#-------------------------------------------------------------

    def sumColors(self, color, tex, color2, tex2):
        color = Vector(color) + Vector(color2)
        if tex and tex2:
            tex = self.mixTexs('ADD', tex, tex2)
        elif tex2:
            tex = tex2
        return color,tex


    def multiplyColors(self, color, tex, color2, tex2):
        color = self.compProd(color, color2)
        if tex and tex2:
            tex = self.mixTexs('MULTIPLY', tex, tex2)
        elif tex2:
            tex = tex2
        return color,tex


    def getRefractionColor(self):
        if self.material.shareGlossy:
            color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
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


    def setRoughness(self, node, channel, roughness, roughtex, square=True):
        if square and bpy.app.version < (2,80,0):
            roughness = roughness * roughness
        node.inputs[channel].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[channel])


    def buildRefraction(self):
        ref = self.getValue("getChannelRefractionStrength", 0.0)
        if ref > 0:
            self.column += 1
            from .cgroup import RefractionGroup
            node = self.addGroup(RefractionGroup, "DAZ Refraction", size=150)
            node.width = 240

            color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
            roughness, roughtex = self.getColorTex("getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
            roughness = roughness**2
            self.linkColor(tex, node, color, "Glossy Color")
            self.linkScalar(roughtex, node, roughness, "Glossy Roughness")

            color,tex,roughness,roughtex = self.getRefractionColor()
            roughness = roughness**2
            self.linkColor(tex, node, color, "Refraction Color")
            ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
            self.linkScalar(iortex, node, ior, "Fresnel IOR")
            if self.material.thinWalled:
                node.inputs["Refraction IOR"].default_value = 1.0
                node.inputs["Refraction Roughness"].default_value = 0.0
            else:
                self.linkScalar(roughtex, node, roughness, "Refraction Roughness")
                self.linkScalar(iortex, node, ior, "Refraction IOR")

            self.linkNormal(node)
            ref,reftex = self.getColorTex("getChannelRefractionStrength", "NONE", 0.0)
            self.material.alphaBlend(1-ref, reftex)
            self.mixWithActive(ref, reftex, node)
            LS.usedFeatures["Transparent"] = True


    def buildCutout(self):
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        if alpha < 1 or tex:
            self.column += 1
            self.useCutout = True
            if alpha == 0:
                node = self.addNode("ShaderNodeBsdfTransparent")
                self.cycles = node
                self.eevee = node
                tex = None
            else:
                from .cgroup import TransparentGroup
                node = self.addGroup(TransparentGroup, "DAZ Transparent")
                self.mixWithActive(1-alpha, tex, node, useAlpha=False, flip=True)
            node.inputs["Color"].default_value[0:3] = WHITE
            self.material.alphaBlend(alpha, tex)
            LS.usedFeatures["Transparent"] = True

#-------------------------------------------------------------
#   Emission
#-------------------------------------------------------------

    def buildEmission(self, scn):
        if not GS.useEmission:
            return
        color = self.getColor("getChannelEmissionColor", BLACK)
        if not isBlack(color):
            from .cgroup import EmissionGroup
            self.column += 1
            #emit = self.addNode("ShaderNodeEmission")
            emit = self.addGroup(EmissionGroup, "DAZ Emission")
            self.links.new(self.getCyclesSocket(), emit.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), emit.inputs["Eevee"])
            self.cycles = self.eevee = emit
            color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
            self.linkColor(tex, emit, color, "Color")
            if tex is None:
                channel = self.material.getChannel(["Luminance"])
                if channel:
                    tex = self.addTexImageNode(channel, "COLOR")
                    self.linkColor(tex, emit, color, "Color")

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
                from .cgroup import OneSidedGroup
                node = self.addGroup(OneSidedGroup, "DAZ One-Sided")
                self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
                self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
                self.cycles = self.eevee = node


    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)


    def buildVolume(self):
        if (self.material.thinWalled or
            LS.materialMethod != "BSDF"):
            return

        from .cgroup import VolumeGroup
        transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            ssscolor,ssstex = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            # https://bitbucket.org/Diffeomorphic/import-daz/issues/27/better-volumes-minor-but-important-fixes
            switch = (transcolor[1] == 0 or ssscolor[1] == 0)
        else:
            switch = False

        self.volume = None
        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
        if not (isBlack(transcolor) or isWhite(transcolor) or dist == 0.0):
            if switch:
                color,tex = self.invertColor(transcolor, transtex, 6)
            else:
                color,tex = transcolor,transtex
            #absorb = self.addNode(6, "ShaderNodeVolumeAbsorption")
            self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            self.volume.inputs["Absorbtion Density"].default_value = 100/dist
            self.linkColor(tex, self.volume, color, "Absorbtion Color")

        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue("getChannelScatterDist", 0.0)
        if not (sssmode == 0 or isBlack(ssscolor) or isWhite(ssscolor) or dist == 0.0):
            if switch:
                color,tex = ssscolor,ssstex
            else:
                color,tex = self.invertColor(ssscolor, ssstex, 6)
            #scatter = self.addNode(6, "ShaderNodeVolumeScatter")
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = 50/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            #scatter = self.addNode(6, "ShaderNodeVolumeScatter")
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            sss,tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            color = (sss,sss,sss)
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = 50/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)

        if self.volume:
            self.volume.width = 240
            LS.usedFeatures["Volume"] = True


    def buildOutput(self):
        self.column += 1
        output = self.addNode("ShaderNodeOutputMaterial")
        if bpy.app.version >= (2,80,0):
            output.target = 'ALL'
        if self.cycles:
            self.links.new(self.getCyclesSocket(), output.inputs["Surface"])
        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])
        if self.displacement:
            self.links.new(self.displacement.outputs[0], output.inputs["Displacement"])
        if self.liegroups:
            node = self.addNode("ShaderNodeValue", col=self.column-1)
            node.outputs[0].default_value = 1.0
            for lie in self.liegroups:
                self.links.new(node.outputs[0], lie.inputs["Alpha"])

        if bpy.app.version >= (2,80,0) and (self.volume or self.eevee):
            output.target = 'CYCLES'
            outputEevee = self.addNode("ShaderNodeOutputMaterial")
            outputEevee.target = 'EEVEE'
            if self.eevee:
                self.links.new(self.getEeveeSocket(), outputEevee.inputs["Surface"])
            elif self.cycles:
                self.links.new(self.getCyclesSocket(), outputEevee.inputs["Surface"])
            if self.displacement:
                self.links.new(self.displacement.outputs[0], outputEevee.inputs["Displacement"])


    def buildDisplacementNodes(self, scn):
        channel = self.material.getChannelDisplacement()
        if not( channel and
                self.material.isActive("Displacement") and
                GS.useDisplacement):
            return
        tex = self.addTexImageNode(channel, "NONE")
        if tex:
            strength = self.material.getChannelValue(channel, 1)
            dmin = self.getValue("getChannelDispMin", -0.05)
            dmax = self.getValue("getChannelDispMax", 0.05)
            if strength == 0:
                return

            from .cgroup import DisplacementGroup
            node = self.addGroup(DisplacementGroup, "DAZ Displacement")
            self.links.new(tex.outputs[0], node.inputs["Texture"])
            node.inputs["Strength"].default_value = LS.scale * strength
            node.inputs["Difference"].default_value = dmax - dmin
            node.inputs["Min"].default_value = dmin
            self.displacement = node


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
                texnode = self.addTextureNode(col, img, colorSpace)
                isnew = True
                if not hasMap:
                    self.setTexNode(key, texnode, colorSpace)
        else:
            texnode = self.addNode("ShaderNodeRGB", col)
            texnode.outputs["Color"].default_value[0:3] = asset.map.color
        return texnode, isnew


    def addTextureNode(self, col, img, colorSpace):
        node = self.addNode("ShaderNodeTexImage", col)
        node.image = img
        self.setColorSpace(node, colorSpace)
        node.name = img.name
        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1
        return node


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
        col = self.column-2
        assets,maps = self.material.getTextures(channel)
        if len(assets) != len(maps):
            print(assets)
            print(maps)
            raise DazError("Bug: Num assets != num maps")
        elif len(assets) == 0:
            return None
        elif len(assets) == 1:
            texnode,isnew = self.addSingleTexture(col, assets[0], maps[0], colorSpace)
            if isnew:
                self.linkVector(self.texco, texnode)
            return texnode

        from .cgroup import LieGroup
        node = self.addNode("ShaderNodeGroup", col)
        try:
            name = os.path.basename(assets[0].map.url)
        except:
            name = "Group"
        group = LieGroup()
        group.create(node, name, self)
        self.linkVector(self.texco, node)
        group.addTextureNodes(assets, maps, colorSpace)
        node.inputs["Alpha"].default_value = 1
        self.liegroups.append(node)
        return node


    def mixTexs(self, op, tex1, tex2, slot1=0, slot2=0):
        if tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1
        mix = self.addNode("ShaderNodeMixRGB", self.column-1)
        mix.blend_type = op
        mix.use_alpha = False
        mix.inputs[0].default_value = 1.0
        self.links.new(tex1.outputs[slot1], mix.inputs[1])
        self.links.new(tex2.outputs[slot2], mix.inputs[2])
        return mix


    def mixWithActive(self, fac, tex, shader, useAlpha=True, flip=False):
        if shader.type != 'GROUP':
            raise RuntimeError("BUG: mixWithActive")
        if fac == 0 and tex is None:
            return
        elif fac == 1 and tex is None:
            shader.inputs["Fac"].default_value = fac
            self.cycles = shader
            self.eevee = shader
            return
        if self.eevee:
            self.makeActiveMix("Eevee", self.eevee, self.getEeveeSocket(), fac, tex, shader, useAlpha, flip)
        self.eevee = shader
        if self.cycles:
            self.makeActiveMix("Cycles", self.cycles, self.getCyclesSocket(), fac, tex, shader, useAlpha, flip)
        self.cycles = shader


    def makeActiveMix(self, slot, active, socket, fac, tex, shader, useAlpha, flip):
        self.links.new(socket, shader.inputs[slot])
        shader.inputs["Fac"].default_value = fac
        if tex:
            if useAlpha and "Alpha" in tex.outputs.keys():
                texsocket = tex.outputs["Alpha"]
            else:
                texsocket = tex.outputs[0]
            self.links.new(texsocket, shader.inputs["Fac"])


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
            inv = self.addNode("ShaderNodeInvert", col)
            self.links.new(tex.outputs[0], inv.inputs["Color"])
            return inv
        else:
            return None


    def multiplyTex(self, value, tex):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex)
        elif tex:
            tex = self.multiplyVectorTex(value, tex)
        return value,tex


    def multiplyVectorTex(self, color, tex, col=None):
        if isWhite(color):
            return tex
        elif isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mix = self.addNode("ShaderNodeMixRGB", col)
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value[0:3] = color
        self.links.new(tex.outputs[0], mix.inputs[2])
        return mix


    def multiplyScalarTex(self, value, tex, col=None, slot=0):
        if value == 1:
            return tex
        elif value == 0:
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.links.new(tex.outputs[slot], mult.inputs[1])
        return mult


    def multiplyAddScalarTex(self, factor, term, tex, slot=0):
        col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
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
            add = self.addNode("ShaderNodeMath", col)
            add.operation = 'ADD'
            add.inputs[1].default_value = term
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
