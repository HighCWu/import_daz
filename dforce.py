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
from .utils import *

#-------------------------------------------------------------
#   SimData base class
#-------------------------------------------------------------

class SimData:
    def __init__(self, mod, geonode, extra, pgeonode):
        self.extra = extra
        self.modifier = mod
        self.geonode = geonode
        self.pgeonode = pgeonode
        self.isHair = False


    def getGeoObject(self):
        geonode = self.geonode
        if self.useParent:
            geonode = self.pgeonode
        ob = None
        if geonode.rna:
            ob = geonode.rna
        return geonode, ob


    def getInfluence(self, ob):
        from .modifier import buildVertexGroup
        nverts = len(ob.data.vertices)
        if "influence_weights" not in self.extra.keys():
            return {},{}
        if nverts != self.extra["vertex_count"]:
            msg = ("Influence vertex count mismatch: %s" % ob.name)
            reportError(msg, trigger=(2,4))
            return {},{}
        else:
            weights = self.extra["influence_weights"]["values"]
            mname = self.modifier.name
            vgrp = buildVertexGroup(ob, mname, weights)
            vgrps = {mname : vgrp}
            weights = {mname : dict(weights)}
            return vgrps, weights


    def getSims(self):
        matnames = []
        sims = {}
        for modname,mod in self.geonode.modifiers.items():
            if (mod.getValue(["Visible in Simulation"], False) and
                modname[0:8] == "DZ__SPS_"):
                matname = mod.groups[0]
                matnames += mod.groups
                sims[matname] = mod
        if matnames:
            return sims
        else:
            return {}


    def getWeights(self, geo):
        ngroups = len(geo.polygon_groups)
        gweights = dict([(gn,{}) for gn in range(ngroups)])
        for gn,face in zip(geo.polygon_indices, geo.faces):
            for vn in face:
                gweights[gn][vn] = 1
        return gweights


    def getPolyGroups(self, geonode, ob):
        from .modifier import buildVertexGroup
        if not geonode:
            return {},{}
        oldvgrps = dict([(vgrp.name.lower(),vgrp) for vgrp in ob.vertex_groups])
        vgrps = {}
        geo = geonode.data
        gweights = self.getWeights(geo)
        weights = {}
        for gn,gname in enumerate(geo.polygon_groups):
            if self.useSingleGroup:
                vgrp = None
            elif gname.lower() in oldvgrps.keys():
                vgrp = oldvgrps[gname.lower()]
            else:
                vgrp = buildVertexGroup(ob, gname.upper(), gweights[gn].items())
            vgrps[gname] = vgrp
            weights[gname] = gweights[gn]

        if self.useSingleGroup:
            return self.mergeGroups(ob, weights)
        else:
            return vgrps, weights


    def mergeGroups(self, ob, gweights):
        if not gweights:
            return {},{}
        from .modifier import buildVertexGroup
        vweights = {}
        for gname in gweights.keys():
            for vn,wt in gweights[gname].items():
                vweights[vn] = wt
        mname = self.modifier.name
        vgrp = buildVertexGroup(ob, mname, vweights.items())
        vgrps = {mname : vgrp}
        weights = {mname : dict(vweights)}
        return vgrps,weights


    def getSizes(self, ob, weights):
        sizes = {}
        verts = ob.data.vertices
        for gname,gweights in weights.items():
            size = Vector((10,10,10))*LS.scale
            for n in range(3):
                coord = [verts[vn].co[n] for vn in gweights.keys()]
                if coord:
                    size[n] = max(coord) - min(coord)
            sizes[gname] = size
        return sizes

#-------------------------------------------------------------
#   Hair simulation
#-------------------------------------------------------------

class HairGenerator(SimData):
    def __init__(self, mod, geonode, extra, pgeonode):
        SimData.__init__(self, mod, geonode, extra, pgeonode)
        self.useParent = True
        self.useSingleGroup = False
        self.isHair = True
        self.vertexGroups = {}
        self.weights = None


    def build(self, ob, polygrp):
        from .modifier import buildVertexGroup
        if polygrp not in self.vertexGroups.keys():
            geonode,ob = self.getGeoObject()
            if not geonode:
                return None
            geo = geonode.data
            if self.weights is None:
                self.weights = self.getWeights(geo)
            vgrp = None
            for gn,gname in enumerate(geo.polygon_groups):
                if gname == polygrp:
                    vgrp = buildVertexGroup(ob, polygrp.upper(), self.weights[gn].items())
                    break
            self.vertexGroups[polygrp] = vgrp
        return self.vertexGroups[polygrp]

#-------------------------------------------------------------
#  dForce simulation
#-------------------------------------------------------------

