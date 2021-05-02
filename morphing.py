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


import os
import bpy

from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from .error import *
from .utils import *
from .fileutils import SingleFile, MultiFile, DazImageFile, DatFile
from .propgroups import DazTextGroup, DazFloatGroup, DazStringGroup
from .load_morph import LoadMorph
from .driver import DriverUser

#-------------------------------------------------------------
#   Morph sets
#-------------------------------------------------------------

theStandardMorphSets = ["Standard", "Units", "Expressions", "Visemes", "Head", "Facs", "Facsexpr", "Body"]
theCustomMorphSets = ["Custom"]
theJCMMorphSets = ["Jcms", "Flexions"]
theMorphSets = theStandardMorphSets + theCustomMorphSets + theJCMMorphSets + ["Visibility"]


def getMorphs0(ob, morphset, sets, category):
    if morphset == "All":
        return getMorphs0(ob, sets, None, category)
    elif isinstance(morphset, list):
        pgs = []
        for mset in morphset:
            pgs += getMorphs0(ob, mset, sets, category)
        return pgs
    elif sets is None or morphset in sets:
        if morphset == "Custom":
            if category:
                if isinstance(category, list):
                    cats = category
                elif isinstance(category, str):
                    cats = [category]
                else:
                    raise DazError("Category must be a string or list but got '%s'" % category)
                pgs = [cat.morphs for cat in ob.DazMorphCats if cat.name in cats]
            else:
                pgs = [cat.morphs for cat in ob.DazMorphCats]
            return pgs
        else:
            pg = getattr(ob, "Daz"+morphset)
            prunePropGroup(ob, pg, morphset)
            return [pg]
    else:
        raise DazError("BUG getMorphs: %s %s" % (morphset, sets))


def prunePropGroup(ob, pg, morphset):
    if morphset in theJCMMorphSets:
        return
    idxs = [n for n,item in enumerate(pg.values()) if item.name not in ob.keys()]
    if idxs:
        print("Prune", idxs, [item.name for item in pg.values()])
        idxs.reverse()
        for idx in idxs:
            pg.remove(idx)


def getAllLowerMorphNames(rig):
    props = []
    for cat in rig.DazMorphCats:
        props += [morph.name.lower() for morph in cat.morphs]
    for morphset in theStandardMorphSets:
        pg = getattr(rig, "Daz"+morphset)
        props += [prop.lower() for prop in pg.keys()]
    return props


def getMorphList(ob, morphset, sets=None):
    pgs = getMorphs0(ob, morphset, sets, None)
    mlist = []
    for pg in pgs:
        mlist += list(pg.values())
    mlist.sort()
    return mlist


def getMorphCategory(rig, prop):
    for cat in rig.DazMorphCats:
        if prop in cat.morphs.keys():
            return cat.name
    return "Shapes"


def getMorphs(ob, morphset, category=None, activeOnly=False):
    """getMorphs(ob, type, category=None, activeOnly=False)
    Get all morph names and values of the specified type from the object.

    Returns:
    A dictonary of morph names - morph values for all morphs in the specified morphsets.

    Arguments:
    ?ob: Object (armature or mesh) which owns the morphs

    ?type: Either a string in ["Units", "Expressions", "Visemes", "Facs", "Facsexpr", "Body", "Custom", "Jcms", "Flexions"],
        or a list of such strings, or the keyword "All" signifying all morphset in the list.

    ?category (optional): The category name for Custom morphs.

    ?activeOnly (optional): Active morphs only (default False).
    """

    def isActiveKey(key, rig):
        if rig:
            return (key in rig.DazActivated.keys() and
                    rig.DazActivated[key].active)
        else:
            return True

    if not isinstance(ob, bpy.types.Object):
        raise DazError("getMorphs: First argument must be a Blender object, but got '%s'" % ob)
    morphset = morphset.capitalize()
    if morphset == "All":
        morphset = theMorphSets
    elif morphset not in theMorphSets:
        raise DazError("getMorphs: Morphset must be 'All' or one of %s, not '%s'" % (theMorphSets, morphset))
    pgs = getMorphs0(ob, morphset, None, category)
    mdict = {}
    rig = None
    if ob.type == 'ARMATURE':
        if activeOnly:
            rig = ob
        #if morphset in theJCMMorphSets:
        #    raise DazError("JCM morphs are stored in the mesh object")
        for pg in pgs:
            for key in pg.keys():
                if key in ob.keys() and isActiveKey(key, rig):
                    mdict[key] = ob[key]
    elif ob.type == 'MESH':
        if activeOnly:
            rig = ob.parent
        #if morphset not in theJCMMorphSets:
        #    raise DazError("Only JCM morphs are stored in the mesh object")
        skeys = ob.data.shape_keys
        if skeys is None:
            return mdict
        for pg in pgs:
            for key in pg.keys():
                if key in skeys.key_blocks.keys() and isActiveKey(key, rig):
                    mdict[key] = skeys.key_blocks[key].value
    return mdict


def addToMorphSet(ob, morphset, prop, asset=None, hidden=False, hideable=True):
    from .modifier import getCanonicalKey
    pg = getattr(ob, "Daz"+morphset)
    if prop in pg.keys():
        item = pg[prop]
    else:
        item = pg.add()
    item.name = prop
    if asset and asset.name == prop:
        label = asset.label
        visible = asset.visible
    else:
        label = getCanonicalKey(prop)
        visible = True
    if hideable and (hidden or not visible):
        item.text = "[%s]" % label
    else:
        item.text = label
    return prop

#-------------------------------------------------------------
#   Classes
#-------------------------------------------------------------

class MorphsetString:
    morphset : StringProperty(default = "")
    category : StringProperty(default = "")
    prefix : StringProperty(default = "")


class CategoryString:
    category : StringProperty(
        name = "Category",
        description = "Add morphs to this category of custom morphs",
        default = "Shapes"
        )


def getActiveCategories(scn, context):
    ob = context.object
    cats = [(cat.name,cat.name,cat.name) for cat in ob.DazMorphCats]
    cats.sort()
    return [("All", "All", "All")] + cats


class CustomEnums:
    custom : EnumProperty(
        items = getActiveCategories,
        name = "Category")


class DazSelectGroup(bpy.types.PropertyGroup):
    text : StringProperty()
    category : StringProperty()
    index : IntProperty()
    select : BoolProperty()

    def __lt__(self, other):
        return (self.text < other.text)


