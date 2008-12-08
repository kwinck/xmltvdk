#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# $Id$
# 
# Copyright (c) 2008, Jonas Häggqvist
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of the program nor the names of its contributors may be
#   used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

class SimpleXMLWriter():
    """
    This class will write XML directly to an output file object while
    storing as little as possible in memory. There is very little error
    checking going on! You're expected to make sure the output is
    correct XML.

    Attribute keys, values and text content is quoted:
    & => &amp;
    " => &quot;
    < => &lt;
    > => &gt;
    """
    __pos = []
    __emptyElement = True

    def __init__(self, output, indent = 4):
        """
        Constructor - output must be a file-like object. At the very
        least it must have write(). Indent is the number of spaces
        per indentation-level.
        """
        self.__output = output
        self.indent = indent
        self.__write('<?xml version="1.0" encoding="UTF-8" ?>\n')

    def __write(self, string):
        self.__output.write(string)

    def __quote(self, string):
        return string.replace("&", "&amp;").replace('"', '&quot;').replace("<", '&lt;').replace(">", '&gt;')

    def __indent(self, level = 0):
        level += len(self.__pos)
        return " "*level*self.indent

    def closeAll(self):
        """
        Close all open elements until there are no elements open.
        """
        while len(self.__pos) > 0:
            self.closeElement()

    def createElement(self, name, attrs = {}):
        """
        Open a new element of the given name - you can optionally pass a dict
        of attributes to set in {key=val} format.
        """
        if len(self.__pos) > 0 and self.__emptyElement:
            self.__write(">\n")
        self.__write("%s<%s" % (self.__indent(), name))
        self.__emptyElement = True
        self.__pos.append(name)
        self.setAttributes(attrs)
        return self

    def setAttributes(self, attrs):
        """
        Set many attributes quickly, pass a dict.
        """
        for key in attrs:
            self.setAttribute(key, attrs[key])

    def setAttribute(self, key, val):
        """
        Set a single attribute of the current element.
        """
        if self.__emptyElement and len(self.__pos) > 0:
            self.__write(' %s="%s"' % (self.__quote(key), self.__quote(val)))
        elif len(self.__pos) == 0:
            raise UserWarning("Can't add attributes when there's no open elements")
        else:
            raise UserWarning("Can't add attributes to element after text content")

    def addText(self, text):
        """
        Add some text to the currently open element.
        """
        if self.__emptyElement and len(self.__pos) > 0:
            self.__write(">\n")
            self.__emptyElement = False
        elif len(self.__pos) == 0:
            raise UserWarning("Can't add text when there's no open elements")
            return False
        self.__write("%s%s\n"  % (self.__indent(), self.__quote(text)))

    def closeElement(self, name = None):
        """
        Close the currently open element. If you pass a name, I'll check
        that it's the right one that's being closed.
        """
        if name != None and name != self.__pos[-1]:
            raise UserWarning("Unmatched closing element %s (expected %s)" % (name, self.__pos[-1]))
        if self.__emptyElement:
            self.__write("/>\n")
        else:
            self.__write("%s</%s>\n" % (self.__indent(-1), self.__pos[-1]))
        self.__pos = self.__pos[0:-1]
        self.__emptyElement = False

    def appendChild(self, elm):
        """
        This is only here to mimic xlm.dom.minidom (badly). It simply calls
        closeElement().
        """
        self.closeElement()