class DForce(SimData):
    def __init__(self, mod, geonode, extra, pgeonode):
        SimData.__init__(self, mod, geonode, extra, pgeonode)
        self.useParent = False
        self.useSingleGroup = True


    def build(self, context):
        if self.geonode.hairgen:
            print("Ignore hair simulation: %s" % self.modifier.id)
            return
        geonode,ob = self.getGeoObject()
        if ob is None:
            return

        if (GS.useSimulation and
            "dForce Simulation" in self.geonode.modifiers.keys()):
            sim = self.geonode.modifiers["dForce Simulation"]
        elif (GS.useInfluence and
              "influence_weights" in self.extra.keys()):
            self.getInfluence(ob)
            return
        else:
            return

        sot = sim.getValue(["Simulation Object Type"], 0)
        # [ "Static Surface", "Dynamic Surface", "Dynamic Surface Add-On" ]
        if sot != 1:
            return
        # Unused simulation properties
        sbt = sim.getValue(["Simulation Base Shape"], 0)
        # [ "Use Simulation Start Frame", "Use Scene Frame 0", "Use Shape from Simulation Start Frame", "Use Shape from Scene Frame 0" ]
        freeze = sim.getValue(["Freeze Simulation"], False)

        sims = self.getSims()
        if not sims:
            print("Cannot build:", self.modifier.name, ob)
            return
        if "influence_weights" in self.extra.keys():
            vgrps,weights = self.getInfluence(ob)
        else:
            vgrps,weights = self.getPolyGroups(geonode, ob)
        sizes = self.getSizes(ob, weights)
        if self.useSingleGroup:
            key = list(vgrps.keys())[0]
            sim = list(sims.values())[0]
            sims = {key : sim}

        # Make modifier
        _,hum,char = self.getHuman(ob)
        activateObject(context, ob)
        deflect = None
        for key,sim in sims.items():
            if GS.useDeflectors:
                deflect = self.makeDeflectionCollection(context, hum, char, sim)
            if ob == hum or not hum:
                mod = self.buildSoftBody(ob, sim, vgrps[key], sizes[key].length)
            else:
                mod = self.buildCloth(ob, sim, vgrps[key], sizes[key].length)
                if deflect:
                    self.addDeflection(mod.collision_settings, deflect, sim)
            self.moveModifierUp(ob, mod)


        # Unused
        dynStrength = sim.getValue(["Dynamics Strength"], 0)
        buckStiff = sim.getValue(["Buckling Stiffness"], 0)
        buckRatio = sim.getValue(["Buckling Ratio"], 0)


    def getHuman(self, ob):
        from .finger import getFingeredCharacter
        while ob.parent:
            ob = ob.parent
        return getFingeredCharacter(ob)


    def makeDeflectionCollection(self, context, hum, char, sim):
        from .proxy import makeDeflection
        if hum is None:
            return None
        if not sim.getValue(["Collision Layer"], 0):
            return
        if char in LS.deflectors.keys():
            return LS.deflectors[char]
        _,deflect = makeDeflection(context, hum, char, 0)
        LS.deflectors[char] = deflect
        return deflect


    def addDeflection(self, mcset, deflect, sim):
        mcset.collection = deflect
        mcset.distance_min = sim.getValue(["Collision Offset"], 0) * LS.scale
        mcset.self_impulse_clamp = sim.getValue(["Collision Response Damping"], 0)


    def moveModifierUp(self, ob, cloth):
        m = 0
        for n,mod in enumerate(ob.modifiers):
            if mod.type in ["SUBSURF", "MULTIRES"]:
                m = len(ob.modifiers) - n - 1
                break
        for n in range(m):
            bpy.ops.object.modifier_move_up(modifier=cloth.name)


    def buildCloth(self, ob, sim, vgrp, size):
        mod = ob.modifiers.new("Cloth", 'CLOTH')
        mset = mod.settings

        density = sim.getValue(["Density"], 0)  # grams/m^2
        mset.mass = density * 1e-3 * 1e-2       # kg/cm^2 - 1 vert/cm^2
        mset.air_damping = sim.getValue(["Damping"], 0)

        ceRatio = sim.getValue(["Contraction-Expansion Ratio"], 1)
        mset.tension_stiffness = sim.getValue(["Stretch Stiffness"], 15)
        mset.compression_stiffness = mset.tension_stiffness * ceRatio
        mset.shear_stiffness = sim.getValue(["Shear Stiffness"], 5)
        mset.bending_stiffness = sim.getValue(["Bend Stiffness"], 0.5)

        mset.tension_damping = sim.getValue(["Stretch Damping"], 5)
        mset.compression_damping = mset.tension_damping * ceRatio
        mset.shear_damping = sim.getValue(["Shear Damping"], 5)
        mset.bending_damping = sim.getValue(["Bend Damping"], 0.5)

        mset.vertex_group_mass = vgrp.name

        return mod


    def buildSoftBody(self, ob, sim, vgrp, size):
        mod = ob.modifiers.new("Softbody", 'SOFT_BODY')
        mset = mod.settings
        if vgrp:
            mset.vertex_group_mass = vgrp.name

        # Object settings
        density = sim.getValue(["Density"], 0) # grams/m^2
        mass = density * size**2 * 1e-3     # kg
        mset.mass = mass
        #mset.friction = sim.getValue(["Friction"], 0)

        # Self collisions - off
        #mset.use_self_collision = sim.getValue(["Self Collide"], False)
        mset.use_self_collision = False
        mset.ball_size = size
        mset.ball_stiff = sim.getValue(["Bend Stiffness"], 0)
        mset.ball_damp = sim.getValue(["Damping"], 0)

        # Goal - on
        mset.use_goal = True

        # Edges - definitely off
        mset.use_edges = False
        if vgrp:
            mset.vertex_group_spring = vgrp.name
        ceRatio = sim.getValue(["Contraction-Expansion Ratio"], 1)
        mset.pull = sim.getValue(["Stretch Stiffness"], 0)
        mset.push = mset.pull * ceRatio
        mset.damping = sim.getValue(["Damping"], 0)
        mset.bend = sim.getValue(["Bend Stiffness"], 0)

        mset.use_stiff_quads = False
        mset.shear = sim.getValue(["Shear Stiffness"], 0)
        return mod
