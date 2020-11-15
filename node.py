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
import math
from mathutils import Matrix, Vector, Euler
from collections import OrderedDict
from .asset import Accessor, Asset
from .channels import Channels
from .formula import Formula
from .error import *
from .utils import *

#-------------------------------------------------------------
#   External access
#-------------------------------------------------------------

def parseNode(asset, struct):
    from .figure import Figure, LegacyFigure
    from .bone import Bone
    from .camera import Camera
    from .light import Light
    try:
        type = struct["type"]
    except KeyError:
        type = None

    if type == "figure":
        return asset.parseTypedAsset(struct, Figure)
    elif type == "legacy_figure":
        return asset.parseTypedAsset(struct, LegacyFigure)
    elif type == "bone":
        return asset.parseTypedAsset(struct, Bone)
    elif type == "node":
        return asset.parseTypedAsset(struct, Node)
    elif type == "camera":
        return asset.parseTypedAsset(struct, Camera)
    elif type == "light":
        return asset.parseTypedAsset(struct, Light)
    else:
        msg = "Not implemented node asset type %s" % type
        print(msg)
        #raise NotImplementedError(msg)
        return None

#-------------------------------------------------------------
#   Instance
#-------------------------------------------------------------

def copyElements(struct):
    nstruct = {}
    for key,value in struct.items():
        if isinstance(value, dict):
            nstruct[key] = value.copy()
        else:
            nstruct[key] = value
    return nstruct


def getChannelIndex(key):
    if key == "scale/general":
        channel = "general_scale"
        idx = -1
    else:
        channel,comp = key.split("/")
        idx = getIndex(comp)
    return channel, idx


