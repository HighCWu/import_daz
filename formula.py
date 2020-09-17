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


import bpy
from bpy.props import *
import math
from mathutils import *
from .error import DazError, reportError
from .asset import *
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
            elif isinstance(asset, Node):
                inst = asset.getInstance(self.caller, ref, False)
                if inst:
                    inst.addToOffset(self.name, key, value)


    def build(self, context, inst):
        from .morphing import addToCategories
        from .driver import setFloatProp, setBoolProp
        rig = inst.rna
        if rig.pose is None:
            return
        formulas = PropFormulas(rig)
        props = formulas.buildPropFormula(self, None)
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
                inst = asset.getInstance(self.caller, ref, False)
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
                reportError("Unknown formula %s" % struct.items(), trigger=(1,5), force=True)

        if len(stack) == 1:
            ref,key = getRefKey(formula["output"])
            return ref,key,stack[0]
        else:
            raise DazError("Stack error %s" % stack)
            return None,None,0


    def evalFormulas(self, exprs, props, rig, mesh, useBone, useStages=False, verbose=False):
        success = False
        stages = []
        for formula in self.formulas:
            if self.evalFormula(formula, exprs, props, rig, mesh, useBone, useStages, stages):
                success = True
        if not success:
            if verbose:
                print("Could not parse formulas")
            return False
        return True


    def evalFormula(self, formula, exprs, props, rig, mesh, useBone, useStages, stages):
        from .bone import getTargetName

        driven = formula["output"].split("#")[-1]
        bname,channel = driven.split("?")
        if channel == "value":
            if False and mesh is None:
                if GS.verbosity > 3:
                    print("Cannot drive properties", bname)
                return False
            pb = None
        else:
            bname1 = getTargetName(bname, rig.pose.bones)
            if bname1 is None:
                reportError("Missing bone (evalFormula): %s" % bname, trigger=(2,3))
                return False
            else:
                bname = bname1
            if bname not in rig.pose.bones.keys():
                return False
            pb = rig.pose.bones[bname]

        path,idx,default = parseChannel(channel)
        if bname not in exprs.keys():
            exprs[bname] = {}
        if path not in exprs[bname].keys():
            value = self.getDefaultValue(useBone, pb, default)
            exprs[bname][path] = {"value" : value, "others" : [], "prop" : None, "bone" : None, "output" : formula["output"]}
        elif "stage" in formula.keys():
            pass
        elif path == "value":
            expr = exprs[bname][path]
            other = {"value" : expr["value"], "prop" : expr["prop"], "bone" : expr["bone"], "output" : formula["output"]}
            expr["others"].append(other)
            expr["value"] = self.getDefaultValue(useBone, pb, default)

        expr = exprs[bname][path]
        nops = 0
        type = None
        ops = formula["operations"]

        # URL
        struct = ops[0]
        if "url" not in struct.keys():
            return False
        prop,type = struct["url"].split("#")[-1].split("?")
        prop = prop.replace("%20", " ")
        path,comp,default = parseChannel(type)
        if type == "value":
            if props is None:
                return False
            expr["prop"] = prop
            props[prop] = True
        else:
            expr["bone"] = prop

        # Main operation
        last = ops[-1]
        op = last["op"]
        if op == "mult" and len(ops) == 3:
            value = ops[1]["val"]
            if not useBone:
                if isinstance(expr["value"], Vector):
                    expr["value"][idx] = value
                else:
                    expr["value"] = value
            elif pb is None:
                expr["value"][comp] = value
            else:
                expr["value"][idx][comp] = value
        elif op == "push" and len(ops) == 1 and useStages:
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
            expr["comp"] = comp
        else:
            #reportError("Unknown formula %s" % ops, trigger=(2,6))
            return False

        if "stage" in formula.keys() and len(stages) > 1:
            exprlist = []
            proplist = []
            for asset,bone,channel in stages:
                exprs1 = {}
                props1 = {}
                asset.evalFormulas(exprs1, props1, rig, mesh, useBone)
                if exprs1:
                    expr1 = list(exprs1.values())[0]
                    exprlist.append(expr1)
                if props1:
                    prop1 = list(props1.values())[0]
                    proplist.append(prop1)

            if formula["stage"] == "mult":
                self.multiplyStages(exprs, exprlist)
                #self.multiplyStages(props, proplist)

        return True


    def getDefaultValue(self, useBone, pb, default):
        if not useBone:
            return default
        elif pb is None:
            return Vector((default, default, default))
        else:
            try:
                return Matrix((default, default, default))
            except:
                pass
            msg = ("formula.py >> evalFormula()\n Failed to set value with default     \n %s" % default)
            reportError(msg, trigger=(2,5))
        return Matrix()


    def multiplyStages(self, exprs, exprlist):
        key = list(exprs.keys())[0]
        if exprlist:
            vectors = []
            for expr in exprlist:
                evalue = expr["value"]
                vectors.append(evalue["value"])
            struct = exprs[key] = exprlist[0]
            struct["value"]["value"] = vectors


