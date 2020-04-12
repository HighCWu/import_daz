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
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from .error import *
from .utils import *
from . import utils
from .settings import theSettings

#-------------------------------------------------------------
#   Morph selector
#-------------------------------------------------------------

class DAZ_OT_SelectAll(bpy.types.Operator):
    bl_idname = "daz.select_all"
    bl_label = "All"
    bl_description = "Select all"

    def execute(self, context):
        for item in context.scene.DazSelector:
            item.select = True
        return {'PASS_THROUGH'}
        

class DAZ_OT_SelectNone(bpy.types.Operator):
    bl_idname = "daz.select_none"
    bl_label = "None"
    bl_description = "Select none"

    def execute(self, context):
        for item in context.scene.DazSelector:
            item.select = False
        return {'PASS_THROUGH'}
        

class Selector(B.FilterString):
    defaultSelect = False
    
    def draw(self, context):
        scn = context.scene
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")
        self.layout.prop(self, "filter")       
        self.drawExtra(context)     
        self.layout.separator()
        items = [item for item in scn.DazSelector
                    if self.selectCondition(item) and 
                        self.filtered(item)]                                
        nitems = len(items)
        ncols = 6
        nrows = 24
        if nitems > ncols*nrows:
            nrows = nitems//ncols + 1
        else:
            ncols = nitems//nrows + 1
        cols = []
        for n in range(ncols):
            cols.append(items[0:nrows])
            items = items[nrows:]
        for m in range(nrows):
            row = self.layout.row()
            for col in cols:
                if m < len(col):
                    item = col[m]
                    row.prop(item, "select", text="")
                    row.label(text=item.text)
                else:                    
                    row.label(text="")


    def drawExtra(self, context):
        pass
        
        
    def selectCondition(self, item):
        return True


    def filtered(self, item):
        return (not self.filter or self.filter in item.text)


    def getSelectedItems(self, scn):
        return [item for item in scn.DazSelector 
            if item.select and 
            self.filtered(item) and
            self.selectCondition(item)]


    def getSelectedProps(self, scn):
        return [item.name for item in self.getSelectedItems(scn)]
        

    def invokeDialog(self, context):
        wm = context.window_manager
        ncols = len(context.scene.DazSelector)//24 + 1
        if ncols > 6:
            ncols = 6
        wm.invoke_props_dialog(self, width=ncols*180)
        return {'RUNNING_MODAL'}
    
    
    def invoke(self, context, event):
        scn = context.scene
        scn.DazSelector.clear()
        for idx,data in enumerate(self.getKeys(context)):
            prop,text,cat = data
            item = scn.DazSelector.add()
            item.name = prop
            item.text = text
            item.category = cat
            item.index = idx
            item.select = self.defaultSelect
        return self.invokeDialog(context)


class StandardSelector(Selector, B.StandardAllEnums):
    prefixes = {"All" : ["DzU", "DzE", "DzV"], 
                "Units" : ["DzU"], 
                "Expressions" : ["DzE"], 
                "Visemes" : ["DzV"]
               }

    def selectCondition(self, item):
        return (item.name[0:3] in self.prefixes[self.type])
     
    def draw(self, context):
        self.layout.prop(self, "type")
        Selector.draw(self, context)
        
    def getKeys(self, context):
        rig = getRigFromObject(context.object)
        prefixes = self.prefixes[self.type]
        return [(key,key[3:],"All") for key in rig.keys() if key[0:3] in prefixes]

    def invoke(self, context, event):
        self.type = "All"
        return Selector.invoke(self, context, event)


class CustomSelector(Selector, B.CustomEnums):

    def selectCondition(self, item):
        return (self.custom == "All" or item.category == self.custom)
     
    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def getKeys(self, context):
        rig = getRigFromObject(context.object)
        keys = []
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                key = morph.prop
                keys.append((key,key,cat.name))
        return keys

#------------------------------------------------------------------
#   Global lists of morph paths
#------------------------------------------------------------------

ShortForms = {
    "phmunits" : ["phmbrow", "phmcheek", "phmeye", "phmjaw", "phmlip", "phmmouth", "phmnos", "phmteeth", "phmtongue"],

    "ectrlunits" : ["ectrlbrow", "ectrlcheek", "ectrleye", "ectrljaw", "ectrllip", "ectrlmouth", "ectrlnos", "ectrlteeth", "ectrltongue"],

    "ctrlhands" : ["ctrllfinger", "ctrllhand", "ctrllthumb", "ctrllindex", "ctrllmid", "ctrllring", "ctrllpinky",
             "ctrlrfinger", "ctrlrhand", "ctrlrthumb", "ctrlrindex", "ctrlrmid", "ctrlrring", "ctrlrpinky"],

    "ctrltoes" : ["ctrllindextoe", "ctrllmidtoe", "ctrllringtoe", "ctrllpinkytoe",
            "ctrlrindextoe", "ctrlrmidtoe", "ctrlrringtoe", "ctrlrpinkytoe"],

    "pctrlhands" : ["pctrllfinger", "pctrllhand", "pctrllthumb", "pctrllindex", "pctrllmid", "pctrllring", "pctrllpinky",
             "pctrlrfinger", "pctrlrhand", "pctrlrthumb", "pctrlrindex", "pctrlrmid", "pctrlrring", "pctrlrpinky"],

    "pctrltoes" : ["pctrllindextoe", "pctrllmidtoe", "pctrllringtoe", "pctrllpinkytoe",
            "pctrlrindextoe", "pctrlrmidtoe", "pctrlrringtoe", "pctrlrpinkytoe"],
}
ShortForms["units"] = ShortForms["ectrlunits"] + ShortForms["phmunits"]

def getShortformList(item):
    if isinstance(item, list):
        return item
    else:
        return ShortForms[item]


theMorphFiles = {}
theMorphNames = {}

