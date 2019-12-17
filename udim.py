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
import os
from bpy.props import *
from .error import *


class DazUdimGroup(bpy.types.PropertyGroup):
    name : StringProperty()
    bool : BoolProperty()


class DAZ_OT_UdimizeMaterials(bpy.types.Operator):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make Udim Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    umats : CollectionProperty(type = DazUdimGroup)
    #active : EnumProperty(items=[], name="Active")
    name : StringProperty(
        name = "Name",
        description = "Name of resulting material",
        default = "Skin"
        )
    
    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazLocalTextures)


    def draw(self, context):            
        self.layout.label(text="Materials To Merge")
        for umat in self.umats:
            self.layout.prop(umat, "bool", text=umat.name)
        self.layout.separator()
        self.layout.prop(self, "name")
        self.layout.label(text="Target Material: %s" % self.trgmat.name)


    def execute(self, context):
        try:
            self.udimize(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


    def invoke(self, context, event):
        ob = context.object
        enums = []
        self.trgmat = None
        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isUdimMaterial(mat)
            if self.trgmat is None:
                self.trgmat = mat
            enums.append((mat.name,mat.name,mat.name))  
        #self.active = EnumProperty(items=enums, name="Active")     
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def isUdimMaterial(self, mat):
        du = str(1001 + mat.DazUDim)
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                print("II", mat.name, node.image.name, du)
                return (node.image.name[-4:] == du)
        return False


    def udimize(self, context):
        from shutil import copyfile

        ob = context.object
        mats = []
        mnums = []
        amat = None
        for mn,umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                if amat is None:
                    amat = mat
                    amnum = mn
                else:
                    mnums.append(mn)
                    
        print("Use", mats)
        print("Active", amat, amnum)
        print("Mnums", mnums)
        
        if amat is None:
            raise DazError("No materials selected")

        self.nodes = {}
        for mat in mats:
            self.nodes[mat.name] = self.getChannels(mat)

        for key,anode in self.nodes[amat.name].items():
            anode.image.source = "TILED"
            anode.extension = "CLIP"
            basename = "T_" + self.getBaseName(anode.name, amat.DazUDim)
            for mat in mats:
                nodes = self.nodes[mat.name]
                if key in nodes.keys():
                    img = nodes[key].image
                    self.updateImage(img, basename, mat.DazUDim)
                    if mat == amat:
                        img.name = basename + "1001" + os.path.splitext(img.name)[1]

        for f in ob.data.polygons:
            if f.material_index in mnums:
                f.material_index = amnum

        mnums.reverse()
        for mn in mnums:
            if mn != amnum:
                ob.data.materials.pop(index=mn)


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
                            

    def getBaseName(self, string, udim):
        du = str(1001 + udim)
        if string[-4:] == du:
            return string[:-4]
        else:
            return string
               

    def updateImage(self, img, basename, udim):
        from shutil import copyfile
        du = str(1001 + udim)
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        folder = os.path.dirname(src)        
        fname,ext = os.path.splitext(bpy.path.basename(src))
        trg = os.path.join(folder, basename + du + ext)
        print("\nUPD", img.name, img.filepath)
        print("S", src)
        print("B", basename)
        print("T", trg)
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)
        print("F", img.filepath)
        
#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazUdimGroup,
    DAZ_OT_UdimizeMaterials,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
        
def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
        


