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
import json
import gzip
import copy
from .error import reportError
from .utils import *

#-------------------------------------------------------------
#   Accessor base class
#-------------------------------------------------------------

class Accessor:
    def __init__(self, fileref):
        self.fileref = fileref
        self.caller = None
        self.rna = None


    def getRna(self, context):
        return self.rna
        global theRnas
        if self.rna is None:
            if self.name in theRnas.keys():
                return theRnas[self.name]
            else:
                print("Did not find RNA", self.name)
        return self.rna


    def storeRna(self, rna):
        global theRnas
        theRnas[self.name] = rna


    def getAsset(self, id, strict=True):
        global theAssets, theOtherAssets

        if isinstance(id, Asset):
            return id

        id = normalizeRef(id)
        if "?" in id:
            # Attribute. Return None
            return None
        ref = getRef(id, self.fileref)
        try:
            return theAssets[ref]
        except KeyError:
            pass

        if id[0] == "#":
            if self.caller:
                ref = getRef(id, self.caller.fileref)
                try:
                    return theAssets[ref]
                except KeyError:
                    pass
            ref = getRef(id, self.fileref)
            try:
                return theAssets[ref]
            except KeyError:
                pass
            try:
                return theOtherAssets[ref]
            except KeyError:
                pass
            msg = ("Missing local asset:\n  '%s'\n" % ref)
            if self.caller:
                msg += ("in file:\n  '%s'\n" % self.caller.fileref)
            if not strict:
                return None
            reportError(msg, trigger=(2,3))
            return None
        else:
            return self.getNewAsset(id, ref, strict)


    def getNewAsset(self, id, ref, strict=True):
        from .files import parseAssetFile
        from .load_json import loadJson

        fileref = id.split("#")[0]
        filepath = getDazPath(fileref)
        file = None
        if filepath:
            struct = loadJson(filepath)
            file = parseAssetFile(struct, fileref=fileref)
            try:
                return theAssets[ref]
            except KeyError:
                pass
        else:
            msg = ("Cannot open file:\n '%s'            " % unquote(fileref))
            reportError(msg, warnPaths=True, trigger=(3,4))
            return None

        LS.missingAssets[ref] = True
        if strict and LS.useStrict:
            msg =("Missing asset:\n  '%s'\n" % ref +
                  "Fileref\n   %s\n" % fileref +
                  "Filepath:\n  '%s'\n" % filepath +
                  "File asset:\n  %s\n" % file )
            reportError(msg, warnPaths=True, trigger=(3,4))
        return None


    def getOldAsset(self, id):
        global theAssets
        ref = getRef(id, self.fileref)
        try:
            return theAssets[ref]
        except KeyError:
            pass
        return self.getNewAsset(id, ref)


    def getTypedAsset(self, id, type):
        asset = self.getAsset(id)
        if (asset is None or
            type is None or
            isinstance(asset,type)):
            return asset
        msg = (
            "Asset of type %s not found:\n  %s\n" % (type, id) +
            "File ref:\n  '%s'\n" % self.fileref
        )
        return reportError(msg, warnPaths=True)


    def parseUrlAsset(self, struct, type=None):
        if "url" not in struct.keys():
            msg = ("URL asset failure: No URL.\n" +
                   "Type: %s\n" % type +
                   "File ref:\n  '%s'\n" % self.fileref +
                   "Id: '%s'\n" % struct["id"] +
                   "Keys:\n %s\n" % list(struct.keys()))
            reportError(msg, warnPaths=True, trigger=(2,3))
            return None
        asset = self.getTypedAsset(struct["url"], type)
        if isinstance(asset, Asset):
            asset.caller = self
            asset.update(struct)
            self.saveAsset(struct, asset)
            return asset
        elif asset is not None:
            msg = ("Empty asset:\n  %s   " % struct["url"])
            return reportError(msg, warnPaths=True)
        else:
            asset = self.getAsset(struct["url"])
            msg = ("URL asset failure:\n" +
                   "URL: '%s'\n" % struct["url"] +
                   "Type: %s\n" % type +
                   "File ref:\n  '%s'\n" % self.fileref +
                   "Found asset:\n %s\n" % asset)
            return reportError(msg, warnPaths=True, trigger=(3,4))
        return None


    def saveAsset(self, struct, asset):
        global theAssets
        ref = ref2 = normalizeRef(asset.id)
        if self.caller:
            if "id" in struct.keys():
                ref = getId(struct["id"], self.caller.fileref)
            else:
                print("No id", struct.keys())

        try:
            asset2 = theAssets[ref]
        except KeyError:
            asset2 = None

        if asset2 and asset2 != asset:
            msg = ("Duplicate asset definition\n" +
                   "  Asset 1: %s\n" % asset +
                   "  Asset 2: %s\n" % asset2 +
                   "  Ref 1: %s\n" % ref +
                   "  Ref 2: %s\n" % ref2)
            reportError(msg, trigger=(2,4))
            theAssets[ref2] = asset
        else:
            theAssets[ref] = theAssets[ref2] = asset
        return

        if asset.caller:
            ref2 = lowerPath(asset.caller.id) + "#" + struct["id"]
            ref2 = normalizeRef(ref2)
            if ref2 in theAssets.keys():
                asset2 = theAssets[ref2]
                if asset != asset2 and GS.verbosity > 1:
                    msg = ("Duplicate asset definition\n" +
                           "  Asset 1: %s\n" % asset +
                           "  Asset 2: %s\n" % asset2 +
                           "  Caller: %s\n" % asset.caller +
                           "  Ref 1: %s\n" % ref +
                           "  Ref 2: %s\n" % ref2)
                    return reportError(msg, trigger=(2,3))
            else:
                print("REF2", ref2)
                print("  ", asset)
                theAssets[ref2] = asset

