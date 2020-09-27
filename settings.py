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

        self.contentDirs = [
            self.fixPath("~/Documents/DAZ 3D/Studio/My Library"),
            "C:/Users/Public/Documents/My DAZ 3D Library",
        ]
        self.mdlDirs = [
            "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray",
        ]
        self.cloudDirs = []
        self.errorPath = self.fixPath("~/Documents/daz_importer_errors.txt")
        if bpy.app.version < (2,80,0):
            path = "~/import-daz-settings-27x.json"
        else:
            path = "~/import-daz-settings-28x.json"
        self.settingsPath = self.fixPath(path)
        self.rootPath = self.fixPath("~/import-daz-paths.json")

        self.verbosity = 2
        self.zup = True
        self.chooseColors = 'GUESS'
        self.orientMethod = 'DAZ STUDIO'
        self.useQuaternions = False
        self.useLegacyLocks = False
        self.caseSensitivePaths = (platform != 'win32')
        self.mergeShells = True
        self.brightenEyes = 1.0

        self.limitBump = False
        self.maxBump = 10
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"
        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.useEnvironment = True
        self.diffuseShader = 'OREN_NAYAR'
        self.specularShader = 'BLINN'
        self.diffuseRoughness = 0.3
        self.specularRoughness = 0.3

        self.propMin = -1.0
        self.propMax = 1.0
        self.useDazPropLimits = True
        self.useDazPropDefault = True

        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.useConnect = True

        self.buildHighdef = True
        self.useMultires = True
        self.strandsAsHair = True
        self.multipleHairMaterials = True
        self.addFaceDrivers = True
        self.useInfluence = True
        self.useSimulation = False
        self.useDeflectors = True


    SceneTable = {
        "DazVerbosity" : "verbosity",
        "DazZup" : "zup",
        "DazErrorPath" : "errorPath",
        "DazCaseSensitivePaths" : "caseSensitivePaths",

        "DazChooseColors" : "chooseColors",
        "DazMergeShells" : "mergeShells",
        "DazBrightenEyes" : "brightenEyes",
        "DazUseEnvironment" : "useEnvironment",
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

        "DazOrientMethod" : "orientMethod",
        "DazUseLegacyLocks" : "useLegacyLocks",
        "DazUseQuaternions" : "useQuaternions",
        "DazUseLockLoc" : "useLockLoc",
        "DazUseLimitLoc" : "useLimitLoc",
        "DazUseLockRot" : "useLockRot",
        "DazUseLimitRot" : "useLimitRot",

        "DazBuildHighdef" : "buildHighdef",
        "DazMultires" : "useMultires",
        "DazStrandsAsHair" : "strandsAsHair",
        "DazMultipleHairMaterials" : "multipleHairMaterials",
        "DazAddFaceDrivers" : "addFaceDrivers",
        "DazInfluence" : "useInfluence",
        "DazSimulation" : "useSimulation",
        "DazDeflectors" : "useDeflectors",
    }

    def fixPath(self, path):
        return os.path.expanduser(path).replace("\\", "/")


    def getDazPaths(self):
        paths = self.contentDirs + self.mdlDirs + self.cloudDirs
        return paths


    def fromScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(scn, prop)
                setattr(self, key, value)
            else:
                print("MIS", prop, key)
        self.contentDirs = self.pathsFromScene(scn.DazContentDirs)
        self.mdlDirs = self.pathsFromScene(scn.DazMDLDirs)
        self.cloudDirs = self.pathsFromScene(scn.DazCloudDirs)
        self.errorPath = self.fixPath(getattr(scn, "DazErrorPath"))
        self.eliminateDuplicates()


    def pathsFromScene(self, pgs):
        paths = []
        for pg in pgs:
            path = self.fixPath(pg.name)
            if os.path.exists(path):
                paths.append(path)
            else:
                print("Skip non-existent path:", path)
        return paths


    def pathsToScene(self, paths, pgs):
        pgs.clear()
        for path in paths:
            pg = pgs.add()
            pg.name = self.fixPath(path)


    def toScene(self, scn):
        for prop,key in self.SceneTable.items():
            if hasattr(scn, prop) and hasattr(self, key):
                value = getattr(self, key)
                try:
                    setattr(scn, prop, value)
                except TypeError:
                    print("Type Error", prop, key, value)
            else:
                print("MIS", prop, key)
        self.pathsToScene(self.contentDirs, scn.DazContentDirs)
        self.pathsToScene(self.mdlDirs, scn.DazMDLDirs)
        self.pathsToScene(self.cloudDirs, scn.DazCloudDirs)
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
            print("Could not open %s" % filepath)
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
            self.contentDirs = self.readSettingsDirs("DazPath", settings)
            self.contentDirs += self.readSettingsDirs("DazContent", settings)
            self.mdlDirs = self.readSettingsDirs("DazMDL", settings)
            self.cloudDirs = self.readSettingsDirs("DazCloud", settings)
            self.eliminateDuplicates()
        else:
            raise DazError("Not a settings file   :\n'%s'" % filepath)


    def readSettingsDirs(self, prefix, settings):
        paths = []
        n = len(prefix)
        pathlist = [(key, path) for key,path in settings.items() if key[0:n] == prefix]
        pathlist.sort()
        for _prop,path in pathlist:
            path = self.fixPath(path)
            if os.path.exists(path):
                paths.append(path)
            else:
                print("No such path:", path)
        return paths


    def eliminateDuplicates(self):
        content = dict([(path,True) for path in self.contentDirs])
        mdl = dict([(path,True) for path in self.mdlDirs])
        cloud = dict([(path,True) for path in self.cloudDirs])
        for path in self.mdlDirs + self.cloudDirs:
            if path in content.keys():
                print("Remove duplicate path: %s" % path)
                del content[path]
        self.contentDirs = list(content.keys())
        self.mdlDirs = list(mdl.keys())
        self.cloudDirs = list(cloud.keys())


    def readDazPaths(self, struct, btn):
        self.contentDirs = []
        if btn.useContent:
            self.contentDirs = self.readAutoDirs("content", struct)
            self.contentDirs += self.readAutoDirs("builtin_content", struct)
        self.mdlDirs = []
        if btn.useMDL:
            self.mdlDirs = self.readAutoDirs("builtin_mdl", struct)
            self.mdlDirs += self.readAutoDirs("mdl_dirs", struct)
        self.cloudDirs = []
        if btn.useCloud:
            self.cloudDirs = self.readCloudDirs("cloud_content", struct)
        self.eliminateDuplicates()


    def readAutoDirs(self, key, struct):
        paths = []
        if key in struct.keys():
            folders = struct[key]
            if not isinstance(folders, list):
                folders = [folders]
            for path in folders:
                path = self.fixPath(path)
                if os.path.exists(path):
                    paths.append(path)
                else:
                    print("Path does not exist", path)
        return paths


    def readCloudDirs(self, key, struct):
        paths = []
        if key in struct.keys():
            folder = struct[key]
            if isinstance(folder, list):
                folder = folder[0]
            folder = self.fixPath(folder)
            if os.path.exists(folder):
                cloud = os.path.join(folder, "data", "cloud")
                if os.path.exists(cloud):
                    for file in os.listdir(cloud):
                        if file != "meta":
                            path = self.fixPath(os.path.join(cloud, file))
                            if os.path.isdir(path):
                                paths.append(path)
                            else:
                                print("Folder does not exist", folder)
        return paths


    def saveDirs(self, paths, prefix, struct):
        for n,path in enumerate(paths):
            struct["%s%03d" % (prefix, n+1)] = self.fixPath(path)


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
        self.saveDirs(self.contentDirs, "DazContent", struct)
        self.saveDirs(self.mdlDirs, "DazMDL", struct)
        self.saveDirs(self.cloudDirs, "DazCloud", struct)
        filepath = os.path.expanduser(filepath)
        filepath = os.path.splitext(filepath)[0] + ".json"
        saveJson({"daz-settings" : struct}, filepath)
        print("Settings file %s saved" % filepath)


    def loadDefaults(self):
        self.load(self.settingsPath)


    def saveDefaults(self):
        self.save(self.settingsPath)

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
        self.materialMethod = 'BSDF'
        self.useCustomShapes = True

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
        self.hdcollection = None
        self.refGroups = None
        self.fps = 30
        self.integerFrames = True
        self.missingAssets = {}
        self.hdfailures = []
        self.deflectors = {}
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
        self.materialMethod = btn.materialMethod
        self.useCustomShapes = btn.useCustomShapes

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

