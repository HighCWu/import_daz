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
import math
from mathutils import Vector
from .settings import GS, LS
from urllib.parse import unquote

#-------------------------------------------------------------
#   Blender 2.8 compatibility
#-------------------------------------------------------------

if True:
    from . import buttons28 as B

    Region = "UI"
    HideViewport = "hide_viewport"
    DrawType = "display_type"
    ShowXRay = "show_in_front"

    def getHideViewport(ob):
        return (ob.hide_get() or ob.hide_viewport)

    def setHideViewport(ob, value):
        ob.hide_set(value)
        ob.hide_viewport = value

    def getSelectedObjects(context):
        return [ob for ob in context.scene.collection.all_objects
                if ob.select_get() and not (ob.hide_get() or ob.hide_viewport)]

    def getSelectedMeshes(context):
        return [ob for ob in context.scene.collection.all_objects
                if ob.select_get() and ob.type == 'MESH' and not (ob.hide_get() or ob.hide_viewport)]

    def getSelectedArmatures(context):
        return [ob for ob in context.scene.collection.all_objects
                if ob.select_get() and ob.type == 'ARMATURE' and not (ob.hide_get() or ob.hide_viewport)]

    def linkObject(context, ob):
        context.scene.collection.objects.link(ob)

    def getActiveObject(context):
        return context.view_layer.objects.active

    def setActiveObject(context, ob):
        try:
            context.view_layer.objects.active = ob
            return True
        except:
            return False

    def putOnHiddenLayer(ob):
        ob.hide_set(True)
        ob.hide_viewport = True
        ob.hide_render = True

    def createHiddenCollection(context, parent, cname="Hidden"):
        coll = bpy.data.collections.new(name=cname)
        if parent is None:
            parent = context.collection
        parent.children.link(coll)
        coll.hide_viewport = True
        coll.hide_render = True
        return coll

    def inSceneLayer(context, ob):
        if getHideViewport(ob):
            return False
        return inCollection(context.view_layer.layer_collection, ob)

    def inCollection(layer, ob):
        if layer.hide_viewport:
            return False
        elif not layer.exclude and ob in layer.collection.objects.values():
            return True
        for child in layer.children:
            if inCollection(child, ob):
                return True
        return False

    def showSceneLayer(context, ob):
        coll = context.collection
        coll.objects.link(ob)


    def activateObject(context, ob):
        context.view_layer.objects.active = ob
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            ok = True
        except RuntimeError:
            print("Could not activate", ob.name)
            ok = False
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        return ok


    def selectObjects(context, objects):
        if context.object:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:
            try:
                ob.select_set(True)
            except RuntimeError:
                pass

    def unlinkAll(ob):
        for coll in bpy.data.collections:
            if ob in coll.objects.values():
                coll.objects.unlink(ob)

    def updateScene(context):
        dg = context.evaluated_depsgraph_get()
        dg.update()

    def updateObject(context, ob):
        dg = context.evaluated_depsgraph_get()
        return ob.evaluated_get(dg)

#-------------------------------------------------------------
#   Overridable properties
#-------------------------------------------------------------

if bpy.app.version < (2,90,0):
    def BoolPropOVR(default, description=""):
        return bpy.props.BoolProperty(default=default, description=description)

    def FloatPropOVR(default, description="", precision=2, min=0, max=1):
        return bpy.props.FloatProperty(default=default, description=description, precision=precision, min=min, max=max)

    def setOverridable(rna, attr):
        pass
else:
    def BoolPropOVR(default, description=""):
        return bpy.props.BoolProperty(default=default, description=description, override={'LIBRARY_OVERRIDABLE'})

    def FloatPropOVR(default, description="", precision=2, min=0, max=1):
        return bpy.props.FloatProperty(default=default, description=description, precision=precision, min=min, max=max, override={'LIBRARY_OVERRIDABLE'})

    def setOverridable(rna, attr):
        rna.property_overridable_library_set('["%s"]' % attr, True)


def setattrOVR(rna, attr, value):
    setattr(rna, attr, value)
    rna[attr] = value
    setOverridable(rna, attr)

#-------------------------------------------------------------
#   Utility functions
#-------------------------------------------------------------

def deleteObjects(context, objects):
    selectObjects(context, objects)
    bpy.ops.object.delete(use_global=False)
    for ob in objects:
        unlinkAll(ob)
        if ob:
            del ob


def setWorldMatrix(ob, wmat):
    if ob.parent:
        ob.matrix_parent_inverse = ob.parent.matrix_world.inverted()
    ob.matrix_world = wmat
    if Vector(ob.location).length < 1e-6:
        ob.location = Zero
    if Vector(ob.rotation_euler).length < 1e-6:
        ob.rotation_euler = Zero
    if (Vector(ob.scale) - One).length < 1e-6:
        ob.scale = One

