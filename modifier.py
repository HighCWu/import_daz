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
##

import bpy
import collections
import os

from .asset import Asset
from .channels import Channels
from .utils import *
from .error import *
from .formula import Formula

#-------------------------------------------------------------
#   External access
#-------------------------------------------------------------

def parseModifierAsset(asset, struct):
    if "skin" in struct.keys():
        return asset.parseTypedAsset(struct, SkinBinding)
    elif "legacy_skin" in struct.keys():
        return asset.parseTypedAsset(struct, LegacySkinBinding)
    elif "morph" in struct.keys():
        return asset.parseTypedAsset(struct, Morph)
    elif "formulas" in struct.keys():
        return asset.parseTypedAsset(struct, FormulaAsset)
    elif "dform" in struct.keys():
        return asset.parseTypedAsset(struct, DForm)
    elif "extra" in struct.keys():
        return asset.parseTypedAsset(struct, ExtraAsset)
    elif "channel" in struct.keys():
        return parseChannelAsset(asset, struct)
    else:
        #print("WARNING: Modifier asset %s not implemented" % asset.fileref)
        #asset = Modifier(asset.fileref)
        raise NotImplementedError("Modifier asset not implemented in file %s:\n  %s" %
            (asset.fileref, list(struct.keys())))


def parseChannelAsset(asset, struct):
    channel = struct["channel"]
    if channel["type"] == "alias":
        return asset.parseTypedAsset(struct, Alias)
    else:
        return asset.parseTypedAsset(struct, ChannelAsset)


def parseMorph(asset, struct):
    if "modifier_library" in struct.keys():
        for mstruct in struct["modifier_library"]:
            if "morph" in mstruct.keys():
                return asset.parseTypedAsset(mstruct, Morph)
            elif "formulas" in mstruct.keys():
                return asset.parseTypedAsset(mstruct, FormulaAsset)
            elif "channel" in mstruct.keys():
                channel = parseChannelAsset(asset, mstruct)
                return channel

#-------------------------------------------------------------
#   Modifier Assets
#-------------------------------------------------------------

