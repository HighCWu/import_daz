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
from bpy.props import BoolProperty, FloatProperty, StringProperty
from mathutils import Vector, Euler, Matrix
from .error import *
from .utils import *

FacsTable = {
    "browInnerUp" : "facs_ctrl_BrowInnerUp",
    "browDown_L" : "facs_BrowDownLeft",
    "browDown_R" : "facs_BrowDownRight",
    "browOuterUp_L" : "facs_BrowOuterUpLeft",
    "browOuterUp_R" : "facs_BrowOuterUpRight",
    "eyeLookUp_L" : "facs_jnt_EyeLookUpLeft",
    "eyeLookUp_R" : "facs_jnt_EyeLookUpRight",
    "eyeLookDown_L" : "facs_jnt_EyeLookDownLeft",
    "eyeLookDown_R" : "facs_jnt_EyeLookDownRight",
    "eyeLookIn_L" : "facs_bs_EyeLookInLeft_div2",
    "eyeLookIn_R" : "facs_bs_EyeLookInRight_div2",
    "eyeLookOut_L" : "facs_bs_EyeLookOutLeft_div2",
    "eyeLookOut_R" : "facs_bs_EyeLookOutRight_div2",
    "eyeBlink_L" : "facs_jnt_EyeBlinkLeft",
    "eyeBlink_R" : "facs_jnt_EyeBlinkRight",
    "eyeSquint_L" : "facs_bs_EyeSquintLeft_div2",
    "eyeSquint_R" : "facs_bs_EyeSquintRight_div2",
    "eyeWide_L" : "facs_jnt_EyesWideLeft",
    "eyeWide_R" : "facs_jnt_EyesWideRight",
    "cheekPuff" : "facs_ctrl_CheekPuff",
    "cheekSquint_L" : "facs_bs_CheekSquintLeft_div2",
    "cheekSquint_R" : "facs_bs_CheekSquintRight_div2",
    "noseSneer_L" : "facs_bs_NoseSneerLeft_div2",
    "noseSneer_R" : "facs_bs_NoseSneerRight_div2",
    "jawOpen" : "facs_jnt_JawOpen",
    "jawForward" : "facs_jnt_JawForward",
    "jawLeft" : "facs_jnt_JawLeft",
    "jawRight" : "facs_jnt_JawRight",
    "mouthFunnel" : "facs_bs_MouthFunnel_div2",
    "mouthPucker" : "facs_bs_MouthPucker_div2",
    "mouthLeft" : "facs_bs_MouthLeft_div2",
    "mouthRight" : "facs_bs_MouthRight_div2",
    "mouthRollUpper" : "facs_bs_MouthRollUpper_div2",
    "mouthRollLower" : "facs_bs_MouthRollLower_div2",
    "mouthShrugUpper" : "facs_bs_MouthShrugUpper_div2",
    "mouthShrugLower" : "facs_bs_MouthShrugLower_div2",
    "mouthClose" : "facs_bs_MouthClose_div2",
    "mouthSmile_L" : "facs_bs_MouthSmileLeft_div2",
    "mouthSmile_R" : "facs_bs_MouthSmileRight_div2",
    "mouthFrown_L" : "facs_bs_MouthFrownLeft_div2",
    "mouthFrown_R" : "facs_bs_MouthFrownRight_div2",
    "mouthDimple_L" : "facs_bs_MouthDimpleLeft_div2",
    "mouthDimple_R" : "facs_bs_MouthDimpleRight_div2",
    "mouthUpperUp_L" : "facs_bs_MouthUpperUpLeft_div2",
    "mouthUpperUp_R" : "facs_bs_MouthUpperUpRight_div2",
    "mouthLowerDown_L" : "facs_bs_MouthLowerDownLeft_div2",
    "mouthLowerDown_R" : "facs_bs_MouthLowerDownRight_div2",
    "mouthPress_L" : "facs_bs_MouthPressLeft_div2",
    "mouthPress_R" : "facs_bs_MouthPressRight_div2",
    "mouthStretch_L" : "facs_bs_MouthStretchLeft_div2",
    "mouthStretch_R" : "facs_bs_MouthStretchRight_div2",
    "tongueOut" : "facs_bs_TongueOut",
}

#------------------------------------------------------------------
#   Import FaceCap
#------------------------------------------------------------------