class Instance(Accessor, Channels):

    def __init__(self, fileref, node, struct):
        from .asset import normalizeRef

        Accessor.__init__(self, fileref)
        self.node = node
        self.index = len(node.instances)
        self.figure = None
        self.id = normalizeRef(struct["id"])
        self.id = self.getSelfId()
        node.instances[self.id] = self
        self.geometries = node.geometries
        node.geometries = []
        self.rotation_order = node.rotation_order
        self.collection = LS.collection
        if "parent" in struct.keys() and node.parent is not None:
            self.parent = node.parent.getInstance(node.caller, struct["parent"])
            if self.parent == self:
                print("Self-parent", self)
                self.parent = None
            if self.parent:
                self.parent.children[self.id] = self
                self.collection = self.parent.collection
        else:
            self.parent = None
        node.parent = None
        self.children = {}
        self.label = node.label
        node.label = None
        self.extra = node.extra
        node.extra = []
        self.channels = node.channels
        node.channels = {}
        self.shstruct = {}
        self.center = Vector((0,0,0))
        self.refgroup = None
        self.isGroupNode = False
        self.isNodeInstance = False
        self.node2 = None
        self.hdobject = None
        self.name = node.getLabel(self)
        self.modifiers = {}
        self.materials = node.materials
        node.materials = {}
        self.attributes = copyElements(node.attributes)
        self.restdata = None
        node.clearTransforms()


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        return "<Instance %s %d N: %s P: %s R: %s>" % (self.label, self.index, self.node.name, pname, self.rna)


    def getSelfId(self):
        return self.id


    def preprocess(self, context):
        self.updateMatrices()
        for channel in self.channels.values():
            if "type" not in channel.keys():
                continue
            elif channel["type"] == "node" and "node" in channel.keys():
                ref = channel["node"]
                node = self.getAsset(ref)
                if node:
                    self.node2 = node.instances[instRef(ref)]
            elif channel["type"] == "bool":
                words = channel["id"].split("_")
                if (words[0] == "material" and words[1] == "group" and words[-1] == "vis"):
                    label = channel["label"]
                    value = getCurrentValue(channel)
                    for geonode in self.geometries:
                        geonode.data.material_group_vis[label] = value
                elif (words[0] == "facet" and words[1] == "group" and words[-1] == "vis"):
                    pass

        for extra in self.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/shell":
                self.shstruct = extra
            elif extra["type"] == "studio/node/group_node":
                self.isGroupNode = True
            elif extra["type"] == "studio/node/instance":
                self.isNodeInstance = True
            elif extra["type"] == "studio/node/strand_hair":
                LS.strandHairs.append(self.name)

        for geo in self.geometries:
            geo.preprocess(context, self)


    def preprocess2(self, context):
        if self.isGroupNode and bpy.app.version >= (2,80,0):
            coll = bpy.data.collections.new(name=self.label)
            self.collection.children.link(coll)
            self.collection = coll
            self.groupChildren(self.collection)


    def groupChildren(self, coll):
        for child in self.children.values():
            child.collection = coll
            child.groupChildren(coll)


    def buildChannels(self, context):
        ob = self.rna
        if ob is None:
            return
        for channel in self.channels.values():
            if self.ignoreChannel(channel):
                continue
            value = getCurrentValue(channel)
            if channel["id"] == "Renderable":
                if not value:
                    ob.hide_render = True
            elif channel["id"] == "Visible in Viewport":
                if not value:
                    setHideViewport(ob, True)
            elif channel["id"] == "Visible":
                if not value:
                    ob.hide_render = True
                    setHideViewport(ob, True)
            elif channel["id"] == "Selectable":
                if not value:
                    ob.hide_select = True
            elif channel["id"] == "Visible in Simulation":
                pass
            elif channel["id"] == "Cast Shadows":
                pass
            elif channel["id"] == "Instance Mode":
                #print("InstMode", ob.name, value)
                pass
            elif channel["id"] == "Instance Target":
                #print("InstTarg", ob.name)
                pass
            elif channel["id"] == "Point At":
                pass


    def ignoreChannel(self, channel):
        return ("id" not in channel.keys() or
                ("visible" in channel.keys() and not channel["visible"]))


    def buildExtra(self, context):
        pass


    def postbuild(self, context):
        self.parentObject(context, self.rna)
        for geonode in self.geometries:
            geonode.postbuild(context, self)


    def buildInstance(self, context):
        if self.isNodeInstance and GS.useInstancing:
            if self.node2 is None:
                print('Instance "%s" has no node' % self.name)
            elif self.rna is None:
                print('Instance "%s" has not been built' % self.name)
            elif self.rna.type != 'EMPTY':
                print('Instance "%s" is not an empty' % self.name)
            elif self.node2.rna is None:
                print('Instance "%s" node2 "%s" not built' % (inst.name, inst.node2.name))
            else:
                self.buildNodeInstance(context)


    def buildNodeInstance(self, context):
        ob = self.node2.rna
        if self.node2.refgroup:
            refgroup = self.node2.refgroup
        else:
            refgroup = self.getInstanceGroup(ob)
        if refgroup is None:
            refgroup,empty = self.makeNewRefgroup(context, ob)
        self.duplicate(self.rna, refgroup)


    def makeNewRefgroup(self, context, ob):
        refname = ob.name + " REF"
        if bpy.app.version < (2,80,0):
            refgroup = bpy.data.groups.new(name=refname)
        else:
            refgroup = bpy.data.collections.new(name=refname)
            if LS.refGroups is None:
                LS.refGroups = bpy.data.collections.new(name=LS.collection.name + " REFS")
                context.scene.collection.children.link(LS.refGroups)
            LS.refGroups.children.link(refgroup)
            layer = findLayerCollection(context.view_layer.layer_collection, refgroup)
            layer.exclude = True

        obname = ob.name
        ob.name = refname
        empty = bpy.data.objects.new(obname, None)
        if self.node2:
            self.node2.refgroup = refgroup
        self.duplicate(empty, refgroup)
        wmat = ob.matrix_world.copy()
        LS.duplis.append((self, ob, empty, wmat, refgroup))
        return refgroup,empty


    def getInstanceGroup(self, ob):
        if bpy.app.version < (2,80,0):
            if ob.dupli_type == 'GROUP':
                for ob1 in ob.dupli_group.objects:
                    group = self.getInstanceGroup(ob1)
                    if group:
                        return group
                return ob.dupli_group
        else:
            if ob.instance_type == 'COLLECTION':
                for ob1 in ob.instance_collection.objects:
                    group = self.getInstanceGroup(ob1)
                    if group:
                        return group
                return ob.instance_collection
        return None


    def duplicate(self, empty, group):
        if bpy.app.version < (2,80,0):
            empty.dupli_type = 'GROUP'
            empty.dupli_group = group
        else:
            empty.instance_type = 'COLLECTION'
            empty.instance_collection = group


    def poseRig(self, context):
        pass


    def finalize(self, context):
        for geonode in self.geometries:
            geonode.finalize(context, self)
        self.buildChannels(context)


    def formulate(self, key, value):
        pass


    def updateMatrices(self):
        # From http://docs.daz3d.com/doku.php/public/dson_spec/object_definitions/node/start
        #
        # center_offset = center_point - parent.center_point
        # global_translation = parent.global_transform * (center_offset + translation)
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        # global_scale for nodes that inherit scale = parent.global_scale * orientation * scale * general_scale * (orientation)-1
        # global_scale for nodes = parent.global_scale * (parent.local_scale)-1 * orientation * scale * general_scale * (orientation)-1
        # global_transform = global_translation * global_rotation * global_scale

        trans = d2b00(self.attributes["translation"])
        rotation = Vector(self.attributes["rotation"])*D
        genscale = self.attributes["general_scale"]
        scale = Vector(self.attributes["scale"]) * genscale
        orientation = Vector(self.attributes["orientation"])*D
        self.cpoint = d2b00(self.attributes["center_point"])

        lrot = Euler(rotation, self.rotation_order).to_matrix().to_4x4()
        self.lscale = Matrix()
        for i in range(3):
            self.lscale[i][i] = scale[i]
        orient = Euler(orientation).to_matrix().to_4x4()

        par = self.parent
        if par:
            coffset = self.cpoint - self.parent.cpoint
            self.wtrans = Mult2(par.wmat, coffset + trans)
            self.wrot = Mult4(par.wrot, orient, lrot, orient.inverted())
            oscale = Mult3(orient, self.lscale, orient.inverted())
            if True:  # self.inherits_scale:
                self.wscale = Mult2(par.wscale, oscale)
            else:
                self.wscale = Mult3(par.wscale, par.lscale.inverted(), oscale)
        else:
            self.wtrans = self.cpoint + trans
            self.wrot = Mult3(orient, lrot, orient.inverted())
            self.wscale = Mult3(orient, self.lscale, orient.inverted())

        transmat = Matrix.Translation(self.wtrans)
        self.wmat = Mult3(transmat, self.wrot, self.wscale)
        if GS.zup:
            self.worldmat = Mult3(self.RXP, self.wmat, self.RXN)
        else:
            self.worldmat = self.wmat

    RXP = Matrix.Rotation(math.pi/2, 4, 'X')
    RXN = Matrix.Rotation(-math.pi/2, 4, 'X')


    def parentObject(self, context, ob):
        from .figure import FigureInstance
        from .bone import BoneInstance

        if ob is None:
            return

        if self.parent is None:
            ob.parent = None
        elif self.parent.rna == ob:
            print("Warning: Trying to parent %s to itself" % ob)
            ob.parent = None
        elif isinstance(self.parent, FigureInstance):
            for geo in self.geometries:
                geo.setHideInfo()
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        elif isinstance(self.parent, BoneInstance):
            if self.parent.figure is None:
                print("No figure found:", self.parent)
                return
            rig = self.parent.figure.rna
            ob.parent = rig
            bname = self.parent.node.name
            if bname in rig.pose.bones.keys():
                ob.parent_bone = bname
                ob.parent_type = 'BONE'
        elif isinstance(self.parent, Instance):
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        else:
            raise RuntimeError("Unknown parent %s %s" % (self, self.parent))

        setWorldMatrix(ob, self.worldmat)
        self.node.postTransform()


