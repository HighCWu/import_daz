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

#-------------------------------------------------------------
#   Settings
#-------------------------------------------------------------

import os
import bpy

#-------------------------------------------------------------
#   Local settings
#-------------------------------------------------------------

class GlobalSettings:

    def __init__(self):
        from sys import platform

        self.numpaths = 3
        self.dazpaths = [
            self.fixPath("~/Documents/DAZ 3D/Studio/My Library"),
            "C:/Users/Public/Documents/My DAZ 3D Library",
            "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray",
        ]
        self.errorPath = self.fixPath("~/Documents/daz_importer_errors.txt")
        if bpy.app.version < (2,80,0):
            path = "~/import-daz-settings-27x.json"
        else:
            path = "~/import-daz-settings-28x.json"
        self.settingsPath = self.fixPath(path)

        self.verbosity = 2
        self.zup = True
        self.chooseColors = 'GUESS'
        self.useDazBones = False
        self.useDazOrientation = False
        self.caseSensitivePaths = (platform != 'win32')
        self.mergeShells = True

        self.limitBump = False
        self.maxBump = 10
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"
        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.diffuseShader = 'OREN_NAYAR'
        self.specularShader = 'BLINN'
        self.diffuseRoughness = 0.3
        self.specularRoughness = 0.3

        self.propMin = -1.0
        self.propMax = 1.0
        self.useDazPropLimits = True
        self.useDazPropDefault = True

        self.useLockRot = True
        self.useLockLoc = True
        self.useLimitRot = False
        self.useLimitLoc = False
        self.useConnect = True

        self.buildHighdef = True
        self.addFaceDrivers = True


    SceneTable = {
        "DazNumPaths" : "numpaths",
        "DazVerbosity" : "verbosity",
        "DazZup" : "zup",
        "DazErrorPath" : "errorPath",
        "DazCaseSensitivePaths" : "caseSensitivePaths",

        "DazChooseColors" : "chooseColors",
        "DazMergeShells" : "mergeShells",
        "DazLimitBump" : "limitBump",
        "DazMaxBump" : "maxBump",
        "DazHandleRenderSettings" : "handleRenderSettings",
        "DazHandleLightSettings" : "handleLightSettings",
        "DazUseDisplacement" : "useDisplacement",
        "DazUseEmission" : "useEmission",
        "DazUseReflection" : "useReflection",
        "DazDiffuseShader" : "diffuseShader",
        "DazSpecularShader" : "specularShader",
        "DazDiffuseRoughness" : "diffuseRoughness",
        "DazSpecularRoughness" : "specularRoughness",

        "DazPropMin" : "propMin",
        "DazPropMax" : "propMax",
        "DazUsePropLimits" : "useDazPropLimits",
        "DazUsePropDefault" : "useDazPropDefault",

        "DazBones" : "useDazBones",
        "DazOrientation" : "useDazOrientation",
        "DazUseLockRot" : "useLockRot",
        "DazUseLockLoc" : "useLockLoc",

        "DazBuildHighdef" : "buildHighdef",
        "DazAddFaceDrivers" : "addFaceDrivers",
    }

    def fixPath(self, path):
        return os.path.expanduser(path).replace("\\", "/")


    def fromScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(scn, prop)
                setattr(self, key, value)
            else:
                print("MIS", prop, key)
        self.dazpaths = []
        for n in range(self.numpaths):
            path = self.fixPath(getattr(scn, "DazPath%d" % (n+1)))
            self.dazpaths.append(path)
        self.errorPath = self.fixPath(getattr(scn, "DazErrorPath"))


    def toScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(self, key)
                setattr(scn, prop, value)
            else:
                print("MIS", prop, key)
        if self.numpaths > len(self.dazpaths):
            self.numpaths = len(self.dazpaths)
        for n in range(self.numpaths):
            path = self.fixPath(self.dazpaths[n])
            setattr(scn, "DazPath%d" % (n+1), path)
        path = self.fixPath(self.errorPath)
        setattr(scn, "DazErrorPath", path)


    def openFile(self, filepath):
        filepath = os.path.expanduser(filepath)
        try:
            fp = open(filepath, "r", encoding="utf-8-sig")
        except:
            fp = None
        if fp:
            import json
            try:
                return json.load(fp)
            except json.decoder.JSONDecodeError as err:
                print("File %s is corrupt" % filepath)
                print("Error: %s" % err)
                return None
            finally:
                fp.close()
        else:
            return None


    def load(self, filepath):
        struct = self.openFile(filepath)
        if struct:
            print("Load settings from", filepath)
            self.readDazSettings(struct)
    

    def readDazSettings(self, struct):
        if "daz-settings" in struct.keys():
            settings = struct["daz-settings"]
            for prop,value in settings.items():
                if prop in self.SceneTable.keys():
                    key = self.SceneTable[prop]
                    setattr(self, key, value)
            self.dazpaths = []
            for n in range(self.numpaths):
                prop = "DazPath%d" % (n+1)
                if prop in settings.keys():
                    path = self.fixPath(settings[prop])
                else:
                    path = ""
                self.dazpaths.append(path)
        else:
            raise DazError("Not a settings file   :\n'%s'" % filepath)


    def readDazPaths(self, struct):
        self.dazpaths = []
        n = 0
        for key in ["content", "builtin_mdl", "import_dirs", "mdl_dirs", "builtin_content", "cloud_content"]:
            if key in struct.keys():
                for path in struct[key]:
                    self.dazpaths.append(self.fixPath(path))
        self.numpaths = len(self.dazpaths)
        print("NP", self.numpaths)
        print("DP", self.dazpaths)


    def save(self, filepath):
        from .load_json import saveJson
        struct = {}
        for prop,key in self.SceneTable.items():
            value = getattr(self, key)
            if (isinstance(value, int) or
                isinstance(value, float) or
                isinstance(value, bool) or
                isinstance(value, str)):
                struct[prop] = value
        for n in range(self.numpaths):
            path = self.fixPath(self.dazpaths[n])
            struct["DazPath%d" % (n+1)] = path
        filepath = os.path.expanduser(filepath)
        filepath = os.path.splitext(filepath)[0] + ".json"
        saveJson({"daz-settings" : struct}, filepath)
        print("Settings file %s saved" % filepath)


    def loadDefaults(self):
        self.load(self.settingsPath)
        filepath = "~/import-daz-paths.json"
        struct = self.openFile(filepath)
        if struct:
            print("Load paths from", filepath)
            self.readDazPaths(struct)


    def saveDefaults(self):
        self.save(self.settingsPath)


    def getDazPaths(self):
        return self.dazpaths[0:self.numpaths]