def getRefKey(string):
    base = string.split(":",1)[-1]
    return base.rsplit("?",1)


#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, pbDriver, errors):
    from .driver import makeSimpleBoneDriver

    exprs = {}
    asset.evalFormulas(exprs, None, rig, None, True)

    for driven,expr in exprs.items():
        if driven not in rig.pose.bones.keys():
            continue
        pbDriven = rig.pose.bones[driven]
        if ("rotation" in expr.keys()):
            rot = expr["rotation"]["value"]
            driver = expr["rotation"]["bone"]
            if rot and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pbDriven:
                    print("Dependency loop: %s %s" % (pbDriver.name, pbDriven.name))
                else:
                    umat = convertDualMatrix(rot, pbDriver, pbDriven)
                    for idx in range(3):
                        makeSimpleBoneDriver(umat[idx], pbDriven, "rotation_euler", rig, None, driver, idx)

#-------------------------------------------------------------
#   Build shape formula
#   For corrective shapekeys
#-------------------------------------------------------------

class ShapeFormulas:
    def buildShapeFormula(self, asset, scn, rig, ob, verbose=True):
        if ob is None or ob.type != 'MESH' or ob.data.shape_keys is None:
            return False

        exprs = {}
        props = {}
        if not asset.evalFormulas(exprs, props, rig, ob, True, useStages=self.useStages, verbose=verbose):
            return False

        from .modifier import addToMorphSet
        for sname,expr in exprs.items():
            if sname in rig.data.bones.keys():
                continue
            addToMorphSet(rig, ob, self.morphset, sname, self.usePropDrivers, asset)
            if sname not in ob.data.shape_keys.key_blocks.keys():
                #print("No such shapekey:", sname)
                return False
            skey = ob.data.shape_keys.key_blocks[sname]
            if "value" in expr.keys():
                self.buildSingleShapeFormula(expr["value"], rig, ob, skey)
                for other in expr["value"]["others"]:
                    self.buildSingleShapeFormula(other, rig, ob, skey)
        return True


    def buildSingleShapeFormula(self, expr, rig, ob, skey):
        from .bone import BoneAlternatives

        bname = expr["bone"]
        if bname is None:
            # print("BSSF", expr, skey.name)
            return False
        if bname not in rig.pose.bones.keys():
            if bname in BoneAlternatives.keys():
                bname = BoneAlternatives[bname]
            else:
                reportError("Missing bone (buildSingleShapeFormula): %s" % bname, trigger=(2,3))
                return False
        makeSomeBoneDriver(expr, skey, "value", rig, ob, bname, -1)
        return True


