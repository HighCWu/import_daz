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
from .error import *
from .utils import *

#------------------------------------------------------------------
#   Import file
#------------------------------------------------------------------

def getMainAsset(filepath, context, btn):
    import time
    from .objfile import getFitFile, fitToFile

    scn = context.scene
    LS.forImport(btn, scn)
    LS.scene = filepath
    print("Scale", LS.scale)
    t1 = time.perf_counter()

    from .fileutils import getTypedFilePath
    path = getTypedFilePath(filepath, ["duf", "dsf", "dse"])
    if path is None:
        raise DazError("Found no .duf file matching\n%s        " % filepath)
    filepath = path
    startProgress("\nLoading %s" % filepath)
    if LS.fitFile:
        getFitFile(filepath)

    from .load_json import loadJson
    struct = loadJson(filepath)
    showProgress(10, 100)

    grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
    LS.collection = makeRootCollection(grpname, context)

    print("Parsing data")
    from .files import parseAssetFile
    main = parseAssetFile(struct, toplevel=True)
    if main is None:
        msg = ("File not found:  \n%s      " % filepath)
        raise DazError(msg)
    showProgress(20, 100)

    print("Preprocessing...")
    for asset,inst in main.nodes:
        inst.preprocess(context)

    if LS.fitFile:
        fitToFile(filepath, main.nodes)
    showProgress(30, 100)

    for asset,inst in main.nodes:
        inst.preprocess2(context)
    for asset,inst in main.modifiers:
        asset.preprocess(inst)

    print("Building objects...")
    for asset in main.materials:
        asset.build(context)
    showProgress(50, 100)

    nnodes = len(main.nodes)
    idx = 0
    for asset,inst in main.nodes:
        showProgress(50 + int(idx*30/nnodes), 100)
        idx += 1
        asset.build(context, inst)      # Builds armature
    showProgress(80, 100)

    nmods = len(main.modifiers)
    idx = 0
    for asset,inst in main.modifiers:
        showProgress(80 + int(idx*10/nmods), 100)
        idx += 1
        asset.build(context, inst)      # Builds morphs
    showProgress(90, 100)

    for _,inst in main.nodes:
        inst.poseRig(context)
    for asset,inst in main.nodes:
        inst.postbuild(context)

    # Need to update scene before calculating object areas
    updateScene(context)
    for asset in main.materials:
        asset.postbuild()

    print("Postprocessing...")
    for asset,inst in main.nodes:
        asset.postprocess(context, inst)
    for asset,inst in main.modifiers:
        asset.postprocess(context, inst)
    for asset,inst in main.modifiers:
        asset.postbuild(context, inst)
    for _,inst in main.nodes:
        inst.buildInstance(context)
    for _,inst in main.nodes:
        inst.finalize(context)

    if LS.render:
        LS.render.build(context)

    from .node import transformDuplis
    transformDuplis()

    if (LS.useMaterials and
        GS.viewportColors != 'WHITE'):
        for asset in main.materials:
            asset.guessColor()

    if GS.useDump:
        from .error import dumpErrors
        dumpErrors(filepath)
    finishMain("File", filepath, t1)

    msg = None
    if LS.missingAssets:
        msg = ("Some assets were not found.\n" +
               "Check that all Daz paths have been set up correctly.        \n" +
               "For details see\n'%s'" % getErrorPath())
    elif LS.hdfailures:
        msg = ("Could not rebuild subdivisions for the following HD objects:       \n")
        for hdname in LS.hdfailures:
            msg += ("  %s\n" % hdname)
    if msg:
        clearErrorMessage()
        handleDazError(context, warning=True, dump=True)
        print(msg)
        raise DazError(msg, warning=True)

    from .material import checkRenderSettings
    msg = checkRenderSettings(context, False)
    if msg:
        raise DazError(msg, warning=True)


def makeRootCollection(grpname, context):
    root = makeNewCollection(grpname)
    if bpy.app.version >= (2,80,0):
        context.scene.collection.children.link(root)
    return root


def finishMain(entity, filepath, t1):
    import time
    from .asset import clearAssets

    t2 = time.perf_counter()
    print('%s "%s" loaded in %.3f seconds' % (entity, filepath, t2-t1))
    clearAssets()

#------------------------------------------------------------------
#   Decode file
#------------------------------------------------------------------

class DAZ_OT_DecodeFile(DazOperator, B.DazFile, B.SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf, *.dbz) to a text file"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        import gzip
        from .asset import getDazPath
        from .fileutils import safeOpen

        print("Decode",  self.filepath)
        try:
            with gzip.open(self.filepath, 'rb') as fp:
                bytes = fp.read()
        except IOError as err:
            msg = ("Cannot decode:\n%s" % self.filepath +
                   "Error: %s" % err)
            print(msg)
            raise DazError(msg)

        try:
            string = bytes.decode("utf_8_sig")
        except UnicodeDecodeError as err:
            msg = ('Unicode error while reading zipped file\n"%s"\n%s' % (self.filepath, err))
            print(msg)
            raise DazError(msg)

        newfile = self.filepath + ".txt"
        with safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_DecodeFile,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
