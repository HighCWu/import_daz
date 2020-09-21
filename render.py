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
import os
from .asset import Asset
from .channels import Channels
from .material import Material, WHITE
from .cycles import CyclesMaterial, CyclesTree
from .utils import *

#-------------------------------------------------------------
#   Render Options
#-------------------------------------------------------------

class RenderOptions(Asset, Channels):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Channels.__init__(self)
        self.world = None
        self.background = None
        self.backdrop = None


    def initSettings(self, settings, backdrop):
        for key,value in settings.items():
            if key == "background_color":
                self.background = value
            if ("backdrop_visible" in settings.keys() and
                backdrop and
                settings["backdrop_visible"] and
                settings["backdrop_visible_in_render"]):
                self.backdrop = backdrop


    def __repr__(self):
        return ("<RenderOptions %s>" % (self.fileref))


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)
        if "children" in struct.keys():
            for child in struct["children"]:
                if "channels" in child.keys():
                    for channel in child["channels"]:
                        self.setChannel(channel["channel"])


    def update(self, struct):
        Asset.update(self, struct)
        Channels.update(self, struct)


    def build(self, context):
        if GS.useEnvironment:
            self.world = WorldMaterial(self, self.fileref)
            self.world.build(context)

#-------------------------------------------------------------
#   World Material
#-------------------------------------------------------------

class WorldMaterial(CyclesMaterial):

    def __init__(self, render, fileref):
        CyclesMaterial.__init__(self, fileref)
        self.name = os.path.splitext(os.path.basename(fileref))[0] + " World"
        self.channels = render.channels
        self.background = None
        if render.background:
            self.background = self.srgbToLinear(render.background)
        self.backdrop = render.backdrop
        self.envmap = None


    def build(self, context):
        self.refractive = False
        Material.build(self, context)
        self.tree = WorldTree(self)

        mode = self.getValue(["Environment Mode"], 0)
        # [Dome and Scene, Dome Only, Sun-Skies Only, Scene Only]

        self.envmap = self.getChannel(["Environment Map"])
        fixray = False
        if mode in [0,1] and self.envmap:
            print("Draw environment", mode)
            if not self.getValue(["Draw Dome"], False):
                print("Don't draw environment. Draw Dome turned off")
                return
            if self.getImageFile(self.envmap) is None:
                print("Don't draw environment. Image file not found")
                return
        elif mode in [0,3] and self.background:
            print("Draw backdrop", mode)
            self.envmap = None
            fixray = True
        else:
            print("Dont draw environment. Environment mode == %d" % mode)
            return

        world = self.rna = bpy.data.worlds.new(self.name)
        world.use_nodes = True
        self.tree.build(context)
        context.scene.world = world
        if fixray:
            vis = world.cycles_visibility
            vis.camera = True
            vis.diffuse = False
            vis.glossy = False
            vis.transmission = False
            vis.scatter = False

#-------------------------------------------------------------
#   World Tree
#-------------------------------------------------------------

class WorldTree(CyclesTree):

    def __init__(self, wmat):
        CyclesTree.__init__(self, wmat)
        self.type == "WORLD"


    def build(self, context):
        from mathutils import Euler, Matrix

        background = self.material.background
        backdrop = self.material.backdrop
        envmap = self.material.envmap
        eeveefix = False
        tex = None
        if envmap:
            self.makeTree(slot="Generated")
            rot = self.getValue(["Dome Rotation"], 0)
            orx = self.getValue(["Dome Orientation X"], 0)
            ory = self.getValue(["Dome Orientation Y"], 0)
            orz = self.getValue(["Dome Orientation Z"], 0)

            if rot != 0 or orx != 0 or ory != 0 or orz != 0:
                mat1 = Euler((0,0,-rot*D)).to_matrix()
                mat2 = Euler((0,-orz*D,0)).to_matrix()
                mat3 = Euler((orx*D,0,0)).to_matrix()
                mat4 = Euler((0,0,ory*D)).to_matrix()
                mat = Mult4(mat1, mat2, mat3, mat4)
                self.addMapping(mat.to_euler())

            color = WHITE
            value = self.material.getChannelValue(envmap, 1)
            img = self.getImage(envmap, "NONE")
            if img:
                tex = self.addTexEnvNode(img, "NONE")
                self.links.new(self.texco, tex.inputs["Vector"])
            strength = self.getValue(["Environment Intensity"], 1) * value
        elif backdrop:
            self.makeTree(slot="Window")
            strength = 1
            color = background
            eeveefix = True
            img = self.getImage(backdrop, "COLOR")
            if img:
                tex = self.addTextureNode(2, img, "COLOR")
                self.linkVector(self.texco, tex)
        else:
            self.makeTree()
            strength = 1
            color = background
            eeveefix = True
            tex = None

        bg = self.addNode("ShaderNodeBackground", 4)
        bg.inputs["Strength"].default_value = strength
        self.linkColor(tex, bg, color)
        output = self.addNode("ShaderNodeOutputWorld", 6)
        if eeveefix:
            lightpath = self.addNode("ShaderNodeLightPath", 4)
            mix = self.addNode("ShaderNodeMixShader", 5)
            self.links.new(lightpath.outputs[0], mix.inputs[0])
            self.links.new(bg.outputs[0], mix.inputs[2])
            self.links.new(mix.outputs[0], output.inputs["Surface"])
        else:
            self.links.new(bg.outputs[0], output.inputs["Surface"])
        self.prune()


    def addMapping(self, rot):
        mapping = self.addNode("ShaderNodeMapping", 2)
        mapping.vector_type = 'TEXTURE'
        if hasattr(mapping, "rotation"):
            mapping.rotation = rot
        else:
            mapping.inputs['Rotation'].default_value = rot
        self.links.new(self.texco, mapping.inputs["Vector"])
        self.texco = mapping.outputs["Vector"]


    def getImage(self, channel, colorSpace):
        assets,maps = self.material.getTextures(channel)
        asset = assets[0]
        img = asset.images[colorSpace]
        if img is None:
            img = asset.buildCycles(colorSpace)
        return img


    def addTexEnvNode(self, img, colorSpace):
        tex = self.addNode("ShaderNodeTexEnvironment", 2)
        self.setColorSpace(tex, colorSpace)
        if img:
            tex.image = img
            tex.name = img.name
        return tex


#-------------------------------------------------------------
#
#-------------------------------------------------------------

def parseRenderOptions(renderSettings, sceneSettings, backdrop, fileref):
    if LS.materialMethod == 'INTERNAL':
        return None
    else:
        renderOptions = renderSettings["render_options"]
        if "render_elements" in renderOptions.keys():
            asset = RenderOptions(fileref)
            asset.initSettings(sceneSettings, backdrop)
            for element in renderOptions["render_elements"]:
                asset.parse(element)
            return asset
    return None

