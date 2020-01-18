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
##

import bpy
from .asset import Asset

#-------------------------------------------------------------
#   
#-------------------------------------------------------------

def getChannels(extras):
    channels = []
    if "studio_modifier_channels" in extras.keys():
        struct = extras["studio_modifier_channels"]
        for channel in struct["channels"]:
            channels.append(channel["channel"])
    return channels


def getValue(channel, default):
    if "current_value" in channel.keys():
        return channel["current_value"]
    elif "value" in channel.keys():
        return channel["value"]
    else:
        return default
        

def buildSimulationModifier(rig, ob, extras):
    objtype = 0
    baseshape = 0
    freeze = 0
    print("BUILD SIM", ob)
    for channel in getChannels(extras):
        print("  ", channel["id"], getValue(channel, None))
        if channel["id"] == "Simulation Object Type":
            # [ "Static Surface", "Dynamic Surface", "Dynamic Surface Add-On" ]
            objtype = getValue(channel, 0)
        elif channel["id"] == "Simulation Base Shape":
            # [ "Use Simulation Start Frame", "Use Scene Frame 0", 
            #   "Use Shape from Simulation Start Frame", "Use Shape from Scene Frame 0" ]
            baseshape = getValue(channel, 0)
        elif channel["id"] == "Freeze Simulation":
            freeze = getValue(channel, False)
    
    struct = extras["studio/modifier/dynamic_simulation"]
    print("SIM", ob, objtype, baseshape, freeze)
    if objtype > 0:
        mod = ob.modifiers.new("Cloth", 'CLOTH')
        cset = mod.settings
        if "vertex_count" in struct.keys():       
            print("VCOU", struct["vertex_count"]) 
            pass


'''
   Visible in Simulation True
   Friction 0.2
   Collision Layer 1
   Collide True
   Self Collide True
   Collision Offset 0.2
   Collision Response Damping 0
   Dynamics Strength 0.1823529
   Stretch Stiffness 0.8
   Shear Stiffness 0.2
   Bend Stiffness 0.5
   Buckling Stiffness 0.05
   Buckling Ratio 0.7
   Density 180
   Contraction-Expansion Ratio 1
   Damping 0.1
   Stretch Damping 0.1
   Shear Damping 0.1
   Bend Damping 0.1
   Velocity Shock Propagation 0
   Velocity Shock Propagation Threshold 1.4
   Local Shape Constraint Stiffness 0.5
   Local Shape Constraint Stiffness Bias 0
   Local Shape Constraint Stiffness Gain 0.5
   Local Shape Constraint Tip Stiffness 0.5
   Hair Sample Rate 1
   Hair Constraint Iterations 1
   Local Shape Constraint Iterations 2
   Length Constraints Iterations 2
   Global Shape Constraint Stiffness 0
   Global Shape Range 0
   Hair Generation Mode 0
   Use Target Surface UVs True
   Hair Growth Group ID 0
   Surface Growth Groups 
   Vertex Style Curve Tolerance 0
   PreSim Hairs Density 0
   PreSim Hair Seed 0
   PreSim Points Per Hair 8
   PreSim Hairs Per Guide 0
   PreSim Hair Distribution Radius 0.1
   PreSim Hair Tip Separation 0
   PreSim Hair Bias 0.5
   PreSim Hair Gain 0.5
   PreSim Generated Style Curve Segment Length 1
   PreSim Interpolation Segment Length 1
   PreSim Interpolation Mode 0
   PreSim Interpolation Auto Parting Angle 180
   PreSim Interpolation Single Guide Strength 0
   PreSim Interpolation Single Guide Base 0
   PreSim Interpolation Single Guide Tip 0
   PreSim Interpolation Single Guide Bias 0.5
   PreSim Clumping 1 Curves Density 0
   PreSim Clumpiness 1 0
   PreSim Clumping 1 Bias 0.5
   PreSim Clumping 1 Seed 0
   PreSim Clumping 2 Curves Density 0
   PreSim Clumpiness 2 0
   PreSim Clumping 2 Bias 0.5
   PreSim Clumping 2 Seed 0
   PreSim Random Length Amount 0
   PreSim Random Length Seed 0
   PreSim Reduce Length Amount 0
   PreSim Random Pitch Angle 0
   PreSim Random Roll Angle 0
   PreSim Random Yaw Angle 0
   PreSim Random Angle Seed 0
   PreSim Scraggle 1 Mode 0
   PreSim Scraggliness 1 0
   PreSim Scraggle 1 Frequency  0
   PreSim Scraggle 1 Freq Depth  0
   PreSim Scraggle 1 Freq Ratio 0
   PreSim Scraggle 1 Freq Mult 0
   PreSim Scraggle 2 Mode 0
   PreSim Scraggliness 2 0
   PreSim Scraggle 2 Frequency  0
   PreSim Scraggle 2 Freq Depth  0
   PreSim Scraggle 2 Freq Ratio 0
   PreSim Scraggle 2 Freq Mult 0
   PreSim Frizz Base Amount 0
   PreSim Frizz Tip Amount 0
   PreSim Frizz Seed 0
   PreSim Generated Hair Scale 1
   PreSim Minimum Generated Hair Scale 0
   PS Hairs at Style Curves True
   PreRender Hairs Density 0
   PreRender Hair Seed 0
   PreRender Points Per Hair 8
   PreRender Hairs Per Guide 0
   PreRender Hair Distribution Radius 0.1
   PreRender Hair Tip Separation 0
   PreRender Hair Bias 0.5
   PreRender Hair Gain 0.5
   PreRender Generated Style Curve Segment Length 1
   PreRender Interpolation Segment Length 1
   PreRender Interpolation Mode 0
   PreRender Interpolation Auto Parting Angle 180
   PreRender Interpolation Single Guide Strength 0
   PreRender Interpolation Single Guide Base 0
   PreRender Interpolation Single Guide Tip 0
   PreRender Interpolation Single Guide Bias 0.5
   PreRender Clumping 1 Curves Density 0
   PreRender Clumpiness 1 0
   PreRender Clumping 1 Bias 0.5
   PreRender Clumping 1 Seed 0
   PreRender Clumping 2 Curves Density 0
   PreRender Clumpiness 2 0
   PreRender Clumping 2 Bias 0.5
   PreRender Clumping 2 Seed 0
   PreRender Random Length Amount 0
   PreRender Random Length Seed 0
   PreRender Reduce Length Amount 0
   PreRender Random Pitch Angle 0
   PreRender Random Roll Angle 0
   PreRender Random Yaw Angle 0
   PreRender Random Angle Seed 0
   PreRender Scraggle 1 Mode 0
   PreRender Scraggliness 1 0
   PreRender Scraggle 1 Frequency  0
   PreRender Scraggle 1 Freq Depth  0
   PreRender Scraggle 1 Freq Ratio 0
   PreRender Scraggle 1 Freq Mult 0
   PreRender Scraggle 2 Mode 0
   PreRender Scraggliness 2 0
   PreRender Scraggle 2 Frequency  0
   PreRender Scraggle 2 Freq Depth  0
   PreRender Scraggle 2 Freq Ratio 0
   PreRender Scraggle 2 Freq Mult 0
   PreRender Frizz Base Amount 0
   PreRender Frizz Tip Amount 0
   PreRender Frizz Seed 0
   PreRender Generated Hair Scale 1
   PreRender Minimum Generated Hair Scale 0
   Velocity Smoothing 0
   Velocity Smoothing Iterations 0
'''