#-------------------------------------------------------------
#   Asset base class
#-------------------------------------------------------------

class Asset(Accessor):
    def __init__(self, fileref):
        Accessor.__init__(self, fileref)
        self.id = None
        self.url = None
        self.name = None
        self.label = None
        self.type = None
        self.visible = True
        self.parent = None
        self.children = []
        self.source = None
        self.sourcing = None
        self.drivable = True


    def __repr__(self):
        return ("<Asset %s t: %s r: %s>" % (self.id, self.type, self.rna))


    def selfref(self):
        return ("#" + self.id.rsplit("#", 2)[-1])


    def getLabel(self, inst=None):
        if inst and inst.label:
            return inst.label
        elif self.label:
            return self.label
        else:
            return self.name


    def getName(self):
        if self.id is None:
            return "None"
        else:
            return unquote(self.id.rsplit("#",1)[-1])


    def copySource(self, asset):
        for key in dir(asset):
            if hasattr(self, key) and key[0] != "_":
                attr = getattr(self, key)
                try:
                    setattr(asset, key, attr)
                except RuntimeError:
                    pass


    def copySourceFile(self, source):
        global theAssets, theSources
        file = source.rsplit("#", 1)[0]
        asset = self.parseUrlAsset({"url": source})
        if asset is None:
            return None
        old = asset.id.rsplit("#", 1)[0]
        new = self.id.rsplit("#", 1)[0]
        self.copySourceAssets(old, new)
        if old not in theSources.keys():
            theSources[old] = []
        for other in theSources[old]:
            self.copySourceAssets(other, new)
        theSources[old].append(new)
        return asset


    def copySourceAssets(self, old, new):
        nold = len(old)
        nnew = len(new)
        adds = []
        assets = []
        for key,asset in theAssets.items():
            if key[0:nold] == old:
                adds.append((new + key[nold:], asset))
        for key,asset in adds:
            if key not in theOtherAssets.keys():
                theOtherAssets[key] = asset
                assets.append(asset)


    def parse(self, struct):
        if "id" in struct.keys():
            self.id = getId(struct["id"], self.fileref)
        else:
            self.id = "?"
            msg = ("Asset without id\nin file \"%s\":\n%s    " % (self.fileref, struct))
            reportError(msg, trigger=(1,2))

        if "url" in struct.keys():
            self.url = struct["url"]
        elif "id" in struct.keys():
            self.url = struct["id"]

        if "type" in struct.keys():
            self.type = struct["type"]

        if "name" in struct.keys():
            self.name = struct["name"]
        elif "id" in struct.keys():
            self.name = struct["id"]
        elif self.url:
            self.name = self.url
        else:
            self.name = "Noname"

        if "label" in struct.keys():
            self.label = struct["label"]

        if "channel" in struct.keys():
            for key,value in struct["channel"].items():
                if key == "visible":
                    self.visible = value
                elif key == "label":
                    self.label = value

        if "parent" in struct.keys():
            self.parent = self.getAsset(struct["parent"])
            if self.parent:
                self.parent.children.append(self)

        if "source" in struct.keys():
            self.parseSource(struct["source"])
        return self


    def parseSource(self, url):
        asset = self.getAsset(url)
        if asset:
            if self.type == asset.type:
                self.source = asset
                asset.sourcing = self
                theAssets[url] = self
            else:
                msg = ("Source type mismatch:   \n" +
                       "%s != %s\n" % (asset.type, self.type) +
                       "URL: %s           \n" % url +
                       "Asset: %s\n" % self +
                       "Source: %s\n" % asset)
                reportError(msg, trigger=(2,3))


    def update(self, struct):
        for key,value in struct.items():
            if key == "type":
                self.type = value
            elif key == "name":
                self.name = value
            elif key == "url":
                self.url = value
            elif key == "label":
                self.label = value
            elif key == "parent":
                if self.parent is None and self.caller:
                    self.parent = self.caller.getAsset(struct["parent"])
            elif key == "channel":
                self.value = getCurrentValue(value)
        return self


    def build(self, context, inst=None):
        return
        raise NotImplementedError("Cannot build %s yet" % self.type)


    def buildData(self, context, inst, center):
        print("BDATA", self)
        if self.rna is None:
            self.build(context)


    def postprocess(self, context, inst):
        return

    def connect(self, struct):
        pass


