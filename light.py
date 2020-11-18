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
from .node import Node, Instance
from .utils import *
from .cycles import CyclesMaterial, CyclesTree
from .internal import InternalMaterial
from .material import Material, WHITE, BLACK
from .error import reportError

#-------------------------------------------------------------
#   Light base class
#-------------------------------------------------------------

def getMinLightSettings():
    return [("use_shadow", "=", True),
            ("shadow_buffer_clip_start", "<", 1.0*LS.scale),
            ("shadow_buffer_bias", "<", 0.01),
            ("use_contact_shadow", "=", True),
            ("contact_shadow_bias", "<", 0.01),
            ("contact_shadow_distance", "<", 1.0*LS.scale),
            ("contact_shadow_thickness", "<", 10*LS.scale),
           ]


class Light(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.type = None
        self.info = {}
        self.presentation = {}
        self.data = None
        self.twosided = False


    def __repr__(self):
        return ("<Light %s %s>" % (self.id, self.rna))


    def parse(self, struct):
        Node.parse(self, struct)
        if "spot" in struct.keys():
            self.type = 'SPOT'
            self.info = struct["spot"]
        elif "point" in struct.keys():
            self.type = 'POINT'
            self.info = struct["point"]
        elif "directional" in struct.keys():
            self.type = 'DIRECTIONAL'
            self.info = struct["directional"]
        else:
            self.presentation = struct["presentation"]
            print("Strange lamp", self)


    def makeInstance(self, fileref, struct):
        return LightInstance(fileref, self, struct)


    def build(self, context, inst):
        lgeo = inst.getValue(["Light Geometry"], -1)
        usePhoto = inst.getValue(["Photometric Mode"], False)
        self.twosided = inst.getValue(["Two Sided"], False)
        height = inst.getValue(["Height"], 0) * LS.scale
        width = inst.getValue(["Width"], 0) * LS.scale

        # [ "Point", "Rectangle", "Disc", "Sphere", "Cylinder" ]
        if bpy.app.version < (2,80,0):
            bpydatalamps = bpy.data.lamps
        else:
            bpydatalamps = bpy.data.lights
        if lgeo == 1:
            lamp = bpydatalamps.new(self.name, "AREA")
            lamp.shape = 'RECTANGLE'
            lamp.size = width
            lamp.size_y = height
        elif lgeo == 2 and bpy.app.version >= (2,80,0):
            lamp = bpydatalamps.new(self.name, "AREA")
            lamp.shape = 'DISK'
            lamp.size = height
        elif lgeo > 1:
            lamp = bpydatalamps.new(self.name, "POINT")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'POINT':
            lamp = bpydatalamps.new(self.name, "POINT")
            lamp.shadow_soft_size = 0
            if bpy.app.version < (2,80,0):
                inst.fluxFactor = 5
            else:
                inst.fluxFactor = 3
            self.twosided = False
        elif self.type == 'SPOT':
            lamp = bpydatalamps.new(self.name, "SPOT")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'DIRECTIONAL':
            lamp = bpydatalamps.new(self.name, "SUN")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'light':
            lamp = bpydatalamps.new(self.name, "AREA")
        else:
            msg = ("Unknown light type: %s" % self.type)
            reportError(msg, trigger=(1,3))
            lamp = bpydatalamps.new(self.name, "SPOT")
            lamp.shadow_soft_size = height/2
            self.twosided = False

        if GS.materialMethod == 'INTERNAL':
            self.setInternalProps(lamp)
        else:
            self.setCyclesProps(lamp)
        self.data = lamp
        Node.build(self, context, inst)
        inst.material.build(context)


    def setCyclesProps(self, lamp):
        for attr,op,value in getMinLightSettings():
            if hasattr(lamp, attr):
                setattr(lamp, attr, value)


    def setInternalProps(self, lamp):
        for key,value in self.info.items():
            if key == "intensity":
                lamp.energy = value
            elif key == "shadow_type":
                if bpy.app.version < (2,80,0):
                    if value == "none":
                        lamp.shadow_method = 'NOSHADOW'
                    else:
                        lamp.shadow_method = 'RAY_SHADOW'
                else:
                    if value == "none":
                        lamp.cycles.cast_shadow = False
                    else:
                        lamp.cycles.case_shadow = True
            elif key == "shadow_softness":
                lamp.shadow_buffer_soft = value
            elif key == "shadow_bias":
                #lamp.shadow_buffer_bias = value
                print("Lamp %s shadow bias: %s" % (lamp.name, value))
            elif key == "falloff_angle":
                if hasattr(lamp, "spot_size"):
                    lamp.spot_size = value*D
            elif key == "falloff_exponent":
                if hasattr(lamp, "distance"):
                    lamp.distance = value
            else:
                print("Unknown lamp prop", key)


    def postTransform(self):
        if GS.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2


    def postbuild(self, context, inst):
        Node.postbuild(self, context, inst)
        if self.twosided:
            if inst.rna:
                ob = inst.rna
                activateObject(context, ob)
                bpy.ops.object.duplicate_move()
                nob = getActiveObject(context)
                nob.data = ob.data
                nob.scale = -ob.scale

#-------------------------------------------------------------
#   LightInstance
#-------------------------------------------------------------

class LightInstance(Instance):
    def __init__(self, fileref, node, struct):
        Instance.__init__(self, fileref, node, struct)
        if GS.materialMethod == 'INTERNAL':
            self.material = InternalLightMaterial(fileref, self)
        else:
            self.material = CyclesLightMaterial(fileref, self)
        self.fluxFactor = 1


    def buildChannels(self, context):
        Instance.buildChannels(self, context)
        lamp = self.rna.data
        if bpy.app.version < (2,80,0):
            if self.getValue(["Cast Shadows"], 0):
                lamp.shadow_method = 'RAY_SHADOW'
            else:
                lamp.shadow_method = 'NOSHADOW'
            value = self.getValue(["Shadow Type"], 0)
            stypes = ['NOSHADOW', 'BUFFER_SHADOW', 'RAY_SHADOW']
            lamp.shadow_method = stypes[value]
        else:
            if self.getValue(["Cast Shadows"], 0):
                lamp.cycles.cast_shadow = True
            else:
                lamp.cycles.cast_shadow = False

        if bpy.app.version < (2,80,0):
            value = self.getValue(["Illumination"], 3)
            # [ "Off", "Diffuse Only", "Specular Only", "On" ]
            lamp.use_diffuse = (value in [1,3])
            lamp.use_specular = (value in [2,3])

        lamp.color = self.getValue(["Color"], WHITE)
        flux = self.getValue(["Flux"], 15000)
        lamp.energy = flux / 15000
        lamp.shadow_color = self.getValue(["Shadow Color"], BLACK)
        if hasattr(lamp, "shadow_buffer_soft"):
            lamp.shadow_buffer_soft = self.getValue(["Shadow Softness"], False)
        #if hasattr(lamp, "shadow_buffer_bias"):
        #    bias = self.getValue(["Shadow Bias"], None)
        #    if bias:
        #        lamp.shadow_buffer_bias = bias
        if hasattr(lamp, "falloff_type"):
            value = self.getValue(["Decay"], 2)
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            lamp.falloff_type = dtypes[value]

#-------------------------------------------------------------
#   InternalLightMaterial
#-------------------------------------------------------------

class InternalLightMaterial(InternalMaterial):
    def __init__(self, fileref, inst):
        InternalMaterial.__init__(self, fileref)
        self.name = inst.name
        self.channels = inst.channels
        self.instance = inst

#-------------------------------------------------------------
#   Cycles Light Material
#-------------------------------------------------------------

class CyclesLightMaterial(CyclesMaterial):

    def __init__(self, fileref, inst):
        CyclesMaterial.__init__(self, fileref)
        self.name = inst.name
        self.channels = inst.channels
        self.instance = inst

    def guessColor(self):
        return

    def build(self, context):
        if self.dontBuild():
            return
        Material.build(self, context)
        self.tree = LightTree(self)
        self.tree.build()


class LightTree(CyclesTree):

    def build(self):
        self.makeTree()
        color = self.getValue(["Color"], WHITE)
        #flux = self.getValue(["Flux"], 15000)

        emit = self.addNode("ShaderNodeEmission", 1)
        emit.inputs["Color"].default_value[0:3] = color
        emit.inputs["Strength"].default_value = self.material.instance.fluxFactor
        if bpy.app.version < (2,80,0):
            output = self.addNode("ShaderNodeOutputLamp", 2)
        else:
            output = self.addNode("ShaderNodeOutputLight", 2)
        self.links.new(emit.outputs[0], output.inputs["Surface"])


    def addTexco(self, slot):
        return



