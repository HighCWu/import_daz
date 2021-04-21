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
from .asset import Asset
from .channels import Channels
from .material import Material, WHITE, isBlack
from .cycles import CyclesMaterial, CyclesTree
from .cgroup import CyclesGroup
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
        if "backdrop_visible" in settings.keys():
            if not settings["backdrop_visible"]:
                return
        if "backdrop_visible_in_render" in settings.keys():
            if not settings["backdrop_visible_in_render"]:
                return
        if backdrop:
            self.backdrop = backdrop
        for key,value in settings.items():
            if key == "background_color":
                self.background = value


    def __repr__(self):
        return ("<RenderOptions %s %s>" % (self.background, self.backdrop))


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
        if LS.useEnvironment:
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
            self.background = self.srgbToLinearGamma22(render.background)
        self.backdrop = render.backdrop
        self.envmap = None


    def guessColor(self):
        return


    def build(self, context):
        if self.dontBuild():
            return
        mode = self.getValue(["Environment Mode"], 3)
        # [Dome and Scene, Dome Only, Sun-Skies Only, Scene Only]
        if mode == 3:
            print("Scene Only")
            return

        self.envmap = self.getChannel(["Environment Map"])
        fixray = False
        foundenv = False
        if mode in [0,1] and self.envmap:
            print("Draw environment", mode)
            if not self.getValue(["Draw Dome"], False):
                print("Draw Dome turned off")
            elif self.getImageFile(self.envmap) is None:
                print("Don't draw environment. Image file not found")
            else:
                foundenv = True
        if (not foundenv and
            mode in [0,3] and
            self.background):
            print("Draw backdrop", mode, self.background)
            self.envmap = None
            fixray = True
            foundenv = True
        if not foundenv:
            print("Dont draw environment. Environment mode == %d" % mode)
            return

        self.refractive = False
        Material.build(self, context)
        self.tree = WorldTree(self)

        world = self.rna = bpy.data.worlds.new(self.name)
        world.use_nodes = True
        self.tree.build()
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

class BackgroundGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color"]
        self.outsockets += ["Fac", "Color"]

    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 2)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Fac")
        self.group.outputs.new("NodeSocketColor", "Color")

    def addNodes(self, args=None):
        lightpath = self.addNode("ShaderNodeLightPath", 1)
        self.links.new(lightpath.outputs["Is Camera Ray"], self.outputs.inputs["Fac"])
        self.links.new(self.inputs.outputs["Color"], self.outputs.inputs["Color"])


class WorldTree(CyclesTree):

    def __init__(self, wmat):
        CyclesTree.__init__(self, wmat)
        self.type == "WORLD"


    def build(self):
        from mathutils import Euler, Matrix

        backdrop = self.material.backdrop
        background = self.material.background
        envmap = self.material.envmap
        strength = 1
        color = WHITE
        if envmap:
            tex, strength = self.buildEnvmap(envmap)
        elif backdrop:
            tex = self.buildBackdrop(backdrop)
        else:
            tex = None
            self.makeTree()

        self.column += 1
        bg = self.addNode("ShaderNodeBackground")
        bg.inputs["Strength"].default_value = strength
        self.linkColor(tex, bg, color)

        if background:
            dazbg = self.addGroup(BackgroundGroup, "DAZ Background")
            dazbg.inputs["Color"].default_value[0:3] = background
            self.column += 1
            mix = self.addNode("ShaderNodeMixShader")
            self.links.new(dazbg.outputs["Fac"], mix.inputs[0])
            self.links.new(bg.outputs["Background"], mix.inputs[1])
            self.links.new(dazbg.outputs["Color"], mix.inputs[2])

        self.column += 1
        output = self.addNode("ShaderNodeOutputWorld")
        if background:
            self.links.new(mix.outputs[0], output.inputs["Surface"])
        else:
            self.links.new(bg.outputs["Background"], output.inputs["Surface"])
        self.prune()


    def buildEnvmap(self, envmap):
        self.makeTree(slot="Generated")
        self.column = 1
        rot = self.getValue(["Dome Rotation"], 0)
        orx = self.getValue(["Dome Orientation X"], 0)
        ory = self.getValue(["Dome Orientation Y"], 0)
        orz = self.getValue(["Dome Orientation Z"], 0)

        if rot != 0 or orx != 0 or ory != 0 or orz != 0:
            mat1 = Euler((0,0,-rot*D)).to_matrix()
            mat2 = Euler((0,-orz*D,0)).to_matrix()
            mat3 = Euler((orx*D,0,0)).to_matrix()
            mat4 = Euler((0,0,ory*D)).to_matrix()
            mat = mat1 @ mat2 @ mat3 @ mat4
            self.addMapping(mat.to_euler())

        value = self.material.getChannelValue(envmap, 1)
        img = self.getImage(envmap, "NONE")
        if img:
            self.column += 1
            tex = self.addNode("ShaderNodeTexEnvironment")
            self.setColorSpace(tex, "NONE")
            if img:
                tex.image = img
                tex.name = img.name
            self.links.new(self.texco, tex.inputs["Vector"])
        strength = self.getValue(["Environment Intensity"], 1) * value
        return tex, strength


    def buildBackdrop(self, backdrop):
        self.makeTree(slot="Window")
        self.column = 1
        img = self.getImage(backdrop, "COLOR")
        if img:
            self.column += 1
            tex = self.addTextureNode(self.column, img, img.name, "COLOR")
            self.linkVector(self.texco, tex)
        return tex


    def addMapping(self, rot):
        self.column += 1
        mapping = self.addNode("ShaderNodeMapping")
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

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def parseRenderOptions(renderSettings, sceneSettings, backdrop, fileref):
    if not LS.useEnvironment:
        return
    else:
        renderOptions = renderSettings["render_options"]
        if "render_elements" in renderOptions.keys():
            if not LS.render:
                LS.render = RenderOptions(fileref)
            LS.render.initSettings(sceneSettings, backdrop)
            for element in renderOptions["render_elements"]:
                LS.render.parse(element)
