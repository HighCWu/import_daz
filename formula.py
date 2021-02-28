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

import math
from mathutils import *
from .error import DazError, reportError
from .utils import *

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class Formula:

    def __init__(self):
        self.formulas = []
        self.built = False


    def parse(self, struct):
        if (LS.useFormulas and
            "formulas" in struct.keys()):
            self.formulas = struct["formulas"]


    def prebuild(self, context, inst):
        from .modifier import Morph
        from .node import Node
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if asset is None:
                continue
            if key == "value" and isinstance(asset, Morph):
                asset.build(context, inst, value)


    def build(self, context, inst):
        from .morphing import addToCategories
        from .driver import setFloatProp, setBoolProp
        rig = inst.rna
        if rig.pose is None:
            return
        formulas = PropFormulas(rig)
        props = formulas.buildPropFormula(self, None, True)
        addToCategories(rig, props, "Imported")
        for prop in props:
            setFloatProp(rig, prop, self.value)


    def postbuild(self, context, inst):
        from .modifier import Morph
        from .node import Node
        if not LS.useMorph:
            return
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if isinstance(asset, Morph):
                pass
            elif isinstance(asset, Node):
                inst = asset.getInstance(ref, self.caller, False)
                if inst:
                    inst.formulate(key, value)


    def computeFormula(self, formula):
        if len(formula["operations"]) != 3:
            return None,None,0
        stack = []
        for struct in formula["operations"]:
            op = struct["op"]
            if op == "push":
                if "url" in struct.keys():
                    ref,key = getRefKey(struct["url"])
                    if ref is None or key != "value":
                        return None,None,0
                    asset = self.getAsset(ref)
                    if not hasattr(asset, "value"):
                        return None,None,0
                    stack.append(asset.value)
                elif "val" in struct.keys():
                    data = struct["val"]
                    stack.append(data)
                else:
                    reportError("Cannot push %s" % struct.keys(), trigger=(1,5), force=True)
            elif op == "mult":
                x = stack[-2]*stack[-1]
                stack = stack[:-2]
                stack.append(x)
            else:
                reportError("Unknown formula %s %s" % (op, struct.items()), trigger=(1,5), force=True)

        if len(stack) == 1:
            ref,key = getRefKey(formula["output"])
            return ref,key,stack[0]
        else:
            raise DazError("Stack error %s" % stack)
            return None,None,0


    def evalFormulas(self, exprs, props, rig, mesh):
        from .modifier import Morph
        success = False
        stages = []
        for formula in self.formulas:
            if self.evalFormula(formula, exprs, props, rig, mesh, stages):
                success = True
        if not success:
            if not self.formulas:
                return False
            if GS.verbosity > 3:
                print("Could not parse formulas", self.formulas)
            return False
        return True


    def evalFormula(self, formula, exprs, props, rig, mesh, stages):
        from .bone import getTargetName
        from .modifier import ChannelAsset

        driven = formula["output"].split("#")[-1]
        output,channel = driven.split("?")
        output = unquote(output)
        if channel == "value":
            if mesh is None:
                if GS.verbosity > 2:
                    print("Cannot drive properties", output)
                return False
            pb = None
        else:
            output1 = getTargetName(output, rig)
            if output1 is None:
                reportError("Missing bone (evalFormula): %s" % output, trigger=(2,4))
                return False
            else:
                output = output1
            if output not in rig.pose.bones.keys():
                return False
            pb = rig.pose.bones[output]

        path,idx,default = parseChannel(channel)
        if output not in exprs.keys():
            exprs[output] = {}
        if path not in exprs[output].keys():
            exprs[output][path] = {}
        if idx not in exprs[output][path].keys():
            exprs[output][path][idx] = {
                "factor" : 0,
                "prop" : None,
                "bone" : None,
                "comp" : -1,
                "mult" : None}

        expr = exprs[output][path][idx]
        nops = 0
        type = None
        ops = formula["operations"]

        # URL
        first = ops[0]
        if "url" not in first.keys():
            print("UU", first)
            return False
        url = first["url"].split("#")[-1]
        prop,type = url.split("?")
        prop = unquote(prop)
        path,comp,default = parseChannel(type)
        if type == "value":
            if props is None:
                return False
            if expr["prop"] is None:
                expr["prop"] = prop
            props[prop] = True
        else:
            expr["bone"] = prop
        expr["comp"] = comp

        # Main operation
        last = ops[-1]
        op = last["op"]
        if op == "mult":
            if len(ops) == 3:
                expr["factor"] = ops[1]["val"]
            elif len(ops) == 1:
                expr["mult"] = prop
        elif op == "push" and len(ops) == 1:
            bone,string = last["url"].split(":")
            url,channel = string.split("?")
            asset = self.getAsset(url)
            if asset:
                stages.append((asset,bone,channel))
            else:
                msg = ("Cannot push asset:\n'%s'    " % last["url"])
                if GS.verbosity > 1:
                    print(msg)
        elif op == "spline_tcb":
            expr["points"] = [ops[n]["val"] for n in range(1,len(ops)-2)]
        else:
            reportError("Unknown formula %s" % ops, trigger=(2,6))
            return False

        if "stage" in formula.keys() and len(ops) > 1:
            print("STAGE", formula)
            halt
            exprlist = []
            proplist = []
            for asset,bone,channel in stages:
                exprs1 = {}
                props1 = {}
                if isinstance(asset, Formula):
                    asset.evalFormulas(exprs1, props1, rig, mesh)
                elif isinstance(asset, ChannelAsset):
                    if GS.verbosity > 2:
                        print("Error stage formula: Channel")
                elif GS.verbosity > 1:
                    msg = "Error when evaluating stage formula"
                    #raise DazError(msg + ".\nWhere you trying to import flexions?")
                    print(msg)
                    print(asset)
                if exprs1:
                    expr1 = list(exprs1.values())[0]
                    exprlist.append(expr1)
                if props1:
                    prop1 = list(props1.values())[0]
                    proplist.append(prop1)

            if formula["stage"] == "mult":
                self.multiplyStages(exprs, exprlist)

        return True


    def getDefaultValue(self, pb, default):
        if pb:
            return Vector((default, default, default))
        else:
            return default


    def multiplyStages(self, exprs, exprlist):
        if not exprlist:
            return
        key = list(exprs.keys())[0]
        expr = exprs[key]
        bone = self.getExprValue(expr, "bone")
        evalue = self.getExprValue(expr, "value")
        vectors = []
        for expr2 in exprlist:
            bone2 = self.getExprValue(expr2, "bone")
            if bone2 is None:
                continue
            if bone is None:
                bone = bone2
                expr = exprs[key] = expr2
            if bone2 == bone:
                evalue2 = self.getExprValue(expr2, "value")
                if evalue2 is not None:
                    vectors.append(evalue2)
        if vectors:
            expr["factor"]["value"] = vectors


    def getExprValue(self, expr, key):
        if ("factor" in expr.keys() and
            key in expr["factor"].keys()):
            return expr["factor"][key]
        else:
            return None


