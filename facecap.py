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
from bpy.props import BoolProperty, FloatProperty
from mathutils import Vector, Euler
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

class ImportFaceCap(DazOperator, B.SingleFile, B.TextFile, IsMeshArmature):
    bl_idname = "daz.import_facecap"
    bl_label = "Import FaceCap File"
    bl_description = "Import a text file with facecap data"
    bl_options = {'UNDO'}

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

    fps : FloatProperty(
        name = "FPS",
        description = "Frames per second",
        default = 25)

    def draw(self, context):
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
        scale = rig.DazScale
        bshapes, hlockeys, hrotkeys, leyekeys, reyekeys, bskeys = self.parse()
        first = list(bskeys.values())[0]
        print("Blendshapes: %d\nKeys: %d" % (len(bshapes), len(first)))

        missing = []
        for bshape in bshapes:
            if bshape not in FacsTable.keys():
                missing.append(bshape)
        if missing:
            msg = "Missing blendshapes:     \n"
            for bshape in missing:
                msg += ("  %s\n" % bshape)
            raise DazError(msg)

        head = rig.pose.bones["head"]
        leye = rig.pose.bones["lEye"]
        reye = rig.pose.bones["rEye"]
        factor = self.fps * 1e-3

        for t in bskeys.keys():
            frame = factor * t

            if self.useHeadLoc:
                hloc = scale * hlockeys[t]
                head.location = hloc
                head.keyframe_insert("location", frame=frame, group="head")

            if self.useHeadRot:
                rot = hrotkeys[t].to_matrix().to_euler(head.rotation_mode)
                head.rotation_euler = rot
                head.keyframe_insert("rotation_euler", frame=frame, group="head")

            if self.useEyesRot:
                rot = leyekeys[t].to_matrix().to_euler(leye.rotation_mode)
                leye.rotation_euler = rot
                leye.keyframe_insert("rotation_euler", frame=frame, group="lEye")
                rot = reyekeys[t].to_matrix().to_euler(reye.rotation_mode)
                reye.rotation_euler = rot
                reye.keyframe_insert("rotation_euler", frame=frame, group="rEye")

            for bshape,value in zip(bshapes,bskeys[t]):
                prop = FacsTable[bshape]
                if prop in rig.keys():
                    rig[prop] = value
                    rig.keyframe_insert('["%s"]' % prop, frame=frame, group="FACS")
                else:
                    print("MISS", bshape, prop)


    # timestamp in milli seconds (file says nano),
    # head position xyz,
    # head eulerAngles xyz,
    # left-eye eulerAngles xy,
    # right-eye eulerAngles xy,
    # blendshapes
    def parse(self):
        bshapes = []
        hlockeys = {}
        hrotkeys = {}
        leyekeys = {}
        reyekeys = {}
        bskeys = {}
        with open(self.filepath, "r") as fp:
            for line in fp:
                line = line.strip()
                if line[0:3] == "bs,":
                    bshapes = line.split(",")[1:]
                elif line[0:2] == "k,":
                    words = line.split(",")
                    t = int(words[1])
                    hlockeys[t] = Vector((float(words[2]), float(words[3]), float(words[4])))
                    hrotkeys[t] = Euler((D*float(words[5]), D*float(words[6]), D*float(words[7])))
                    leyekeys[t] = Euler((D*float(words[8]), D*float(words[9]), 0.0))
                    reyekeys[t] = Euler((D*float(words[10]), D*float(words[11]), 0.0))
                    bskeys[t] = [float(word) for word in words[12:]]
                elif line[0:5] == "info,":
                    pass
                else:
                    raise DazError("Illegal syntax:\%s     " % line)
        return bshapes, hlockeys, hrotkeys, leyekeys, reyekeys, bskeys

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