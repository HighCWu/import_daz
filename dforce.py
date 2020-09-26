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

class SimData:
    def __init__(self, mod, geonode, extra, pgeonode):
        self.extra = extra
        self.modifier = mod
        self.geonode = geonode
        self.pgeonode = pgeonode


    def getSimulationData(self):
        if self.useParent:
            geonode = self.pgeonode
        else:
            geonode = self.geonode
        if geonode.rna:
            ob = geonode.rna
        else:
            return None,{},{},{},{}

        from .modifier import buildVertexGroup
        matnames = []
        sims = {}
        for modname,mod in self.geonode.modifiers.items():
            if (mod.getValue(["Visible in Simulation"], False) and
                modname[0:8] == "DZ__SPS_"):
                matname = mod.groups[0]
                matnames += mod.groups
                sims[matname] = mod
        if not matnames:
            return ob,{},{},{},{}

        nverts = len(ob.data.vertices)
        oldvgrps = dict([(vgrp.name.lower(),vgrp) for vgrp in ob.vertex_groups])
        vgrps = {}
        if "influence_weights" in self.extra.keys():
            if nverts != self.extra["vertex_count"]:
                msg = ("Influence vertex count mismatch: %s" % ob.name)
                reportError(msg, trigger=(2,4))
                return ob,{},{},{},{}
            else:
                weights = self.extra["influence_weights"]["values"]
                mname = self.modifier.name
                vgrp = buildVertexGroup(ob, mname, weights)
                sim = list(sims.values())[0]
                sims = {mname : sim}
                vgrps = {mname : vgrp}
                weights = {mname : dict(weights)}
        elif geonode:
            geo = geonode.data
            ngroups = len(geo.polygon_groups)
            gweights = dict([(gn,{}) for gn in range(ngroups)])
            for gn,face in zip(geo.polygon_indices, geo.faces):
                for vn in face:
                    gweights[gn][vn] = 1
            if self.useSingleGroup:
                weights = {}
                for gn in gweights.keys():
                    for vn,wt in gweights[gn].items():
                        weights[vn] = wt
                mname = self.modifier.name
                vgrp = buildVertexGroup(ob, mname, weights.items())
                sim = list(sims.values())[0]
                sims = {mname : sim}
                vgrps = {mname : vgrp}
                weights = {mname : dict(weights)}
            else:
                weights = {}
                for gn,gname in enumerate(geo.polygon_groups):
                    if False and gname.lower() in oldvgrps.keys():
                        vgrp = oldvgrps[gname.lower()]
                    else:
                        vgrp = buildVertexGroup(ob, gname.upper(), gweights[gn].items())
                    vgrps[gname] = vgrp
                    weights[gname] = gweights[gn]
        else:
            print("FOO", self)
            return ob,{},{},{},{}

        sizes = {}
        verts = ob.data.vertices
        for gname,gweights in weights.items():
            size = Vector((10,10,10))*LS.scale
            for n in range(3):
                coord = [verts[vn].co[n] for vn in gweights.keys()]
                if coord:
                    size[n] = max(coord) - min(coord)
            sizes[gname] = size

        return ob, sims, vgrps, weights, sizes


class DForce(SimData):
    def __init__(self, mod, geonode, extra, pgeonode):
        SimData.__init__(self, mod, geonode, extra, pgeonode)
        self.useParent = False
        self.useSingleGroup = True


    def build(self):
        if "dForce Simulation" in self.geonode.modifiers.keys():
            sim = self.geonode.modifiers["dForce Simulation"]
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

        ob,sims,vgrps,weights,sizes = self.getSimulationData()
        if not sims:
            print("Cannot build: %s" % self.modifier.name)
            return
        sim = list(sims.values())[0]
        vgrp = list(vgrps.values())[0]
        size = list(sizes.values())[0].length

        # More unused
        collLayer = sim.getValue(["Collision Layer"], 0)
        collOffset = sim.getValue(["Collision Offset"], 0)
        collRespDamping = sim.getValue(["Collision Response Damping"], 0)
        dynStrength = sim.getValue(["Dynamics Strength"], 0)
        buckStiff = sim.getValue(["Buckling Stiffness"], 0)
        buckRatio = sim.getValue(["Buckling Ratio"], 0)
        bendDamp = sim.getValue(["Bend Damping"], 0)
        stretchDamp = sim.getValue(["Stretch Damping"], 0)
        shearDamp = sim.getValue(["Shear Damping"], 0)

        # Create modifier
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
