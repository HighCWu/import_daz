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
from bpy.props import *
#from .drivers import *
from .utils import *
from .error import *


def getMaskName(string):
    return "Mask_" + string.split(".",1)[0]

def getHidePropName(string):
    return "Mhh" + string.split(".",1)[0]

def isHideProp(string):
    return (string[0:3] == "Mhh")

def getMannequinName(string):
    return "MhhMannequin"

#------------------------------------------------------------------------
#   Object selection
#------------------------------------------------------------------------

class ObjectSelection(B.SingleProp):
    def draw(self, context):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")
        for pg in context.scene.DazSelector:
            row = self.layout.row()
            row.prop(pg, "select", text="")
            row.label(text = pg.text)

    def selectAll(self, context):
        for pg in context.scene.DazSelector:
            pg.select = True
        
    def selectNone(self, context):
        for pg in context.scene.DazSelector:
            pg.select = False

    def getSelectedMeshes(self, context):
        selected = []
        for pg in context.scene.DazSelector:
            if pg.select:
                ob = bpy.data.objects[pg.text]
                selected.append(ob)
        return selected    
    
    def invoke(self, context, event):
        from .morphing import setSelector
        setSelector(self)
        pgs = context.scene.DazSelector
        pgs.clear()
        for ob in getSceneObjects(context):
            if ob.type == self.type and ob != context.object:
                pg = pgs.add()
                pg.text = ob.name
                pg.select = True
        return DazPropsOperator.invoke(self, context, event)
        
#------------------------------------------------------------------------
#    Setup: Add and remove hide drivers
#------------------------------------------------------------------------

class HidersHandler:

    def run(self, context):
        from .morphing import prettifyAll
        from .driver import updateAll
        rig = context.object
        for ob in self.getMeshesInGroup(context, rig):
            self.handleHideDrivers(ob, rig, context)
            setattr(ob, self.flag, self.value)
        setattr(rig, self.flag, self.value)
        prettifyAll(context)
        updateAll(context)
        setActiveObject(context, rig)


    def getMeshesInGroup(self, context, rig):
        self.collection = None
        meshes = list(rig.children)
        if bpy.app.version >= (2,80,0):
            for coll in bpy.data.collections:
                if rig in coll.all_objects.values():
                    for ob in meshes:
                        if ob in coll.all_objects.values():
                            self.collection = coll
                            return meshes
        return meshes


    def handleHideDrivers(self, clo, rig, context):
        prop = getHidePropName(clo.name)
        self.handleProp(prop, clo, rig, context)
        if clo.DazMannequin:
            return
        modname = getMaskName(clo.name)
        for ob in rig.children:
            for mod in ob.modifiers:
                if (mod.type == 'MASK' and mod.name == modname):
                    self.handleMod(prop, rig, mod)


class DAZ_OT_AddVisibility(DazPropsOperator, ObjectSelection, B.ActiveMesh, B.SingleProp, IsArmature):
    bl_idname = "daz.add_visibility_drivers"
    bl_label = "Add Visibility Drivers"
    bl_description = "Control visibility with rig property. For file linking."
    bl_options = {'UNDO'}

    type = 'MESH'

    def draw(self, context):    
        self.layout.prop(self, "singleProp")
        if self.singleProp:
            self.layout.prop(self, "maskName")
        self.layout.prop(self, "activeMesh")
        ObjectSelection.draw(self, context)
        
        
    def run(self, context):
        rig = context.object
        print("Create visibility drivers for %s:" % rig.name)
        selected = self.getSelectedMeshes(context)
        ob = bpy.data.objects[self.activeMesh]
        if self.singleProp:      
            for clo in selected:
                self.createObjectVisibility(rig, clo, self.maskName)            
            self.createMaskVisibility(rig, ob, self.maskName)
        else:
            for clo in selected:
                self.createObjectVisibility(rig, clo, clo.name)
                self.createMaskVisibility(rig, ob, clo.name)
        rig.DazVisibilityDrivers = True
        updateDrivers(rig)
        print("Visibility drivers created")
 
 
    def createObjectVisibility(self, rig, ob, obname):
        from .driver import makePropDriver, setBoolProp
        prop = getHidePropName(obname)
        setBoolProp(rig, prop, True, "Show %s" % prop)
        makePropDriver(prop, ob, HideViewport, rig, expr="not(x)")
        makePropDriver(prop, ob, "hide_render", rig, expr="not(x)")


    def createMaskVisibility(self, rig, ob, obname):
        from .driver import makePropDriver
        prop = getHidePropName(obname)
        modname = getMaskName(obname)
        masked = False
        for mod in ob.modifiers:
            if (mod.type == 'MASK' and
                mod.name == modname):
                masked = True
                break
        if masked:
            makePropDriver(prop, mod, "show_viewport", rig, expr="x")
            makePropDriver(prop, mod, "show_render", rig, expr="x")


    def invoke(self, context, event):
        return ObjectSelection.invoke(self, context, event)


