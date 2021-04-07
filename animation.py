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
import os
from collections import OrderedDict
from mathutils import *
from .error import *
from .utils import *
from .transform import Transform
from .globvars import theDazExtensions
from .fileutils import MultiFile, SingleFile, JsonFile, JsonExportFile

#-------------------------------------------------------------
#   Convert between frames and vectors
#-------------------------------------------------------------

def framesToVectors(frames):
    vectors = {}
    for idx in frames.keys():
        for t,y in frames[idx]:
            if t not in vectors.keys():
                vectors[t] = Vector((0,0,0))
            vectors[t][idx] = y
    return vectors


def vectorsToFrames(vectors):
    frames = {}
    for idx in range(3):
        frames[idx] = [[t,vectors[t][idx]] for t in vectors.keys()]
    return frames

#-------------------------------------------------------------
#   Combine bend and twist. Unused
#-------------------------------------------------------------

def combineBendTwistAnimations(anim, twists):
    for (bend,twist) in twists:
        if twist in anim.keys():
            if bend in anim.keys():
                addTwistFrames(anim[bend], anim[twist])
            else:
                anim[bend] = {"rotation" : halfRotation(anim[twist]["rotation"])}


def addTwistFrames(bframes, tframes):
    if "rotation" not in bframes:
        if "rotation" not in tframes:
            return bframes
        else:
            bframes["rotation"] = halfRotation(tframes["rotation"])
            return bframes
    elif "rotation" not in tframes:
        return bframes
    for idx in bframes["rotation"].keys():
        bkpts = dict(bframes["rotation"][idx])
        if idx in tframes["rotation"].keys():
            tkpts = tframes["rotation"][idx]
            for n,y in tkpts:
                if n in bkpts.keys():
                    bkpts[n] += y/2
                else:
                    bkpts[n] = y/2
        kpts = list(bkpts.items())
        kpts.sort()
        bframes["rotation"][idx] = kpts


def halfRotation(frames):
    nframes = {}
    for idx in frames.keys():
        nframes[idx] = [(n,y/2) for n,y in frames[idx]]
    return nframes

#-------------------------------------------------------------
#   Animations
#-------------------------------------------------------------

def extendFcurves(rig, frame0, frame1):
    act = rig.animation_data.action
    if act is None:
        return
    for fcu in act.fcurves:
        if fcu.keyframe_points:
            value = fcu.evaluate(frame0)
            print(fcu.data_path, fcu.array_index, value)
            for frame in range(frame0, frame1):
                fcu.keyframe_points.insert(frame, value, options={'FAST'})


def getChannel(url):
    words = url.split(":")
    if len(words) == 2:
        key = words[0]
    elif len(words) == 3:
        words = words[1].rsplit("/",1)
        if len(words) == 2:
            key = words[1].rsplit("#")[-1]
        else:
            return None,None,None
    else:
        return None,None,None

    words = url.rsplit("?", 2)
    if len(words) != 2:
        return None,None,None
    words = words[1].split("/")
    if len(words) in [2,3]:
        channel = words[0]
        comp = words[1]
        return key,channel,comp
    else:
        return None,None,None

#-------------------------------------------------------------
#   Frame converter class
#-------------------------------------------------------------