def getRefKey(string):
    base = string.split(":",1)[-1]
    return base.rsplit("?",1)

#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, errors):

    def buildChannel(exprs, pbDriven, channel, default):
        from .driver import makeSimpleBoneDriver
        for idx,expr in exprs.items():
            factor = expr["factor"]
            driver = expr["bone"]
            comp = expr["comp"]
            if factor and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pbDriven:
                    print("Dependency loop: %s %s" % (pbDriver.name, pbDriven.name))
                else:
                    uvec = getBoneVector(factor*D, comp, pbDriver)
                    dvec = getBoneVector(1, idx, pbDriven)
                    idx2,sign = getDrivenComp(dvec)
                    makeSimpleBoneDriver(sign*uvec, pbDriven, "rotation_euler", rig, None, driver, idx2)

    exprs = {}
    asset.evalFormulas(exprs, None, rig, None)
    for driven,expr in exprs.items():
        if driven not in rig.pose.bones.keys():
            continue
        pb = rig.pose.bones[driven]
        if "rotation" in expr.keys():
            buildChannel(expr["rotation"], pb, "rotation_euler", Zero)

#-------------------------------------------------------------
#   Build bone driver
#-------------------------------------------------------------

def makeSomeBoneDriver(expr, rna, channel, rig, skeys, bname, idx):
    from .driver import makeSimpleBoneDriver, makeProductBoneDriver, makeSplineBoneDriver
    pb = rig.pose.bones[bname]
    comp = expr["comp"]
    if "points" in expr.keys():
        uvec,xys = getSplinePoints(expr, pb, comp)
        makeSplineBoneDriver(uvec, xys, rna, channel, rig, skeys, bname, idx)
    elif isinstance(expr["factor"], list):
        print("FOO", expr)
        halt
        uvecs = []
        for factor in expr["factor"]:
            uvec = getBoneVector(factor, comp, pb)
            uvecs.append(uvec)
        makeProductBoneDriver(uvecs, rna, channel, rig, skeys, bname, idx)
    else:
        factor = expr["factor"]
        uvec = getBoneVector(factor, comp, pb)
        makeSimpleBoneDriver(uvec, rna, channel, rig, skeys, bname, idx)


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