def makeSomeBoneDriver(expr, rna, channel, rig, ob, bname, idx):
    from .driver import makeSimpleBoneDriver, makeProductBoneDriver, makeSplineBoneDriver
    if bname not in rig.pose.bones:
        reportError("Missing bone (makeSomeBoneDriver): %s" % bname, trigger=(2,3))
        return
    pb = rig.pose.bones[bname]
    if "comp" in expr.keys():
        uvec,xys = getSplinePoints(expr, pb)
        makeSplineBoneDriver(uvec, xys, rna, channel, rig, ob, bname, idx)
    elif isinstance(expr["value"], list):
        uvecs = []
        for vec in expr["value"]:
            uvec = convertDualVector(vec/D, pb, False)
            uvecs.append(uvec)
        makeProductBoneDriver(uvecs, rna, channel, rig, ob, bname, idx)
    else:
        vec = expr["value"]
        uvec = convertDualVector(vec/D, pb, False)
        makeSimpleBoneDriver(uvec, rna, channel, rig, ob, bname, idx)


def getSplinePoints(expr, pb):
    j = expr["comp"]
    points = expr["points"]
    n = len(points)
    if (points[0][0] > points[n-1][0]):
        points.reverse()

    diff = points[n-1][0] - points[0][0]
    vec = Vector((0,0,0))
    vec[j] = 1/(diff*D)
    uvec = convertDualVector(vec, pb, False)
    xys = []
    for k in range(n):
        x = points[k][0]/diff
        y = points[k][1]
        xys.append((x, y))
    return uvec, xys


Units = [
    Euler((1,0,0)).to_matrix(),
    Euler((0,1,0)).to_matrix(),
    Euler((0,0,1)).to_matrix()
]

def convertDualVector(uvec, pb, invert):
    from .node import getTransformMatrix
    smat = getTransformMatrix(pb)
    if invert:
        smat.invert()
    nvec = Vector((0,0,0))
    for i in range(3):
        mat = Mult3(smat, Units[i], smat.inverted())
        euler = mat.to_euler(pb.DazRotMode)
        nvec[i] = uvec.dot(Vector(euler))
    return nvec


