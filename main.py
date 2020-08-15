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

    print("Parsing data")
    from .files import parseAssetFile
    main = parseAssetFile(struct, toplevel=True)
    if main is None:
        msg = ("File not found:  \n%s      " % filepath)
        raise DazError(msg)
    showProgress(20, 100)

    if LS.fitFile:
        fitToFile(filepath, main.nodes)
    showProgress(30, 100)

    print("Preprocessing...")
    LS.collection = makeRootCollection(filepath, context)
    for asset,inst in main.nodes:
        inst.preprocess(context)

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

    for asset,inst in main.nodes:
        asset.postbuild(context, inst)
    # Need to update scene before calculating object areas
    updateScene(context)
    for asset in main.materials:
        asset.postbuild(context)

    print("Postprocessing...")
    for asset,inst in main.nodes:
        asset.postprocess(context, inst)
    for asset,inst in main.modifiers:
        asset.postprocess(context, inst)
    for _,inst in main.nodes:
        inst.pose(context)
    for asset,inst in main.modifiers:
        asset.postbuild(context, inst)
    for _,inst in main.nodes:
        inst.finalize(context)

    for extra in main.extras:
        if extra:
            extra.build(context)

    if (LS.useMaterials and
        GS.chooseColors != 'WHITE'):
        for asset,inst in main.nodes:
            asset.guessColor(scn, GS.chooseColors, inst)

    finishMain("File", filepath, t1)
    if LS.missingAssets:
        clearErrorMessage()
        handleDazError(context, warning=True, dump=True)
        msg = ("Some assets were not found.\n" +
               "Check that all Daz paths have been set up correctly.        \n" +
               "For details see\n'%s'" % getErrorPath())
        print(msg)
        raise DazError(msg, warning=True)

    from .material import checkRenderSettings
    msg = checkRenderSettings(context, False)
    if msg:
        raise DazError(msg, warning=True)


def makeRootCollection(filepath, context):
    grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
    if bpy.app.version < (2,80,0):
        root = bpy.data.groups.new(name=grpname)
    else:
        root = bpy.data.collections.new(name=grpname)
        context.scene.collection.children.link(root)
    return root


def finishMain(entity, filepath, t1):
    import time
    from .asset import clearAssets

    t2 = time.perf_counter()
    print('%s "%s" loaded in %.3f seconds' % (entity, filepath, t2-t1))
    clearAssets()

#------------------------------------------------------------------
#   Reparent extra bones
#------------------------------------------------------------------

class DAZ_OT_ReparentBones(DazOperator):
    bl_idname = "daz.reparent_bones"
    bl_label = "Reparent Bones"
    bl_description = "Reparent selected bones to active"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        par = rig.data.edit_bones.active
        for eb in rig.data.edit_bones:
            if eb.select and eb != par:
                eb.parent = par

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
        string = bytes.decode("utf_8_sig")
        newfile = self.filepath + ".txt"
        with safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ReparentBones,
    DAZ_OT_DecodeFile,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