def getBoneVector(factor, comp, pb):
    from .node import getTransformMatrix
    tmat = getTransformMatrix(pb)
    uvec = Vector((0,0,0))
    uvec[comp] = factor/D
    return uvec @ tmat


def getDrivenComp(vec):
    for n,x in enumerate(vec):
        if abs(x) > 1e-5:
            return n, (1 if x >= 0 else -1)
    return 0

#-------------------------------------------------------------
#   class PoseboneDriver
#-------------------------------------------------------------

class PoseboneDriver:
    def __init__(self, rig):
        self.rig = rig
        self.errors = {}
        self.default = None


    def addPoseboneDriver(self, pb, tfm):
        from .node import getBoneMatrix
        mat = getBoneMatrix(tfm, pb)
        loc,quat,scale = mat.decompose()
        scale -= One
        success = False
        if (tfm.transProp and loc.length > 0.01*self.rig.DazScale):
            self.setFcurves(pb, "", loc, tfm.transProp, "location", 0)
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                value = Vector(quat)
                value[0] = 1.0 - value[0]
                self.setFcurves(pb, "1.0-", value, tfm.rotProp, "rotation_quaternion", 0)
                success = True
            else:
                value = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, "", value, tfm.rotProp, "rotation_euler", 0)
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, "", scale, tfm.scaleProp, "scale", 1)
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, "", scale, tfm.generalProp, "scale", 1)
            success = True
        return success


    def getBoneFcurves(self, pb, channel):
        if channel[0] == "[":
            dot = ""
        else:
            dot = "."
        path = 'pose.bones["%s"]%s%s' % (pb.name, dot, channel)
        fcurves = []
        if self.rig.animation_data:
            for fcu in self.rig.animation_data.drivers:
                if path == fcu.data_path:
                    fcurves.append((fcu.array_index, fcu))
        if fcurves:
            return [data[1] for data in fcurves]
        else:
            try:
                return pb.driver_add(channel)
            except TypeError:
                return []


    def setFcurves(self, pb, init, value, prop, channel, default):
        path = '["%s"]' % prop
        key = channel[0:3].capitalize()
        fcurves = self.getBoneFcurves(pb, channel)
        if len(fcurves) == 0:
            return
        for fcu in fcurves:
            idx = fcu.array_index
            self.addCustomDriver(fcu, pb, init, value[idx], prop, key, default)
            init = ""


    def addCustomDriver(self, fcu, pb, init, value, prop, key, default):
        from .driver import addTransformVar, driverHasVar
        fcu.driver.type = 'SCRIPTED'
        if abs(value) > 1e-4:
            expr = 'evalMorphs%s%d(self)' % (key, fcu.array_index)
            drvexpr = fcu.driver.expression[len(init):]
            if drvexpr in ["0.000", "-0.000"]:
                if init:
                    fcu.driver.expression = init + "+" + expr
                else:
                    fcu.driver.expression = expr
            elif expr not in drvexpr:
                if init:
                    fcu.driver.expression = init + "(" + drvexpr + "+" + expr + ")"
                else:
                    fcu.driver.expression = drvexpr + "+" + expr
            fcu.driver.use_self = True
            pb.DazDriven = True
            self.addMorphGroup(pb, fcu.array_index, key, prop, default, value)
            if len(fcu.modifiers) > 0:
                fmod = fcu.modifiers[0]
                fcu.modifiers.remove(fmod)


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


    def addError(self, err, asset):
        if err not in self.errors.keys():
            self.errors[err] = []
        label = asset.getLabel()
        if label not in self.errors[err]:
            self.errors[err].append(label)

#-------------------------------------------------------------
#   class PropFormulas
#-------------------------------------------------------------

