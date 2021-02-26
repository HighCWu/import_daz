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

import os
import bpy
from bpy.props import *

from . import globvars as G

#-------------------------------------------------------------
#   Property groups
#-------------------------------------------------------------

class DazMorphGroupProps:
    prop : StringProperty()
    factor : FloatProperty()
    factor2 : FloatProperty()
    index : IntProperty()
    default : FloatProperty()
    simple : BoolProperty(default=True)


class DazIntGroup(bpy.types.PropertyGroup):
    a : IntProperty()

class DazFloatGroup(bpy.types.PropertyGroup):
    f : FloatProperty()

class DazPairGroup(bpy.types.PropertyGroup):
    a : IntProperty()
    b : IntProperty()

class DazDriverGroup(bpy.types.PropertyGroup):
    index : IntProperty()
    expression : StringProperty()
    channel : StringProperty()

class DazStringStringGroup(bpy.types.PropertyGroup):
    names : CollectionProperty(type = bpy.types.PropertyGroup)

class DazKeys(bpy.types.PropertyGroup):
    keys : CollectionProperty(type = StringProperty)


class DazTextGroup(bpy.types.PropertyGroup):
    text : StringProperty()

    def __lt__(self, other):
        return (self.text < other.text)

if bpy.app.version < (2,90,0):
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False)

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True)
else:
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False, override={'LIBRARY_OVERRIDABLE'})

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True, override={'LIBRARY_OVERRIDABLE'})

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
