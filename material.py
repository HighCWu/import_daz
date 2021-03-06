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
import copy
import math
from collections import OrderedDict

from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .fileutils import MultiFile, ImageFile
from mathutils import Vector, Matrix

WHITE = Vector((1.0,1.0,1.0))
GREY = Vector((0.5,0.5,0.5))
BLACK = Vector((0.0,0.0,0.0))

#-------------------------------------------------------------
#   Materials
#-------------------------------------------------------------

class Material(Asset, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.classType = Material
        self.scene = None
        self.shader = 'UBER_IRAY'
        self.channels = OrderedDict()
        self.textures = OrderedDict()
        self.groups = []
        self.ignore = False
        self.force = False
        self.shells = {}
        self.geometry = None
        self.geoemit = []
        self.geobump = {}
        self.uv_set = None
        self.uv_sets = {}
        self.useDefaultUvs = True
        self.udim = 0
        self.basemix = 0
        self.thinWall = False
        self.refractive = False
        self.shareGlossy = False
        self.metallic = False
        self.dualLobeWeight = 0
        self.translucent = False
        self.isHair = False
        self.isShellMat = False
        self.enabled = {}


    def __repr__(self):
        return ("<Material %s %s %s>" % (self.id, self.geometry.name, self.rna))


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)


    def getMatName(self, id):
        id = unquote(id)
        key = id.split("#")[-1]
        words = key.rsplit("-",1)
        if (len(words) == 2 and
            words[1].isdigit()):
            return words[0]
        else:
            return key


    def addToGeoNode(self, geonode, key):
        if key in geonode.materials.keys():
            msg = ("Duplicate geonode material: %s\n" % key +
                   "  %s\n" % geonode +
                   "  %s\n" % geonode.materials[key] +
                   "  %s" % self)
            reportError(msg, trigger=(2,3))
        geonode.materials[key] = self
        self.geometry = geonode


    def update(self, struct):
        from .geometry import Geometry, GeoNode
        Asset.update(self, struct)
        Channels.update(self, struct)
        geo = geonode = None
        if "geometry" in struct.keys():
            ref = struct["geometry"]
            geo = self.getAsset(ref, True)
            if isinstance(geo, GeoNode):
                geonode = geo
                geo = geonode.data
            elif isinstance(geo, Geometry):
                iref = instRef(ref)
                if iref in geo.nodes.keys():
                    geonode = geo.nodes[iref]
            if geonode:
                key = self.getMatName(self.id)
                self.addToGeoNode(geonode, key)
        if "uv_set" in struct.keys():
            from .geometry import Uvset
            uvset = self.getTypedAsset(struct["uv_set"], Uvset)
            if uvset:
                uvset.material = self
                if geo and uvset != geo.default_uv_set:
                    geo.uv_sets[uvset.name] = uvset
                    self.useDefaultUvs = False
                self.uv_set = uvset
        self.basemix = self.getValue(["Base Mixing"], 0)
        if self.basemix == 2:
            self.basemix = 0
        elif self.basemix not in [0,1]:
            raise DazError("Unknown Base Mixing: %s             " % self.material.basemix)

        if self.shader == 'UBER_IRAY':
            self.enabled = {
                "Diffuse" : True,
                "Subsurface" : True,
                "Bump" : True,
                "Normal" : True,
                "Displacement" : True,
                "Metallicity" : True,
                "Translucency" : True,
                "Transmission" : True,
                "Dual Lobe Specular" : True,
                "Top Coat" : True,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : True,
                "Velvet" : False,
            }
        elif self.shader == 'PBRSKIN':
            self.enabled = {
                "Diffuse" : self.getValue(["Diffuse Enable"], False),
                "Subsurface" : self.getValue(["Sub Surface Enable"], False),
                "Bump" : self.getValue(["Bump Enable"], False),
                "Normal" : self.getValue(["Bump Enable"], False),
                "Displacement" : True,
                "Metallicity" : self.getValue(["Metallicity Enable"], False),
                "Translucency" : self.getValue(["Translucency Enable"], False),
                "Transmission" : self.getValue(["Transmission Enable"], False),
                "Dual Lobe Specular" : self.getValue(["Dual Lobe Specular Enable"], False),
                "Top Coat" : self.getValue(["Top Coat Enable"], False),
                "Makeup" : self.getValue(["Makeup Enable"], False),
                "Specular Occlusion" : self.getValue(["Specular Occlusion Enable"], False),
                "Detail" : self.getValue(["Detail Enable"], False),
                "Metallic Flakes" : self.getValue(["Metallic Flakes Enable"], False),
                "Velvet" : False,
            }
        elif self.shader == 'DAZ_SHADER':
            self.enabled = {
                "Diffuse" : self.getValue(["Diffuse Active"], False),
                "Subsurface" : self.getValue(["Subsurface Active"], False),
                "Bump" : self.getValue(["Bump Active"], False),
                "Normal" : False,
                "Displacement" : self.getValue(["Displacement Active"], False),
                "Metallicity" : self.getValue(["Metallicity Active"], False),
                "Translucency" : self.getValue(["Translucency Active"], False),
                "Transmission" : not self.getValue(["Opacity Active"], False),
                "Dual Lobe Specular" : False,
                "Top Coat" : False,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : False,
                "Velvet" : not self.getValue(["Velvet Active"], False),
            }
        elif self.shader == '3DELIGHT':
            self.enabled = {
                "Diffuse" : True,
                "Subsurface" : True,
                "Bump" : True,
                "Normal" : True,
                "Displacement" : True,
                "Metallicity" : False,
                "Translucency" : True,
                "Transmission" : True,
                "Dual Lobe Specular" : False,
                "Top Coat" : False,
                "Makeup" : False,
                "Specular Occlusion" : False,
                "Detail" : False,
                "Metallic Flakes" : False,
                "Velvet" : True,
        }
        else:
            raise DazError("Bug: Unknown shader %s" % self.shader)

        self.thinWall = self.getValue(["Thin Walled"], False)
        self.refractive = (self.getValue("getChannelRefractionWeight", 0) > 0.01 or
                           self.getValue("getChannelOpacity", 1) < 0.99)
        self.shareGlossy = self.getValue(["Share Glossy Inputs"], False)
        self.metallic = (self.getValue(["Metallic Weight"], 0) > 0.5 and self.enabled["Metallicity"])
        self.dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
        self.translucent = (self.enabled["Translucency"] and self.getValue("getChannelTranslucencyWeight", 0) > 0.01)
        self.isHair = ("Root Transmission Color" in self.channels.keys())


    def setExtra(self, struct):
        if struct["type"] == "studio/material/uber_iray":
            self.shader = 'UBER_IRAY'
        elif struct["type"] == "studio/material/daz_brick":
            if self.url.split("#")[-1] == "PBRSkin":
                self.shader = 'PBRSKIN'
            else:
                self.shader = '3DELIGHT'
        elif struct["type"] == "studio/material/daz_shader":
            self.shader = 'DAZ_SHADER'


    def build(self, context):
        from .geometry import Geometry, GeoNode
        if self.dontBuild():
            return
        mat = self.rna
        if mat is None:
            mat = self.rna = bpy.data.materials.new(self.name)
            LS.materials[mat.name] = mat
        scn = self.scene = context.scene
        mat.DazRenderEngine = scn.render.engine
        mat.DazShader = self.shader
        if self.uv_set:
            self.uv_sets[self.uv_set.name] = self.uv_set
        geonode = self.geometry
        if (isinstance(geonode, GeoNode) and
            geonode.data and
            geonode.data.uv_sets):
            for uv,uvset in geonode.data.uv_sets.items():
                if uvset:
                    self.uv_sets[uv] = self.uv_sets[uvset.name] = uvset
        for shell in self.shells.values():
            shell.material.shader = self.shader


    def dontBuild(self):
        if self.ignore:
            return True
        elif self.force:
            return False
        elif GS.reuseMaterials and self.name in bpy.data.materials.keys():
            self.rna = bpy.data.materials[self.name]
            return True
        elif self.geometry:
            return (not self.geometry.isVisibleMaterial(self))
        return False


    def postbuild(self):
        if LS.useMaterials:
            self.guessColor()


    def guessColor(self):
        return


    def getUvKey(self, key, struct):
        if key not in struct.keys():
            print("Missing UV for '%s', '%s' not in %s" % (self.getLabel(), key, list(struct.keys())))
        return key


    def getUvSet(self, uv):
        key = self.getUvKey(uv, self.uv_sets)
        if key is None:
            return self.uv_set
        elif key not in self.uv_sets.keys():
            uvset = Asset(None)
            uvset.name = key
            self.uv_sets[key] = uvset
        return self.uv_sets[key]


    def fixUdim(self, context, udim):
        mat = self.rna
        if mat is None:
            return
        try:
            mat.DazUDim = udim
        except ValueError:
            print("UDIM out of range: %d" % udim)
        mat.DazVDim = 0
        addUdim(mat, udim, 0)


    def getGamma(self, channel):
        url = self.getImageFile(channel)
        gamma = 0
        if url in LS.gammas.keys():
            gamma = LS.gammas[url]
        elif "default_image_gamma" in channel.keys():
            gamma = channel["default_image_gamma"]
        return gamma

