# Copyright (c) 2016-2019, Thomas Larsson
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
from bpy.props import *

class DazBoolGroup(bpy.types.PropertyGroup):
    b : BoolProperty()

class DAZ_OT_UdimizeMaterials(bpy.types.Operator):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make Udim Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    use : CollectionProperty(type = DazBoolGroup)
    active : EnumProperty(items=[], name="")
    
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def draw(self, context):
        from .guess import getSkinMaterial
        ob = context.object
        enums = []
        active = None
        for mat in ob.data.materials:
            item = self.use.add()
            item.b = (getSkinMaterial(mat)[0] in ["Skin", "Red"])
            if item.b and active is None:
                active = mat
            enums.append((mat.name,mat.name,mat.name))        
            
        self.layout.label(text="Materials To Merge")
        for n,mat in enumerate(ob.data.materials):
            row = self.layout.row()
            row.label(text=mat.name)
            row.prop(self.use[n], "b", text="")

        self.layout.separator()
        self.layout.label(text="Active Material: %s" % active.name)  
        return
        prop = EnumProperty(items=enums)  
        scn = context.scene
        setattr(bpy.types.Scene, "DazUdimActive", prop)
        self.layout.prop(scn, "active")


    def execute(self, context):
        try:
            self.udimize(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def udimize(self, context):
        ob = context.object
        mats = []
        active = None
        for n,mat in enumerate(ob.data.materials):
            if self.use[n].b:            
                mats.append(mat)
                if active is None:
                    active = mat
        print("Use", mats)
        print("Active", active)

        self.channels = {}
        for mat in mats:
            self.channels[mat.name] = self.getChannels(mat)

        self.udimMaterial(active, active)
        for mat in mats:
            if mat != active:
                self.udimMaterial(mat, active)

    def getChannels(self, mat):
        channels = {}
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                channel = self.getChannel(node, mat.node_tree.links)
                channels[channel] = node
        return channels              


    def getChannel(self, node, links):
        for link in links:
            if link.from_node == node:
                if link.to_node.type in ["MIX_RGB", "MATH"]:
                    return self.getChannel(link.to_node, links)
                elif link.to_node.type == "BSDF_PRINCIPLED":
                    return ("PBR_%s" % link.to_socket.name)
                else:
                    return link.to_node.type
        return None
                            

    def udimMaterial(self, mat, active):
        du = 1000 + mat.DazUDim
        dv = 1000 + mat.DazVDim
        print("\nMAT", mat.name, du, dv)
        
        
        
#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazBoolGroup,
    DAZ_OT_UdimizeMaterials,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
        
def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
        