def setupMorphPaths(scn, force):
    global theMorphFiles, theMorphNames
    from collections import OrderedDict
    from .asset import getDazPaths, fixBrokenPath
    from .load_json import loadJson

    if theMorphFiles and not force:
        return
    theMorphFiles = {}
    theMorphNames = {}

    folder = os.path.join(os.path.dirname(__file__), "data/paths/")
    charPaths = {}
    files = list(os.listdir(folder))
    files.sort()
    for file in files:
        path = os.path.join(folder, file)
        struct = loadJson(path)
        charPaths[struct["name"]] = struct

    for char in charPaths.keys():
        charFiles = theMorphFiles[char] = {}

        for key,struct in charPaths[char].items():
            if key in ["name", "hd-morphs"]:
                continue
            type = key.capitalize()
            if type not in charFiles.keys():
                charFiles[type] = OrderedDict()
            typeFiles = charFiles[type]
            if type not in theMorphNames.keys():
                theMorphNames[type] = OrderedDict()
            typeNames = theMorphNames[type]

            if isinstance(struct["prefix"], list):
                prefixes = struct["prefix"]
            else:
                prefixes = [struct["prefix"]]
            folder = struct["path"]
            includes = getShortformList(struct["include"])
            excludes = getShortformList(struct["exclude"])
            if "exclude2" in struct.keys():
                excludes += getShortformList(struct["exclude2"])

            for dazpath in getDazPaths(scn):
                folderpath = os.path.join(dazpath, folder)
                if not os.path.exists(folderpath):
                    folderpath = fixBrokenPath(folderpath)
                if os.path.exists(folderpath):
                    files = list(os.listdir(folderpath))
                    files.sort()
                    for file in files:
                        fname,ext = os.path.splitext(file)
                        if ext not in [".duf", ".dsf"]:
                            continue
                        isright,name = isRightType(fname, prefixes, includes, excludes)
                        if isright:
                            fpath = os.path.join(folder, file)
                            typeFiles[name] = os.path.join(folderpath, file)
                            prop = BoolProperty(name=name, default=True)
                            setattr(bpy.types.Scene, "Daz"+name, prop)
                            typeNames[fname.lower()] = name


def isRightType(fname, prefixes, includes, excludes):
    string = fname.lower()
    ok = False
    for prefix in prefixes:
        n = len(prefix)
        if string[0:n] == prefix:
            ok = True
            name = fname[n:]
            break
    if not ok:
        return False, fname

    if includes == []:
        for exclude in excludes:
            if exclude in string:
                return False, name
        return True, name

    for include in includes:
        if (include in string or
            string[0:len(include)-1] == include[1:]):
            for exclude in excludes:
                if (exclude in string or
                    string[0:len(exclude)-1] == exclude[1:]):
                    return False, name
            return True, name
    return False, name


class DAZ_OT_Update(DazOperator):
    bl_idname = "daz.update_morph_paths"
    bl_label = "Update Morph Paths"
    bl_description = "Update paths to predefined morphs"
    bl_options = {'UNDO'}

    def run(self, context):
        setupMorphPaths(context.scene, True)


class DAZ_OT_SelectAllMorphs(DazOperator, B.TypeString, B.ValueBool):
    bl_idname = "daz.select_all_morphs"
    bl_label = "Select All"
    bl_description = "Select/Deselect all morphs in this section"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        names = theMorphNames[self.type]
        for name in names.values():
            scn["Daz"+name] = self.value

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

theLimitationsMessage = (
'''
Not all morphs were loaded correctly
due to Blender limitations.
See console for details.
''')

from .formula import PropFormulas

class LoadMorph(PropFormulas):

    useSoftLimits = True
    useShapekeysOnly = False
    useShapekeys = True
    useDrivers = True
    suppressError = False

    def __init__(self, mesh=None, rig=None):
        PropFormulas.__init__(self, rig)
        self.mesh = mesh


    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)


    def getObject(self):
        if self.rig:
            return self.rig
        elif self.mesh:
            return self.mesh


    def getSingleMorph(self, filepath, scn, occur=0):
        from .modifier import Morph, FormulaAsset, ChannelAsset
        from .readfile import readDufFile
        from .files import parseAssetFile
        from .driver import makeShapekeyDriver

        miss = False
        ob = self.getObject()
        if ob is None:
            return [],miss

        struct = readDufFile(filepath)
        asset = parseAssetFile(struct)
        props = []
        if asset is None:
            if theSettings.verbosity > 1:
                msg = ("Not a morph asset:\n  '%s'" % filepath)
                if self.suppressError:
                    print(msg)
                else:
                    raise DazError(msg)
            return [],miss

        skey = None
        prop = None
        if self.useShapekeys and isinstance(asset, Morph) and self.mesh and self.mesh.type == 'MESH':
            if asset.vertex_count != len(self.mesh.data.vertices):
                if theSettings.verbosity > 2:
                    msg = ("Vertex count mismatch:\n  %d != %d" % (asset.vertex_count, len(self.mesh.data.vertices)))
                    if self.suppressError:
                        print(msg)
                    else:
                        raise DazError(msg)
                return [],miss
            asset.buildMorph(self.mesh, ob.DazCharacterScale, self.useSoftLimits)
            skey,ob,sname = asset.rna
            if self.rig and theSettings.useDrivers:
                prop = propFromName(sname, self.type, self.prefix, self.rig)
                skey.name = prop
                min = skey.slider_min if theSettings.useDazPropLimits else None
                max = skey.slider_max if theSettings.useDazPropLimits else None
                makeShapekeyDriver(ob, prop, skey.value, self.rig, prop, min=min, max=max)
                props = [prop]

        if self.useDrivers and self.rig:
            from .formula import buildShapeFormula
            if isinstance(asset, FormulaAsset) and asset.formulas:
                if self.useShapekeys:
                    success = buildShapeFormula(asset, scn, self.rig, self.mesh, occur=occur)
                    if self.useShapekeysOnly and not success and skey:
                        print("Could not build shape formula", skey.name)
                    if not success:
                        miss = True
                if not self.useShapekeysOnly:
                    prop = asset.clearProp(self.prefix, self.rig)
                    self.taken[prop] = False
                    props = self.buildPropFormula(asset, filepath)
            elif isinstance(asset, ChannelAsset) and not self.useShapekeysOnly:
                prop = asset.clearProp(self.prefix, self.rig)
                self.taken[prop] = False
                props = []
                miss = True

        if props:
            for props in props:
                setActivated(self.rig, prop, True)
            return props,False
        elif skey:
            prop = skey.name
            setActivated(self.rig, prop, True)
            return [prop],miss
        else:
            return [],miss


