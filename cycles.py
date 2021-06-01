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
        self.classType = CyclesMaterial
        self.tree = None
        self.useEevee = False


    def __repr__(self):
        treetype = None
        if self.tree:
            treetype = self.tree.type
        geoname = None
        if self.geometry:
            geoname = self.geometry.name
        return ("<%sMaterial %s r:%s g:%s i:%s t:%s>" % (treetype, self.id, self.rna, geoname, self.ignore, self.hasAnyTexture()))


    def guessColor(self):
        from .guess import guessMaterialColor
        guessMaterialColor(self.rna, GS.viewportColors, False)


    def build(self, context):
        if self.dontBuild():
            return
        Material.build(self, context)
        self.tree = self.setupTree()
        self.tree.build()


    def setupTree(self):
        from .pbr import PbrTree
        if self.isHair:
            from .hair import getHairTree
            geo = self.geometry
            if geo and geo.isStrandHair:
                geo.hairMaterials.append(self)
            return getHairTree(self)
        elif self.metallic:
            return PbrTree(self)
        elif GS.materialMethod == 'PRINCIPLED':
            return PbrTree(self)
        else:
            return CyclesTree(self)


    def postbuild(self):
        geonode = self.geometry
        if geonode and geonode.data and geonode.data.rna:
            geo = geonode.data
            me = geo.rna
            mnum = -1
            for mn,mat in enumerate(me.materials):
                if mat == self.rna:
                    mnum = mn
                    break
            if mnum < 0:
                return
            nodes = list(geo.nodes.values())
            if self.geoemit:
                self.correctEmitArea(nodes, me, mnum)
            if self.geobump:
                area = geo.getBumpArea(me, self.geobump.keys())
                self.correctBumpArea(area)
        if self.tree:
            self.tree.prune()


    def addGeoBump(self, tex, socket):
        bumpmin = self.getValue("getChannelBumpMin", -0.01)
        bumpmax = self.getValue("getChannelBumpMax", -0.01)
        socket.default_value = (bumpmax-bumpmin) * LS.scale
        key = tex.name
        if key not in self.geobump.keys():
            self.geobump[key] = (tex, [])
        self.geobump[key][1].append(socket)


    def correctBumpArea(self, area):
        if area <= 0.0:
            return
        for tex,sockets in self.geobump.values():
            img = tex.image
            if img is None:
                continue
            width,height = img.size
            density = width * height / area
            if density == 0.0:
                continue
            link = self.tree.getLinkTo(tex, "Vector")
            if link and link.from_node.type == 'MAPPING':
                scale = link.from_node.inputs["Scale"]
                density *= scale.default_value[0] * scale.default_value[1]
                if density == 0.0:
                    continue
            height = 3.0/math.sqrt(density)
            for socket in sockets:
                socket.default_value = height


    def correctEmitArea(self, nodes, me, mnum):
        ob = nodes[0].rna
        ob.data = me2 = me.copy()
        wmat = ob.matrix_world.copy()
        me2.transform(wmat)
        setWorldMatrix(ob, Matrix())
        area = sum([f.area for f in me2.polygons if f.material_index == mnum])
        ob.data = me
        setWorldMatrix(ob, wmat)
        bpy.data.meshes.remove(me2, do_unlink=True)

        area *= 1e-4/(LS.scale*LS.scale)
        for socket in self.geoemit:
            socket.default_value /= area
            for link in self.tree.links:
                if link.to_socket == socket:
                    node = link.from_node
                    if node.type == 'MATH':
                        node.inputs[0].default_value /= area


    def setTransSettings(self, useRefraction, useBlend, color, alpha):
        LS.usedFeatures["Transparent"] = True
        mat = self.rna
        if useBlend:
            mat.blend_method = 'BLEND'
            mat.show_transparent_back = False
        else:
            mat.blend_method = 'HASHED'
        mat.use_screen_refraction = useRefraction
        if hasattr(mat, "transparent_shadow_method"):
            mat.transparent_shadow_method = 'HASHED'
        else:
            mat.shadow_method = 'HASHED'
        mat.diffuse_color[0:3] = color
        mat.diffuse_color[3] = alpha