#-------------------------------------------------------------
#   Get channels
#-------------------------------------------------------------

    def getChannelDiffuse(self):
        return self.getChannel(["diffuse", "Diffuse Color"])

    def getDiffuse(self):
        return self.getColor("getChannelDiffuse", BLACK)

    def getChannelDiffuseStrength(self):
        return self.getChannel(["diffuse_strength", "Diffuse Strength"])

    def getChannelDiffuseRoughness(self):
        return self.getChannel(["Diffuse Roughness"])

    def getChannelGlossyColor(self):
        return self.getTexChannel(["Glossy Color", "specular", "Specular Color"])

    def getChannelGlossyLayeredWeight(self):
        return self.getTexChannel(["Glossy Layered Weight", "Glossy Weight", "specular_strength", "Specular Strength"])

    def getChannelGlossyReflectivity(self):
        return self.getChannel(["Glossy Reflectivity"])

    def getChannelGlossyRoughness(self):
        return self.getChannel(["Glossy Roughness"])

    def getChannelGlossySpecular(self):
        return self.getChannel(["Glossy Specular"])

    def getChannelGlossiness(self):
        channel = self.getChannel(["glossiness", "Glossiness"])
        if channel:
            return channel, False
        else:
            return self.getChannel(["Glossy Roughness"]), True

    def getChannelOpacity(self):
        return self.getChannel(["opacity", "Opacity Strength"])

    def getChannelCutoutOpacity(self):
        return self.getChannel(["Cutout Opacity", "transparency"])

    def getChannelAmbientColor(self):
        return self.getChannel(["ambient", "Ambient Color"])

    def getChannelAmbientStrength(self):
        return self.getChannel(["ambient_strength", "Ambient Strength"])

    def getChannelEmissionColor(self):
        return self.getChannel(["emission", "Emission Color"])

    def getChannelReflectionColor(self):
        return self.getChannel(["reflection", "Reflection Color"])

    def getChannelReflectionStrength(self):
        return self.getChannel(["reflection_strength", "Reflection Strength"])

    def getChannelRefractionColor(self):
        return self.getChannel(["refraction", "Refraction Color"])

    def getChannelRefractionWeight(self):
        return self.getChannel(["Refraction Weight", "refraction_strength"])

    def getChannelIOR(self):
        return self.getChannel(["ior", "Refraction Index"])

    def getChannelTranslucencyWeight(self):
        return self.getChannel(["translucency", "Translucency Weight"])

    def getChannelSSSColor(self):
        return self.getChannel(["SSS Color", "Subsurface Color"])

    def getChannelSSSAmount(self):
        return self.getChannel(["SSS Amount", "Subsurface Strength"])

    def getChannelSSSScale(self):
        return self.getChannel(["SSS Scale", "Subsurface Scale"])

    def getChannelScatterDist(self):
        return self.getChannel(["Scattering Measurement Distance"])

    def getChannelSSSIOR(self):
        return self.getChannel(["Subsurface Refraction"])

    def getChannelTopCoatRoughness(self):
        return self.getChannel(["Top Coat Roughness"])

    def getChannelNormal(self):
        return self.getChannel(["normal", "Normal Map"])

    def getChannelBump(self):
        return self.getChannel(["bump", "Bump Strength"])

    def getChannelBumpMin(self):
        return self.getChannel(["bump_min", "Bump Minimum", "Negative Bump"])

    def getChannelBumpMax(self):
        return self.getChannel(["bump_max", "Bump Maximum", "Positive Bump"])

    def getChannelDisplacement(self):
        return self.getChannel(["displacement", "Displacement Strength"])

    def getChannelDispMin(self):
        return self.getChannel(["displacement_min", "Displacement Minimum", "Minimum Displacement"])

    def getChannelDispMax(self):
        return self.getChannel(["displacement_max", "Displacement Maximum", "Maximum Displacement"])

    def getChannelHorizontalTiles(self):
        return self.getChannel(["u_scale", "Horizontal Tiles"])

    def getChannelHorizontalOffset(self):
        return self.getChannel(["u_offset", "Horizontal Offset"])

    def getChannelVerticalTiles(self):
        return self.getChannel(["v_scale", "Vertical Tiles"])

    def getChannelVerticalOffset(self):
        return self.getChannel(["v_offset", "Vertical Offset"])


    def getColor(self, attr, default):
        return self.getChannelColor(self.getChannel(attr), default)


    def getTexChannel(self, channels):
        for key in channels:
            channel = self.getChannel([key])
            if channel and self.hasTextures(channel):
                return channel
        return self.getChannel(channels)


    def hasTexChannel(self, channels):
        for key in channels:
            channel = self.getChannel([key])
            if channel and self.hasTextures(channel):
                return True
        return False


    def getChannelColor(self, channel, default, warn=True):
        color = self.getChannelValue(channel, default, warn)
        if isinstance(color, int) or isinstance(color, float):
            color = (color, color, color)
        if channel and channel["type"] == "color":
            return self.srgbToLinearCorrect(color)
        else:
            return self.srgbToLinearGamma22(color)


    def srgbToLinearCorrect(self, srgb):
        lin = []
        for s in srgb:
            if s < 0:
                l = 0
            elif s < 0.04045:
                l = s/12.92
            else:
                l = ((s+0.055)/1.055)**2.4
            lin.append(l)
        return Vector(lin)


    def srgbToLinearGamma22(self, srgb):
        lin = []
        for s in srgb:
            if s < 0:
                l = 0
            else:
                l = round(s**2.2, 6)
            lin.append(l)
        return Vector(lin)


    def getImageMod(self, attr, key):
        channel = self.getChannel(attr)
        if channel and "image_modification" in channel.keys():
            mod = channel["image_modification"]
            if key in mod.keys():
                return mod[key]
        return None


    def getTextures(self, channel):
        if isinstance(channel, tuple):
            channel = channel[0]
        if channel is None:
            return [],[]
        elif "image" in channel.keys():
            if channel["image"] is None:
                return [],[]
            else:
                maps = self.getAsset(channel["image"]).maps
                if maps is None:
                    maps = []
        elif "image_file" in channel.keys():
            map = Map({}, False)
            map.url = channel["image_file"]
            maps = [map]
        elif "map" in channel.keys():
            maps = Maps(self.fileref)
            maps.parse(channel["map"])
            halt
        elif "literal_image" in channel.keys():
            map = Map(channel, False)
            map.image = channel["literal_image"]
            maps = [map]
        elif "literal_maps" in channel.keys():
            maps = []
            for struct in channel["literal_maps"]["map"]:
                if "mask" in struct.keys():
                    mask = Map(struct["mask"], True)
                    maps.append(mask)
                map = Map(struct, False)
                maps.append(map)
        else:
            return [],[]

        texs = []
        nmaps = []
        for map in maps:
            if map.url:
                tex = map.getTexture()
            elif map.literal_image:
                tex = Texture(map)
                tex.image = map.literal_image
            else:
                tex = None
            if tex:
                texs.append(tex)
                nmaps.append(map)
        return texs,nmaps


    def hasTextures(self, channel):
        return (self.getTextures(channel)[0] != [])


    def hasAnyTexture(self):
        for key in self.channels:
            channel = self.getChannel([key])
            if self.getTextures(channel)[0]:
                return True
        return False


    def sssActive(self):
        if not self.enabled["Subsurface"]:
            return False
        if self.refractive or self.thinWall:
            return False
        return True

