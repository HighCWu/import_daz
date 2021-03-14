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

from .utils import *

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

class LoadMorph:
    morphset = None
    usePropDrivers = True
    useMults = True

    def __init__(self, rig, mesh):
        self.rig = rig
        self.mesh = mesh
        self.mult = []

    def loadAllMorphs(self, namepaths):
        self.makeAllMorphs(namepaths)
        if self.rig:
            self.buildDrivers()
            self.buildSumDrivers()
            updateDrivers(self.rig)
            updateDrivers(self.mesh)

    #------------------------------------------------------------------
    #   Make all morphs
    #------------------------------------------------------------------

    def makeAllMorphs(self, namepaths):
        print("Making morphs")
        self.alias = {}
        self.primary = {}
        self.visible = {}
        self.ecr = False
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
        from .modifier import Alias, ChannelAsset
        struct = loadJson(filepath)
        asset = parseAssetFile(struct)
        if not isinstance(asset, ChannelAsset):
            return " -"
        elif isinstance(asset, Alias):
            return " _"
        sname = self.buildShapekey(asset)
        if self.rig:
            self.makeFormulas(asset, sname)
        return " *"


    def buildShapekey(self, asset, useBuild=True):
        from .modifier import Morph
        from .driver import makePropDriver, setFloatProp
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
                             strength=self.strength)
        skey,_,sname = asset.rna
        if skey:
            prop = unquote(skey.name)
            self.alias[prop] = skey.name
            skey.name = prop
            self.shapekeys[prop] = skey
            #if self.rig:
            #    final = self.addNewProp(prop)
            #    makePropDriver(propRef(final), skey, "value", self.rig, "x")
            return prop
        return None


    def makeFormulas(self, asset, sname):
        from .formula import Formula
        self.addNewProp(asset.getName(), asset, sname)
        if not isinstance(asset, Formula):
            return
        exprs = asset.evalFormulas(self.rig, self.mesh)
        for output,data in exprs.items():
            for key,data1 in data.items():
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


    def addNewProp(self, raw, asset=None, sname=None):
        from .driver import setBoolProp
        from .morphing import setActivated
        final = finalProp(raw)
        if raw not in self.drivers.keys():
            self.drivers[raw] = []
            self.visible[raw] = False
            self.primary[raw] = False
            #self.rig[raw] = 0.0
            #self.rig[final] = 0.0
        if asset:
            visible = (asset.visible or GS.useMakeHiddenSliders)
            self.visible[raw] = visible
            self.primary[raw] = True
            if sname:
                return final
            if asset.type == "bool":
                setBoolProp(self.rig, raw, asset.value)
                setBoolProp(self.rig, final, asset.value)
            elif asset.type == "float":
                self.setFloatLimits(raw, GS.rawLimits, asset)
                self.setFloatLimits(final, GS.finalLimits, asset)
            else:
                print("Unknown asset type:", asset.type)
                raise RuntimeError("BUG")
            if visible:
                setActivated(self.rig, raw, True)
                self.addToMorphSet(raw, asset, False)
        return final


    def setFloatLimits(self, prop, limits, asset):
        from .driver import setFloatProp
        if limits == 'DAZ':
            setFloatProp(self.rig, prop, 0.0, asset.min, asset.max)
        elif limits == 'CUSTOM':
            setFloatProp(self.rig, prop, 0.0, GS.customMin, GS.customMax)
        else:
            setFloatProp(self.rig, prop, 0.0, None, None)


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
            self.setFcurves(pb, loc, tfm.transProp, "location", 0)
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                vec = Vector(quat)
                self.setFcurves(pb, vec, tfm.rotProp, "rotation_quaternion", 0)
                success = True
            else:
                euler = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, euler, tfm.rotProp, "rotation_euler", 0)
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, scale, tfm.scaleProp, "scale", 1)
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, scale, tfm.generalProp, "scale", 1)
            success = True
        return success


    def setFcurves(self, pb, vec, prop, channel, default):
        def getBoneFcurves(pb, channel):
            if channel[0] == "[":
                dot = ""
            else:
                dot = "."
            path = 'pose.bones["%s"]%s%s' % (pb.name, dot, channel)
            fcurves = {}
            if self.rig.animation_data:
                for fcu in self.rig.animation_data.drivers:
                    if path == fcu.data_path:
                        fcurves[fcu.array_index] = fcu
            return fcurves

        key = channel[0:3].capitalize()
        fcurves = getBoneFcurves(pb, channel)
        idx,factor = self.getMaxFactor(vec, default)
        if GS.useCustomDrivers:
            if idx in fcurves.keys():
                fcu = fcurves[idx]
            else:
                fcu = pb.driver_add(channel, idx)
            self.addCustomDriver(fcu, factor, key)
        else:
            if idx in fcurves.keys():
                fcu = fcurves[idx]
            else:
                fcu = None
            self.addSumDriver(pb, idx, channel, fcu, (key, prop, factor, 0, default))
        pb.DazDriven = True
        self.addMorphGroup(pb, idx, key, prop, default, factor)


    def getMaxFactor(self, vec, default):
        vals = [(abs(factor-default), idx, factor) for idx,factor in enumerate(vec)]
        vals.sort()
        _,idx,factor = vals[-1]
        return idx, factor


    def addCustomDriver(self, fcu, factor, key):
        fcu.driver.type = 'SCRIPTED'
        expr = 'evalMorphs%s%d(self)' % (key, fcu.array_index)
        drvexpr = fcu.driver.expression
        try:
            f = float(drvexpr)
        except ValueError:
            f = 1.0
        if f == 0.0:
            fcu.driver.expression = expr
        elif expr not in drvexpr:
            fcu.driver.expression = "%s+%s" % (drvexpr, expr)
        fcu.driver.use_self = True
        if len(fcu.modifiers) > 0:
            fmod = fcu.modifiers[0]
            fcu.modifiers.remove(fmod)


    def addSumDriver(self, pb, idx, channel, fcu, data):
        bname = pb.name
        if drvBone(bname) in self.rig.data.bones.keys():
            bname = drvBone(bname)
        if bname not in self.sumdrivers.keys():
            self.sumdrivers[bname] = {}
        if channel not in self.sumdrivers[bname].keys():
            self.sumdrivers[bname][channel] = {}
        if idx not in self.sumdrivers[bname][channel].keys():
            self.sumdrivers[bname][channel][idx] = (pb, fcu, [])
        self.sumdrivers[bname][channel][idx][2].append(data)


    def clearProp(self, pgs, prop, idx):
        for n,pg in enumerate(pgs):
            if pg.name == prop and pg.index == idx:
                pgs.remove(n)
                return


    def addMorphGroup(self, pb, idx, key, prop, default, factor, factor2=None):
        from .propgroups import getPropGroups
        pgs = getPropGroups(pb, key, idx)
        self.clearProp(pgs, prop, idx)
        pg = pgs.add()
        pg.init(prop, idx, default, factor, factor2)
        if prop not in self.rig.keys():
            from .driver import setFloatProp
            setFloatProp(self.rig, prop, 0.0)

    #------------------------------------------------------------------
    #   Second pass: Build the drivers
    #------------------------------------------------------------------

    def buildDrivers(self):
        print("Building drivers")
        for output,drivers in self.drivers.items():
            if drivers:
                if self.isDriverType('BONE', drivers):
                    for dtype,bname,expr in drivers:
                        if dtype == 'BONE':
                            self.buildBoneDriver(output, bname, expr)
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
        def multiply(factor, varname):
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "+%g*%s" % (factor, varname)

        from .driver import addDriverVar, getRnaDriver
        self.mult = []
        if raw in self.mults.keys():
            self.mult = self.mults[raw]
        final = finalProp(raw)
        if final not in self.rig.keys():
            self.rig[final] = 0.0
        if not self.primary[raw]:
            fcu = getRnaDriver(self.rig, propRef(final), 'SINGLE_PROP')
            if fcu and fcu.driver.type == 'SCRIPTED':
                self.analyzeFcurve(fcu, raw)
        self.rig.driver_remove(propRef(final))
        fcu = self.rig.driver_add(propRef(final))
        fcu.driver.type = 'SCRIPTED'
        varname = "a"
        string = ""
        if self.visible[raw] or not self.primary[raw]:
            string = varname
            addDriverVar(fcu, varname, propRef(raw), self.rig)
        for dtype,subraw,factor in drivers:
            if dtype != 'PROP':
                continue
            subfinal = finalProp(subraw)
            varname = nextLetter(varname)
            string += multiply(factor, varname)
            self.ensureExists(subraw, subfinal)
            addDriverVar(fcu, varname, propRef(subfinal), self.rig)
        string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string


    def analyzeFcurve(self, fcu, raw):
        # (a+b+c+..)*M*N*...
        from .driver import getDriverPaths
        paths = getDriverPaths(fcu, self.rig)
        self.mult = []
        words = fcu.driver.expression.rsplit(")*", 1)
        if len(words) == 2:
            mvars = words[1].split("*")
            for mvar in mvars:
                if mvar in paths.keys():
                    self.mult.append(baseBone(unPath(paths[mvar])))


    def multiplyMults(self, fcu, string):
        from .driver import addDriverVar
        if self.mult and self.useMults:
           string = "(%s)" % string
           varname = "M"
           for mult in self.mult:
               string += "*%s" % varname
               multfinal = finalProp(mult)
               self.ensureExists(mult, multfinal)
               addDriverVar(fcu, varname, propRef(multfinal), self.rig)
               varname = nextLetter(varname)
        return string


    def ensureExists(self, raw, final):
        if raw not in self.drivers.keys():
            self.rig[raw] = 0.0
            self.rig[final] = 0.0


    def buildBoneDriver(self, raw, bname, expr):
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

        self.mult = []
        if raw in self.mults.keys():
            self.mult = self.mults[raw]

        pb = self.rig.pose.bones[bname]
        if raw in self.shapekeys.keys():
            rna = self.mesh.data.shape_keys
            channel = 'key_blocks["%s"].value' % raw
        else:
            rna = self.rig
            channel = propRef(finalProp(raw))

        self.rig.driver_remove(channel)
        comp = expr["comp"]
        if "points" in expr.keys():
            uvec,xys = getSplinePoints(expr, pb, comp)
            self.makeSplineBoneDriver(uvec, xys, rna, channel, -1, bname)
        elif isinstance(expr["factor"], list):
            print("FOO", expr)
            halt
            uvecs = []
            for factor in expr["factor"]:
                uvec = getBoneVector(factor, comp, pb)
                uvecs.append(uvec)
            self.makeProductBoneDriver(uvecs, rna, channel, -1, bname)
        else:
            factor = expr["factor"]
            uvec = getBoneVector(factor, comp, pb)
            self.makeSimpleBoneDriver(uvec, rna, channel, -1, bname)

    #-------------------------------------------------------------
    #   Bone drivers
    #-------------------------------------------------------------

    def makeVarsString(self, uvec, bname):
        vals = [(abs(x), n, x) for n,x in enumerate(uvec)]
        vals.sort()
        _,n,umax = vals[-1]
        if drvBone(bname) in self.rig.pose.bones.keys():
            if GS.useApproxDrvCombine:
                string = "(A+A2)"
                vars = [(n, "A", bname), (n, "A2", drvBone(bname))]
            else:
                string = "A"
                vars = [(n, "A", finBone(bname))]
        else:
            string = "A"
            vars = [(n, "A", bname)]
        return string, vars, umax


    def makeSimpleBoneDriver(self, vec, rna, channel, idx, bname=None):
        var,vars,umax = self.makeVarsString(vec, bname)
        string = getMult(umax, var)
        self.makeBoneDriver(string, vars, rna, channel, idx)


    def makeProductBoneDriver(self, vecs, rna, channel, idx, bname):
        string = ""
        vars = []
        for vec in vecs:
            string1,vars1 = self.makeVarsString(vec, bname)
            if string1:
                vars += vars1
                string += ("*min(1,max(0,%s))" % string1)
        if string:
            self.makeBoneDriver(string, vars, rna, channel, idx)


    def makeSplineBoneDriver(self, uvec, points, rna, channel, idx, bname):
        # Only make spline for one component
        #[1 if x< -1.983 else -x-0.983 if x< -0.983  else 0 for x in [+0.988*A]][0]
        #1 if A< -1.983/0.988 else -0.988*A-0.983 if A< -0.983/0.988  else 0

        var,vars,umax = self.makeVarsString(uvec, bname)
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

        self.makeBoneDriver(string, vars, rna, channel, idx)


    def makeBoneDriver(self, string, vars, rna, channel, idx):
        from .driver import addTransformVar
        rna.driver_remove(channel, idx)
        fcu = rna.driver_add(channel, idx)
        fcu.driver.type = 'SCRIPTED'
        string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        ttypes = ["ROT_X", "ROT_Y", "ROT_Z"]
        for j,vname,bname in vars:
            addTransformVar(fcu, vname, ttypes[j], self.rig, bname)
        return fcu

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

#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, errors):

    def buildChannel(exprs, pb, channel, default):
        lm = LoadMorph(rig, None)
        for idx,expr in exprs.items():
            factor = expr["factor"]
            driver = expr["bone"]
            comp = expr["comp"]
            if factor and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pb:
                    print("Dependency loop: %s %s" % (pbDriver.name, pb.name))
                else:
                    uvec = getBoneVector(factor*D, comp, pbDriver)
                    dvec = getBoneVector(D, idx, pb)
                    idx2,sign,x = getDrivenComp(dvec)
                    lm.makeSimpleBoneDriver(sign*uvec, pb, "rotation_euler", idx2, driver)

    exprs = asset.evalFormulas(rig, None)
    for driven,expr in exprs.items():
        if driven not in rig.pose.bones.keys():
            continue
        pb = rig.pose.bones[driven]
        if "rotation" in expr.keys():
            buildChannel(expr["rotation"], pb, "rotation_euler", Zero)


#------------------------------------------------------------------
#   Utilities
#------------------------------------------------------------------

def getBoneVector(factor, comp, pb):
    from .node import getTransformMatrix
    tmat = getTransformMatrix(pb)
    uvec = Vector((0,0,0))
    uvec[comp] = factor/D
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
