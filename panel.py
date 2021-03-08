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
from .buildnumber import BUILD

UseAddonUpdater = (bpy.app.version < (2,93,0))
#UseAddonUpdater = False

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

def showBox(scn, attr, layout):
    if not getattr(scn, attr):
        layout.prop(scn, attr, icon="RIGHTARROW", emboss=False)
        return False
    else:
        layout.prop(scn, attr, icon="DOWNARROW_HLT", emboss=False)
        return True


class DAZ_PT_Setup(bpy.types.Panel):
    bl_label = "Setup (version 1.6.0.%04d)" % BUILD
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"

    def draw(self, context):
        scn = context.scene
        ob = context.object
        layout = self.layout

        if UseAddonUpdater:
            from .updater import drawUpdateButton
            drawUpdateButton(self, context)

        layout.operator("daz.import_daz")
        layout.separator()
        layout.operator("daz.global_settings")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowCorrections", box):
            box.operator("daz.merge_rigs")
            box.operator("daz.apply_rest_pose")
            box.operator("daz.eliminate_empties")
            box.operator("daz.merge_toes")
            box.operator("daz.add_extra_face_bones")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowMaterials", box):
            box.operator("daz.update_settings")
            box.operator("daz.save_local_textures")
            box.operator("daz.resize_textures")
            box.operator("daz.change_resolution")

            box.separator()
            box.operator("daz.change_colors")
            box.operator("daz.change_skin_color")
            box.operator("daz.merge_materials")
            box.operator("daz.copy_materials")
            box.operator("daz.prune_node_trees")

            box.separator()
            box.operator("daz.launch_editor")
            box.operator("daz.reset_material")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowMorphs", box):
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
                box.operator("daz.import_facs")
                box.operator("daz.import_facs_expressions")
                box.operator("daz.import_body_morphs")
                box.separator()
                box.operator("daz.import_jcms")
                box.operator("daz.import_flexions")
                box.separator()
                box.operator("daz.import_custom_morphs")
                box.separator()
                box.label(text="Create low-poly meshes before transfers.")
                box.operator("daz.transfer_jcms")
                box.operator("daz.transfer_other_morphs")
                box.operator("daz.add_shrinkwrap")
                box.separator()
                box.operator("daz.mix_shapekeys")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowFinish", box):
            if bpy.app.version >= (2,82,0):
                box.operator("daz.set_udims")
            box.operator("daz.merge_geografts")
            if bpy.app.version >= (2,82,0):
                box.operator("daz.make_udim_materials")
            box.operator("daz.merge_uv_layers")
            box.separator()
            box.operator("daz.make_all_bones_posable")
            box.operator("daz.optimize_pose")
            box.operator("daz.apply_rest_pose")
            box.operator("daz.connect_ik_chains")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowRigging", box):
            box.operator("daz.add_custom_shapes")
            box.operator("daz.add_simple_ik")
            box.separator()
            box.operator("daz.convert_mhx")
            box.separator()
            box.operator("daz.rigify_daz")
            box.operator("daz.create_meta")
            box.operator("daz.rigify_meta")
            box.separator()
            box.operator("daz.add_mannequin")


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
        if showBox(scn, "DazShowLowpoly", box):
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
            box.operator("daz.make_deflection")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowVisibility", box):
            box.operator("daz.add_shrinkwrap")
            box.operator("daz.create_masks")
            box.operator("daz.add_visibility_drivers")
            box.operator("daz.remove_visibility_drivers")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowMaterials2", box):
            if bpy.app.version >= (2,82,0):
                box.operator("daz.bake_maps")
                box.operator("daz.load_baked_maps")
            box.operator("daz.load_vector_disp")
            box.operator("daz.load_normal_map")
            box.operator("daz.add_driven_value_nodes")
            box.separator()
            box.operator("daz.load_uv")
            box.operator("daz.prune_uv_maps")
            box.separator()
            box.operator("daz.collapse_udims")
            box.operator("daz.restore_udims")
            box.operator("daz.udims_from_textures")
            box.separator()
            box.operator("daz.remove_shells")
            box.operator("daz.replace_shells")
            box.separator()
            box.operator("daz.make_decal")


        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowMesh", box):
            box.operator("daz.limit_vertex_groups")
            box.operator("daz.prune_vertex_groups")
            box.operator("daz.transfer_vertex_groups")
            #box.operator("daz.copy_vertex_groups_by_number")
            box.operator("daz.apply_subsurf")
            box.operator("daz.find_seams")
            box.operator("daz.get_finger_print")
            box.operator("daz.mesh_add_pinning")
            if bpy.app.version >= (2,90,0):
                box.operator("daz.make_multires")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowRigging2", box):
            box.operator("daz.remove_custom_shapes")
            box.separator()
            box.operator("daz.convert_rig")
            box.operator("daz.apply_rest_pose")
            box.operator("daz.copy_bones")
            box.operator("daz.copy_poses")
            box.separator()
            box.operator("daz.add_ik_goals")
            box.operator("daz.add_winder")
            if bpy.app.version < (2,80,0):
                box.separator()
                box.operator("daz.add_to_group")
                box.operator("daz.remove_from_groups")
            box.separator()
            box.operator("daz.update_rig_version")
            box.operator("daz.convert_mhx_actions")
            box.operator("daz.copy_daz_props")

        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowMorphs2", box):
            box.operator("daz.remove_standard_morphs")
            box.operator("daz.remove_custom_morphs")
            box.operator("daz.remove_jcms")
            box.separator()
            box.operator("daz.add_shape_to_category")
            box.operator("daz.remove_shape_from_category")
            box.operator("daz.rename_category")
            box.operator("daz.remove_categories")
            box.separator()
            box.operator("daz.convert_standard_morphs_to_shapekeys")
            box.operator("daz.convert_custom_morphs_to_shapekeys")
            box.operator("daz.transfer_mesh_to_shape")
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
            box.operator("daz.update_slider_limits")
            box.separator()
            box.operator("daz.create_graft_groups")
            box.separator()
            box.operator("daz.import_dbz")
            box.separator()
            box.operator("daz.update_morphs")
            box.operator("daz.update_morph_paths")


        layout.separator()
        box = layout.box()
        if showBox(scn, "DazShowHair", box):
            from .hair import getHairAndHuman
            box.operator("daz.print_statistics")
            box.operator("daz.select_strands_by_size")
            box.operator("daz.select_strands_by_width")
            box.operator("daz.select_random_strands")
            box.separator()
            box.operator("daz.make_hair")
            hair,hum = getHairAndHuman(context, False)
            box.label(text = "  Hair:  %s" % (hair.name if hair else None))
            box.label(text = "  Human: %s" % (hum.name if hum else None))
            box.separator()
            box.operator("daz.update_hair")
            box.operator("daz.color_hair")
            box.operator("daz.combine_hairs")


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
        layout.operator("daz.print_statistics")
        layout.operator("daz.update_all")
        layout.separator()
        box = layout.box()
        if ob:
            box.label(text = "Active Object: %s" % ob.type)
            box.prop(ob, "name")
            box.prop(ob, "DazId")
            box.prop(ob, "DazUrl")
            box.prop(ob, "DazScene")
            box.prop(ob, "DazRig")
            box.prop(ob, "DazMesh")
            box.prop(ob, "DazOrientMethod")
            box.prop(ob, "DazScale")
            factor = 1/ob.DazScale
        else:
            box.label(text = "No active object")
            factor = 1
        layout.separator()
        pb = context.active_pose_bone
        box = layout.box()
        if pb:
            box.label(text = "Active Bone: %s" % pb.bone.name)
            self.propRow(box, pb.bone, "DazHead")
            self.propRow(box, pb.bone, "DazTail")
            self.propRow(box, pb.bone, "DazOrient")
            self.propRow(box, pb, "DazRotMode")
            self.propRow(box, pb, "DazLocLocks")
            self.propRow(box, pb, "DazRotLocks")
            mat = ob.matrix_world @ pb.matrix
            loc,quat,scale = mat.decompose()
            self.vecRow(box, factor*loc, "Location")
            self.vecRow(box, Vector(quat.to_euler())/D, "Rotation")
            self.vecRow(box, scale, "Scale")
        else:
            box.label(text = "No active bone")

        layout.separator()
        from .error import getSilentMode
        if getSilentMode():
            layout.operator("daz.set_silent_mode", text="Silent Mode ON")
        else:
            layout.operator("daz.set_silent_mode", text="Silent Mode OFF")
        layout.operator("daz.get_finger_print")
        layout.operator("daz.inspect_prop_groups")
        layout.operator("daz.inspect_prop_dependencies")
        layout.operator("daz.inspect_world_matrix")

    def propRow(self, layout, rna, prop):
        row = layout.row()
        row.label(text=prop[3:])
        attr = getattr(rna, prop)
        for n in range(3):
            if isinstance(attr[n], float):
                row.label(text = "%.3f" % attr[n])
            else:
                row.label(text = str(attr[n]))

    def vecRow(self, layout, vec, text):
        row = layout.row()
        row.label(text=text)
        for n in range(3):
            row.label(text = "%.3f" % vec[n])


