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
from .utils import *

theSimPresets = {}

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

        collision = self.hideModifier(ob, 'COLLISION')
        subsurf = self.hideModifier(ob, 'SUBSURF')
        multires = self.hideModifier(ob, 'MULTIRES')

        cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        self.setPreset(cset)
        cset.mass *= GS.gsmFactor
        cset.quality = GS.simQuality
        # Collision settings
        colset = cloth.collision_settings
        colset.distance_min = 0.1*LS.scale
        colset.use_self_collision = True
        colset.self_distance_min = 0.1*LS.scale
        colset.collision_quality = GS.collQuality
        # Pinning
        pingrp = self.addConstantVertexGroup(ob, "DForce Pin", 1-strength)
        cset.vertex_group_mass = pingrp.name
        cset.pin_stiffness = 1.0

        if collision:
            collision.restore(ob)
        if subsurf:
            subsurf.restore(ob)
        if multires:
            multires.restore(ob)


    def setPreset(self, cset):
        global theSimPresets
        if not theSimPresets:
            from .load_json import loadJson
            folder = os.path.dirname(__file__) + "/data/presets"
            for file in os.listdir(folder):
                filepath = os.path.join(folder, file)
                theSimPresets[file] = loadJson(filepath)
        struct = theSimPresets[GS.simPreset]
        for key,value in struct.items():
            setattr(cset, key, value)


    def addConstantVertexGroup(self, ob, vgname, value):
        vgrp = ob.vertex_groups.new(name = vgname)
        nverts = len(ob.data.vertices)
        for vn in range(nverts):
            vgrp.add([vn], value, 'REPLACE')
        return vgrp


    def hideModifier(self, ob, mtype):
        mod = getModifier(ob, mtype)
        if mod:
            store = ModStore(mod)
            ob.modifiers.remove(mod)
            return store
        else:
            return None

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

#-------------------------------------------------------------
#  class for storing modifiers
#-------------------------------------------------------------

class ModStore:
    def __init__(self, mod):
        self.name = mod.name
        self.type = mod.type
        self.data = {}
        self.store(mod, self.data)
        self.settings = {}
        if hasattr(mod, "settings"):
            self.store(mod.settings, self.settings)
        self.collision_settings = {}
        if hasattr(mod, "collision_settings"):
            self.store(mod.collision_settings, self.collision_settings)


    def store(self, data, struct):
        for key in dir(data):
            if (key[0] == '_' or
                key == "name" or
                key == "type"):
                continue
            value = getattr(data, key)
            if isSimpleType(value):
                struct[key] = value


    def restore(self, ob):
        mod = ob.modifiers.new(self.name, self.type)
        self.restoreData(self.data, mod)
        if self.settings:
            self.restoreData(self.settings, mod.settings)
        if self.collision_settings:
            self.restoreData(self.collision_settings, mod.collision_settings)


    def restoreData(self, struct, data):
        for key,value in struct.items():
            try:
                setattr(data, key, value)
            except:
                pass

