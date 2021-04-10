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

    def build(self, context):
        pass

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
        if not (GS.useInfluence or GS.useSimulation):
            return
        from .node import Instance
        from .geometry import GeoNode
        if isinstance(self.instance, Instance):
            geonode = self.instance.geometries[0]
        elif isinstance(self.instance, GeoNode):
            geonode = self.instance
        else:
            reportError("Bug DynSim %s" % self.instance, trigger=(2,3))
            return
        ob = geonode.rna
        if not (ob and ob.type == 'MESH'):
            return

        visible = False
        for simset in geonode.simsets:
            if simset.modifier.getValue(["Visible in Simulation"], False):
                visible = True
        if not GS.useSimulation or not visible:
            if GS.useInfluence:
                self.addPinVertexGroup(ob, geonode)
            return
        elif GS.useInfluence:
            pingrp = self.addPinVertexGroup(ob, geonode)
        else:
            pingrp = None

        settings = geonode.simsets[0]
        collision = self.hideModifier(ob, 'COLLISION')
        subsurf = self.hideModifier(ob, 'SUBSURF')
        multires = self.hideModifier(ob, 'MULTIRES')

        cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        if GS.useDazSimSettings:
            self.setDazSettings(settings, cset)
        else:
            self.setPreset(cset)
        cset.mass *= GS.gsmFactor
        cset.quality = GS.simQuality
        # Collision settings
        colset = cloth.collision_settings
        colset.distance_min = 0.1*LS.scale
        colset.self_distance_min = 0.1*LS.scale
        colset.collision_quality = GS.collQuality
        # Pinning
        if pingrp:
            cset.vertex_group_mass = pingrp.name
        cset.pin_stiffness = 1.0

        if GS.useDazSimSettings and settings:
            useColl = settings.getValue(["Collide"], True)
            if collision and useColl:
                collision.restore(ob)
            if settings.getValue(["Self Collide"], False):
                colset.use_self_collision = True
            distmin = settings.getValue(["Collision Offset"], 0.1)*LS.scale
            colset.distance_min = distmin
            colset.self_distance_min = distmin
        else:
            if collision:
                collision.restore(ob)
        if subsurf:
            subsurf.restore(ob)
        if multires:
            multires.restore(ob)


    def setDazSettings(self, settings, cset):
        params = {
            "Friction" : ([], 1.0),
            "Dynamics Strength" : ([], 1.0),
            "Stretch Stiffness" : (["compression_stiffness", "tension_stiffness"], 1/LS.scale),
            "Shear Stiffness" : (["shear_stiffness"], 1/LS.scale),
            "Bend Stiffness" : (["bending_stiffness"], 1/LS.scale),
            "Buckling Stiffness" : ([], 1/LS.scale),
            "Buckling Ratio" : ([], 1.0),
            "Density" : (["mass"], LS.scale),
            "Contraction-Expansion Ratio" : ([], 1.0),
            "Damping" : (["air_damping"], 1.0),
            "Stretch Damping" : (["compression_damping", "tension_damping"], 1.0),
            "Shear Damping" : (["shear_damping"], 1.0),
            "Bend Damping" : (["bending_damping"], 1.0),
            "Velocity Smoothing" : ([], 1.0),
            "Velocity Smoothing Iterations" : ([], 1),
        }
        for key in settings.channels.keys():
            if key in params.keys():
                attrs,factor = params[key]
                value = settings.getValue([key], None)
                for attr in attrs:
                    setattr(cset, attr, factor*value)


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


    def addPinVertexGroup(self, ob, geonode):
        nverts = len(ob.data.vertices)
        vgrp = ob.vertex_groups.new(name = "DForce Pin")

        # Influence group
        if "influence_weights" in self.extra.keys():
            vcount = self.extra["vertex_count"]
            if vcount == nverts:
                weights = self.extra["influence_weights"]["values"]
                for vn,w in weights:
                    ww = 1-w*strength
                    if ww > 1e-5:
                        vgrp.add([vn], ww, 'REPLACE')
                return vgrp
            else:
                msg = ("Influence weight mismatch: %d != %d" % (vcount, nverts))
                reportError(msg, trigger=(2,4))

        # Dform
        dforms = []
        for vgrp in ob.vertex_groups:
            if vgrp.name[0:5] == "Dform":
                dforms.append(vgrp.index)
        if dforms:
            weights = dict([(vn, 0.0) for vn in range(nverts)])
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group in dforms:
                        weights[v.index] += g.weight
            for vn,w in weights.items():
                vgrp.add([vn], 1-w*strength, 'REPLACE')
            return vgrp

        # Constant per material vertex group
        geo = geonode.data
        mnums = dict([(mgrp, mn) for mn,mgrp in enumerate(geo.polygon_material_groups)])
        for simset in geonode.simsets:
            strength = simset.modifier.getValue(["Dynamics Strength"], 0.0)
            value = 1-strength
            if value == 0.0:
                continue
            for mgrp in simset.modifier.groups:
                mn = mnums[mgrp]
                for f in ob.data.polygons:
                    if f.material_index == mn:
                        for vn in f.vertices:
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
            if (isSimpleType(value) or
                isinstance(value, bpy.types.Object)):
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