if bpy.app.version < (2,90,0):
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False)

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True)
else:
    class DazCategory(bpy.types.PropertyGroup):
        custom : StringProperty()
        morphs : CollectionProperty(type = DazTextGroup)
        active : BoolProperty(default=False, override={'LIBRARY_OVERRIDABLE'})

    class DazActiveGroup(bpy.types.PropertyGroup):
        active : BoolProperty(default=True, override={'LIBRARY_OVERRIDABLE'})

#-------------------------------------------------------------
#   Morph selector
#-------------------------------------------------------------

def getSelector():
    global theSelector
    return theSelector

def setSelector(selector):
    global theSelector
    theSelector = selector


class DAZ_OT_SelectAll(bpy.types.Operator):
    bl_idname = "daz.select_all"
    bl_label = "All"
    bl_description = "Select all"

    def execute(self, context):
        getSelector().selectAll(context)
        return {'PASS_THROUGH'}


class DAZ_OT_SelectNone(bpy.types.Operator):
    bl_idname = "daz.select_none"
    bl_label = "None"
    bl_description = "Select none"

    def execute(self, context):
        getSelector().selectNone(context)
        return {'PASS_THROUGH'}


class Selector():
    selection : CollectionProperty(type = DazSelectGroup)

    filter : StringProperty(
        name = "Filter",
        description = "Show only items containing this string",
        default = ""
        )

    defaultSelect = False
    columnWidth = 180
    ncols = 6
    nrows = 20

    def draw(self, context):
        scn = context.scene
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")
        self.layout.prop(self, "filter", icon='VIEWZOOM', text="")
        self.drawExtra(context)
        self.layout.separator()
        items = [item for item in self.selection if self.isSelected(item)]
        items.sort()
        nitems = len(items)
        ncols = self.ncols
        nrows = self.nrows
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


    def selectAll(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = True


    def selectNone(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = False


    def isSelected(self, item):
        return (self.selectCondition(item) and self.filtered(item))


    def selectCondition(self, item):
        return True


    def filtered(self, item):
        return (not self.filter or self.filter.lower() in item.text.lower())


    def getSelectedItems(self):
        return [item for item in self.selection if item.select and self.isSelected(item)]


    def getSelectedProps(self):
        from .fileutils import getSelection
        if getSelection():
            return getSelection()
        else:
            return [item.name for item in self.getSelectedItems()]


    def invokeDialog(self, context):
        setSelector(self)
        from .fileutils import clearSelection
        clearSelection()
        wm = context.window_manager
        ncols = len(self.selection)//self.nrows + 1
        if ncols > self.ncols:
            ncols = self.ncols
        wm.invoke_props_dialog(self, width=ncols*self.columnWidth)
        return {'RUNNING_MODAL'}


    def invoke(self, context, event):
        scn = context.scene
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        self.selection.clear()
        for idx,data in enumerate(self.getKeys(rig, ob)):
            prop,text,cat = data
            item = self.selection.add()
            item.name = prop
            item.text = text
            item.category = cat
            item.index = idx
            item.select = self.defaultSelect
        return self.invokeDialog(context)


theMorphEnums = []

def getMorphEnums(scn, context):
    return theMorphEnums

class StandardSelector(Selector):
    morphset : EnumProperty(
        items = getMorphEnums,
        name = "Type")

    allSets = theStandardMorphSets

    def selectCondition(self, item):
        if self.morphset == "All":
            names = []
            for morphset in self.allSets:
                pg = getattr(self.rig, "Daz"+morphset)
                names += list(pg.keys())
        else:
            pg = getattr(self.rig, "Daz"+self.morphset)
            names = list(pg.keys())
        return (item.name in names)

    def draw(self, context):
        self.layout.prop(self, "morphset")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        morphs = getMorphList(rig, self.morphset, sets=self.allSets)
        return [(item.name, item.text, "All") for item in morphs]

    def invoke(self, context, event):
        global theMorphEnums
        theMorphEnums = [("All", "All", "All")]
        for morphset in self.allSets:
            theMorphEnums.append((morphset, morphset, morphset))
        self.morphset = "All"
        return Selector.invoke(self, context, event)


class CustomSelector(Selector, CustomEnums):

    def selectCondition(self, item):
        return (self.custom == "All" or item.category == self.custom)

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        morphs = getMorphList(rig, self.morphset, sets=theCustomMorphSets)
        keys = []
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name,item.text,cat.name))
        return keys


class JCMSelector(Selector):
    bodypart : EnumProperty(
        items = [("All", "All", "All"),
                 ("Face", "Face", "Face"),
                 ("Body", "Body", "Body"),
                 ("Custom", "Custom", "Custom")],
        name = "Body part",
        description = "Part of character that the morphs affect",
        default = "All")

    def selectCondition(self, item):
        return (self.bodypart == "All" or item.category == self.bodypart)

    def draw(self, context):
        self.layout.prop(self, "bodypart")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        keys = []
        skeys = ob.data.shape_keys
        for skey in skeys.key_blocks[1:]:
            keys.append((skey.name, skey.name, self.bodyparts[skey.name]))
        return keys

    def invoke(self, context, event):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            print("Object %s has no shapekeys")
            return {'FINISHED'}
        self.bodyparts = classifyShapekeys(ob, skeys)
        return Selector.invoke(self, context, event)


def classifyShapekeys(ob, skeys):
    morphs = {}
    bodyparts = {}
    pgs = ob.data.DazBodyPart
    for skey in skeys.key_blocks[1:]:
        if skey.name in pgs.keys():
            item = pgs[skey.name]
            if item.s not in morphs.keys():
                morphs[item.s] = []
            morphs[item.s].append(skey.name)
            bodyparts[skey.name] = item.s
        else:
            bodyparts[skey.name] = "Custom"
    return bodyparts

#------------------------------------------------------------------
#   Global lists of morph paths
#------------------------------------------------------------------

ShortForms = {
    "phmunits" : ["phmbrow", "phmcheek", "phmeye", "phmjaw", "phmlip", "phmmouth", "phmnos", "phmteeth", "phmtongue"],

    "ectrlunits" : ["ectrlbrow", "ectrlcheek", "ectrleye", "ectrljaw", "ectrllip", "ectrlmouth", "ectrlnos", "ectrlteeth", "ectrltongue"],
}

ShortForms["units"] = ShortForms["ectrlunits"] + ShortForms["phmunits"]

def getShortformList(item):
    if isinstance(item, list):
        return item
    else:
        return ShortForms[item]


theMorphFiles = {}
theMorphNames = {}

def getAllMorphFiles(char, morphset):
    return list(theMorphFiles[char][morphset].values())