class FrameConverter:

    def getConv(self, bones, rig):
        from .figure import getRigType
        from .convert import getConverter
        stype = None
        conv = {}
        twists = {}
        if (rig.DazRig == "mhx" or
            rig.DazRig[0:6] == "rigify"):
            stype = "genesis8"
        else:
            stype = getRigType(bones)
        if stype:
            conv,twists = getConverter(stype, rig)
            if not conv:
                conv = {}
        else:
            print("Could not auto-detect character in duf/dsf file")
        bonemap = OrderedDict()
        return conv, twists, bonemap


    def getRigifyLocks(self, rig, conv):
        locks = []
        if rig.DazRig[0:6] == "rigify":
            for bname in conv.values():
                if (bname in rig.pose.bones.keys() and
                    bname not in ["torso"]):
                    pb = rig.pose.bones[bname]
                    locks.append((pb, tuple(pb.lock_location)))
                    pb.lock_location = (True, True, True)
        return locks


    def convertAnimations(self, anims, rig):
        if rig.type != 'ARMATURE':
            return anims, []
        conv,twists,bonemap = self.getConv(anims[0][0], rig)
        locks = self.getRigifyLocks(rig, conv)

        for banim,vanim in anims:
            bonenames = list(banim.keys())
            bonenames.reverse()
            for bname in bonenames:
                if bname in rig.data.bones.keys():
                    bonemap[bname] = bname
                elif bname in conv.keys():
                    bonemap[bname] = conv[bname]
                else:
                    bonemap[bname] = bname

        nanims = []
        for banim,vanim in anims:
            #combineBendTwistAnimations(banim, twists)
            nbanim = {}
            for bname,frames in banim.items():
                nbanim[bonemap[bname]] = frames
            nanims.append((nbanim,vanim))

        if self.convertPoses:
            self.convertAllFrames(nanims, rig, bonemap)
        return nanims, locks


    def convertAllFrames(self, anims, rig, bonemap):
        from .convert import getCharacter, getParent

        trgCharacter = getCharacter(rig)
        if trgCharacter is None:
            return anims

        restmats = {}
        nrestmats = {}
        transmats = {}
        ntransmats = {}
        xyzs = {}
        nxyzs = {}
        for bname,nname in bonemap.items():
            bparname = getParent(self.srcCharacter, bname)
            self.getMatrices(bname, None, self.srcCharacter, bparname, restmats, transmats, xyzs)
            if nname[0:6] == "TWIST-":
                continue
            if bparname in bonemap.keys():
                nparname = bonemap[bparname]
                if nparname[0:6] == "TWIST-":
                    nparname = nparname[6:]
            elif bparname is None:
                nparname = None
            else:
                continue
            self.getMatrices(nname, rig, trgCharacter, nparname, nrestmats, ntransmats, nxyzs)

        for banim,vanim in anims:
            nbanim = {}
            for bname,nname in bonemap.items():
                if nname in banim.keys() and nname in ntransmats.keys() and bname in transmats.keys():
                    frames = banim[nname]
                    if "rotation" in frames.keys():
                        amat = ntransmats[nname].inverted()
                        bmat = transmats[bname]
                        nframes = self.convertFrames(amat, bmat, xyzs[bname], nxyzs[nname], frames["rotation"])
                        banim[nname]["rotation"] = nframes


    def getMatrices(self, bname, rig, char, parname, restmats, transmats, xyzs):
        from .convert import getOrientation

        orient,xyzs[bname] = getOrientation(char, bname, rig)
        if orient is None:
            return
        restmats[bname] = Euler(Vector(orient)*D, 'XYZ').to_matrix()

        orient = None
        if parname:
            orient,xyz = getOrientation(char, parname, rig)
            if orient:
                parmat = Euler(Vector(orient)*D, 'XYZ').to_matrix()
                transmats[bname] = restmats[bname] @ parmat.inverted()
        if orient is None:
            transmats[bname] = Matrix().to_3x3()


    def convertFrames(self, amat, bmat, xyz, nxyz, frames):
        vecs = framesToVectors(frames)
        nvecs = {}
        for t,vec in vecs.items():
            mat = Euler(vec*D, xyz).to_matrix()
            nmat = amat @ mat @ bmat
            nvecs[t] = Vector(nmat.to_euler(nxyz))/D
        return vectorsToFrames(nvecs)

#-------------------------------------------------------------
#   HideOperator class
#-------------------------------------------------------------

class HideOperator(DazOperator):
    def prequel(self, context):
        DazOperator.prequel(self, context)
        rig = context.object
        self.boneLayers = list(rig.data.layers)
        rig.data.layers = 32*[True]
        self.simpleIK = False
        if rig.DazSimpleIK:
            from .figure import SimpleIK
            self.simpleIK = SimpleIK()
            self.simpleIK.storeProps(rig)
            self.simpleIK.setProps(rig, False)
            updateScene(context)
            self.lArmIK = self.simpleIK.getLimbBoneNames(rig, "l", "Arm")
            self.rArmIK = self.simpleIK.getLimbBoneNames(rig, "r", "Arm")
            self.lLegIK = self.simpleIK.getLimbBoneNames(rig, "l", "Leg")
            self.rLegIK = self.simpleIK.getLimbBoneNames(rig, "r", "Leg")

        self.layerColls = []
        self.obhides = []
        for ob in context.scene.collection.all_objects:
            self.obhides.append((ob, ob.hide_get()))
            ob.hide_set(False)
        self.hideLayerColls(rig, context.view_layer.layer_collection)


    def hideLayerColls(self, rig, layer):
        if layer.exclude:
            return True
        ok = True
        for ob in layer.collection.objects:
            if ob == rig:
                ok = False
        for child in layer.children:
            ok = (self.hideLayerColls(rig, child) and ok)
        if ok:
            self.layerColls.append(layer)
            layer.exclude = True
        return ok


    def sequel(self, context):
        DazOperator.sequel(self, context)
        rig = context.object
        rig.data.layers = self.boneLayers
        if self.simpleIK:
            self.simpleIK.restoreProps(rig)
        for layer in self.layerColls:
            layer.exclude = False
        for ob,hide in self.obhides:
            ob.hide_set(hide)

#-------------------------------------------------------------
#   AnimatorBase class
#-------------------------------------------------------------

class ConvertOptions:
    convertPoses : BoolProperty(
        name = "Convert Poses",
        description = "Attempt to convert poses to the current rig.",
        default = False)

    srcCharacter : EnumProperty(
        items = G.theRestPoseItems,
        name = "Source Character",
        description = "Character this file was made for",
        default = "genesis_3_female")


