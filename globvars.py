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

import os
from collections import OrderedDict

#-------------------------------------------------------------
#   animation.py
#-------------------------------------------------------------

theImagedDefaults = ";*.png;*.jpeg;*.jpg;*.bmp"
theImageExtensions = ["png", "jpeg", "jpg", "bmp", "tif", "tiff"]

theDazExtensions = ["dsf", "duf"]
theDazUpcaseExtensions = [ext.upper() for ext in theDazExtensions]
theDazDefaults = ";".join(["*.%s" % ext for ext in theDazExtensions+theDazUpcaseExtensions])

thePoserExtensions = ["pp2", "pz2", "cr2", "pp3", "pz3", "cr3"]
thePoserUpcaseExtensions = [ext.upper() for ext in thePoserExtensions]
thePoserDefaults = ";".join(["*.%s" % ext for ext in thePoserExtensions+thePoserUpcaseExtensions])
theImagedPoserDefaults = theImagedDefaults + thePoserDefaults

#-------------------------------------------------------------
#   convert.py
#-------------------------------------------------------------

theRestPoseFolder = os.path.join(os.path.dirname(__file__), "data", "restposes")
theParentsFolder = os.path.join(os.path.dirname(__file__), "data", "parents")
theIkPoseFolder = os.path.join(os.path.dirname(__file__), "data", "ikposes")

theRestPoseItems = []
for file in os.listdir(theRestPoseFolder):
    fname = os.path.splitext(file)[0]
    name = fname.replace("_", " ").capitalize()
    theRestPoseItems.append((fname, name, name))
    
# ---------------------------------------------------------------------
#   material.py   
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, isColor)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1)),
    ("Bump Distance", ("BUMP", "Distance", None, None, 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1)),

    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", None, None, 4)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", None, None, 1)),

    ("Glossy Color", ("BSDF_GLOSSY", "Color", None, None, 4)),
    ("Glossy Roughness", ("BSDF_GLOSSY", "Roughness", None, None, 1)),

    ("Translucency Color", ("BSDF_TRANSLUCENT", "Color", "use_map_translucency", "translucency_factor", 4)),

    ("Subsurface Color", ("SUBSURFACE_SCATTERING", "Color", None, None, 4)),
    ("Subsurface Scale", ("SUBSURFACE_SCATTERING", "Scale", None, None, 1)),
    ("Subsurface Radius", ("SUBSURFACE_SCATTERING", "Radius", None, None, 3)),

    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", None, None, 4)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", None, None, 1)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", None, None, 1)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", None, None, 1)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", None, None, 4)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", None, None, 3)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", None, None, 1)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", None, None, 1)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", None, None, 1)),
])
    