class PropFormulas(PoseboneDriver):

    def __init__(self, rig):
        PoseboneDriver.__init__(self, rig)
        self.others = {}
        self.taken = {}
        self.built = {}
        self.depends = {}
        self.alias = {}


    def buildPropFormula(self, asset, filepath, fresh):
        self.filepath = filepath
        exprs = {}
        props = {}
        asset.evalFormulas(exprs, props, self.rig, None)
        if not props:
            if GS.verbosity > 3:
                print("Cannot evaluate formula")
            if GS.verbosity > 4:
                print(asset.formulas)
        if fresh:
            asset.setupProp(self.morphset, self.rig, self.usePropDrivers)
        else:
            asset.setupQuick(self.morphset, self.rig)

        opencoded = {}
        self.opencode(exprs, asset, opencoded, 0)
        for prop,openlist in opencoded.items():
            self.combineExpressions(openlist, prop, exprs, 1.0)
        self.getOthers(exprs, asset)
        if self.buildBoneFormulas(asset, exprs):
            return props
        else:
            return []


    def getOthers(self, exprs, asset):
        from .bone import getTargetName
        for prop,expr in exprs.items():
            prop = unquote(prop)
            bname = getTargetName(prop, self.rig)
            if bname is None:
                if prop in self.built.keys() and self.built[prop]:
                    continue
                struct = expr["value"]
                key = struct["prop"]
                if key not in self.taken.keys():
                    self.taken[key] = False
                val = struct["value"]
                if prop not in self.others.keys():
                    self.others[prop] = []
                self.others[prop].append((key, val))


    def opencode(self, exprs, asset, opencoded, level):
        from .bone import getTargetName
        from .modifier import ChannelAsset, Morph
        from .propgroups import addDependency
        if level > self.maxRecursionDepth:
            self.addError("Recursion too deep", asset)
            return
        for prop,expr in exprs.items():
            bname = getTargetName(prop, self.rig)
            if bname is None:
                struct = expr["value"]
                key = struct["prop"]
                if "points" in struct.keys():
                    # Should do this right some day
                    val = struct["points"][-1][0]
                else:
                    val = struct["value"]
                words = struct["output"].rsplit("?", 1)
                if not (len(words) == 2 and words[1] == "value"):
                    continue
                url = words[0].split(":")[-1]
                if url[0] == "#" and url[1:] == prop:
                    #print("Recursive definition:", prop, asset.selfref())
                    continue
                addDependency(key, prop, val)
                if prop not in self.depends.keys():
                    self.depends[prop] = []
                self.depends[prop].append((key,val))
                subasset = asset.getTypedAsset(url, ChannelAsset)
                if GS.useMultiShapes and isinstance(subasset, Morph):
                    subdata = self.evalSubAsset(asset, subasset, level)
                    morph = subasset
                elif isinstance(subasset, Formula):
                    subdata = self.evalSubAsset(asset, subasset, level)
                    morph = None
                else:
                    continue
                if key not in opencoded.keys():
                    opencoded[key] = []
                opencoded[key].append((val,subdata,morph,subasset.name))


    def evalSubAsset(self, asset, subasset, level):
        subexprs = {}
        subprops = {}
        subasset.evalFormulas(subexprs, subprops, self.rig, None)
        subopen = {}
        self.opencode(subexprs, asset, subopen, level+1)
        return (subexprs,subprops,subopen)


    def combineExpressions(self, openlist, prop, exprs, value):
        from .bone import getTargetName
        for val,subdata,morph,subname in openlist:
            value1 = val*value
            subexprs,subprops,subopen = subdata
            if morph is not None:
                self.shapes.append((value1, morph))
            if subopen:
                for subprop,sublist in subopen.items():
                    self.combineExpressions(sublist, prop, exprs, value1)
            else:
                for bname,subexpr in subexprs.items():
                    bname1 = getTargetName(bname, self.rig)
                    if bname1 is not None:
                        self.addValue("translation", bname1, prop, exprs, subexpr, value1)
                        self.addValue("rotation", bname1, prop, exprs, subexpr, value1)
                        self.addValue("scale", bname1, prop, exprs, subexpr, value1)
                        self.addValue("general_scale", bname1, prop, exprs, subexpr, value1)


    def addValue(self, slot, bname, prop, exprs, subexpr, value):
        if slot not in subexpr.keys():
            return
        delta = value * subexpr[slot]["value"]
        if bname in exprs.keys():
            expr = exprs[bname]
        else:
            expr = exprs[bname] = {}
        if slot in expr.keys():
            expr[slot]["value"] += delta
        else:
            expr[slot] = {"value" : delta, "prop" : prop}


    def buildOthers(self, missing):
        from .modifier import getCanonicalKey
        remains = self.others
        sorted = []
        nremains = len(remains)
        props = []
        for level in range(1,6):
            print("--- Pass %d (%d left) ---" % (level+1, nremains))
            batch, used, remains = self.getNextLevelMorphs(remains)
            self.buildMorphBatch(batch)
            for key in batch.keys():
                prop = getCanonicalKey(key)
                print(" *", prop)
                missing[prop] = False
                props.append(key)
            if len(remains) == nremains:
                break
            for key in batch.keys():
                self.built[key] = True
            for key in used.keys():
                self.taken[key] = True
            nremains = len(remains)
        if remains:
            print("Missing:")
            for key in remains.keys():
                prop = getCanonicalKey(key)
                print("-", prop)
        return props


    def getNextLevelMorphs(self, others):
        from .propgroups import addDependency
        remains = {}
        batch = {}
        used = {}
        for prop,data in others.items():
            for key,factor in data:
                if key in self.built.keys():
                    pass
                elif prop in self.taken.keys() and self.taken[prop]:
                    if key not in batch.keys():
                        batch[key] = []
                    batch[key].append((factor, prop, self.getStoredMorphs(prop)))
                    addDependency(key, prop, factor)
                    used[key] = True
                else:
                    remains[prop] = data
        return batch, used, remains


    def getStoredMorphs(self, key):
        from .propgroups import hasPropGroups, getLocProps, getRotProps, getScaleProps
        stored = {}
        for pb in self.rig.pose.bones:
            if not hasPropGroups(pb):
                continue
            data = stored[pb.name] = {"Loc" : {}, "Rot" : {}, "Sca" : {}}
            for channel,pgs in [
                ("Loc", getLocProps(pb)),
                ("Rot", getRotProps(pb)),
                ("Sca", getScaleProps(pb))]:
                for pg in pgs:
                    if pg.name == key:
                        data[channel][pg.index] = (pg.factor, pg.factor2, pg.default)
        return stored


    def buildMorphBatch(self, batch):
        for prop,bdata in batch.items():
            success = False
            if len(bdata) == 1:
                factor,prop1,bones = bdata[0]
                for pbname,pdata in bones.items():
                    pb = self.rig.pose.bones[pbname]
                    for key,channel in pdata.items():
                        if channel:
                            success = True
                        for idx in channel.keys():
                            value, value2, default = channel[idx]
                            self.addMorphGroup(pb, idx, key, prop, default, factor*value)
                if not success:
                    self.addOtherShapekey(prop, prop1, factor)

            elif len(bdata) == 2:
                factor1,prop1,bones1 = bdata[0]
                factor2,prop2,bones2 = bdata[1]
                if factor1 > 0 and factor2 < 0:
                    simple = False
                elif factor2 > 0 and factor1 < 0:
                    factor1,prop1,bones1 = bdata[1]
                    factor2,prop2,bones2 = bdata[0]
                    simple = False
                elif factor1 > 0 and factor2 > 0:
                    simple = True
                else:
                    raise RuntimeError("Unexpected morph data:", prop, factor1, factor2)

                self.addMissingBones(bones1, bones2)
                self.addMissingBones(bones2, bones1)
                for pbname in bones1.keys():
                    pb = self.rig.pose.bones[pbname]
                    data1 = bones1[pbname]
                    data2 = bones2[pbname]
                    for key in data1.keys():
                        channel1 = data1[key]
                        channel2 = data2[key]
                        if channel1:
                            success = True
                        for idx in channel1.keys():
                            value11, value12, default1 = channel1[idx]
                            value21, value22, default2 = channel2[idx]
                            if simple:
                                v1 = factor1*value11+factor2*value21
                                v2 = factor2*value12+factor1*value22
                            else:
                                v1 = factor1*value11+factor2*value22
                                v2 = factor2*value21+factor1*value12
                            self.addMorphGroup(pb, idx, key, prop, default1, v1, v2)
                if not success:
                    self.addOtherShapekey(prop, prop1, factor1)
                    self.addOtherShapekey(prop, prop2, factor2)

            if success:
                from .morphing import addToPropGroup
                addToPropGroup(prop, self.rig, self.morphset)


    def addOtherShapekey(self, prop, key, factor):
        from .driver import getShapekeyPropDriver, addVarToDriver
        if self.mesh and self.mesh.type == 'MESH' and self.rig:
            skeys = self.mesh.data.shape_keys
            if skeys:
                if key in self.alias.keys():
                    key = self.alias[key]
                if key in skeys.key_blocks.keys():
                    fcu = getShapekeyPropDriver(skeys, key)
                    addVarToDriver(fcu, self.rig, prop, factor)


    def addMissingBones(self, bones1, bones2):
        for bname in bones1.keys():
            data1 = bones1[bname]
            if bname not in bones2.keys():
                bones2[bname] = {"Loc" : {}, "Rot" : {}, "Sca" : {}}
            data2 = bones2[bname]
            for key in data1.keys():
                channel1 = data1[key]
                channel2 = data2[key]
                for idx in channel1.keys():
                    if idx not in channel2.keys():
                        channel2[idx] = (0, 0, 0)
                for idx in channel2.keys():
                    if idx not in channel1.keys():
                        channel1[idx] = (0, 0, 0)


    def buildBoneFormulas(self, asset, exprs):
        from .bone import getTargetName
        from .transform import Transform

        success = False
        prop,self.default = asset.initProp(self.rig, None)
        for bname,expr in exprs.items():
            if self.rig.data.DazExtraFaceBones or self.rig.data.DazExtraDrivenBones:
                dname = bname + "Drv"
                if dname in self.rig.pose.bones.keys():
                    bname = dname

            bname = getTargetName(bname, self.rig)
            if bname is None:
                continue
            self.taken[prop] = self.built[prop] = True

            pb = self.rig.pose.bones[bname]
            tfm = Transform()
            nonzero = False
            if "translation" in expr.keys():
                exprv = self.cheatSplineTCB(expr["translation"])
                value = exprv["value"]
                prop = exprv["prop"]
                tfm.setTrans(self.strength*value, prop)
                nonzero = True
            if "rotation" in expr.keys():
                exprv = self.cheatSplineTCB(expr["rotation"])
                value = exprv["value"]
                prop = exprv["prop"]
                tfm.setRot(self.strength*value, prop)
                nonzero = True
            if "scale" in expr.keys():
                exprv = expr["scale"]
                value = exprv["value"]
                prop = exprv["prop"]
                tfm.setScale(value, prop)
                nonzero = True
            if "general_scale" in expr.keys():
                exprv = expr["general_scale"]
                value = exprv["value"]
                prop = exprv["prop"]
                tfm.setGeneral(value, prop)
                nonzero = True
            if nonzero:
                # Fix: don't assume that the rest pose is at slider value 0.0.
                # For example: for 'default pose' (-1.0...1.0, default 1.0), use 1.0 for the rest pose, not 0.0.
                if self.addPoseboneDriver(pb, tfm):
                    success = True
        return success


    def cheatSplineTCB(self, expr):
        if "points" in expr.keys():
            comp = expr["output"][-1]
            idx = ord(comp) - ord('x')
            last = expr["points"][-1]
            expr["value"][idx] = last[0]*last[1]
            return expr
        else:
            return expr

