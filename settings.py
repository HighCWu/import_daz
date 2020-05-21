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

class Settings:
    def __init__(self):
        self.scale = 0.1
        self.binary = False
        self.chooseColors = 'GUESS'
        self.skinColor = None
        self.clothesColor = None
        self.verbosity = 1
        self.useStrict = False
        self.zup = True
        self.caseSensitivePaths = False
        self.makeDrivers = 'PROPS'
        self.propMin = -1.0
        self.propMax = 1.0
        self.useDazPropLimits = True
        self.useDazPropDefault = True
        self.autoMaterials = True
        self.handleOpaque = 'BSDF'
        self.handleVolumetric = 'VOLUMETRIC'
        self.handleRefractive = 'BSDF'
        self.brightenEyes = 1.0
        self.useEnvironment = False
        self.renderMethod = 'PBR'
        self.fps = 30
        self.integerFrames = True
        self.missingAssets = []

        self.collection = None
        self.refGroups = None

        self.useLockRot = True
        self.useLockLoc = True
        self.useLimitRot = True
        self.useLimitLoc = True
        self.useConnect = True
        
        self.usedFeatures = {}        

        self.errorPath = ""
        self.useNothing()


    def useNothing(self):
        self.fitFile = False
        self.useScene = True
        self.useNodes = False
        self.useGeometries = False
        self.useImages = False
        self.useMaterials = False
        self.useModifiers = False
        self.useMorph = False
        self.useFormulas = False
        self.applyMorphs = False
        self.useAnimations = False
        self.useLibraries = False
        self.useUV = False
        self.collection = None
        self.refGroups = None
        self.fps = 30
        self.integerFrames = True
        self.missingAssets = []


    def __repr__(self):
        string = "<Settings"
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

        self.scene = scn
        self.errorPath = scn.DazErrorPath
        self.verbosity = scn.DazVerbosity
        self.useStrict = False
        self.singleUser = False

        #print("Unit", scn.unit_settings.system)
        #if scn.unit_settings.system == 'IMPERIAL':
        #    self.scale = 0.01/(0.0254*scn.unit_settings.scale_length)
        #elif scn.unit_settings.system == 'METRIC':
        #    self.scale = 0.01/scn.unit_settings.scale_length
        self.zup = scn.DazZup
        self.caseSensitivePaths = scn.DazCaseSensitivePaths
        self.makeDrivers = scn.DazMakeDrivers
        self.propMin = scn.DazPropMin
        self.propMax = scn.DazPropMax
        self.useDazPropLimits = scn.DazUsePropLimits
        self.useDazPropDefault = scn.DazUsePropDefault
        self.chooseColors = scn.DazChooseColors

        self.useLockRot = (scn.DazUseLockRot or scn.DazUseLimitRot)
        self.useLockLoc = (scn.DazUseLockLoc or scn.DazUseLimitLoc)
        self.useLimitRot = scn.DazUseLimitRot
        self.useLimitLoc = scn.DazUseLimitLoc
        
        self.usedFeatures = {
            "Bounces" : True,
            "Diffuse" : False,
            "Glossy" : False,
            "Transparent" : False,
            "Volume" : False,
        }


    def forImport(self, btn, scn):
        self.reset(scn)
        self.scale = btn.unitScale
        self.useNothing()
        self.useScene = True
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
        self.handleOpaque = btn.handleOpaque
        self.handleVolumetric = btn.handleVolumetric
        self.handleRefractive = btn.handleRefractive
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
        self.reset(scn)
        self.scale = ob.DazScale
        self.useNothing()
        self.useScene = True
        self.useNodes = True
        self.useAnimations = True
        if hasattr(btn, "fps"):
            self.fps = btn.fps
            self.integerFrames = btn.integerFrames



    def forMorphLoad(self, ob, scn):
        self.reset(scn)
        self.scale = ob.DazScale
        self.useNothing()
        self.useScene = True
        self.useMorph = True
        self.useFormulas = True
        self.applyMorphs = False
        self.useModifiers = True


    def forUV(self, ob, scn):
        self.reset(scn)
        self.scale = ob.DazScale
        self.useNothing()
        self.useUV = True


    def forMaterial(self, ob, scn):
        self.reset(scn)
        self.scale = ob.DazScale
        self.useNothing()
        self.useImages = True
        self.useMaterials = True
        self.verbosity = 1


    def forEngine(self, scn):
        self.reset(scn)
        self.useNothing()


theSettings = Settings()
theTrace = []

