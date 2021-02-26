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
        modnames = ["buildnumber", "globvars", "settings", "utils", "error",
                    "buttons28",
                    "propgroups", "daz", "panel", "fileutils", "load_json", "driver", "asset", "channels", "formula",
                    "transform", "node", "figure", "bone", "geometry", "objfile",
                    "fix", "modifier", "morphing", "convert", "material", "internal",
                    "cycles", "cgroup", "pbr", "render", "camera", "light",
                    "guess", "animation", "files", "main", "finger",
                    "matedit", "tables", "proxy", "rigify", "merge", "hide",
                    "mhx", "layers", "fkik", "hair", "transfer", "dforce"]
        if bpy.app.version >= (2,82,0):
            modnames += ["udim", "facecap"]
        anchor = os.path.basename(__file__[0:-12])
        theModules = []
        for modname in modnames:
            mod = importlib.import_module("." + modname, anchor)
            theModules.append(mod)

import bpy
from . import addon_updater_ops
importModules()

#----------------------------------------------------------
#   Import documented functions available for external scripting
#----------------------------------------------------------

from .error import getErrorMessage, setSilentMode
from .fileutils import setSelection, getSelection, clearSelection
from .morphing import getMorphs
from .settings import GS

#----------------------------------------------------------
#   Updater preferences
#----------------------------------------------------------

@addon_updater_ops.make_annotations
class ImportDazPreferences(bpy.types.AddonPreferences):
    """Demo bare-bones preferences"""
    bl_idname = __package__

    # addon updater preferences

    auto_check_update = bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
        )
    updater_intrval_months = bpy.props.IntProperty(
        name='Months',
        description="Number of months between checking for updates",
        default=0,
        min=0
        )
    updater_intrval_days = bpy.props.IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31
        )
    updater_intrval_hours = bpy.props.IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23
        )
    updater_intrval_minutes = bpy.props.IntProperty(
        name='Minutes',
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59
        )

    def draw(self, context):
        layout = self.layout

        # works best if a column, or even just self.layout
        mainrow = layout.row()
        col = mainrow.column()

        # updater draw function
        # could also pass in col as third arg
        addon_updater_ops.update_settings_ui(self, context)

        # Alternate draw function, which is more condensed and can be
        # placed within an existing draw function. Only contains:
        #   1) check for update/update now buttons
        #   2) toggle for auto-check (interval will be equal to what is set above)
        # addon_updater_ops.update_settings_ui_condensed(self, context, col)

        # Adding another column to help show the above condensed ui as one column
        # col = mainrow.column()
        # col.scale_y = 2
        # col.operator("wm.url_open","Open webpage ").url=addon_updater_ops.updater.website


#----------------------------------------------------------
#   Register
#----------------------------------------------------------

def menu_func_import(self, context):
    self.layout.operator(daz.ImportDAZ.bl_idname, text="DAZ Native (.duf, .dsf)")

classes = (
    ImportDazPreferences,
)

def register():
    addon_updater_ops.register(bl_info)
    convert.initialize()
    propgroups.initialize()
    daz.initialize()
    driver.initialize()
    figure.initialize()
    finger.initialize()
    fix.initialize()
    fkik.initialize()
    geometry.initialize()
    guess.initialize()
    hide.initialize()
    layers.initialize()
    main.initialize()
    material.initialize()
    merge.initialize()
    morphing.initialize()
    animation.initialize()
    matedit.initialize()
    hair.initialize()
    mhx.initialize()
    objfile.initialize()
    proxy.initialize()
    rigify.initialize()
    transfer.initialize()
    panel.initialize()
    if bpy.app.version >= (2,82,0):
        udim.initialize()
        facecap.initialize()

    if bpy.app.version < (2,80,0):
        bpy.types.INFO_MT_file_import.append(menu_func_import)
    else:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    for cls in classes:
        addon_updater_ops.make_annotations(cls) # to avoid blender 2.8 warnings
        bpy.utils.register_class(cls)
    settings.GS.loadDefaults()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    addon_updater_ops.unregister()
    animation.uninitialize()
    convert.uninitialize()
    propgroups.uninitialize()
    daz.uninitialize()
    driver.uninitialize()
    figure.uninitialize()
    finger.uninitialize()
    fix.uninitialize()
    fkik.uninitialize()
    geometry.uninitialize()
    guess.uninitialize()
    hide.uninitialize()
    layers.uninitialize()
    main.uninitialize()
    material.uninitialize()
    merge.uninitialize()
    morphing.uninitialize()
    matedit.uninitialize()
    hair.uninitialize()
    mhx.uninitialize()
    objfile.uninitialize()
    proxy.uninitialize()
    rigify.uninitialize()
    transfer.uninitialize()
    panel.uninitialize()
    if bpy.app.version >= (2,82,0):
        udim.uninitialize()
        facecap.uninitialize()

    if bpy.app.version < (2,80,0):
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
    else:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()

print("DAZ loaded")