class AffectOptions:
    affectBones : BoolProperty(
        name = "Affect Bones",
        description = "Animate bones.",
        default = True)

    affectDrivenBones : BoolProperty(
        name = "Affect Driven Bones",
        description = "Animate bones with a Drv parent",
        default = True)

    affectMorphs : BoolProperty(
        name = "Affect Morphs",
        description = "Animate morph properties.",
        default = True)

    affectObject : EnumProperty(
        items = [('OBJECT', "Object", "Animate global object transformation"),
                 ('MASTER', "Master Bone", "Object transformations affect master/root bone instead of object.\nOnly for MHX and Rigify"),
                 ('NONE', "None", "Don't animate global object transformations"),
                ],
        name = "Affect Object",
        description = "How to animate global object transformation",
        default = 'OBJECT')

    reportMissingMorphs : BoolProperty(
        name = "Report Missing Morphs",
        description = "Print a list of missing morphs.",
        default = False)

    affectSelectedOnly : BoolProperty(
        name = "Selected Bones Only",
        description = "Only animate selected bones.",
        default = False)

    ignoreLimits : BoolProperty(
        name = "Ignore Limits",
        description = "Set pose even if outside limit constraints",
        default = True)

    ignoreLocks : BoolProperty(
        name = "Ignore Locks",
        description = "Set pose even for locked bones",
        default = False)


class ActionOptions:
    makeNewAction : BoolProperty(
        name = "New Action",
        description = "Unlink current action and make a new one",
        default = True)

    actionName : StringProperty(
        name = "Action Name",
        description = "Name of loaded action",
        default = "Action")

    fps : FloatProperty(
        name = "Frame Rate",
        description = "Animation FPS in Daz Studio",
        default = 30)

    integerFrames : BoolProperty(
        name = "Integer Frames",
        description = "Round all keyframes to intergers",
        default = True)

    atFrameOne : BoolProperty(
        name = "Start At Frame 1",
        description = "Always start actions at frame 1",
        default = False)

    firstFrame : IntProperty(
        name = "First Frame",
        description = "Start import with this frame",
        default = 1)

    lastFrame : IntProperty(
        name = "Last Frame",
        description = "Finish import with this frame",
        default = 250)


class PoseLibOptions:
    makeNewPoseLib : BoolProperty(
        name = "New Pose Library",
        description = "Unlink current pose library and make a new one",
        default = True)

    poseLibName : StringProperty(
        name = "Pose Library Name",
        description = "Name of loaded pose library",
        default = "PoseLib")