def transformDuplis():
    for inst,ob,empty,wmat,refgroup in LS.duplis:
        if bpy.app.version < (2,80,0):
            putOnHiddenLayer(ob)
        if ob.name in inst.collection.objects:
            inst.collection.objects.unlink(ob)
        if ob.name in LS.collection.objects:
            LS.collection.objects.unlink(ob)
        empty.parent = ob.parent
        setWorldMatrix(empty, wmat)
        for child in ob.children:
            addToRefgroup(child, refgroup, inst)
        ob.parent = None
        ob.matrix_world = Matrix()
        inst.collection.objects.link(empty)
        refgroup.objects.link(ob)
        print("LiiS", refgroup.name, ob.name, ob.type)


def addToRefgroup(ob, refgroup, inst):
    if ob.name in inst.collection.objects:
        inst.collection.objects.unlink(ob)
    if ob.name not in refgroup.objects:
        if bpy.app.version < (2,80,0):
            putOnHiddenLayer(ob)
        try:
            refgroup.objects.link(ob)
        except RuntimeError:
            print("Cannot link '%s' to '%s'" % (ob.name, refgroup.name))
            pass
    if checkDependency(ob, ob):
        refgroup.objects.unlink(ob)
    for child in ob.children:
        addToRefgroup(child, refgroup, inst)


def checkDependency(empty, ob):
    dupli = getDupli(ob)
    if dupli:
        if empty.name in dupli.objects:
            print("DEPENDENCY", empty.name)
            return True
        else:
            for ob in dupli.objects:
                if checkDependency(empty, ob):
                    return True
    else:
        return False


