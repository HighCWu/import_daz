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


import copy
from .error import reportError
from .utils import *

#-------------------------------------------------------------
#   Channels class
#-------------------------------------------------------------

class Channels:
    def __init__(self):
        self.channels = {}
        self.extra = []


    def parse(self, struct):
        if "url" in struct.keys():
            asset = self.getAsset(struct["url"])
            if asset:
                self.channels = copy.deepcopy(asset.channels)
        for key,data in struct.items():
            if key == "extra":
                self.extra = data
                for extra in data:
                    self.setExtra(extra)
                    if "channels" in extra.keys():
                        for data in extra["channels"]:
                            self.setChannel(data["channel"])
            elif isinstance(data, dict):
                if "channel" in data.keys():
                    self.setChannel(data["channel"])


    def setChannel(self, channel):                
        if ("visible" in channel.keys() and not channel["visible"]):
            return
        self.channels[channel["id"]] = channel
        if False and "label" in channel.keys():
            self.channels[channel["label"]] = channel


    def update(self, struct):
        for key,data in struct.items():
            if key == "extra":
                self.extra = data
                for extra in data:
                    self.setExtra(extra)
                    if "channels" in extra.keys():
                        for data in extra["channels"]:
                            self.replaceChannel(data["channel"])
            elif isinstance(data, dict):
                if "channel" in data.keys():
                    self.replaceChannel(data["channel"])        


    def setExtra(self, struct):
        pass
        

    def replaceChannel(self, channel, key=None):
        if ("visible" in channel.keys() and not channel["visible"]):
            return
        if key is None:
            key = channel["id"]        
        if key in self.channels.keys():
            oldchannel = self.channels[key]
            self.channels[key] = channel
            for name,value in oldchannel.items():
                if name not in channel.keys():
                    channel[name] = value
        else:
            self.channels[key] = copy.deepcopy(channel)
        if False and "label" in channel.keys():
            self.channels[channel["label"]] = self.channels[key]


    def getChannel(self, attr):
        if isinstance(attr, str):
            return getattr(self, attr)()
        for key in attr:
            if key in self.channels.keys():
                channel = self.channels[key]
                if ("visible" not in channel.keys() or
                    channel["visible"]):
                    return channel
        return None
                            

    def equalChannels(self, other):
        for key,value in self.channels.items():
            if (key not in other.channels.keys() or
                other.channels[key] != value):
                return False
        return True

          

