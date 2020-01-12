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

def buildSimulation(rig, ob, extras):
    objtype = 0
    baseshape = 0
    freeze = 0
    if "studio_modifier_channels" in extras.keys():
        struct = extras["studio_modifier_channels"]
        for channels in struct["channels"]:
            channel = channels["channel"]
            if channel["id"] == "Simulation Object Type":
                # [ "Static Surface", "Dynamic Surface", "Dynamic Surface Add-On" ]
                objtype = channel["value"]
            elif channel["id"] == "Simulation Base Shape":
                # [ "Use Simulation Start Frame", "Use Scene Frame 0", 
                #   "Use Shape from Simulation Start Frame", "Use Shape from Scene Frame 0" ]
                baseshape = channel["value"]
            elif channel["id"] == "Freeze Simulation":
                freeze = channel["value"]
    
    if "studio/modifier/dynamic_simulation" in extras.keys():
        struct = extras["studio/modifier/dynamic_simulation"]
        print("SIM", ob, objtype, baseshape, freeze)
        if objtype > 0:
            mod = ob.modifiers.new("Cloth", 'CLOTH')
            cset = mod.settings
            if "vertex_count" in struct.keys():       
                print("VCOU", struct["vertex_count"]) 
                pass


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
    