def getDupli(empty):
    if bpy.app.version < (2,80,0):
        if empty.dupli_type == 'GROUP':
            return empty.dupli_group
    else:
        if empty.instance_type == 'COLLECTION':
            return empty.instance_collection
    return None


def printExtra(self, name):
    print(name, self.id)
    for extra in self.extra:
        print("  ", extra.keys())


def findLayerCollection(layer, coll):
    if layer.collection == coll:
        return layer
    for child in layer.children:
        clayer = findLayerCollection(child, coll)
        if clayer:
            return clayer
    return None

#-------------------------------------------------------------
#   Node
#-------------------------------------------------------------

class Node(Asset, Formula, Channels):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Formula.__init__(self)
        Channels.__init__(self)
        self.instances = {}
        self.count = 0
        self.data = None
        self.center = None
        self.geometries = []
        self.materials = {}
        self.rotation_order = 'XYZ'
        self.attributes = self.defaultAttributes()
        self.origAttrs = self.defaultAttributes()
        self.figure = None


    def defaultAttributes(self):
        return {
            "center_point": Vector((0,0,0)),
            "end_point": Vector((0,0,0)),
            "orientation": Vector((0,0,0)),
            "translation": Vector((0,0,0)),
            "rotation": Vector((0,0,0)),
            "scale": Vector((1,1,1)),
            "general_scale": 1
        }


    def clearTransforms(self):
        default = self.defaultAttributes()
        for key in ["translation", "rotation", "scale", "general_scale"]:
            self.attributes[key] = default[key]


    def __repr__(self):
        pid = (self.parent.id if self.parent else None)
        return ("<Node %s P: %s>" % (self.id, pid))


    def postTransform(self):
        pass


    def makeInstance(self, fileref, struct):
        return Instance(fileref, self, struct)


    def getInstance(self, caller, ref, strict=True):
        iref = instRef(ref)
        if caller:
            try:
                return caller.instances[iref]
            except KeyError:
                msg = ("Did not find instance %s in %s" % (iref, caller))
                insts = caller.instances
        else:
            try:
                return self.instances[iref]
            except KeyError:
                msg = ("Did not find instance %s in %s" % (iref, self))
                insts = self.instances
        if strict:
            reportError(msg, insts, trigger=(2,3))
        return None


    def parse(self, struct):
        Asset.parse(self, struct)
        Channels.parse(self, struct)

        for key,data in struct.items():
            if key == "formulas":
                self.formulas = data
            elif key == "inherits_scale":
                pass
            elif key == "rotation_order":
                self.rotation_order = data
            elif key in self.attributes.keys():
                self.setAttribute(key, data)

        for key in self.attributes.keys():
            self.origAttrs[key] = self.attributes[key]
        return self


    def setExtra(self, extra):
        pass


    Indices = { "x": 0, "y": 1, "z": 2 }

    def setAttribute(self, channel, data):
        if isinstance(data, list):
            for comp in data:
                idx = self.Indices[comp["id"]]
                value = getCurrentValue(comp)
                if value is not None:
                    self.attributes[channel][idx] = value
        else:
            self.attributes[channel] = getCurrentValue(data)


    def update(self, struct):
        from .geometry import GeoNode

        Asset.update(self, struct)
        Channels.update(self, struct)
        for channel,data in struct.items():
            if channel == "geometries":
                for geostruct in data:
                    if "url" in geostruct.keys():
                        geo = self.parseUrlAsset(geostruct)
                        node = GeoNode(self, geo, geostruct["id"])
                    else:
                        print("No geometry URL")
                        node = GeoNode(self, None, geostruct["id"])
                        self.saveAsset(geostruct, node)
                    node.parse(geostruct)
                    node.update(geostruct)
                    node.extra = self.extra
                    self.geometries.append(node)
            elif channel in self.attributes.keys():
                self.setAttribute(channel, data)
        self.count += 1


    def build(self, context, inst):
        center = d2b(inst.attributes["center_point"])
        if inst.geometries:
            for geonode in inst.geometries:
                geonode.buildObject(context, inst, center)
                inst.rna = geonode.rna
        else:
            self.buildObject(context, inst, center)
        if inst.extra:
            inst.buildExtra(context)


    def buildObject(self, context, inst, center):
        scn = context.scene
        if isinstance(self.data, Asset):
            if self.data.shstruct and GS.mergeShells:
                return
            ob = self.data.buildData(context, self, inst, center)
            if not isinstance(ob, bpy.types.Object):
                ob = bpy.data.objects.new(inst.name, self.data.rna)
        else:
            ob = bpy.data.objects.new(inst.name, self.data)
        self.rna = inst.rna = ob
        self.arrangeObject(ob, inst, context, center)
        self.subdivideObject(ob, inst, context)


    def arrangeObject(self, ob, inst, context, center):
        from .asset import normalizePath
        blenderRotMode = {
            'XYZ' : 'XZY',
            'XZY' : 'XYZ',
            'YXZ' : 'ZXY',
            'YZX' : 'ZYX',
            'ZXY' : 'YXZ',
            'ZYX' : 'YZX',
        }
        ob.rotation_mode = blenderRotMode[self.rotation_order]
        ob.DazRotMode = self.rotation_order
        ob.DazMorphPrefixes = False
        inst.collection.objects.link(ob)
        if bpy.app.version < (2,80,0):
            context.scene.objects.link(ob)
        ob.DazId = self.id
        ob.DazUrl = normalizePath(self.url)
        ob.DazScene = LS.scene
        ob.DazScale = LS.scale
        ob.DazOrient = inst.attributes["orientation"]
        self.subtractCenter(ob, inst, center)


    def subtractCenter(self, ob, inst, center):
        ob.location = -center
        inst.center = center


    def subdivideObject(self, ob, inst, context):
        pass


    def guessColor(self, scn, flag, inst):
        from .guess import guessColor
        for node in inst.geometries:
            if node.rna:
                guessColor(node.rna, scn, flag, LS.skinColor, LS.clothesColor, False)