class DAZ_PT_Posing(bpy.types.Panel):
    bl_label = "Posing"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type == 'ARMATURE')

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout

        layout.operator("daz.import_pose")
        layout.operator("daz.import_poselib")
        layout.operator("daz.import_action")
        layout.separator()
        layout.operator("daz.import_node_pose")
        layout.separator()
        layout.operator("daz.clear_pose")
        op = layout.operator("daz.clear_morphs")
        op.morphset = "All"
        op.category = ""
        layout.separator()
        layout.operator("daz.prune_action")
        layout.operator("daz.rotate_bones")

        layout.separator()
        split = layout.split(factor=0.6)
        icon = 'CHECKBOX_HLT' if ob.DazLocLocks else 'CHECKBOX_DEHLT'
        layout.operator("daz.toggle_loc_locks", icon=icon, emboss=False)
        icon = 'CHECKBOX_HLT' if ob.DazRotLocks else 'CHECKBOX_DEHLT'
        layout.operator("daz.toggle_rot_locks", icon=icon, emboss=False)
        icon = 'CHECKBOX_HLT' if ob.DazLocLimits else 'CHECKBOX_DEHLT'
        layout.operator("daz.toggle_loc_limits", icon=icon, emboss=False)
        icon = 'CHECKBOX_HLT' if ob.DazRotLimits else 'CHECKBOX_DEHLT'
        layout.operator("daz.toggle_rot_limits", icon=icon, emboss=False)

        return
        layout.separator()
        layout.operator("daz.save_current_frame")
        layout.operator("daz.restore_current_frame")
        layout.separator()
        layout.operator("daz.save_current_pose")
        layout.operator("daz.load_pose")