#-------------------------------------------------------------
#   UDims
#-------------------------------------------------------------

def addUdim(mat, udim, vdim):
    if mat.node_tree:
        addUdimTree(mat.node_tree, udim, vdim)
    else:
        for mtex in mat.texture_slots:
            if mtex and mtex.texture and mtex.texture.extension == 'CLIP':
                mtex.offset[0] += udim
                mtex.offset[1] += vdim


def addUdimTree(tree, udim, vdim):
    if tree is None:
        return
    for node in tree.nodes:
        if node.type == 'MAPPING':
            if hasattr(node, "translation"):
                slot = node.translation
            else:
                slot = node.inputs["Location"].default_value
            slot[0] += udim
            slot[1] += vdim
        elif node.type == 'GROUP':
            addUdimTree(node.node_tree, udim, vdim)

#-------------------------------------------------------------
#   Textures
#-------------------------------------------------------------

class Map:
    def __init__(self, map, ismask):
        self.url = None
        self.label = None
        self.operation = "alpha_blend"
        self.color = (1,1,1)
        self.ismask = ismask
        self.image = None
        self.size = None
        for key,default in [
            ("url", None),
            ("color", BLACK),
            ("label", None),
            ("operation", "alpha_blend"),
            ("literal_image", None),
            ("invert", False),
            ("transparency", 1),
            ("rotation", 0),
            ("xmirror", False),
            ("ymirror", False),
            ("xscale", 1),
            ("yscale", 1),
            ("xoffset", 0),
            ("yoffset", 0)]:
            if key in map.keys():
                setattr(self, key, map[key])
            else:
                setattr(self, key, default)


    def __repr__(self):
        return ("<Map %s %s %s (%s %s)>" % (self.image, self.ismask, self.size, self.xoffset, self.yoffset))


    def getTexture(self):
        if self.url in LS.textures.keys():
            return LS.textures[self.url]
        else:
            tex = Texture(self)
        if self.url:
            LS.textures[self.url] = tex
        return tex


    def build(self):
        if self.image:
            return self.image
        elif self.url:
            self.image = getImage(self.url)
            return self.image
        else:
            return self


