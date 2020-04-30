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
from mathutils import *
from collections import OrderedDict
from .asset import Accessor, Asset
from .channels import Channels
from .formula import Formula
from .settings import theSettings
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


class Instance(Accessor):

    def __init__(self, fileref, node, struct):
        from .asset import normalizeRef

        Accessor.__init__(self, fileref)
        self.node = node
        self.index = len(node.instances)
        self.figure = None
        self.id = normalizeRef(struct["id"])
        self.id = self.getSelfId()
        node.instances[self.id] = self
        self.offsets = self.node.defaultAttributes()
        self.namedOffsets = {}
        self.geometries = node.geometries
        node.geometries = []
        self.rotDaz = node.rotDaz
        self.hasBoneParent = False
        if "parent" in struct.keys() and node.parent is not None:
            self.parent = node.parent.getInstance(node.caller, struct["parent"])
            if self.parent == self:
                print("Self-parent", self)
                self.parent = None
            if self.parent:
                self.parent.children[self.id] = self
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
        self.shell = {}
        self.dupli = False
        self.collection = None
        self.hidden = None
        self.isGroupNode = False
        self.isInstance = False
        self.node2 = None
        self.strand_hair = node.strand_hair
        node.strand_hair = None
        self.name = node.getLabel(self)
        self.modifiers = []
        self.materials = node.materials
        node.materials = {}
        self.material_group_vis = {}
        self.attributes = copyElements(node.attributes)
        self.previewAttrs = copyElements(node.previewAttrs)
        self.updateMatrices()
        node.clearTransforms()


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        return "<Instance %s %d N: %s P: %s R: %s, E: %d>" % (self.id, self.index, self.node.name, pname, self.rna, len(self.extra))


    def getSelfId(self):
        return self.id


    def clearTransforms(self):
        self.deltaMatrix = Matrix()
        default = self.node.defaultAttributes()
        for key in ["translation", "rotation", "scale", "general_scale"]:
            self.attributes[key] = default[key]


    def addToOffset(self, name, key, value):
        channel,idx = getChannelIndex(key)
        if name not in self.namedOffsets.keys():
            self.namedOffsets[name] = self.node.defaultAttributes()
        if idx >= 0:
            self.offsets[channel][idx] += value
            self.namedOffsets[name][channel][idx] = value
        else:
            self.offsets[channel] += value
            self.namedOffsets[name][channel] = value


    def getCharacterScale(self):
        return self.offsets["general_scale"]


    def preprocess(self, context, root):
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
                    self.material_group_vis[channel["label"]] = getCurrentValue(channel)
                elif (words[0] == "facet" and words[1] == "group" and words[-1] == "vis"):
                    pass

        if self.parent:
            self.collection = self.parent.collection
        else:
            self.collection = root
            
        for extra in self.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/shell":
                self.shell = extra
            elif extra["type"] == "studio/node/group_node":
                self.isGroupNode = True
                if bpy.app.version < (2,80,0):
                    group = bpy.data.groups.new(self.name)
                    self.collection = group
                else:
                    coll = bpy.data.collections.new(name=self.name)
                    if self.parent:
                        self.parent.collection.children.link(coll)
                    else:
                        root.children.link(coll)
                    self.collection = coll                        
            elif extra["type"] == "studio/node/instance":
                self.isInstance = True

        for geo in self.geometries:
            geo.preprocess(context, self)


    def buildExtra(self, context):
        if self.strand_hair:
            print("Strand-based hair is not implemented.")
            #return
            import base64
            bytes = base64.b64decode(self.strand_hair, validate=True)
            with open(os.path.expanduser("~/foo.obj"), "wb") as fp:
                fp.write(bytes)
            return

        elif self.node2 and self.rna and self.rna.type == 'EMPTY':
            if self.node2.rna is None:
                print("WHUT")
                return
            ob = self.node2.rna
            if self.node2.hidden:
                hidden = self.node2.hidden
            else:
                if bpy.app.version < (2,80,0):
                    putOnHiddenLayer(ob)
                    hidden = bpy.data.groups.new(name=self.name)
                else:
                    hidden = bpy.data.collections.new(name=self.name)
                    self.collection.children.link(hidden)
                    layer = findLayerCollection(context.view_layer.layer_collection, hidden)
                    layer.exclude = True
                hidden.objects.link(ob)                    
                self.node2.hidden = hidden
                empty = bpy.data.objects.new(ob.name + "_Dupli", None)
                self.collection.objects.link(empty)
                empty.parent = ob.parent
                setSelected(empty, True)
                self.node2.dupli = empty
                self.duplicate(empty, hidden)
            self.duplicate(self.rna, hidden)

        elif self.isGroupNode:
            pass
            
        elif self.isInstance:            
            print("\nIINST", self)
            #self.duplicate(self.rna, self.parent.collection)
            

    def duplicate(self, empty, group):
        if bpy.app.version < (2,80,0):
            empty.dupli_type = 'GROUP'
            empty.dupli_group = group
        else:
            empty.instance_type = 'COLLECTION'
            empty.instance_collection = group


    def pose(self, context):
        pass


    def finalize(self, context):
        from mathutils import Matrix
        if self.dupli:
            ob = self.rna
            wmat = ob.matrix_basis.copy()
            ob.matrix_basis = Matrix()
            self.dupli.matrix_basis = wmat
            self.collection.objects.unlink(ob)


    def formulate(self, key, value):
        pass


    def updateMatrices(self):
        # Dont do zup here
        center = d2b00(self.attributes["center_point"])
        rotmat = Matrix()
        self.restMatrix = Mult2(Matrix.Translation(center), rotmat)
        self.updateDeltaMatrix(self.attributes["translation"], self.attributes["rotation"], self.attributes["scale"])


    def updateDeltaMatrix(self, wspos, wsrot, wsscale):
        trans = d2b00(wspos)
        rot = d2b00u(wsrot)*D
        scale = d2b00s(wsscale) * self.attributes["general_scale"]
        rotmat = Euler(rot, self.rotDaz).to_matrix().to_4x4()
        scalemat = Matrix()
        for i in range(3):
            scalemat[i][i] = scale[i]
        self.deltaMatrix = Mult3(Matrix.Translation(trans), rotmat, scalemat)


    def parentObject(self, context):
        from .figure import FigureInstance
        from .bone import BoneInstance
        from .geometry import GeoNode

        ob = self.rna
        if ob is None:
            return
        activateObject(context, ob)
        useTransform = not (theSettings.fitFile and ob.type == 'MESH')

        if self.parent is None:
            ob.parent = None
            if useTransform:
                self.transformObject()

        elif self.parent.rna == ob:
            print("Warning: Trying to parent %s to itself" % ob)
            ob.parent = None

        elif isinstance(self.parent, FigureInstance):
            for geo in self.geometries:
                for pgeo in self.parent.geometries:
                    geo.setHideInfo(pgeo)
            setParent(context, ob, self.parent.rna)
            if useTransform:
                self.transformObject()

        elif isinstance(self.parent, BoneInstance):
            self.hasBoneParent = True
            if self.parent.figure is None:
                print("No figure found:", self.parent)
                return
            rig = self.parent.figure.rna
            bname = self.parent.node.name
            if bname in rig.pose.bones.keys():
                setParent(context, ob, rig, bname)
                if useTransform:
                    pb = rig.pose.bones[bname]
                    self.transformObject(pb)

        elif isinstance(self.parent, Instance):
            setParent(context, ob, self.parent.rna)
            if useTransform:
                self.transformObject()

        else:
            raise RuntimeError("Unknown parent %s %s" % (self, self.parent))


    def getTransformMatrix(self, pb):
        from .settings import theSettings
        if theSettings.zup:
            wmat = Matrix.Rotation(math.pi/2, 4, 'X')
        else:
            wmat = Matrix()

        if pb:
            rmat = self.restMatrix
            mat = Mult2(rmat, self.deltaMatrix)
            mat = Mult3(wmat, mat, wmat.inverted())
            mat = Mult2(pb.bone.matrix_local.inverted(), mat)
            offset = Vector((0,pb.bone.length,0))
        else:
            rmat = self.restMatrix
            if self.parent:
                rmat = Mult2(rmat, self.parent.restMatrix.inverted())
            mat = Mult2(rmat, self.deltaMatrix)
            mat = Mult3(wmat, mat, wmat.inverted())
            offset = Vector((0,0,0))
        return mat, offset


    def transformObject(self, pb=None):
        mat,offset = self.getTransformMatrix(pb)
        trans,quat,scale = mat.decompose()
        ob = self.rna
        ob.location = trans - offset
        ob.rotation_euler = quat.to_euler(ob.rotation_mode)
        ob.scale = scale
        self.node.postTransform()


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
        self.geometries = []
        self.materials = {}
        self.strand_hair = None
        self.inherits_scale = False
        self.rotDaz = 'XYZ'
        self.attributes = self.defaultAttributes()
        self.origAttrs = self.defaultAttributes()
        self.previewAttrs = {
            "center_point": Vector((0,0,0)),
            "end_point": Vector((0,0,0)),
        }
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
        self.deltaMatrix = Matrix()
        default = self.defaultAttributes()
        for key in ["translation", "rotation", "scale", "general_scale"]:
            self.attributes[key] = default[key]
        self.previewAttrs = {
            "center_point": Vector((0,0,0)),
            "end_point": Vector((0,0,0)),
        }


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
                self.inherits_scale = data
            elif key == "rotation_order":
                self.rotDaz = data
            elif key in self.attributes.keys():
                self.setAttribute(key, data)

        for key in self.attributes.keys():
            self.origAttrs[key] = self.attributes[key]
        return self


    def setExtra(self, extra):
        if extra["type"] == "studio/node/strand_hair":
            self.strand_hair = extra["data"]
            print("STRAND")
    

    Indices = { "x": 0, "y": 1, "z": 2 }

    def setAttribute(self, channel, data):
        from .channels import getCurrentValue
        #self.attributes[channel] = self.defaultAttributes()[channel]
        if isinstance(data, list):
            for comp in data:
                idx = self.Indices[comp["id"]]
                value = getCurrentValue(comp)
                if value is not None:
                    self.attributes[channel][idx] = value
        else:
            self.attributes[channel] = getCurrentValue(data)


    def preview(self, struct):
        if "preview" in struct.keys():
            pstruct = struct["preview"]
            for key in ["center_point", "end_point"]:
                if key in pstruct.keys():
                    self.previewAttrs[key] = Vector(pstruct[key])


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
            if theSettings.fitFile:
                geocenter = Vector((0,0,0))
            else:
                geocenter = center
            for geonode in inst.geometries:
                geonode.buildObject(context, inst, geocenter)
                inst.rna = geonode.rna
        else:
            self.buildObject(context, inst, center)
        ob = inst.rna
        if isinstance(ob, bpy.types.Object):
            ob.DazOrientation = inst.attributes["orientation"]
        if inst.extra:
            inst.buildExtra(context)


    def postbuild(self, context, inst):
        from .geometry import GeoNode
        inst.parentObject(context)
        for geo in inst.geometries:
            geo.postbuild(context)


    def buildObject(self, context, inst, center):
        from .geometry import Geometry
        from .asset import normalizePath

        cscale = inst.getCharacterScale()
        scn = context.scene
        if isinstance(self.data, Asset):
            if self.data.shell and scn.DazMergeShells:
                return
            ob = self.data.buildData(context, self, inst, cscale, center)
            if not isinstance(ob, bpy.types.Object):
                ob = bpy.data.objects.new(inst.name, self.data.rna)
        else:
            ob = bpy.data.objects.new(inst.name, self.data)
        
        if (self.type == "subdivision_surface" and
            isinstance(self.data, Geometry) and 
            (self.data.SubDIALevel > 0 or self.data.SubDRenderLevel > 0)):
            mod = ob.modifiers.new(name='SUBSURF', type='SUBSURF')
            mod.render_levels = self.data.SubDIALevel + self.data.SubDRenderLevel
            mod.levels = self.data.SubDIALevel

        self.rna = inst.rna = ob
        ob.rotation_mode = BlenderRotMode[self.rotDaz]
        ob.DazRotMode = self.rotDaz
        inst.collection.objects.link(ob)
        if bpy.app.version < (2,80,0):
            scn.objects.link(ob)
        activateObject(context, ob)
        setSelected(ob, True)
        ob.DazId = self.id
        ob.DazUrl = normalizePath(self.url)
        ob.DazScale = theSettings.scale
        ob.DazCharacterScale = cscale
        if not (theSettings.fitFile and ob.type == 'MESH'):
            ob.location = -center


    def guessColor(self, scn, flag, inst):
        from .guess import guessColor
        for node in inst.geometries:
            if node.rna:
                guessColor(node.rna, scn, flag, theSettings.skinColor, theSettings.clothesColor, False)