def getAssetFromStruct(struct, fileref):
    id = getId(struct["id"], fileref)
    try:
        return theAssets[id]
    except KeyError:
        return None


def getExistingFile(fileref):
    global theAssets
    ref = normalizeRef(fileref)
    if ref in theAssets.keys():
        #print("Reread", fileref, ref)
        return theAssets[ref]
    else:
        return None

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def storeAsset(asset, url):
    global theAssets
    theAssets[url] = asset


def getAssets():
    global theAssets
    return theAssets


def getId(id0, fileref):
    id = normalizeRef(id0)
    if len(id) == 0:
        print("Asset with no id in %s" % fileref)
        return fileref + "#"
    elif id[0] == "/":
        return id
    else:
        return fileref + "#" + id


def getRef(id, fileref):
    id = normalizeRef(id)
    if id[0] == "#":
        return fileref + id
    else:
        return id


def lowerPath(path):
    #return path
    if len(path) > 0 and path[0] == "/":
        words = path.split("#",1)
        if len(words) == 1:
            return tolower(words[0])
        else:
            return tolower(words[0]) + "#" + words[1]
    else:
        return path


def normalizeRef(id):
    from urllib.parse import quote
    ref= lowerPath(undoQuote(quote(id)))
    return ref.replace("//", "/")

def undoQuote(ref):
    ref = ref.replace("%23","#").replace("%25","%").replace("%2D", "-").replace("%2E", ".").replace("%2F", "/").replace("%3F", "?")
    return ref.replace("%5C", "/").replace("%5F", "_").replace("%7C", "|")


def clearAssets():
    global theAssets, theOtherAssets, theSources, theRnas
    theAssets = {}
    theOtherAssets = {}
    theSources = {}
    theRnas = {}

clearAssets()

#-------------------------------------------------------------
#   Paths
#-------------------------------------------------------------

def setDazPaths(scn):
    from .error import DazError
    global theDazPaths
    filepaths = []
    for path in GS.getDazPaths():
        if path:
            if not os.path.exists(path):
                msg = ("The DAZ library path\n" +
                       "%s          \n" % path +
                       "does not exist. Check and correct the\n" +
                       "Paths to DAZ library section in the Settings panel." +
                       "For more details see\n" +
                       "http://diffeomorphic.blogspot.se/p/settings-panel_17.html.       ")
                print(msg)
                raise DazError(msg)
            else:
                filepaths.append(path)
                if os.path.isdir(path):
                    for fname in os.listdir(path):
                        if "." not in fname:
                            numname = "".join(fname.split("_"))
                            if numname.isdigit():
                                subpath = path + "/" + fname
                                filepaths.append(subpath)
    theDazPaths = filepaths


def fixBrokenPath(path):
    """
    many asset file paths assume a case insensitive file system, try to fix here
    :param path:
    :return:
    """
    path_components = []
    head = path
    while True:
        head, tail = os.path.split(head)
        if tail != "":
            path_components.append(tail)
        else:
            if head != "":
                path_components.append(head)
            path_components.reverse()
            break

    check = path_components[0]
    for pc in path_components[1:]:
        if not os.path.exists(check):
            return check
        cand = os.path.join(check, pc)
        if not os.path.exists(cand):
            corrected = [f for f in os.listdir(check) if f.lower() == pc.lower()]
            if len(corrected) > 0:
                cand = os.path.join(check, corrected[0])
            else:
                msg = ("Broken path: '%s'\n" % path +
                       "  Folder: '%s'\n" % check +
                       "  File: '%s'\n" % pc +
                       "  Files: %s" % os.listdir(check))
                reportError(msg, trigger=(4,5))
        check = cand

    return check


def getRelativeRef(ref):
    global theDazPaths

    path = unquote(ref)
    for dazpath in theDazPaths:
        n = len(dazpath)
        if path[0:n].lower() == dazpath.lower():
            return ref[n:]
    print("Not a relative path:\n  '%s'" % path)
    return ref


def getDazPath(ref):
    global theDazPaths

    path = unquote(ref)
    filepath = path
    if path[2] == ":":
        filepath = path[1:]
        if GS.verbosity > 2:
            print("Load", filepath)
    elif path[0] == "/":
        for folder in theDazPaths:
            filepath = folder + path
            if os.path.exists(filepath):
                return filepath
            elif GS.caseSensitivePaths:
                filepath = fixBrokenPath(filepath)
                if os.path.exists(filepath):
                    return filepath

    if os.path.exists(filepath):
        if GS.verbosity > 2:
            print("Found", filepath)
        return filepath

    LS.missingAssets[ref] = True
    msg = ("Did not find path:\n\"%s\"\nRef:\"%s\"" % (filepath, ref))
    reportError(msg, trigger=(3,4))
    return None