#-------------------------------------------------------------
#   Eval formulas
#   For all kinds of drivers
#-------------------------------------------------------------

def parseChannel(channel):
    if channel == "value":
        return channel, 0, 0.0
    elif channel  == "general_scale":
        return channel, 0, 1.0
    attr,comp = channel.split("/")
    idx = getIndex(comp)
    if attr in ["rotation", "translation", "scale", "center_point", "end_point"]:
        default = Vector((0,0,0))
    elif attr in ["orientation"]:
        return None, 0, Vector()
    else:
        msg = ("Unknown attribute: %s" % attr)
        reportError(msg)
    return attr, idx, default


def removeInitFromExpr(var, expr, init):
    import re
    expr = expr[len(init):]
    string = expr.replace("+"," +").replace("-"," -")
    words = re.split(' ', string[1:-6])
    nwords = [word for word in words if (word and var not in word)]
    return "".join(nwords)


def getDriverVar(path, drv):
    n1 = ord('A')-1
    for var in drv.variables:
        trg = var.targets[0]
        if trg.data_path == path:
            return var.name, False
        n = ord(var.name[0])
        if n > n1:
            n1 = n
    if n1 == ord('Z'):
        var = "a"
    elif n1 == ord('z'):
        var = None
    else:
        var = chr(n1+1)
    return var,True


def deleteRigProperty(rig, prop):
    if prop in rig.keys():
        del rig[prop]
    if hasattr(bpy.types.Object, prop):
        delattr(bpy.types.Object, prop)