def setupMorphPaths(scn, force):
    global theMorphFiles, theMorphNames
    from collections import OrderedDict
    from .asset import fixBrokenPath
    from .load_json import loadJson
    from .modifier import getCanonicalKey

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
            if "strip" in struct.keys():
                strips = struct["strip"]
            else:
                strips = prefixes
            folder = struct["path"]
            includes = getShortformList(struct["include"])
            excludes = getShortformList(struct["exclude"])
            if "exclude2" in struct.keys():
                excludes += getShortformList(struct["exclude2"])

            for dazpath in GS.getDazPaths():
                folderpath = os.path.join(dazpath, folder)
                if not os.path.exists(folderpath) and GS.caseSensitivePaths:
                    folderpath = fixBrokenPath(folderpath)
                if os.path.exists(folderpath):
                    files = list(os.listdir(folderpath))
                    files.sort()
                    for file in files:
                        fname,ext = os.path.splitext(file)
                        if ext not in [".duf", ".dsf"]:
                            continue
                        isright,name = isRightType(fname, prefixes, strips, includes, excludes)
                        if isright:
                            fname = fname.lower()
                            #fpath = os.path.join(folder, file)
                            typeFiles[name] = os.path.join(folderpath, file)
                            #prop = BoolProperty(name=name, default=True)
                            #setattr(bpy.types.Scene, "Daz"+name, prop)
                            typeNames[fname] = name


def isRightType(fname, prefixes, strips, includes, excludes):
    string = fname.lower()
    ok = False
    for prefix in prefixes:
        n = len(prefix)
        if string[0:n] == prefix:
            ok = True
            if prefix in strips:
                name = fname[n:]
            else:
                name = fname
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
        print(theMorphFiles.items())
        print("UU", theMorphNames.items())


class DAZ_OT_SelectAllMorphs(DazOperator):
    bl_idname = "daz.select_all_morphs"
    bl_label = "Select All"
    bl_description = "Select/Deselect all morphs in this section"
    bl_options = {'UNDO'}

    type : StringProperty()
    value : BoolProperty()

    def run(self, context):
        scn = context.scene
        names = theMorphNames[self.morphset]
        for name in names.values():
            scn["Daz"+name] = self.value

#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class MorphLoader(LoadMorph):
    def __init__(self, rig=None, mesh=None):
        from .finger import getFingeredCharacter
        self.rig, self.mesh, self.char = getFingeredCharacter(bpy.context.object)
        if mesh:
            self.mesh = mesh


    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)


    def getBodyPart(self, context):
        return self.bodypart


    def getAllMorphs(self, namepaths, context):
        from time import perf_counter
        from .asset import clearAssets
        from .propgroups import clearDependecies
        from .driver import setBoolProp

        if self.mesh:
            ob = self.mesh
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        LS.forMorphLoad(ob)
        if not self.usePropDrivers:
            self.rig = None
        clearDependecies()

        self.errors = {}
        t1 = perf_counter()
        if namepaths:
            path = list(namepaths.values())[0]
            folder = os.path.dirname(path)
        else:
            raise DazError("No morphs selected")
        self.loadAllMorphs(list(namepaths.items()))
        t2 = perf_counter()
        print("Folder %s loaded in %.3f seconds" % (folder, t2-t1))
        if self.errors:
            msg = "Morphs loaded with errors."
            for err,props in self.errors.items():
                msg += "\n%s:    \n" % err
                for prop in props:
                    msg += "    %s\n" % prop
            raise DazError(msg, warning=True)
        if self.ecr and GS.verbosity >= 3:
            msg = "Found morphs that want to\nchange the rest pose"
            raise DazError(msg, warning=True)

#------------------------------------------------------------------
#   Load standard morphs
#------------------------------------------------------------------

class StandardMorphLoader(MorphLoader):
    suppressError = True
    ignoreHD = False

    def setupCharacter(self, context, rigIsMesh):
        ob = context.object
        if self.mesh is None and rigIsMesh:
            if self.rig.DazRig == "genesis3":
                self.char = "Genesis3-female"
                #self.mesh = self.rig
            elif self.rig.DazRig == "genesis8":
                self.char = "Genesis8-female"
                #self.mesh = self.rig
        if not self.char:
            from .error import invokeErrorMessage
            msg = ("Can not add morphs to this mesh:\n %s" % ob.name)
            invokeErrorMessage(msg)
            return False
        return True


    def addToMorphSet(self, prop, asset, hidden):
        addToMorphSet(self.rig, self.morphset, prop, asset, hidden=hidden)


    def getMorphFiles(self):
        try:
            return theMorphFiles[self.char][self.morphset]
        except KeyError:
            return []


    def getPaths(self, context):
        return


    def run(self, context):
        scn = context.scene
        setupMorphPaths(scn, False)
        self.rig.DazMorphPrefixes = False
        namepaths = self.getActiveMorphFiles(context)
        self.getAllMorphs(namepaths, context)

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class StandardMorphSelector(Selector):
    strength = 1

    def draw(self, context):
        Selector.draw(self, context)


    def getActiveMorphFiles(self, context):
        from .fileutils import getSelection
        pathdir = {}
        paths = getSelection()
        if paths:
            for path in paths:
                text = os.path.splitext(os.path.basename(path))[0]
                pathdir[text] = path
        else:
            for item in self.getSelectedItems():
                pathdir[item.text] = item.name
        return pathdir


    def isActive(self, name, scn):
        return True

    def selectCondition(self, item):
        return True

    def invoke(self, context, event):
        global theMorphFiles
        scn = context.scene
        self.selection.clear()
        if not self.setupCharacter(context, False):
            return {'FINISHED'}
        setupMorphPaths(scn, False)
        try:
            pg = theMorphFiles[self.char][self.morphset]
        except KeyError:
            msg = ("Character %s does not support feature %s" % (self.char, self.morphset))
            print(msg)
            return {'FINISHED'}
        for key,path in pg.items():
            item = self.selection.add()
            item.name = path
            item.text = key
            item.category = self.morphset
            item.select = True
        return self.invokeDialog(context)


