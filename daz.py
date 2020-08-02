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
import bpy
from bpy.props import *
from .error import *
from .utils import *

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(DazOperator, B.DazImageFile, B.SingleFile, B.DazOptions):
    """Import a DAZ DUF/DSF File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ File"
    bl_description = "Import a native DAZ file (*.duf, *.dsf, *.dse)"
    bl_options = {'PRESET', 'UNDO'}

    def run(self, context):
        from .main import getMainAsset
        getMainAsset(self.filepath, context, self)


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def draw(self, context):
        layout = self.layout
        scn = context.scene
        layout.prop(self, "unitScale")
        layout.separator()

        box = layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)

        layout.separator()
        layout.prop(self, "skinColor")
        layout.prop(self, "clothesColor")
        layout.prop(self, "brightenEyes")
        if scn.render.engine  in ['BLENDER_RENDER', 'BLENDER_GAME']:
            return
        layout.separator()
        layout.prop(self, "useAutoMaterials")
        layout.prop(self, "methodOpaque")
        layout.prop(self, "methodRefractive")
        layout.prop(self, "methodVolumetric")
        layout.prop(self, "useEnvironment")

#-------------------------------------------------------------
#   Silent mode
#-------------------------------------------------------------

class DAZ_OT_SetSilentMode(bpy.types.Operator):
    bl_idname = "daz.set_silent_mode"
    bl_label = "Silent Mode"
    bl_description = "Toggle silent mode on or off (error popups off or on)"

    def execute(self, context):
        from .error import getSilentMode, setSilentMode
        setSilentMode(not getSilentMode())
        return {'FINISHED'}

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

class DazMorphGroup(bpy.types.PropertyGroup, B.DazMorphGroupProps):
    def __repr__(self):
        return "<MorphGroup %d %s %f %f>" % (self.index, self.prop, self.factor, self.default)

    def eval(self, rig):
        if self.simple:
            return self.factor*(rig[self.name]-self.default)
        else:
            value = rig[self.name]-self.default
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


# Old style evalMorphs, for backward compatibility
def evalMorphs(pb, idx, key):
    rig = pb.constraints[0].target
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.factor*(rig[pg.prop]-pg.default) for pg in props if pg.index == idx])


# New style evalMorphs
def evalMorphs2(pb, idx, key):
    rig = pb.constraints[0].target
    pgs = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.eval(rig) for pg in pgs if pg.index == idx])


def hasSelfRef(pb):
    return (pb.constraints and
            pb.constraints[0].name == "Do Not Touch")


def addSelfRef(rig, pb):
    if pb.constraints:
        cns = pb.constraints[0]
        if cns.name == "Do Not Touch":
            return
        else:
            raise DazError("Inconsistent self reference constraint\n for bone '%s'" % pb.name)
    cns = pb.constraints.new('COPY_LOCATION')
    cns.name = "Do Not Touch"
    cns.target = rig
    cns.mute = True


def copyPropGroups(rig1, rig2, pb2):
    if pb2.name not in rig1.pose.bones.keys():
        return
    pb1 = rig1.pose.bones[pb2.name]
    if not (pb1.DazLocProps or pb1.DazRotProps or pb1.DazScaleProps):
        return
    addSelfRef(rig2, pb2)
    for props1,props2 in [
        (pb1.DazLocProps, pb2.DazLocProps),
        (pb1.DazRotProps, pb2.DazRotProps),
        (pb1.DazScaleProps, pb2.DazScaleProps)
        ]:
        for pg1 in props1:
            pg2 = props2.add()
            pg2.name = pg1.name
            pg2.index = pg1.index
            pg2.prop = pg1.prop
            pg2.factor = pg1.factor
            pg2.default = pg1.default


class DAZ_OT_InspectPropGroups(DazOperator, IsArmature):
    bl_idname = "daz.inspect_prop_groups"
    bl_label = "Inspect Prop Groups"
    bl_description = "Show the property groups for the selected posebones."

    def run(self, context):
        rig = context.object
        for pb in rig.pose.bones:
            if pb.bone.select:
                print("\n", pb.name)
                for key,props in [("Loc",pb.DazLocProps),
                                  ("Rot",pb.DazRotProps),
                                  ("Sca",pb.DazScaleProps)
                                  ]:
                    print("  ", key)
                    props = list(props)
                    props.sort()
                    for pg in props:
                        print("    ", pg.display())

#-------------------------------------------------------------
#   Dependencies
#   For debugging
#-------------------------------------------------------------

def clearDependecies():
    global theDependecies
    theDependecies = {}

clearDependecies()


def addDependency(key, prop, factor):
    global theDependecies
    if key not in theDependecies.keys():
        deps = theDependecies[key] = []
    else:
        deps = theDependecies[key]
    deps.append((prop,factor))


class DAZ_OT_InspectPropDependencies(DazOperator, IsArmature):
    bl_idname = "daz.inspect_prop_dependencies"
    bl_label = "Inspect Prop Dependencies"
    bl_description = "List properties depending on other properties"

    def run(self, context):
        global theDependecies
        print("--- Property dependencies from latest load ---")
        deps = list(theDependecies.items())
        deps.sort()
        for key,dep in deps:
            if len(dep) > 0:
                prop,val = dep[0]
                print("  %-24s: %6.4f %-24s" % (key, val, prop))
            for prop,val in dep[1:]:
                print("  %-24s: %6.4f %-24s" % ("", val, prop))

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

class DAZ_PT_Setup(bpy.types.Panel):
    bl_label = "Setup (version 1.5.0)"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"

    def draw(self, context):
        scn = context.scene
        ob = context.object
        layout = self.layout

        layout.operator("daz.import_daz")
        layout.separator()
        layout.operator("daz.global_settings")

        layout.separator()
        box = layout.box()
        if not scn.DazShowCorrections:
            box.prop(scn, "DazShowCorrections", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowCorrections", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.merge_rigs")
            box.operator("daz.eliminate_empties")
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
            box.operator("daz.copy_materials")

            box.separator()
            box.operator("daz.load_uv")
            box.operator("daz.prune_uv_maps")

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
            if ob and ob.DazDriversDisabled:
                box.label(text = "Face drivers disabled")
                box.operator("daz.enable_drivers")
            elif ob and ob.type in ['ARMATURE', 'MESH']:
                if ob.DazMorphPrefixes:
                    box.operator("daz.update_morphs")
                    return
                box.operator("daz.import_units")
                box.operator("daz.import_expressions")
                box.operator("daz.import_visemes")
                box.operator("daz.import_body_morphs")
                box.operator("daz.import_custom_morphs")
                box.separator()
                box.operator("daz.import_standard_jcms")
                box.operator("daz.import_custom_jcms")
                box.operator("daz.import_flexions")
                box.label(text="Create low-poly meshes before transfers.")
                box.operator("daz.transfer_jcms")
                box.operator("daz.transfer_other_morphs")
                box.separator()
                box.operator("daz.mix_shapekeys")

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
    bl_category = "DAZ Importer"
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
            box.operator("daz.create_masks")
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
            box.operator("daz.limit_vertex_groups")
            box.operator("daz.apply_subsurf")
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

        layout.separator()
        box = layout.box()
        if not scn.DazShowAdvancedMorph:
            box.prop(scn, "DazShowAdvancedMorph", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowAdvancedMorph", icon="DOWNARROW_HLT", emboss=False)
            box.operator("daz.remove_standard_morphs")
            box.operator("daz.remove_custom_morphs")
            box.operator("daz.remove_jcms")
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
            box.operator("daz.remove_all_shapekey_drivers")
            box.separator()
            box.operator("daz.copy_props")
            box.operator("daz.copy_bone_drivers")
            box.operator("daz.retarget_mesh_drivers")
            box.separator()
            box.operator("daz.update_prop_limits")
            box.separator()
            box.operator("daz.create_graft_groups")
            box.separator()
            box.operator("daz.import_dbz")

        layout.separator()
        box = layout.box()
        if not scn.DazShowHair:
            box.prop(scn, "DazShowHair", icon="RIGHTARROW", emboss=False)
        else:
            box.prop(scn, "DazShowHair", icon="DOWNARROW_HLT", emboss=False)
            from .hair import getHairAndHuman
            box.operator("daz.select_random_strands")
            box.separator()
            box.operator("daz.make_hair")
            hair,hum = getHairAndHuman(context, False)
            box.label(text = "  Hair:  %s" % (hair.name if hair else None))
            box.label(text = "  Human: %s" % (hum.name if hum else None))
            box.separator()
            box.operator("daz.update_hair")
            box.operator("daz.color_hair")
            #box.operator("daz.connect_hair")


class DAZ_PT_Utils(bpy.types.Panel):
    bl_label = "Utilities"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        layout = self.layout
        layout.operator("daz.decode_file")
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
        layout.separator()
        layout.operator("daz.list_bones")
        layout.operator("daz.get_finger_print")
        layout.separator()
        layout.operator("daz.inspect_prop_groups")
        layout.operator("daz.inspect_prop_dependencies")


class DAZ_PT_Addons(bpy.types.Panel):
    bl_label = "Add-Ons"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
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
                        split = splitLayout(box, 0.2)
                        split.label(text=key.capitalize()+":")
                        split.label(text=str(bl_info[key]))
                split = splitLayout(box, 0.2)
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
    bl_category = "DAZ Importer"
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
        split = splitLayout(layout, 0.6)
        layout.operator("daz.toggle_loc_locks", text = "Location Locks Are " + ("ON" if ob.DazUseLocLocks else "OFF"))
        layout.operator("daz.toggle_rot_locks", text = "Rotation Locks Are " + ("ON" if ob.DazUseRotLocks else "OFF"))
        layout.operator("daz.toggle_limits", text = "Limits Are " + ("ON" if ob.DazUseLimits else "OFF"))

        layout.separator()
        layout.operator("daz.rotate_bones")

        return

        layout.separator()
        layout.operator("daz.save_current_pose")
        layout.operator("daz.load_pose")


def activateLayout(layout, rig, self):
    split = splitLayout(layout, 0.25)
    split.operator("daz.prettify")
    op = split.operator("daz.activate_all")
    op.morphset = self.morphset
    op = split.operator("daz.deactivate_all")
    op.morphset = self.morphset
    if rig.DazDriversDisabled:
        split.operator("daz.enable_drivers")
    else:
        split.operator("daz.disable_drivers")


def keyLayout(layout, self):
    split = splitLayout(layout, 0.25)
    op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
    op.morphset = self.morphset
    op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
    op.morphset = self.morphset
    op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
    op.morphset = self.morphset
    op = split.operator("daz.clear_morphs", text="", icon='X')
    op.morphset = self.morphset


class DAZ_PT_Morphs:

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob and ob.DazMesh:
            if ob.type == 'MESH' and ob.parent:
                ob = ob.parent
            return getattr(ob, "Daz"+self.morphset)
        return False


    def draw(self, context):
        rig = context.object
        if rig.type == 'MESH':
            rig = rig.parent
        if rig is None:
            return
        if rig.type != 'ARMATURE':
            return
        layout = self.layout

        if rig.DazDriversDisabled:
            layout.label(text = "Face drivers disabled")
            layout.operator("daz.enable_drivers")
            return

        scn = context.scene
        activateLayout(layout, rig, self)
        keyLayout(layout, self)
        layout.prop(scn, "DazFilter", icon='VIEWZOOM', text="")
        self.drawItems(scn, rig)


    def drawItems(self, scn, rig):
        self.layout.separator()
        filter = scn.DazFilter.lower()
        pg = getattr(rig, "Daz"+self.morphset)
        for item in pg.values():
            if filter in item.text.lower():
                self.displayProp(item.text, item.name, rig, self.layout, scn)


    def displayProp(self, name, key, rig, layout, scn):
        if key not in rig.keys():
            return
        row = splitLayout(layout, 0.8)
        row.prop(rig, '["%s"]' % key, text=name)
        showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset = self.morphset


def showBool(layout, ob, key, text=""):
    from .morphing import getExistingActivateGroup
    pg = getExistingActivateGroup(ob, key)
    if pg is not None:
        layout.prop(pg, "active", text=text)


class DAZ_PT_Units(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Face Units"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Units"


class DAZ_PT_Expressions(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Expressions"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Expressions"


class DAZ_PT_Visemes(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Visemes"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Visemes"

    def draw(self, context):
        self.layout.operator("daz.load_moho")
        DAZ_PT_Morphs.draw(self, context)


class DAZ_PT_BodyMorphs(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Body Morphs"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Body"

#------------------------------------------------------------------------
#    Custom panels
#------------------------------------------------------------------------

class DAZ_PT_CustomMorphs(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Custom Morphs"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Custom"

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob and ob.DazMesh:
            if ob.type == 'MESH' and ob.parent:
                ob = ob.parent
            return ob.DazCustomMorphs
        return False


    def drawItems(self, scn, rig):
        row = self.layout.row()
        row.operator("daz.toggle_all_cats", text="Open All Categories").useOpen=True
        row.operator("daz.toggle_all_cats", text="Close All Categories").useOpen=False
        self.layout.separator()
        filter = scn.DazFilter.lower()

        for cat in rig.DazMorphCats:
            self.layout.separator()
            box = self.layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name, icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name, icon="DOWNARROW_HLT", emboss=False)
            for morph in cat.morphs:
                if (morph.name in rig.keys() and
                    filter in morph.text.lower()):
                    self.displayProp(morph.text, morph.name, rig, box, scn)

#------------------------------------------------------------------------
#    Mhx Layers Panel
#------------------------------------------------------------------------

class DAZ_PT_MhxLayers(bpy.types.Panel):
    bl_label = "MHX Layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
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
    bl_category = "DAZ Importer"
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
    bl_category = "DAZ Importer"
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
#   Visibility panels
#------------------------------------------------------------------------

class DAZ_PT_Hide:
    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
        split = splitLayout(layout, 0.3333)
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
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    prefix = "Mhh"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityDrivers)

#-------------------------------------------------------------
#   Settings popup
#-------------------------------------------------------------

class DAZ_OT_SaveSettingsFile(DazOperator, B.SingleFile, B.JsonExportFile):
    bl_idname = "daz.save_settings_file"
    bl_label = "Save Settings File"
    bl_description = "Save current settings to file"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.fromScene(context.scene)
        GS.save(self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(GS.settingsPath)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAZ_OT_LoadFactorySettings(DazOperator):
    bl_idname = "daz.load_factory_settings"
    bl_label = "Load Factory Settings"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.__init__()
        GS.toScene(context.scene)
        return {'PASS_THROUGH'}


class DAZ_OT_LoadSettingsFile(DazOperator, B.SingleFile, B.JsonFile):
    bl_idname = "daz.load_settings_file"
    bl_label = "Load Settings File"
    bl_description = "Load settings from file"
    bl_options = {'UNDO'}

    def execute(self, context):
        GS.load(self.filepath)
        GS.toScene(context.scene)
        print("Settings file %s saved" % self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(GS.settingsPath)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAZ_OT_GlobalSettings(DazOperator):
    bl_idname = "daz.global_settings"
    bl_label = "Global Settings"
    bl_description = "Show or update global settings"

    def draw(self, context):
        scn = context.scene
        split = splitLayout(self.layout, 0.4)
        col = split.column()
        box = col.box()
        box.label(text = "DAZ Root Paths")
        box.prop(scn, "DazCaseSensitivePaths")
        box.prop(scn, "DazNumPaths")
        for n in range(scn.DazNumPaths):
            box.prop(scn, "DazPath%d" % (n+1), text="")
        box.label(text = "Path To Output Errors:")
        box.prop(scn, "DazErrorPath", text="")

        col = split.column()
        box = col.box()
        box.label(text = "General")
        box.prop(scn, "DazVerbosity")
        box.prop(scn, "DazZup")
        from .error import getSilentMode
        if getSilentMode():
            box.operator("daz.set_silent_mode", text="Silent Mode ON")
        else:
            box.operator("daz.set_silent_mode", text="Silent Mode OFF")
        box.separator()
        box.prop(scn, "DazPropMin")
        box.prop(scn, "DazPropMax")
        box.prop(scn, "DazUsePropLimits")
        box.prop(scn, "DazUsePropDefault")

        col = split.column()
        box = col.box()
        box.label(text = "Rigging")
        box.prop(scn, "DazAddFaceDrivers")
        box.prop(scn, "DazBuildHighdef")
        box.prop(scn, "DazUseLockRot")
        box.prop(scn, "DazUseLockLoc")
        box.prop(scn, "DazBones")
        box.prop(scn, "DazOrientation")

        box = split.box()
        box.label(text = "Materials")
        box.prop(scn, "DazChooseColors")
        box.prop(scn, "DazMergeShells")
        box.prop(scn, "DazLimitBump")
        if scn.DazLimitBump:
            box.prop(scn, "DazMaxBump")
        box.prop(scn, "DazHandleRenderSettings")
        box.prop(scn, "DazHandleLightSettings")
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

        row = self.layout.row()
        row.operator("daz.load_factory_settings")
        row.operator("daz.save_settings_file")
        row.operator("daz.load_settings_file")


    def run(self, context):
        GS.fromScene(context.scene)
        GS.saveDefaults()


    def invoke(self, context, event):
        GS.toScene(context.scene)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=900)

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

from bpy.app.handlers import persistent

@persistent
def updateHandler(scn):
    global evalMorphs, evalMorphs2
    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.driver_namespace["evalMorphs2"] = evalMorphs2


classes = [
    ImportDAZ,
    DazMorphGroup,
    B.DazStringGroup,
    DAZ_OT_InspectPropGroups,
    DAZ_OT_InspectPropDependencies,
    DAZ_OT_SetSilentMode,

    DAZ_OT_LoadFactorySettings,
    DAZ_OT_SaveSettingsFile,
    DAZ_OT_LoadSettingsFile,
    DAZ_OT_GlobalSettings,

    DAZ_PT_Setup,
    DAZ_PT_Advanced,
    DAZ_PT_Utils,
    DAZ_PT_Addons,
    DAZ_PT_Posing,
    DAZ_PT_Units,
    DAZ_PT_Expressions,
    DAZ_PT_Visemes,
    DAZ_PT_BodyMorphs,
    DAZ_PT_CustomMorphs,
    DAZ_PT_MhxLayers,
    DAZ_PT_MhxFKIK,
    DAZ_PT_MhxProperties,
    DAZ_PT_Visibility,

    ErrorOperator
]

def initialize():
    bpy.types.Scene.DazNumPaths = IntProperty(
        name = "Number Of DAZ Paths",
        description = "The number of DAZ library paths",
        min=1, max = 9)

    for n in range(1, 10):
        setattr(bpy.types.Scene, "DazPath%d" % n,
            StringProperty(
                name = "DAZ Path %d" % n,
                description = "Search path for DAZ Studio assets"))

    bpy.types.Scene.DazErrorPath = StringProperty(
        name = "Error Path",
        description = "Path to error report file")

    bpy.types.Scene.DazVerbosity = IntProperty(
        name = "Verbosity",
        description = "Controls the number of warning messages when loading files",
        min=1, max = 5)

    bpy.types.Scene.DazPropMin = FloatProperty(
        name = "Property Minima",
        description = "Minimum value of properties",
        min = -10.0, max = 0.0)

    bpy.types.Scene.DazPropMax = FloatProperty(
        name = "Property Maxima",
        description = "Maximum value of properties",
        min = 0.0, max = 10.0)

    bpy.types.Scene.DazUsePropLimits = BoolProperty(
        name = "DAZ Property Limits",
        description = "Use the minima and maxima from DAZ files if available")

    bpy.types.Scene.DazUsePropDefault = BoolProperty(
        name = "DAZ Property Defaults",
        description = "Use the default values from DAZ files as default slider values.")

    bpy.types.Scene.DazBones = BoolProperty(
        name = "Daz Bones",
        description = "Match bones exactly with Daz Studio",
        default = False)

    bpy.types.Scene.DazOrientation = BoolProperty(
        name = "Daz Orientation",
        description = "Orient bones as in Daz Studio",
        default = False)


    # Object properties

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
    bpy.types.Object.DazBodies = StringProperty(default = "")
    bpy.types.Object.DazFlexions = StringProperty(default = "")
    bpy.types.Object.DazCorrectives = StringProperty(default = "")

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

    bpy.types.Scene.DazFilter = StringProperty(
        name = "Filter",
        description = "Filter string",
        default = ""
    )
    bpy.types.Scene.DazChooseColors = EnumProperty(
        items = [('WHITE', "White", "Default diffuse color"),
                 ('RANDOM', "Random", "Random colors for each object"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Color Choice",
        description = "Method to use object colors")

    bpy.types.Scene.DazUseLockRot = BoolProperty(
        name = "Rotation Locks",
        description = "Use rotation locks")

    bpy.types.Scene.DazUseLockLoc = BoolProperty(
        name = "Location Locks",
        description = "Use location locks")

    bpy.types.Scene.DazZup = BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention",
        default = True)

    bpy.types.Scene.DazOrientation = BoolProperty(
        name = "DAZ Orientation",
        description = "Treat bones as nodes with same orientation as in Daz Studio",
        default = False)

    bpy.types.Scene.DazCaseSensitivePaths = BoolProperty(
        name = "Case-Sensitive Paths",
        description = "Convert URLs to lowercase. Works best on Windows.")

    bpy.types.Scene.DazAddFaceDrivers = BoolProperty(
        name = "Add Face Drivers",
        description = "Add drivers to facial morphs. Only for Genesis 1 and 2.")

    bpy.types.Scene.DazBuildHighdef = BoolProperty(
        name = "Build HD Meshes",
        description = "Build HD meshes if included in .dbz file")

    bpy.types.Scene.DazMergeShells = BoolProperty(
        name = "Merge Shells",
        description = "Merge shell materials with object materials")

    bpy.types.Scene.DazMaxBump = FloatProperty(
        name = "Max Bump Strength",
        description = "Max bump strength",
        min = 0.1, max = 10)

    bpy.types.Scene.DazLimitBump = BoolProperty(
        name = "Limit Bump Strength",
        description = "Limit the bump strength")

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name = "Displacement",
        description = "Use displacement maps. Affects internal renderer only")

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name = "Emission",
        description = "Use emission.")

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name = "Reflection",
        description = "Use reflection maps. Affects internal renderer only")

    bpy.types.Scene.DazDiffuseRoughness = FloatProperty(
        name = "Diffuse Roughness",
        description = "Default diffuse roughness",
        min = 0, max = 1.0)

    bpy.types.Scene.DazSpecularRoughness = FloatProperty(
        name = "Specular Roughness",
        description = "Default specular roughness",
        min = 0, max = 1.0)

    bpy.types.Scene.DazDiffuseShader = EnumProperty(
        items = [
            ('FRESNEL', "Fresnel", ""),
            ('MINNAERT', "Minnaert", ""),
            ('TOON', "Toon", ""),
            ('OREN_NAYAR', "Oren-Nayar", ""),
            ('LAMBERT', "Lambert", "")
        ],
        name = "Diffuse Shader",
        description = "Diffuse shader (Blender Internal)")

    bpy.types.Scene.DazSpecularShader = EnumProperty(
        items = [
            ('WARDISO', "WardIso", ""),
            ('TOON', "Toon", ""),
            ('BLINN', "Blinn", ""),
            ('PHONG', "Phong", ""),
            ('COOKTORR', "CookTorr", "")
        ],
        name = "Specular Shader",
        description = "Specular shader (Blender Internal)")

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')
    bpy.types.Material.DazThinGlass = BoolProperty(default=False)

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.PoseBone.DazLocProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazRotProps = CollectionProperty(type = DazMorphGroup)
    bpy.types.PoseBone.DazScaleProps = CollectionProperty(type = DazMorphGroup)

    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.driver_namespace["evalMorphs2"] = evalMorphs2
    bpy.app.handlers.load_post.append(updateHandler)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

