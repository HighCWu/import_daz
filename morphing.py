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
from . import utils
from .fileutils import SingleFile, MultiFile, DazImageFile, DatFile
from .propgroups import DazTextGroup, DazFloatGroup

#-------------------------------------------------------------
#   Morph sets
#-------------------------------------------------------------

theStandardMorphSets = ["Units", "Expressions", "Visemes", "Facs", "Facsexpr", "Body"]
theCustomMorphSets = ["Custom"]
theJCMMorphSets = ["Standardjcms", "Flexions"]
theMorphSets = theStandardMorphSets + theCustomMorphSets + theJCMMorphSets + ["Visibility"]
theMorphEnums = []


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

    ?type: Either a string in ["Units", "Expressions", "Visemes", "Facs", "Facsexpr", "Body", "Custom", "Standardjcms", "Flexions"],
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

class CustomEnums:
    custom : EnumProperty(
        items = G.getActiveCategories,
        name = "Category")

class DeleteShapekeysBool:
    deleteShapekeys : BoolProperty(
        name = "Delete Shapekeys",
        description = "Delete both drivers and shapekeys",
        default = True
    )


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


    def getSelectedItems(self, scn):
        return [item for item in self.selection if item.select and self.isSelected(item)]


    def getSelectedProps(self, scn):
        from .fileutils import getSelection
        if getSelection():
            return getSelection()
        else:
            return [item.name for item in self.getSelectedItems(scn)]


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