def convertDualMatrix(umat, pbDriver, pbDriven):
    from .node import getTransformMatrix
    smat = getTransformMatrix(pbDriver)
    tmat = getTransformMatrix(pbDriven)
    nmat = Matrix().to_3x3()
    nmat.zero()

    for i in range(3):
        imat = Mult3(tmat, Units[i], tmat.inverted())
        ivec = Vector(imat.to_euler(pbDriven.DazRotMode))
        for j in range(3):
            jmat = Mult3(smat, Units[j], smat.inverted())
            jvec = Vector(jmat.to_euler(pbDriver.DazRotMode))
            nmat[i][j] = ivec.dot(Mult2(umat, jvec))
    return nmat

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
        scale -= Vector((1,1,1))
        success = False
        if (tfm.transProp and loc.length > 0.01*self.rig.DazScale):
            self.setFcurves(pb, "", loc, tfm.transProp, "location")
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                value = Vector(quat)
                value[0] = 1.0 - value[0]
                self.setFcurves(pb, "1.0-", value, tfm.rotProp, "rotation_quaternion")
                success = True
            else:
                value = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, "", value, tfm.rotProp, "rotation_euler")
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, "", scale, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, "", scale, tfm.generalProp, "scale")
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


    def setFcurves(self, pb, init, value, prop, channel):
        path = '["%s"]' % prop
        key = channel[0:3].capitalize()
        fcurves = self.getBoneFcurves(pb, channel)
        if len(fcurves) == 0:
            return
        if hasattr(fcurves[0].driver, "use_self"):
            for fcu in fcurves:
                idx = fcu.array_index
                self.addCustomDriver(fcu, pb, init, value[idx], prop, key)
                init = ""
        else:
            fcurves = self.getBoneFcurves(pb, channel)
            for fcu in fcurves:
                idx = fcu.array_index
                self.addScriptedDriver(fcu, pb, init, value[idx], path)
                init = ""


    def addCustomDriver(self, fcu, pb, init, value, prop, key):
        from .driver import addTransformVar, driverHasVar
        from .daz import addSelfRef
        fcu.driver.type = 'SCRIPTED'
        if abs(value) > 1e-4:
            expr = 'evalMorphs%s(self, %d)' % (key, fcu.array_index)
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
            addSelfRef(self.rig, pb)
            self.addMorphGroup(pb, fcu.array_index, key, prop, self.default, value)
            if len(fcu.modifiers) > 0:
                fmod = fcu.modifiers[0]
                fcu.modifiers.remove(fmod)


    def clearProp(self, pgs, prop, idx):
        for n,pg in enumerate(pgs):
            if pg.name == prop and pg.index == idx:
                pgs.remove(n)
                return


    def addMorphGroup(self, pb, idx, key, prop, default, factor, factor2=None):
        pgs = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
        self.clearProp(pgs, prop, idx)
        pg = pgs.add()
        pg.init(prop, idx, default, factor, factor2)
        if prop not in self.rig.keys():
            from .driver import setFloatProp
            setFloatProp(self.rig, prop, 0.0)


    def addError(self, err, prop, pb):
        if err not in self.errors.keys():
            self.errors[err] = {"props" : [], "bones": []}
        if prop not in self.errors[err]["props"]:
            self.errors[err]["props"].append(prop)
        if pb.name not in self.errors[err]["bones"]:
            self.errors[err]["bones"].append(pb.name)


    def addScriptedDriver(self, fcu, pb, init, value, path):
        fcu.driver.type = 'SCRIPTED'
        var,isnew = getDriverVar(path, fcu.driver)
        if var is None:
            self.addError("Too many variables for the following properties:", path, pb)
            return
        drvexpr = removeInitFromExpr(var, fcu.driver.expression, init)
        if abs(value) > 1e-4:
            if isnew:
                self.addDriverVar(var, path, fcu.driver)
            if value < 0:
                sign = "-"
                value = -value
            else:
                sign = "+"
            expr = "%s%d*%s" % (sign, int(1000*value), var)
            drvexpr = init + "(" + drvexpr + expr + ")/1000"
            if len(drvexpr) <= 255:
                fcu.driver.expression = drvexpr
            else:
                string = drvexpr[0:249]
                string1 = string.rsplit("+",1)[0]
                string2 = string.rsplit("-",1)[0]
                if len(string1) > len(string2):
                    string = string1
                else:
                    string = string2
                drvexpr = string + ")/1000"
                fcu.driver.expression = drvexpr
                self.addError("Drive expression too long:", path, pb, errors)
                return

        if len(fcu.modifiers) > 0:
            fmod = fcu.modifiers[0]
            fcu.modifiers.remove(fmod)


    def addDriverVar(self, vname, path, drv):
        var = drv.variables.new()
        var.name = vname
        var.type = 'SINGLE_PROP'
        trg = var.targets[0]
        trg.id_type = 'OBJECT'
        trg.id = self.rig
        trg.data_path = path

#-------------------------------------------------------------
#   class PropFormulas
#-------------------------------------------------------------