class Modifier(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.classType = Modifier
        self.groups = []


    def parse(self, struct):
        Asset.parse(self, struct)
        if "groups" in struct.keys():
            self.groups = struct["groups"]


    def update(self, struct):
        Asset.update(self, struct)
        if "groups" in struct.keys():
            self.groups = struct["groups"]


    def __repr__(self):
        return ("<Modifier %s %s>" % (self.id, self.type))


    def preprocess(self, inst):
        pass


    def postbuild(self, context, inst):
        pass


class DForm(Modifier):
    def __repr__(self):
        return ("<Dform %s %s>" % (self.id, self.type))

#-------------------------------------------------------------
#   Extra
#-------------------------------------------------------------

class ExtraAsset(Modifier, Channels):
    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        Channels.__init__(self)
        self.extras = {}
        self.type = None


    def __repr__(self):
        return ("<Extra %s %s p: %s>" % (self.id, list(self.extras.keys()), self.parent))


    def parse(self, struct):
        Modifier.parse(self, struct)
        extras = struct["extra"]
        if not isinstance(extras, list):
            extras = [extras]
        for extra in extras:
            if "type" in extra.keys():
                etype = extra["type"]
                self.extras[etype] = extra


    def update(self, struct):
        Modifier.update(self, struct)
        if "extra" not in struct.keys():
            return
        extras = struct["extra"]
        if not isinstance(extras, list):
            extras = [extras]
        for extra in extras:
            if "type" in extra.keys():
                etype = extra["type"]
                if etype in self.extras.keys():
                    for key,value in extra.items():
                        self.extras[etype][key] = value
                else:
                    self.extras[etype] = extra


    def preprocess(self, inst):
        geonode, pgeonode = self.getGeoNodes(inst)
        if geonode is None:
            return
        if "studio_modifier_channels" in self.extras.keys():
            geonode.modifiers[self.name] = self
            modchannels = self.extras["studio_modifier_channels"]
            for cstruct in modchannels["channels"]:
                channel = cstruct["channel"]
                self.setChannel(channel)
        if "studio/modifier/push" in self.extras.keys():
            geonode.push = self.getValue(["Value"], 0)


    def getGeoNodes(self, inst):
        if inst is None:
            reportError("Cannot build %s" % self, trigger=(3,4))
            return None,None
        pinst = inst.parent
        geonode = self.getGeoNode(inst)
        pgeonode = self.getGeoNode(pinst)
        if geonode is None and GS.verbosity > 2:
            print("No geo", self)
        return geonode, pgeonode


    def build(self, context, inst):
        geonode, pgeonode = self.getGeoNodes(inst)
        if geonode is None:
            return
        for etype,extra in self.extras.items():
            if etype == "studio/modifier/dynamic_generate_hair":
                geonode.addHairSim(self, extra, pgeonode)
                geonode.pgeonode = pgeonode
            elif etype == "studio/modifier/dynamic_simulation":
                geonode.addDForce(self, extra, pgeonode)
            elif etype == "studio/modifier/dynamic_hair_follow":
                pass
            elif etype == "studio/modifier/line_tessellation":
                pass
            elif etype == "studio/simulation_settings/dynamic_simulation":
                pass


    def getGeoNode(self, inst):
        from .node import Instance
        from .geometry import GeoNode
        if isinstance(inst, Instance):
            if inst.geometries:
                return inst.geometries[0]
            else:
                return None
        elif isinstance(inst, GeoNode):
            return inst
        else:
            return None

#-------------------------------------------------------------
#   ChannelAsset
#-------------------------------------------------------------

class ChannelAsset(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.classType = ChannelAsset
        self.type = "channel"
        self.value = 0
        self.min = None
        self.max = None

    def __repr__(self):
        return ("<Channel %s %s>" % (self.id, self.type))

    def parse(self, struct):
        Modifier.parse(self, struct)
        if not LS.useMorph:
            return
        if "channel" in struct.keys():
            for key,value in struct["channel"].items():
                if key == "value":
                    self.value = value
                elif key == "min":
                    self.min = value
                elif key == "max":
                    self.max = value


    def update(self, struct):
        Modifier.update(self, struct)
        if ("channel" in struct.keys() and
            "current_value" in struct["channel"].keys()):
            self.value = struct["channel"]["current_value"]


    def setupQuick(self, morphset, rig):
        self.morphset = morphset
        self.rig = rig
        self.prop = self.getName()


    def setupProp(self, morphset, rig):
        self.setupQuick(morphset, rig)
        prop = unquote(self.name)
        if prop in rig.DazPropNames.keys():
            pg = rig.DazPropNames[prop]
        else:
            pg = rig.DazPropNames.add()
        pg.name = prop
        pg.text = self.prop
        addToMorphSet(rig, morphset, self.prop, self)


    def initProp(self, ob, prop):
        from .driver import setFloatProp
        if prop is None:
            prop = self.prop
        if GS.useDazPropLimits:
            value = self.value
            min = self.min
            max = self.max
        else:
            value = 0.0
            min = max = None
        setFloatProp(ob, prop, value, min=min, max=max)
        return prop,value


    def clearProp(self, morphset, rig):
        self.setupProp(morphset, rig, False)
        prop,_value = self.initProp(rig, None)
        return prop


def stripPrefix(prop):
    lprop = prop.lower()
    for prefix in [
        "ectrlv", "ectrl", "pctrl", "ctrl",
        "phm", "ephm", "pbm", "ppbm", "vsm",
        "pjcm", "ejcm", "jcm", "mcm",
        "dzu", "dze", "dzv", "dzb",
        "facs_jnt_", "facs_ctrl_", "facs_",
        ]:
        n = len(prefix)
        if lprop[0:n] == prefix:
            return prop[n:]
    return prop


def getCanonicalKey(key):
    key = stripPrefix(key)
    lkey = key.lower()
    if lkey[-5:] == "_div2":
        key = key[:-5]
        lkey = lkey[:-5]
    if lkey[-3:] == "_hd":
        key = key[:-3]
        lkey = lkey[:-3]
    if lkey[-2:] == "hd":
        key = key[:-2]
        lkey = lkey[:-2]
    if lkey[-4:-1] == "_hd":
        key = key[:-4] + key[-1]
        lkey = lkey[:-4] + lkey[-1]
    if lkey[-3:-1] == "hd":
        key = key[:-3] + key[-1]
        lkey = lkey[:-3] + lkey[-1]
    return key


def addToMorphSet(ob, morphset, prop, asset=None):
    pg = getattr(ob, "Daz"+morphset)
    if prop in pg.keys():
        item = pg[prop]
    else:
        item = pg.add()
    item.name = prop
    if asset is None:
        item.text = getCanonicalKey(prop)
    elif asset.visible:
        item.text = asset.label
    else:
        item.text = "[%s]" % getCanonicalKey(prop)
    return prop


class Alias(ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        self.alias = None
        self.parent = None
        self.type = "alias"
        self.value = 0.0

    def __repr__(self):
        return ("<Alias %s\n  %s>" % (self.id, self.alias))

    def parse(self, struct):
        ChannelAsset.parse(self, struct)
        channel = struct["channel"]
        #self.parent = self.getAsset(struct["parent"])
        self.alias = self.getAsset(channel["target_channel"])

    def update(self, struct):
        if self.alias:
            self.alias.update(struct)
            if hasattr(self.alias, "value"):
                self.value = self.alias.value

    def build(self, context, inst):
        if self.alias:
            self.alias.build(context)

#-------------------------------------------------------------
#   Skin Binding
#-------------------------------------------------------------

class SkinBinding(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.classType = SkinBinding
        self.parent = None
        self.skin = None
        self.type = "skin_binding"

    def __repr__(self):
        return ("<SkinBinding %s>" % (self.id))


    def parse(self, struct):
        from .geometry import Geometry
        from .figure import Figure
        Modifier.parse(self, struct)
        self.skin = struct["skin"]
        self.parent = self.getAsset(struct["parent"])
        if not (isinstance(self.parent, Geometry) or
                isinstance(self.parent, Figure)):
            msg = "Parent of %s\nshould be a geometry or a figure but is\n%s" % (self, self.parent)
            reportError(msg, trigger=(2,3))


    def parseSource(self, url):
        from .asset import theAssets
        asset = self.getAsset(url)
        if asset:
            if (self.parent is None or
                self.parent.type != asset.type):
                msg = ("SkinBinding source bug:\n" +
                       "URL: %s\n" % url +
                       "Skin: %s\n" % self +
                       "Asset: %s\n" % asset +
                       "Parent: %s\n" % self.parent)
                reportError(msg, trigger=(2,3))
            if asset != self.parent:
                self.parent.source = asset
                asset.sourcing = self.parent
            theAssets[url] = self.parent


    def build(self, context, inst):
        ob,rig,geonode = self.getGeoRig(context, inst, self.skin["geometry"])
        if ob is None or rig is None or ob.type != 'MESH':
            return
        makeArmatureModifier(self.name, context, ob, rig)
        self.addVertexGroups(ob, geonode, rig)
        hdob = geonode.hdobject
        if (hdob and
            hdob != ob and
            hdob.DazMultires and
            GS.useMultires):
            hdob.parent = ob.parent
            makeArmatureModifier(self.name, context, hdob, rig)
            if len(hdob.data.vertices) == len(ob.data.vertices):
                copyVertexGroups(ob, hdob)
            else:
                LS.hdweights.append(hdob.name)


    def getGeoRig(self, context, inst, geoname):
        from .geometry import GeoNode
        from .figure import FigureInstance
        if isinstance(inst, GeoNode):
            ob = inst.getRna(context)
            if ob:
                rig = ob.parent
            else:
                rig = None
            return ob, rig, inst
        else:
            msg = ("Expected geonode but got:\n  %s" % inst)
            reportError(msg, trigger=(2,3))
            return None,None,None


    def addVertexGroups(self, ob, geonode, rig):
        bones = geonode.figure.bones
        for joint in self.skin["joints"]:
            bname = joint["id"]
            if bname in bones.keys():
                vgname = bones[bname]
            else:
                vgname = bname

            weights = None
            if "node_weights" in joint.keys():
                weights = joint["node_weights"]
            elif "local_weights" in joint.keys():
                if bname in rig.data.bones.keys():
                    calc_weights = self.calcLocalWeights(bname, joint, rig)
                    weights = {"values": calc_weights}
                else:
                    print("Local weights missing bone:", bname)
                    for comp in ["x", "y", "z"]:
                        if comp in joint["local_weights"].keys():
                            weights = joint["local_weights"][comp]
                            break
            elif "scale_weights" in joint.keys():
                weights = joint["scale_weights"]
            else:
                reportError("No weights for %s in %s" % (bname, ob.name), trigger=(2,5))
                continue

            buildVertexGroup(ob, vgname, weights["values"])


    def calcLocalWeights(self, bname, joint, rig):
        local_weights = joint["local_weights"]
        bone = rig.data.bones[bname]
        head = bone.head_local
        tail = bone.tail_local
        # find longitudinal axis of the bone and take the other two into consideration
        consider = []
        x_delta = abs(head[0] - tail[0])
        y_delta = abs(head[1] - tail[1])
        z_delta = abs(head[2] - tail[2])
        max_delta = max(x_delta, y_delta, z_delta)
        if x_delta < max_delta:
            consider.append("x")
        if y_delta < max_delta:
            consider.append("z")
        if z_delta < max_delta:
            consider.append("y")

        # create deques sorted in descending order
        weights = [collections.deque(local_weights[letter]["values"]) for letter in consider if
                   letter in local_weights]
        for w in weights:
            w.reverse()
        target = []
        calc_weights = []
        if len(weights) == 1:
            calc_weights = weights[0]
        elif len(weights) > 1:
            self.mergeWeights(weights[0], weights[1], target)
            calc_weights = target
        if len(weights) > 2:
            # this happens mostly with zero length bones
            calc_weights = []
            self.mergeWeights(target, weights[2], calc_weights)
        return calc_weights


    def mergeWeights(self, first, second, target):
        # merge the two local_weight groups and calculate arithmetic mean for vertices that are present in both groups
        while len(first) > 0 and len(second) > 0:
            a = first.pop()
            b = second.pop()
            if a[0] == b[0]:
                target.append([a[0], (a[1] + b[1]) / 2.0])
            elif a[0] < b[0]:
                target.append(a)
                second.append(b)
            else:
                target.append(b)
                first.append(a)
        while len(first) > 0:
            a = first.pop()
            target.append(a)
        while len(second) > 0:
            b = second.pop()
            target.append(b)


def buildVertexGroup(ob, vgname, weights, default=None):
    if weights:
        if vgname in ob.vertex_groups.keys():
            print("Duplicate vertex group:\n  %s %s" % (ob.name, vgname))
            return ob.vertex_groups[vgname]
        else:
            vgrp = ob.vertex_groups.new(name=vgname)
        if default is None:
            for vn,w in weights:
                vgrp.add([vn], w, 'REPLACE')
        else:
            for vn in weights:
                vgrp.add([vn], default, 'REPLACE')
        return vgrp
    return None


def makeArmatureModifier(name, context, ob, rig):
    mod = ob.modifiers.new(name, 'ARMATURE')
    mod.object = rig
    mod.use_deform_preserve_volume = True
    activateObject(context, ob)
    for n in range(len(ob.modifiers)-1):
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    ob.location = (0,0,0)
    ob.rotation_euler = (0,0,0)
    ob.scale = (1,1,1)
    ob.lock_location = (True,True,True)
    ob.lock_rotation = (True,True,True)
    ob.lock_scale = (True,True,True)


def copyVertexGroups(ob, hdob):
    hdvgrps = {}
    for vgrp in ob.vertex_groups:
        hdvgrp = hdob.vertex_groups.new(name=vgrp.name)
        hdvgrps[vgrp.index] = hdvgrp
    for v in ob.data.vertices:
        vn = v.index
        for g in v.groups:
            hdvgrps[g.group].add([vn], g.weight, 'REPLACE')


class LegacySkinBinding(SkinBinding):

    def __repr__(self):
        return ("<LegacySkinBinding %s>" % (self.id))

    def parse(self, struct):
        struct["skin"] = struct["legacy_skin"]
        SkinBinding.parse(self, struct)

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class FormulaAsset(Formula, ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        Formula.__init__(self)
        self.group = ""

    def __repr__(self):
        return ("<Formula %s %f>" % (self.id, self.value))


    def parse(self, struct):
        ChannelAsset.parse(self, struct)
        if not LS.useMorph:
            return
        if "group" in struct.keys():
            words = struct["group"].split("/")
            if (len(words) > 2 and
                words[0] == "" and
                words[1] == "Pose Controls"):
                self.group = words[2]
        Formula.parse(self, struct)


    def build(self, context, inst):
        if not LS.useMorph:
            return
        Formula.build(self, context, inst)


    def postbuild(self, context, inst):
        if not LS.useMorph:
            return
        Formula.postbuild(self, context, inst)

#-------------------------------------------------------------
#   Morph
#-------------------------------------------------------------

class Morph(FormulaAsset):

    def __init__(self, fileref):
        FormulaAsset.__init__(self, fileref)
        self.classType = Morph
        self.type = "morph"
        self.vertex_count = 0
        self.deltas = []
        self.hd_url = None


    def __repr__(self):
        return ("<Morph %s %f %d %d %s>" % (self.name, self.value, self.vertex_count, len(self.deltas), self.rna))


    def parse(self, struct):
        FormulaAsset.parse(self, struct)
        if not LS.useMorph:
            return
        self.parent = struct["parent"]
        morph = struct["morph"]
        self.deltas = morph["deltas"]["values"]
        self.vertex_count = morph["vertex_count"]
        if "hd_url" in morph.keys():
            self.hd_url = morph["hd_url"]


    def parseSource(self, url):
        #print("Skip source", self)
        pass


    def update(self, struct):
        from .geometry import GeoNode, Geometry
        from .figure import Figure, FigureInstance
        FormulaAsset.update(self, struct)
        if not LS.useMorph:
            return

        parent = self.getAsset(self.parent)
        if "parent" not in struct.keys():
            return

        if isinstance(parent, Geometry):
            ref = instRef(struct["parent"])
            if ref in parent.nodes:
                geonode = parent.nodes[ref]
            else:
                reportError("Missing geonode %s in\n %s" %(ref, parent), trigger=(2,4))
                return
        elif isinstance(parent, GeoNode):
            geonode = parent
        elif isinstance(parent, Figure) and parent.instances:
            ref = list(parent.instances.keys())[0]
            inst = parent.getInstance(ref, self.caller)
            geonode = inst.geometries[0]
        elif isinstance(parent, FigureInstance):
            geonode = parent.geometries[0]
        else:
            msg = ("Strange morph parent.\n  %s\n  %s" % (self, parent))
            return reportError(msg)
        geonode.morphsValues[self.name] = self.value


    def build(self, context, inst, value=-1):
        from .geometry import GeoNode, Geometry
        from .figure import FigureInstance
        from .bone import BoneInstance

        if not LS.useMorph:
            return self
        if len(self.deltas) == 0:
            print("Morph without deltas: %s" % self.name)
            return self
        Formula.build(self, context, inst)
        Modifier.build(self, context)

        if isinstance(inst, FigureInstance):
            geonodes = inst.geometries
        elif isinstance(inst, GeoNode):
            geonodes = [inst]
        elif isinstance(inst, BoneInstance):
            geonodes = inst.figure.geometries
        else:
            asset = self.getAsset(self.parent)
            print("BMO", inst)
            print("  ", asset)
            inst = None
            if asset:
                geonodes = list(asset.nodes.values())
                if len(geonodes) > 0:
                    inst = geonodes[0]

        if inst is None:
            msg = ("Morph not found:\n  %s\n  %s\n  %s" % (self.id, self.parent, asset))
            reportError(msg, trigger=(2,3))
            return None

        for geonode in geonodes:
            ob = geonode.rna
            if value >= 0:
                self.value = value
                if self not in geonode.modifiers:
                    geonode.modifiers.append(self)
                geonode.morphsValues[self.name] = value
            elif self.name in geonode.morphsValues.keys():
                self.value = geonode.morphsValues[self.name]
            else:
                if GS.verbosity > 3:
                    print("MMMO", self.name)
                    print("  ", geonode)
                    print("  ", geonode.morphsValues.keys())
                self.value = 0.0

            if ob is None:
                continue
            elif LS.applyMorphs:
                self.addMorphToVerts(ob.data)
            elif self.value > 0.0:
                self.buildMorph(ob)
        return self


    def addMorphToVerts(self, me):
        if self.value == 0.0:
            return
        scale = self.value * LS.scale
        for delta in self.deltas:
            vn = delta[0]
            me.vertices[vn].co += scale * d2bu(delta[1:])


    def buildMorph(self, ob,
                   useBuild=True,
                   useSoftLimits=False,
                   morphset=None,
                   strength=1):
        #sname = unquote(self.name)
        sname = self.getName()
        rig = ob.parent
        if rig:
            addToMorphSet(rig, morphset, sname, self)
        skey = addShapekey(ob, sname)
        if useSoftLimits:
            skey.slider_min = self.min if self.min is not None and GS.useDazPropLimits else GS.propMin
            skey.slider_max = self.max if self.max is not None and GS.useDazPropLimits else GS.propMax
        skey.value = self.value
        self.rna = (skey, ob, sname)
        if useBuild:
            self.buildShapeKey(ob, skey, strength)


    def buildShapeKey(self, ob, skey, strength=1):
        if strength != 1:
            scale = LS.scale
            LS.scale *= strength
        for v in ob.data.vertices:
            skey.data[v.index].co = v.co
        if GS.zup:
            for delta in self.deltas:
                vn = delta[0]
                skey.data[vn].co += d2b90(delta[1:])
        else:
            for delta in self.deltas:
                vn = delta[0]
                skey.data[vn].co += d2b00(delta[1:])
        if strength != 1:
            LS.scale = scale


    def rebuild(self, geonode, value):
        ob = geonode.rna
        self.value = value
        if (ob.data.shape_keys and
            self.name in ob.data.shape_keys.key_blocks.keys()):
            skey = ob.data.shape_keys.key_blocks[self.name]
            skey.value = value
            self.buildShapeKey(ob, skey)
        else:
            if LS.applyMorphs:
                self.addMorphToVerts(ob.data)
            elif ob:
                if self.value > 0.0:
                    self.buildMorph(ob)
            #raise DazError("No such shapekey %s in %s" % (skey, ob))


def addShapekey(ob, sname):
    if not ob.data.shape_keys:
        basic = ob.shape_key_add(name="Basic")
    else:
        basic = ob.data.shape_keys.key_blocks[0]
    if sname in ob.data.shape_keys.key_blocks.keys():
        skey = ob.data.shape_keys.key_blocks[sname]
        ob.shape_key_remove(skey)
    return ob.shape_key_add(name=sname)