class DAZ_OT_ImportUnits(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_units"
    bl_label = "Import Units"
    bl_description = "Import selected face unit morphs"
    bl_options = {'UNDO'}

    morphset = "Units"
    bodypart = "Face"


class DAZ_OT_ImportExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_expressions"
    bl_label = "Import Expressions"
    bl_description = "Import selected expression morphs"
    bl_options = {'UNDO'}

    morphset = "Expressions"
    bodypart = "Face"


class DAZ_OT_ImportVisemes(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_visemes"
    bl_label = "Import Visemes"
    bl_description = "Import selected viseme morphs"
    bl_options = {'UNDO'}

    morphset = "Visemes"
    bodypart = "Face"


class DAZ_OT_ImportFacs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs"
    bl_label = "Import FACS Units"
    bl_description = "Import selected FACS unit morphs"
    bl_options = {'UNDO'}

    morphset = "Facs"
    bodypart = "Face"


class DAZ_OT_ImportFacsExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs_expressions"
    bl_label = "Import FACS Expressions"
    bl_description = "Import selected FACS expression morphs"
    bl_options = {'UNDO'}

    morphset = "Facsexpr"
    bodypart = "Face"
    loadMissed = False


class DAZ_OT_ImportBodyMorphs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_body_morphs"
    bl_label = "Import Body Morphs"
    bl_description = "Import selected body morphs"
    bl_options = {'UNDO'}

    morphset = "Body"
    bodypart = "Body"


class DAZ_OT_ImportJCMs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_jcms"
    bl_label = "Import JCMs"
    bl_description = "Import selected joint corrective morphs"
    bl_options = {'UNDO'}

    morphset = "Jcms"
    bodypart = "Body"

    def addToMorphSet(self, prop, asset, hidden):
        addToMorphSet(self.rig, self.morphset, prop, asset, hidden=hidden, hideable=False)


class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    morphset = "Flexions"
    bodypart = "Body"

    def addToMorphSet(self, prop, asset, hidden):
        addToMorphSet(self.rig, self.morphset, prop, asset, hidden=hidden, hideable=False)

#------------------------------------------------------------------------
#   Import all standard morphs in one bunch, for performance
#------------------------------------------------------------------------

from .main import MorphTypeOptions

class DAZ_OT_ImportStandardMorphs(DazPropsOperator, StandardMorphLoader, MorphTypeOptions, IsMeshArmature):
    bl_idname = "daz.import_standard_morphs"
    bl_label = "Import Standard Morphs"
    bl_description = "Import all standard morphs of selected types.\nDoing this once is faster than loading individual types"
    bl_options = {'UNDO'}

    strength = 1.0
    morphset = "Standard"

    def run(self, context):
        if not self.setupCharacter(context, False):
            return
        scn = context.scene
        setupMorphPaths(scn, False)
        self.rig.DazMorphPrefixes = False
        self.morphsets = {}
        self.bodyparts = {}
        self.namepaths = {}
        self.addFiles(self.units, "Units", "Face")
        self.addFiles(False, "Head", "Face")
        self.addFiles(self.expressions, "Expressions", "Face")
        self.addFiles(self.visemes, "Visemes", "Face")
        self.addFiles(self.facs, "Facs", "Face")
        self.addFiles(self.facsexpr, "Facsexpr", "Face")
        self.addFiles(self.body, "Body", "Body")
        self.addFiles(self.jcms, "Jcms", "Body")
        self.addFiles(self.flexions, "Flexions", "Body")
        self.getAllMorphs(self.namepaths, context)


    def addFiles(self, use, morphset, bodypart):
        try:
            struct = theMorphFiles[self.char][morphset]
        except KeyError:
            msg = ("Character %s does not support feature %s" % (self.char, morphset))
            print(msg)
            return
        for key,filepath in struct.items():
            fileref = self.getFileRef(filepath)
            self.morphsets[fileref] = morphset
            self.bodyparts[fileref] = bodypart
            if use:
                self.namepaths[key] = filepath


    def getMorphSet(self, asset):
        if asset is None:
            return "Standard"
        fileref = unquote(asset.fileref.lower())
        if fileref in self.morphsets.keys():
            return self.morphsets[fileref]
        else:
            msg = "Missing morphset: %s" % fileref
            if GS.verbosity > 2:
                print("Morphset keys:")
                for key in self.morphsets.keys():
                    print("  ", key)
                raise DazError(msg)
            else:
                print(msg)
            return "Standard"


    def getBodyPart(self, asset):
        fileref = unquote(asset.fileref.lower())
        if fileref in self.bodyparts.keys():
            return self.bodyparts[fileref]
        else:
            print("Missing bodypart", fileref)
            return "Custom"


    def addToMorphSet(self, prop, asset, hidden):
        morphset = self.getMorphSet(asset)
        if morphset in ["Jcms", "Flexions"]:
            addToMorphSet(self.rig, morphset, prop, asset, hideable=False)
        else:
            addToMorphSet(self.rig, morphset, prop, asset, hidden=hidden)

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class DAZ_OT_ImportCustomMorphs(DazOperator, MorphLoader, DazImageFile, MultiFile, IsMeshArmature):
    bl_idname = "daz.import_custom_morphs"
    bl_label = "Import Custom Morphs"
    bl_description = "Import selected morphs from native DAZ files (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    morphset = "Custom"

    catname : StringProperty(
        name = "Category",
        default = "Shapes")

    usePropDrivers : BoolProperty(
        name = "Use Rig Property Drivers",
        description = "Drive shapekeys with rig properties",
        default = True)

    useMeshCats : BoolProperty(
        name = "Use Mesh Categories",
        description = "Mesh categories",
        default = False)

    bodypart : EnumProperty(
        items = [("Face", "Face", "Face"),
                 ("Body", "Body", "Body"),
                 ("Custom", "Custom", "Custom")],
        name = "Body part",
        description = "Part of character that the morphs affect",
        default = "Custom")

    strength : FloatProperty(
        name = "Strength",
        description = "Multiply morphs with this value",
        default = 1.0)

    treatHD : EnumProperty(
        items = [('ERROR', "Error", "Raise error"),
                 ('CREATE', "Create Shapekey", "Create empty shapekeys"),
                 ('ACTIVE', "Active Shapekey", "Drive active shapekey")],
        name = "Treat HD Mismatch",
        description = "How to deal with vertex count mismatch for HD morphs",
        default = 'ERROR'
    )

    def draw(self, context):
        self.layout.prop(self, "usePropDrivers")
        if self.usePropDrivers:
            self.layout.prop(self, "catname")
        else:
            self.layout.prop(self, "useMeshCats")
            if self.useMeshCats:
                self.layout.prop(self, "catname")
        self.layout.prop(self, "bodypart")
        self.layout.prop(self, "strength")
        self.layout.prop(self, "treatHD")


    def invoke(self, context, event):
        from .fileutils import getFolders
        folders = getFolders(self.mesh, context.scene, ["Morphs/", ""])
        if folders:
            self.properties.filepath = folders[0]
        return MultiFile.invoke(self, context, event)


    def run(self, context):
        from .driver import setBoolProp
        namepaths = self.getNamePaths()
        self.getAllMorphs(namepaths, context)
        if self.usePropDrivers and self.drivers:
            self.rig.DazCustomMorphs = True
        elif self.useMeshCats and self.shapekeys:
            props = self.shapekeys.keys()
            addToCategories(self.mesh, props, self.catname)
            self.mesh.DazMeshMorphs = True
        if self.errors:
            raise DazError(theLimitationsMessage)


    def getNamePaths(self):
        namepaths = {}
        folder = ""
        for path in self.getMultiFiles(["duf", "dsf"]):
            name = os.path.splitext(os.path.basename(path))[0]
            namepaths[name] = path
        return namepaths


    def addToMorphSet(self, prop, asset, hidden):
        from .modifier import getCanonicalKey
        if self.rig is None:
            return
        cats = self.rig.DazMorphCats
        if self.catname not in cats.keys():
            cat = cats.add()
            cat.name = self.catname
        else:
            cat = cats[self.catname]
        if prop not in cat.morphs.keys():
            item = cat.morphs.add()
            item.name = prop
        else:
            item = cat.morphs[prop]
        if asset and asset.name == prop:
            label = asset.label
            visible = asset.visible
        else:
            label = getCanonicalKey(prop)
            visible = True
        if hidden or not visible:
            item.text = "[%s]" % label
        else:
            item.text = label

#------------------------------------------------------------------------
#   Categories
#------------------------------------------------------------------------

def addToCategories(ob, props, catname):
    from .driver import setBoolProp
    from .modifier import getCanonicalKey

    if props and ob is not None:
        cats = dict([(cat.name,cat) for cat in ob.DazMorphCats])
        if catname not in cats.keys():
            cat = ob.DazMorphCats.add()
            cat.name = catname
        else:
            cat = cats[catname]
        setBoolProp(cat, "active", True)
        for prop in props:
            if prop not in cat.morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = cat.morphs[prop]
            morph.name = prop
            morph.text = getCanonicalKey(prop)
            setBoolProp(morph, "active", True)

#------------------------------------------------------------------------
#   Rename category
#------------------------------------------------------------------------

class DAZ_OT_RenameCategory(DazPropsOperator, CustomEnums, CategoryString, IsMeshArmature):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def draw(self, context):
       self.layout.prop(self, "custom")
       self.layout.prop(self, "category", text="New Name")

    def run(self, context):
        rig = context.object
        if self.custom == "All":
            raise DazError("Cannot rename all categories")
        cat = rig.DazMorphCats[self.custom]
        cat.name = self.category


def removeFromPropGroups(rig, prop, keep=False):
    from .propgroups import getAllPropGroups
    for pb in rig.pose.bones:
        pgs = getAllPropGroups(pb)
        for pg in pgs:
            removeFromPropGroup(pg, prop)

    for morphset in theStandardMorphSets:
        pgs = getattr(rig, "Daz" + morphset)
        removeFromPropGroup(pgs, prop)

    if not keep:
        rig[prop] = 0
        del rig[prop]
        for ob in rig.children:
            if prop in ob.keys():
                ob[prop] = 0
                del ob[prop]


def removeFromPropGroup(pgs, prop):
    idxs = []
    for n,pg in enumerate(pgs):
        if pg.name == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgs.remove(n)

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

class Activator(MorphsetString):
    useMesh : BoolProperty(default=False)

    def run(self, context):
        if self.useMesh:
            ob = context.object
            morphs = getCustomMorphs(ob, self.category)
        else:
            ob = getRigFromObject(context.object)
            morphs = getRelevantMorphs(ob, self.morphset, self.category)
        for morph in morphs:
           setActivated(ob, morph, self.activate)


def setActivated(ob, key, value):
    from .driver import setBoolProp
    if ob is None:
        return
    pg = getActivateGroup(ob, key)
    setBoolProp(pg, "active", value)


def getActivated(ob, rna, key, force=False):
    if key not in rna.keys():
        return False
    elif force:
        return True
    else:
        pg = getActivateGroup(ob, key)
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
    from .driver import setBoolProp
    scn = context.scene
    for ob in getSelectedObjects(context):
        for prop in ob.keys():
            if prop[0:7] == "DazShow":
                setBoolProp(ob, prop, True)
            elif prop[0:3] in ["Mhh", "DzM"]:
                setBoolProp(ob, prop, True)
        for cat in ob.DazMorphCats:
            setBoolProp(cat, "active", True)
            for morph in cat.morphs:
                if morph.name in ob.keys():
                    setOverridable(ob, morph.name)
        for pg in ob.DazActivated:
            setBoolProp(pg, "active", True)


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
#   Clear morphs
#------------------------------------------------------------------

def getRelevantMorphs(rig, morphset, category):
    morphs = []
    if rig is None:
        return morphs
    if morphset == "Custom":
        return getCustomMorphs(rig, category)
    elif rig.DazMorphPrefixes:
        for key in rig.keys():
            if key[0:2] == "Dz":
                raise DazError("OLD morphs", rig, key)
    elif morphset == "All":
        for mset in theStandardMorphSets:
            pg = getattr(rig, "Daz"+mset)
            for key in pg.keys():
                morphs.append(key)
        for cat in rig.DazMorphCats:
            morphs += [morph.name for morph in cat.morphs]
    else:
        pg = getattr(rig, "Daz"+morphset)
        for key in pg.keys():
            morphs.append(key)
    return morphs


def getCustomMorphs(ob, category):
    morphs = []
    if category:
        for cat in ob.DazMorphCats:
            if cat.name == category:
                morphs = [morph.name for morph in cat.morphs]
                return morphs
    else:
        for cat in ob.DazMorphCats:
            morphs += [morph.name for morph in cat.morphs]
    return morphs


def clearMorphs(rig, morphset, category, scn, frame, force):
    morphs = getRelevantMorphs(rig, morphset, category)
    for morph in morphs:
        if (getActivated(rig, rig, morph, force) and
            isinstance(rig[morph], float)):
            rig[morph] = 0.0
            autoKeyProp(rig, morph, scn, frame, force)


def clearShapes(ob, category, scn, frame):
    skeys = ob.data.shape_keys
    if skeys is None:
        return
    morphs = getCustomMorphs(ob, category)
    for morph in morphs:
        if getActivated(ob, skeys.key_blocks, morph):
            skeys.key_blocks[morph].value = 0.0
            autoKeyShape(skeys, morph, scn, frame)


class DAZ_OT_ClearMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear Morphs"
    bl_description = "Set all morphs of specified type to zero.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            clearMorphs(rig, self.morphset, self.category, scn, scn.frame_current, False)
            updateRigDrivers(context, rig)


class DAZ_OT_ClearShapes(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.clear_shapes"
    bl_label = "Clear Shapes"
    bl_description = "Set all shapekeys values of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        clearShapes(context.object, self.category, scn, scn.frame_current)

#------------------------------------------------------------------
#   Add morphs to keyset
#------------------------------------------------------------------

def addKeySet(rig, morphset, scn, frame):
    if rig is None:
        return
    aksi = scn.keying_sets.active_index
    if aksi <= -1:
        aks = scn.keying_sets.new(idname = "daz_morphs", name = "daz_morphs")
    aks = scn.keying_sets.active
    if morphset == "Custom":
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                path = "[" + '"' + morph.name + '"' + "]"
                aks.paths.add(rig.id_data, path)
    else:
        pg = getattr(rig, "Daz"+morphset)
        for key in pg.keys():
            if key in rig.keys():
                path = "[" + '"' + key + '"' + "]"
                aks.paths.add(rig.id_data, path)


class DAZ_OT_AddKeysets(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add category morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            addKeySet(rig, self.morphset, scn, scn.frame_current)
            updateRigDrivers(context, rig)

#------------------------------------------------------------------
#   Set morph keys
#------------------------------------------------------------------

class DAZ_OT_KeyMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            self.keyMorphs(rig, scn, scn.frame_current)
            updateRigDrivers(context, rig)



    def keyMorphs(self, rig, scn, frame):
        if rig is None:
            return
        if self.morphset == "Custom":
            if self.category:
                cats = [rig.DazMorphCats[self.category]]
            else:
                cats = rig.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(rig, rig, morph.name):
                        keyProp(rig, morph.name, frame)
        else:
            pg = getattr(rig, "Daz" + self.morphset)
            for key in pg.keys():
                if getActivated(rig, rig, key):
                    keyProp(rig, key, frame)


class DAZ_OT_KeyShapes(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.key_shapes"
    bl_label = "Set Keys"
    bl_description = "Set keys for all shapes of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys:
            scn = context.scene
            if self.category:
                cats = [ob.DazMorphCats[self.category]]
            else:
                cats = ob.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(ob, skeys.key_blocks, morph.name):
                        keyShape(skeys, morph.name, scn.frame_current)

#------------------------------------------------------------------
#   Remove morph keys
#------------------------------------------------------------------

class DAZ_OT_UnkeyMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig and rig.animation_data and rig.animation_data.action:
            scn = context.scene
            self.unkeyMorphs(rig, scn, scn.frame_current)
            updateRigDrivers(context, rig)


    def unkeyMorphs(self, rig, scn, frame):
        if rig is None:
            return
        if self.morphset == "Custom":
            if self.category:
                cats = [rig.DazMorphCats[self.category]]
            else:
                cats = rig.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(rig, rig, morph.name):
                        unkeyProp(rig, morph.name, frame)
        else:
            pg = getattr(rig, "Daz" + self.morphset)
            for key in pg.keys():
                if getActivated(rig, rig, key):
                    unkeyProp(rig, key, frame)


class DAZ_OT_UnkeyShapes(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.unkey_shapes"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all shapekeys of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and skeys.animation_data and skeys.animation_data.action:
            scn = context.scene
            if self.category:
                cats = [ob.DazMorphCats[self.category]]
            else:
                cats = ob.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(ob, skeys.key_blocks, morph.name):
                        unkeyShape(skeys, morph.name, scn.frame_current)

#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

class DAZ_OT_UpdateSliderLimits(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.update_slider_limits"
    bl_label = "Update Slider Limits"
    bl_description = "Update slider min and max values"
    bl_options = {'UNDO'}

    min : FloatProperty(
        name = "Min",
        description = "Minimum slider value",
        min = -10.0, max = 0.0)

    max : FloatProperty(
        name = "Max",
        description = "Maximum slider value",
        min = 0.0, max = 10.0)

    allShapes : BoolProperty(
        name = "All Shapekeys",
        description = "Update all shapekey sliders",
        default = True)

    def draw(self, context):
        scn = context.scene
        self.layout.prop(self, "min")
        self.layout.prop(self, "max")
        self.layout.prop(self, "allShapes")


    def run(self, context):
        ob = context.object
        scn = context.scene
        GS.customMin = self.min
        GS.customMax = self.max
        rig = getRigFromObject(ob)
        if rig:
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)


    def invoke(self, context, event):
        self.min = GS.customMin
        self.max = GS.customMax
        return DazPropsOperator.invoke(self, context, event)


    def updatePropLimits(self, rig, context):
        from .driver import setFloatProp
        scn = context.scene
        props = getAllLowerMorphNames(rig)
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys:
                for skey in ob.data.shape_keys.key_blocks:
                    if self.allShapes or skey.name.lower() in props:
                        skey.slider_min = GS.customMin
                        skey.slider_max = GS.customMax
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in props:
                final = finalProp(raw)
                setFloatProp(rig, raw, rig[raw], GS.customMin, GS.customMax)
                setFloatProp(amt, final, amt[final], GS.customMin, GS.customMax)
        updateRigDrivers(context, rig)
        print("Slider limits updated")

#------------------------------------------------------------------
#   Remove all morph drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllDrivers(DazPropsOperator, DriverUser, IsMeshArmature):
    bl_idname = "daz.remove_all_drivers"
    bl_label = "Remove All Drivers"
    bl_description = "Remove all drivers from selected objects"
    bl_options = {'UNDO'}

    useRemoveProps : BoolProperty(
        name = "Remove Properties",
        description = "Also remove driving properties",
        default = True)

    useRemoveAllProps : BoolProperty(
        name = "Remove All Properties",
        description = "Also remove other properties",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useRemoveProps")
        if self.useRemoveProps:
            self.layout.prop(self, "useRemoveAllProps")


    def run(self, context):
        self.targets = {}
        meshes = getSelectedMeshes(context)
        rigs = getSelectedArmatures(context)
        for ob in meshes:
            skeys = ob.data.shape_keys
            if skeys:
                self.removeDrivers(skeys)
        for rig in rigs:
            self.removeDrivers(rig.data)
            self.removeDrivers(rig)

        if not self.useRemoveProps:
            return
        for path,rna in self.targets.items():
            words = path.split('"')
            if len(words) == 5 and words[0] == "pose.bones[" and words[4] == "]":
                bname = words[1]
                prop = words[3]
                pb = rna.pose.bones[bname]
                if prop in pb.keys():
                    del pb[prop]
            elif len(words) == 3 and words[2] == "]":
                prop = words[1]
                if prop in rna.keys():
                    del rna[prop]

        if not self.useRemoveAllProps:
            return
        for rig in rigs:
            for key in list(rig.keys()):
                if not (key[0] == "_" or hasattr(rig, key)):
                    del rig[key]
            for key in list(rig.data.keys()):
                if not (key[0] == "_" or hasattr(rig.data, key)):
                    del rig.data[key]


    def removeDrivers(self, rna):
        if not rna.animation_data:
            return
        for fcu in list(rna.animation_data.drivers):
            for var in fcu.driver.variables:
                for trg in var.targets:
                    self.targets[trg.data_path] = trg.id
            idx = self.getArrayIndex(fcu)
            self.removeDriver(rna, fcu.data_path, idx)

#-------------------------------------------------------------
#   Add driven value nodes
#-------------------------------------------------------------

class DAZ_OT_AddDrivenValueNodes(DazOperator, Selector, DriverUser, IsMesh):
    bl_idname = "daz.add_driven_value_nodes"
    bl_label = "Add Driven Value Nodes"
    bl_description = "Add driven value nodes"
    bl_options = {'UNDO'}

    allSets = theMorphSets

    def getKeys(self, rig, ob):
        skeys = ob.data.shape_keys
        if skeys:
            return [(sname, sname, "All") for sname in skeys.key_blocks.keys()]
        else:
            return []


    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text = "Active material: %s" % mat.name)
        Selector.draw(self, context)


    def run(self, context):
        from .driver import getShapekeyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromObject(ob)
        mat = ob.data.materials[ob.active_material_index]
        props = self.getSelectedProps()
        nprops = len(props)
        for n,prop in enumerate(props):
            skey = skeys.key_blocks[prop]
            fcu = getShapekeyDriver(skeys, prop)
            node = mat.node_tree.nodes.new(type="ShaderNodeValue")
            node.name = node.label = skey.name
            node.location = (-1100, 250-250*n)
            if fcu:
                channel = ('nodes["%s"].outputs[0].default_value' % node.name)
                fcu2 = mat.node_tree.driver_add(channel)
                fcu2 = self.copyFcurve(fcu, fcu2)

#-------------------------------------------------------------
#   Add and remove driver
#-------------------------------------------------------------

class AddRemoveDriver:

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            for sname in self.getSelectedProps():
                self.handleShapekey(sname, rig, ob)
            updateRigDrivers(context, rig)
        updateDrivers(ob.data.shape_keys)


    def invoke(self, context, event):
        self.selection.clear()
        ob = context.object
        rig = ob.parent
        if (rig and rig.type != 'ARMATURE'):
            rig = None
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks[1:]:
                if self.includeShapekey(skeys, skey.name):
                    item = self.selection.add()
                    item.name = item.text = skey.name
                    item.category = self.getCategory(rig, ob, skey.name)
                    item.select = False
        return self.invokeDialog(context)


class DAZ_OT_AddShapeToCategory(DazOperator, AddRemoveDriver, Selector, CustomEnums, CategoryString, IsMesh):
    bl_idname = "daz.add_shape_to_category"
    bl_label = "Add Shapekey To Category"
    bl_description = "Add selected shapekeys to mesh category"
    bl_options = {'UNDO'}

    makenew : BoolProperty(
        name = "New Category",
        description = "Create a new category",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "makenew")
        if self.makenew:
            self.layout.prop(self, "category")
        else:
            self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        if self.makenew:
            cat = self.category
        elif self.custom == "All":
            raise DazError("Cannot add to all categories")
        else:
            cat = self.custom
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            addToCategories(ob, [sname], cat)
            ob.DazMeshMorphs = True


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, CategoryString, IsMesh):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)


    def handleShapekey(self, sname, rig, ob):
        from .driver import getShapekeyDriver, addDriverVar, setFloatProp
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        if getShapekeyDriver(skeys, skey.name):
            raise DazError("Shapekey %s is already driven" % skey.name)
        setFloatProp(rig, sname, skey.value, skey.slider_min, skey.slider_max)
        fcu = skey.driver_add("value")
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", propRef(sname), rig)
        fcu.driver.expression = "a"
        addToCategories(rig, [sname], self.category)
        rig.DazCustomMorphs = True


    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return (not getShapekeyDriver(skeys, sname))


    def getCategory(self, rig, ob, sname):
        return ""


class DAZ_OT_RemoveShapeFromCategory(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shape_from_category"
    bl_label = "Remove Shapekey From Category"
    bl_description = "Remove selected shapekeys from mesh category"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)


    def run(self, context):
        ob = context.object
        snames = []
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in ob.DazMorphCats:
                self.removeFromCategory(ob, snames, cat.name)
        else:
            self.removeFromCategory(ob, snames, self.custom)
        updateDrivers(ob.data.shape_keys)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


    def removeFromCategory(self, ob, props, catname):
        if catname in ob.DazMorphCats.keys():
            cat = ob.DazMorphCats[catname]
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)


class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
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


    def includeShapekey(self, skeys, sname):
        from .driver import getShapekeyDriver
        return getShapekeyDriver(skeys, sname)


    def getCategory(self, rig, ob, sname):
        if rig is None:
            return ""
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getRigFromObject(ob, useMesh=False):
    if ob.type == 'ARMATURE':
        return ob
    elif useMesh and ob.type == 'MESH':
        return ob
    else:
        ob = ob.parent
        if ob is None or ob.type != 'ARMATURE':
            return None
        return ob


class DAZ_OT_ToggleAllCats(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    useMesh : BoolProperty(default=False)
    useOpen : BoolProperty()

    def run(self, context):
        rig = getRigFromObject(context.object, self.useMesh)
        if rig:
            for cat in rig.DazMorphCats:
                cat["active"] = self.useOpen

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def keyProp(rig, key, frame):
    rig.keyframe_insert(propRef(key), frame=frame)


def keyShape(skeys, key, frame):
    skeys.keyframe_insert('key_blocks["%s"].value' % key, frame=frame)


def unkeyProp(rig, key, frame):
    try:
        rig.keyframe_delete(propRef(key), frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def unkeyShape(skeys, key, frame):
    try:
        skeys.keyframe_delete('key_blocks["%s"].value' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = propRef(key)
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def autoKeyShape(skeys, key, scn, frame):
    if scn.tool_settings.use_keyframe_insert_auto:
        keyShape(skeys, key, frame)


def pinProp(rig, scn, key, morphset, category, frame):
    if rig:
        clearMorphs(rig, morphset, category, scn, frame, True)
        rig[key] = 1.0
        autoKeyProp(rig, key, scn, frame, True)


def pinShape(ob, scn, key, category, frame):
    skeys = ob.data.shape_keys
    if skeys:
        clearShapes(ob, category, scn, frame)
        skeys.key_blocks[key].value = 1.0
        autoKeyShape(skeys, key, scn, frame)


class DAZ_OT_PinProp(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        rig = getRigFromObject(context.object)
        scn = context.scene
        setupMorphPaths(scn, False)
        pinProp(rig, scn, self.key, self.morphset, self.category, scn.frame_current)
        updateRigDrivers(context, rig)


class DAZ_OT_PinShape(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.pin_shape"
    bl_label = ""
    bl_description = "Pin shapekey value"
    bl_options = {'UNDO'}

    key : StringProperty()

    def run(self, context):
        ob = context.object
        scn = context.scene
        pinShape(ob, scn, self.key, self.category, scn.frame_current)

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

class DAZ_OT_LoadMoho(DazOperator, DatFile, SingleFile):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

    def run(self, context):
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
        auto = scn.tool_settings.use_keyframe_insert_auto
        scn.tool_settings.use_keyframe_insert_auto = True
        fp = safeOpen(self.filepath, "r")
        for line in fp:
            words= line.split()
            if len(words) < 2:
                pass
            else:
                moho = words[1]
                frame = int(words[0]) + 1
                if moho == "rest":
                    clearMorphs(rig, "Visemes", "", scn, frame, True)
                else:
                    key = self.getMohoKey(moho, rig)
                    if key not in rig.keys():
                        raise DazError("Missing viseme: %s => %s" % (moho, key))
                    pinProp(rig, scn, key, "Visemes", "", frame)
        fp.close()
        #setInterpolation(rig)
        updateRigDrivers(context, rig)
        scn.tool_settings.use_keyframe_insert_auto = auto
        print("Moho file %s loaded" % self.filepath)


    def getMohoKey(self, moho, rig):
        Moho2Daz = {
            "rest" : "Rest",
            "etc" : "K",
            "AI" : "AA",
            "O" : "OW",
            "U" : "UW",
            "WQ" : "W",
            "L" : "L",
            "E" : "EH",
            "MBP" : "M",
            "FV" : "F"
        }
        daz = Moho2Daz[moho]
        for pg in rig.DazVisemes:
            if pg.text == daz:
                return pg.name
        return None

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class MorphsToShapes:
    def run(self, context):
        ob = context.object
        rig = ob.parent
        if rig is None or rig.type != 'ARMATURE':
            return
        items = self.getSelectedItems()
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
                mod = getModifier(ob, 'ARMATURE')
                if mod:
                    rig[key] = 1.0
                    updateRigDrivers(context, rig)
                    self.applyArmature(ob, rig, mod, mname)
                    rig[key] = 0.0
        updateRigDrivers(context, rig)


    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        if bpy.app.version < (2,90,0):
            bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        else:
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
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

    morphset = "Custom"

#-------------------------------------------------------------
#   Transfer verts to shapekeys
#-------------------------------------------------------------

class DAZ_OT_MeshToShape(DazOperator, IsMesh):
    bl_idname = "daz.transfer_mesh_to_shape"
    bl_label = "Transfer Mesh To Shapekey"
    bl_description = "Transfer selected mesh to active shapekey"
    bl_options = {'UNDO'}

    def run(self, context):
        trg = context.object
        skeys = trg.data.shape_keys
        if skeys is None:
            raise DazError("Target mesh must have shapekeys")
        idx = trg.active_shape_key_index
        if idx == 0:
            raise DazError("Cannot transfer to Basic shapekeys")
        objects = [ob for ob in getSelectedMeshes(context) if ob != trg]
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected")
        src = objects[0]
        nsverts = len(src.data.vertices)
        ntverts = len(trg.data.vertices)
        if nsverts != ntverts:
            raise DazError("Vertex count mismatch:  \n%d != %d" % (nsverts, ntverts))
        skey = skeys.key_blocks[idx]
        for v in src.data.vertices:
            skey.data[v.index].co = v.co

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

classes = [
    DazSelectGroup,
    DazActiveGroup,
    DazCategory,

    DAZ_OT_SelectAll,
    DAZ_OT_SelectNone,

    DAZ_OT_Update,
    DAZ_OT_SelectAllMorphs,
    DAZ_OT_ImportUnits,
    DAZ_OT_ImportExpressions,
    DAZ_OT_ImportVisemes,
    DAZ_OT_ImportFacs,
    DAZ_OT_ImportFacsExpressions,
    DAZ_OT_ImportBodyMorphs,
    DAZ_OT_ImportFlexions,
    DAZ_OT_ImportStandardMorphs,
    DAZ_OT_ImportCustomMorphs,
    DAZ_OT_ImportJCMs,
    DAZ_OT_AddShapeToCategory,
    DAZ_OT_RemoveShapeFromCategory,
    DAZ_OT_RenameCategory,
    DAZ_OT_Prettify,
    DAZ_OT_ActivateAll,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_ClearShapes,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_KeyShapes,
    DAZ_OT_UnkeyShapes,
    DAZ_OT_UpdateSliderLimits,
    DAZ_OT_AddDrivenValueNodes,
    DAZ_OT_RemoveAllDrivers,
    DAZ_OT_AddShapekeyDrivers,
    DAZ_OT_RemoveShapekeyDrivers,
    DAZ_OT_ToggleAllCats,
    DAZ_OT_PinProp,
    DAZ_OT_PinShape,
    DAZ_OT_LoadMoho,
    DAZ_OT_ConvertStandardMorphsToShapes,
    DAZ_OT_ConvertCustomMorphsToShapes,
    DAZ_OT_MeshToShape,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazCustomMorphs = BoolProperty(default = False)
    bpy.types.Object.DazMeshMorphs = BoolProperty(default = False)
    bpy.types.Object.DazMorphAuto = BoolProperty(default = False)

    bpy.types.Object.DazMorphPrefixes = BoolProperty(default = True)
    for morphset in theMorphSets:
        setattr(bpy.types.Object, "Daz"+morphset, CollectionProperty(type = DazTextGroup))
    bpy.types.Object.DazAutoFollow = CollectionProperty(type = DazTextGroup)

    if bpy.app.version < (2,90,0):
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup)
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory)
    else:
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Mesh.DazBodyPart = CollectionProperty(type = DazStringGroup)
    bpy.types.Mesh.DazHdUrls = CollectionProperty(type = DazStringGroup)
    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items = [],
        name = "Morph")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name = "New Name",
        default = "Name")

    bpy.types.Scene.DazSelector = CollectionProperty(type = DazSelectGroup)
    bpy.types.Object.DazPropNames = CollectionProperty(type = DazTextGroup)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