class AnimatorBase(MultiFile, FrameConverter, ConvertOptions, AffectOptions, IsMeshArmature):
    filename_ext = ".duf"
    filter_glob : StringProperty(default = G.theDazDefaults + G.theImagedDefaults, options={'HIDDEN'})
    lockMeshes = False

    def __init__(self):
        pass

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "affectBones")
        if self.affectBones:
            layout.prop(self, "affectSelectedOnly")
            layout.prop(self, "affectDrivenBones")
        layout.label(text="Object Transformations Affect:")
        layout.prop(self, "affectObject", expand=True)
        layout.prop(self, "affectMorphs")
        if self.affectMorphs:
            layout.prop(self, "reportMissingMorphs")
        layout.prop(self, "ignoreLimits")
        layout.prop(self, "ignoreLocks")
        layout.prop(self, "convertPoses")
        if self.convertPoses:
            layout.prop(self, "srcCharacter")


    def invoke(self, context, event):
        return MultiFile.invoke(self, context, event)


    def getSingleAnimation(self, filepath, context, offset, missing):
        from .load_json import loadJson
        if filepath is None:
            return
        ext = os.path.splitext(filepath)[1]
        if ext in [".duf", ".dsf"]:
            struct = loadJson(filepath, False)
        else:
            raise DazError("Wrong type of file: %s" % filepath)
        if "scene" not in struct.keys():
            return offset
        animations = self.parseScene(struct["scene"])
        rig = context.object
        if rig.type == 'ARMATURE':
            bpy.ops.object.mode_set(mode='POSE')
            self.prepareRig(rig)
        self.clearPose(rig, offset)
        animations,locks = self.convertAnimations(animations, rig)
        prop = None
        result = self.animateBones(context, animations, offset, prop, filepath, missing)
        for pb,lock in locks:
            pb.lock_location = lock
        updateDrivers(rig)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.mergeHipObject(rig)
        return result


    def prepareRig(self, rig):
        self.setupRigProps(rig)
        if not self.affectBones:
            return
        if rig.DazRig == "rigify":
            from .rigify import setToFk1
            self.boneLayers = setToFk1(rig, self.boneLayers)
        elif rig.DazRig == "rigify2":
            from .rigify import setToFk2
            self.boneLayers = setToFk2(rig, self.boneLayers)
        elif rig.MhxRig or rig.DazRig == "mhx":
            from .mhx import setToFk
            self.boneLayers = setToFk(rig, self.boneLayers)


    def parseScene(self, struct):
        animations = []
        bones = {}
        values = {}
        animations.append((bones, values))
        self.parseAnimations(struct, bones, values)
        return animations


    def parseAnimations(self, struct, bones, values):
        if "animations" in struct.keys():
            for anim in struct["animations"]:
                if "url" in anim.keys():
                    key,channel,comp = getChannel(anim["url"])
                    if channel is None:
                        continue
                    elif channel == "value":
                        if self.affectMorphs:
                            values[key] = getAnimKeys(anim)
                    elif channel in ["translation", "rotation", "scale"]:
                        if key not in bones.keys():
                            bone = bones[key] = {
                                "translation" : {},
                                "rotation" : {},
                                "scale" : {},
                                "general_scale" : {},
                                }
                        idx = getIndex(comp)
                        if idx >= 0:
                            bones[key][channel][idx] = getAnimKeys(anim)
                        else:
                            bones[key]["general_scale"][0] = getAnimKeys(anim)
                    else:
                        print("Unknown channel:", channel)
        elif "extra" in struct.keys():
            for extra in struct["extra"]:
                if extra["type"] == "studio/scene_data/aniMate":
                    msg = ("Animation with aniblocks.\n" +
                           "In aniMate Lite tab, right-click         \n" +
                           "and Bake To Studio Keyframes.")
                    print(msg)
                    raise DazError(msg)
        elif self.verbose:
            print("No animations in this file")


    def isAvailable(self, pb, rig):
        if self.affectSelectedOnly:
            return pb.bone.select
        elif (pb.parent and
              isDrvBone(pb.parent.name) and
              not self.affectDrivenBones):
            return False
        elif (pb.name == self.getMasterBone(rig) and
              self.affectObject != 'MASTER'):
            return False
        else:
            return True


    def getMasterBone(self, rig):
        if rig.DazRig == "mhx":
            return "master"
        elif rig.DazRig[0:6] == "rigify":
            return "root"
        else:
            return None


    def clearPose(self, rig, frame):
        self.worldMatrix = rig.matrix_world.copy()
        tfm = Transform()
        if self.affectObject == 'OBJECT':
            tfm.setRna(rig)
            if self.insertKeys:
                tfm.insertKeys(rig, None, frame, rig.name, self.driven)
        if rig.type != 'ARMATURE':
            return
        if self.affectBones:
            for pb in rig.pose.bones:
                if self.isAvailable(pb, rig):
                    pb.matrix_basis = Matrix()
                    if self.insertKeys:
                        tfm.insertKeys(rig, pb, frame, pb.name, self.driven)
        if self.affectMorphs:
            from .morphing import getAllLowerMorphNames
            lprops = getAllLowerMorphNames(rig)
            for prop in rig.keys():
                if prop.lower() in lprops:
                    rig[prop] = 0.0
                    if self.insertKeys:
                        rig.keyframe_insert(propRef(prop), frame=frame, group=prop)


    KnownRigs = [
        "Genesis",
        "GenesisFemale",
        "GenesisMale",
        "Genesis2",
        "Genesis2Female",
        "Genesis2Male",
        "Genesis3",
        "Genesis3Female",
        "Genesis3Male",
    ]

    def animateBones(self, context, animations, offset, prop, filepath, missing):
        rig = context.object
        errors = {}
        for banim,vanim in animations:
            frames = {}
            n = -1
            for bname, channels in banim.items():
                for key,channel in channels.items():
                    if key in ["rotation", "translation"]:
                        self.addFrames(bname, channel, 3, key, frames, default=(0,0,0))
                    elif key == "scale":
                        self.addFrames(bname, channel, 3, key, frames, default=(1,1,1))
                    elif key == "general_scale":
                        self.addFrames(bname, channel, 1, key, frames)

            for vname, channels in vanim.items():
                self.addFrames(vname, {0: channels}, 1, "value", frames)

            for n,frame in frames.items():
                twists = []
                for bname in frame.keys():
                    bframe = frame[bname]
                    tfm = Transform()
                    value = 0.0
                    for key in bframe.keys():
                        if key == "translation":
                            tfm.setTrans(bframe["translation"], prop)
                        elif key == "rotation":
                            tfm.setRot(bframe["rotation"], prop)
                        elif key == "scale":
                            tfm.setScale(bframe["scale"], False, prop)
                        elif key == "general_scale":
                            tfm.setGeneral(bframe["general_scale"], False, prop)
                        elif key == "value":
                            value = bframe["value"][0]
                        else:
                            print("Unknown key:", bname, key)

                    if (bname == "@selection" or
                        bname in self.KnownRigs):
                        if self.affectObject != 'NONE':
                            tfm.setRna(rig)
                            if self.insertKeys:
                                tfm.insertKeys(rig, None, n+offset, rig.name, self.driven)
                    elif rig.type != 'ARMATURE':
                        continue
                    elif bname in rig.data.bones.keys():
                        self.transformBone(rig, bname, tfm, value, n, offset, False)
                    elif bname[0:6] == "TWIST-":
                        twists.append((bname[6:], tfm, value))
                    else:
                        if self.affectMorphs:
                            key = self.getRigKey(bname, rig, missing)
                            if key:
                                rig[key] = value
                                if self.insertKeys:
                                    rig.keyframe_insert(propRef(key), frame=n+offset, group="Morphs")

                for (bname, tfm, value) in twists:
                    self.transformBone(rig, bname, tfm, value, n, offset, True)

                # Fix scale: Blender bones inherit scale, DS bones do not
                for root in rig.pose.bones:
                    if root.parent is None:
                        self.fixScale(root, root.scale[0])

                if self.simpleIK:
                    from .figure import snapSimpleIK
                    updateScene(context)
                    snapSimpleIK(rig, self.lArmIK, "DazArmIK_L")
                    snapSimpleIK(rig, self.rArmIK, "DazArmIK_R")
                    snapSimpleIK(rig, self.lLegIK, "DazLegIK_L")
                    snapSimpleIK(rig, self.rLegIK, "DazLegIK_R")
                    if self.insertKeys:
                        updateScene(context)
                        self.simpleIK.insertIKKeys(rig, n+offset)
                    self.simpleIK.setProps(rig, False)
                    updateScene(context)

                if rig.DazRig == "mhx" and self.affectBones:
                    for suffix in ["L", "R"]:
                        forearm = rig.pose.bones["forearm.fk."+suffix]
                        hand = rig.pose.bones["hand.fk."+suffix]
                        hand.rotation_euler[1] = forearm.rotation_euler[1]
                        forearm.rotation_euler[1] = 0
                        if self.insertKeys:
                            tfm.insertKeys(rig, forearm, n+offset, bname, self.driven)
                            tfm.insertKeys(rig, hand, n+offset, bname, self.driven)

                if self.usePoseLib:
                    name = os.path.splitext(os.path.basename(filepath))[0]
                    self.addToPoseLib(rig, name)

            offset += n + 1
        return offset,prop


    def addFrames(self, bname, channel, nmax, cname, frames, default=None):
        for comp in range(nmax):
            if comp not in channel.keys():
                continue
            for t,y in channel[comp]:
                n = t*LS.fps
                if LS.integerFrames:
                    n = int(round(n))
                if n < self.firstFrame-1:
                    continue
                if n >= self.lastFrame:
                    break
                if n not in frames.keys():
                    frame = frames[n] = {}
                else:
                    frame = frames[n]
                if bname not in frame.keys():
                    bframe = frame[bname] = {}
                else:
                    bframe = frame[bname]
                if cname == "value":
                    bframe[cname] = {0: y}
                elif nmax == 1:
                    bframe[cname] = y
                elif nmax == 3:
                    if cname not in bframe.keys():
                        bframe[cname] = Vector(default)
                    bframe[cname][comp] = y


    def fixScale(self, pb, pscale):
        if self.isDazBone(pb):
            scale = pb.scale[0]
            if pb.parent:
                if abs(pscale - 1) > 1e-4:
                    if self.inheritsScale(pb):
                        scale = scale * pscale
                    else:
                        for n in range(3):
                            pb.scale[n] /= pscale
        else:
            scale = pscale
        for child in pb.children:
            self.fixScale(child, scale)


    def isDazBone(self, pb):
        return ("DazHead" in pb.bone.keys())


    def inheritsScale(self, pb):
        return (pb.name[-5:] == "Twist")


    def getRigKey(self, key, rig, missing):
        from .modifier import getCanonicalKey
        key = unquote(key)
        if key in rig.keys():
            return key
        elif rig.DazPropNames:
            if key in rig.DazPropNames.keys():
                pg = rig.DazPropNames[key]
                return pg.text
        else:
            lkey = getCanonicalKey(key.lower())
            if lkey in self.rigProps.keys():
                return self.rigProps[lkey]
        if key not in missing:
            missing.append(key)
            return None


    def setupRigProps(self, rig):
        from .modifier import getCanonicalKey
        if rig.DazPropNames:
            return
        if not self.affectMorphs:
            return
        synonymList = [
            ["updown", "up-down", "downup", "down-up"],
            ["inout", "in-out", "outin", "out-in"],
            ["cheeks", "cheek"],
        ]
        self.rigProps = {}
        for key in rig.keys():
            lkey = getCanonicalKey(key.lower())
            self.rigProps[lkey] = key
            for syns in synonymList:
                for syn1 in syns:
                    if syn1 in lkey:
                        for syn2 in syns:
                            if syn1 != syn2:
                                synkey = lkey.replace(syn1, syn2)
                                self.rigProps[synkey] = key


    def transformBone(self, rig, bname, tfm, value, n, offset, twist):
        from .node import setBoneTransform, setBoneTwist
        from .driver import isFaceBoneDriven

        if not self.affectBones:
            return
        pb = rig.pose.bones[bname]
        if self.isAvailable(pb, rig):
            if twist:
                setBoneTwist(tfm, pb)
            else:
                setBoneTransform(tfm, pb)
                self.imposeLocks(pb)
                self.imposeLimits(pb)
            if self.insertKeys:
                tfm.insertKeys(rig, pb, n+offset, bname, self.driven)
        else:
            pass
            #print("NOT AVIL", pb.name)


    def imposeLocks(self, pb):
        if self.ignoreLocks:
            return
        for n in range(3):
            if pb.lock_location[n]:
                pb.location[n] = 0
            if pb.lock_scale[n]:
                pb.scale[n] = 1
        if pb.rotation_mode == 'QUATERNION':
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_quaternion[n+1] = 0
        else:
            for n in range(3):
                if pb.lock_rotation[n]:
                    pb.rotation_euler[n] = 0


    def imposeLimits(self, pb):
        if self.ignoreLimits:
            return
        for cns in pb.constraints:
            if (cns.type == 'LIMIT_ROTATION' and
                pb.rotation_mode != 'QUATERNION'):
                if cns.use_limit_x:
                    if pb.rotation_euler[0] > cns.max_x:
                        pb.rotation_euler[0] = cns.max_x
                    elif pb.rotation_euler[0] < cns.min_x:
                        pb.rotation_euler[0] = cns.min_x
                if cns.use_limit_y:
                    if pb.rotation_euler[1] > cns.max_y:
                        pb.rotation_euler[1] = cns.max_y
                    elif pb.rotation_euler[1] < cns.min_y:
                        pb.rotation_euler[1] = cns.min_y
                if cns.use_limit_z:
                    if pb.rotation_euler[2] > cns.max_z:
                        pb.rotation_euler[2] = cns.max_z
                    elif pb.rotation_euler[2] < cns.min_z:
                        pb.rotation_euler[2] = cns.min_z
            elif cns.type == 'LIMIT_LOCATION':
                if cns.use_max_x and pb.location[0] > cns.max_x:
                    pb.location[0] = cns.max_x
                if cns.use_min_x and pb.location[0] < cns.min_x:
                    pb.location[0] = cns.min_x
                if cns.use_max_y and pb.location[0] > cns.max_y:
                    pb.location[1] = cns.max_y
                if cns.use_min_y and pb.location[0] < cns.min_y:
                    pb.location[1] = cns.min_y
                if cns.use_max_z and pb.location[0] > cns.max_z:
                    pb.location[2] = cns.max_z
                if cns.use_min_z and pb.location[0] < cns.min_z:
                    pb.location[2] = cns.min_z


    def mergeHipObject(self, rig):
        if self.affectObject == 'MASTER' and self.affectBones:
            master = self.getMasterBone(rig)
            if master in rig.pose.bones.keys():
                pb = rig.pose.bones[master]
                wmat = rig.matrix_world.copy()
                setWorldMatrix(rig, self.worldMatrix)
                pb.matrix_basis = self.worldMatrix.inverted() @ wmat


    def findDrivers(self, rig):
        driven = {}
        if (rig.animation_data and
            rig.animation_data.drivers):
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (words[0] == "pose.bones[" and
                    words[2] != "].constraints["):
                    driven[words[1]] = True
        self.driven = list(driven.keys())


    def addToPoseLib(self, rig, name):
        if rig.pose_library:
            pmarkers = rig.pose_library.pose_markers
            frame = 0
            for pmarker in pmarkers:
                if pmarker.frame >= frame:
                    frame = pmarker.frame + 1
        else:
            frame = 0
        bpy.ops.poselib.pose_add(frame=frame)
        pmarker = rig.pose_library.pose_markers.active
        pmarker.name = name
        #for pmarker in rig.pose_library.pose_markers:
        #    print("  ", pmarker.name, pmarker.frame)

