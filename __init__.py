# Copyright (c) 2016-2021, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
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


bl_info = {
    "name": "DAZ (.duf, .dsf) importer",
    "author": "Thomas Larsson",
    "version": (1,6,0),
    "blender": (2,91,0),
    "location": "UI > Daz Importer",
    "description": "Import native DAZ files (.duf, .dsf)",
    "warning": "",
    "wiki_url": "http://diffeomorphic.blogspot.se/p/daz-importer-version-16.html",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import_daz/issues?status=new&status=open",
    "category": "Import-Export"}


def importModules():
    import os
    import importlib
    global theModules

    try:
        theModules
    except NameError:
        theModules = []

    if theModules:
        print("\nReloading DAZ")
        for mod in theModules:
            importlib.reload(mod)
    else:
        print("\nLoading DAZ")
        modnames = ["buildnumber", "globvars", "settings", "utils", "error",
                    "propgroups", "daz", "fileutils", "load_json", "driver", "asset", "channels", "formula",
                    "transform", "node", "figure", "bone", "geometry", "objfile",
                    "fix", "modifier", "animation", "load_morph", "morphing", "panel",
                    "material", "cycles", "cgroup", "pbr", "render", "camera", "light",
                    "guess", "convert", "files", "main", "finger",
                    "matedit", "tables", "proxy", "rigify", "merge", "hide",
                    "mhx", "layers", "hair", "transfer", "dforce",
                    "hdmorphs", "facecap", "api"]
        if bpy.app.version >= (2,82,0):
            modnames += ["udim"]
        anchor = os.path.basename(__file__[0:-12])
        theModules = []
        for modname in modnames:
            mod = importlib.import_module("." + modname, anchor)
            theModules.append(mod)

import bpy
importModules()
from .api import *

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def register():
    convert.register()
    propgroups.register()
    daz.register()
    driver.register()
    figure.register()
    finger.register()
    fix.register()
    geometry.register()
    guess.register()
    hide.register()
    layers.register()
    main.register()
    material.register()
    merge.register()
    morphing.register()
    animation.register()
    matedit.register()
    cgroup.register()
    hair.register()
    mhx.register()
    objfile.register()
    proxy.register()
    rigify.register()
    transfer.register()
    panel.register()
    if bpy.app.version >= (2,82,0):
        udim.register()
        facecap.register()
    hdmorphs.register()
    dforce.register()

    settings.GS.loadDefaults()


def unregister():
    animation.unregister()
    convert.unregister()
    propgroups.unregister()
    daz.unregister()
    driver.unregister()
    figure.unregister()
    finger.unregister()
    fix.unregister()
    geometry.unregister()
    guess.unregister()
    hide.unregister()
    layers.unregister()
    main.unregister()
    material.unregister()
    merge.unregister()
    morphing.unregister()
    matedit.unregister()
    cgroup.unregister()
    hair.unregister()
    mhx.unregister()
    objfile.unregister()
    proxy.unregister()
    rigify.unregister()
    transfer.unregister()
    panel.unregister()
    if bpy.app.version >= (2,82,0):
        udim.unregister()
        facecap.unregister()
    hdmorphs.unregister()
    dforce.unregister()


if __name__ == "__main__":
    register()

print("DAZ loaded")
