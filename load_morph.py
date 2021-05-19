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
from .driver import DriverUser
from .utils import *
from .error import reportError

MAX_EXPRESSION_SIZE = 255
MAX_TERMS = 12
MAX_TERMS2 = 9
MAX_EXPR_LEN = 240

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

class LoadMorph(DriverUser):
    morphset = None
    usePropDrivers = True
    loadMissed = True
    isJcm = False

    def __init__(self, rig, mesh):
        self.rig = rig
        self.mesh = mesh
        self.initAmt()
        self.mult = []
        self.mults = {}


    def initAmt(self):
        if self.rig:
            self.amt = self.rig.data
        else:
            self.amt = None


    def loadAllMorphs(self, namepaths):
        DriverUser.__init__(self)
        self.alias = {}
        self.loaded = []
        self.referred = {}
        self.primary = {}
        self.visible = {}
        self.ecr = False
        self.drivers = {}
        self.shapekeys = {}
        self.mults = {}
        self.sumdrivers = {}
        self.restdrivers = {}
        self.initAmt()
        print("Making morphs")
        self.makeAllMorphs(namepaths, True)
        if self.loadMissed:
            print("Making missing morphs")
            bodypart = namepaths[0][2]
            self.makeMissingMorphs(bodypart)
        if self.rig:
            self.createTmp()
            try:
                self.buildDrivers()
                self.buildSumDrivers()
                self.buildRestDrivers()
            finally:
                self.deleteTmp()
            self.rig.update_tag()
            if self.mesh:
                self.mesh.update_tag()

    #------------------------------------------------------------------
    #   Make all morphs
    #------------------------------------------------------------------

    def makeAllMorphs(self, namepaths, force):
        namepaths.sort()
        idx = 0
        npaths = len(namepaths)
        for name,path,bodypart in namepaths:
            showProgress(idx, npaths)
            idx += 1
            char = self.makeSingleMorph(name, path, bodypart, force)
            print(char, name)

    #------------------------------------------------------------------
    #   First pass: collect data
    #------------------------------------------------------------------

    def makeSingleMorph(self, name, filepath, bodypart, force):
        from .load_json import loadJson
        from .files import parseAssetFile
        from .modifier import Alias, ChannelAsset
        struct = loadJson(filepath)
        asset = parseAssetFile(struct)
        fileref = self.getFileRef(filepath)
        self.loaded.append(fileref)
        if not force:
            raw = asset.getName()
            final = finalProp(raw)
            if raw in self.rig.keys() and final in self.amt.keys():
                return " ."
        if not isinstance(asset, ChannelAsset):
            return " -"
        elif isinstance(asset, Alias):
            return " _"
        skey,ok = self.buildShapekey(asset, bodypart)
        if not ok:
            return " #"
        elif self.rig:
            self.makeFormulas(asset, skey)
        aliaspath = self.getAliasFile(filepath)
        aliases = {}
        if aliaspath is not None:
            aliases = self.loadAlias(aliaspath)
        self.addUrl(asset, aliases, filepath, bodypart)
        return " *"


    def getAliasFile(self, filepath):
        folder = os.path.dirname(filepath)
        file1 = os.path.basename(filepath)
        for file in os.listdir(folder):
            if (file[0:5] == "alias" and
                file.endswith(file1)):
                return os.path.join(folder, file)
        return None


    def loadAlias(self, filepath):
        from .load_json import loadJson
        struct = loadJson(filepath)
        aliases = {}
        if "modifier_library" in struct.keys():
            for mod in struct["modifier_library"]:
                if "channel" in mod.keys():
                    channel = mod["channel"]
                    if ("type" in channel.keys() and
                        channel["type"] == "alias"):
                        alias = channel["name"]
                        prop = channel["target_channel"].rsplit('#')[-1].split("?")[0]
                        if alias != prop:
                            print(" = %s %s" % (prop, alias))
                            pgs = self.rig.DazAlias
                            if alias in pgs.keys():
                                pg = pgs[alias]
                            else:
                                pg = pgs.add()
                                pg.name = alias
                            pg.s = prop
                            aliases[alias] = prop
        return aliases


    def buildShapekey(self, asset, bodypart, useBuild=True):
        from .modifier import Morph
        from .driver import makePropDriver
        from .hdmorphs import addSkeyToUrls
        if not (isinstance(asset, Morph) and
                self.mesh and
                asset.deltas):
            return None,True
        useBuild = True
        if asset.vertex_count < 0:
            print("Vertex count == %d" % asset.vertex_count)
        elif asset.vertex_count != len(self.mesh.data.vertices):
            msg = ("Vertex count mismatch: %d != %d" % (asset.vertex_count, len(self.mesh.data.vertices)))
            if GS.verbosity > 2:
                print(msg)
            if asset.hd_url:
                if self.treatHD == 'CREATE':
                    useBuild = False
                elif self.treatHD == 'ACTIVE':
                    skey = self.getActiveShape(asset)
                else:
                    reportError(msg, trigger=(2,3))
                    return None,False
            else:
                reportError(msg, trigger=(2,3))
                return None,False
        if not asset.rna:
            asset.buildMorph(self.mesh,
                             useBuild=useBuild,
                             strength=self.strength)
        skey,_,sname = asset.rna
        if skey:
            prop = unquote(skey.name)
            self.alias[prop] = skey.name
            skey.name = prop
            self.shapekeys[prop] = skey
            addSkeyToUrls(self.mesh, self.isJcm, asset, skey)
            if self.rig:
                final = self.addNewProp(prop, None, skey)
                makePropDriver(propRef(final), skey, "value", self.amt, "x")
            pgs = self.mesh.data.DazBodyPart
            if prop in pgs.keys():
                item = pgs[prop]
            else:
                item = pgs.add()
                item.name = prop
            item.s = bodypart
            return skey,True
        else:
            return None,True


    def makeFormulas(self, asset, skey):
        from .formula import Formula
        self.addNewProp(asset.getName(), asset, skey)
        if not isinstance(asset, Formula):
            return
        exprs = asset.evalFormulas(self.rig, self.mesh)
        for output,data in exprs.items():
            for key,data1 in data.items():
                if key == "*fileref":
                    ref,channel = data1
                    if channel == "value" and len(ref) > 3:
                        self.referred[ref.lower()] = True
                    continue
                for idx,expr in data1.items():
                    if key == "value":
                        self.makeValueFormula(output, expr)
                    elif key == "rotation":
                        self.makeRotFormula(output, idx, expr)
                    elif key == "translation":
                        self.makeTransFormula(output, idx, expr)
                    elif key == "scale":
                        self.makeScaleFormula(output, idx, expr)
                    elif key in ["center_point", "end_point"]:
                        self.ecr = True


    def getFileRef(self, filepath):
        filepath = filepath.replace("\\", "/").lower()
        words = filepath.rsplit("/data/",1)
        if len(words) == 2:
            return "/data/%s" % words[1]
        else:
            raise RuntimeError("getFileRef", filepath)


    def addNewProp(self, raw, asset=None, skey=None):
        from .driver import setBoolProp
        from .morphing import setActivated
        final = finalProp(raw)
        if raw not in self.drivers.keys():
            self.drivers[raw] = []
            self.visible[raw] = False
            self.primary[raw] = False
        if asset:
            visible = (asset.visible or GS.useMakeHiddenSliders)
            self.visible[raw] = visible
            self.primary[raw] = True
            if skey and not visible:
                return final
            elif asset.type == "bool":
                setBoolProp(self.rig, raw, asset.value)
                setBoolProp(self.amt, final, asset.value)
            elif asset.type == "float":
                self.setFloatLimits(self.rig, raw, GS.sliderLimits, asset, skey)
                self.setFloatLimits(self.amt, final, GS.internalLimits, asset, skey)
            elif asset.type == "int":
                self.rig[raw] = 0
                self.amt[final] = 0
            else:
                self.setFloatLimits(self.rig, raw, GS.sliderLimits, asset, skey)
                self.setFloatLimits(self.amt, final, GS.internalLimits, asset, skey)
                reportError("BUG: Unknown asset type: %s.\nAsset: %s" % (asset.type, asset), trigger=(2,3))
            if visible:
                setActivated(self.rig, raw, True)
                self.addToMorphSet(raw, asset, False)
        return final


    def setFloatLimits(self, rna, prop, limits, asset, skey):
        from .driver import setFloatProp
        if limits == 'DAZ':
            min = GS.morphMultiplier * asset.min
            max = GS.morphMultiplier * asset.max
            setFloatProp(rna, prop, 0.0, min, max)
            if skey:
                skey.slider_min = min
                skey.slider_max = max
        elif limits == 'CUSTOM':
            setFloatProp(rna, prop, 0.0, GS.customMin, GS.customMax)
            if skey:
                skey.slider_min = GS.customMin
                skey.slider_max = GS.customMax
        else:
            setFloatProp(rna, prop, 0.0, None, None)
            if skey:
                skey.slider_min = 0.0
                skey.slider_max = 1.0


    def makeValueFormula(self, output, expr):
        if expr["prop"]:
            self.addNewProp(output)
            prop = expr["prop"]
            self.drivers[output].append(("PROP", prop, expr["factor"]))
        if expr["mult"]:
            if output not in self.mults.keys():
                self.mults[output] = []
            mult = expr["mult"]
            self.mults[output].append(mult)
            self.addNewProp(mult)
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
        return getTargetName(bname, self.rig)


    def getDrivenBone(self, bname):
        bname = self.getRealBone(bname)
        if bname:
            dname = drvBone(bname)
            if dname in self.rig.pose.bones.keys():
                return dname
        return bname


    def getBoneData(self, bname, expr):
        from .transform import Transform
        bname = self.getDrivenBone(bname)
        if bname is None:
            return
        pb = self.rig.pose.bones[bname]
        factor = expr["factor"]
        if "points" in expr.keys():
            factor = self.cheatSplineTCB(expr["points"], factor)
        raw = expr["prop"]
        final = self.addNewProp(raw)
        tfm = Transform()
        return tfm, pb, final, factor


    def cheatSplineTCB(self, points, factor):
        x0 = y0 = None
        for n,point in enumerate(points):
            x,y = point[0:2]
            if x == 0 and y == 0:
                x0 = x
                y0 = y
                n0 = n
                break
        if x0 is None:
            return factor
        if n0 == 0:
            x1,y1 = points[-1][0:2]
        else:
            x1,y1 = points[0][0:2]
        factor = (y1-y0)/(x1-x0)
        return factor


    def makeRotFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setRot(self.strength*factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeTransFormula(self, bname, idx, expr):
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setTrans(self.strength*factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)


    def makeScaleFormula(self, bname, idx, expr):
        if not GS.useScaleMorphs:
            return
        # DS and Blender seem to inherit scale differently
        tfm,pb,prop,factor = self.getBoneData(bname, expr)
        tfm.setScale(self.strength*factor, True, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)

    #-------------------------------------------------------------
    #   Add posebone driver
    #-------------------------------------------------------------

    def addPoseboneDriver(self, pb, tfm):
        from .node import getBoneMatrix
        mat = getBoneMatrix(tfm, pb)
        loc,quat,scale = mat.decompose()
        success = False
        if (tfm.transProp and loc.length > 0.01*self.rig.DazScale):
            self.setFcurves(pb, loc, tfm.transProp, "location")
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                quat[0] -= 1
                self.setFcurves(pb, quat, tfm.rotProp, "rotation_quaternion")
                success = True
            else:
                euler = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, euler, tfm.rotProp, "rotation_euler")
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, scale-One, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, scale-One, tfm.generalProp, "scale")
            success = True
        return success


    def setFcurves(self, pb, vec, prop, channel):
        def getBoneFcurves(pb, channel):
            dot = ("" if channel[0] == "[" else ".")
            path = 'pose.bones["%s"]%s%s' % (pb.name, dot, channel)
            fcurves = {}
            if self.rig.animation_data:
                for fcu in self.rig.animation_data.drivers:
                    if path == fcu.data_path:
                        fcurves[fcu.array_index] = fcu
            return fcurves

        fcurves = getBoneFcurves(pb, channel)
        for idx,factor in self.getFactors(vec):
            if idx in fcurves.keys():
                fcu = fcurves[idx]
            else:
                fcu = None
            bname,drivers = self.findSumDriver(pb, channel, idx, (pb, fcu, {}))
            drivers[prop] = factor
        pb.DazDriven = True


    def getFactors(self, vec):
        maxfactor = max([abs(factor) for factor in vec])
        return [(idx,factor) for idx,factor in enumerate(vec) if abs(factor) > 0.01*maxfactor]


    def findSumDriver(self, pb, channel, idx, data):
        bname = pb.name
        if drvBone(bname) in self.rig.data.bones.keys():
            bname = drvBone(bname)
        if bname not in self.sumdrivers.keys():
            self.sumdrivers[bname] = {}
        if channel not in self.sumdrivers[bname].keys():
            self.sumdrivers[bname][channel] = {}
        if idx not in self.sumdrivers[bname][channel].keys():
            self.sumdrivers[bname][channel][idx] = data
        return bname, self.sumdrivers[bname][channel][idx][2]


    def clearProp(self, pgs, prop, idx):
        for n,pg in enumerate(pgs):
            if pg.name == prop and pg.index == idx:
                pgs.remove(n)
                return

    #------------------------------------------------------------------
    #   Second pass: Load missing morphs
    #------------------------------------------------------------------

    def makeMissingMorphs(self, bodypart):
        from .asset import getDazPath
        for fileref in self.loaded:
            self.referred[fileref] = False
        namepaths = []
        for ref,unloaded in self.referred.items():
            if unloaded:
                path = getDazPath(ref)
                if path:
                    name = ref.rsplit("/",1)[-1]
                    namepaths.append((name,path,bodypart))
        self.makeAllMorphs(namepaths, False)

    #------------------------------------------------------------------
    #   Third pass: Build the drivers
    #------------------------------------------------------------------

    def buildDrivers(self):
        print("Building drivers")
        for output,drivers in self.drivers.items():
            if drivers:
                if self.isDriverType('BONE', drivers):
                    for dtype,bname,expr in drivers:
                        if dtype == 'BONE':
                            self.buildBoneDriver(output, bname, expr, False)
                elif self.isDriverType('PROP', drivers):
                    self.buildPropDriver(output, drivers)
            else:
                self.buildPropDriver(output, drivers)


    def isDriverType(self, dtype, drivers):
        for driver in drivers:
            if driver[0] == dtype:
                return True
        return False


    def buildPropDriver(self, raw, drivers):
        from .driver import getRnaDriver, Variable
        rna,channel = self.getDrivenChannel(raw)
        bvars = []
        string = ""
        fcu0 = getRnaDriver(rna, channel, None)
        if fcu0 and fcu0.driver.type == 'SCRIPTED':
            if not self.primary[raw]:
                self.extendPropDriver(fcu0, raw, drivers)
                return
            btargets = self.getBoneTargets(fcu0)
            if btargets:
                varname = btargets[-1][0]
                string = self.extractBoneExpression(fcu0.driver.expression, varname)
                for _,_,var0 in btargets:
                    bvars.append(Variable(var0))
        rna.driver_remove(channel)
        fcu = rna.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)

        varname = "a"
        if self.visible[raw] or not self.primary[raw]:
            string += varname
            self.addPathVar(fcu, varname, self.rig, propRef(raw))
            if raw not in self.rig.keys():
                self.rig[raw] = 0.0
        string,rdrivers = self.addDriverVars(fcu, string, varname, raw, drivers)
        self.mult = []
        if raw in self.mults.keys():
            self.mult = self.mults[raw]
        string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        if rdrivers:
            self.extendPropDriver(fcu, raw, rdrivers)


    def extractBoneExpression(self, string, varname):
        string = string.split("(", 1)[-1]
        mult = string.split(varname, 1)[0]
        if mult == "0":
            mult = "0*"
        return "%s%s+" % (mult, varname)


    def addDriverVars(self, fcu, string, varname, raw, drivers):
        def multiply(factor, varname):
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "+%g*%s" % (factor, varname)

        channels = [var.targets[0].data_path for var in fcu.driver.variables]
        for dtype,subraw,factor in drivers[0:MAX_TERMS2]:
            if dtype != 'PROP':
                continue
            subfinal = finalProp(subraw)
            channel = propRef(subfinal)
            if channel in channels:
                continue
            varname = nextLetter(varname)
            string += multiply(factor, varname)
            self.ensureExists(subraw, subfinal, 0.0)
            self.addPathVar(fcu, varname, self.amt, channel)
        if len(drivers) > MAX_TERMS2:
            return string, drivers[MAX_TERMS2:]
        else:
            return string, []


    def extendPropDriver(self, fcu, raw, drivers):
        string = fcu.driver.expression
        char = ""
        while string[-1] == ")":
            char += ")"
            string = string[:-1]
        if string[-1] == "R":
            rest = restProp(raw)
            self.addRestDrivers(rest, drivers)
            return
        else:
            string += "+R"
            rest = restProp(raw)
            self.amt[rest] = 0.0
            self.addPathVar(fcu, "R", self.amt, propRef(rest))
            self.addRestDrivers(rest, drivers)
        string += char
        if len(string) > MAX_EXPRESSION_SIZE:
            errtype = "Driving expressions too long for the following properties:"
            if errtype not in self.errors.keys():
                self.errors[errtype] = []
            self.errors[errtype].append(raw)
        else:
            fcu.driver.expression = string


    def addRestDrivers(self, rest, drivers):
        struct = self.restdrivers[rest] = {}
        for dtype,raw,factor in drivers:
            if dtype == 'PROP':
                struct[finalProp(raw)] = factor


    def addPathVar(self, fcu, varname, rna, path):
        from .driver import addDriverVar
        addDriverVar(fcu, varname, path, rna)


    def getDrivenChannel(self, raw):
        rna = self.amt
        final = finalProp(raw)
        self.ensureExists(raw, final, 0.0)
        channel = propRef(final)
        return rna, channel


    def multiplyMults(self, fcu, string):
        if self.mult:
            varname = "M"
            mstring = ""
            for mult in self.mult:
                mstring += "%s*" % varname
                multfinal = finalProp(mult)
                self.ensureExists(mult, multfinal, 1)
                self.addPathVar(fcu, varname, self.amt, propRef(multfinal))
                varname = nextLetter(varname)
            return "%s(%s)" % (mstring, string)
        else:
            return string


    def ensureExists(self, raw, final, default):
        if raw not in self.rig.keys():
            self.rig[raw] = default
        if final not in self.amt.keys():
            self.amt[final] = default
            fcu = self.amt.driver_add(propRef(final))
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = "a"
            self.addPathVar(fcu, "a", self.rig, propRef(raw))


    def buildBoneDriver(self, raw, bname, expr, keep):
        def getSplinePoints(expr, pb, comp):
            points = expr["points"]
            n = len(points)
            if (points[0][0] > points[n-1][0]):
                points.reverse()

            diff = points[n-1][0] - points[0][0]
            uvec = getBoneVector(unit/diff, comp, pb)
            xys = []
            for k in range(n):
                x = points[k][0]/diff
                y = points[k][1]
                xys.append((x, y))
            return uvec, xys

        self.mult = []
        if raw in self.mults.keys():
            self.mult = self.mults[raw]

        pb = self.rig.pose.bones[bname]
        rna,channel = self.getDrivenChannel(raw)
        #rna.driver_remove(channel)
        path = expr["path"]
        comp = expr["comp"]
        unit = getUnit(path, self.rig)
        if "points" in expr.keys():
            uvec,xys = getSplinePoints(expr, pb, comp)
            self.makeSplineBoneDriver(path, uvec, xys, rna, channel, -1, bname, keep)
        elif isinstance(expr["factor"], list):
            print("FOO", expr)
            halt
            uvecs = []
            for factor in expr["factor"]:
                uvec = unit*getBoneVector(factor, comp, pb)
                uvecs.append(uvec)
            self.makeProductBoneDriver(path, uvecs, rna, channel, -1, bname, keep)
        else:
            factor = expr["factor"]
            uvec = unit*getBoneVector(factor, comp, pb)
            self.makeSimpleBoneDriver(path, uvec, rna, channel, -1, bname, keep)

    #-------------------------------------------------------------
    #   Bone drivers
    #-------------------------------------------------------------

    def getVarData(self, uvec, bname):
        vals = [(abs(x), n, x) for n,x in enumerate(uvec)]
        vals.sort()
        _,n,umax = vals[-1]
        if drvBone(bname) in self.rig.pose.bones.keys():
            vars = [(n, "A", finBone(bname))]
        else:
            vars = [(n, "A", bname)]
        return "A", vars, umax


    def makeSimpleBoneDriver(self, channel, vec, rna, path, idx, bname, keep):
        var,vars,umax = self.getVarData(vec, bname)
        string = getMult(umax, var)
        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeProductBoneDriver(self, channel, vecs, rna, path, idx, bname, keep):
        string = ""
        vars = []
        for vec in vecs:
            string1,vars1 = self.getVarData(vec, bname)
            if string1:
                vars += vars1
                string += ("*min(1,max(0,%s))" % string1)
        if string:
            self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeSplineBoneDriver(self, channel, uvec, points, rna, path, idx, bname, keep):
        # Only make spline for one component
        #[1 if x< -1.983 else -x-0.983 if x< -0.983  else 0 for x in [+0.988*A]][0]
        #1 if A< -1.983/0.988 else -0.988*A-0.983 if A< -0.983/0.988  else 0

        var,vars,umax = self.getVarData(uvec, bname)
        lt = ("<" if umax > 0 else ">")

        n = len(points)
        xi,yi = points[0]
        string = "%s if %s%s %s" % (getPrint(yi), var, lt, getPrint(xi/umax))
        for i in range(1, n):
            xj,yj = points[i]
            kij = (yj-yi)/(xj-xi)
            zs,zi = getSign((yi - kij*xi)/umax)
            zstring = ""
            if abs(zi) > 5e-4:
                zstring = ("%s%s" % (zs, getPrint(zi*umax)))
            string += (" else %s%s if %s%s %s " % (getMult(kij*umax, var), zstring, var, lt, getPrint(xj/umax)))
            xi,yi = xj,yj
        string += " else %s" % getPrint(yj)

        if len(string) > 254:
            msg = "String driver too long:\n"
            for n in range(5):
                msg += "%s         \n" % (string[30*n, 30*(n+1)])
            raise DazError(msg)

        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)


    def makeBoneDriver(self, string, vars, channel, rna, path, idx, keep):
        from .driver import addTransformVar, Variable, getRnaDriver
        bvars = []
        if keep:
            fcu0 = getRnaDriver(rna, path, None)
            if fcu0 and fcu0.driver.type == 'SCRIPTED':
                btargets = self.getBoneTargets(fcu0)
                if btargets:
                    varname = btargets[-1][0]
                    string0 = self.extractBoneExpression(fcu0.driver.expression, varname)
                    for _,_,var0 in btargets:
                        bvars.append(Variable(var0))
                    vname = nextLetter(varname)
                    string = string0 + string.replace(varname, vname)
                    vars = [(idx, varname.replace(varname, vname), prop)
                        for (idx, varname, prop) in  vars]
        rna.driver_remove(path, idx)
        fcu = rna.driver_add(path, idx)
        fcu.driver.type = 'SCRIPTED'
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)
        string = self.multiplyMults(fcu, string)
        if GS.useMakeHiddenSliders and isPath(path):
            final = unPath(path)
            if isFinal(final):
                raw = baseProp(final)
                string = "u+" + string
                self.rig[raw] = 0.0
                self.addPathVar(fcu, "u", self.rig, propRef(raw))
                self.addToMorphSet(raw, None, True)
        fcu.driver.expression = string
        if channel == "rotation":
            ttypes = ["ROT_X", "ROT_Y", "ROT_Z"]
        elif channel == "translation":
            ttypes = ["LOC_X", "LOC_Y", "LOC_Z"]
        else:
            reportError("Unknown channel: %s" % channel, trigger=(2,3))
        for j,vname,bname in vars:
            addTransformVar(fcu, vname, ttypes[j], self.rig, bname)
        return fcu

    #------------------------------------------------------------------
    #   Build sum drivers
    #   For Xin's non-python drivers
    #------------------------------------------------------------------

    def buildSumDrivers(self):
        print("Building sum drivers")
        for bname,bdata in self.sumdrivers.items():
            for channel,cdata in bdata.items():
                for idx,idata in cdata.items():
                    pb,fcu0,drivers = idata
                    pathids = {}
                    if ((channel == "rotation_quaternion" and idx == 0) or
                        (channel == "scale")):
                        path = self.getUnity(pb, idx)
                        pathids[path] = 'ARMATURE'
                    if fcu0:
                        if fcu0.driver.type == 'SUM':
                            self.recoverOldDrivers(fcu0, drivers)
                        else:
                            path = self.getOrigo(fcu0, pb, channel, idx)
                            pathids[path] = 'ARMATURE'

                    pb.driver_remove(channel, idx)
                    prefix = self.getChannelPrefix(pb, channel, idx)
                    fcu = self.addSumDriver(prefix, drivers, pathids)
                    sumfcu = self.rig.animation_data.drivers.from_existing(src_driver=fcu)
                    sumfcu.data_path = 'pose.bones["%s"].%s' % (pb.name, channel)
                    sumfcu.array_index = idx
                    self.clearTmpDriver(0)
            print(" + %s" % bname)


    def getChannelPrefix(self, pb, channel, idx):
        key = channel[0:3].capitalize()
        return "%s:%s:%s" % (pb.name, key, idx)


    def getTermDriverName(self, prefix, n):
        return ("%s:%02d" % (prefix, n))


    def buildRestDrivers(self):
        from .driver import getRnaDriver
        if self.restdrivers:
            print("Building rest drivers")
        else:
            print("No rest drivers")
        for rest,drivers in self.restdrivers.items():
            self.amt[rest] = 0.0
            fcu = getRnaDriver(self.amt, propRef(rest))
            if fcu:
                self.recoverOldDrivers(fcu, drivers)
            self.amt.driver_remove(propRef(rest))
            fcu = self.addSumDriver(rest, drivers, {})
            sumfcu = self.amt.animation_data.drivers.from_existing(src_driver=fcu)
            self.amt.driver_remove(rest)
            sumfcu.data_path = propRef(rest)
            self.clearTmpDriver(0)


    def recoverOldDrivers(self, sumfcu, drivers):
        from .driver import getRnaDriver
        for var in sumfcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'OBJECT':
                fcu2 = getRnaDriver(self.rig, trg.data_path)
            else:
                fcu2 = getRnaDriver(self.amt, trg.data_path)
            if fcu2:
                targets = {}
                for var2 in fcu2.driver.variables:
                    if var2.type == 'SINGLE_PROP':
                        trg2 = var2.targets[0]
                        targets[var2.name] = trg2
                string = fcu2.driver.expression
                while string and string[0] == "(":
                    string = string[1:-1]
                words = string.split("*")
                word1 = words[0]
                for word2 in words[1:]:
                    varname = word2[0]
                    if varname in targets.keys():
                        trg2 = targets[varname]
                        prop = unPath(trg2.data_path)
                        if prop not in drivers.keys():
                            try:
                                factor = float(word1)
                            except ValueError:
                                msg = ("BUG recoverOldDrivers: not a float\n" +
                                       "FCU2 %s %d" % (fcu2.data_path, fcu2.array_index) +
                                       "EXPR %s" % fcu2.driver.expression +
                                       "TARGETS %s" % list(targets.keys()))
                                reportError(msg, trigger=(0,0))
                            drivers[prop] = factor
                    word1 = word2[1:]


    def getOrigo(self, fcu0, pb, channel, idx):
        from .driver import Driver
        prefix = self.getChannelPrefix(pb, channel, idx)
        prop = self.getTermDriverName(prefix, 0)
        self.amt[prop] = 0.0
        fcu = self.amt.driver_add(propRef(prop))
        driver = Driver(fcu0, True)
        driver.fill(fcu)
        return propRef(prop)


    def getUnity(self, pb, idx):
        from .driver import getRnaDriver
        prop = "Unity"
        self.amt[prop] = 1.0
        path = propRef(prop)
        if not getRnaDriver(self.amt, path):
            fcu = self.amt.driver_add(path)
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = "1.0"
        return path


    def getParentScale(self, pname, idx):
        from .driver import getRnaDriver
        prop = "scale:%s:%d" % (pname, idx)
        if prop not in self.amt.keys():
            self.amt[prop] = 0.0
        if getRnaDriver(self.amt, propRef(prop)):
            return prop
        fcu = self.amt.driver_add(propRef(prop))
        fcu.driver.type = 'SCRIPTED'
        fcu.driver.expression = "var-1.0"
        var = fcu.driver.variables.new()
        var.name = "var"
        var.type = 'TRANSFORMS'
        trg = var.targets[0]
        trg.id = self.rig
        trg.bone_target = pname
        trg.transform_type = 'SCALE_%s' % chr(ord('X')+idx)
        trg.transform_space = 'LOCAL_SPACE'
        return prop


    def getBatches(self, drivers):
        def getTermDriverExpr(varname, factor):
            if factor < 0:
                return "%g*%s" % (factor, varname)
            else:
                return "+%g*%s" % (factor, varname)

        batches = []
        string = ""
        nterms = 0
        varname = "a"
        vars = []
        for final,factor in drivers.items():
            string += getTermDriverExpr(varname, factor)
            nterms += 1
            vars.append((varname, final))
            varname = nextLetter(varname)
            if (nterms > MAX_TERMS or
                len(string) > MAX_EXPR_LEN):
                batches.append((string, vars))
                string = ""
                nterms = 0
                varname = "a"
                vars = []
        if vars:
            batches.append((string, vars))
        return batches


    def addSumDriver(self, prefix, drivers, pathids):
        batches = self.getBatches(drivers)
        sumfcu = self.getTmpDriver(0)
        sumfcu.driver.type = 'SUM'
        for n,batch in enumerate(batches):
            string,vars = batch
            drvprop = self.getTermDriverName(prefix, n+1)
            self.amt[drvprop] = 0.0
            path = propRef(drvprop)
            self.amt.driver_remove(path)
            fcu = self.getTmpDriver(1)
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = string
            for varname,final in vars:
                self.addPathVar(fcu, varname, self.amt, propRef(final))
            pathids[path] = 'ARMATURE'
            fcu2 = self.amt.animation_data.drivers.from_existing(src_driver=fcu)
            fcu2.data_path = path
            self.clearTmpDriver(1)
        for n,data in enumerate(pathids.items()):
            path,idtype = data
            if idtype == 'OBJECT':
                rna = self.rig
            else:
                rna = self.amt
            self.addPathVar(sumfcu, "t%.02d" % n, rna, path)
        return sumfcu


    def getActiveShape(self, asset):
        ob = self.mesh
        sname = asset.name
        skey = None
        if ob.data.shape_keys:
            skey = ob.data.shape_keys.key_blocks[ob.active_shape_key_index]
            skey.name = sname
        return skey, ob, sname