#-------------------------------------------------------------
#
#-------------------------------------------------------------


def getAnimKeys(anim):
    return [key[0:2] for key in anim["keys"]]


def clearAction(self, ob):
    if self.useAction:
        if self.makeNewAction and ob.animation_data:
            ob.animation_data.action = None
    elif self.usePoseLib:
        if self.makeNewPoseLib and ob.pose_library:
            ob.pose_library = None


def nameAction(self, ob):
    if self.useAction:
        if self.makeNewAction and ob.animation_data:
            act = ob.animation_data.action
            if act:
                act.name = self.actionName
    elif self.usePoseLib:
        if self.makeNewPoseLib and ob.pose_library:
            if ob.pose_library:
                ob.pose_library.name = self.poseLibName



class StandardAnimation:

    def run(self, context):
        import time
        from .main import finishMain
        from .fileutils import getMultiFiles

        rig = context.object
        scn = context.scene
        if not self.affectSelectedOnly:
            selected = self.selectAll(rig, True)
        LS.forAnimation(self, rig)
        if scn.tool_settings.use_keyframe_insert_auto:
            self.insertKeys = True
        else:
            self.insertKeys = self.useAction
        self.findDrivers(rig)
        clearAction(self, rig)
        missing = []
        startframe = offset = scn.frame_current
        props = []
        t1 = time.perf_counter()
        print("\n--------------------")

        dazfiles = getMultiFiles(self, theDazExtensions)
        nfiles = len(dazfiles)
        if nfiles == 0:
            raise DazError("No corresponding DAZ file selected")
        self.verbose = (nfiles == 1)

        for filepath in dazfiles:
            if self.atFrameOne and len(dazfiles) == 1:
                offset = 1
            print("*", os.path.basename(filepath), offset)
            offset,prop = self.getSingleAnimation(filepath, context, offset, missing)
            if prop:
                props.append(prop)

        finishMain("File", self.filepath, t1)
        scn.frame_current = startframe
        nameAction(self, rig)
        if not self.affectSelectedOnly:
            self.selectAll(rig, selected)

        if missing and self.reportMissingMorphs:
            missing.sort()
            print("Missing morphs:\n  %s" % missing)
            raise DazError(
                "Animation loaded but some morphs were missing.     \n"+
                "See list in terminal window.\n" +
                "Check results carefully.", warning=True)


    def selectAll(self, rig, select):
        if rig.type != 'ARMATURE':
            return
        selected = []
        for bone in rig.data.bones:
            if bone.select:
                selected.append(bone.name)
            if select == True:
                bone.select = True
            else:
                bone.select = (bone.name in select)
        return selected