class DAZ_OT_RemoveVisibility(DazOperator, HidersHandler):
    bl_idname = "daz.remove_visibility_drivers"
    bl_label = "Remove Visibility Drivers"
    bl_description = "Remove ability to control visibility from rig property"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityDrivers)

    def run(self, context):
        rig = context.object
        for ob in rig.children:
            ob.driver_remove(HideViewport)
            ob.driver_remove("hide_render")
            setattr(ob, HideViewport, False)
            ob.hide_render = False
            for mod in ob.modifiers:
                if mod.type == 'MASK':
                    mod.driver_remove("show_viewport")
                    mod.driver_remove("show_render")
                    mod.show_viewport = True
                    mod.show_render = True
        for prop in rig.keys():
            if isHideProp(prop):
                del rig[prop]
        updateDrivers(rig)
        rig.DazVisibilityDrivers = False
        print("Visibility drivers removed")

#------------------------------------------------------------------------
#   Hider collections
#------------------------------------------------------------------------

if bpy.app.version >= (2,80,0):

    class DAZ_OT_AddHiderCollections(DazOperator, HidersHandler):
        bl_idname = "daz.add_hide_collections"
        bl_label = "Add Visibility Collections"
        bl_description = "Control visibility with rig property. For file linking."
        bl_options = {'UNDO'}

        flag = "DazVisibilityCollections"
        value = True

        @classmethod
        def poll(self, context):
            ob = context.object
            return (ob and ob.type == 'ARMATURE' and not ob.DazVisibilityCollections)

        def getMeshesInGroup(self, context, rig):
            meshes = HidersHandler.getMeshesInGroup(self, context, rig)
            return [rig] + meshes

        def handleProp(self, prop, clo, rig, context):
            if self.collection is None:
                return
            subcoll = bpy.data.collections.new(clo.name)
            self.collection.children.link(subcoll)
            if clo in self.collection.objects.values():
                self.collection.objects.unlink(clo)
            subcoll.objects.link(clo)

        def handleMod(self, prop, rig, mod):
            return


    class DAZ_OT_RemoveHiderCollections(DazOperator, HidersHandler):
        bl_idname = "daz.remove_hide_collections"
        bl_label = "Remove Visibility Collections"
        bl_description = "Remove ability to control visibility from rig property"
        bl_options = {'UNDO'}

        flag = "DazVisibilityCollections"
        value = False

        @classmethod
        def poll(self, context):
            ob = context.object
            return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityCollections)

        def getMeshesInGroup(self, context, rig):
            meshes = HidersHandler.getMeshesInGroup(self, context, rig)
            return [rig] + meshes

        def handleProp(self, prop, clo, rig, context):
            if self.collection is None:
                return
            for subcoll in self.collection.children.values():
                if clo in subcoll.objects.values():
                    if subcoll in self.collection.children.values():
                        self.collection.children.unlink(subcoll)
                    subcoll.objects.unlink(clo)
                    self.collection.objects.link(clo)
                    break

        def handleMod(self, prop, rig, mod):
            return

#------------------------------------------------------------------------
#   Show/Hide all
#------------------------------------------------------------------------

