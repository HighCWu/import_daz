# Copyright (c) 2016-2021, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
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

#----------------------------------------------------------
#   Api functions available for external scripting
#----------------------------------------------------------

def get_error_message():
    """get_error_message()

    Get the current error message.

    Returns:
    The error message from previous operator invokation if it raised
    an error, or the empty string if the operator exited without errors.
    """
    from .error import theMessage
    return theMessage


def get_silent_mode():
    global theSilentMode
    return theSilentMode


def set_silent_mode(value):
    """set_silent_mode(value)

    In silent mode, operators fail silently if they encounters an error.
    This is useful for scripting.

    Arguments:
    ?value: True turns silent mode on, False turns it off.
    """
    global theSilentMode
    theSilentMode = value

set_silent_mode(False)


def get_morphs(ob, morphset, category=None, activeOnly=False):
    """get_morphs(ob, type, category=None, activeOnly=False)
    Get all morph names and values of the specified type from the object.

    Returns:
    A dictonary of morph names - morph values for all morphs in the specified morphsets.

    Arguments:
    ?ob: Object (armature or mesh) which owns the morphs

    ?type: Either a string in ["Units", "Expressions", "Visemes", "Facs", "Facsexpr", "Body", "Custom", "Jcms", "Flexions"],
        or a list of such strings, or the keyword "All" signifying all morphset in the list.

    ?category (optional): The category name for Custom morphs.

    ?activeOnly (optional): Active morphs only (default False).
    """
    from .morphing import getMorphsExternal
    getMorphsExternal(ob, morphset, category, activeOnly)

#-------------------------------------------------------------
#   Active file paths used from python
#-------------------------------------------------------------

def clear_selection():
    """get_selection()

    Clear the active file selection to be loaded by consecutive operators.
    """
    global theFilePaths
    theFilePaths = []
    print("File paths cleared")


def get_selection():
    """get_selection()

    Get the active file selection to be loaded by consecutive operators.

    Returns:
    The active list of file paths (strings).
    """
    global theFilePaths
    return theFilePaths


def set_selection(files):
    """set_selection(files)

    Set the active file selection to be loaded by consecutive operators.

    Arguments:
    ?files: A list of file paths (strings).
    """
    global theFilePaths
    if isinstance(files, list):
        theFilePaths = files
    else:
        raise DazError("File paths must be a list of strings")

clear_selection()

#-------------------------------------------------------------
#   Paths used by Xin's HD-morphs add-on
#-------------------------------------------------------------

def get_default_morph_directories(ob):
    from .fileutils import getFolders
    return getFolders(ob, ["Morphs/"])

def get_dhdm_files(ob=None):
    from .hdmorphs import getHDFiles
    return getHDFiles(ob, "DazDhdmFiles")

def get_morph_files(ob=None):
    from .hdmorphs import getHDFiles
    return getHDFiles(ob, "DazMorphFiles")

def get_dhdm_directories(ob=None):
    from .hdmorphs import getHDFiles
    return getHDDirs(ob, "DazDhdmFiles")

def get_morph_directories(ob=None):
    from .hdmorphs import getHDFiles
    return getHDDirs(ob, "DazMorphFiles")

