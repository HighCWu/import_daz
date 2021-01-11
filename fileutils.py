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
import os
from bpy.props import *
from .error import *
from .utils import B

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

def safeOpen(filepath, rw, dirMustExist=False, fileMustExist=False, mustOpen=False):
    if dirMustExist:
        folder = os.path.dirname(filepath)
        if not os.path.exists(folder):
            msg = ("Directory does not exist:      \n" +
                   "%s          " % folder)
            raise DazError(msg)

    if fileMustExist:
        if not os.path.exists(filepath):
            msg = ("File does not exist:      \n" +
                   "%s          " % filepath)
            raise DazError(msg)

    if rw == "w":
        encoding="utf_8"
    else:
        encoding="utf_8_sig"
    try:
        fp = open(filepath, rw, encoding=encoding)
    except FileNotFoundError:
        fp = None

    if fp is None:
        if rw[0] == "r":
            mode = "reading"
        else:
            mode = "writing"
        msg = ("Could not open file for %s:   \n" % mode +
               "%s          " % filepath)
        if mustOpen:
            raise DazError(msg)
        reportError(msg, warnPaths=True, trigger=(2,4))
    return fp

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

def getFolder(ob, scn, subdirs):
    from .asset import getDazPath, setDazPaths
    setDazPaths(scn)
    if ob is None:
        return None
    fileref = ob.DazUrl.split("#")[0]
    if len(fileref) < 2:
        return None
    folder = os.path.dirname(fileref)
    basedir = getDazPath(folder)
    if basedir is None:
        return None
    for subdir in subdirs:
        folder = os.path.join(basedir, subdir)
        if os.path.exists(folder):
            return folder
    return None


"""
import winreg

def subkeys(key):
    i = 0
    while True:
        try:
            subkey = winreg.EnumKey(key, i)
            yield subkey
            i+=1
        except WindowsError as e:
            break

def traverse_registry_tree(fp, hkey, keypath, tabs=0):
    try:
        key = winreg.OpenKey(hkey, keypath, 0, winreg.KEY_READ)
    except PermissionError:
        return
    for subkeyname in subkeys(key):
        fp.write("  "*tabs + subkeyname + "\n")
        subkeypath = "%s\\%s" % (keypath, subkeyname)
        traverse_registry_tree(fp, hkey, subkeypath, tabs+1)

keypath = r"SOFTWARE\\Microsoft\\Windows"

with safeOpen("/home/hkeys.txt", "w") as fp:
    traverse_registry_tree(fp, winreg.HKEY_LOCAL_MACHINE, keypath)
"""

#-------------------------------------------------------------
#   Active file paths used from python
#-------------------------------------------------------------

def clearSelection():
    """getSelection()

    Clear the active file selection to be loaded by consecutive operators.
    """
    global theFilePaths
    theFilePaths = []
    print("File paths cleared")

def getSelection():
    """getSelection()

    Get the active file selection to be loaded by consecutive operators.

    Returns:
    The active list of file paths (strings).
    """
    global theFilePaths
    return theFilePaths

def setSelection(files):
    """setSelection(files)

    Set the active file selection to be loaded by consecutive operators.

    Arguments:
    ?files: A list of file paths (strings).
    """
    global theFilePaths
    if isinstance(files, list):
        theFilePaths = files
    else:
        raise DazError("File paths must be a list of strings")

clearSelection()

#-------------------------------------------------------------
#   Multifiles
#-------------------------------------------------------------

class MultiFile(B.MultiFile):
    def invoke(self, context, event):
        clearSelection()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def getMultiFiles(self, extensions):
    paths = getSelection()
    if paths:
        return paths
    paths = []
    for file_elem in self.files:
        filepath = os.path.join(self.directory, file_elem.name)
        if os.path.isfile(filepath):
            path = getTypedFilePath(filepath, extensions)
            if path:
                paths.append(path)
    return paths


def getTypedFilePath(filepath, exts):
    words = os.path.splitext(filepath)
    if len(words) == 2:
        fname,ext = words
    else:
        return None
    if fname[-4:] == ".tip":
        fname = fname[:-4]
    if ext in [".png", ".jpeg", ".jpg", ".bmp"]:
        if os.path.exists(fname):
            words = os.path.splitext(fname)
            if (len(words) == 2 and
                words[1][1:] in exts):
                return fname
        for ext1 in exts:
            path = fname+"."+ext1
            if os.path.exists(path):
                return path
        return None
    elif ext[1:].lower() in exts:
        return filepath
    else:
        return None
