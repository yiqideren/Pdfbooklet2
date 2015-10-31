#!/usr/bin/python

#
# PdfBooklet 2.3.0 - GTK+ based utility to create booklets and other layouts 
# from PDF documents.
# Copyright (C) 2008-2012 GAF Software
# <https://sourceforge.net/projects/pdfbooklet>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import os
import re
import glob

version = "2.3.2"
os.system('sudo python setup.py bdist')
os.system('sudo python setup.py sdist')
os.system('sudo python setup.py bdist_rpm')

new_file = "./dist/pdfBooklet-" + version + "-1.noarch.rpm"
new_dir = "./pdfBooklet-" + version + "/"
if os.path.isfile(new_file) :
  print "found"

# generate Debian package
os.system('sudo alien --generate --scripts ' + new_file)
control_file = "./pdfBooklet-" + version + "/debian/control"
if os.path.isfile(control_file) :
  print "control found"

f1 = open(control_file, "r")

data1 = f1.read()
data1 = data1.replace("${shlibs:Depends}", "pygtk2|python-gtk2, pypoppler|python-poppler")
f1.close()
f1 = open(control_file, "w")
f1.write(data1)
f1.close()

os.system("cd " + new_dir + "; sudo dpkg-buildpackage")
  





#os.system('rpmrebuild -b -R --change-spec-requires rebuild.py -p ' + new_file )


"""
# Clean up temporary files
if os.path.isdir('mo/'):
    os.system ('rm -r mo/')
if os.path.isdir('build/'):
    os.system ('rm -r build/')
"""
