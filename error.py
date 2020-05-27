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

def clearErrorMessage():
    global theMessage, theErrorLines
    theMessage = ""
    theErrorLines = []
    
clearErrorMessage()

def getErrorMessage():
    global theMessage
    return theMessage


def getSilentMode():
    global theSilentMode
    return theSilentMode

def setSilentMode(value):
    global theSilentMode
    theSilentMode = value

setSilentMode(False)
    

class ErrorOperator(bpy.types.Operator):
    bl_idname = "daz.error"
    bl_label = "Daz Importer"

    def execute(self, context):
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        global theMessage, theErrorLines
        theErrorLines = theMessage.split('\n')
        maxlen = len(self.bl_label)
        for line in theErrorLines:
            if len(line) > maxlen:
                maxlen = len(line)
        width = 20+5*maxlen
        height = 20+5*len(theErrorLines)
        #self.report({'INFO'}, theMessage)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width)

    def draw(self, context):
        global theErrorLines
        for line in theErrorLines:
            self.layout.label(text=line)


def invokeErrorMessage(value, warning=False):       
    global theMessage
    if warning:
        theMessage = "WARNING:\n" + value
    else:
        theMessage = "ERROR:\n" + value
    if getSilentMode():
        print(theMessage)
    else:
        bpy.ops.daz.error('INVOKE_DEFAULT')


class DazError(Exception):

    def __init__(self, value, warning=False):
        invokeErrorMessage(value, warning)

    def __str__(self):
        global theMessage
        return repr(theMessage)


def reportError(msg, instances={}, warnPaths=False, trigger=(2,3), force=False):
    global theUseDumpErrors, theInstances
    from .settings import theSettings
    trigWarning,trigError = trigger
    if theSettings.verbosity >= trigWarning or force:
        print(msg)
    if theSettings.verbosity >= trigError or force:
        theUseDumpErrors = True
        theInstances = instances
        if warnPaths:
            msg += ("\nHave all DAZ library paths been set up correctly?\n" +
                    "See https://diffeomorphic.blogspot.se/p/setting-up-daz-library-paths.html         ")
        msg += ("\nFor details see\n'%s'" % getErrorPath())
        raise DazError(msg)
    return None


def getErrorPath():
    import os
    from .settings import theSettings
    return os.path.realpath(os.path.expanduser(theSettings.errorPath))


def handleDazError(context, warning=False, dump=False):
    global theMessage, theUseDumpErrors

    if not (dump or theUseDumpErrors):
        return
    theUseDumpErrors = False

    filepath = getErrorPath()
    try:
        fp = open(filepath, "w", encoding="utf_8")
    except:
        print("Could not write to %s" % filepath)
        return
    fp.write(theMessage)

    try:
        if warning:
            string = getMissingAssets()
            fp.write(string)
            print(string)
        else:
            printTraceBack(context, fp)
    except:
        pass
    finally:
        fp.write("\n")
        fp.close()
        print(theMessage)


def getMissingAssets():
    from .settings import theSettings
    if not theSettings.missingAssets:
        return ""
    string = "\nMISSING ASSETS:\n"
    for ref in theSettings.missingAssets:
        string += ("  %s\n" % ref)
    return string
        
        
def printTraceBack(context, fp):
    global theInstances      

    import sys, traceback
    type,value,tb = sys.exc_info()
    fp.write("\n\nTRACEBACK:\n")
    traceback.print_tb(tb, 30, fp)

    from .settings import theTrace
    from .asset import theAssets, theOtherAssets, theDazPaths

    fp.write("\n\nFILES VISITED:\n")
    for string in theTrace:
        fp.write("  %s\n" % string)

    fp.write("\nINSTANCES:\n")
    refs = list(theInstances.keys())
    refs.sort()
    for ref in refs:
        fp.write('"%s":    %s\n' % (ref, theInstances[ref]))

    fp.write("\nASSETS:\n")
    refs = list(theAssets.keys())
    refs.sort()
    for ref in refs:
        fp.write('"%s"\n    %s\n\n' % (ref, theAssets[ref]))

    fp.write("\nOTHER ASSETS:\n")
    refs = list(theOtherAssets.keys())
    refs.sort()
    for ref in refs:
        fp.write('"%s"\n    %s\n\n' % (ref, theOtherAssets[ref]))

    fp.write("\nDAZ ROOT PATHS:\n")
    for n, path in enumerate(theDazPaths):
        fp.write('%d:   "%s"\n' % (n, path))

    string = getMissingAssets()
    fp.write(string)
    
    fp.write("\nSETTINGS:\n")
    settings = []
    scn = bpy.context.scene
    for attr in dir(scn):
        if attr[0:3] == "Daz":
            value = getattr(scn, attr)
            if (isinstance(value, int) or
                isinstance(value, float) or
                isinstance(value, str) or
                isinstance(value, bool)):
                settings.append((attr, value))
    settings.sort()
    for attr,value in settings:
        if isinstance(value, str):
            value = ('"%s"' % value)
        fp.write('%25s:    %s\n' % (attr, value))


theUseDumpErrors = False

#-------------------------------------------------------------
#   Execute
#-------------------------------------------------------------

class DazOperator(bpy.types.Operator):
    def execute(self, context):
        clearErrorMessage()
        try:
            self.run(context)
        except DazError:
            handleDazError(context)
        except KeyboardInterrupt:
            global theMessage
            theMessage = "Keyboard interrupt"
            bpy.ops.daz.error('INVOKE_DEFAULT')            
        finally:
            wm = bpy.context.window_manager
            wm.progress_end()            
        return{'FINISHED'}    

class DazPropsOperator(DazOperator):
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

class IsObject:
    @classmethod
    def poll(self, context):
        return context.object

class IsMesh:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

class IsArmature:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

class IsMeshArmature:
    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])