#-------------------------------------------------------------
#   Transform matrix
#
#   dmat = Daz bone orientation, in Daz world space
#   bmat = Blender bone rest matrix, in Blender world space
#   rotmat = Daz rotation matrix, in Daz local space
#   trans = Daz translation vector, in Daz world space
#   wmat = Full transformation matrix, in Daz world space
#   mat = Full transformation matrix, in Blender local space
#
#-------------------------------------------------------------

def setParent(context, ob, rig, bname=None, update=True):
    if update:
        updateScene(context)
    if ob.parent != rig:
        wmat = ob.matrix_world.copy()
        ob.parent = rig
        if bname:
            ob.parent_bone = bname
            ob.parent_type = 'BONE'
        else:
            ob.parent_type = 'OBJECT'
        setWorldMatrix(ob, wmat)


def reParent(context, ob, rig):
    if ob.parent_type == 'BONE':
        bname = ob.parent_bone
    else:
        bname = None
    setParent(context, ob, rig, bname, False)


def clearParent(ob):
    wmat = ob.matrix_world.copy()
    ob.parent = None
    setWorldMatrix(ob, wmat)


def getTransformMatrices(pb):
    dmat = Euler(Vector(pb.bone.DazOrient)*D, 'XYZ').to_matrix().to_4x4()
    dmat.col[3][0:3] = d2b00(pb.bone.DazHead)

    parbone = pb.bone.parent
    if parbone and parbone.DazAngle != 0:
        rmat = Matrix.Rotation(parbone.DazAngle, 4, parbone.DazNormal)
    else:
        rmat = Matrix()

    if GS.zup:
        bmat = Mult2(Matrix.Rotation(-90*D, 4, 'X'), pb.bone.matrix_local)
    else:
        bmat = pb.bone.matrix_local

    return dmat,bmat,rmat


def getTransformMatrix(pb):
    dmat,bmat,rmat = getTransformMatrices(pb)
    tmat = Mult2(dmat.inverted(), bmat)
    return tmat.to_3x3()


def getBoneMatrix(tfm, pb, test=False):
    dmat,bmat,rmat = getTransformMatrices(pb)
    wmat = Mult4(dmat, tfm.getRotMat(pb), tfm.getScaleMat(), dmat.inverted())
    wmat = Mult4(rmat.inverted(), tfm.getTransMat(), rmat, wmat)
    mat = Mult3(bmat.inverted(), wmat, bmat)

    if test:
        print("GGT", pb.name)
        print("D", dmat)
        print("B", bmat)
        print("R", tfm.rotmat)
        print("RR", rmat)
        print("W", wmat)
        print("M", mat)
    return mat


def setBoneTransform(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    pb.matrix_basis = mat


def setBoneTwist(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    _,quat,_ = mat.decompose()
    euler = pb.matrix_basis.to_3x3().to_euler('YZX')
    euler.y += quat.to_euler('YZX').y
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = euler.to_quaternion()
    else:
        pb.rotation_euler = euler


def isUnitMatrix(mat):
    diff = mat - Matrix()
    maxelt = max([abs(diff[i][j]) for i in range(3) for j in range(4)])
    return (maxelt < 0.01*LS.scale)  # Ignore shifts < 0.1 mm