#-------------------------------------------------------------
#   Import Node Pose
#-------------------------------------------------------------

class NodePose:
    def parseAnimations(self, struct, bones, values):
        if "nodes" in struct.keys():
            for node in struct["nodes"]:
                key = node["id"]
                self.addTransform(node, "translation", bones, key)
                self.addTransform(node, "rotation", bones, key)
                self.addTransform(node, "scale", bones, key)
                #self.addTransform(node, "general_scale", bones, key)
        elif self.verbose:
            print("No nodes in this file")


    def addTransform(self, node, channel, bones, key):
        if channel in node.keys():
            if key not in bones.keys():
                bone = bones[key] = {}
            else:
                bone = bones[key]
            if channel not in bone.keys():
                bone[channel] = {}
            for struct in node[channel]:
                comp = struct["id"]
                value = struct["current_value"]
                bone[channel][getIndex(comp)] = [[0, value]]

#-------------------------------------------------------------
#   Import Action
#-------------------------------------------------------------

class ActionBase(ActionOptions, AnimatorBase):
    verbose = False
    useAction = True
    usePoseLib = False

    def draw(self, context):
        AnimatorBase.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "fps")
        self.layout.prop(self, "integerFrames")
        self.layout.prop(self, "atFrameOne")
        self.layout.prop(self, "firstFrame")
        self.layout.prop(self, "lastFrame")


