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
from .utils import *
from .error import *

#-------------------------------------------------------------
#   Property groups
#-------------------------------------------------------------

class DazIntGroup(bpy.types.PropertyGroup):
    a : IntProperty()

class DazBoolGroup(bpy.types.PropertyGroup):
    t : BoolProperty()

class DazFloatGroup(bpy.types.PropertyGroup):
    f : FloatProperty()

class DazStringGroup(bpy.types.PropertyGroup):
    s : StringProperty()

class DazStringIntGroup(bpy.types.PropertyGroup):
    s : StringProperty()
    i : IntProperty()

class DazStringBoolGroup(bpy.types.PropertyGroup):
    s : StringProperty()
    b : BoolProperty()

class DazPairGroup(bpy.types.PropertyGroup):
    a : IntProperty()
    b : IntProperty()

class DazStringStringGroup(bpy.types.PropertyGroup):
    names : CollectionProperty(type = bpy.types.PropertyGroup)


class DazTextGroup(bpy.types.PropertyGroup):
    text : StringProperty()

    def __lt__(self, other):
        return (self.text < other.text)


class DazMorphInfoGroup(bpy.types.PropertyGroup):
    morphset : StringProperty()
    text : StringProperty()
    bodypart : StringProperty()
    category : StringProperty()

#-------------------------------------------------------------
#   Rigidity groups
#-------------------------------------------------------------

class DazRigidityGroup(bpy.types.PropertyGroup):
    id : StringProperty()
    rotation_mode : StringProperty()
    scale_modes : StringProperty()
    reference_vertices : CollectionProperty(type = DazIntGroup)
    mask_vertices : CollectionProperty(type = DazIntGroup)
    use_transform_bones_for_scale : BoolProperty()

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

class DazMorphGroupProps:
    prop : StringProperty()
    factor : FloatProperty()
    factor2 : FloatProperty()
    index : IntProperty()
    default : FloatProperty()
    simple : BoolProperty(default=True)


class DazMorphGroup(bpy.types.PropertyGroup, DazMorphGroupProps):
    def __repr__(self):
        return "<MorphGroup %d %s %f %f>" % (self.index, self.prop, self.factor, self.default)

    def eval(self, rig):
        if self.simple:
            return self.factor*(rig[self.name] - self.default)
        else:
            value = rig[self.name] - self.default
            return (self.factor*(value > 0) + self.factor2*(value < 0))*value

    def display(self):
        return ("MG %d %-25s %10.6f %10.6f %10.2f" % (self.index, self.name, self.factor, self.factor2, self.default))

    def init(self, prop, idx, default, factor, factor2):
        self.name = prop
        self.index = idx
        self.factor = factor
        self.default = default
        if factor2 is None:
            self.factor2 = 0
            self.simple = True
        else:
            self.factor2 = factor2
            self.simple = False

    def __lt__(self,other):
        if self.name == other.name:
            return (self.index < other.index)
        else:
            return (self.name < other.name)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DazIntGroup,
    DazBoolGroup,
    DazFloatGroup,
    DazStringGroup,
    DazStringBoolGroup,
    DazPairGroup,
    DazRigidityGroup,
    DazStringStringGroup,
    DazTextGroup,
    DazMorphInfoGroup,
    DazMorphGroup,
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
