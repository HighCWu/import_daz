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

#----------------------------------------------------------
#   Panels
#----------------------------------------------------------

class DAZ_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

#----------------------------------------------------------
#   Setup panel
#----------------------------------------------------------

class DAZ_PT_Setup(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Setup (version 1.6.1.%04d)" % BUILD
    bl_options = set()

    def draw(self, context):
        scn = context.scene
        self.layout.operator("daz.import_daz")
        self.layout.separator()
        self.layout.operator("daz.easy_import_daz")
        self.layout.prop(scn, "DazFavoPath")
        self.layout.separator()
        self.layout.operator("daz.global_settings")


class DAZ_PT_SetupCorrections(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupCorrections"
    bl_label = "Corrections"

    def draw(self, context):
        self.layout.operator("daz.eliminate_empties")
        self.layout.operator("daz.merge_rigs")
        self.layout.operator("daz.merge_toes")
        self.layout.separator()
        self.layout.operator("daz.copy_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.change_armature")


class DAZ_PT_SetupMaterials(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.update_settings")
        self.layout.operator("daz.save_local_textures")
        self.layout.operator("daz.resize_textures")
        self.layout.operator("daz.change_resolution")

        self.layout.separator()
        self.layout.operator("daz.change_colors")
        self.layout.operator("daz.change_skin_color")
        self.layout.operator("daz.merge_materials")
        self.layout.operator("daz.copy_materials")
        self.layout.operator("daz.prune_node_trees")

        self.layout.separator()
        self.layout.operator("daz.launch_editor")
        self.layout.operator("daz.reset_material")


class DAZ_PT_SetupMorphs(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        ob = context.object
        if ob and ob.DazDriversDisabled:
            self.layout.label(text = "Morph Drivers Disabled")
            self.layout.operator("daz.enable_drivers")
        elif ob and ob.type in ['ARMATURE', 'MESH']:
            if ob.DazMorphPrefixes:
                self.layout.label(text="Object with obsolete morphs")
                return
            self.layout.operator("daz.import_units")
            self.layout.operator("daz.import_expressions")
            self.layout.operator("daz.import_visemes")
            self.layout.operator("daz.import_facs")
            self.layout.operator("daz.import_facs_expressions")
            self.layout.operator("daz.import_body_morphs")
            self.layout.separator()
            self.layout.operator("daz.import_jcms")
            self.layout.operator("daz.import_flexions")
            self.layout.separator()
            self.layout.operator("daz.import_standard_morphs")
            self.layout.operator("daz.import_custom_morphs")
            self.layout.separator()
            self.layout.operator("daz.save_favo_morphs")
            self.layout.operator("daz.load_favo_morphs")
            self.layout.separator()
            self.layout.label(text="Create low-poly meshes before transfers.")
            self.layout.operator("daz.transfer_shapekeys")
            self.layout.operator("daz.apply_all_shapekeys")
            self.layout.operator("daz.mix_shapekeys")


class DAZ_PT_SetupFinishing(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupFinishing"
    bl_label = "Finishing"

    def draw(self, context):
        self.layout.operator("daz.merge_geografts")
        self.layout.operator("daz.merge_uv_layers")
        if bpy.app.version >= (2,82,0):
            self.layout.operator("daz.set_udims")
            self.layout.operator("daz.make_udim_materials")
        self.layout.operator("daz.convert_widgets")
        self.layout.operator("daz.finalize_meshes")
        self.layout.separator()
        self.layout.operator("daz.make_all_bones_poseable")
        self.layout.operator("daz.optimize_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.connect_ik_chains")


class DAZ_PT_SetupRigging(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.add_custom_shapes")
        self.layout.operator("daz.add_simple_ik")
        self.layout.separator()
        self.layout.operator("daz.convert_to_mhx")
        self.layout.separator()
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")
        self.layout.separator()
        self.layout.operator("daz.add_mannequin")

#----------------------------------------------------------
#   Advanced setup panel
#----------------------------------------------------------

class DAZ_PT_Advanced(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Advanced Setup"

    def draw(self, context):
        pass


class DAZ_PT_AdvancedLowpoly(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedLowpoly"
    bl_label = "Lowpoly"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.separator()
        self.layout.operator("daz.apply_morphs")
        self.layout.operator("daz.make_quick_proxy")
        self.layout.separator()
        self.layout.operator("daz.make_faithful_proxy")
        self.layout.operator("daz.split_ngons")
        self.layout.operator("daz.quadify")
        self.layout.separator()
        self.layout.operator("daz.add_push")


class DAZ_PT_AdvancedVisibility(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedVisibility"
    bl_label = "Visibility"

    def draw(self, context):
        self.layout.operator("daz.add_shrinkwrap")
        self.layout.operator("daz.create_masks")
        self.layout.operator("daz.add_visibility_drivers")
        self.layout.operator("daz.remove_visibility_drivers")


class DAZ_PT_AdvancedHDMesh(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedHDMesh"
    bl_label = "HDMesh"

    def draw(self, context):
        if bpy.app.version >= (2,90,0):
            self.layout.operator("daz.make_multires")
            self.layout.separator()
        if bpy.app.version >= (2,82,0):
            self.layout.operator("daz.bake_maps")
            self.layout.operator("daz.load_baked_maps")
            self.layout.separator()
        self.layout.operator("daz.load_normal_map")
        self.layout.operator("daz.load_scalar_disp")
        self.layout.operator("daz.load_vector_disp")
        self.layout.operator("daz.add_driven_value_nodes")


class DAZ_PT_AdvancedMaterials(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.load_uv")
        self.layout.operator("daz.prune_uv_maps")
        self.layout.separator()
        self.layout.operator("daz.collapse_udims")
        self.layout.operator("daz.restore_udims")
        self.layout.operator("daz.udims_from_textures")
        self.layout.separator()
        self.layout.operator("daz.remove_shells")
        self.layout.operator("daz.replace_shells")
        self.layout.separator()
        self.layout.operator("daz.make_decal")
        self.layout.operator("daz.make_shader_groups")


class DAZ_PT_AdvancedMesh(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMesh"
    bl_label = "Mesh"

    def draw(self, context):
        self.layout.operator("daz.limit_vertex_groups")
        self.layout.operator("daz.prune_vertex_groups")
        self.layout.operator("daz.create_graft_groups")
        self.layout.operator("daz.transfer_vertex_groups")
        self.layout.operator("daz.apply_subsurf")
        self.layout.operator("daz.copy_modifiers")
        self.layout.operator("daz.find_seams")
        self.layout.operator("daz.separate_loose_parts")
        self.layout.operator("daz.mesh_add_pinning")


class DAZ_PT_AdvancedSimulation(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedSimulation"
    bl_label = "Simulation"

    def draw(self, context):
        self.layout.operator("daz.make_simulation")
        self.layout.separator()
        self.layout.operator("daz.make_deflection")
        self.layout.operator("daz.make_collision")
        self.layout.operator("daz.make_cloth")


class DAZ_PT_AdvancedRigging(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.change_unit_scale")
        self.layout.operator("daz.remove_custom_shapes")
        self.layout.operator("daz.copy_daz_props")
        self.layout.operator("daz.convert_rig")
        self.layout.operator("daz.add_extra_face_bones")
        self.layout.separator()
        self.layout.operator("daz.add_ik_goals")
        self.layout.operator("daz.add_winders")
        self.layout.operator("daz.change_prefix_to_suffix")
        self.layout.operator("daz.lock_bones")
        self.layout.separator()
        self.layout.operator("daz.categorize_objects")


class DAZ_PT_AdvancedMorphs(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        self.layout.operator("daz.add_shape_to_category")
        self.layout.operator("daz.remove_shape_from_category")
        self.layout.operator("daz.rename_category")
        self.layout.operator("daz.remove_categories")
        self.layout.separator()
        self.layout.operator("daz.convert_morphs_to_shapekeys")
        self.layout.operator("daz.transfer_mesh_to_shape")
        self.layout.separator()
        self.layout.operator("daz.add_shapekey_drivers")
        self.layout.operator("daz.remove_shapekey_drivers")
        self.layout.operator("daz.remove_all_drivers")
        self.layout.separator()
        self.layout.operator("daz.copy_props")
        self.layout.operator("daz.copy_bone_drivers")
        self.layout.separator()
        self.layout.operator("daz.update_slider_limits")
        self.layout.operator("daz.import_dbz")
        self.layout.operator("daz.update_morph_paths")


class DAZ_PT_AdvancedHair(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedHair"
    bl_label = "Hair"

    def draw(self, context):
        from .hair import getHairAndHuman
        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.select_strands_by_size")
        self.layout.operator("daz.select_strands_by_width")
        self.layout.operator("daz.select_random_strands")
        self.layout.separator()
        self.layout.operator("daz.make_hair")
        hair,hum = getHairAndHuman(context, False)
        self.layout.label(text = "  Hair:  %s" % (hair.name if hair else None))
        self.layout.label(text = "  Human: %s" % (hum.name if hum else None))
        self.layout.separator()
        self.layout.operator("daz.update_hair")
        self.layout.operator("daz.color_hair")
        self.layout.operator("daz.combine_hairs")

#----------------------------------------------------------
#   Utilities panel
#----------------------------------------------------------

class DAZ_PT_Utils(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Utilities"

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
        layout.operator("daz.decode_file")
        layout.operator("daz.quote_unquote")
        layout.operator("daz.print_statistics")
        layout.operator("daz.update_all")
        layout.separator()
        box = layout.box()
        if ob:
            box.label(text = "Active Object: %s" % ob.type)
            box.prop(ob, "name")
            box.prop(ob, "DazBlendFile")
            box.prop(ob, "DazId")
            box.prop(ob, "DazUrl")
            box.prop(ob, "DazScene")
            box.prop(ob, "DazRig")
            box.prop(ob, "DazMesh")
            if ob.type == 'MESH':
                box.prop(ob.data, "DazFingerPrint")
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
        icon = 'CHECKBOX_HLT' if G.theSilentMode else 'CHECKBOX_DEHLT'
        layout.operator("daz.set_silent_mode", icon=icon, emboss=False)
        layout.operator("daz.get_finger_print")
        layout.operator("daz.inspect_world_matrix")
        layout.operator("daz.enable_all_layers")


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

#----------------------------------------------------------
#   Posing panel
#----------------------------------------------------------

class DAZ_PT_Posing(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Posing"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type in ['ARMATURE', 'MESH'])


    def draw(self, context):
        from .morphing import getRigFromObject
        ob = context.object
        rig = getRigFromObject(ob)
        if rig is None:
            return
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
        if rig.DazDriversDisabled:
            layout.operator("daz.enable_drivers")
        else:
            layout.operator("daz.disable_drivers")
        layout.operator("daz.prune_action")
        layout.separator()
        layout.operator("daz.impose_locks_limits")
        layout.operator("daz.bake_pose_to_fk_rig")
        layout.operator("daz.save_pose_preset")

        layout.separator()
        prop = "Adjust Morph Strength"
        if prop in rig.keys():
            layout.prop(rig, propRef(prop))
        split = layout.split(factor=0.6)
        layout.prop(rig, "DazLocLocks")
        layout.prop(rig, "DazRotLocks")
        layout.prop(rig, "DazLocLimits")
        layout.prop(rig, "DazRotLimits")

        return
        layout.separator()
        layout.operator("daz.save_poses")
        layout.operator("daz.load_poses")
        layout.separator()
        layout.operator("daz.rotate_bones")

#----------------------------------------------------------
#   Morphs UIList
#----------------------------------------------------------

filterFlags = {0: [], 1: [], 2: []}
filterInvert = {0: False, 1: False, 2: False}

class DAZ_UL_MorphList(bpy.types.UIList):
    def draw_item(self, context, layout, data, morph, icon, active, indexProp):
        rig,amt = self.getRigAmt(context)
        key = morph.name
        if rig is None or key not in rig.keys():
            return
        split = layout.split(factor=0.8)
        final = finalProp(key)
        if GS.showFinalProps and final in amt.keys():
            split2 = split.split(factor=0.8)
            split2.prop(rig, propRef(key), text=morph.text)
            split2.label(text = "%.3f" % amt[final])
        else:
            split.prop(rig, propRef(key), text=morph.text)
        row = split.row()
        self.showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset, op.category = self.getMorphCat(data, indexProp)


    def getRigAmt(self, context):
        rig = context.object
        while rig.type != 'ARMATURE' and rig.parent:
            rig = rig.parent
        if rig.type == 'ARMATURE':
            amt = rig.data
            return rig, amt
        else:
            return None, None


    def showBool(self, layout, ob, key, text=""):
        from .morphing import getExistingActivateGroup
        pg = getExistingActivateGroup(ob, key)
        if pg is not None:
            layout.prop(pg, "active", text=text)


    def filter_items(self, context, data, propname):
        global filterFlags, filterInvert
        morphs = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list
        flt_flags = []
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, morphs, "text")
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(morphs)
        flt_neworder = helper_funcs.sort_items_by_name(morphs, "text")
        filterFlags[self.filterType] = flt_flags
        filterInvert[self.filterType] = self.use_filter_invert
        return flt_flags, flt_neworder


class DAZ_UL_Morphs(DAZ_UL_MorphList):
    filterType = 0

    def getMorphCat(self, data, indexProp):
        return indexProp[8:], ""


class DAZ_UL_CustomMorphs(DAZ_UL_MorphList):
    filterType = 1

    def getMorphCat(self, cat, indexProp):
        return "Custom", cat.name


class DAZ_UL_Shapekeys(DAZ_UL_MorphList):
    filterType = 2

    def draw_item(self, context, layout, cat, morph, icon, active, indexProp):
        ob = context.object
        skeys = ob.data.shape_keys
        key = morph.name
        if skeys and key in skeys.key_blocks.keys():
            skey = skeys.key_blocks[key]
            row = layout.split(factor=0.8)
            row.prop(skey, "value", text=morph.text)
            self.showBool(row, ob, key)
            op = row.operator("daz.pin_shape", icon='UNPINNED')
            op.key = key
            op.category = cat.name

#----------------------------------------------------------
#   Morphs panel
#----------------------------------------------------------

class DAZ_PT_Morphs:
    useMesh = False
    filterType = 0

    @classmethod
    def poll(self, context):
        rig = self.getCurrentRig(self, context)
        return (rig and
                not rig.DazDriversDisabled and
                (self.hasTheseMorphs(self, rig) or self.hasAdjustProp(self, rig)))


    def getCurrentRig(self, context):
        rig = context.object
        if rig is None:
            return None
        elif rig.type == 'MESH':
            rig = rig.parent
        if rig and rig.type == 'ARMATURE':
            return rig
        else:
            return None


    def hasTheseMorphs(self, rig):
        return getattr(rig, "Daz"+self.morphset)


    def hasAdjustProp(self, rig):
        from .morphing import theAdjusters
        adj = theAdjusters[self.morphset]
        return (adj in rig.keys())


    def draw(self, context):
        scn = context.scene
        rig = self.getCurrentRig(context)
        from .morphing import theAdjusters
        adj = theAdjusters[self.morphset]
        if adj in rig.keys():
            self.layout.prop(rig, propRef(adj))
        if not self.hasTheseMorphs(rig):
            return
        self.preamble(self.layout, rig)
        self.drawItems(scn, rig)


    def preamble(self, layout, rig):
        self.activateLayout(layout, "", rig)
        self.keyLayout(layout, "", rig)


    def activateLayout(self, layout, category, rig):
        split = layout.split(factor=0.333)
        op = split.operator("daz.activate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op.filterType = self.filterType
        op = split.operator("daz.deactivate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op.filterType = self.filterType
        op = self.setMorphsBtn(split)
        op.category = category
        op.filterType = self.filterType


    def setMorphsBtn(self, layout):
        op = layout.operator("daz.set_morphs")
        op.morphset = self.morphset
        return op


    def keyLayout(self, layout, category, rig):
        split = layout.split(factor=0.25)
        op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
        op.morphset = self.morphset
        op.category = category
        op.filterType = self.filterType
        op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
        op.morphset = self.morphset
        op.category = category
        op.filterType = self.filterType
        op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
        op.morphset = self.morphset
        op.category = category
        op.filterType = self.filterType
        op = split.operator("daz.clear_morphs", text="", icon='X')
        op.morphset = self.morphset
        op.category = category
        op.filterType = self.filterType

    def drawItems(self, scn, rig):
        self.layout.template_list( "DAZ_UL_Morphs", "",
                                   rig, "Daz%s" % self.morphset,
                                   rig.data, "DazIndex%s" % self.morphset )


class DAZ_PT_MorphGroup(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Morphs"
    morphset = "All"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        rig = self.getCurrentRig(context)
        if not rig:
            return
        if rig.DazDriversDisabled:
            self.layout.label(text = "Morph Drivers Disabled")
            self.layout.operator("daz.enable_drivers")
            return
        else:
            self.layout.operator("daz.disable_drivers")
        self.preamble(self.layout, rig)
        self.layout.operator("daz.morph_armature")



class DAZ_PT_Standard(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Unclassified Standard Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Standard"

class DAZ_PT_Units(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Face Units"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Units"

class DAZ_PT_Head(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Head"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Head"

class DAZ_PT_Expressions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Expressions"

class DAZ_PT_Visemes(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Visemes"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Visemes"

    def draw(self, context):
        self.layout.operator("daz.load_moho")
        DAZ_PT_Morphs.draw(self, context)


class DAZ_PT_FacsUnits(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Units"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facs"

    def preamble(self, layout, rig):
        layout.operator("daz.import_facecap")
        layout.operator("daz.import_livelink")
        DAZ_PT_Morphs.preamble(self, layout, rig)


class DAZ_PT_FacsExpressions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facsexpr"


class DAZ_PT_BodyMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Body Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Body"


class DAZ_PT_JCMs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "JCMs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Jcms"


class DAZ_PT_Flexions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Flexions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Flexions"

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
        for cat in ob.DazMorphCats:
            box = self.layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name, icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name, icon="DOWNARROW_HLT", emboss=False)
            self.drawCustomBox(box, cat, scn, ob)


class DAZ_PT_CustomMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Custom Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"
    filterType = 1

    def hasTheseMorphs(self, ob):
        return ob.DazCustomMorphs

    def preamble(self, layout, rig):
        pass

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob

    def drawCustomBox(self, box, cat, scn, rig):
        adj = "Adjust Custom/%s" % cat.name
        if adj in rig.keys():
            box.prop(rig, propRef(adj))
        if len(cat.morphs) == 0:
            return
        self.activateLayout(box, cat.name, rig)
        self.keyLayout(box, cat.name, rig)
        self.layout.template_list("DAZ_UL_CustomMorphs", "", cat, "morphs", cat, "index")


class DAZ_PT_CustomMeshMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Mesh Shape Keys"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"
    useMesh = True
    filterType = 2

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and self.hasTheseMorphs(self, ob))

    def hasTheseMorphs(self, ob):
        return (ob.DazMeshMorphs or len(ob.DazAutoFollow) > 0)

    def draw(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and len(ob.DazAutoFollow) > 0:
            box = self.layout.box()
            box.label(text = "Auto Follow")
            for item in ob.DazAutoFollow:
                sname = item.name
                if (sname in ob.keys() and
                    sname in skeys.key_blocks.keys()):
                    skey = skeys.key_blocks[sname]
                    self.drawAutoItem(box, ob, skey, sname, item.text)
            self.layout.separator()
        if ob.DazMeshMorphs:
            DAZ_PT_Morphs.draw(self, context)


    def drawAutoItem(self, layout, ob, skey, sname, text):
        if GS.showFinalProps:
            split = layout.split(factor=0.8)
            split.prop(ob, propRef(sname), text=text)
            split.label(text = "%.3f" % skey.value)
        else:
            layout.prop(ob, propRef(sname), text=text)


    def getCurrentRig(self, context):
        return context.object


    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob.data.shape_keys

    def setMorphsBtn(self, layout):
        return layout.operator("daz.set_shapes")

    def keyLayout(self, layout, category, rig):
        split = layout.split(factor=0.333)
        op = split.operator("daz.key_shapes", text="", icon='KEY_HLT')
        op.category = category
        op.filterType = self.filterType
        op = split.operator("daz.unkey_shapes", text="", icon='KEY_DEHLT')
        op.category = category
        op.filterType = self.filterType
        op = split.operator("daz.clear_shapes", text="", icon='X')
        op.category = category
        op.filterType = self.filterType


    def drawCustomBox(self, box, cat, scn, ob):
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        self.activateLayout(box, cat.name, ob)
        self.keyLayout(box, cat.name, ob)
        self.layout.template_list("DAZ_UL_Shapekeys", "", cat, "morphs", cat, "index")

#------------------------------------------------------------------------
#    Simple IK Panel
#------------------------------------------------------------------------

class DAZ_PT_SimpleRig(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Simple Rig"

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazCustomShapes)

    def draw(self, context):
        amt = context.object.data
        self.drawLayers(amt)
        if amt.DazSimpleIK:
            self.drawSimpleIK(amt)


    def drawSimpleIK(self, amt):
        layout = self.layout
        layout.separator()
        layout.label(text="IK Influence")
        split = layout.split(factor=0.2)
        split.label(text="")
        split.label(text="Left")
        split.label(text="Right")
        split = layout.split(factor=0.2)
        split.label(text="Arm")
        split.prop(amt, "DazArmIK_L", text="")
        split.prop(amt, "DazArmIK_R", text="")
        split = layout.split(factor=0.2)
        split.label(text="Leg")
        split.prop(amt, "DazLegIK_L", text="")
        split.prop(amt, "DazLegIK_R", text="")

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


    def drawLayers(self, amt):
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
            row.prop(amt, "layers", index=m, toggle=True, text=first)
            row.prop(amt, "layers", index=n, toggle=True, text=second)

#------------------------------------------------------------------------
#   Visibility panels
#------------------------------------------------------------------------

class DAZ_PT_Visibility(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Visibility"
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

#------------------------------------------------------------------------
#   DAZ Rigify props panels
#------------------------------------------------------------------------

class DAZ_PT_DazRigifyProps(bpy.types.Panel):
    bl_label = "DAZ Rigify Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and
                ob.DazRig in ["rigify", "rigify2"] and
                "MhaGazeFollowsHead" in ob.data.keys())

    def draw(self, context):
        amt = context.object.data
        self.layout.prop(amt, propRef("MhaGazeFollowsHead"), text="Gaze Follows Head")
        self.layout.prop(amt, propRef("MhaGaze_L"), text="Left Gaze")
        self.layout.prop(amt, propRef("MhaGaze_R"), text="Right Gaze")

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_PT_Setup,
    DAZ_PT_SetupCorrections,
    DAZ_PT_SetupMaterials,
    DAZ_PT_SetupMorphs,
    DAZ_PT_SetupFinishing,
    DAZ_PT_SetupRigging,

    DAZ_PT_Advanced,
    DAZ_PT_AdvancedLowpoly,
    DAZ_PT_AdvancedVisibility,
    DAZ_PT_AdvancedHDMesh,
    DAZ_PT_AdvancedMaterials,
    DAZ_PT_AdvancedMesh,
    DAZ_PT_AdvancedSimulation,
    DAZ_PT_AdvancedRigging,
    DAZ_PT_AdvancedMorphs,
    DAZ_PT_AdvancedHair,

    DAZ_PT_Utils,
    DAZ_PT_Posing,

    DAZ_UL_Morphs,
    DAZ_UL_CustomMorphs,
    DAZ_UL_Shapekeys,

    DAZ_PT_MorphGroup,
    DAZ_PT_Standard,
    DAZ_PT_Units,
    DAZ_PT_Head,
    DAZ_PT_Expressions,
    DAZ_PT_Visemes,
    DAZ_PT_FacsUnits,
    DAZ_PT_FacsExpressions,
    DAZ_PT_BodyMorphs,
    DAZ_PT_JCMs,
    DAZ_PT_Flexions,

    DAZ_PT_CustomMorphs,
    DAZ_PT_CustomMeshMorphs,
    DAZ_PT_SimpleRig,
    DAZ_PT_Visibility,
    DAZ_PT_DazRigifyProps,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