class StandardSelector(Selector):
    morphset : EnumProperty(
        items = G.getMorphEnums,
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
                        isright,name = isRightType(fname, prefixes, includes, excludes)
                        if isright:
                            #name = getCanonicalKey(name)
                            fname = fname.lower()
                            fpath = os.path.join(folder, file)
                            typeFiles[name] = os.path.join(folderpath, file)
                            prop = BoolProperty(name=name, default=True)
                            setattr(bpy.types.Scene, "Daz"+name, prop)
                            typeNames[fname] = name


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
#   LoadMorph base class
#------------------------------------------------------------------

from .formula import PoseboneDriver

class LoadMorph(PoseboneDriver):
    morphset = None
    usePropDrivers = True
    useMeshCats = False

    def __init__(self, mesh=None):
        from .finger import getFingeredCharacter
        self.rig, self.mesh, self.char = getFingeredCharacter(bpy.context.object)
        if mesh:
            self.mesh = mesh


    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)


    def getAllMorphs(self, namepaths, context):
        import time
        from .asset import clearAssets
        from .main import finishMain
        from .propgroups import clearDependecies

        if self.mesh:
            ob = self.mesh
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        LS.forMorphLoad(ob, context.scene)
        if not self.usePropDrivers:
            self.rig = None
        clearDependecies()

        self.errors = {}
        t1 = time.perf_counter()
        if namepaths:
            path = list(namepaths.values())[0]
            folder = os.path.dirname(path)
        else:
            raise DazError("No morphs selected")
        self.makeAllMorphs(list(namepaths.items()))
        if self.rig:
            self.buildDrivers()
            self.buildSumDrivers()
            updateDrivers(self.rig)
            updateDrivers(self.mesh)
        finishMain("Folder", folder, t1)
        if self.errors:
            msg = "Morphs loaded with errors.\n  "
            for err,props in self.errors.items():
                msg += "\n%s:    \n" % err
                for prop in props:
                    msg += "    %s\n" % prop
            raise DazError(msg, warning=True)

    #------------------------------------------------------------------
    #   Make all morphs
    #------------------------------------------------------------------

    def makeAllMorphs(self, namepaths):
        print("Making morphs")
        self.alias = {}
        self.drivers = {}
        self.shapekeys = {}
        self.mults = {}
        self.sumdrivers = {}
        namepaths.sort()
        idx = 0
        npaths = len(namepaths)
        for name,path in namepaths:
            showProgress(idx, npaths)
            idx += 1
            char = self.makeSingleMorph(name, path)
            print(char, name)

    #------------------------------------------------------------------
    #   First pass: collect data
    #------------------------------------------------------------------

    def makeSingleMorph(self, name, filepath):
        from .load_json import loadJson
        from .files import parseAssetFile
        struct = loadJson(filepath)
        asset = parseAssetFile(struct)
        if asset is None:
            if GS.verbosity > 1:
                msg = ("Not a morph asset:\n  '%s'" % filepath)
                if self.suppressError:
                    print(msg)
                else:
                    raise DazError(msg)
            return " -"
        self.buildShapekey(asset)
        if self.rig:
            self.makeFormulas(asset)
        return " *"


    def buildShapekey(self, asset, useBuild=True):
        from .modifier import Morph
        from .driver import makePropDriver
        if not (isinstance(asset, Morph) and
                self.mesh and
                asset.deltas):
            return None
        useBuild = True
        if asset.vertex_count < 0:
            print("Vertex count == %d" % asset.vertex_count)
        elif asset.vertex_count != len(self.mesh.data.vertices):
            msg = ("Vertex count mismatch:\n  %d != %d" % (asset.vertex_count, len(self.mesh.data.vertices)))
            if GS.verbosity > 2:
                print(msg)
            if asset.hd_url:
                if self.treatHD == 'CREATE':
                    useBuild = False
                elif self.treatHD == 'ACTIVE':
                    skey = self.getActiveShape(asset)
            if useBuild and not skey:
                return None
        if not asset.rna:
            asset.buildMorph(self.mesh,
                             useBuild=useBuild,
                             useSoftLimits=False,
                             morphset=self.morphset,
                             strength=self.strength)
        skey,_,sname = asset.rna
        if skey:
            prop = unquote(skey.name)
            self.alias[prop] = skey.name
            skey.name = prop
            self.shapekeys[prop] = skey
            if self.rig:
                final = self.addNewProp(prop, asset)
                makePropDriver(propRef(final), skey, "value", self.rig, "x")
        return skey


    def makeFormulas(self, asset):
        from .formula import Formula
        if not isinstance(asset, Formula):
            print("Not a formula", asset)
            return

        exprs = {}
        props = {}
        asset.evalFormulas(exprs, props, self.rig, self.mesh)
        for prop in props.keys():
            self.addNewProp(prop, asset)
        for output,data in exprs.items():
            for key,data1 in data.items():
                for idx,expr in data1.items():
                    if key == "value":
                        self.makeValueFormula(output, expr, asset)
                    elif key == "rotation":
                        self.makeRotFormula(output, idx, expr, asset)
                    elif key == "translation":
                        self.makeTransFormula(output, idx, expr, asset)
                    elif key == "scale":
                        self.makeTransFormula(output, idx, expr, asset)


    def addNewProp(self, raw, asset):
        final = self.getFinalProp(raw)
        if raw in self.drivers.keys():
            return final
        from .driver import setFloatProp
        from .modifier import addToMorphSet
        self.drivers[raw] = []
        setFloatProp(self.rig, raw, 0.0, asset.min, asset.max)
        setActivated(self.rig, raw, True)
        addToMorphSet(self.rig, self.morphset, raw)
        self.rig[final] = 0.0
        return final


    def makeValueFormula(self, output, expr, asset):
        if expr["prop"]:
            self.addNewProp(output, asset)
            prop = expr["prop"]
            self.drivers[output].append(("PROP", prop, expr["factor"]))
        if expr["mult"]:
            if output not in self.mults.keys():
                self.mults[output] = []
            mult = expr["mult"]
            self.mults[output].append(mult)
            self.addNewProp(mult, asset)
        if expr["bone"]:
            bname = self.getRealBone(expr["bone"])
            if bname:
                if output not in self.drivers.keys():
                    self.drivers[output] = []
                self.drivers[output].append(("BONE", bname, expr))
            else:
                print("Missing bone:", expr["bone"])


    def getRealBone(self, bname):
        from .bone import getTargetName
        if (self.rig.data.DazExtraFaceBones or
            self.rig.data.DazExtraDrivenBones):
            dname = bname + "Drv"
            if dname in self.rig.pose.bones.keys():
                bname = dname
        return getTargetName(bname, self.rig)


    def getBoneData(self, bname, expr, asset):
        from .bone import getTargetName
        from .transform import Transform
        bname = getTargetName(bname, self.rig)
        if bname is None:
            return
        pb = self.rig.pose.bones[bname]
        factor = expr["factor"]
        raw = expr["prop"]
        final = self.addNewProp(raw, asset)
        tfm = Transform()
        return tfm, pb, final, factor


    def getFinalProp(self, prop):
        assert(len(prop) >= 1)
        return "%s(fin)" % prop


    def makeRotFormula(self, bname, idx, expr, asset):
        tfm,pb,prop,factor = self.getBoneData(bname, expr, asset)
        tfm.setRot(self.strength*factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeTransFormula(self, bname, idx, expr, asset):
        tfm,pb,prop,factor = self.getBoneData(bname, expr, asset)
        tfm.setTrans(self.strength*factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeScaleFormula(self, bname, idx, expr, asset):
        tfm,pb,prop,factor = self.getBoneData(bname, expr, asset)
        tfm.setScale(self.strength*factor, prop, False, index=idx)
        self.addPoseboneDriver(pb, tfm)

    #------------------------------------------------------------------
    #   Second pass: Build the drivers
    #------------------------------------------------------------------

    def buildDrivers(self):
        print("Building drivers")
        for output,drivers in self.drivers.items():
            if drivers:
                dtype = drivers[0][0]
                if dtype == 'PROP':
                    self.buildPropDriver(output, drivers)
                elif dtype == 'BONE':
                    self.buildBoneDriver(output, drivers)
            else:
                self.buildPropDriver(output, drivers)


    def buildPropDriver(self, raw, drivers):
        def multiply(factor, varname):
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "+%g*%s" % (factor, varname)

        from .driver import addDriverVar
        mults = []
        if raw in self.mults.keys():
            mults = self.mults[raw]
        final = self.getFinalProp(raw)
        channel = propRef(final)
        self.rig.driver_remove(channel)
        fcu = self.rig.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        varname = "a"
        expr = varname
        addDriverVar(fcu, varname, propRef(raw), self.rig)
        for dtype,subraw,factor in drivers:
            if dtype != 'PROP':
                continue
            subfinal = self.getFinalProp(subraw)
            varname = nextLetter(varname)
            expr += multiply(factor, varname)
            addDriverVar(fcu, varname, propRef(subfinal), self.rig)
        if mults:
            expr = "(%s)" % expr
            varname = "M"
            for mult in mults:
                expr += "*%s" % varname
                multfinal = self.getFinalProp(mult)
                addDriverVar(fcu, varname, propRef(multfinal), self.rig)
                varname = nextLetter(varname)
        fcu.driver.expression = expr


    def buildBoneDriver(self, raw, drivers):
        def getSplinePoints(expr, pb, comp):
            points = expr["points"]
            n = len(points)
            if (points[0][0] > points[n-1][0]):
                points.reverse()

            diff = points[n-1][0] - points[0][0]
            uvec = getBoneVector(1/diff, comp, pb)
            xys = []
            for k in range(n):
                x = points[k][0]/diff
                y = points[k][1]
                xys.append((x, y))
            return uvec, xys

        _,bname,expr = drivers[0]
        final = self.getFinalProp(raw)
        channel = propRef(final)
        self.rig.driver_remove(channel)
        pb = self.rig.pose.bones[bname]
        rna = self.rig
        comp = expr["comp"]

        from .driver import makeSplineBoneDriver, makeProductBoneDriver, makeSimpleBoneDriver
        from .formula import getBoneVector
        if "points" in expr.keys():
            uvec,xys = getSplinePoints(expr, pb, comp)
            makeSplineBoneDriver(uvec, xys, rna, channel, -1, self.rig, bname)
        elif isinstance(expr["factor"], list):
            print("FOO", expr)
            halt
            uvecs = []
            for factor in expr["factor"]:
                uvec = getBoneVector(factor, comp, pb)
                uvecs.append(uvec)
            makeProductBoneDriver(uvecs, rna, channel, -1, self.rig, bname)
        else:
            factor = expr["factor"]
            uvec = getBoneVector(factor, comp, pb)
            makeSimpleBoneDriver(uvec, rna, channel, -1, self.rig, bname)

    #------------------------------------------------------------------
    #   Build sum drivers
    #   For Xin's non-python drivers
    #------------------------------------------------------------------

    def buildSumDrivers(self):
        def getTermDriverName(prop, key, idx):
            return ("%s:%s:%d" % (prop.split("(",1)[0], key, idx))

        def getTermDriverExpr(varname, factor1, factor2, default):
            if default > 0:
                term = "(%s+%g)" % (varname, default)
            elif default < 0:
                term = "(%s-%g)" % (varname, default)
            else:
                term = varname
            if factor2:
                return "(%g if %s > 0 else %g)*%s" % (factor1, term, factor2, term)
            elif factor1 == 1:
                return term
            else:
                return "%g*%s" % (factor1, term)

        from .driver import addDriverVar, Driver
        print("Building sum drivers")
        for bname,data in self.sumdrivers.items():
            print(" +", bname)
            for channel,kdata in data.items():
                for idx,idata in kdata.items():
                    pb,fcu0,dlist = idata
                    if fcu0:
                        if fcu0.driver.type == 'SUM':
                            for var in fcu0.driver.variables:
                                if var.name.startswith(self.prefix):
                                    fcu0.driver.variables.remove(var)
                            sumfcu = fcu0
                        else:
                            prop0 = "origo:%d" % idx
                            pb[prop0] = 0.0
                            fcu = pb.driver_add(propRef(prop0))
                            driver = Driver(fcu0, True)
                            driver.fill(fcu)
                            pb.driver_remove(channel, idx)
                            sumfcu = pb.driver_add(channel, idx)
                            sumfcu.driver.type = 'SUM'
                            path0 = 'pose.bones["%s"]["%s"]' % (pb.name, prop0)
                            addDriverVar(sumfcu, "x", path0, self.rig)
                    else:
                        sumfcu = pb.driver_add(channel, idx)
                        sumfcu.driver.type = 'SUM'

                    for n,data in enumerate(dlist):
                        key,prop,factor1,factor2,default = data
                        drvprop = getTermDriverName(prop, key, idx)
                        pb[drvprop] = 0.0
                        path = propRef(drvprop)
                        pb.driver_remove(path)
                        fcu = pb.driver_add(path)
                        fcu.driver.type = 'SCRIPTED'
                        fcu.driver.expression = getTermDriverExpr("x", factor1, factor2, default)
                        addDriverVar(fcu, "x", propRef(prop), self.rig)
                        path2 = 'pose.bones["%s"]%s' % (pb.name, path)
                        addDriverVar(sumfcu, "%s%.03d" % (self.prefix, n), path2, self.rig)


    def getActiveShape(self, asset):
        ob = self.mesh
        sname = asset.name
        skey = None
        if ob.data.shape_keys:
            skey = ob.data.shape_keys.key_blocks[ob.active_shape_key_index]
            skey.name = sname
        return skey, ob, sname

#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class LoadAllMorphs(LoadMorph):
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
            for item in self.getSelectedItems(context.scene):
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


class DAZ_OT_ImportUnits(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_units"
    bl_label = "Import Units"
    bl_description = "Import selected face unit morphs"
    bl_options = {'UNDO'}

    prefix = "u"
    morphset = "Units"


class DAZ_OT_ImportExpressions(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_expressions"
    bl_label = "Import Expressions"
    bl_description = "Import selected expression morphs"
    bl_options = {'UNDO'}

    prefix = "e"
    morphset = "Expressions"


class DAZ_OT_ImportVisemes(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_visemes"
    bl_label = "Import Visemes"
    bl_description = "Import selected viseme morphs"
    bl_options = {'UNDO'}

    prefix = "v"
    morphset = "Visemes"


class DAZ_OT_ImportFacs(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_facs"
    bl_label = "Import FACS Units"
    bl_description = "Import selected FACS unit morphs"
    bl_options = {'UNDO'}

    prefix = "f"
    morphset = "Facs"


class DAZ_OT_ImportFacsExpressions(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_facs_expressions"
    bl_label = "Import FACS Expressions"
    bl_description = "Import selected FACS expression morphs"
    bl_options = {'UNDO'}

    prefix = "g"
    morphset = "Facsexpr"


class DAZ_OT_ImportBodyMorphs(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMeshArmature):
    bl_idname = "daz.import_body_morphs"
    bl_label = "Import Body Morphs"
    bl_description = "Import selected body morphs"
    bl_options = {'UNDO'}

    prefix = "y"
    morphset = "Body"


class DAZ_OT_ImportJCMs(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMesh):
    bl_idname = "daz.import_jcms"
    bl_label = "Import JCMs"
    bl_description = "Import selected joint corrective morphs"
    bl_options = {'UNDO'}

    prefix = "j"
    morphset = "Standardjcms"

    useShapekeysOnly = True
    useSoftLimits = False


class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, LoadAllMorphs, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    prefix = "k"
    morphset = "Flexions"

    useShapekeysOnly = True
    useSoftLimits = False

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class DAZ_OT_ImportCustomMorphs(DazOperator, LoadMorph, DazImageFile, MultiFile, IsMeshArmature):
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
        self.prefix = "_%s_" % self.catname
        namepaths = self.getNamePaths()
        self.getAllMorphs(namepaths, context)
        if self.usePropDrivers and self.drivers:
            props = []
            for key,drivers in self.drivers.items():
                if not drivers or drivers[0][0] == 'PROP':
                    props.append(key)
            addToCategories(self.rig, props, self.catname)
            self.rig.DazCustomMorphs = True
        elif self.useMeshCats and self.shapekeys:
            addToCategories(self.mesh, self.shapekeys, self.catname)
            self.mesh.DazMeshMorphs = True
        if self.errors:
            raise DazError(theLimitationsMessage)


    def getNamePaths(self):
        from .fileutils import getMultiFiles
        namepaths = {}
        folder = ""
        for path in getMultiFiles(self, ["duf", "dsf"]):
            name = os.path.splitext(os.path.basename(path))[0]
            namepaths[name] = path
        return namepaths

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


def removeFromCategory(ob, props, catname):
    if catname in ob.DazMorphCats.keys():
        cat = ob.DazMorphCats[catname]
        for prop in props:
            removeFromPropGroup(cat.morphs, prop)

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


class DAZ_OT_RemoveCategories(DazOperator, Selector, IsMeshArmature, DeleteShapekeysBool):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    def drawExtra(self, context):
        self.layout.prop(self, "deleteShapekeys")

    def run(self, context):
        items = [(item.index, item.name) for item in self.getSelectedItems(context.scene)]
        items.sort()
        items.reverse()
        ob = context.object
        if ob.type == 'ARMATURE':
            self.runRig(context, ob, items)
        elif ob.type == 'MESH':
            self.runMesh(context, ob, items)


    def runMesh(self, context, ob, items):
        for idx,key in items:
            cat = ob.DazMorphCats[key]
            ob.DazMorphCats.remove(idx)
        if len(ob.DazMorphCats) == 0:
            ob.DazMeshMorphs = False


    def runRig(self, context, rig, items):
        from .driver import removePropDrivers
        for idx,key in items:
            cat = rig.DazMorphCats[key]
            for pg in cat.morphs:
                if pg.name in rig.keys():
                    rig[pg.name] = 0.0
                path = ('["%s"]' % pg.name)
                keep = removePropDrivers(rig, path, rig)
                for ob in rig.children:
                    if ob.type == 'MESH':
                        if removePropDrivers(ob.data.shape_keys, path, rig):
                            keep = True
                        if self.deleteShapekeys and ob.data.shape_keys:
                            if pg.name in ob.data.shape_keys.key_blocks.keys():
                                skey = ob.data.shape_keys.key_blocks[pg.name]
                                ob.shape_key_remove(skey)
                if pg.name in rig.keys():
                    removeFromPropGroups(rig, pg.name, keep)
            rig.DazMorphCats.remove(idx)
        if len(rig.DazMorphCats) == 0:
            rig.DazCustomMorphs = False


    def selectCondition(self, item):
        return True


    def getKeys(self, rig, ob):
        keys = []
        for cat in ob.DazMorphCats:
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


def addToPropGroup(prop, ob, morphset, asset=None):
    from .modifier import getCanonicalKey
    pg = getattr(ob, "Daz"+morphset)
    if prop not in pg.keys():
        item = pg.add()
        item.name = prop
        if asset is None:
            item.text = getCanonicalKey(prop)
        elif asset.visible:
            item.text = asset.label
        else:
            item.text = "[%s]" % getCanonicalKey(prop)
        setActivated(ob, prop, True)


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
        if getActivated(rig, rig, morph, force):
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
    bl_description = "Set all morphs of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            clearMorphs(rig, self.morphset, self.category, scn, scn.frame_current, False)
            updateDrivers(rig)


class DAZ_OT_ClearShapes(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.clear_shapes"
    bl_label = "Clear Shapes"
    bl_description = "Set all shapekeys values of specified type to zero"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        clearShapes(context.object, self.category, scn, scn.frame_current)


class DAZ_OT_UpdateMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.update_morphs"
    bl_label = "Update Morphs For Version 1.5"
    bl_description = "Update morphs for the new morph system in version 1.5"
    bl_options = {'UNDO'}

    key : StringProperty()

    morphsets = {"DzU" : "Units",
                 "DzE" : "Expressions",
                 "DzV" : "Visemes",
                 "DzP" : "Body",
                 "DzC" : "Standardjcms",
                 "DzF" : "Flexions",
                 "DzM" : "Custom",
                 "Mhh" : "Visibility"
                }


    def run(self, context):
        from .propgroups import getAllPropGroups
        for ob in context.scene.objects:
            for key in ob.keys():
                self.updateKey(ob, key)
            for cat in ob.DazMorphCats:
                for item in cat.morphs:
                    item.text = item.name
                    if item.text[0:2] == "Dz":
                        item.text = item.text[3:]
            if ob.type == 'MESH' and ob.data.shape_keys:
                for key in ob.data.shape_keys.key_blocks.keys():
                    self.updateKey(ob, key)
            elif ob.type == 'ARMATURE':
                bad = False
                for pb in ob.pose.bones:
                    for pgs in getAllPropGroups(pb):
                        for pg in pgs:
                            if pg.prop:
                                pg.name = pg.prop
                            elif pg.name:
                                pg.prop = pg.name
                            else:
                                bad = True
                if bad:
                    self.removeAllMorphs(ob)
            updateDrivers(ob)
            ob.DazMorphPrefixes = False
        prettifyAll(context)


    def removeAllMorphs(self, rig):
        from propgroups import getAllPropGroups
        for pb in rig.pose.bones:
            for pgs in getAllPropGroups(pb):
                pgs.clear()
        deletes = []
        for key in rig.keys():
            if key[0:3] in self.morphsets.keys():
                deletes.append(key)
        for key in deletes:
            rig[key] = 0
            del rig[key]


    def updateKey(self, ob, key):
        prefix = key[0:3]
        if prefix[0:2] == "Dz" or prefix == "Mhh":
            if prefix not in self.morphsets.keys():
                return
            prop = "Daz" + self.morphsets[prefix]
            pg = getattr(ob, prop)
            if key not in pg.keys():
                item = pg.add()
                item.name = key
                item.text = key[3:]
            else:
                print("Duplicate", key)

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
            updateDrivers(rig)

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
            updateScene(context)
            updateRig(rig, context)


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
            updateScene(context)
            updateRig(rig, context)


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

class DAZ_OT_UpdatePropLimits(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.update_prop_limits"
    bl_label = "Update Property Limits"
    bl_description = "Update min and max value for properties"
    bl_options = {'UNDO'}

    def draw(self, context):
        scn = context.scene
        self.layout.prop(scn, "DazPropMin")
        self.layout.prop(scn, "DazPropMax")


    def run(self, context):
        ob = context.object
        scn = context.scene
        GS.propMin = scn.DazPropMin
        GS.propMax = scn.DazPropMax
        rig = getRigFromObject(ob)
        if rig:
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)


    def invoke(self, context, event):
        context.scene.DazPropMin = GS.propMin
        context.scene.DazPropMax = GS.propMax
        return DazPropsOperator.invoke(self, context, event)


    def updatePropLimits(self, rig, context):
        from .driver import setFloatProp
        scn = context.scene
        props = getAllLowerMorphNames(rig)
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys:
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in props:
                        skey.slider_min = GS.propMin
                        skey.slider_max = GS.propMax
        for prop in rig.keys():
            if prop.lower() in props:
                setFloatProp(rig, prop, rig[prop], GS.propMin, GS.propMax)
        updateScene(context)
        updateRig(rig, context)
        print("Property limits updated")

#------------------------------------------------------------------
#   Remove all morph drivers
#------------------------------------------------------------------

class DAZ_OT_RemoveAllShapekeyDrivers(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.remove_all_shapekey_drivers"
    bl_label = "Remove All Shapekey Drivers"
    bl_description = "Remove all shapekey drivers"
    bl_options = {'UNDO'}

    useStandard : BoolProperty(
        name = "Standard Morphs",
        description = "Remove drivers to all standard morphs",
        default = True)

    useCustom : BoolProperty(
        name = "Custom Morphs",
        description = "Remove drivers to all custom morphs",
        default = True)

    useJCM : BoolProperty(
        name = "JCMs",
        description = "Remove drivers to all JCMs",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "useStandard")
        self.layout.prop(self, "useCustom")
        self.layout.prop(self, "useJCM")


    def run(self, context):
        from .driver import removeRigDrivers, removePropDrivers
        morphsets = []
        force = False
        if self.useStandard:
            morphsets += theStandardMorphSets
        if self.useCustom:
            morphsets += theCustomMorphSets
        if self.useJCM:
            morphsets += theJCMMorphSets
            force = True
        scn = context.scene
        rig = getRigFromObject(context.object)
        if rig:
            setupMorphPaths(scn, False)
            removeRigDrivers(rig)
            self.clearPropGroups(rig)
            if self.useCustom:
                self.removeCustom(rig, morphsets)
            self.removeMorphSets(rig, morphsets)
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    removePropDrivers(ob.data.shape_keys, force=force)
                    if self.useCustom:
                        self.removeCustom(ob, morphsets)
                    self.removeMorphSets(ob, morphsets)
            updateScene(context)
            updateRig(rig, context)


    def clearPropGroups(self, rig):
        from .propgroups import getAllPropGroups
        for pb in rig.pose.bones:
            for pgs in getAllPropGroups(pb):
                pgs.clear()
            pb.location = (0,0,0)
            pb.rotation_euler = (0,0,0)
            pb.rotation_quaternion = (1,0,0,0)
            pb.scale = (1,1,1)


    def removeCustom(self, rig, morphsets):
        rig.DazCustomMorphs = False
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                key = morph.name
                if key in rig.keys():
                    rig[key] = 0.0
                    del rig[key]
        rig.DazMorphCats.clear()


    def removeMorphSets(self, rig, morphsets):
        for item in getMorphList(rig, morphsets):
            key = item.name
            if key in rig.keys():
                rig[key] = 0.0
                del rig[key]

        for morphset in morphsets:
            pg = getattr(rig, "Daz"+morphset)
            pg.clear()


#-------------------------------------------------------------
#   Remove specific morphs
#-------------------------------------------------------------

class MorphRemover(DeleteShapekeysBool):
    def run(self, context):
        rig = getRigFromObject(context.object)
        scn = context.scene
        if rig:
            props = self.getSelectedProps(scn)
            print("Remove", props)
            paths = ['["%s"]' % prop for prop in props]
            for ob in rig.children:
                if ob.type == 'MESH' and ob.data.shape_keys:
                    self.removeShapekeyDrivers(ob, paths, props, rig)
                    if self.deleteShapekeys:
                        for prop in props:
                            if prop in ob.data.shape_keys.key_blocks.keys():
                                skey = ob.data.shape_keys.key_blocks[prop]
                                ob.shape_key_remove(skey)
            for prop in props:
                removeFromPropGroups(rig, prop)
            self.finishRemove(rig, props)
            updateScene(context)
            updateRig(rig, context)


    def removeShapekeyDrivers(self, ob, paths, props, rig):
        from .driver import removePropDrivers
        removePropDrivers(ob.data.shape_keys, paths, rig, force=True)


    def finishRemove(self, rig, props):
        return


class DAZ_OT_RemoveStandardMorphs(DazOperator, StandardSelector, MorphRemover, IsMeshArmature):
    bl_idname = "daz.remove_standard_morphs"
    bl_label = "Remove Standard Morphs"
    bl_description = "Remove specific standard morphs and their associated drivers"
    bl_options = {'UNDO'}

    def drawExtra(self, context):
        self.layout.prop(self, "deleteShapekeys")


class DAZ_OT_RemoveCustomMorphs(DazOperator, CustomSelector, MorphRemover, IsMeshArmature):
    bl_idname = "daz.remove_custom_morphs"
    bl_label = "Remove Custom Morphs"
    bl_description = "Remove specific custom morphs and their associated drivers"
    bl_options = {'UNDO'}

    morphset = "Custom"

    def drawExtra(self, context):
        self.layout.prop(self, "deleteShapekeys")

    def finishRemove(self, rig, props):
        for cat in rig.DazMorphCats:
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)
        removes = []
        for cat in rig.DazMorphCats:
            if len(cat.morphs) == 0:
                removes.append(cat.name)
        for catname in removes:
            print("Remove category", catname)
            removeFromPropGroup(rig.DazMorphCats, catname)


class DAZ_OT_RemoveJCMs(DazOperator, Selector, MorphRemover, IsMesh):
    bl_idname = "daz.remove_jcms"
    bl_label = "Remove JCMs"
    bl_description = "Remove specific JCMs"
    bl_options = {'UNDO'}

    allSets = theJCMMorphSets

    def getKeys(self, rig, ob):
        skeys = ob.data.shape_keys
        if skeys:
            morphs = getMorphList(ob, theJCMMorphSets)
            return [(item.name, item.text, "All") for item in morphs
                    if item.name in skeys.key_blocks.keys()]
        else:
            return []


    def removeShapekeyDrivers(self, ob, paths, snames, rig):
        from .driver import getShapekeyDriver
        skeys = ob.data.shape_keys
        for sname in snames:
            if sname in skeys.key_blocks.keys():
                skey = skeys.key_blocks[sname]
                if getShapekeyDriver(skeys, sname):
                    skey.driver_remove("value")


    def run(self, context):
        self.deleteShapekeys = True
        MorphRemover.run(self, context)

#-------------------------------------------------------------
#   Add driven value nodes
#-------------------------------------------------------------

class DAZ_OT_AddDrivenValueNodes(DazOperator, Selector, IsMesh):
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
        from .driver import getShapekeyDriver, copyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromObject(ob)
        scn = context.scene
        mat = ob.data.materials[ob.active_material_index]
        props = self.getSelectedProps(scn)
        nprops = len(props)
        for n,prop in enumerate(props):
            skey = skeys.key_blocks[prop]
            fcu = getShapekeyDriver(skeys, prop)
            node = mat.node_tree.nodes.new(type="ShaderNodeValue")
            node.name = node.label = skey.name
            node.location = (-800, 250-250*n)
            if fcu:
                channel = ('nodes["%s"].outputs[0].default_value' % node.name)
                copyDriver(fcu, mat.node_tree, channel2=channel)


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
        for sname in self.getSelectedProps(context.scene):
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
        from .driver import makeShapekeyDriver
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        makeShapekeyDriver(skeys, sname, skey.value, rig, sname, {})
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
        for sname in self.getSelectedProps(context.scene):
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in ob.DazMorphCats:
                removeFromCategory(ob, snames, cat.name)
        else:
            removeFromCategory(ob, snames, self.custom)


    def includeShapekey(self, skeys, sname):
        return True


    def getCategory(self, rig, ob, sname):
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""


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
    rig.keyframe_insert('["%s"]' % key, frame=frame)


def keyShape(skeys, key, frame):
    skeys.keyframe_insert('key_blocks["%s"].value' % key, frame=frame)


def unkeyProp(rig, key, frame):
    try:
        rig.keyframe_delete('["%s"]' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def unkeyShape(skeys, key, frame):
    try:
        skeys.keyframe_delete('key_blocks["%s"].value' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = '["%s"]' % key
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
        updateDrivers(rig)


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
        updateDrivers(rig)
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


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

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
    DAZ_OT_ImportCustomMorphs,
    DAZ_OT_ImportJCMs,
    DAZ_OT_AddShapeToCategory,
    DAZ_OT_RemoveShapeFromCategory,
    DAZ_OT_RenameCategory,
    DAZ_OT_RemoveCategories,
    DAZ_OT_Prettify,
    DAZ_OT_ActivateAll,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_ClearShapes,
    DAZ_OT_UpdateMorphs,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_KeyShapes,
    DAZ_OT_UnkeyShapes,
    DAZ_OT_UpdatePropLimits,
    DAZ_OT_RemoveStandardMorphs,
    DAZ_OT_RemoveCustomMorphs,
    DAZ_OT_RemoveJCMs,
    DAZ_OT_AddDrivenValueNodes,
    DAZ_OT_RemoveAllShapekeyDrivers,
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

    bpy.types.Object.DazMorphPrefixes = BoolProperty(default = True)
    for morphset in theMorphSets:
        setattr(bpy.types.Object, "Daz"+morphset, CollectionProperty(type = DazTextGroup))

    if bpy.app.version < (2,90,0):
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup)
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory)
    else:
        bpy.types.Object.DazActivated = CollectionProperty(type = DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
        bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory, override={'LIBRARY_OVERRIDABLE'})

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


