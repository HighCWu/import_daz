bl_info = {
    "name": "DAZ rig bone utility",
    "author": "WaitInFuture",
    "version": (2, 0, 3),
    "blender": (2, 80, 0),
    "location": "View3D > Npanel",
    "description": "renameDAZgenesisBone, adjust rig pos for daz importer rig",
    "warning": "testonly",
    "wiki_url": "https://bitbucket.org/engetudouiti/wifdazimportaddons/src/master/",
    "tracker_url": "",
    "category": "Rigging"}
    
""" blender add on version , it work as individual add on, install as same as other blender add ons"""

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty

from mathutils import Vector, Matrix, Quaternion
from math import radians, pi
import json
import os
    
def unsetSceneprop():
    scns = bpy.data.scenes
    for scn in scns:
        if "wif-info" in scn.keys():
            del scn["wif-info"]
    
def sel_act(context, ob):
    ob.select_set(True)
    context.view_layer.objects.active = ob
    
def showInfo(self, context, msg):
    scn = context.scene
    scn["wif-info"] = msg
    self.report({'INFO'}, msg)
    
def update_prop(context, rig):
    loc = rig.location
    rig.location = loc    

class WIF_OT_addinfo(bpy.types.Operator):
    bl_idname = "dazinfo.reflesh"
    bl_label = "WIF DAZ show info"
    bl_description = "open info labell"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        scn = context.scene
        scn["wif-info"] = "***infomation***"
        return {'FINISHED'}

class WIF_PT_dazBoneUtils(bpy.types.Panel):
    bl_label = "WIF DAZ bone utility"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ BoneTool"
    
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=False)
        box = row.box()
        box.operator("bonename.change", text="Change Bone Name")
        box.operator("bonename.dazname", text="Return Bone Name")
        row = layout.row(align=False)
        box = row.box()
        box.operator("import_js.setpath", text="Set Json Path")
        box.operator("import_js.dazdata", text="Import json")
        box.operator("dazbone.adjust", text="Adjust Daz bones")
        box.operator("dazbone.memorize", text="Memorize edit-bones")
        box.operator("dazbone.return", text="Restore edit-bones")
        row = layout.row(align=False)
        box = row.box()        
        box.operator("dazbone.dotshow", text="Update bone layer")
        box.operator("dazbone.selectchild", text = "Select Child Bones")
        box.operator("dazbone.deselectchild", text = "Deselect Child Bones")
        box.operator("dazbone.flipbone", text="Flip selected edit bones")
        row = layout.row(align=False)
        box = row.box()
        box.label(text = "plus or minus roll")
        row = box.row()
        row.alignment = 'EXPAND'        
        row.operator("dazbone.addroll", text="+90 roll").rfg = True
        row.operator("dazbone.addroll", text="-90 roll").rfg = False
        row = layout.row(align=False)
        box = row.box()
        box.label(text = "save or load morph preset")
        row = box.row()
        row.alignment = 'EXPAND'        
        row.operator("export.morph_preset", text="save")
        row.operator("import.morphpreset", text="load")        
        
        #row.operator("dazinfo.reflesh", text="Open info")
        scn = bpy.context.scene
        row = layout.row(align=False)
        row.label(text = "infomation")
        if "wif-info" in scn.keys():
            row = layout.row(align=False)
            row.prop(scn, '["wif-info"]', text = "")
        