def setAllVisibility(context, prefix, value):
    from .morphing import autoKeyProp
    from .driver import updateAll
    rig = context.object
    scn = context.scene
    if rig is None:
        return
    for key in rig.keys():
        if key[0:3] == prefix:
            if key:
                rig[key] = value
                autoKeyProp(rig, key, scn, scn.frame_current, True)
    updateAll(context)


class DAZ_OT_ShowAll(DazOperator, B.PrefixString):
    bl_idname = "daz.show_all"
    bl_label = "Show All"
    bl_description = "Show all meshes/makeup of this rig"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        setAllVisibility(context, self.prefix, True)


class DAZ_OT_HideAll(DazOperator, B.PrefixString):
    bl_idname = "daz.hide_all"
    bl_label = "Hide All"
    bl_description = "Hide all meshes/makeup of this rig"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        setAllVisibility(context, self.prefix, False)

#------------------------------------------------------------------------
#   Mask modifiers
#------------------------------------------------------------------------

class DAZ_OT_CreateMasks(DazPropsOperator, IsMesh, ObjectSelection):
    bl_idname = "daz.create_masks"
    bl_label = "Create Masks"
    bl_description = "Create vertex groups and mask modifiers in active mesh for selected meshes"
    bl_options = {'UNDO'}

    type = 'MESH'

    def draw(self, context):    
        self.layout.prop(self, "singleProp")
        if self.singleProp:
            self.layout.prop(self, "maskName")
        else:
            ObjectSelection.draw(self, context)
        
    
    def run(self, context):
        print("Create masks for %s:" % context.object.name)
        if self.singleProp:
            modname = getMaskName(self.maskName)
            print("  ", modname)
            self.createMask(context.object, modname)
        else:
            for ob in self.getSelectedMeshes(context):
                modname = getMaskName(ob.name)
                print("  ", ob.name, modname)
                self.createMask(context.object, modname)
        print("Masks created")
            
            
    def createMask(self, ob, modname):            
        mod = None
        for mod1 in ob.modifiers:
            if mod1.type == 'MASK' and mod1.name == modname:
                mod = mod1
        if modname in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[modname]
        else:
            vgrp = ob.vertex_groups.new(name=modname)
        if mod is None:
            mod = ob.modifiers.new(modname, 'MASK')
        mod.vertex_group = modname
        mod.invert_vertex_group = True

    
    def invoke(self, context, event):
        return ObjectSelection.invoke(self, context, event)

#----------------------------------------------------------
#   Create collections
#----------------------------------------------------------

class DAZ_OT_CreateCollections(DazPropsOperator, B.NameString):
    bl_idname = "daz.create_collections"
    bl_label = "Create Collections"
    bl_description = "Create collections for selected objects"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "name")

    def run(self, context):
        newcoll = bpy.data.collections.new(self.name)
        coll = context.collection
        coll.children.link(newcoll)
        meshcoll = None
        for ob in coll.objects:
            if ob.select_get():
                if ob.type == 'EMPTY':
                    if meshcoll is None:
                        meshcoll = bpy.data.collections.new(self.name + " Meshes")
                        newcoll.children.link(meshcoll)
                    subcoll = bpy.data.collections.new(ob.name)
                    meshcoll.children.link(subcoll)
                    ob.hide_select = True
                    subcoll.objects.link(ob)
                    coll.objects.unlink(ob)
                else:
                    ob.show_in_front = True
                    newcoll.objects.link(ob)
                    coll.objects.unlink(ob)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddVisibility,
    DAZ_OT_RemoveVisibility,
    DAZ_OT_ShowAll,
    DAZ_OT_HideAll,
    DAZ_OT_CreateMasks,
]

if bpy.app.version >= (2,80,0):
    classes += [
        DAZ_OT_AddHiderCollections,
        DAZ_OT_RemoveHiderCollections,
        DAZ_OT_CreateCollections,
    ]

def initialize():
    bpy.types.Object.DazVisibilityDrivers = BoolProperty(default = False)
    bpy.types.Object.DazVisibilityCollections = BoolProperty(default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)