#-------------------------------------------------------------
#   Cycles node tree
#-------------------------------------------------------------

NCOLUMNS = 20
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
        self.bump = None
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


    def isEnabled(self, channel):
        return self.material.isEnabled(channel)


    def getColor(self, channel, default):
        return self.material.getColor(channel, default)


    def addNode(self, stype, col=None, size=0, label=None, parent=None):
        if col is None:
            col = self.column
        node = self.nodes.new(type = stype)
        node.location = ((col-2)*XSIZE, self.ycoords[col])
        self.ycoords[col] -= (YSIZE + size)
        if label:
            node.label = label
        if parent:
            node.parent = parent
        return node


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


    def addGroup(self, classdef, name, col=None, size=0, args=[], force=False):
        if col is None:
            col = self.column
        node = self.addNode("ShaderNodeGroup", col, size=size)
        group = classdef()
        if name in bpy.data.node_groups.keys() and not force:
            tree = bpy.data.node_groups[name]
            if group.checkSockets(tree):
                node.node_tree = tree
                return node
        group.create(node, name, self)
        group.addNodes(args)
        return node


    def addShellGroup(self, shell, push):
        shmat = shell.material
        shname = shell.name
        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
            shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.material.name))
            return None
        node = self.addNode("ShaderNodeGroup")
        node.width = 240
        nname = ("%s_%s" % (shname, self.material.name))
        node.name = nname
        node.label = shname
        if shell.tree:
            node.node_tree = shell.tree
            node.inputs["Influence"].default_value = 1.0
            return node
        elif shell.match and shell.match.tree:
            node.node_tree = shell.tree = shell.match.tree
            node.inputs["Influence"].default_value = 1.0
            return node
        if self.type == 'CYCLES':
            from .cgroup import ShellCyclesGroup
            group = ShellCyclesGroup(push)
        elif self.type == 'PBR':
            from .cgroup import ShellPbrGroup
            group = ShellPbrGroup(push)
        else:
            raise RuntimeError("Bug Cycles type %s" % self.type)
        group.create(node, nname, self)
        group.addNodes((shmat, shell.uv))
        node.inputs["Influence"].default_value = 1.0
        shell.tree = node.node_tree
        return node


    def build(self):
        self.makeTree()
        self.buildLayer("")
        self.buildCutout()
        self.buildVolume()
        self.buildDisplacementNodes()
        self.buildShells()
        self.buildOutput()


    def buildShells(self):
        shells = []
        n = 0
        for shell in self.material.shells.values():
            for geonode in shell.geometry.nodes.values():
                shells.append((geonode.push, n, shell))
                n += 1
        shells.sort()
        if shells:
            self.column += 1
        for push,n,shell in shells:
            node = self.addShellGroup(shell, push)
            if node:
                self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
                self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
                self.links.new(self.getTexco(shell.uv), node.inputs["UV"])
                if self.displacement:
                    self.links.new(self.displacement, node.inputs["Displacement"])
                self.cycles = self.eevee = node
                self.displacement = node.outputs["Displacement"]
                self.ycoords[self.column] -= 50


    def buildLayer(self, uvname):
        self.buildBumpNodes(uvname)
        self.buildDiffuse()

        self.buildTranslucency()
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
        self.buildEmission()
        return self.cycles


    def makeTree(self, slot="UV"):
        mat = self.material.rna
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        return self.addTexco(slot)


    def addTexco(self, slot):
        if self.material.useDefaultUvs:
            node = self.addNode("ShaderNodeTexCoord", 1)
            self.texco = node.outputs[slot]
        else:
            node = self.addNode("ShaderNodeUVMap", 1)
            node.uv_map = self.material.uv_set.name
            self.texco = node.outputs["UV"]

        mat = self.material
        ox = mat.getChannelValue(mat.getChannelHorizontalOffset(), 0)
        oy = mat.getChannelValue(mat.getChannelVerticalOffset(), 0)
        kx = mat.getChannelValue(mat.getChannelHorizontalTiles(), 1)
        ky = mat.getChannelValue(mat.getChannelVerticalTiles(), 1)
        if ox != 0 or oy != 0 or kx not in [0,1] or ky not in [0,1]:
            sx = sy = 1
            dx = dy = 0
            if kx != 0:
                sx = 1/kx
                dx = -ox/kx
            if ky != 0:
                sy = 1/ky
                dy = oy/ky
            self.mapping = self.addMappingNode((dx,dy,sx,sy,0), None)
            if self.mapping:
                self.linkVector(self.texco, self.mapping, 0)
                self.texco = self.mapping

        for key,uvset in self.material.uv_sets.items():
            self.addUvNode(key, uvset.name)
        return node


    def addUvNode(self, key, uvname):
        node = self.addNode("ShaderNodeUVMap", 1)
        node.uv_map = uvname
        slot = "UV"
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
        if GS.pruneNodes:
            from .material import pruneNodeTree
            marked = pruneNodeTree(self)
            if self.diffuseTex and marked[self.diffuseTex.name]:
                self.diffuseTex.select = True
                self.nodes.active = self.diffuseTex