class DAZ_OT_ImportAction(HideOperator, ActionBase, StandardAnimation):
    bl_idname = "daz.import_action"
    bl_label = "Import Action"
    bl_description = "Import poses from DAZ pose preset file(s) to action"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportNodeAction(HideOperator, NodePose, ActionBase, StandardAnimation):
    bl_idname = "daz.import_node_action"
    bl_label = "Import Action From Scene"
    bl_description = "Import poses from DAZ scene file(s) (not pose preset files) to action"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)

    def parseAnimations(self, struct, bones, values):
        NodePose.parseAnimations(self, struct, bones, values)

#-------------------------------------------------------------
#   Import Poselib
#-------------------------------------------------------------

class PoselibBase(PoseLibOptions, AnimatorBase):
    verbose = False
    useAction = False
    usePoseLib = True
    atFrameOne = False
    firstFrame = -1000
    lastFrame = 1000

    def draw(self, context):
        AnimatorBase.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "makeNewPoseLib")
        if self.makeNewPoseLib:
            self.layout.prop(self, "poseLibName")


class DAZ_OT_ImportPoseLib(HideOperator, PoselibBase, StandardAnimation):
    bl_idname = "daz.import_poselib"
    bl_label = "Import Pose Library"
    bl_description = "Import poses from DAZ pose preset file(s) to pose library"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportNodePoseLib(HideOperator, NodePose, PoselibBase, StandardAnimation):
    bl_idname = "daz.import_node_poselib"
    bl_label = "Import Pose Library From Scene"
    bl_description = "Import a poses from DAZ scene file(s) (not pose preset files) to pose library"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)

    def parseAnimations(self, struct, bones, values):
        NodePose.parseAnimations(self, struct, bones, values)

#-------------------------------------------------------------
#   Import Single Pose
#-------------------------------------------------------------

class PoseBase(AnimatorBase):
    verbose = False
    useAction = False
    usePoseLib = False
    atFrameOne = False
    firstFrame = -1000
    lastFrame = 1000


class DAZ_OT_ImportPose(HideOperator, PoseBase, StandardAnimation):
    bl_idname = "daz.import_pose"
    bl_label = "Import Pose"
    bl_description = "Import a pose from DAZ pose preset file(s)"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)


class DAZ_OT_ImportNodePose(HideOperator, NodePose, PoseBase, StandardAnimation):
    bl_idname = "daz.import_node_pose"
    bl_label = "Import Pose From Scene"
    bl_description = "Import a pose from DAZ scene file(s) (not pose preset files)"
    bl_options = {'UNDO'}

    def run(self, context):
        StandardAnimation.run(self, context)

    def parseAnimations(self, struct, bones, values):
        NodePose.parseAnimations(self, struct, bones, values)

#-------------------------------------------------------------
#   Save current frame
#-------------------------------------------------------------

def actionFrameName(ob, frame):
    return ("%s_%s" % (ob.name, frame))


def findAction(aname):
    for act in bpy.data.actions:
        if act.name == aname:
            return act
    return None


#----------------------------------------------------------
#   Clear pose
#----------------------------------------------------------

class DAZ_OT_ClearPose(DazOperator, IsArmature):
    bl_idname = "daz.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Clear all bones and object transformations"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        unit = Matrix()
        setWorldMatrix(rig, unit)
        for pb in rig.pose.bones:
            pb.matrix_basis = unit

#----------------------------------------------------------
#   Prune action
#----------------------------------------------------------

def pruneAction(act, cm):
    def matchAll(kpts, default, eps):
        for kp in kpts:
            if abs(kp.co[1] - default) > eps:
                return False
        return True

    deletes = []
    for fcu in act.fcurves:
        kpts = fcu.keyframe_points
        channel = fcu.data_path.rsplit(".", 1)[-1]
        if len(kpts) == 0:
            deletes.append(fcu)
        else:
            default = 0
            eps = 0
            if channel == "scale":
                default = 1
                eps = 0.001
            elif (channel == "rotation_quaternion" and
                fcu.array_index == 0):
                default = 1
                eps = 1e-4
            elif channel == "rotation_quaternion":
                eps = 1e-4
            elif channel == "rotation_euler":
                eps = 1e-4
            elif channel == "location":
                eps = 0.001*cm
            if matchAll(kpts, default, eps):
                deletes.append(fcu)

    for fcu in deletes:
        act.fcurves.remove(fcu)


