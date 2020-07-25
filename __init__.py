# Copyright (c) 2016-2020, Thomas Larsson
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
    "name": "DAZ (.duf, .dsf) format",
    "author": "Thomas Larsson",
    "version": (1,5,0),
    "blender": (2,83,0),
    "location": "File > Import-Export",
    "description": "Import-Export DAZ",
    "warning": "",
    "wiki_url": "http://diffeomorphic.blogspot.se/p/daz-importer-version-15.html",
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
        modnames = ["globvars", "settings", "utils", "error"]
        if bpy.app.version < (2,80,0):
            modnames.append("buttons27")
        else:
            modnames.append("buttons28")
        modnames += ["daz", "fileutils", "load_json", "driver", "asset", "channels", "formula",
                    "transform", "node", "figure", "bone", "geometry", "objfile",
                    "fix", "modifier", "convert", "material", "matedit", "internal",
                    "cycles", "cgroup", "pbr", "render", "camera", "light",
                    "guess", "animation", "files", "main", "finger",
                    "morphing", "tables", "proxy", "rigify", "merge", "hide",
                    "mhx", "layers", "fkik", "hair",
                    "transfer", "addon", "addons"]
        if bpy.app.version >= (2,82,0):
            modnames.append("udim")
        anchor = os.path.basename(__file__[0:-12])
        theModules = []
        for modname in modnames:
            mod = importlib.import_module("." + modname, anchor)
            theModules.append(mod)

import bpy
importModules()

#----------------------------------------------------------
#   Import documented functions available for external scripting
#----------------------------------------------------------

from .error import getErrorMessage, setSilentMode
from .fileutils import setSelection, getSelection, clearSelection
from .morphing import getMorphList, getMorphs

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

addon.loadEnabledAddons()

def menu_func_import(self, context):
    self.layout.operator(daz.ImportDAZ.bl_idname, text="DAZ Native (.duf, .dsf)")


def register():
    animation.initialize()
    convert.initialize()
    daz.initialize()
    driver.initialize()
    figure.initialize()
    fileutils.initialize()
    finger.initialize()
    fix.initialize()
    fkik.initialize()
    geometry.initialize()
    guess.initialize()
    hair.initialize()
    hide.initialize()
    layers.initialize()
    main.initialize()
    material.initialize()
    matedit.initialize()
    merge.initialize()
    mhx.initialize()
    morphing.initialize()
    objfile.initialize()
    proxy.initialize()
    rigify.initialize()
    transfer.initialize()
    addon.initialize()
    if bpy.app.version >= (2,82,0):
        udim.initialize()

    if bpy.app.version < (2,80,0):
        bpy.types.INFO_MT_file_import.append(menu_func_import)
    else:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    animation.uninitialize()
    convert.uninitialize()
    daz.uninitialize()
    driver.uninitialize()
    figure.uninitialize()
    fileutils.uninitialize()
    finger.uninitialize()
    fix.uninitialize()
    fkik.uninitialize()
    geometry.uninitialize()
    guess.uninitialize()
    hair.uninitialize()
    hide.uninitialize()
    layers.uninitialize()
    main.uninitialize()
    material.uninitialize()
    matedit.uninitialize()
    merge.uninitialize()
    mhx.uninitialize()
    morphing.uninitialize()
    objfile.uninitialize()
    proxy.uninitialize()
    rigify.uninitialize()
    transfer.uninitialize()
    addon.uninitialize()
    if bpy.app.version >= (2,82,0):
        udim.uninitialize()

    if bpy.app.version < (2,80,0):
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
    else:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)



if __name__ == "__main__":
    register()

print("DAZ loaded")