BlenderRotMode = {
    'XYZ' : 'XZY',
    'XZY' : 'XYZ',
    'YXZ' : 'ZXY',
    'YZX' : 'ZYX',
    'ZXY' : 'YXZ',
    'ZYX' : 'YZX',
    'QUATERNION' : 'XZY'
}

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
        mat = ob.matrix_world.copy()
        ob.parent = rig
        if bname:
            ob.parent_bone = bname
            ob.parent_type = 'BONE'
        else:
            ob.parent_type = 'OBJECT'
        ob.matrix_world = mat


def clearParent(ob):
    mat = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = mat


def getTransformMatrices(pb):
    dmat = Euler(Vector(pb.bone.DazOrientation)*D, 'XYZ').to_matrix().to_4x4()
    dmat.col[3][0:3] = d2b00(pb.bone.DazHead)

    parbone = pb.bone.parent
    if parbone and parbone.DazAngle != 0:
        rmat = Matrix.Rotation(parbone.DazAngle, 4, parbone.DazNormal)
    else:
        rmat = Matrix()

    if theSettings.zup:
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

    lock = pb.lock_rotation
    if lock[0] or lock[1] or lock[2]:
        _,quat,scale = mat.decompose()
        for n in range(3):
            if pb.lock_rotation[n]:
                quat[n+1] = 0
        quat.normalize()
        rotmat = quat.to_matrix()
        for n in range(3):
            mat[n][0:3] = rotmat[n]

    loc,quat,scale = mat.decompose()
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = quat
    else:
        pb.rotation_euler = quat.to_euler(pb.rotation_mode)
    for n in range(3):
        if not pb.lock_location[n]:
            pb.location[n] = loc[n]


def setBoneTwist(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    _,quat,_ = mat.decompose()
    euler = pb.matrix_basis.to_3x3().to_euler('YZX')
    euler.y += quat.to_euler('YZX').y
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = euler.to_quaternion()
    else:
        pb.rotation_euler = euler