class DAZ_OT_PruneAction(DazOperator):
    bl_idname = "daz.prune_action"
    bl_label = "Prune Action"
    bl_description = "Remove F-curves with zero keys only"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.animation_data and ob.animation_data.action)

    def run(self, context):
        ob = context.object
        pruneAction(ob.animation_data.action, ob.DazScale)

#-------------------------------------------------------------
#   Save pose
#-------------------------------------------------------------

class DAZ_OT_SavePoses(DazOperator, JsonExportFile, IsArmature):
    bl_idname = "daz.save_poses"
    bl_label = "Save Poses"
    bl_description = "Save the current pose or action as a json file"
    bl_options = {'UNDO'}

    def run(self, context):
        from .load_json import saveJson
        rig = context.object
        struct = OrderedDict()
        self.savePose(rig, struct)
        if rig.animation_data and rig.animation_data.action:
            self.saveAction(rig, struct)
        saveJson(struct, self.filepath)


    def savePose(self, rig, struct):
        struct["object"] = {
            "location" : self.addStatic(rig.location),
            "rotation_euler" : self.addStatic(rig.rotation_euler),
            "scale" : self.addStatic(rig.scale)
        }

        bones = struct["bones"] = OrderedDict()
        for pb in rig.pose.bones:
            bone = bones[pb.name] = {}
            if nonzero(pb.location):
                bone["location"] = self.addStatic(pb.location)
            if pb.rotation_mode == 'QUATERNION':
                bone["rotation_quaternion"] = self.addStatic(pb.rotation_quaternion)
            else:
                bone["rotation_euler"] = self.addStatic(pb.rotation_euler)
            if nonzero(pb.scale-One):
                bone["scale"] = self.addStatic(pb.scale)


    def addStatic(self, vec):
        return [[(0.0, x)] for x in vec]


    def saveAction(self, rig, struct):
        act = rig.animation_data.action
        object = {"location" : 3*[None], "rotation_euler" : 3*[None], "scale" : 3*[None]}
        bones = OrderedDict()
        for pb in rig.pose.bones:
            bones[pb.name] = {"location" : 3*[None], "rotation_quaternion": 4*[None], "rotation_euler" : 3*[None], "scale" : 3*[None]}

        for fcu in act.fcurves:
            channel = fcu.data_path.rsplit(".")[-1]
            words = fcu.data_path.split('"')
            if words[0] == "pose.bones[":
                bname = words[1]
                if bname in bones.keys() and channel in bones[bname].keys():
                    bones[bname][channel][fcu.array_index] = fcu
            elif channel in object.keys():
                object[channel][fcu.array_index] = fcu

        for channel,fcus in object.items():
            for idx,fcu in enumerate(fcus):
                if fcu is not None:
                    struct["object"][channel][idx] = self.addFcurve(fcu)
        for bname,channels in bones.items():
            for channel,fcus in channels.items():
                for idx, fcu in enumerate(fcus):
                    if fcu is not None:
                        struct["bones"][bname][channel][idx] = self.addFcurve(fcu)


    def addFcurve(self, fcu):
        return [list(kp.co) for kp in fcu.keyframe_points]

#-------------------------------------------------------------
#   Load pose
#-------------------------------------------------------------

class DAZ_OT_LoadPoses(HideOperator, JsonFile, SingleFile, IsArmature):
    bl_idname = "daz.load_poses"
    bl_label = "Load Poses"
    bl_description = "Load pose or action from a json file"
    bl_options = {'UNDO'}

    def run(self, context):
        from .load_json import loadJson
        struct = loadJson(self.filepath)
        rig = context.object
        if "object" in struct.keys():
            self.addFcurves(rig, struct["object"], rig, "")
        if "bones" in struct.keys():
            bones = struct["bones"]
            for pb in rig.pose.bones:
                if pb.name in bones.keys():
                    path = 'pose.bones["%s"].' % pb.name
                    self.addFcurves(pb, bones[pb.name], rig, path)


    def addFcurves(self, rna, struct, rig, path):
        for channel,data in struct.items():
            attr = getattr(rna, channel)
            for idx,kpoints in enumerate(data):
                t,y = kpoints[0]
                attr[idx] = y
                if len(kpoints) > 1:
                    rna.keyframe_insert(channel, index=idx, frame=t, group=rna.name)
                    fcu = self.findFcurve(rig, path+channel, idx)
                    for t,y in kpoints[1:]:
                        fcu.keyframe_points.insert(t, y, options={'FAST'})


    def findFcurve(self, rig, path, idx):
        for fcu in rig.animation_data.action.fcurves:
            if fcu.data_path == path and fcu.array_index == idx:
                return fcu
        return None

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportAction,
    DAZ_OT_ImportNodeAction,
    DAZ_OT_ImportPoseLib,
    DAZ_OT_ImportNodePoseLib,
    DAZ_OT_ImportPose,
    DAZ_OT_ImportNodePose,
    DAZ_OT_ClearPose,
    DAZ_OT_PruneAction,
    DAZ_OT_SavePoses,
    DAZ_OT_LoadPoses,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