class DAZ_PT_Morphs:
    useMesh = False

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob and ob.DazMesh:
            if ob.type == 'MESH' and ob.parent:
                ob = ob.parent
            return getattr(ob, "Daz"+self.morphset)
        return False


    def getCurrentRig(self, context):
        rig = context.object
        if rig.type == 'MESH':
            rig = rig.parent
        if rig and rig.type == 'ARMATURE':
            return rig
        else:
            return None


    def draw(self, context):
        rig = self.getCurrentRig(context)
        if not rig:
            return
        layout = self.layout

        if rig.DazDriversDisabled:
            layout.label(text = "Face drivers disabled")
            layout.operator("daz.enable_drivers")
            return

        scn = context.scene
        self.preamble(layout, rig)
        layout.prop(scn, "DazFilter", icon='VIEWZOOM', text="")
        self.drawItems(scn, rig)


    def preamble(self, layout, rig):
        split = layout.split(factor=0.25)
        split.operator("daz.prettify")
        self.activateLayout(split, "", rig)
        split.operator("daz.disable_drivers")
        self.keyLayout(layout, "")


    def activateLayout(self, layout, category, rig):
        op = layout.operator("daz.activate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op = layout.operator("daz.deactivate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh


    def keyLayout(self, layout, category):
        split = layout.split(factor=0.25)
        op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.clear_morphs", text="", icon='X')
        op.morphset = self.morphset
        op.category = category


    def drawItems(self, scn, rig):
        self.layout.separator()
        filter = scn.DazFilter.lower()
        pg = getattr(rig, "Daz"+self.morphset)
        items = [(data[1].text, n, data[1]) for n,data in enumerate(pg.items())]
        items.sort()
        for _,_,item in items:
            if filter in item.text.lower():
                self.displayProp(item, "", rig, self.layout, scn)


    def showBool(self, layout, ob, key, text=""):
        from .morphing import getExistingActivateGroup
        pg = getExistingActivateGroup(ob, key)
        if pg is not None:
            layout.prop(pg, "active", text=text)


    def displayProp(self, morph, category, rig, layout, scn):
        key = morph.name
        if key not in rig.keys():
            return
        split = layout.split(factor=0.85)
        split2 = split.split(factor=0.8)
        split2.prop(rig, propRef(key), text=morph.text)
        split2.label(text = "%.3f" %rig[finalProp(key)])
        row = split.row()
        self.showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset = self.morphset
        op.category = category


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


class DAZ_PT_FacsUnits(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Units"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Facs"

    def preamble(self, layout, rig):
        if bpy.app.version >= (2,80,0):
            layout.operator("daz.import_facecap")
            layout.operator("daz.import_livelink")
        DAZ_PT_Morphs.preamble(self, layout, rig)


class DAZ_PT_FacsExpressions(bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Expressions"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Facsexpr"


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

class CustomDrawItems:
    def drawItems(self, scn, ob):
        row = self.layout.row()
        op = row.operator("daz.toggle_all_cats", text="Open All Categories")
        op.useOpen = True
        op.useMesh = self.useMesh
        op = row.operator("daz.toggle_all_cats", text="Close All Categories")
        op.useOpen = False
        op.useMesh = self.useMesh
        self.layout.separator()
        filter = scn.DazFilter.lower()

        for cat in ob.DazMorphCats:
            self.layout.separator()
            box = self.layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name, icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name, icon="DOWNARROW_HLT", emboss=False)
            self.drawBox(box, cat, scn, ob, filter)


class DAZ_PT_CustomMorphs(bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Custom Morphs"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Custom"

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob:
            if ob.type == 'MESH' and ob.parent:
                ob = ob.parent
            return ob.DazCustomMorphs
        return False

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob


    def drawBox(self, box, cat, scn, ob, filter):
        split = box.split(factor=0.5)
        self.activateLayout(split, cat.name, ob)
        self.keyLayout(box, cat.name)
        for morph in cat.morphs:
            if (morph.name in ob.keys() and
                filter in morph.text.lower()):
                self.displayProp(morph, cat.name, ob, box, scn)


class DAZ_PT_CustomMeshMorphs(bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Mesh Shape Keys"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    morphset = "Custom"
    useMesh = True

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.DazMeshMorphs)


    def preamble(self, layout, ob):
        split = layout.split(factor=0.333)
        split.operator("daz.prettify")
        self.activateLayout(split, "", ob)
        self.keyLayout(layout, "")


    def getCurrentRig(self, context):
        return context.object

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob.data.shape_keys


    def keyLayout(self, layout, category):
        split = layout.split(factor=0.333)
        op = split.operator("daz.key_shapes", text="", icon='KEY_HLT')
        op.category = category
        op = split.operator("daz.unkey_shapes", text="", icon='KEY_DEHLT')
        op.category = category
        op = split.operator("daz.clear_shapes", text="", icon='X')
        op.category = category


    def drawBox(self, box, cat, scn, ob, filter):
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        split = box.split(factor=0.5)
        self.activateLayout(split, cat.name, ob)
        self.keyLayout(box, cat.name)
        for morph in cat.morphs:
            if (morph.name in skeys.key_blocks.keys() and
                filter in morph.text.lower()):
                skey = skeys.key_blocks[morph.name]
                self.displayProp(morph, cat.name, ob, skey, box, scn)


    def displayProp(self, morph, category, ob, skey, layout, scn):
        key = morph.name
        row = layout.split(factor=0.8)
        row.prop(skey, "value", text=morph.text)
        self.showBool(row, ob, key)
        op = row.operator("daz.pin_shape", icon='UNPINNED')
        op.key = key
        op.category = category

#------------------------------------------------------------------------
#    Simple IK Panel
#------------------------------------------------------------------------

class DAZ_PT_SimpleRig(bpy.types.Panel):
    bl_label = "Simple Rig"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazCustomShapes)

    def draw(self, context):
        rig = context.object
        self.drawLayers(rig)
        if rig.DazSimpleIK:
            self.drawSimpleIK(rig)


    def drawSimpleIK(self, rig):
        layout = self.layout
        layout.separator()
        layout.label(text="IK Influence")
        split = layout.split(factor=0.2)
        split.label(text="")
        split.label(text="Left")
        split.label(text="Right")
        split = layout.split(factor=0.2)
        split.label(text="Arm")
        split.prop(rig, "DazArmIK_L", text="")
        split.prop(rig, "DazArmIK_R", text="")
        split = layout.split(factor=0.2)
        split.label(text="Leg")
        split.prop(rig, "DazLegIK_L", text="")
        split.prop(rig, "DazLegIK_R", text="")

        layout.label(text="Snap FK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op = row.operator("daz.snap_simple_fk", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op = row.operator("daz.snap_simple_fk", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"

        layout.label(text="Snap IK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op = row.operator("daz.snap_simple_ik", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op = row.operator("daz.snap_simple_ik", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"


    def drawLayers(self, rig):
        from .figure import BoneLayers
        layout = self.layout
        layout.label(text="Layers")
        row = layout.row()
        row.operator("daz.select_named_layers")
        row.operator("daz.unselect_named_layers")
        layout.separator()
        for lnames in [("Spine", "Face"), "FK Arm", "IK Arm", "FK Leg", "IK Leg", "Hand", "Foot"]:
            row = layout.row()
            if isinstance(lnames, str):
                first,second = "Left "+lnames, "Right "+lnames
            else:
                first,second = lnames
            m = BoneLayers[first]
            n = BoneLayers[second]
            row.prop(rig.data, "layers", index=m, toggle=True, text=first)
            row.prop(rig.data, "layers", index=n, toggle=True, text=second)

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

        layout.separator()
        icon = 'CHECKBOX_HLT' if rig.MhaHintsOn else 'CHECKBOX_DEHLT'
        layout.operator("daz.toggle_hints", icon=icon, emboss=False)


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
        layout.operator("daz.reinit_mhx_props")
        if "MhaGazeFollowsHead" not in ob.keys():
            return
        layout.separator()
        layout.prop(ob, "MhaGazeFollowsHead", text="Gaze Follows Head")
        row = layout.row()
        row.label(text = "Left")
        row.label(text = "Right")
        props = [key for key in ob.keys() if key[0:3] == "Mha" and key[-1] in ["L", "R"]]
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

class DAZ_PT_Visibility(bpy.types.Panel):
    bl_label = "Visibility"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

    prefix = "Mhh"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.DazVisibilityDrivers)

    def draw(self, context):
        ob = rig = context.object
        scn = context.scene
        if ob.type == 'MESH':
            self.layout.operator("daz.set_shell_visibility")
            self.layout.separator()
            if ob.parent and ob.parent.type == 'ARMATURE':
                rig = ob.parent
            else:
                return
        split = self.layout.split(factor=0.3333)
        split.operator("daz.prettify")
        split.operator("daz.show_all_vis")
        split.operator("daz.hide_all_vis")
        props = list(rig.keys())
        props.sort()
        self.drawProps(rig, props, "Mhh")
        self.drawProps(rig, props, "DzS")

    def drawProps(self, rig, props, prefix):
        for prop in props:
            if prop[0:3] == prefix:
                icon = 'CHECKBOX_HLT' if rig[prop] else 'CHECKBOX_DEHLT'
                op = self.layout.operator("daz.toggle_vis", text=prop[3:], icon=icon, emboss=False)
                op.name = prop

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_Setup,
    DAZ_PT_Advanced,
    DAZ_PT_Utils,
    DAZ_PT_Posing,
    DAZ_PT_Units,
    DAZ_PT_Expressions,
    DAZ_PT_Visemes,
    DAZ_PT_FacsUnits,
    DAZ_PT_FacsExpressions,
    DAZ_PT_BodyMorphs,
    DAZ_PT_CustomMorphs,
    DAZ_PT_CustomMeshMorphs,
    DAZ_PT_SimpleRig,
    DAZ_PT_MhxLayers,
    DAZ_PT_MhxFKIK,
    DAZ_PT_MhxProperties,
    DAZ_PT_Visibility,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)