def propFromName(key, type, prefix, rig):
    if prefix:
        names = theMorphNames[type]
        name = nameFromKey(key, names, rig)
        if name:
            prop = prefix+name
            return prop
    return key


class LoadShapekey(LoadMorph):

    useDrivers = False

#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class LoadAllMorphs(LoadMorph):

    suppressError = True

    def setupCharacter(self, context, rigIsMesh):
        from .finger import getFingeredCharacter
        ob = context.object
        self.rig, self.mesh, self.char = getFingeredCharacter(ob)
        if self.mesh is None and rigIsMesh:
            if self.rig.DazRig == "genesis3":
                self.char = "Genesis3-female"
                self.mesh = self.rig
                addDrivers = True
            elif self.rig.DazRig == "genesis8":
                self.char = "Genesis8-female"
                self.mesh = self.rig
                addDrivers = True
        if not self.char:
            from .error import invokeErrorMessage
            msg = ("Can not add morphs to this mesh:\n %s" % ob.name) 
            invokeErrorMessage(msg)
            return False
        return True
        

    def getMorphFiles(self):
        try:
            return theMorphFiles[self.char][self.type]
        except KeyError:
            return []


    def run(self, context):
        import time
        from .main import finishMain

        scn = context.scene
        setupMorphPaths(scn, False)
        addDrivers = (scn.DazAddFaceDrivers and not self.useShapekeysOnly)
        files = self.getActiveMorphFiles(context)
        self.rig["Daz"+self.type] = self.char
        self.mesh["Daz"+self.type] = self.char
        self.rig.DazNewStyleExpressions = True
        
        theSettings.forMorphLoad(self.mesh, scn, addDrivers)
        t1 = time.perf_counter()
        startProgress("\n--------------------\n%s" % self.type)
        nfiles = len(files)
        idx = 0
        snames = []
        missing = []
        for name,filepath in files.items():
            showProgress(idx, nfiles)
            idx += 1
            if self.isActive(name, scn):
                sname,miss = self.getSingleMorph(filepath, scn)
                if miss:
                    print("?", name)
                    missing.append((name,filepath))
                else:
                    snames += sname
                    print("*", name)
            else:
                print("-", name)
        self.buildOthers()

        updateDrivers(self.mesh)
        updateDrivers(self.rig)
        finishMain("", t1)
        if self.errors:
            print("but there were errors:")
            for err,struct in self.errors.items():
                print("%s:" % err)
                print("  Props: %s" % struct["props"])
                print("  Bones: %s" % struct["bones"])

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class DAZ_OT_ImportCorrectives(DazOperator, Selector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_correctives"
    bl_label = "Import Correctives"
    bl_description = "Import corrective morphs"
    bl_options = {'UNDO'}

    type = "Correctives"
    prefix = "DzC"
    useShapekeysOnly = True
    useSoftLimits = False
    
    def getActiveMorphFiles(self, context):
        return dict([(item.text,item.name) for item in self.getSelectedItems(context.scene)])        

    def isActive(self, name, scn):
        return True

    def invoke(self, context, event):
        global theMorphFiles
        scn = context.scene
        scn.DazSelector.clear()
        if not self.setupCharacter(context, False):
            return {'FINISHED'}
        setupMorphPaths(scn, False)
        for key,path in theMorphFiles[self.char]["Correctives"].items():
            item = scn.DazSelector.add()
            item.name = path
            item.text = key
            item.select = True
        return self.invokeDialog(context)

    
class StandardMorphSelector(Selector):
                
    def getActiveMorphFiles(self, context):
        return dict([(item.text,item.name) for item in self.getSelectedItems(context.scene)])        

    def isActive(self, name, scn):
        return True

    def selectCondition(self, item):
        return True

    def invoke(self, context, event):
        global theMorphFiles
        scn = context.scene
        scn.DazSelector.clear()
        if not self.setupCharacter(context, True):
            return {'FINISHED'}
        setupMorphPaths(scn, False)
        for key,path in theMorphFiles[self.char][self.type].items():
            item = scn.DazSelector.add()
            item.name = path
            item.text = key
            item.category = self.type
            item.select = True
        return self.invokeDialog(context)


class DAZ_OT_ImportUnits(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_units"
    bl_label = "Import Units"
    bl_description = "Import face unit morphs"
    bl_options = {'UNDO'}

    type = "Units"
    prefix = "DzU"


class DAZ_OT_ImportExpressions(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_expressions"
    bl_label = "Import Expressions"
    bl_description = "Import expression morphs"
    bl_options = {'UNDO'}

    type = "Expressions"
    prefix = "DzE"


class DAZ_OT_ImportVisemes(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_visemes"
    bl_label = "Import Visemes"
    bl_description = "Import viseme morphs"
    bl_options = {'UNDO'}

    type = "Visemes"
    prefix = "DzV"

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class DAZ_OT_ImportCustomMorphs(DazOperator, LoadMorph, B.DazImageFile, B.MultiFile, B.MorphStrings, IsMeshArmature):
    bl_idname = "daz.import_custom_morphs"
    bl_label = "Import Custom Morphs"
    bl_description = "Import morphs from native DAZ files (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    type = "Shapes"
    prefix = ""
    custom = "DazCustomMorphs"

    def draw(self, context):
        self.layout.prop(self, "useDrivers")
        self.layout.prop(self, "catname")


    def invoke(self, context, event):
        from .fileutils import getFolder
        from .finger import getFingeredCharacter
        self.rig, self.mesh, char = getFingeredCharacter(context.object)
        folder = getFolder(self.mesh, context.scene, ["Morphs/", ""])
        if folder is not None:
            self.properties.filepath = folder
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def run(self, context):
        from .driver import setBoolProp
        snames = self.getMorphs(self.filepath, context.scene)
        addToCategories(self.rig, snames, self.catname)
        if self.rig:
            setBoolProp(self.rig, self.custom, True)
        if self.mesh:
            setBoolProp(self.mesh, self.custom, True)
        if self.errors:
            raise DazError(theLimitationsMessage)


    def getMorphs(self, filepath, scn):
        import time
        from .asset import clearAssets
        from .main import finishMain
        from .fileutils import getMultiFiles

        if self.mesh:
            ob = self.mesh
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        theSettings.forMorphLoad(ob, scn, self.useDrivers)

        self.errors = {}
        t1 = time.perf_counter()
        startProgress("\n--------------------")
        snames = []
        missing = []
        paths = getMultiFiles(self, ["duf", "dsf"])
        npaths = len(paths)
        self.suppressError = (len(paths) > 1)
        for idx,path in enumerate(paths):
            showProgress(idx, npaths)
            file = os.path.basename(path)
            names,miss = self.getSingleMorph(path, scn)
            if miss:
                print("?", file)
                missing.append(path)
            elif names:
                print("*", file)
                snames += names
            else:
                print("-", file)

        for path in missing:
            names,miss = self.getSingleMorph(path, scn, occur=1)
            if names and not miss:
                print("*", file)
                snames += names
            elif names:
                print("-", file)

        updateDrivers(self.rig)
        updateDrivers(self.mesh)
        finishMain(filepath, t1)
        if self.errors:
            print("but there were errors:")
            for err,struct in self.errors.items():
                print("%s:" % err)
                print("  Props: %s" % struct["props"])
                print("  Bones: %s" % struct["bones"])

        return snames

#------------------------------------------------------------------------
#   Categories
#------------------------------------------------------------------------

def addToCategories(rig, snames, catname):
    from .driver import setBoolProp
    if snames and rig is not None:
        cats = dict([(cat.name,cat) for cat in rig.DazMorphCats])
        if catname not in cats.keys():
            cat = rig.DazMorphCats.add()
            cat.name = catname
        else:
            cat = cats[catname]
        setBoolProp(cat, "active", True)

        morphs = dict([(morph.prop,morph) for morph in cat.morphs])
        for sname in snames:
            if sname not in morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = morphs[sname]

            morph.prop = sname
            if sname[0:4].lower() == "ctrl":
                morph.name = sname[4:]
            elif sname[1:5].lower() == "ctrl":
                morph.name = sname[5:]
            else:
                morph.name = sname

#------------------------------------------------------------------------
#   Rename category
#------------------------------------------------------------------------

class DAZ_OT_RenameCategory(DazPropsOperator, B.CustomEnums, B.CategoryString, IsArmature):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def draw(self, context):
       self.layout.prop(self, "custom")
       self.layout.prop(self, "category", text="New Name")

    def run(self, context):
        from .driver import setBoolProp
        rig = context.object
        if self.custom == "All":
            raise DazError("Cannot rename all categories")
        cat = rig.DazMorphCats[self.custom]
        cat.name = self.category


def removeFromPropGroups(rig, prop, keep=False):             
    for pb in rig.pose.bones:
        removeFromPropGroup(pb.DazLocProps, prop)
        removeFromPropGroup(pb.DazRotProps, prop)
        removeFromPropGroup(pb.DazScaleProps, prop)

    if not keep:
        rig[prop] = 0
        del rig[prop]
        for ob in rig.children:
            if prop in ob.keys():
                ob[prop] = 0
                del ob[prop]


def removeFromPropGroup(pgrps, prop):
    idxs = []
    for n,pg in enumerate(pgrps):
        if pg.prop == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgrps.remove(n)            
            

class DAZ_OT_RemoveCategories(DazOperator, Selector, IsArmature):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    def run(self, context):
        from .driver import removePropDrivers
        items = [(item.index, item.name) for item in self.getSelectedItems(context.scene)]
        items.sort()
        items.reverse()
        rig = context.object
        for idx,key in items:
            cat = rig.DazMorphCats[key]
            for pg in cat.morphs:
                if pg.prop in rig.keys():
                    rig[pg.prop] = 0.0
                path = ('["%s"]' % pg.prop)
                keep = removePropDrivers(rig, path, rig)
                for ob in rig.children:
                    if ob.type == 'MESH':
                        if removePropDrivers(ob.data.shape_keys, path, rig):
                            keep = True
                if pg.prop in rig.keys():
                    removeFromPropGroups(rig, pg.prop, keep)
            rig.DazMorphCats.remove(idx)

        if len(rig.DazMorphCats) == 0:
            rig.DazCustomMorphs = False
            for ob in rig.children:
                if len(ob.DazMorphCats) == 0:
                    ob.DazCustomMorphs = False


    def selectCondition(self, item):
        return True


    def getKeys(self, context):
        rig = getRigFromObject(context.object)
        keys = []
        for cat in rig.DazMorphCats:
            key = cat.name
            keys.append((key,key,key))
        return keys

#------------------------------------------------------------------------
#   Apply morphs
#------------------------------------------------------------------------

def getShapeKeyCoords(ob):
    coords = [v.co for v in ob.data.vertices]
    skeys = []
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if abs(skey.value) > 1e-4:
                coords = [co + skey.value*(skey.data[n].co - ob.data.vertices[n].co) for n,co in enumerate(coords)]
            skeys.append(skey)
    return skeys,coords


def applyMorphs(rig, props):
    for ob in rig.children:
        basic = ob.data.shape_keys.key_blocks[0]
        skeys,coords = getShapeKeyCoords(ob)
        for skey in skeys:
            path = 'key_blocks["%s"].value' % skey.name
            getDrivingProps(ob.data.shape_keys, path, props)
            ob.shape_key_remove(skey)
        basic = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(basic)
        for vn,co in enumerate(coords):
            ob.data.vertices[vn].co = co
    print("Morphs applied")


def getDrivingProps(rna, channel, props):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = trg.data_path.split('"')[1]
                    props[prop] = trg.id


def removeDrivingProps(rig, props):
    for prop,id in props.items():
        if rig == id:
            del rig[prop]
    for cat in rig.DazCategories:
        rig.DazCategories.remove(cat)

#------------------------------------------------------------------------
#   Select and unselect all
#------------------------------------------------------------------------

class Activator(B.PrefixString, B.TypeString):
    def run(self, context):
        from .driver import setBoolProp
        rig = getRigFromObject(context.object)
        keys = getRelevantMorphs(rig, self.type, self.prefix)
        if self.type == "CUSTOM":
            for key in keys:
                setActivated(rig, key.prop, self.activate)
        else:
            for key in keys:
                setActivated(rig, key, self.activate)


def setActivated(rig, key, value):
    if rig is None:
        return
    pg = getActivateGroup(rig, key)
    pg.active = value


def getActivated(rig, key, force=False):
    if key not in rig.keys():
        return False
    elif force:
        return True
    else:
        pg = getActivateGroup(rig, key)
        return pg.active
        

def getExistingActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        return None
        
        
def getActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        pg = rig.DazActivated.add()
        pg.name = key
        return pg


class DAZ_OT_ActivateAll(DazOperator, Activator):
    bl_idname = "daz.activate_all"
    bl_label = "Select All"
    bl_description = "Select all morphs of this type"
    bl_options = {'UNDO'}

    activate = True


class DAZ_OT_DeactivateAll(DazOperator, Activator):
    bl_idname = "daz.deactivate_all"
    bl_label = "Unselect All"
    bl_description = "Unselect all morphs of this type"
    bl_options = {'UNDO'}

    activate = False

#------------------------------------------------------------------------
#   Prettifying
#------------------------------------------------------------------------

def prettifyAll(context):
    scn = context.scene
    for ob in getSceneObjects(context):
        if ob.type == 'ARMATURE':
            for prop in ob.keys():
                if prop[0:7] == "DazShow":
                    setattr(bpy.types.Object, prop, BoolProperty(default=True))
                elif prop[0:3] in ["Mhh", "DzM"]:
                    setattr(bpy.types.Object, prop, BoolProperty(default=True))                            


class DAZ_OT_Prettify(DazOperator):
    bl_idname = "daz.prettify"
    bl_label = "Prettify Panels"
    bl_description = (
        "Change sliders to checkboxes\n" +
        "(If boolean options appear as sliders, use this button to refresh them)"
        )
    bl_options = {'UNDO'}

    def run(self, context):
        prettifyAll(context)

#------------------------------------------------------------------
#   Update scene
#------------------------------------------------------------------

class DAZ_OT_ForceUpdate(DazOperator):
    bl_idname = "daz.force_update"
    bl_label = "Update"
    bl_description = "Force all morphs to update"
    bl_options = {'UNDO'}

    def run(self, context):
        updateScene(context)
        rig = getRigFromObject(context.object)
        updateRig(rig, context)
        updateDrivers(context.object)

#------------------------------------------------------------------
#   Clear morphs
#------------------------------------------------------------------

def getRelevantMorphs(rig, type, prefix):
    morphs = []
    if rig is None:
        return morphs
    if type == "CUSTOM":
        for cat in rig.DazMorphCats:
            morphs += cat.morphs
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix:
                morphs.append(key)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                morphs.append(key)
    return morphs


def clearMorphs(rig, type, prefix, scn, frame, force):
    keys = getRelevantMorphs(rig, type, prefix)

    if type == "CUSTOM":
        for key in keys:
            if getActivated(rig, key.prop, force) and not rig[key.prop] == 0.0:
                rig[key.prop] = 0.0
                autoKeyProp(rig, key.prop, scn, frame, force)
    else:
        for key in keys:
            if getActivated(rig, key, force) and not rig[key] == 0.0:
                rig[key] = 0.0
                autoKeyProp(rig, key, scn, frame, force)


def updateMorphs(rig, type, prefix, scn, frame, force):
    keys = getRelevantMorphs(rig, type, prefix)
    for key in keys:
        if getActivated(rig, key):
            autoKeyProp(rig, key, scn, frame, force)


def nameFromKey(key, names, rig):
    key = key.lower()
    if rig.DazRig == "genesis8":
        keyhd = key + "_hd"
        if keyhd in names.keys():
            return names[keyhd]
        elif "e"+keyhd in names.keys():
            return names["e"+keyhd]
    if key in names.keys():
        return names[key]
    elif "e"+key in names.keys():
        return names["e"+key]
    else:
        for end1,end2 in [("in-out", "out-in")]:
            n = len(end1)
            for prefix in ["e", ""]:
                stem = prefix+key[:-n]
                if key[-n:] == end1 and stem+end2 in names.keys():
                    return names[stem+end2]
                elif key[-n:] == end2 and stem+end1 in names.keys():
                    return names[stem+end1]
    return None


class DAZ_OT_ClearMorphs(DazOperator, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear"
    bl_description = "Set all morphs of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            clearMorphs(rig, self.type, self.prefix, scn, scn.frame_current, False)
            updateRig(rig, context)
            if scn.tool_settings.use_keyframe_insert_auto:
                updateScene(context)


class DAZ_OT_UpdateMorphs(DazOperator, B.KeyString, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.update_morphs"
    bl_label = "Update"
    bl_description = "Set keys at current frame for all props of specified type with keys"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            updateMorphs(rig, self.type, self.prefix, scn, scn.frame_current)
            updateScene(context)
            updateRig(rig, context)

#------------------------------------------------------------------
#   Add morphs to keyset
#------------------------------------------------------------------

def addKeySet(rig, type, prefix, scn, frame):
    if rig is None:
        return
    aksi = scn.keying_sets.active_index
    if aksi <= -1:
        aks = scn.keying_sets.new(idname = "daz_morphs", name = "daz_morphs")
    aks = scn.keying_sets.active
    if type == "CUSTOM":
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                path = "[" + '"' + morph.prop + '"' + "]"
                aks.paths.add(rig.id_data, path)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix:
                path = "[" + '"' + key + '"' + "]"
                aks.paths.add(rig.id_data, path)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                path = "[" + '"' + key + '"' + "]"
                aks.paths.add(rig.id_data, path)


class DAZ_OT_AddKeysets(DazOperator, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add category morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    def run(self, context):
        from .finger import getFingeredCharacter
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            addKeySet(rig, self.type, self.prefix, scn, scn.frame_current)
            updateScene(context)
            updateRig(rig, context)

#------------------------------------------------------------------
#   Set morph keys
#------------------------------------------------------------------

def keyMorphs(rig, type, prefix, scn, frame):
    if rig is None:
        return
    if type == "CUSTOM":
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if getActivated(rig, morph.prop):
                    keyProp(rig, morph.prop, frame)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix and getActivated(rig, key):
                keyProp(rig, key, frame)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                keyProp(rig, key, frame)


class DAZ_OT_KeyMorphs(DazOperator, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            keyMorphs(rig, self.type, self.prefix, scn, scn.frame_current)
            updateScene(context)
            updateRig(rig, context)

#------------------------------------------------------------------
#   Remove morph keys
#------------------------------------------------------------------

def unkeyMorphs(rig, type, prefix, scn, frame):
    if rig is None:
        return
    if type == "CUSTOM":
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if getActivated(rig, morph.prop):
                    unkeyProp(rig, morph.prop, frame)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix and getActivated(rig, key):
                unkeyProp(rig, key, frame)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                unkeyProp(rig, key, frame)


class DAZ_OT_UnkeyMorphs(DazOperator, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig and rig.animation_data and rig.animation_data.action:
            scn = context.scene
            unkeyMorphs(rig, self.type, self.prefix, scn, scn.frame_current)
            updateScene(context)
            updateRig(rig, context)

#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

def getCustomProps(ob):
    props = []
    for cat in ob.DazMorphCats:
        props += [morph.prop for morph in cat.morphs]
    return props


def updatePropLimits(rig, context):
    from .driver import getShapekeyBoneDriver, setFloatProp
    scn = context.scene
    min = scn.DazPropMin
    max = scn.DazPropMax
    props = getCustomProps(rig)
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.shape_keys:
            for skey in ob.data.shape_keys.key_blocks:
                if skey.name in props or skey.name[0:2] == "Dz":
                    skey.slider_min = min
                    skey.slider_max = max

    for prop in rig.keys():
        if (prop in props or 
            (prop[0:2] == "Dz" and prop[0:3] != "DzA")):
            setFloatProp(rig, prop, rig[prop], min, max)
    updateScene(context)
    updateRig(rig, context)
    print("Property limits updated")


class DAZ_OT_UpdatePropLimits(DazOperator, IsMeshArmature):
    bl_idname = "daz.update_prop_limits"
    bl_label = "Update Property Limits"
    bl_description = "Update min and max value for properties"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            updatePropLimits(rig, context)

#------------------------------------------------------------------
#   Remove all morph drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllMorphDrivers(DazOperator, IsMeshArmature):
    bl_idname = "daz.remove_all_morph_drivers"
    bl_label = "Remove All Morph Drivers"
    bl_description = "Remove drivers associated with morphs (not corrective shapekeys)"
    bl_options = {'UNDO'}

    def run(self, context):
        from .driver import removeRigDrivers, removePropDrivers
        rig = getRigFromObject(context.object)
        scn = context.scene
        prefix = "Dz"
        if rig:
            setupMorphPaths(scn, False)
            removeRigDrivers(rig)
            self.removeSelfRefs(rig)
            self.removeAllProps(rig)
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    removePropDrivers(ob.data.shape_keys)
                    self.removeAllProps(ob)
            updateScene(context)
            updateRig(rig, context)


    def removeSelfRefs(self, rig):
        for pb in rig.pose.bones:
            if len(pb.constraints) > 0:
                cns = pb.constraints[0]
                if (cns.mute and
                    cns.name == "Do Not Touch"):
                    pb.constraints.remove(cns)


    def removeAllProps(self, ob):
        ob.DazCustomMorphs = False
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                key = morph.prop
                if key in ob.keys():
                    ob[key] = 0.0
                    del ob[key]

        for key in ob.keys():
            if key[0:2] == "Dz":
                ob[key] = 0.0
                del ob[key]
        
        for mtype in theMorphNames.keys():
            key = "Daz"+mtype
            if key in ob.keys():
                ob[key] = False
                del ob[key]

#-------------------------------------------------------------
#   Remove specific morphs
#-------------------------------------------------------------

class MorphRemover(B.DeleteShapekeysBool):
    def run(self, context):
        from .driver import removePropDrivers
        rig = getRigFromObject(context.object)
        scn = context.scene
        if rig:
            props = self.getSelectedProps(scn)
            print("Remove", props)            
            paths = ['["%s"]' % prop for prop in props]
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    removePropDrivers(ob.data.shape_keys, paths, rig)
                    if self.deleteShapekeys:
                        for prop in props:
                            if prop in ob.data.shape_keys.key_blocks.keys():
                                skey = ob.data.shape_keys.key_blocks[prop]
                                ob.shape_key_remove(skey)
            for prop in props:
                removeFromPropGroups(rig, prop)
            self.finalize(rig)
            updateScene(context)
            updateRig(rig, context)


class DAZ_OT_RemoveStandardMorphs(DazOperator, StandardSelector, MorphRemover, IsMeshArmature):
    bl_idname = "daz.remove_standard_morphs"
    bl_label = "Remove Standard Morphs"
    bl_description = "Remove specific standard morphs and their associated drivers"
    bl_options = {'UNDO'}

    shows = {"All" : ["DazUnits", "DazExpressions", "DazVisemes"], 
             "Units" : ["DazUnits"], 
             "Expressions" : ["DazExpressions"], 
             "Visemes" : ["DazVisemes"]
            }

    def drawExtra(self, context):
        self.layout.prop(self, "deleteShapekeys")
        
    def finalize(self, rig):
        return
        if self.selectAll:
            for show in self.shows[self.type]:
                setattr(rig, show, "")
            for ob in rig.children:
                for show in self.shows[self.type]:
                    setattr(ob, show, "")


class DAZ_OT_RemoveCustomMorphs(DazOperator, CustomSelector, MorphRemover, IsMeshArmature):
    bl_idname = "daz.remove_custom_morphs"
    bl_label = "Remove Custom Morphs"
    bl_description = "Remove specific custom morphs and their associated drivers"
    bl_options = {'UNDO'}

    def drawExtra(self, context):
        self.layout.prop(self, "deleteShapekeys")

    def finalize(self, rig):
        return
        if self.selectAll:
            if self.custom == "All":
                for cat in rig.DazMorphCats:
                    self.deleteCategory(rig, cat)
            else:
                cat = rig.DazMorphCats[self.custom]                
                self.deleteCategory(rig, cat)


    def deleteCategory(self, rig, cat):
        for n,cat1 in enumerate(rig.DazMorphCats):
            if cat == cat1:
                rig.DazMorphCats.remove(n)
                return

#-------------------------------------------------------------
#   Add and remove driver
#-------------------------------------------------------------

class AddRemoveDriver:

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            for sname in self.getSelectedProps(context.scene):
                self.handleShapekey(sname, rig, ob)
            updateDrivers(rig)

        
    def invoke(self, context, event):
        context.scene.DazSelector.clear()
        ob = context.object
        scn = context.scene
        if ob.data.shape_keys:
            for skey in ob.data.shape_keys.key_blocks[1:]:
                item = scn.DazSelector.add()
                item.name = item.text = skey.name
                item.select = False
        return self.invokeDialog(context)


class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, B.CategoryString, IsMesh):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)

    def handleShapekey(self, sname, rig, ob):                    
        from .driver import makeShapekeyDriver
        skey = ob.data.shape_keys.key_blocks[sname]
        makeShapekeyDriver(ob, sname, skey.value, rig, sname)
        addToCategories(rig, [sname], self.category)
        ob.DazCustomMorphs = True
        rig.DazCustomMorphs = True


class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, IsMesh):
    bl_idname = "daz.remove_shapekey_drivers"
    bl_label = "Remove Shapekey Drivers"
    bl_description = "Remove rig drivers from shapekeys"
    bl_options = {'UNDO'}

    def handleShapekey(self, sname, rig, ob):                    
        #skey = ob.data.shape_keys.key_blocks[sname]
        self.removeShapekeyDriver(ob, sname)
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE' and
            sname in rig.keys()):
            del rig[sname]

    def removeShapekeyDriver(self, ob, sname):
        adata = ob.data.shape_keys.animation_data
        if (adata and adata.drivers):
            for fcu in adata.drivers:
                words = fcu.data_path.split('"')
                if (words[0] == "key_blocks[" and
                    words[1] == sname):
                    ob.data.shape_keys.driver_remove(fcu.data_path)
                    return
        #raise DazError("Did not find driver for shapekey %s" % skey.name)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getRigFromObject(ob):
    if ob.type == 'ARMATURE':
        return ob
    else:
        ob = ob.parent
        if ob is None or ob.type != 'ARMATURE':
            return None
        return ob


class DAZ_OT_ToggleAllCats(DazOperator, B.UseOpenBool, IsMeshArmature):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            for cat in rig.DazMorphCats:
                cat.active = self.useOpen

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def keyProp(rig, key, frame):
    rig.keyframe_insert('["%s"]' % key, frame=frame)


def unkeyProp(rig, key, frame):
    rig.keyframe_delete('["%s"]' % key, frame=frame)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = '["%s"]' % key
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def pinProp(rig, scn, key, type, prefix, frame):
    if rig:
        clearMorphs(rig, type, prefix, scn, frame, True)
        rig[key] = 1.0
        autoKeyProp(rig, key, scn, frame, True)


class DAZ_OT_PinProp(DazOperator, B.KeyString, B.TypePrefix, IsMeshArmature):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        scn = context.scene
        setupMorphPaths(scn, False)
        pinProp(rig, scn, self.key, self.type, self.prefix, scn.frame_current)
        updateScene(context)
        updateRig(rig, context)

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

Moho = {
    "rest" : "Rest",
    "etc" : "K",
    "AI" : "AA",
    "O" : "OU",
    "U" : "OW",
    "WQ" : "AH",
    "L" : "L",
    "E" : "EH",
    "MBP" : "M",
    "FV" : "F"
}

def getVisemesPrefix(rig):
    return Visemes[rig.DazVisemes][2]


def loadMoho(context, filepath, offs):
    from .fileutils import safeOpen
    scn = context.scene
    ob = context.object
    if ob.type == 'ARMATURE':
        rig = ob
    elif ob.type == 'MESH':
        rig = ob.parent
    else:
        rig = None
    if rig is None:
        return
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='POSE')
    if rig.DazNewStyleExpressions:
        vprefix = "DzV"
        prefix = "DzV"
    else:
        vprefix = getVisemesPrefix(rig)
        prefix = ""
    auto = scn.tool_settings.use_keyframe_insert_auto
    scn.tool_settings.use_keyframe_insert_auto = True
    fp = safeOpen(filepath, "rU")
    for line in fp:
        words= line.split()
        if len(words) < 2:
            pass
        else:
            frame = int(words[0]) + offs
            if words[1] == "rest":
                clearMorphs(rig, "Visemes", prefix, None, scn, frame, True)
            else:
                key = vprefix + Moho[words[1]]
                print("MOI", frame, words[1], key)
                pinProp(rig, scn, key, "Visemes", prefix, None, frame)
    fp.close()
    #setInterpolation(rig)
    updateScene(context)
    updateRig(rig, context)
    scn.tool_settings.use_keyframe_insert_auto = auto
    print("Moho file %s loaded" % filepath)


class DAZ_OT_LoadMoho(DazOperator, B.DatFile, B.SingleFile):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

    def run(self, context):
        loadMoho(context, self.filepath, 1.0)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# ---------------------------------------------------------------------
#   Delete lipsync
# ---------------------------------------------------------------------

def getArmature(ob):
    if ob.type == 'MESH':
        ob = ob.parent
    if ob and ob.type == 'ARMATURE':
        return ob
    return None


def deleteLipsync(rig):
    if rig.animation_data is None:
        return
    act = rig.animation_data.action
    if act is None:
        return
    if rig.MhxFaceShapeDrivers:
        for fcu in act.fcurves:
            if (fcu.data_path[0:5] == '["Mhf' and
                fcu.data_path[5:9] in ["mout", "lips", "tong"]):
                    act.fcurves.remove(fcu)
        for key in getMouthShapes():
            rig["Mhf"+key] = 0.0
    elif rig.MhxFacePanel:
        for key in getMouthShapes():
            pb,_fac,idx = getBoneFactor(rig, key)
            path = 'pose.bones["%s"].location' % pb.name
            for fcu in act.fcurves:
                if fcu.data_path == path:
                    act.fcurves.remove(fcu)
                    pb.location[idx] = 0.0


class DAZ_OT_DeleteLipsync(DazOperator):
    bl_idname = "daz.delete_lipsync"
    bl_label = "Delete Lipsync"
    bl_description = "Delete F-curves associated with lipsync"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getArmature(context.object)
        if rig:
            deleteLipsync(rig)
        updateScene(context)
        updateRig(rig, context)

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class MorphsToShapes:
    def run(self, context):
        ob = context.object
        rig = ob.parent
        if rig is None or rig.type != 'ARMATURE':
            return
        items = self.getSelectedItems(context.scene)
        nitems = len(items)
        startProgress("Convert morphs to shapekeys")
        for n,item in enumerate(items):
            showProgress(n, nitems)
            key = item.name
            mname = item.text            
            rig[key] = 0.0
            if (ob.data.shape_keys and 
                mname in ob.data.shape_keys.key_blocks.keys()):
                print("Skip", mname)
                continue
            if mname:
                for mod in ob.modifiers:
                    if mod.type == 'ARMATURE':
                        rig[key] = 1.0
                        updateScene(context)
                        updateRig(rig, context)
                        self.applyArmature(ob, rig, mod, mname)
                        rig[key] = 0.0
                        break
        updateScene(context)
        updateRig(rig, context)
        updateDrivers(rig)
    

    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        skey = ob.data.shape_keys.key_blocks[mname]
        skey.value = 0.0
        offsets = [(skey.data[vn].co - v.co).length for vn,v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * ob.DazScale    # eps = 0.1 mm
        if abs(omax) < eps and abs(omin) < eps:
            idx = ob.data.shape_keys.key_blocks.keys().index(skey.name)
            ob.active_shape_key_index = idx
            bpy.ops.object.shape_key_remove()
            ob.active_shape_key_index = 0
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True   
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)


class DAZ_OT_ConvertStandardMorphsToShapes(DazOperator, StandardSelector, MorphsToShapes, IsMesh):
    bl_idname = "daz.convert_standard_morphs_to_shapekeys"
    bl_label = "Convert Standard Morphs To Shapekeys"
    bl_description = "Convert standard face rig morphs to shapekeys"
    bl_options = {'UNDO'}


class DAZ_OT_ConvertCustomMorphsToShapes(DazOperator, CustomSelector, MorphsToShapes, IsMesh):
    bl_idname = "daz.convert_custom_morphs_to_shapekeys"
    bl_label = "Convert Custom Morphs To Shapekeys"
    bl_description = "Convert custom rig morphs to shapekeys"
    bl_options = {'UNDO'}


#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

classes = [
    DAZ_OT_SelectAll,
    DAZ_OT_SelectNone,
    
    DAZ_OT_Update,
    DAZ_OT_SelectAllMorphs,
    DAZ_OT_ImportUnits,
    DAZ_OT_ImportExpressions,
    DAZ_OT_ImportVisemes,
    #DAZ_OT_ImportStandardMorphs,
    DAZ_OT_ImportCustomMorphs,
    DAZ_OT_ImportCorrectives,
    DAZ_OT_RenameCategory,
    DAZ_OT_RemoveCategories,
    DAZ_OT_Prettify,
    DAZ_OT_ForceUpdate,
    DAZ_OT_ActivateAll,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_UpdateMorphs,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_UpdatePropLimits,
    DAZ_OT_RemoveStandardMorphs,
    DAZ_OT_RemoveCustomMorphs,
    DAZ_OT_RemoveAllMorphDrivers,
    DAZ_OT_AddShapekeyDrivers,
    DAZ_OT_RemoveShapekeyDrivers,
    DAZ_OT_ToggleAllCats,
    DAZ_OT_PinProp,
    DAZ_OT_LoadMoho,
    DAZ_OT_DeleteLipsync,
    DAZ_OT_ConvertStandardMorphsToShapes,
    DAZ_OT_ConvertCustomMorphsToShapes,        
]

def initialize():
    bpy.utils.register_class(B.DazSelectGroup)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazCustomMorphs = BoolProperty(default = False)
    bpy.types.Object.DazCustomPoses = BoolProperty(default = False)

    bpy.utils.register_class(B.DazCustomGroup)
    bpy.utils.register_class(B.DazCategory)
    bpy.utils.register_class(B.DazActiveGroup)
    
    bpy.types.Object.DazActivated = CollectionProperty(type = B.DazActiveGroup)
    bpy.types.Object.DazMorphCats = CollectionProperty(type = B.DazCategory)
    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items = [],
        name = "Morph")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name = "New Name",
        default = "Name")

    bpy.types.Scene.DazSelector = CollectionProperty(type = B.DazSelectGroup)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(B.DazCustomGroup)
    bpy.utils.unregister_class(B.DazCategory)
    bpy.utils.unregister_class(B.DazSelectGroup)
    
    
