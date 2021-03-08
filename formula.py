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


    def build(self, context, inst):
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
                inst = asset.getInstance(ref, self.caller)
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
                    ref,key = self.getRefKey(struct["url"])
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
            ref,key = self.getRefKey(formula["output"])
            return ref,key,stack[0]
        else:
            raise DazError("Stack error %s" % stack)
            return None,None,0


    def evalFormulas(self, rig, mesh):
        success = False
        exprs = {}
        for formula in self.formulas:
            self.evalFormula(formula, exprs, rig, mesh)
        if not exprs and GS.verbosity > 3:
            print("Could not parse formulas", self.formulas)
        return exprs


    def evalFormula(self, formula, exprs, rig, mesh):
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

        path,idx,default = self.parseChannel(channel)
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
        if "stage" in formula.keys():
            self.evalStage(formula, expr)
        else:
            self.evalOperations(formula, expr)


    def evalStage(self, formula, expr):
        if formula["stage"] == "mult":
            opers = formula["operations"]
            prop,type,comp = self.evalUrl(opers[0])
            if type == "value":
                expr["mult"] = prop


    def evalOperations(self, formula, expr):
        opers = formula["operations"]
        prop,type,comp = self.evalUrl(opers[0])
        if type == "value":
            if expr["prop"] is None:
                expr["prop"] = prop
        else:
            expr["bone"] = prop
        expr["comp"] = comp
        self.evalMainOper(opers, expr)


    def evalUrl(self, oper):
        if "url" not in oper.keys():
            print(oper)
            raise RuntimeError("BUG: Operation without URL")
        url = oper["url"].split("#")[-1]
        prop,type = url.split("?")
        prop = unquote(prop)
        path,comp,default = self.parseChannel(type)
        return prop,type,comp


    def evalMainOper(self, opers, expr):
        if len(opers) == 1:
            expr["factor"] = 1
            return
        oper = opers[-1]
        op = oper["op"]
        if op == "mult":
            expr["factor"] = opers[1]["val"]
        elif op == "spline_tcb":
            expr["points"] = [opers[n]["val"] for n in range(1,len(opers)-2)]
        else:
            reportError("Unknown formula %s" % opers, trigger=(2,6))
            return


    def parseChannel(self, channel):
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


    def getExprValue(self, expr, key):
        if ("factor" in expr.keys() and
            key in expr["factor"].keys()):
            return expr["factor"][key]
        else:
            return None


    def getRefKey(self, string):
        base = string.split(":",1)[-1]
        return base.rsplit("?",1)

#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, errors):

    def buildChannel(exprs, pb, channel, default):
        from .driver import makeSimpleBoneDriver
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
                    makeSimpleBoneDriver(sign*uvec, pb, "rotation_euler", idx2, rig, driver)

    exprs = asset.evalFormulas(rig, None)
    for driven,expr in exprs.items():
        if driven not in rig.pose.bones.keys():
            continue
        pb = rig.pose.bones[driven]
        if "rotation" in expr.keys():
            buildChannel(expr["rotation"], pb, "rotation_euler", Zero)


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

#-------------------------------------------------------------
#   class PoseboneDriver
#-------------------------------------------------------------

class PoseboneDriver:
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
        from .driver import addTransformVar
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