#-------------------------------------------------------------
#   Updating
#-------------------------------------------------------------

def updateRig(rig, context):
    ob = context.object
    if ob is None:
        return
    if bpy.app.version >= (2,80,0):
        if ob.type == 'MESH' and rig.name in context.view_layer.objects:
            context.view_layer.objects.active = rig
            bpy.ops.object.posemode_toggle()
            bpy.ops.object.posemode_toggle()
            context.view_layer.objects.active = ob
        elif ob.type == 'ARMATURE':
            bpy.ops.object.posemode_toggle()
            bpy.ops.object.posemode_toggle()

    else:
        if ob.type == "MESH":
            context.scene.objects.active = rig
            if rig.mode == "POSE":
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
            elif rig.mode == "OBJECT":
                bpy.ops.object.posemode_toggle()
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
                bpy.ops.object.posemode_toggle()
            context.scene.objects.active = ob

        elif ob.type == 'ARMATURE':
            if rig.mode == "POSE":
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
            elif rig.mode == "OBJECT":
                bpy.ops.object.posemode_toggle()
                pos = rig.pose.bones[0].location[0]
                rig.pose.bones[0].location[0] = pos + 0
                bpy.ops.object.posemode_toggle()


def updateDrivers(ob):
    def updateRna(rna):
        if rna and rna.animation_data:
            for fcu in rna.animation_data.drivers:
                string = str(fcu.driver.expression)
                fcu.driver.expression = string

    if ob:
        updateRna(ob)
        if ob.type == 'MESH':
            updateRna(ob.data.shape_keys)

#-------------------------------------------------------------
#   More utility functions
#-------------------------------------------------------------

def instRef(ref):
    return ref.rsplit("#",1)[-1]


def tolower(url):
    if not GS.caseSensitivePaths:
        return url.lower()
    else:
        return url


def clamp(value):
    return min(1, max(0, value))


def isVector(value):
    return (hasattr(value, "__len__") and len(value) >= 3)


def addToStruct(struct, key, prop, value):
    if key not in struct.keys():
        struct[key] = {}
    struct[key][prop] = value


def averageColor(value):
    if isVector(value):
        x,y,z = value
        return (x+y+z)/3
    else:
        return value


Zero = Vector((0,0,0))
One = Vector((1,1,1))

def hasObjectTransforms(ob):
    return (ob.location != Zero or
            Vector(ob.rotation_euler) != Zero or
            ob.scale != One)


def match(tests, string):
    for test in tests:
        if test in string:
            return test
    return None


def sorted(seq):
    slist = list(seq)
    slist.sort()
    return slist


def hasPoseBones(rig, bnames):
    for bname in bnames:
        if bname not in rig.pose.bones.keys():
            return False
    return True


def getCurrentValue(struct, default=None):
    if "current_value" in struct.keys():
        return struct["current_value"]
    elif "value" in struct.keys():
        return struct["value"]
    else:
        return default

#-------------------------------------------------------------
#   Profiling
#-------------------------------------------------------------

from time import perf_counter

class Timer:
    def __init__(self):
        self.t = perf_counter()

    def print(self, msg):
        t = perf_counter()
        print("%8.6f: %s" % (t-self.t, msg))
        self.t = t

#-------------------------------------------------------------
#   Progress
#-------------------------------------------------------------

def startProgress(string):
    print(string)
    wm = bpy.context.window_manager
    wm.progress_begin(0, 100)

def endProgress():
    wm = bpy.context.window_manager
    wm.progress_update(100)
    wm.progress_end()

def showProgress(n, total):
    pct = (100.0*n)/total
    wm = bpy.context.window_manager
    wm.progress_update(int(pct))

#-------------------------------------------------------------
#   Coords
#-------------------------------------------------------------

def getIndex(id):
    if id == "x": return 0
    elif id == "y": return 1
    elif id == "z": return 2
    else: return -1


def getCoord(p):
    co = Zero
    for c in p:
        co[getIndex(c["id"])] = c["value"]
    return d2b(co)


def d2b90(v):
    return LS.scale*Vector((v[0], -v[2], v[1]))

def d2b90u(v):
    return Vector((v[0], -v[2], v[1]))

def d2b90s(v):
    return Vector((v[0], v[2], v[1]))


def d2b00(v):
    return LS.scale*Vector(v)

def d2b00u(v):
    return Vector(v)

def d2b00s(v):
    return Vector(v)


def d2b(v):
    if GS.zup:
        return d2b90(v)
    else:
        return d2b00(v)

def d2bu(v):
    if GS.zup:
        return d2b90u(v)
    else:
        return d2b00u(v)

def d2bs(v):
    if GS.zup:
        return d2b90s(v)
    else:
        return d2b00s(v)


D2R = "%.6f*" % (math.pi/180)
D = math.pi/180



