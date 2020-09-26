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

class DForce:
    def __init__(self, mod, geonode, extra, pgeonode):
        self.extra = extra
        self.modifier = mod
        self.pgeonode = pgeonode


    def getSimulationData(self, geonode, ob):
        from .modifier import buildVertexGroup
        matnames = []
        sim = None
        for modname,mod in geonode.modifiers.items():
            if (mod.getValue(["Visible in Simulation"], False) and
                modname[0:8] == "DZ__SPS_"):
                matnames += mod.groups
                sim = mod
        if not matnames:
            return None, None, None, None

        nverts = len(ob.data.vertices)
        geo = geonode.data
        pgeo = self.pgeonode.data
        vgrps = {}
        if "influence_weights" in self.extra.keys():
            if nverts != self.extra["vertex_count"]:
                msg = ("Influence vertex count mismatch: %s" % ob.name)
                reportError(msg, trigger=(2,4))
                return None, None, None, None
            else:
                weights = self.extra["influence_weights"]["values"]
                vgrp = buildVertexGroup(ob, self.modifier.name, weights)
                vgrps[0] = vgrp
                weights[0] = dict(weights)
        else:
            ngroups = len(pgeo.polygon_groups)
            weights = dict([(gn,{}) for gn in range(ngroups)])
            for gn,face in zip(pgeo.polygon_indices, pgeo.faces):
                for vn in face:
                    weights[gn][vn] = 1
            for gn,gname in enumerate(pgeo.polygon_groups):
                vgrp = buildVertexGroup(ob, gname, weights[gn].items())
                vgrps[gn] = vgrp

        sizes = {}
        for gn in vgrps.keys():
            size = Vector((10,10,10))*LS.scale
            verts = ob.data.vertices
            for n in range(3):
                coord = [verts[vn].co[n] for vn in weights.keys()]
                if coord:
                    size[n] = max(coord) - min(coord)
            sizes[gn] = size

        return sim, vgrps, weights, sizes


    def build(self, geonode):
        if "dForce Simulation" in geonode.modifiers.keys():
            sim = geonode.modifiers["dForce Simulation"]
        else:
            return

        sot = sim.getValue(["Simulation Object Type"], 0)
        # [ "Static Surface", "Dynamic Surface", "Dynamic Surface Add-On" ]
        if geonode.skull and self.pgeonode.rna:
            ob = self.pgeonode.rna
        else:
            ob = geonode.rna
        if sot != 1:
            return
        # Unused simulation properties
        sbt = sim.getValue(["Simulation Base Shape"], 0)
        # [ "Use Simulation Start Frame", "Use Scene Frame 0", "Use Shape from Simulation Start Frame", "Use Shape from Scene Frame 0" ]
        freeze = sim.getValue(["Freeze Simulation"], False)

        sim,vgrps,weights,sizes = self.getSimulationData(geonode, ob)
        if sim is None:
            print("Cannot build: %s" % self.modifier.name)
            return
        vgrp = vgrps[0]
        size = sizes[0].length

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
        if vgrps[0]:
            mset.vertex_group_mass = vgrps[0].name

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