#-------------------------------------------------------------
#   Local settings
#-------------------------------------------------------------

class LocalSettings:
    def __init__(self):
        self.scale = 0.1
        self.skinColor = None
        self.clothesColor = None
        self.fitFile = False
        self.autoMaterials = True
        self.methodOpaque = 'BSDF'
        self.methodVolumetric = 'VOLUMETRIC'
        self.methodRefractive = 'BSDF'
        self.brightenEyes = 1.0
        self.useEnvironment = False
        self.renderMethod = 'PBR'

        self.useNodes = False
        self.useGeometries = False
        self.useImages = False
        self.useMaterials = False
        self.useModifiers = False
        self.useMorph = False
        self.useFormulas = False
        self.applyMorphs = False
        self.useAnimations = False
        self.useUV = False
        self.collection = None
        self.refGroups = None
        self.fps = 30
        self.integerFrames = True
        self.missingAssets = {}
        self.singleUser = False

        self.usedFeatures = {
            "Bounces" : True,
            "Diffuse" : False,
            "Glossy" : False,
            "Transparent" : False,
            "SSS" : False,
            "Volume" : False,
        }


    def __repr__(self):
        string = "<Local Settings"
        for key in dir(self):
            if key[0] != "_":
                #attr = getattr(self, key)
                string += "\n  %s : %s" % (key, 0)
        return string + ">"


    def reset(self, scn):
        from .material import clearMaterials
        from .asset import setDazPaths, clearAssets
        global theTrace
        theTrace = []
        setDazPaths(scn)
        clearAssets()
        clearMaterials()
        self.useStrict = False
        self.scene = scn


    def forImport(self, btn, scn):
        self.__init__()
        self.reset(scn)
        self.scale = btn.unitScale
        self.useNodes = True
        self.useGeometries = True
        self.useImages = True
        self.useMaterials = True
        self.useModifiers = True
        self.useUV = True

        self.skinColor = btn.skinColor
        self.clothesColor = btn.clothesColor
        self.brightenEyes = btn.brightenEyes
        self.renderMethod = scn.render.engine

        self.autoMaterials = btn.useAutoMaterials
        self.methodOpaque = btn.methodOpaque
        self.methodVolumetric = btn.methodVolumetric
        self.methodRefractive = btn.methodRefractive
        self.useEnvironment = btn.useEnvironment

        self.useStrict = True
        self.singleUser = True
        if btn.fitMeshes == 'SHARED':
            self.singleUser = False
        elif btn.fitMeshes == 'UNIQUE':
            pass
        elif btn.fitMeshes == 'DBZFILE':
            self.fitFile = True


    def forAnimation(self, btn, ob, scn):
        self.__init__()
        self.reset(scn)
        self.scale = ob.DazScale
        self.useNodes = True
        self.useAnimations = True
        if hasattr(btn, "fps"):
            self.fps = btn.fps
            self.integerFrames = btn.integerFrames



    def forMorphLoad(self, ob, scn):
        self.__init__()
        self.reset(scn)
        self.scale = ob.DazScale
        self.useMorph = True
        self.useFormulas = True
        self.applyMorphs = False
        self.useModifiers = True


    def forUV(self, ob, scn):
        self.__init__()
        self.reset(scn)
        self.scale = ob.DazScale
        self.useUV = True


    def forMaterial(self, ob, scn):
        self.__init__()
        self.reset(scn)
        self.scale = ob.DazScale
        self.useImages = True
        self.useMaterials = True
        self.verbosity = 1


    def forEngine(self, scn):
        self.__init__()
        self.reset(scn)


GS = GlobalSettings()
LS = LocalSettings()
theTrace = []