#-------------------------------------------------------------
#   Bump
#-------------------------------------------------------------

    def buildBumpNodes(self, uvname):
        # Column 3: Normal, Bump and Displacement

        # Normal map
        channel = self.material.getChannelNormal()
        if channel and self.isEnabled("Normal"):
            tex = self.addTexImageNode(channel, "NONE")
            #_,tex = self.getColorTex("getChannelNormal", "NONE", BLACK)
            if not uvname and self.material.uv_set:
                uvname = self.material.uv_set.name
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
        self.bumpval,self.bumptex = self.getColorTex("getChannelBump", "NONE", 0, False)
        if self.bumpval and self.bumptex and self.isEnabled("Bump"):
            self.bump = self.buildBumpMap(self.bumpval, self.bumptex, col=3)
            self.linkNormal(self.bump)


    def buildBumpMap(self, bump, bumptex, col=3):
        node = self.addNode("ShaderNodeBump", col=col)
        node.inputs["Strength"].default_value = bump * GS.bumpFactor
        self.links.new(bumptex.outputs[0], node.inputs["Height"])
        self.material.addGeoBump(bumptex, node.inputs["Distance"])
        return node


    def linkBumpNormal(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])
        elif self.normal:
            self.links.new(self.normal.outputs["Normal"], node.inputs["Normal"])


    def linkBump(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])


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


    def buildDiffuse(self):
        channel = self.material.getChannelDiffuse()
        if channel and self.isEnabled("Diffuse"):
            self.column = 4
            color,tex = self.getDiffuseColor()
            self.diffuseTex = tex
            node = self.addNode("ShaderNodeBsdfDiffuse")
            self.cycles = self.eevee = node
            self.linkColor(tex, node, color, "Color")
            roughness,roughtex = self.getColorTex(["Diffuse Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkBumpNormal(node)
            LS.usedFeatures["Diffuse"] = True


    def buildOverlay(self):
        if self.getValue(["Diffuse Overlay Weight"], 0):
            self.column += 1
            slot = self.getImageSlot(["Diffuse Overlay Weight"])
            weight,wttex = self.getColorTex(["Diffuse Overlay Weight"], "NONE", 0, slot=slot)
            if self.getValue(["Diffuse Overlay Weight Squared"], False):
                power = 4
            else:
                power = 2
            if wttex:
                wttex = self.raiseToPower(wttex, power, slot)
            color,tex = self.getColorTex(["Diffuse Overlay Color"], "COLOR", WHITE)
            from .cgroup import DiffuseGroup
            node = self.addGroup(DiffuseGroup, "DAZ Overlay")
            self.linkColor(tex, node, color, "Color")
            roughness,roughtex = self.getColorTex(["Diffuse Overlay Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkBumpNormal(node)
            self.mixWithActive(weight**power, wttex, node)
            return True
        else:
            return False


    def getImageSlot(self, attr):
        if self.material.getImageMod(attr, "grayscale_mode") == "alpha":
            return "Alpha"
        else:
            return 0


    def raiseToPower(self, tex, power, slot):
        node = self.addNode("ShaderNodeMath", col=self.column-1)
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if slot not in tex.outputs.keys():
            slot = 0
        self.links.new(tex.outputs[slot], node.inputs[0])
        return node


    def getColorTex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None, slot=0):
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
        elif channel["type"] in ["color", "float_color"]:
            value = self.material.getChannelColor(channel, default)
        else:
            value = self.material.getChannelValue(channel, default)
            if value < 0:
                return 0,None
        if useFactor:
            value,tex = self.multiplySomeTex(value, tex, slot)
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
        from .cgroup import DualLobeGroupUberIray, DualLobeGroupPBRSkin
        if not self.isEnabled("Dual Lobe Specular"):
            return

        self.column += 1
        if self.material.shader == 'PBRSKIN':
            node = self.addGroup(DualLobeGroupPBRSkin, "DAZ Dual Lobe PBR", size=100)
        else:
            node = self.addGroup(DualLobeGroupUberIray, "DAZ Dual Lobe Uber", size=100)
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

        ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)
        if self.material.shader == 'PBRSKIN':
            roughness,roughtex = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            lobe2mult = self.getValue(["Specular Lobe 2 Roughness Mult"], 1.0)
            duallobemult = self.getValue(["Dual Lobe Specular Roughness Mult"], 1.0)
            self.setRoughness(node, "Roughness 1", roughness*duallobemult, roughtex)
            self.setRoughness(node, "Roughness 2", roughness*duallobemult*lobe2mult, roughtex)
            ratio = 1 - ratio
        else:
            roughness1,roughtex1 = self.getColorTex(["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 1", roughness1, roughtex1)
            roughness2,roughtex2 = self.getColorTex(["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 2", roughness2, roughtex2)

        self.linkBumpNormal(node)
        self.mixWithActive(ratio, None, node, keep=True)
        LS.usedFeatures["Glossy"] = True


    def getGlossyColor(self):
        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength,strtex = self.getColorTex("getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE, False)
        if tex and strtex:
            tex = self.mixTexs('MULTIPLY', tex, strtex)
        elif strtex:
            tex = strtex
        color = strength*color
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
        self.linkBumpNormal(fresnel)
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
        self.linkBumpNormal(glossy)
        self.linkScalar(roughtex, fresnel, fnroughness, "Roughness")

        LS.usedFeatures["Glossy"] = True
        self.mixWithActive(1.0, self.fresnel, glossy)


    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
        ior = 1.45
        iortex = None
        if self.material.shader == 'UBER_IRAY':
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
        if not self.isEnabled("Top Coat"):
            return
        topweight = self.getValue(["Top Coat Weight"], 0)
        if topweight == 0:
            return
        if self.material.shader == 'UBER_IRAY':
            # Top Coat Layering Mode
            #   [ "Reflectivity", "Weighted", "Fresnel", "Custom Curve" ]
            # Top Coat Bump Mode
            #   [ "Height Map", "Normal Map" ]
            refl,refltex = self.getColorTex(["Reflectivity"], "NONE", 0, useFactor=False)
            bump,bumptex = self.getColorTex(["Top Coat Bump"], "NONE", 0, useFactor=False)
        else:
            refl,refltex = self.getColorTex(["Top Coat Reflectivity"], "NONE", 0, useFactor=False)
            bump = self.getValue(["Top Coat Bump Weight"], 0)
            bump *= self.bumpval
            bumptex = None

        weight = 0.05 * topweight * refl
        _,tex = self.getColorTex(["Top Coat Weight"], "NONE", 0, value=weight)
        weighttex = self.multiplyTexs(tex, refltex)
        color,coltex = self.getColorTex(["Top Coat Color"], "COLOR", WHITE)
        roughness,roughtex = self.getColorTex(["Top Coat Roughness"], "NONE", 0)
        if roughness == 0:
            glossiness,glosstex = self.getColorTex(["Top Coat Glossiness"], "NONE", 1)
            roughness = 1-glossiness
            roughtex = self.invertTex(glosstex, 5)

        from .cgroup import TopCoatGroup
        self.column += 1
        top = self.addGroup(TopCoatGroup, "DAZ Top Coat", size=100)
        self.linkColor(coltex, top, color, "Color")
        self.linkScalar(roughtex, top, roughness, "Roughness")
        if self.material.shader == 'PBRSKIN':
            if self.bumptex:
                self.links.new(self.bumptex.outputs[0], top.inputs["Height"])
                self.material.addGeoBump(self.bumptex, top.inputs["Distance"])
        elif bumptex:
            self.links.new(bumptex.outputs[0], top.inputs["Height"])
            self.material.addGeoBump(bumptex, top.inputs["Distance"])
        top.inputs["Bump"].default_value = bump * GS.bumpFactor
        self.linkNormal(top)
        self.mixWithActive(weight, weighttex, top)

#-------------------------------------------------------------
#   Translucency
#-------------------------------------------------------------

    def checkTranslucency(self):
        if not self.isEnabled("Translucency"):
            return False
        if (self.material.thinWall or
            self.volume or
            self.material.translucent):
            return True
        if (self.material.refractive or
            not self.material.translucent):
            return False


    def buildTranslucency(self):
        if not self.checkTranslucency():
            return
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if fac == 0 and effect != 1:
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
        self.linkBumpNormal(node)
        fac,factex = self.getColorTex("getChannelTranslucencyWeight", "NONE", 0)
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
        if self.material.thinWall:
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
        if tex and tex2:
            tex = self.mixTexs('ADD', tex, tex2)
        elif tex2:
            tex = tex2
        color = Vector(color) + Vector(color2)
        return color,tex


    def multiplyColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self.mixTexs('MULTIPLY', tex, tex2)
        elif tex2:
            tex = tex2
        color = self.compProd(color, color2)
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


    def setRoughness(self, node, slot, roughness, roughtex, square=True):
        node.inputs[slot].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return roughness


    def buildRefraction(self):
        weight,wttex = self.getColorTex("getChannelRefractionWeight", "NONE", 0.0)
        if weight == 0:
            return
        node,color = self.buildRefractionNode()
        self.mixWithActive(weight, wttex, node)
        if GS.useFakeCaustics and not self.material.thinWall:
            from .cgroup import FakeCausticsGroup
            self.column += 1
            node = self.addGroup(FakeCausticsGroup, "DAZ Fake Caustics", args=[color], force=True)
            self.mixWithActive(weight, wttex, node, keep=True)


    def buildRefractionNode(self):
        from .cgroup import RefractionGroup
        self.column += 1
        node = self.addGroup(RefractionGroup, "DAZ Refraction", size=150)
        node.width = 240

        color,tex = self.getColorTex("getChannelGlossyColor", "COLOR", WHITE)
        roughness, roughtex = self.getColorTex("getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        roughness = roughness**2
        self.linkColor(tex, node, color, "Glossy Color")
        self.linkScalar(roughtex, node, roughness, "Glossy Roughness")

        color,coltex,roughness,roughtex = self.getRefractionColor()
        ior,iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
        roughness = roughness**2
        self.linkColor(coltex, node, color, "Refraction Color")
        self.linkScalar(iortex, node, ior, "Fresnel IOR")
        if self.material.thinWall:
            node.inputs["Thin Wall"].default_value = 1
            node.inputs["Refraction IOR"].default_value = 1.0
            node.inputs["Refraction Roughness"].default_value = 0.0
            self.material.setTransSettings(False, True, color, 0.1)
        else:
            node.inputs["Thin Wall"].default_value = 0
            self.linkScalar(roughtex, node, roughness, "Refraction Roughness")
            self.linkScalar(iortex, node, ior, "Refraction IOR")
            self.material.setTransSettings(True, False, color, 0.2)
        self.linkBumpNormal(node)
        return node, color


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
                self.mixWithActive(alpha, tex, node)
            node.inputs["Color"].default_value[0:3] = WHITE
            if alpha < 1 or tex:
                self.material.setTransSettings(False, False, WHITE, alpha)
            LS.usedFeatures["Transparent"] = True

    #-------------------------------------------------------------
    #   Emission
    #-------------------------------------------------------------

    def buildEmission(self):
        if not GS.useEmission:
            return
        color = self.getColor("getChannelEmissionColor", BLACK)
        if not isBlack(color):
            from .cgroup import EmissionGroup
            self.column += 1
            emit = self.addGroup(EmissionGroup, "DAZ Emission")
            self.addEmitColor(emit, "Color")
            strength = self.getLuminance(emit)
            emit.inputs["Strength"].default_value = strength
            self.links.new(self.getCyclesSocket(), emit.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), emit.inputs["Eevee"])
            self.cycles = self.eevee = emit
            self.addOneSided()


    def addEmitColor(self, emit, slot):
        color,tex = self.getColorTex("getChannelEmissionColor", "COLOR", BLACK)
        if tex is None:
            _,tex = self.getColorTex(["Luminance"], "COLOR", BLACK)
        temp = self.getValue(["Emission Temperature"], None)
        if temp is None:
            self.linkColor(tex, emit, color, slot)
            return
        elif temp == 0:
            temp = 6500
        blackbody = self.addNode("ShaderNodeBlackbody", self.column-2)
        blackbody.inputs["Temperature"].default_value = temp
        if isWhite(color) and tex is None:
            self.links.new(blackbody.outputs["Color"], emit.inputs[slot])
        else:
            mult = self.addNode("ShaderNodeMixRGB", self.column-1)
            mult.blend_type = 'MULTIPLY'
            mult.inputs[0].default_value = 1
            self.links.new(blackbody.outputs["Color"], mult.inputs[1])
            self.linkColor(tex, mult, color, 2)
            self.links.new(mult.outputs[0], emit.inputs[slot])


    def getLuminance(self, emit):
        lum = self.getValue(["Luminance"], 1500)
        # "cd/m^2", "kcd/m^2", "cd/ft^2", "cd/cm^2", "lm", "W"
        units = self.getValue(["Luminance Units"], 3)
        factors = [1, 1000, 10.764, 10000, 1, 1]
        strength = lum/2 * factors[units] / 15000
        if units >= 4:
            self.material.geoemit.append(emit.inputs["Strength"])
            if units == 5:
                strength *= self.getValue(["Luminous Efficacy"], 1)
        return strength


    def addOneSided(self):
        twosided = self.getValue(["Two Sided Light"], False)
        if not twosided:
            from .cgroup import OneSidedGroup
            node = self.addGroup(OneSidedGroup, "DAZ One-Sided")
            self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
            self.cycles = self.eevee = node

    #-------------------------------------------------------------
    #   Volume
    #-------------------------------------------------------------

    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)


    def buildVolume(self):
        if (self.material.thinWall or
            GS.materialMethod != "BSDF"):
            return
        useSSS = self.isEnabled("Sub Surface")
        useTrans = self.isEnabled("Transmission")
        if not (useSSS or useTrans):
            return
        transcolor,transtex = self.getColorTex(["Transmitted Color"], "COLOR", BLACK)
        sssmode, ssscolor, ssstex, switch = self.getSSSInfo(transcolor)
        self.volume = None
        if useTrans:
            self.buildVolumeTransmission(transcolor, transtex, switch)
        if useSSS:
            self.buildVolumeSubSurface(sssmode, ssscolor, ssstex, switch)
        if self.volume:
            self.volume.width = 240
            LS.usedFeatures["Volume"] = True


    def getSSSInfo(self, transcolor):
        if self.material.shader == 'UBER_IRAY':
            sssmode = self.getValue(["SSS Mode"], 0)
        elif self.material.shader == 'PBRSKIN':
            sssmode = 1
        else:
            sssmode = 0
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            ssscolor,ssstex = self.getColorTex("getChannelSSSColor", "COLOR", BLACK)
            # https://bitbucket.org/Diffeomorphic/import-daz/issues/27/better-volumes-minor-but-important-fixes
            switch = (transcolor[1] == 0 or ssscolor[1] == 0)
            return 1, ssscolor, ssstex, switch
        else:
            return 0, WHITE, None, False


    def buildVolumeTransmission(self, transcolor, transtex, switch):
        from .cgroup import VolumeGroup
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


    def buildVolumeSubSurface(self, sssmode, ssscolor, ssstex, switch):
        from .cgroup import VolumeGroup
        if self.material.shader == 'UBER_IRAY':
            factor = 50
        else:
            factor = 25

        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue("getChannelScatterDist", 0.0)
        if not (sssmode == 0 or isBlack(ssscolor) or isWhite(ssscolor) or dist == 0.0):
            if switch:
                color,tex = ssscolor,ssstex
            else:
                color,tex = self.invertColor(ssscolor, ssstex, 6)
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            if self.volume is None:
                self.volume = self.addGroup(VolumeGroup, "DAZ Volume")
            sss,tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            color = (sss,sss,sss)
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue(["SSS Direction"], 0)

    #-------------------------------------------------------------
    #   Output
    #-------------------------------------------------------------

    def buildOutput(self):
        self.column += 1
        output = self.addNode("ShaderNodeOutputMaterial")
        output.target = 'ALL'
        if self.cycles:
            self.links.new(self.getCyclesSocket(), output.inputs["Surface"])
        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])
        if self.displacement:
            self.links.new(self.displacement, output.inputs["Displacement"])
        if self.liegroups:
            node = self.addNode("ShaderNodeValue", col=self.column-1)
            node.outputs[0].default_value = 1.0
            for lie in self.liegroups:
                self.links.new(node.outputs[0], lie.inputs["Alpha"])

        if self.volume or self.eevee:
            output.target = 'CYCLES'
            outputEevee = self.addNode("ShaderNodeOutputMaterial")
            outputEevee.target = 'EEVEE'
            if self.eevee:
                self.links.new(self.getEeveeSocket(), outputEevee.inputs["Surface"])
            elif self.cycles:
                self.links.new(self.getCyclesSocket(), outputEevee.inputs["Surface"])
            if self.displacement:
                self.links.new(self.displacement, outputEevee.inputs["Displacement"])


    def buildDisplacementNodes(self):
        channel = self.material.getChannelDisplacement()
        if not( channel and
                self.material.isEnabled("Displacement") and
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
            node.inputs["Strength"].default_value = strength
            node.inputs["Max"].default_value = LS.scale * dmax
            node.inputs["Min"].default_value = LS.scale * dmin
            self.linkNormal(node)
            self.displacement = node.outputs["Displacement"]
            mat = self.material.rna
            mat.cycles.displacement_method = 'BOTH'


    def getLinkFrom(self, node, slot):
        for link in self.links:
            if (link.from_node == node and
                link.from_socket.name == slot):
                return link
        return None


    def getLinkTo(self, node, slot):
        for link in self.links:
            if (link.to_node == node and
                link.to_socket.name == slot):
                return link
        return None


    def addSingleTexture(self, col, asset, map, colorSpace):
        isnew = False
        img = asset.buildCycles(colorSpace)
        if img:
            imgname = img.name
        else:
            imgname = asset.getName()
        hasMap = asset.hasMapping(map)
        texnode = self.getTexNode(imgname, colorSpace)
        if not hasMap and texnode:
            return texnode, False
        else:
            texnode = self.addTextureNode(col, img, imgname, colorSpace)
            isnew = True
            if not hasMap:
                self.setTexNode(imgname, texnode, colorSpace)
        return texnode, isnew


    def addTextureNode(self, col, img, imgname, colorSpace):
        node = self.addNode("ShaderNodeTexImage", col)
        node.image = img
        node.label = imgname.rsplit("/",1)[-1]
        self.setColorSpace(node, colorSpace)
        node.name = imgname
        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1
        return node


    def setColorSpace(self, node, colorSpace):
        if hasattr(node, "color_space"):
            node.color_space = colorSpace


    def addImageTexNode(self, filepath, tname, col):
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        img.colorspace_settings.name = "Non-Color"
        return self.addTextureNode(col, img, tname, "NONE")


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
        if (isinstance(texco, bpy.types.NodeSocketVector) or
            isinstance(texco, bpy.types.NodeSocketFloat)):
            self.links.new(texco, node.inputs[slot])
            return
        if "Vector" in texco.outputs.keys():
            self.links.new(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.links.new(texco.outputs["UV"], node.inputs[slot])


    def addTexImageNode(self, channel, colorSpace=None):
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
        node.width = 240
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


    def mixTexs(self, op, tex1, tex2, slot1=0, slot2=0, color1=None, color2=None, fac=1, factex=None):
        if fac < 1 or factex:
            pass
        elif tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1
        mix = self.addNode("ShaderNodeMixRGB", self.column-1)
        mix.blend_type = op
        mix.use_alpha = False
        mix.inputs[0].default_value = fac
        if factex:
            self.links.new(factex.outputs[0], mix.inputs[0])
        if color1:
            mix.inputs[1].default_value[0:3] = color1
        if tex1:
            self.links.new(tex1.outputs[slot1], mix.inputs[1])
        if color2:
            mix.inputs[2].default_value[0:3] = color2
        if tex2:
            self.links.new(tex2.outputs[slot2], mix.inputs[2])
        return mix


    def mixWithActive(self, fac, tex, shader, useAlpha=False, keep=False):
        if shader.type != 'GROUP':
            raise RuntimeError("BUG: mixWithActive", shader.type)
        if fac == 0 and tex is None and not keep:
            return
        elif fac == 1 and tex is None and not keep:
            shader.inputs["Fac"].default_value = fac
            self.cycles = shader
            self.eevee = shader
            return
        if self.eevee:
            self.makeActiveMix("Eevee", self.eevee, self.getEeveeSocket(), fac, tex, shader, useAlpha)
        self.eevee = shader
        if self.cycles:
            self.makeActiveMix("Cycles", self.cycles, self.getCyclesSocket(), fac, tex, shader, useAlpha)
        self.cycles = shader


    def makeActiveMix(self, slot, active, socket, fac, tex, shader, useAlpha):
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
        _,tex = self.multiplySomeTex(value, tex)
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


    def multiplySomeTex(self, value, tex, slot=0):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, slot)
        elif tex:
            tex = self.multiplyVectorTex(value, tex, slot)
        return value,tex


    def multiplyVectorTex(self, color, tex, slot=0, col=None):
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


    def multiplyScalarTex(self, value, tex, slot=0, col=None):
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


    def multiplyAddScalarTex(self, factor, term, tex, slot=0, col=None):
        if col is None:
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


    def multiplyTexs(self, tex1, tex2):
        if tex1 and tex2:
            mult = self.addNode("ShaderNodeMath")
            mult.operation = 'MULTIPLY'
            self.links.new(tex1.outputs[0], mult.inputs[0])
            self.links.new(tex2.outputs[0], mult.inputs[1])
            return mult
        elif tex1:
            return tex1
        else:
            return tex2

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def findTree(mat):
    from .cycles import CyclesTree
    tree = CyclesTree(None)
    tree.nodes = mat.node_tree.nodes
    tree.links = mat.node_tree.links
    return tree


def findTexco(tree, col):
    nodes = findNodes(tree, "TEX_COORD")
    if nodes:
        return nodes[0]
    else:
        return tree.addNode("ShaderNodeTexCoord", col)


def findNodes(tree, nodeType):
    nodes = []
    for node in tree.nodes.values():
        if node.type == nodeType:
            nodes.append(node)
    return nodes


def findNode(tree, ntypes):
    if isinstance(ntypes, list):
        for ntype in ntypes:
            node = findNode(tree, ntype)
            if node:
                return node
    for node in tree.nodes:
        if node.type == ntypes:
            return node
    return None


def findLinksFrom(tree, ntype):
    links = []
    for link in tree.links:
        if link.from_node.type == ntype:
            links.append(link)
    return links


def findLinksTo(tree, ntype):
    links = []
    for link in tree.links:
        if link.to_node.type == ntype:
            links.append(link)
    return links