def getImage(url):
    if url in LS.images.keys():
        return LS.images[url]
    else:
        return loadImage(url)


def loadImage(url):
    from .asset import getDazPath
    filepath = getDazPath(url)
    if filepath is None:
        reportError('Image not found:  \n"%s"' % filepath, trigger=(3,4))
        img = None
    else:
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        LS.images[url] = img
    return img


class Images(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.maps = []


    def __repr__(self):
        return ("<Images %s r: %s>" % (self.id, self.maps))


    def parse(self, struct):
        Asset.parse(self, struct)
        mapSize = None
        for key in struct.keys():
            if key == "map":
                for mstruct in struct["map"]:
                    if "mask" in mstruct.keys():
                        self.maps.append(Map(mstruct["mask"], True))
                    self.maps.append(Map(mstruct, False))
            elif key == "map_size":
                mapSize = struct[key]
        if mapSize is not None:
            for map in self.maps:
                map.size = mapSize
        self.parseGamma(struct)


    def update(self, struct):
        self.parseGamma(struct)


    def parseGamma(self, struct):
        if "map_gamma" in struct.keys():
            gamma = struct["map_gamma"]
            for map in self.maps:
                LS.gammas[map.url] = gamma


    def build(self):
        images = []
        for map in self.maps:
            img = map.build()
            images.append(img)
        return images


def setImageColorSpace(img, colorspace):
    try:
        img.colorspace_settings.name = colorspace
        return
    except TypeError:
        pass
    alternatives = {
        "sRGB" : ["sRGB OETF"],
        "Non-Color" : ["Non-Colour Data"],
    }
    for alt in alternatives[colorspace]:
        try:
            img.colorspace_settings.name = alt
            return
        except TypeError:
            pass


class Texture:

    def __init__(self, map):
        self.rna = None
        self.map = map
        self.built = {"COLOR":False, "NONE":False}
        self.images = {"COLOR":None, "NONE":None}

    def __repr__(self):
        return ("<Texture %s %s %s>" % (self.map.url, self.map.image, self.rna))


    def getName(self):
        if self.map.url:
            return self.map.url
        elif self.map.image:
            return self.map.image.name
        else:
            return ""


    def buildInternal(self):
        if self.built["COLOR"]:
            return self
        key = self.getName()
        if key:
            img = self.images["COLOR"] = self.map.build()
            if img:
                tex = self.rna = bpy.data.textures.new(img.name, 'IMAGE')
                tex.image = img
            else:
                tex = None
            LS.textures[key] = self
        else:
            tex = self.rna = bpy.data.textures.new(self.map.label, 'BLEND')
            tex.use_color_ramp = True
            r,g,b = self.map.color
            for elt in tex.color_ramp.elements:
                elt.color = (r,g,b,1)
        self.built["COLOR"] = True
        return self


    def buildCycles(self, colorSpace):
        if self.built[colorSpace]:
            return self.images[colorSpace]
        elif colorSpace == "COLOR" and self.images["NONE"]:
            img = self.images["NONE"].copy()
        elif colorSpace == "NONE" and self.images["COLOR"]:
            img = self.images["COLOR"].copy()
        elif self.map.url:
            img = self.map.build()
        elif self.map.image:
            img = self.map.image
        else:
            img = None
        if img:
            if colorSpace == "COLOR":
                img.colorspace_settings.name = "sRGB"
            elif colorSpace == "NONE":
                img.colorspace_settings.name = "Non-Color"
            else:
                img.colorspace_settings.name = colorSpace
        self.images[colorSpace] = img
        self.built[colorSpace] = True
        return img


    def hasMapping(self, map):
        if map:
            return (map.size is not None)
        else:
            return (self.map and self.map.size is not None)


    def getMapping(self, mat, map):
        # mapping scale x = texture width / lie document size x * (lie x scale / 100)
        # mapping scale y = texture height / lie document size y * (lie y scale / 100)
        # mapping location x = udim place + lie x position * (lie y scale / 100) / lie document size x
        # mapping location y = (lie document size y - texture height * (lie y scale / 100) - lie y position) / lie document size y

        if self.images["COLOR"]:
            img = self.images["COLOR"]
        elif self.images["NONE"]:
            img = self.images["NONE"]
        else:
            reportError("BUG: getMapping finds no image", trigger=(3,5))
            return (0,0,1,1,0)

        tx,ty = img.size
        mx,my = map.size
        kx,ky = tx/mx,ty/my
        ox,oy = map.xoffset/mx, map.yoffset/my
        rz = map.rotation

        ox += mat.getValue("getChannelHorizontalOffset", 0)
        oy += mat.getValue("getChannelVerticalOffset", 0)
        kx *= mat.getValue("getChannelHorizontalTiles", 1)
        ky *= mat.getValue("getChannelVerticalTiles", 1)

        sx = map.xscale*kx
        sy = map.yscale*ky

        if rz == 0:
            dx = ox
            dy = 1 - sy - oy
            if map.xmirror:
                dx = sx + ox
                sx = -sx
            if map.ymirror:
                dy = 1 - oy
                sy = -sy
        elif rz == 90:
            dx = ox
            dy = 1 - oy
            if map.xmirror:
                dy = 1 - sy - oy
                sy = -sy
            if map.ymirror:
                dx = sx + ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 270*D
        elif rz == 180:
            dx = sx + ox
            dy = 1 - oy
            if map.xmirror:
                dx = ox
                sx = -sx
            if map.ymirror:
                dy = 1 - sy - oy
                sy = -sy
            rz = 180*D
        elif rz == 270:
            dx = sx + ox
            dy = 1 - sy - oy
            if map.xmirror:
                dy = 1 - oy
                sy = -sy
            if map.ymirror:
                dx = ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 90*D

        return (dx,dy,sx,sy,rz)

#-------------------------------------------------------------z
#
#-------------------------------------------------------------

def isWhite(color):
    return (tuple(color[0:3]) == (1.0,1.0,1.0))

def isBlack(color):
    return (tuple(color[0:3]) == (0.0,0.0,0.0))

#-------------------------------------------------------------
#   Save local textures
#-------------------------------------------------------------

class DAZ_OT_SaveLocalTextures(DazPropsOperator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Local Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"
    bl_options = {'UNDO'}

    keepdirs : BoolProperty(
        name = "Keep Directories",
        description = "Keep the directory tree from Daz Studio, otherwise flatten the directory structure",
        default = True)

    @classmethod
    def poll(self, context):
        return bpy.data.filepath

    def draw(self, context):
        self.layout.prop(self, "keepdirs")

    def run(self, context):
        from shutil import copyfile
        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures")
        print("Save textures to '%s'" % texpath)
        if not os.path.exists(texpath):
            os.makedirs(texpath)

        self.images = []
        for ob in getVisibleMeshes(context):
            for mat in ob.data.materials:
                if mat:
                    if mat.use_nodes:
                        self.saveNodesInTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.saveTextureSlots(psys.settings)
            ob.DazLocalTextures = True

        for img in self.images:
            src = bpy.path.abspath(img.filepath)
            src = bpy.path.reduce_dirs([src])[0]
            file = bpy.path.basename(src)
            srclower = src.lower().replace("\\", "/")
            if self.keepdirs and "/textures/" in srclower:
                subpath = os.path.dirname(srclower.rsplit("/textures/",1)[1])
                folder = os.path.join(texpath, subpath)
                if not os.path.exists(folder):
                    print("Make %s" % folder)
                    os.makedirs(folder)
                trg = os.path.join(folder, file)
            else:
                trg = os.path.join(texpath, file)
            if src != trg and not os.path.exists(trg):
                print("Copy %s\n => %s" % (src, trg))
                copyfile(src, trg)
            img.filepath = bpy.path.relpath(trg)


    def saveNodesInTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                self.images.append(node.image)
            elif node.type == 'GROUP':
                self.saveNodesInTree(node.node_tree)


    def saveTextureSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex:
                tex = mtex.texture
                if hasattr(tex, "image") and tex.image:
                    self.images.append(tex.image)

#-------------------------------------------------------------
#   Merge identical materials
#-------------------------------------------------------------

class MaterialMerger:

    def mergeMaterials(self, ob):
        if ob.type != 'MESH':
            return

        self.matlist = []
        self.assoc = {}
        self.reindex = {}
        self.newname = {None : None}
        m = 0
        reduced = False
        for n,mat in enumerate(ob.data.materials):
            self.newname[mat.name] = mat.name
            if self.keepMaterial(n, mat, ob):
                self.matlist.append(mat)
                self.reindex[n] = self.assoc[mat.name] = m
                m += 1
            else:
                reduced = True
        if reduced:
            phairs = []
            for f in ob.data.polygons:
                f.material_index = self.reindex[f.material_index]
            for psys in ob.particle_systems:
                pset = psys.settings
                phairs.append((pset, pset.material_slot))
            for n,mat in enumerate(self.matlist):
                ob.data.materials[n] = mat
            for n in range(len(self.matlist), len(ob.data.materials)):
                ob.data.materials.pop()
            for pset,matslot in phairs:
                pset.material_slot = self.newname[matslot]


class DAZ_OT_MergeMaterials(DazPropsOperator, MaterialMerger, IsMesh):
    bl_idname = "daz.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge identical materials"
    bl_options = {'UNDO'}

    ignoreStrength : BoolProperty(
        name = "Ignore Strength",
        description = "Merge materials even if some scalar values differ.\nOften needed to merge materials with bump maps",
        default = False)

    ignoreColor : BoolProperty(
        name = "Ignore Color",
        description = "Merge materials even if some vector values differ",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "ignoreStrength")
        self.layout.prop(self, "ignoreColor")


    def run(self, context):
        for ob in getSelectedMeshes(context):
           self.mergeMaterials(ob)
           self.removeUnusedMaterials(ob)


    def keepMaterial(self, mn, mat, ob):
        for mat2 in self.matlist:
            if self.areSameMaterial(mat, mat2):
                self.reindex[mn] = self.assoc[mat2.name]
                self.newname[mat.name] = mat2.name
                return False
        return True


    def areSameMaterial(self, mat1, mat2):
        mname1 = mat1.name
        mname2 = mat2.name
        deadMatProps = [
            "texture_slots", "node_tree",
            "name", "name_full", "active_texture",
        ]
        deadMatProps.append("diffuse_color")
        matProps = self.getRelevantProps(mat1, deadMatProps)
        if not self.haveSameAttrs(mat1, mat2, matProps, mname1, mname2):
            return False
        if mat1.use_nodes and mat2.use_nodes:
            if self.areSameCycles(mat1.node_tree, mat2.node_tree, mname1, mname2):
                print(mat1.name, "=", mat2.name)
                return True
            else:
                return False
        else:
            return False


    def getRelevantProps(self, rna, deadProps):
        props = []
        for prop in dir(rna):
            if (prop[0] != "_" and
                prop not in deadProps):
                props.append(prop)
        return props


    def haveSameAttrs(self, rna1, rna2, props, mname1, mname2):
        for prop in props:
            attr1 = attr2 = None
            if (prop[0] == "_" or
                prop[0:3] == "Daz" or
                prop in ["select"]):
                pass
            elif hasattr(rna1, prop) and hasattr(rna2, prop):
                attr1 = getattr(rna1, prop)
                if prop == "name":
                    attr1 = self.fixKey(attr1, mname1, mname2)
                attr2 = getattr(rna2, prop)
                if not self.checkEqual(attr1, attr2):
                    return False
            elif hasattr(rna1, prop) or hasattr(rna2, prop):
                return False
        return True


    def checkEqual(self, attr1, attr2):
        if (isinstance(attr1, int) or
            isinstance(attr1, float) or
            isinstance(attr1, str)):
            return (attr1 == attr2)
        elif isinstance(attr1, bpy.types.Image):
            return (isinstance(attr2, bpy.types.Image) and (attr1.name == attr2.name))
        elif (isinstance(attr1, set) and isinstance(attr2, set)):
            return True
        elif hasattr(attr1, "__len__") and hasattr(attr2, "__len__"):
            if (len(attr1) != len(attr2)):
                return False
            for n in range(len(attr1)):
                if not self.checkEqual(attr1[n], attr2[n]):
                    return False
        return True


    def areSameCycles(self, tree1, tree2, mname1, mname2):
        def rehash(struct):
            nstruct = {}
            for key,node in struct.items():
                if node.name[0:2] == "T_":
                    nstruct[node.name] = node
                elif node.type == 'GROUP':
                    nstruct[node.node_tree.name] = node
                else:
                    nstruct[key] = node
            return nstruct

        nodes1 = rehash(tree1.nodes)
        nodes2 = rehash(tree2.nodes)
        if not self.haveSameKeys(nodes1, nodes2, mname1, mname2):
            return False
        if not self.haveSameKeys(tree1.links, tree2.links, mname1, mname2):
            return False
        for key1,node1 in nodes1.items():
            key2 = self.fixKey(key1, mname1, mname2)
            node2 = nodes2[key2]
            if not self.areSameNode(node1, node2, mname1, mname2):
                return False
        for link1 in tree1.links:
            hit = False
            for link2 in tree2.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        for link2 in tree2.links:
            hit = False
            for link1 in tree1.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        return True


    def areSameNode(self, node1, node2, mname1, mname2):
        if node1.type != node2.type:
            return False
        if not self.haveSameKeys(node1, node2, mname1, mname2):
            return False
        deadNodeProps = ["dimensions", "location"]
        nodeProps = self.getRelevantProps(node1, deadNodeProps)
        if node1.type == 'GROUP':
            if node1.node_tree != node2.node_tree:
                return False
        elif not self.haveSameAttrs(node1, node2, nodeProps, mname1, mname2):
            return False
        if not self.haveSameInputs(node1, node2):
            return False
        return True


    def areSameLink(self, link1, link2, mname1, mname2):
        fromname1 = self.getNodeName(link1.from_node)
        toname1 = self.getNodeName(link1.to_node)
        fromname2 = self.getNodeName(link2.from_node)
        toname2 = self.getNodeName(link2.to_node)
        fromname1 = self.fixKey(fromname1, mname1, mname2)
        toname1 = self.fixKey(toname1, mname1, mname2)
        return (
            (fromname1 == fromname2) and
            (toname1 == toname2) and
            (link1.from_socket.name == link2.from_socket.name) and
            (link1.to_socket.name == link2.to_socket.name)
        )


    def getNodeName(self, node):
        if node.type == 'GROUP':
            return node.node_tree.name
        else:
            return node.name


    def haveSameInputs(self, node1, node2):
        if len(node1.inputs) != len(node2.inputs):
            return False
        for n,socket1 in enumerate(node1.inputs):
            socket2 = node2.inputs[n]
            if hasattr(socket1, "default_value"):
                if not hasattr(socket2, "default_value"):
                    return False
                val1 = socket1.default_value
                val2 = socket2.default_value
                if (hasattr(val1, "__len__") and
                    hasattr(val2, "__len__")):
                    if self.ignoreColor:
                        continue
                    for m in range(len(val1)):
                        if val1[m] != val2[m]:
                            return False
                elif val1 != val2 and not self.ignoreStrength:
                    return False
            elif hasattr(socket2, "default_value"):
                return False
        return True


    def fixKey(self, key, mname1, mname2):
        n = len(key) - len(mname1)
        if key[n:] == mname1:
            return key[:n] + mname2
        else:
            return key


    def haveSameKeys(self, struct1, struct2, mname1, mname2):
        m = len(mname1)
        for key1 in struct1.keys():
            if key1 in ["interface"]:
                continue
            key2 = self.fixKey(key1, mname1, mname2)
            if key2 not in struct2.keys():
                return False
        return True


    def removeUnusedMaterials(self, ob):
        nmats = len(ob.data.materials)
        used = dict([(mn,False) for mn in range(nmats)])
        for f in ob.data.polygons:
            used[f.material_index] = True
        used = list(used.items())
        used.sort()
        used.reverse()
        for n,use in used:
            if not use:
                ob.data.materials.pop(index=n)

# ---------------------------------------------------------------------
#   Copy materials
# ---------------------------------------------------------------------

class DAZ_OT_CopyMaterials(DazPropsOperator, IsMesh):
    bl_idname = "daz.copy_materials"
    bl_label = "Copy Materials"
    bl_description = "Copy materials from active mesh to selected meshes"
    bl_options = {'UNDO'}

    useMatchNames : BoolProperty(
        name = "Match Names",
        description = "Match materials based on names rather than material number",
        default = False)

    errorMismatch : BoolProperty(
        name = "Error On Mismatch",
        description = "Raise an error if the number of source and target materials are different",
        default = True)

    def draw(self, context):
        self.layout.prop(self, "useMatchNames")
        self.layout.prop(self, "errorMismatch")


    def run(self, context):
        src = context.object
        self.mismatch = ""
        found = False
        for trg in getSelectedMeshes(context):
           if trg != src:
               self.copyMaterials(src, trg)
               found = True
        if not found:
            raise DazError("No target mesh selected")
        if self.mismatch:
            msg = "Material number mismatch.\n" + self.mismatch
            raise DazError(msg, warning=True)


    def copyMaterials(self, src, trg):
        ntrgmats = len(trg.data.materials)
        nsrcmats = len(src.data.materials)
        if ntrgmats != nsrcmats:
            self.mismatch += ("\n%s (%d materials) != %s (%d materials)"
                          % (src.name, nsrcmats, trg.name, ntrgmats))
            if self.errorMismatch:
                msg = "Material number mismatch.\n" + self.mismatch
                raise DazError(msg)
        mnums = [(f,f.material_index) for f in trg.data.polygons]
        srclist = [(mat.name, mn, mat) for mn,mat in enumerate(src.data.materials)]
        trglist = [(mat.name, mn, mat) for mn,mat in enumerate(trg.data.materials)]

        trgrest = trglist[nsrcmats:ntrgmats]
        trglist = trglist[:nsrcmats]
        srcrest = srclist[ntrgmats:nsrcmats]
        srclist = srclist[:ntrgmats]
        if self.useMatchNames:
            srclist.sort()
            trglist.sort()
            trgmats = {}
            for n,data in enumerate(srclist):
                mat = data[2]
                tname,mn,_tmat = trglist[n]
                trgmats[mn] = mat
                mat.name = tname
            trgmats = list(trgmats.items())
            trgmats.sort()
        else:
            trgmats = [data[1:3] for data in srclist]

        trg.data.materials.clear()
        for _mn,mat in trgmats:
            trg.data.materials.append(mat)
        for _,_,mat in trgrest:
            trg.data.materials.append(mat)
        for f,mn in mnums:
            f.material_index = mn

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class ChangeResolution():
    steps : IntProperty(
        name = "Steps",
        description = "Resize original images with this number of steps",
        min = 0, max = 8,
        default = 2)

    resizeAll : BoolProperty(
        name = "Resize All",
        description = "Resize all textures of the selected meshes",
        default = True)

    def __init__(self):
        self.filenames = []
        self.images = {}


    def getFileNames(self, paths):
        for path in paths:
            fname = bpy.path.basename(self.getBasePath(path))
            self.filenames.append(fname)


    def getAllTextures(self, context):
        paths = {}
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    self.getTreeTextures(mat.node_tree, paths)
                else:
                    self.getSlotTextures(mat, paths)
            for psys in ob.particle_systems:
                self.getSlotTextures(psys.settings, paths)
        return paths


    def getSlotTextures(self, mat, paths):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                paths[mtex.texture.image.filepath] = True


    def getTreeTextures(self, tree, paths):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                if img.source == 'TILED':
                    folder,basename,ext = self.getTiledPath(img.filepath)
                    for file1 in os.listdir(folder):
                        fname1,ext1 = os.path.splitext(file1)
                        if fname1[:-4] == basename and ext1 == ext:
                            path = os.path.join(folder, "%s%s" % (fname1, ext1))
                            paths[path] = True
                else:
                    paths[img.filepath] = True
            elif node.type == 'GROUP':
                self.getTreeTextures(node.node_tree, paths)


    def getTiledPath(self, filepath):
        path = bpy.path.abspath(filepath)
        path = bpy.path.reduce_dirs([path])[0]
        folder = os.path.dirname(path)
        fname,ext = os.path.splitext(bpy.path.basename(path))
        return folder, fname[:-4], ext


    def replaceTextures(self, context):
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    self.resizeTree(mat.node_tree)
                else:
                    self.resizeSlots(mat)
            for psys in ob.particle_systems:
                self.resizeSlots(psys.settings)


    def resizeSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                img = self.replaceImage(mtex.texture.image)
                mtex.texture.image = img


    def resizeTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                img = self.replaceImage(node.image)
                node.image = img
                if img:
                    node.name = img.name
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)


    def getBasePath(self, path):
        fname,ext = os.path.splitext(path)
        if fname[-5:] == "-res0":
            return "%s%s" % (fname[:-5], ext)
        elif fname[-5:-1] == "-res" and fname[-1].isdigit():
            return "%s%s" % (fname[:-5], ext)
        elif (fname[-10:-6] == "-res" and
              fname[-6].isdigit() and
              fname[-5] == "_" and
              fname[-4:].isdigit()):
            return "%s%s%s" % (fname[:-10], fname[-5:], ext)
        else:
            return path


    def replaceImage(self, img):
        if img is None:
            return None
        colorSpace = img.colorspace_settings.name
        if colorSpace not in self.images.keys():
            self.images[colorSpace] = {}
        images = self.images[colorSpace]

        path = self.getBasePath(img.filepath)
        filename = bpy.path.basename(path)
        if filename not in self.filenames:
            return img

        newname,newpath = self.getNewPath(path)
        if img.source == 'TILED':
            newname = newname[:-5]
        if newpath == img.filepath:
            return img
        elif newpath in images.keys():
            return images[newpath][1]
        elif newname in bpy.data.images.keys():
            return bpy.data.images[newname]
        else:
            try:
                newimg = self.loadNewImage(img, newpath)
            except RuntimeError:
                newimg = None
        if newimg:
            newimg.name = newname
            newimg.colorspace_settings.name = colorSpace
            newimg.source = img.source
            images[newpath] = (img, newimg)
            return newimg
        else:
            print('"%s" does not exist' % newpath)
            return img


    def loadNewImage(self, img, newpath):
        print('Replace "%s" with "%s"' % (img.filepath, newpath))
        if img.source == 'TILED':
            folder,basename,ext = self.getTiledPath(newpath)
            newimg = None
            print("Tiles:")
            for file1 in os.listdir(folder):
                fname1,ext1 = os.path.splitext(file1)
                if fname1[:-4] == basename and ext1 == ext:
                    path = os.path.join(folder, file1)
                    img = bpy.data.images.load(path)
                    udim = int(fname1[-4:])
                    if newimg is None:
                        newimg = img
                        newimg.source = 'TILED'
                        tile = img.tiles[0]
                        tile.number = udim
                    else:
                        newimg.tiles.new(tile_number = udim)
                    print('  "%s"' % file1)
            return newimg
        else:
            return bpy.data.images.load(newpath)


    def getNewPath(self, path):
        base,ext = os.path.splitext(path)
        if self.steps == 0:
            newbase = base
        elif len(base) > 5 and base[-5] == "_" and base[-4:].isdigit():
            newbase = ("%s-res%d%s" % (base[:-5], self.steps, base[-5:]))
        else:
            newbase = ("%s-res%d" % (base, self.steps))
        newname = bpy.path.basename(newbase)
        newpath = newbase + ext
        return newname, newpath


class DAZ_OT_ChangeResolution(DazOperator, ChangeResolution):
    bl_idname = "daz.change_resolution"
    bl_label = "Change Resolution"
    bl_description = (
        "Change all textures of selected meshes with resized versions.\n" +
        "The resized textures must already exist.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)

    def draw(self, context):
        self.layout.prop(self, "steps")

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        self.overwrite = False
        paths = self.getAllTextures(context)
        self.getFileNames(paths.keys())
        self.replaceTextures(context)


class DAZ_OT_ResizeTextures(DazOperator, ImageFile, MultiFile, ChangeResolution):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = (
        "Replace all textures of selected meshes with resized versions.\n" +
        "Python and OpenCV must be installed on your system.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)

    def draw(self, context):
        self.layout.prop(self, "steps")
        self.layout.prop(self, "resizeAll")

    def invoke(self, context, event):
        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures/")
        self.properties.filepath = texpath
        return MultiFile.invoke(self, context, event)

    def run(self, context):
        if self.resizeAll:
            paths = self.getAllTextures(context)
        else:
            paths = self.getMultiFiles(G.theImageExtensions)
        self.getFileNames(paths)

        program = os.path.join(os.path.dirname(__file__), "standalone/resize.py")
        folder = os.path.dirname(bpy.data.filepath)
        for path in paths:
            if path[0:2] == "//":
                path = os.path.join(folder, path[2:])
            _,newpath = self.getNewPath(self.getBasePath(path))
            if not os.path.exists(newpath):
                cmd = ('python "%s" "%s" "%s" %d' % (program, path, newpath, self.steps))
                os.system(cmd)
            else:
                print("Skip", os.path.basename(newpath))

        self.replaceTextures(context)

#----------------------------------------------------------
#   Prune node tree
#----------------------------------------------------------

class DAZ_OT_PruneNodeTrees(DazOperator, IsMesh):
    bl_idname = "daz.prune_node_trees"
    bl_label = "Prune Node Trees"
    bl_description = "Prune all material node trees for selected meshes"
    bl_options = {'UNDO'}

    def run(self, context):
        from .cycles import pruneNodeTree
        for ob in getSelectedMeshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    pruneNodeTree(mat.node_tree)

#----------------------------------------------------------
#   Render settings
#----------------------------------------------------------

def checkRenderSettings(context, force):
    from .light import getMinLightSettings

    renderSettingsCycles = {
        "Bounces" : [("max_bounces", ">", 8)],
        "Diffuse" : [("diffuse_bounces", ">", 1)],
        "Glossy" : [("glossy_bounces", ">", 4)],
        "Transparent" : [("transparent_max_bounces", ">", 16),
                         ("transmission_bounces", ">", 8),
                         ("caustics_refractive", "=", True)],
        "Volume" : [("volume_bounces", ">", 4)],
    }

    renderSettingsEevee = {
        "Transparent" : [
                 ("use_ssr", "=", True),
                 ("use_ssr_refraction", "=", True),
                 ("use_ssr_halfres", "=", False),
                 ("ssr_thickness", "<", 2*GS.unitScale),
                 ("ssr_quality", ">", 1.0),
                 ("ssr_max_roughness", ">", 1.0),
                ],
        "Bounces" : [("shadow_cube_size", ">", "1024"),
                 ("shadow_cascade_size", ">", "2048"),
                 ("use_shadow_high_bitdepth", "=", True),
                 ("use_soft_shadows", "=", True),
                 ("light_threshold", "<", 0.001),
                 ("sss_samples", ">", 16),
                 ("sss_jitter_threshold", ">", 0.5),
                ],
    }

    renderSettingsRender = {
        "Bounces" : [("hair_type", "=", 'STRIP')],
    }

    lightSettings = {
        "Bounces" : getMinLightSettings(),
    }

    scn = context.scene
    handle = GS.handleRenderSettings
    if force:
        handle = "UPDATE"
    msg = ""
    msg += checkSettings(scn.cycles, renderSettingsCycles, handle, "Cycles Settings", force)
    msg += checkSettings(scn.eevee, renderSettingsEevee, handle, "Eevee Settings", force)
    msg += checkSettings(scn.render, renderSettingsRender, handle, "Render Settings", force)

    handle = GS.handleLightSettings
    if force:
        handle = "UPDATE"
    for light in getVisibleObjects(context):
        if light.type == 'LIGHT':
            header = ('Light "%s" settings' % light.name)
            msg += checkSettings(light.data, lightSettings, handle, header, force)

    if msg:
        msg += "See http://diffeomorphic.blogspot.com/2020/04/render-settings.html for details."
        print(msg)
        return msg
    else:
        return ""


def checkSettings(engine, settings, handle, header, force):
    msg = ""
    if handle == "IGNORE":
        return msg
    ok = True
    for key,used in LS.usedFeatures.items():
        if (force or used) and key in settings.keys():
            for attr,op,minval in settings[key]:
                if not hasattr(engine, attr):
                    continue
                val = getattr(engine, attr)
                fix,minval = checkSetting(attr, op, val, minval, ok, header)
                if fix:
                    ok = False
                    if handle == "UPDATE":
                        setattr(engine, attr, minval)
    if not ok:
        if handle == "WARN":
            msg = ("%s are insufficient to render this scene correctly.\n" % header)
        else:
            msg = ("%s have been updated to minimal requirements for this scene.\n" % header)
    return msg


def checkSetting(attr, op, val, minval, first, header):
    negop = None
    eps = 1e-4
    if op == "=":
        if val != minval:
            negop = "!="
    elif op == ">":
        if isinstance(val, str):
            if int(val) < int(minval):
                negop = "<"
        elif val < minval-eps:
            negop = "<"
    elif op == "<":
        if isinstance(val, str):
            if int(val) > int(minval):
                negop = ">"
        elif val > minval+eps:
            negop = ">"

    if negop:
        msg = ("  %s: %s %s %s" % (attr, val, negop, minval))
        if first:
            print("%s:" % header)
        print(msg)
        return True,minval
    else:
        return False,minval


class DAZ_OT_UpdateSettings(DazOperator):
    bl_idname = "daz.update_settings"
    bl_label = "Update Render Settings"
    bl_description = "Update render and light settings if they are inadequate"
    bl_options = {'UNDO'}

    def run(self, context):
        checkRenderSettings(context, True)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SaveLocalTextures,
    DAZ_OT_MergeMaterials,
    DAZ_OT_CopyMaterials,
    DAZ_OT_PruneNodeTrees,
    DAZ_OT_ChangeResolution,
    DAZ_OT_ResizeTextures,
    DAZ_OT_UpdateSettings,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazLocalTextures = BoolProperty(default = False)

    bpy.types.Scene.DazHandleRenderSettings = EnumProperty(
        items = [("IGNORE", "Ignore", "Ignore insufficient render settings"),
                 ("WARN", "Warn", "Warn about insufficient render settings"),
                 ("UPDATE", "Update", "Update insufficient render settings")],
        name = "Render Settings",
        default = "UPDATE"
    )

    bpy.types.Scene.DazHandleLightSettings = EnumProperty(
        items = [("IGNORE", "Ignore", "Ignore insufficient light settings"),
                 ("WARN", "Warn", "Warn about insufficient light settings"),
                 ("UPDATE", "Update", "Update insufficient light settings")],
        name = "Light Settings",
        default = "UPDATE"
    )


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
