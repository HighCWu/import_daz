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
    def __init__(self, mod, geonode, extra):
        self.vertexGroup = None
        self.weights = {}
        if (GS.useInfluence and
            "influence_weights" in extra.keys()):
            self.buildInfluence(mod, geonode, extra)


    def buildInfluence(self, mod, geonode, extra):
        from .modifier import buildVertexGroup
        ob = geonode.rna
        nverts = len(ob.data.vertices)
        if nverts != extra["vertex_count"]:
            msg = ("Influence vertex count mismatch: %s" % inst.name)
            reportError(msg, trigger=(2,4))
        else:
            weights = extra["influence_weights"]
            self.simulated = True
            self.vertexGroup = buildVertexGroup(ob, mod.name, weights)
            self.weights = weights["values"]


    def getSimulationData(self, geonode):
        matnames = []
        sim = None
        for modname,mod in geonode.modifiers.items():
            if (mod.getValue(["Visible in Simulation"], False) and
                modname[0:8] == "DZ__SPS_"):
                matnames.append(modname[8:])
                sim = mod

        ob = geonode.rna
        if "dForce Simulation" in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups["dForce Simulation"]
            weights = {}
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == vgrp.index:
                        weights[v.index] = g.weight
        else:
            mnums = []
            for mn,mat in enumerate(ob.data.materials):
                for matname in matnames:
                    if mat.name.startswith(matname):
                        mnums.append(mn)
                        break
            nverts = len(ob.data.vertices)
            weights = {}
            for f in ob.data.polygons:
                if f.material_index in mnums:
                    for vn in f.vertices:
                        weights[vn] = 1
            vgrp = ob.vertex_groups.new(name="dForce Simulation")
            for vn,w in weights.items():
                vgrp.add([vn], w, 'REPLACE')

        sizes = Vector((10,10,10))*LS.scale
        verts = ob.data.vertices
        for n in range(3):
            coord = [verts[vn].co[n] for vn in weights.keys()]
            sizes[n] = max(coord) - min(coord)
        return sim, vgrp, weights, sizes


    def build(self, geonode):
        if "dForce Simulation" in geonode.modifiers.keys():
            sim = geonode.modifiers["dForce Simulation"]
        else:
            return

        sot = sim.getValue(["Simulation Object Type"], 0)
        # [ "Static Surface", "Dynamic Surface", "Dynamic Surface Add-On" ]
        ob = geonode.rna
        if sot != 1:
            return
        # Unused simulation properties
        sbt = sim.getValue(["Simulation Base Shape"], 0)
        # [ "Use Simulation Start Frame", "Use Scene Frame 0", "Use Shape from Simulation Start Frame", "Use Shape from Scene Frame 0" ]
        freeze = sim.getValue(["Freeze Simulation"], False)

        sim,vgrp,weights,sizes = self.getSimulationData(geonode)

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
        size = sizes.length
        mass = density * size**2 * 1e-3     # kg
        mset.mass = mass
        #mset.friction = sim.getValue(["Friction"], 0)

        # Self collisions - off
        #mset.use_self_collision = sim.getValue(["Self Collide"], False)
        mset.use_self_collision = False
        mset.ball_size = sizes.length
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