class PropFormulas(PoseboneDriver):

    def __init__(self, rig):
        PoseboneDriver.__init__(self, rig)
        self.others = {}
        self.taken = {}
        self.built = {}


    def buildPropFormula(self, asset, filepath):
        self.filepath = filepath
        exprs = {}
        props = {}
        asset.evalFormulas(exprs, props, self.rig, None, False)

        if not props:
            if GS.verbosity > 3:
                print("Cannot evaluate formula")
            if GS.verbosity > 4:
                print(asset.formulas)

        asset.setupProp(self.morphset, self.rig, self.usePropDrivers)

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
            bname = getTargetName(prop, self.rig.pose.bones)
            if bname is None:
                if prop in self.built.keys() and self.built[prop]:
                    continue
                struct = expr["value"]
                key = struct["prop"]
                self.taken[key] = False
                val = struct["value"]
                if prop not in self.others.keys():
                    self.others[prop] = []
                self.others[prop].append((key, val))


    def opencode(self, exprs, asset, opencoded, level):
        from .bone import getTargetName
        from .modifier import ChannelAsset
        from .daz import addDependency
        if level > 5:
            raise DazError("Recursion too deep")
        for prop,expr in exprs.items():
            bname = getTargetName(prop, self.rig.pose.bones)
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
                subasset = asset.getTypedAsset(url, ChannelAsset)
                if isinstance(subasset, Formula):
                    subexprs = {}
                    subprops = {}
                    subasset.evalFormulas(subexprs, subprops, self.rig, None, False)
                    subopen = {}
                    self.opencode(subexprs, asset, subopen, level+1)
                    if key not in opencoded.keys():
                        opencoded[key] = []
                    opencoded[key].append((val,subexprs,subprops,subopen))


    def combineExpressions(self, openlist, prop, exprs, value):
        from .bone import getTargetName
        for val,subexprs,subprops,subopen in openlist:
            value1 = val*value
            if subopen:
                for subprop,sublist in subopen.items():
                    self.combineExpressions(sublist, prop, exprs, value1)
            else:
                for bname,subexpr in subexprs.items():
                    bname1 = getTargetName(bname, self.rig.pose.bones)
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
        from .modifier import stripPrefix
        remains = self.others
        sorted = []
        nremains = len(remains)
        props = []
        for level in range(1,6):
            print("--- Pass %d (%d left) ---" % (level+1, nremains))
            batch, used, remains = self.getNextLevelMorphs(remains)
            self.buildMorphBatch(batch)
            for key in batch.keys():
                prop = stripPrefix(key)
                print(" *", prop)
                missing[prop] = False
                props.append(prop)
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
                prop = stripPrefix(key)
                print("-", prop)
        return props


    def getNextLevelMorphs(self, others):
        from .daz import addDependency
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
        stored = {}
        for pb in self.rig.pose.bones:
            if not (pb.DazLocProps or pb.DazRotProps or pb.DazScaleProps):
                continue
            data = stored[pb.name] = {"Loc" : {}, "Rot" : {}, "Sca" : {}}
            for channel,pgs in [
                ("Loc", pb.DazLocProps),
                ("Rot", pb.DazRotProps),
                ("Sca", pb.DazScaleProps)]:
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
                self.addToPropGroup(prop)


    def addToPropGroup(self, prop):
        from .modifier import stripPrefix
        from .morphing import setActivated
        pg = getattr(self.rig, "Daz"+self.morphset)
        if prop not in pg.keys():
            item = pg.add()
            item.name = prop
            item.text = stripPrefix(prop)
            setActivated(self.rig, prop, True)


    def addOtherShapekey(self, prop, key, factor):
        from .driver import getShapekeyPropDriver, addVarToDriver
        if self.mesh and self.mesh.type == 'MESH' and self.rig:
            skeys = self.mesh.data.shape_keys
            if skeys and key in skeys.key_blocks.keys():
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

            bname = getTargetName(bname, self.rig.pose.bones)
            if bname is None:
                continue
            self.taken[prop] = self.built[prop] = True

            pb = self.rig.pose.bones[bname]
            tfm = Transform()
            nonzero = False
            if "translation" in expr.keys():
                tfm.setTrans(expr["translation"]["value"], expr["translation"]["prop"])
                nonzero = True
            if "rotation" in expr.keys():
                tfm.setRot(expr["rotation"]["value"], expr["rotation"]["prop"])
                nonzero = True
            if "scale" in expr.keys():
                tfm.setScale(expr["scale"]["value"], False, expr["scale"]["prop"])
                nonzero = True
            if "general_scale" in expr.keys():
                tfm.setGeneral(expr["general_scale"]["value"], False, expr["general_scale"]["prop"])
                nonzero = True
            if nonzero:
                # Fix: don't assume that the rest pose is at slider value 0.0.
                # For example: for 'default pose' (-1.0...1.0, default 1.0), use 1.0 for the rest pose, not 0.0.
                if self.addPoseboneDriver(pb, tfm):
                    success = True
        return success

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