class ImportFaceCap(DazOperator, B.SingleFile, B.TextFile, B.ActionOptions, IsMeshArmature):
    bl_idname = "daz.import_facecap"
    bl_label = "Import FaceCap File"
    bl_description = "Import a text file with facecap data"
    bl_options = {'UNDO'}

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
        description = "Animation FPS in FaceCap file",
        default = 24)

    useHeadLoc : BoolProperty(
        name = "Head Location",
        description = "Include head location animation",
        default = False)

    useHeadRot : BoolProperty(
        name = "Head Rotation",
        description = "Include head rotation animation",
        default = True)

    useEyesRot : BoolProperty(
        name = "Eyes Rotation",
        description = "Include eyes rotation animation",
        default = True)


    def draw(self, context):
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "fps")
        self.layout.prop(self, "useHeadLoc")
        self.layout.prop(self, "useHeadRot")
        self.layout.prop(self, "useEyesRot")


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        from .morphing import getRigFromObject
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No rig selected")
        LS.scale = rig.DazScale
        self.parse()
        first = list(self.bskeys.values())[0]
        print("Blendshapes: %d\nKeys: %d" % (len(self.bshapes), len(first)))
        if self.makeNewAction and rig.animation_data:
            rig.animation_data.action = None
        self.build(rig)
        if self.makeNewAction and rig.animation_data:
            act = rig.animation_data.action
            if act:
                act.name = self.actionName


    def build(self, rig):
        missing = []
        for bshape in self.bshapes:
            if bshape not in FacsTable.keys():
                missing.append(bshape)
        if missing:
            msg = "Missing blendshapes:     \n"
            for bshape in missing:
                msg += ("  %s\n" % bshape)
            raise DazError(msg)

        head = self.getBone("head", rig)
        leye = self.getBone("lEye", rig)
        reye = self.getBone("rEye", rig)
        if self.useHeadLoc:
            hip = self.getBone("hip", rig)

        factor = self.fps * 1e-3

        for t in self.bskeys.keys():
            frame = factor * t

            if self.useHeadLoc:
                hip.location = self.hlockeys[t]
                hip.keyframe_insert("location", frame=frame, group="hip")

            if self.useHeadRot:
                hmat = self.hrotkeys[t].to_matrix()
                head.rotation_euler = hmat.to_euler(head.rotation_mode)
                head.keyframe_insert("rotation_euler", frame=frame, group="head")

            if self.useEyesRot:
                lmat = self.leyekeys[t].to_matrix()
                leye.rotation_euler = lmat.to_euler()
                leye.keyframe_insert("rotation_euler", frame=frame, group="lEye")

                rmat = self.reyekeys[t].to_matrix()
                reye.rotation_euler = rmat.to_euler()
                reye.keyframe_insert("rotation_euler", frame=frame, group="rEye")

            for bshape,value in zip(self.bshapes,self.bskeys[t]):
                prop = FacsTable[bshape]
                if prop in rig.keys():
                    rig[prop] = value
                    rig.keyframe_insert('["%s"]' % prop, frame=frame, group="FACS")
                else:
                    print("MISS", bshape, prop)


    def getBone(self, bname, rig):
        if bname not in rig.pose.bones.keys():
            raise DazError("Did not find bone: %s" % bname)
        pb = rig.pose.bones[bname]
        msg = ("Bone %s is driven.\nMake extra face bones first" % bname)
        if rig.animation_data:
            datapath = 'pose.bones["%s"].rotation_euler' % bname
            for fcu in rig.animation_data.drivers:
                if fcu.data_path == datapath:
                    raise DazError(msg)
        return pb


    # timestamp in milli seconds (file says nano),
    # head position xyz,
    # head eulerAngles xyz,
    # left-eye eulerAngles xy,
    # right-eye eulerAngles xy,
    # blendshapes
    def parse(self):
        self.bshapes = []
        self.hlockeys = {}
        self.hrotkeys = {}
        self.leyekeys = {}
        self.reyekeys = {}
        self.bskeys = {}
        with open(self.filepath, "r") as fp:
            for line in fp:
                line = line.strip()
                if line[0:3] == "bs,":
                    self.bshapes = line.split(",")[1:]
                elif line[0:2] == "k,":
                    words = line.split(",")
                    t = int(words[1])
                    self.hlockeys[t] = d2b((float(words[2]), float(words[3]), float(words[4])))
                    self.hrotkeys[t] = Euler((D*float(words[5]), D*float(words[6]), D*float(words[7])))
                    self.leyekeys[t] = Euler((D*float(words[9]), 0.0, D*float(words[8])))
                    self.reyekeys[t] = Euler((D*float(words[11]), 0.0, D*float(words[10])))
                    self.bskeys[t] = [float(word) for word in words[12:]]
                elif line[0:5] == "info,":
                    pass
                else:
                    raise DazError("Illegal syntax:\%s     " % line)
        return self.bshapes, self.hlockeys, self.hrotkeys, self.leyekeys, self.reyekeys, self.bskeys

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    ImportFaceCap,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)