def buildSimulationSettings(rig, ob, extras):
    print("BUILD SETT", rig, ob)
    for channel in getChannels(extras):
        pass


def buildSmoothingModifier(rig, ob, extras):
    print("BUILD SMOOTH", ob)
    for channel in getChannels(extras):
        print("  ", channel["id"], getValue(channel, None))
        if channel["id"] == "Enable Smoothing":
            pass
        elif channel["id"] == "Smoothing Type":
            # [ "Base Shape Matching", "Generic" ]
            pass
        elif channel["id"] == "Smoothing Iterations":
            pass
        elif channel["id"] == "Weight":
            pass
        elif channel["id"] == "Secondary Weight":
            pass
        elif channel["id"] == "Lock Distance":
            pass
        elif channel["id"] == "Length Influence":
            pass
        elif channel["id"] == "Interactive Update":
            pass
        elif channel["id"] == "Collision Item":
            # "type" : "node"
            pass
        elif channel["id"] == "Collision Iterations":
            pass
        elif channel["id"] == "Collision Smoothing Interval":
            pass
        else:
            print("Didnt expect", channel["id"])

#-------------------------------------------------------------
#   Simulation Options
#-------------------------------------------------------------

class SimulationOptions(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.channels = {}


    def __repr__(self):
        return ("<SimulationOptions %s>" % (self.fileref))


    def parse(self, struct):
        if struct["id"] == "dForce Simulation Options":
            self.channels = struct["channels"]

                
    def build(self, context):
        for cstruct in self.channels:
            channel = cstruct["channel"]
            print(" C", channel["id"], channel["current_value"])         

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def parseSimulationOptions(struct, fileref):
    print("PSIM", struct.keys())
    if "simulation_elements" in struct.keys():
        asset = SimulationOptions(fileref)
        for element in struct["simulation_elements"]:
            asset.parse(element)
        return asset
    return None
    
