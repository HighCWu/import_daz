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
from .utils import *

#-------------------------------------------------------------
#  dForce simulation
#-------------------------------------------------------------

class DForce:
    def __init__(self, inst, mod, extra):
        self.instance = inst
        self.modifier = mod
        self.extra = extra
        #print("\nCREA", self)

    def __repr__(self):
        return "<DForce %s\ni: %s\nm: %s\ne: %s>" % (self.type, self.instance, self.modifier, self.instance.rna)


#-------------------------------------------------------------
#  studio/modifier/dynamic_generate_hair
#-------------------------------------------------------------

class DynGenHair(DForce):
    type = "DynGenHair"

#-------------------------------------------------------------
#  studio/modifier/dynamic_simulation
#-------------------------------------------------------------

class DynSim(DForce):
    type = "DynSim"

    def build(self, context):
        from .node import Instance
        from .geometry import GeoNode
        #print("\nBUILD", self)
        if isinstance(self.instance, Instance):
            inst = self.instance
            geonode = self.instance.geometries[0]
        elif isinstance(self.instance, GeoNode):
            inst = self.instance
            geonode = self.instance

        ob = geonode.rna
        if not (ob and ob.type == 'MESH'):
            return

        visible = False
        strength = 0.0
        if geonode.simset:
            settings = geonode.simset.modifier
            for key in settings.channels.keys():
                if key == "Visible in Simulation":
                    visible = settings.getValue([key], False)
                elif key == "Dynamics Strength":
                    strength = settings.getValue([key], 0.0)
        if not visible or strength == 0.0:
            return

        cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        self.setSilk(cset)
        # Collision settings
        colset = cloth.collision_settings
        colset.distance_min = 0.1*LS.scale
        colset.use_self_collision = True
        colset.self_distance_min = 0.1*LS.scale
        colset.collision_quality = 4
        # Pinning
        pingrp = self.addConstantVertexGroup(ob, "DForce Pin", 1-strength)
        cset.vertex_group_mass = pingrp.name
        cset.pin_stiffness = 1.0


    def setSilk(self, cset):
        # Cloth
        cset.quality = 16
        # Physical properties
        cset.mass = 0.15
        cset.air_damping = 1.0
        # Stiffness
        cset.tension_stiffness = 5.0
        cset.compression_stiffness = 5.0
        cset.shear_stiffness = 5.0
        cset.bending_stiffness = 0.05
        # Damping
        cset.tension_damping = 0.0
        cset.compression_damping = 0.0
        cset.shear_damping = 0.0
        cset.bending_damping = 0.5
        #
        cset.use_internal_springs = False
        cset.use_pressure = False


    def addConstantVertexGroup(self, ob, vgname, value):
        vgrp = ob.vertex_groups.new(name = vgname)
        nverts = len(ob.data.vertices)
        for vn in range(nverts):
            vgrp.add([vn], value, 'REPLACE')
        return vgrp

#-------------------------------------------------------------
#  studio/modifier/dynamic_hair_follow
#-------------------------------------------------------------

class DynHairFlw(DForce):
    type = "DynHairFlw"

#-------------------------------------------------------------
#  studio/modifier/line_tessellation
#-------------------------------------------------------------

class LinTess(DForce):
    type = "LinTess"

#-------------------------------------------------------------
#  studio/simulation_settings/dynamic_simulation
#-------------------------------------------------------------

class SimSet(DForce):
    type = "SimSet"