class WIF_OT_changeDazBoneName(bpy.types.Operator):
    bl_idname = "bonename.change"
    bl_label = "text"
    bl_description = "change bones name for blender mirror"
    bl_options = {'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        obj = bpy.context.active_object
        if not obj:
            msg = "select daz armature first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif not obj.type == 'ARMATURE':
            msg = "select daz armature first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        pblist = bpy.context.object.pose.bones
        
        for pb in pblist:
            bName = pb.name
            if bName[0] == "r" and bName[1] != ".":
                lbname= "l" + bName[1:]
                for lpb in pblist:
                    lpbName = lpb.name
                    if lpbName == lbname:
                        lpbName = lpbName[:1] + "." + lpbName[1:]
                        lpb.name = lpbName
                        bName = bName[:1] + "." + bName[1:]
                        pb.name=bName
                        
        msg = "rename daz bones for mirror!"
        showInfo(self, context, msg)
        return{'FINISHED'}

class WIF_OT_returnDazBoneName(bpy.types.Operator):
    bl_idname = "bonename.dazname"
    bl_label = "text"
    bl_description = "return bones names as default"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        obj = bpy.context.active_object
        if not obj:
            msg = "select renamed armature first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif not obj.type == 'ARMATURE':
            msg = "select renamed armature first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        pblist = bpy.context.object.pose.bones
        for pb in pblist:
            bName = pb.name
            if bName[0] == "r" and bName[1] == ".":
                lbname= "l" + bName[1:]
                for lpb in pblist:
                    lpbName = lpb.name
                    if lpbName == lbname:
                        lpbName = lpbName[:1] + lpbName[2:]
                        lpb.name = lpbName
                        bName = bName[:1] + bName[2:]
                        pb.name=bName
                        
        msg = "return daz bone names as default"
        showInfo(self, context, msg)
        return{'FINISHED'}
    
def read_daz_json(context, fp): 
    dazdata = None    
    with open(fp, 'r', encoding='utf-8') as f:
        print(f.name)
        dazdata = json.load(f)
        f.close()
    return (dazdata)

def convert_daz_json(scn, dazdata):
    amtdic = {}
    if "figures" in dazdata.keys():
        figdic = dazdata["figures"]
    else:
        print("no figure in json")
        scn["wif-info"] = "no figure in json!"         
        return {'FINISHED'}

    figdata = {}
    for fig in figdic:
        if ("bones" in fig.keys() and
            "label" in fig.keys()):
            figdata[fig["label"]] = fig["bones"]
    
    if figdata == {}:
        print ("json have no label!!")
        scn["wif-info"] = "json missing label or bone!"
        return amtdic
    
    for key in figdata.keys(): 
        bonedic = {}
        for bn in figdata[key]:
            bonedic[bn["name"]] = {"cp": bn["center_point"], "ep": bn["end_point"], "rot": bn["ws_rot"]}
        amtdic[key] = bonedic
         
    return amtdic

def set_daz_props(context, rigs, dazdata):
    scn = context.scene
    amtdic = convert_daz_json(scn, dazdata)
    if amtdic == {}:
        return
    for rig in rigs:
        rig.select_set(False)
    for rig in rigs:        
        if rig.type == 'ARMATURE' and "DazRig" in rig.keys():
            sel_act(context, rig)
            bpy.ops.object.mode_set(mode = 'EDIT')
            ebones = rig.data.edit_bones
            sname = rig.name            
            rigdic = {}
            if sname in amtdic.keys():
                rigdic = amtdic[sname]
                print("find:", sname)
            else:
                print (sname, " is not in json!!")
                scn["wif-info"] = sname + ":is not in json!!" 
                return

            for bn in ebones:
                bname = bn.name
                if bname in rigdic.keys():
                    bn["DazWsrot"] = rigdic[bname]["rot"]
                    bn["DazCp"] = rigdic[bname]["cp"]
                    bn["DazEp"] = rigdic[bname]["ep"]
                else:
                    scn["wif-info"] = sname + ": " + bname + " failed!!" 
                    return
                
                if not "def_hd" in bn:
                    bn["def_hd"] = bn.head
                    bn["def_tl"] = bn.tail
                    bn["def_rl"] = bn.roll                

            print(rig.name, ":addprop for bones complete")
            bpy.ops.object.mode_set(mode = 'OBJECT')
    scn["wif-info"] = "Import json succeed!!" 
               
class WIF_OT_SetFilePath(bpy.types.Operator):
    bl_idname = "import_js.setpath"
    bl_label = "setJsonPath"
    bl_description = "Set Json path with select mesh"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        bpy.types.Scene.js_path = StringProperty( 
                                name="json path",
                                default="", 
                                )
        bpy.types.Scene.DazJsAbs = StringProperty( 
                                name="Abs Json Path",
                                default="", 
                                )
                                
        scn = bpy.context.scene
        try:
            DazId = bpy.context.active_object.DazId
            ind = DazId.rfind("#")
            duf_path = DazId[:ind]
            js_path = duf_path[:-3] + "json"
            scn.js_path = js_path
            
            dir_count = scn.DazNumPaths
            for i in range(dir_count):
                dp = "DazPath" + str(i +1)
                basePath = getattr(scn, dp)
                if os.path.isfile(basePath + scn.js_path):
                    scn.DazJsAbs = basePath + scn.js_path
                    msg = scn.DazJsAbs
                    showInfo(self, context, msg)
                    break                  

            return {'FINISHED'}
            
        except:
               msg = "select mesh to set json path"
               showInfo(self, context, msg)
               return {'FINISHED'}

class WIF_OT_ImportDazData(bpy.types.Operator, ImportHelper):
    bl_idname = "import_js.dazdata"
    bl_label = "Import Json"
    bl_description = "import rig data to adjust daz bones"
    bl_options = {'UNDO'}
    
    filter_glob: StringProperty( 
                                default='*.json;*.duf', 
                                options={'HIDDEN'},
                                )
                                    
    directory: StringProperty(
                              name="directory",
                              description="directory used for importing the file",
                              maxlen=1024,
                              )
                              
    filename: StringProperty(
                             name = "filename",
                             description = "filename used for importing the file",
                             )
                             
    info: StringProperty(
                         default = "nomessage",
                         name = "infomsg",
                         description = "infomation",
                        )
    
    def execute(self, context):
        filename, extension = os.path.splitext(self.filepath)
        scn = context.scene
        
        print("directory: ", self.directory)
        print("filename: ", self.filename)
        
        if extension == '.json':            
            dazdata = read_daz_json(context, self.filepath)
            rigs = bpy.context.selected_objects
            set_daz_props(context, rigs, dazdata)
            
        else:
            msg = "Select json please!"
            showInfo(self, context, msg)
            
        return {'FINISHED'}
    
    def invoke(self, context, _event):
        scn = context.scene
        bpy.ops.dazinfo.reflesh()
        rigs = bpy.context.selected_objects
        
        if not rigs:
            msg = "Select import rigs first!!"
            showInfo(self, context, msg)
            return {'FINISHED'}
        
        self.filepath = scn.DazJsAbs
            
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    #Test to set directory and file for enhancement
    """def invoke(self, context, _event):
        self.filename = ""
        self.directory = ""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'} """                    
    
def circulate_tp(tcp,tep,ro,length):
    roll = 0
    tp = Vector((0, 0, 0))

    if ro[0] == "X" :       #xyz xzy
        if tep[0] >= tcp[0]:
            tp[0] =  length
            if ro[1] == "Y" :
                roll = pi
            else:
                roll = -pi/2
        else:
            tp[0] =  -length
            if ro[1] == "Y" :
                roll = pi
            else:
                roll = pi/2

    elif ro[0] == "Y" :   #yxz, yzx
        if tep[1] >= tcp[1] :
            tp[2] = length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = 0

        else:
            tp[2] = -length
            if ro[1] == "X":
                roll =  pi/2
            else:
                roll = 0

    else:
        if tep[2] >= tcp[2] :
            tp[1] = -length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = -pi
        else:
            tp[1] =  length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = 0

    return tp, roll

def orientate_bone(ebn, ot, pr):
    rx = radians(ot[0])
    ry = radians(ot[1])
    rz = -radians(ot[2])

    dq = [-pr[3], pr[0], -pr[2], pr[1]]
    dquat = Quaternion(dq)
    bp_mat = dquat.to_matrix()
    mat_pr = bp_mat.to_4x4()

    mat_o = ebn.matrix
    mat_ra = Matrix.Rotation(rx, 4, 'X')
    mat_rb = Matrix.Rotation(ry, 4, 'Z')
    mat_rc = Matrix.Rotation(rz, 4, 'Y')
    
    mat_r = mat_pr @ mat_rc @ mat_rb @ mat_ra
    ebn.matrix = mat_r @ mat_o

def trans_bone(ebn, cp):
    tcp = Vector((cp[0], -cp[2], cp[1]))
    ebn.translate(tcp)

def generate_ds_bone(amt,cp,ep,tcp,tep,ro,ot,pr,name):
    length = abs((ep - cp).length)
    #print(length)
    bn = amt.data.edit_bones.new(name)
    bn.head = (0, 0, 0)
    tpr = circulate_tp(tcp,tep,ro,length)
    bn.tail = tpr[0]
    bn.roll = tpr[1]
    orientate_bone(bn, ot, pr)
    trans_bone(bn, cp)
    
    for index in range(len(bn.layers)):
        bn.layers[index] = False
        if not index == 16:
            continue
            
        bn.layers[index] = True      
            
def copy_edit_bone(amt, bname, name):
    ebones = amt.data.edit_bones
    ebones[bname].tail = ebones[name].tail
    ebones[bname].align_orientation(ebones[name])

    #comment-out below function to check generate _edit bones
    ebones.remove(ebones[name])
    
def rtn_edit_bone(amt):
    ebones = amt.data.edit_bones
    for bn in ebones:
        if "def_hd" in bn:
            bn.head = bn["def_hd"]
            bn.tail = bn["def_tl"]
            bn.roll = bn["def_rl"]
            
def memorize_edit_bone(amt):
    ebones = amt.data.edit_bones
    for bn in ebones:
        bn["def_hd"] = bn.head
        bn["def_tl"] = bn.tail
        bn["def_rl"] = bn.roll
        
def update_bn_layer(amt):
    ebones = amt.data.edit_bones
    for ebn in ebones:
        ebn.select = False
    ebn = ebones[0]
    ebn.select = True
    layer = ebn.layers
    bpy.ops.armature.bone_layers(layers=layer)
    
class WIF_OT_adjustDazBonePos(bpy.types.Operator):
    bl_idname = "dazbone.adjust"
    bl_label = "text"
    bl_description = "adjust tip and local axis of selected daz rigs"
    bl_options = {'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        objs = bpy.context.selected_objects
        if not objs:
            msg = "Select daz rigs first!!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        for ob in objs:
            ob.select_set(False)
        for ob in objs:
            if ob.type == 'ARMATURE' and "DazRig" in ob.keys():
                sel_act(context, ob)
                #ob.select_set(True)
                #context.view_layer.objects.active = ob
                amt = bpy.context.active_object
                print(amt.name)
                bpy.ops.object.mode_set(mode = 'EDIT')
                ebones = amt.data.edit_bones
                pbones = amt.pose.bones
                bn_lst = []
                for bn in ebones:
                    if "DazHead" in bn.keys() and "DazRotMode" in pbones[bn.name].keys():
                        bn_lst.append(bn.name)
                for bname in bn_lst:
                    if "DazCp" not in ebones[bname].keys():
                        print("Bone without DazCp: %s" % bname)
                        continue

                    name = bname + "_Edt"
                    cp = ebones[bname]["DazHead"]
                    ep = ebones[bname]["DazTail"]
                    ro = pbones[bname]["DazRotMode"]
                    ot = ebones[bname]["DazOrientation"]

                    dcp = ebones[bname]["DazCp"]
                    dep = ebones[bname]["DazEp"]

                    pr = ebones[bname]["DazWsrot"]
                    cp = Vector(cp)/100
                    dcp = Vector(dcp)/100
                    ep = Vector(ep)/100
                    dep = Vector(dep)/100

                    generate_ds_bone(amt,cp,ep,dcp,dep,ro,ot,pr,name)
                    copy_edit_bone(amt, bname, name)
                    
                bpy.ops.object.mode_set(mode = 'OBJECT')
        msg = "Adjust bones Finish!"
        showInfo(self, context, msg)
        return{'FINISHED'}
        
class WIF_OT_memorizeDefBone(bpy.types.Operator):
    bl_idname = "dazbone.memorize"
    bl_label = "text"
    bl_description = "memorize editbones for restore!!"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        objs = bpy.context.selected_objects
        
        if not objs:
            msg = "select armatures first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        for ob in objs:
            ob.select_set(False)
            
        for ob in objs:
            if ob.type == 'ARMATURE':
                sel_act(context, ob)
                amt = bpy.context.active_object
                bpy.ops.object.mode_set(mode = 'EDIT')
                memorize_edit_bone(ob)
                bpy.ops.object.mode_set(mode = 'OBJECT')
        
        msg = "Edit-bones memorized!!"
        showInfo(self, context, msg)
        return{'FINISHED'}                
        
class WIF_OT_returnDefBone(bpy.types.Operator):
    bl_idname = "dazbone.return"
    bl_label = "text"
    bl_description = "return editbones to memorized"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        objs = bpy.context.selected_objects
        if not objs:
            msg = "select adjusted rig first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        for ob in objs:
            ob.select_set(False)
            
        for ob in objs:
            if ob.type == 'ARMATURE':
                sel_act(context, ob)
                amt = bpy.context.active_object
                bpy.ops.object.mode_set(mode = 'EDIT')
                rtn_edit_bone(ob)
                bpy.ops.object.mode_set(mode = 'OBJECT')
                
        msg = "Edit-bones restored!!"
        showInfo(self, context, msg)
        return{'FINISHED'}

class WIF_OT_showBoneDots(bpy.types.Operator):
    bl_idname = "dazbone.dotshow"
    bl_label = "text"
    bl_description = "update bone-layer to show all dots"
    bl_options = {'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        objs = bpy.context.selected_objects
        if not objs:
            msg = "select armatures first!"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        for ob in objs:
            ob.select_set(False)
            
        for ob in objs:
            if ob.type == 'ARMATURE':
                sel_act(context, ob)
                amt = bpy.context.active_object
                bpy.ops.object.mode_set(mode = 'EDIT')
                update_bn_layer(ob)
                bpy.ops.object.mode_set(mode = 'OBJECT')
                
        msg = "up-date all bone layers!!"
        showInfo(self, context, msg)
        return{'FINISHED'}            

def select_children(self, context, mode):
    if mode == 'POSE':
        bn_selection = bpy.context.selected_pose_bones        
    else:
        bn_selection = bpy.context.selected_editable_bones
    
    b_list = []
      
    if not len(bn_selection)==0:
        for i in bn_selection:
            b_list += i.children_recursive
            b_list = list(set(b_list))
            
        for i in b_list:
            if mode == 'POSE':
                i.bone.select = True
            else:
                i.select = True
                i.select_head = True
                i.select_tail = True
                
        msg = "child bones selected!!"
        showInfo(self, context, msg)
                
    else:
        msg = "select bones first!!"
        showInfo(self, context, msg)
    
    return
    
def unselect_children(self, context, mode):

    if mode == 'POSE':
        bn_selection = bpy.context.selected_pose_bones
        bn_active = bpy.context.active_pose_bone
    else:
        bn_selection = bpy.context.selected_bones
        bn_active = bpy.context.active_bone
        
    b_list = []
        
    if bn_active:
        print("active bone ", bn_active)        
        b_list = bn_active.children_recursive
        b_list.append(bn_active)
        if mode == 'POSE':
            for i in b_list:                
                i.bone.select = False
        else:
            for i in b_list:
                i.select_head = False
                i.select_tail = False
                i.select = False
        msg = "child bones unselected!!"
        showInfo(self, context, msg)
    else:
        msg = "select bones first!!"
        showInfo(self, context, msg)
    
    return
    
class WIF_OT_SelectChildBones(bpy.types.Operator):
    bl_idname = "dazbone.selectchild"
    bl_label = "SelectChildBones"
    bl_description = "select child bones from current selection (for pose and edit mode)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        aob = bpy.context.active_object
        if not aob:
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif not aob.type == "ARMATURE":
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif aob.mode == 'OBJECT':
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        else:
            select_children(self, context, aob.mode)
            
        return {'FINISHED'}
        
class WIF_OT_DeselectChildBones(bpy.types.Operator):
    bl_idname = "dazbone.deselectchild"
    bl_label = "DeselectChildBones"
    bl_description = "deselect child bones of Active bone (for pose and edit mode)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        aob = bpy.context.active_object
        if not aob:
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif not aob.type == "ARMATURE":
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}
            
        elif aob.mode == 'OBJECT':
            msg = "select bones in pose or edit mode"
            showInfo(self, context, msg)
            return {'FINISHED'}  
            
        else:
            unselect_children(self, context, aob.mode)

        return {'FINISHED'}
        
class WIF_OT_flipBones(bpy.types.Operator):
    bl_idname = "dazbone.flipbone"
    bl_label = "text"
    bl_description = "flip selected edit-bones along bone direciton"
    bl_options = {'UNDO'}

    def execute(self, context):
        bpy.ops.dazinfo.reflesh()
        ob = bpy.context.active_object
        slist = []
        if not ob:
            msg = "select bones in edit mode!!"
            showInfo(self, context, msg)
            return{'FINISHED'}
            
        if ob.type == "ARMATURE" and ob.mode == "EDIT":
            ebn = bpy.context.selected_bones
            for bn in ebn:
                slist.append(bn.name)
            print(slist)
            for bn in slist:
                ebone = ob.data.edit_bones[bn]
                ehead = ebone.head
                etail = ebone.tail
                ebone.tail = ehead + ehead - etail
            
            msg = "flip bones!!"
            showInfo(self, context, msg)
            return{'FINISHED'}
        
        else:
            msg = "select bones in edit mode!!"
            showInfo(self, context, msg)
            return{'FINISHED'}
        
        return{'FINISHED'}                

class WIF_OT_addRoll(bpy.types.Operator):
    bl_idname = "dazbone.addroll"
    bl_label = "text"
    bl_description = "plus or minus roll 90 for selected edit bones"
    bl_options = {'UNDO'}
    
    rfg: BoolProperty(default=True)

    def execute(self, context):
        ob = bpy.context.active_object
        bpy.ops.dazinfo.reflesh()
        if not ob:
            msg = "select bones in edit mode!"
            showInfo(self, context, msg)
            return{'FINISHED'}
            
        if ob.type == 'ARMATURE' and context.mode == 'EDIT_ARMATURE':
            ebones = context.selected_bones
            if self.rfg == True:
                for bn in ebones:
                    bn.roll += pi/2
            else:
                for bn in ebones:
                    bn.roll -= pi/2
            msg = "change roll!!"
            showInfo(self, context, msg)
            return{'FINISHED'}
            
        else:
            msg = "select bones in edit mode!"
            showInfo(self, context, msg)
            return{'FINISHED'}
        
# save morph preset as json. 

def save_morphs(context, filepath, use_setting, data):
    print(type(filepath), filepath)
    print(data)
    with open(filepath, 'w', encoding ='utf-8') as f:
        json.dump(data, f)
        f.close()
    return{'FINISHED'}



class WIF_OT_saveDazMorph(bpy.types.Operator, ExportHelper):
    bl_idname = "export.morph_preset"
    bl_label = "Export Morph preset"
    bl_description = "Export morphs value as json"
    bl_options = {'UNDO'}
    
    filename_ext = ".json"
    filter_glob: StringProperty(
            default = "*.json",
            options = {'HIDDEN'},
            )
            
    use_setting: BoolProperty(
        name="Save daz morph as JSON",
        description="save daz morph as json preset",
        default=True,
    )
            
    morph_dic = {}
    
    def make_preset_dic(self, context):
        act = bpy.context.active_object
        self.morph_dic = {}
        for prop in act.keys():
            if prop[0: 2] == "Dz":
                self.morph_dic[prop] = round(act[prop], 2)
        
    def execute(self, context):
        dic = self.morph_dic
        save_morphs(context, self.filepath, False, dic)
        return{'FINISHED'} 
    
    def invoke(self, context, _event):
        blend_path = bpy.data.filepath
        js_path = blend_path[:-6]
        
        self.make_preset_dic(context)        
        
        context.window_manager.fileselect_add(self)
        self.filepath = js_path + "_preset" + ".json"     
        return {'RUNNING_MODAL'}
    
# import saved morph preset json

class WIF_OT_loadDazMorph(bpy.types.Operator, ImportHelper):
    bl_idname = "import.morphpreset"
    bl_label = "Import Morph preset"
    bl_description = "Import morph preset"
    bl_options = {'UNDO'}
    
    filename_ext = ".json"
    filename = "preset.json"

    filter_glob: StringProperty(
            default = "*.json; *.blend",
            options = {'HIDDEN'},
            )
            
    morph_dic = {}
    
    def import_mpreset(self, context, filepath, use_setting):
        with open(filepath, 'r', encoding ='utf-8') as f:
            self.morph_dic = json.load(f)
            f.close()
            
    def set_morphs (self, context, dic):
        act = bpy.context.active_object
        for prop in dic.keys():
            if prop in act:
                act[prop] = dic[prop]
        update_prop(context, act)
                

    def execute(self, context):
        self.import_mpreset(context, self.filepath, False)
        print(self.morph_dic)
        
        self.set_morphs(context, self.morph_dic)
        return{'FINISHED'}
        
    
    def invoke(self, context, _event):
        blend_path = bpy.data.filepath
        js_path = blend_path[:-6]       
        
        context.window_manager.fileselect_add(self)
        self.filepath = js_path + "_preset" + ".json"     
        return {'RUNNING_MODAL'}            
    
            
classes = (
    WIF_OT_addinfo,
    WIF_PT_dazBoneUtils,
    WIF_OT_changeDazBoneName,
    WIF_OT_returnDazBoneName,
    WIF_OT_SetFilePath,
    WIF_OT_ImportDazData,
    WIF_OT_adjustDazBonePos,
    WIF_OT_memorizeDefBone,
    WIF_OT_returnDefBone,
    WIF_OT_showBoneDots,
    WIF_OT_SelectChildBones,
    WIF_OT_DeselectChildBones,
    WIF_OT_flipBones,
    WIF_OT_addRoll,
    WIF_OT_saveDazMorph,
    WIF_OT_loadDazMorph
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
def unregister():
    unsetSceneprop()
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()