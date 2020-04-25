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
    "version": (1,4,2),
    "blender": (2,80,2),
    "location": "File > Import-Export",
    "description": "Import-Export DAZ",
    "warning": "",
    "wiki_url": "http://diffeomorphic.blogspot.se/p/daz-importer-version-14.html",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import-daz/issues?status=new&status=open",
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
from bpy.props import *
importModules()
from .error import *

if bpy.app.version < (2,80,0):
    Region = "TOOLS"
else:
    Region = "UI"

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

class DAZ_PT_Setup(bpy.types.Panel):
    bl_label = "Setup (version %d.%d.%d)" % bl_info["version"]
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"

    def draw(self, context):
        scn = context.scene
        ob = context.object
        layout = self.layout

        layout.operator("daz.import_daz")

        layout.separator()
        box = layout.box()
        if not scn.DazShowCorrections:
            box.prop(scn, "DazShowCorrections", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowCorrections", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.merge_rigs")
            box.operator("daz.merge_toes")
            box.operator("daz.add_extra_face_bones")
            box.operator("daz.make_all_bones_posable")
            box.operator("daz.update_all")

        layout.separator()
        box = layout.box()
        if not scn.DazShowMaterials:
            box.prop(scn, "DazShowMaterials", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowMaterials", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.save_local_textures")
            box.operator("daz.resize_textures")
            box.operator("daz.change_resolution")

            box.separator()
            box.operator("daz.change_colors")
            box.operator("daz.change_skin_color")
            box.operator("daz.merge_materials")

            box.separator()
            box.operator("daz.load_uv")
            box.operator("daz.prune_uv_maps")
            #box.operator("daz.load_materials")

            box.separator()
            box.operator("daz.collapse_udims")
            box.operator("daz.restore_udims")

            box.separator()
            box.operator("daz.launch_editor")
            box.operator("daz.reset_material")

        layout.separator()
        box = layout.box()
        if not scn.DazShowMorphs:
            box.prop(scn, "DazShowMorphs", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowMorphs", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.import_units")
            box.operator("daz.import_expressions")
            box.operator("daz.import_visemes")
            box.operator("daz.import_custom_morphs")
            box.operator("daz.import_correctives")
            box.label(text="Create low-poly meshes before transfers.")
            box.operator("daz.transfer_correctives")
            box.operator("daz.transfer_other_morphs")

        layout.separator()
        box = layout.box()
        if not scn.DazShowFinish:
            box.prop(scn, "DazShowFinish", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowFinish", icon="DOWNARROW_HLT", emboss=False)
            if bpy.app.version >= (2,82,0):
                box.operator("daz.set_udims")
            box.operator("daz.merge_geografts")
            if bpy.app.version >= (2,82,0):
                box.operator("daz.make_udim_materials")
            box.operator("daz.merge_shapekeys")
            box.operator("daz.merge_uv_layers")

            box.separator()
            box.operator("daz.optimize_pose")
            box.operator("daz.apply_rest_pose")
            box.operator("daz.convert_mhx")
            box.separator()
            box.operator("daz.rigify_daz")
            box.operator("daz.create_meta")
            box.operator("daz.rigify_meta")


    def showBox(self, layout, scn, ob, type):
        from .morphing import theMorphNames, theMorphFiles
        if ob is None:
            return
        box = layout.box()
        if ob.DazMesh not in theMorphFiles.keys():
            box.label(text = "Object '%s'" % ob.name)
            box.label(text = "has no available %s morphs" % type)
            return
        box.label(text = "Select morphs to load")
        btn = box.operator("daz.select_all_morphs", text="Select All")
        btn.type = type
        btn.value = True
        btn = box.operator("daz.select_all_morphs", text="Deselect All")
        btn.type = type
        btn.value = False
        if ob.DazMesh in theMorphFiles.keys():
            names = list(theMorphFiles[ob.DazMesh][type].keys())
            names.sort()
            for name in names:
                box.prop(scn, "Daz"+name)


class DAZ_PT_Advanced(bpy.types.Panel):
    bl_label = "Advanced Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scn = context.scene
        ob = context.object
        layout = self.layout

        box = layout.box()
        if not scn.DazShowLowpoly:
            box.prop(scn, "DazShowLowpoly", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowLowpoly", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.print_statistics")
            box.separator()
            box.operator("daz.apply_morphs")
            box.operator("daz.make_quick_proxy")
            box.separator()
            box.operator("daz.make_faithful_proxy")
            box.operator("daz.split_ngons")
            box.operator("daz.quadify")
            box.separator()
            box.operator("daz.select_random_strands")
            box.separator()
            box.operator("daz.add_push")
            box.operator("daz.add_subsurf")
            box.separator()
            box.operator("daz.make_deflection")

        layout.separator()
        box = layout.box()
        if not scn.DazShowVisibility:
            box.prop(scn, "DazShowVisibility", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowVisibility", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.create_all_masks")
            box.operator("daz.create_selected_masks")
            box.operator("daz.add_hide_drivers")
            box.operator("daz.remove_hide_drivers")
            if bpy.app.version >= (2,80,0):
                box.separator()
                box.operator("daz.add_hide_collections")
                box.operator("daz.remove_hide_collections")
                box.operator("daz.create_collections")

        layout.separator()
        box = layout.box()
        if not scn.DazShowMesh:
            box.prop(scn, "DazShowMesh", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowMesh", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.fit_mesh_to_other")
            box.operator("daz.find_seams")
            box.operator("daz.prune_vertex_groups")
            box.operator("daz.get_finger_print")
            box.operator("daz.mesh_add_pinning")

        layout.separator()
        box = layout.box()
        if not scn.DazShowRigging:
            box.prop(scn, "DazShowRigging", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowRigging", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.convert_rig")
            box.separator()
            box.operator("daz.apply_rest_pose")
            box.operator("daz.copy_bones")
            box.operator("daz.copy_poses")
            #box.operator("daz.reparent_toes")
            box.separator()
            box.operator("daz.add_mannequin")
            box.separator()
            box.operator("daz.add_ik_goals")
            box.operator("daz.add_winder")
            if bpy.app.version < (2,80,0):
                box.separator()
                box.operator("daz.add_to_group")
                box.operator("daz.remove_from_groups")
                box.prop(scn, "DazGroup")
            box.separator()
            box.operator("daz.list_bones")
            box.operator("daz.get_finger_print")

        layout.separator()
        box = layout.box()
        if not scn.DazShowAdvancedMorph:
            box.prop(scn, "DazShowAdvancedMorph", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowAdvancedMorph", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.remove_standard_morphs")
            box.operator("daz.remove_custom_morphs")
            box.separator()
            box.operator("daz.rename_category")
            box.operator("daz.remove_categories")
            box.separator()
            box.operator("daz.convert_standard_morphs_to_shapekeys")
            box.operator("daz.convert_custom_morphs_to_shapekeys")
            box.separator()
            box.operator("daz.add_shapekey_drivers")
            box.operator("daz.remove_shapekey_drivers")
            box.operator("daz.remove_unused_drivers")
            box.operator("daz.remove_all_morph_drivers")
            box.separator()
            box.operator("daz.copy_props")
            box.operator("daz.copy_bone_drivers")
            box.operator("daz.retarget_mesh_drivers")
            box.separator()
            box.operator("daz.update_prop_limits")
            box.prop(scn, "DazPropMin")
            box.prop(scn, "DazPropMax")
            box.separator()
            box.operator("daz.create_graft_groups")
            box.separator()
            box.operator("daz.import_json")

        layout.separator()
        box = layout.box()
        if not scn.DazShowHair:
            box.prop(scn, "DazShowHair", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowHair", icon="DOWNARROW_HLT", emboss=False)
            from .hair import getHairAndHuman
            box.operator("daz.make_hair")
            hair,hum = getHairAndHuman(context, False)
            box.label(text = "  Hair:  %s" % (hair.name if hair else None))
            box.label(text = "  Human: %s" % (hum.name if hum else None))
            box.separator()
            box.operator("daz.update_hair")
            box.operator("daz.color_hair")
            #box.operator("daz.connect_hair")        
    

class DAZ_PT_Settings(bpy.types.Panel):
    bl_label = "Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scn = context.scene
        layout = self.layout

        layout.separator()
        box = layout.box()
        if not scn.DazShowSettings:
            box.prop(scn, "DazShowSettings", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowSettings", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.load_factory_settings")
            box.operator("daz.save_default_settings")
            box.operator("daz.load_default_settings")
            box.operator("daz.save_settings_file")
            box.operator("daz.load_settings_file")

        layout.separator()
        box = layout.box()
        if not scn.DazShowPaths:
            box.prop(scn, "DazShowPaths", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowPaths", icon="DOWNARROW_HLT", emboss=False)
            box.prop(scn, "DazNumPaths")
            for n in range(scn.DazNumPaths):
                box.prop(scn, "DazPath%d" % (n+1), text="")
            box.label(text = "Path to output errors:")
            box.prop(scn, "DazErrorPath", text="")

        layout.separator()
        box = layout.box()
        if not scn.DazShowGeneral:
            box.prop(scn, "DazShowGeneral", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowGeneral", icon="DOWNARROW_HLT", emboss=False)
            box.prop(scn, "DazVerbosity")
            box.separator()
            box.prop(scn, "DazPropMin")
            box.prop(scn, "DazPropMax")
            box.prop(scn, "DazUsePropLimits")
            box.prop(scn, "DazUsePropDefault")
            box.separator()
            box.prop(scn, "DazZup")
            box.prop(scn, "DazOrientation")
            box.prop(scn, "DazBestOrientation")
            box.prop(scn, "DazCaseSensitivePaths")
            box.prop(scn, "DazRename")
            box.prop(scn, "DazUseGroup")

        layout.separator()
        box = layout.box()
        if not scn.DazShowRiggingSettings:
            box.prop(scn, "DazShowRiggingSettings", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowRiggingSettings", icon="DOWNARROW_HLT", emboss=False)
            box.prop(scn, "DazAddFaceDrivers")
            box.prop(scn, "DazUseLockRot")
            box.prop(scn, "DazUseLockLoc")
            #box.prop(scn, "DazUseLimitRot")
            #box.prop(scn, "DazUseLimitLoc")
            box.prop(scn, "DazDeleteMeta")
            box.prop(scn, "DazMakeDrivers")

        layout.separator()
        box = layout.box()
        if not scn.DazShowMaterialSettings:
            box.prop(scn, "DazShowMaterialSettings", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowMaterialSettings", icon="DOWNARROW_HLT", emboss=False)
            box.prop(scn, "DazChooseColors")
            box.prop(scn, "DazMergeShells")
            box.prop(scn, "DazMaxBump")
            box.prop(scn, "DazHandleRenderSettings")            
            box.separator()
            box.prop(scn, "DazUseDisplacement")
            box.prop(scn, "DazUseEmission")
            box.prop(scn, "DazUseReflection")
            if bpy.app.version < (2,80,0):
                box.separator()
                box.prop(scn, "DazDiffuseShader")
                box.prop(scn, "DazSpecularShader")
                box.prop(scn, "DazDiffuseRoughness")
                box.prop(scn, "DazSpecularRoughness")


class DAZ_PT_Utils(bpy.types.Panel):
    bl_label = "Utilities"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        layout = self.layout
        layout.operator("daz.decode_file")
        layout.separator()
        layout.operator("daz.inspect_prop_groups")
        layout.operator("daz.inspect_prop_dependencies")        
        layout.separator()
        box = layout.box()
        box.label(text = "Information About Active Object")
        if ob:
            box.prop(ob, "name")
            box.prop(ob, "DazId")
            box.prop(ob, "DazUrl")
            box.prop(ob, "DazRig")
            box.prop(ob, "DazMesh")
            box.prop(ob, "DazScale")
            box.operator("daz.print_statistics")
        else:
            box.label(text = "No active object")


class DAZ_PT_Addons(bpy.types.Panel):
    bl_label = "Add-Ons"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        from .addon import theAddons
        row = self.layout.row()
        row.operator("daz.refresh_addons")
        row.operator("daz.save_addons")
        for mname in theAddons.keys():
            module,enabled,show,bl_info = theAddons[mname]
            box = self.layout.box()
            row = box.row()
            if show:
                icon = "TRIA_DOWN"
            else:
                icon = "TRIA_RIGHT"
            row.operator("daz.show_addon", icon=icon, text="", emboss=False).name=mname
            if enabled:
                icon = "CHECKBOX_HLT"
            else:
                icon = "CHECKBOX_DEHLT"
            row.operator("daz.enable_addon", icon=icon, text="", emboss=False).name=mname
            row.label(text=bl_info["name"])

            if show and bl_info:
                for key in ["description", "location", "file", "author", "version"]:
                    if key in bl_info.keys():
                        split = utils.splitLayout(box, 0.2)
                        split.label(text=key.capitalize()+":")
                        split.label(text=str(bl_info[key]))
                split = utils.splitLayout(box, 0.2)
                split.label(text="Internet:")
                for label,key,icon in [
                    ("Documentation", "wiki_url", "HELP"),
                    ("Report a Bug", "tracker_url", "URL")]:
                    if key in bl_info.keys():
                        split.operator("wm.url_open", text=label, icon=icon).url=bl_info[key]


class DAZ_PT_Posing(bpy.types.Panel):
    bl_label = "Posing"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object)

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout

        layout.operator("daz.import_single_pose")
        layout.operator("daz.import_poselib")
        layout.operator("daz.import_action")
        layout.separator()
        layout.operator("daz.prune_action")
        layout.separator()
        layout.operator("daz.save_current_frame")
        layout.operator("daz.restore_current_frame")

        layout.separator()
        split = utils.splitLayout(layout, 0.6)
        layout.operator("daz.toggle_loc_locks", text = "Location Locks Are " + ("ON" if ob.DazUseLocLocks else "OFF"))
        layout.operator("daz.toggle_rot_locks", text = "Rotation Locks Are " + ("ON" if ob.DazUseRotLocks else "OFF"))
        layout.operator("daz.toggle_limits", text = "Limits Are " + ("ON" if ob.DazUseLimits else "OFF"))

        layout.separator()
        layout.operator("daz.rotate_bones")

        return

        layout.separator()
        layout.operator("daz.save_current_pose")
        layout.operator("daz.load_pose")
        return

        layout.separator()
        layout.operator("daz.import_node_poses")



def activateLayout(layout, type, prefix):
    split = utils.splitLayout(layout, 0.3333)
    split.operator("daz.prettify")
    op = split.operator("daz.activate_all")
    op.type = type
    op.prefix = prefix
    op = split.operator("daz.deactivate_all")
    op.type = type
    op.prefix = prefix


def keyLayout(layout, type, prefix):
    split = utils.splitLayout(layout, 0.25)
    op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
    op.type = type
    op.prefix = prefix
    op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
    op.type = type
    op.prefix = prefix
    op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
    op.type = type
    op.prefix = prefix
    op = split.operator("daz.clear_morphs", text="", icon='X')
    op.type = type
    op.prefix = prefix


class DAZ_PT_Morphs:

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and getattr(ob, self.show) and ob.DazMesh)

    def draw(self, context):
        from .morphing import theMorphNames, nameFromKey
        rig = context.object
        scn = context.scene
        if rig.type == 'MESH':
            rig = rig.parent
            if rig is None:
                return
        if rig.type != 'ARMATURE':
            return
        layout = self.layout

        if not (rig.DazNewStyleExpressions or theMorphNames):
            layout.operator("daz.update_morph_paths")
            return

        activateLayout(layout, self.type, self.prefix)
        keyLayout(layout, self.type, self.prefix)
        layout.separator()

        if rig.DazNewStyleExpressions:
            from .formula import inStringGroup
            for key in utils.sorted(rig.keys()):
                if (key[0:3] == self.prefix and
                    not inStringGroup(rig.DazHiddenProps, key)):
                    self.displayProp(key[3:], key, rig, scn)
        else:
            names = theMorphNames[self.type]
            for key in utils.sorted(rig.keys()):
                name = nameFromKey(key, names, rig)
                if name:
                    self.displayProp(name, key, rig, scn)


    def displayProp(self, name, key, rig, scn):
        row = utils.splitLayout(self.layout, 0.8)
        row.prop(rig, '["%s"]' % key, text=name)
        showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.type = self.type
        op.prefix = self.prefix


def showBool(layout, ob, key, text=""):
    from .morphing import getExistingActivateGroup
    pg = getExistingActivateGroup(ob, key)
    if pg is not None:
        layout.prop(pg, "active", text=text)


class DAZ_PT_Units(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Face Units"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    type = "Units"
    prefix = "DzU"
    show = "DazUnits"


class DAZ_PT_Expressions(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Expressions"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    type = "Expressions"
    prefix = "DzE"
    show = "DazExpressions"


class DAZ_PT_Viseme(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Visemes"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    type = "Visemes"
    prefix = "DzV"
    show = "DazVisemes"

    def draw(self, context):
        self.layout.operator("daz.load_moho")
        DAZ_PT_Morphs.draw(self, context)

#------------------------------------------------------------------------
#    Custom panels
#------------------------------------------------------------------------

class DAZ_PT_CustomMorphs(bpy.types.Panel):
    bl_label = "Custom Morphs"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazCustomMorphs)


    def draw(self, context):
        ob = morphing.getRigFromObject(context.object)
        scn = context.scene
        if ob is None:
            return
        layout = self.layout

        activateLayout(layout, "CUSTOM", "")
        keyLayout(layout, "CUSTOM", "")
        row = layout.row()
        row.operator("daz.toggle_all_cats", text="Open All Categories").useOpen=True
        row.operator("daz.toggle_all_cats", text="Close All Categories").useOpen=False

        for cat in ob.DazMorphCats:
            layout.separator()
            box = layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name, icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name, icon="DOWNARROW_HLT", emboss=False)
            for morph in cat.morphs:
                if morph.prop in ob.keys():
                    row = utils.splitLayout(box, 0.8)
                    row.prop(ob, '["%s"]' % morph.prop, text=morph.name)
                    showBool(row, ob, morph.prop)
                    op = row.operator("daz.pin_prop", icon='UNPINNED')
                    op.key = morph.prop
                    op.type = "CUSTOM"

#------------------------------------------------------------------------
#    Mhx Layers Panel
#------------------------------------------------------------------------

class DAZ_PT_MhxLayers(bpy.types.Panel):
    bl_label = "MHX Layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazRig == "mhx")

    def draw(self, context):
        from .layers import MhxLayers, OtherLayers

        layout = self.layout
        layout.operator("daz.pose_enable_all_layers")
        layout.operator("daz.pose_disable_all_layers")

        rig = context.object
        if rig.DazRig == "mhx":
            layers = MhxLayers
        else:
            layers = OtherLayers

        for (left,right) in layers:
            row = layout.row()
            if type(left) == str:
                row.label(text=left)
                row.label(text=right)
            else:
                for (n, name, prop) in [left,right]:
                    row.prop(rig.data, "layers", index=n, toggle=True, text=name)

#------------------------------------------------------------------------
#    Mhx FK/IK switch panel
#------------------------------------------------------------------------

class DAZ_PT_MhxFKIK(bpy.types.Panel):
    bl_label = "MHX FK/IK Switch"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazRig == "mhx")

    def draw(self, context):
        rig = context.object
        layout = self.layout

        row = layout.row()
        row.label(text = "")
        row.label(text = "Left")
        row.label(text = "Right")

        layout.label(text = "FK/IK switch")
        row = layout.row()
        row.label(text = "Arm")
        self.toggle(row, rig, "MhaArmIk_L", " 3", " 2")
        self.toggle(row, rig, "MhaArmIk_R", " 19", " 18")
        row = layout.row()
        row.label(text = "Leg")
        self.toggle(row, rig, "MhaLegIk_L", " 5", " 4")
        self.toggle(row, rig, "MhaLegIk_R", " 21", " 20")

        layout.label(text = "IK Influence")
        row = layout.row()
        row.label(text = "Arm")
        row.prop(rig, '["MhaArmIk_L"]', text="")
        row.prop(rig, '["MhaArmIk_R"]', text="")
        row = layout.row()
        row.label(text = "Leg")
        row.prop(rig, '["MhaLegIk_L"]', text="")
        row.prop(rig, '["MhaLegIk_R"]', text="")

        layout.separator()
        layout.label(text = "Snap Arm Bones")
        row = layout.row()
        row.label(text = "FK Arm")
        row.operator("daz.snap_fk_ik", text="Snap L FK Arm").data = "MhaArmIk_L 2 3 12"
        row.operator("daz.snap_fk_ik", text="Snap R FK Arm").data = "MhaArmIk_R 18 19 28"
        row = layout.row()
        row.label(text = "IK Arm")
        row.operator("daz.snap_ik_fk", text="Snap L IK Arm").data = "MhaArmIk_L 2 3 12"
        row.operator("daz.snap_ik_fk", text="Snap R IK Arm").data = "MhaArmIk_R 18 19 28"

        layout.label(text = "Snap Leg Bones")
        row = layout.row()
        row.label(text = "FK Leg")
        row.operator("daz.snap_fk_ik", text="Snap L FK Leg").data = "MhaLegIk_L 4 5 12"
        row.operator("daz.snap_fk_ik", text="Snap R FK Leg").data = "MhaLegIk_R 20 21 28"
        row = layout.row()
        row.label(text = "IK Leg")
        row.operator("daz.snap_ik_fk", text="Snap L IK Leg").data = "MhaLegIk_L 4 5 12"
        row.operator("daz.snap_ik_fk", text="Snap R IK Leg").data = "MhaLegIk_R 20 21 28"

        onoff = "Off" if rig.DazHintsOn else "On"
        layout.operator("daz.toggle_hints", text="Toggle Hints %s" % onoff)


    def toggle(self, row, rig, prop, fk, ik):
        if getattr(rig, prop) > 0.5:
            row.operator("daz.toggle_fk_ik", text="IK").toggle = prop + " 0" + fk + ik
        else:
            row.operator("daz.toggle_fk_ik", text="FK").toggle = prop + " 1" + ik + fk

#------------------------------------------------------------------------
#    Mhx Properties Panel
#------------------------------------------------------------------------

class DAZ_PT_MhxProperties(bpy.types.Panel):
    bl_label = "MHX Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazRig == "mhx")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        layout.prop(ob, "DazGazeFollowsHead", text="Gaze Follows Head")
        row = layout.row()
        row.label(text = "Left")
        row.label(text = "Right")
        props = [key for key in dir(ob) if key[0:3] == "Mha"]
        props.sort()
        while props:
            left,right = props[0:2]
            props = props[2:]
            row = layout.row()
            row.prop(ob, left, text=left[3:-2])
            row.prop(ob, right, text=right[3:-2])

#------------------------------------------------------------------------
#   Visibility and Makeup panels
#------------------------------------------------------------------------

class DAZ_PT_Hide:
    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
        split = utils.splitLayout(layout, 0.3333)
        split.operator("daz.prettify")
        split.operator("daz.show_all").prefix=self.prefix
        split.operator("daz.hide_all").prefix=self.prefix
        props = list(ob.keys())
        props.sort()
        for prop in props:
            if prop[0:3] == self.prefix:
                layout.prop(ob, prop, text=prop[3:])


class DAZ_PT_Visibility(DAZ_PT_Hide, bpy.types.Panel):
    bl_label = "Visibility"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    prefix = "Mhh"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityDrivers)


class DAZ_PT_Makeup(DAZ_PT_Hide, bpy.types.Panel):
    bl_label = "Makeup"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ"
    bl_options = {'DEFAULT_CLOSED'}

    prefix = "DzM"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazMakeupDrivers)

#----------------------------------------------------------
#   Register
#----------------------------------------------------------

addon.loadEnabledAddons()

def menu_func_import(self, context):
    self.layout.operator(daz.ImportDAZ.bl_idname, text="DAZ Native (.duf, .dsf)")


def initialize():

    bpy.types.Scene.DazStrictMorphs = BoolProperty(
        name = "Strict Morphs",
        description = "Require that mesh and morph vertex counts are equal",
        default = True)

    bpy.types.Scene.DazLoadAllMorphs = BoolProperty(
        name = "Load All Morphs",
        description = "Load all morphs in selected directory",
        default = False)

    bpy.types.Scene.DazPropMin = FloatProperty(
        name = "Property Minima",
        description = "Minimum value of properties",
        min = -10.0, max = 0.0,
        default = -1.0)

    bpy.types.Scene.DazPropMax = FloatProperty(
        name = "Property Maxima",
        description = "Maximum value of properties",
        min = 0.0, max = 10.0,
        default = 1.0)

    bpy.types.Scene.DazUsePropLimits = BoolProperty(
        name = "DAZ Property Limits",
        description = "Use the minima and maxima from DAZ files if available",
        default = True)

    bpy.types.Scene.DazUsePropDefault = BoolProperty(
        name = "DAZ Property Defaults",
        description = "Use the default values from DAZ files as default slider values.",
        default = True)

    bpy.types.Scene.DazShareThreshold = FloatProperty(
        name = "Sharing Threshold",
        description = "Maximum allowed distance for sharing meshes",
        min = 0.0, max = 0.01,
        precision = 5,
        default = 0.001)

    bpy.types.Scene.DazGroup = StringProperty(
        name = "Group",
        description = "Add/Remove objects to/from this group",
        default = "Group")

    bpy.types.Object.DazId = StringProperty(
        name = "ID",
        default = "")

    bpy.types.Object.DazUrl = StringProperty(
        name = "URL",
        default = "")

    bpy.types.Object.DazRig = StringProperty(
        name = "Rig Type",
        default = "")

    bpy.types.Object.DazMesh = StringProperty(
        name = "Mesh Type",
        default = "")

    bpy.types.Object.DazScale = FloatProperty(
        name = "Unit Scale",
        default = 0.1,
        precision = 3)

    bpy.types.Object.DazCharacterScale = FloatProperty(default = 0.1, precision = 3)

    bpy.types.Object.DazUnits = StringProperty(default = "")
    bpy.types.Object.DazExpressions = StringProperty(default = "")
    bpy.types.Object.DazVisemes = StringProperty(default = "")
    bpy.types.Object.DazCorrectives = StringProperty(default = "")
    bpy.types.Object.DazHands = StringProperty(default = "")

    bpy.types.Object.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.PoseBone.DazRotMode = StringProperty(default = 'XYZ')
    bpy.types.Object.DazOrientation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazOrientation = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazTail = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Object.DazAngle = FloatProperty(default=0)
    bpy.types.Object.DazNormal = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazHead = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazTail = FloatVectorProperty(size=3, default=(0,0,0))
    bpy.types.Bone.DazAngle = FloatProperty(default=0)
    bpy.types.Bone.DazNormal = FloatVectorProperty(size=3, default=(0,0,0))

    bpy.types.Object.DazUseRotLocks = BoolProperty(default = True)
    bpy.types.Object.DazUseLocLocks = BoolProperty(default = True)
    bpy.types.Object.DazUseLimits = BoolProperty(default = False)

    bpy.types.PoseBone.DazRotLocks = BoolVectorProperty(
        name = "Rotation Locks",
        size = 3,
        default = (False,False,False)
    )

    bpy.types.PoseBone.DazLocLocks = BoolVectorProperty(
        name = "Location Locks",
        size = 3,
        default = (False,False,False)
    )

    bpy.types.Object.DazMakeupDrivers = BoolProperty(default = False)
    bpy.types.Object.DazNewStyleExpressions = BoolProperty(default = False)

    bpy.types.Armature.DazExtraFaceBones = BoolProperty(default = False)
    bpy.types.Armature.DazExtraDrivenBones = BoolProperty(default = False)

    bpy.types.Scene.DazShowCorrections = BoolProperty(name = "Corrections", default = False)
    bpy.types.Scene.DazShowMaterials = BoolProperty(name = "Materials", default = False)
    bpy.types.Scene.DazShowMaterialSettings = BoolProperty(name = "Materials", default = False)
    bpy.types.Scene.DazShowMorphs = BoolProperty(name = "Morphs", default = False)
    bpy.types.Scene.DazShowFinish = BoolProperty(name = "Finishing", default = False)
    bpy.types.Scene.DazShowLowpoly = BoolProperty(name = "Low-poly Versions", default = False)
    bpy.types.Scene.DazShowVisibility = BoolProperty(name = "Visibility", default = False)
    bpy.types.Scene.DazShowRigging = BoolProperty(name = "Rigging", default = False)
    bpy.types.Scene.DazShowRiggingSettings = BoolProperty(name = "Rigging", default = False)
    bpy.types.Scene.DazShowMesh = BoolProperty(name = "Mesh", default = False)
    bpy.types.Scene.DazShowAdvancedMorph = BoolProperty(name = "Morphs", default = False)
    bpy.types.Scene.DazShowHair = BoolProperty(name = "Hair", default = False)
    bpy.types.Scene.DazShowGeneral = BoolProperty(name = "General", default = False)
    bpy.types.Scene.DazShowPaths = BoolProperty(name = "Paths To DAZ Library", default = False)
    bpy.types.Scene.DazShowSettings = BoolProperty(name = "Load/Save Settings", default = False)

    bpy.types.Scene.DazDeleteMeta = BoolProperty(
        name = "Delete Metarig",
        description = "Delete intermediate rig after Rigify",
        default = False
    )


classes = [
    DAZ_PT_Setup,
    DAZ_PT_Advanced,
    DAZ_PT_Settings,
    DAZ_PT_Utils,
    DAZ_PT_Addons,
    DAZ_PT_Posing,
    DAZ_PT_Units,
    DAZ_PT_Expressions,
    DAZ_PT_Viseme,
    DAZ_PT_CustomMorphs,
    DAZ_PT_MhxLayers,
    DAZ_PT_MhxFKIK,
    DAZ_PT_MhxProperties,
    DAZ_PT_Visibility,
    DAZ_PT_Makeup,

    ErrorOperator
]

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

    initialize()
    from .fileutils import loadSettingsDefaults
    loadSettingsDefaults()
    for cls in classes:
        bpy.utils.register_class(cls)
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

    for cls in classes:
        bpy.utils.unregister_class(cls)
    if bpy.app.version < (2,80,0):
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
    else:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)



if __name__ == "__main__":
    register()

print("DAZ loaded")