#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, errors):

    def buildChannel(exprs, pb, channel):
        lm = LoadMorph(rig, None)
        for idx,expr in exprs.items():
            factor = expr["factor"]
            driver = expr["bone"]
            path = expr["path"]
            comp = expr["comp"]
            unit = getUnit(path, rig)
            if factor and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pb:
                    print("Dependency loop: %s %s" % (pbDriver.name, pb.name))
                else:
                    uvec = getBoneVector(factor, comp, pbDriver)
                    dvec = getBoneVector(1.0, idx, pb)
                    idx2,sign,x = getDrivenComp(dvec)
                    lm.makeSimpleBoneDriver(path, sign*uvec, pb, channel, idx2, driver, False)


    def buildValueDriver(exprs, raw):
        lm = LoadMorph(rig, None)
        for idx,expr in exprs.items():
            bname = expr["bone"]
            if bname not in rig.pose.bones.keys():
                print("Missing bone:", bname)
                continue
            final = finalProp(raw)
            if final not in rig.data.keys():
                rig.data[final] = 0.0
            lm.buildBoneDriver(raw, bname, expr, True)

    exprs = asset.evalFormulas(rig, None)
    for driven,expr in exprs.items():
        if "rotation" in expr.keys():
            if driven in rig.pose.bones.keys():
                pb = rig.pose.bones[driven]
                buildChannel(expr["rotation"], pb, "rotation_euler")
        elif "value" in expr.keys():
            buildValueDriver(expr["value"], driven)

#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def isPath(path):
    return (path[0:2] == '["')

def unPath(path):
    if path[0:2] == '["':
        return path[2:-2]
    elif path[0:6] == 'data["':
        return path[6,-2]
    else:
        return path

def getBoneVector(factor, comp, pb):
    from .node import getTransformMatrix
    tmat = getTransformMatrix(pb)
    uvec = Vector((0,0,0))
    uvec[comp] = factor
    return uvec @ tmat

def getDrivenComp(vec):
    for n,x in enumerate(vec):
        if abs(x) > 0.1:
            return n, (1 if x >= 0 else -1), x

def getPrint(x):
    string = "%.3f" % x
    while (string[-1] == "0"):
        string = string[:-1]
    return string[:-1] if string[-1] == "." else string

def getMult(x, comp):
    xx = getPrint(x)
    if xx == "0":
        return "0"
    elif xx == "1":
        return comp
    elif xx == "-1":
        return "-" + comp
    else:
        return xx + "*" + comp

def getSign(u):
    if u < 0:
        return "-", -u
    else:
        return "+", u

def getUnit(path, rig):
    if path == "translation":
        return 1/rig.DazScale
    elif path == "rotation":
        return 1/D
    else:
        return 1
