#!/usr/bin/python
# coding: utf-8 -*-

# version 2.3.4;  19 / 10 / 2016
# Revision 1  (bug fix for xCopies in layout)



PB_version = "2.3.4"


"""
website : pdfbooklet.sourceforge.net

This software is a computer program whose purpose is to manipulate pdf files.

This software is governed by the CeCILL license under French law and
abiding by the rules of distribution of free software.  You can  use,
modify and/ or redistribute the software under the terms of the CeCILL
license as circulated by CEA, CNRS and INRIA at the following URL
"http://www.cecill.info".

As a counterpart to the access to the source code and  rights to copy,
modify and redistribute granted by the license, users are provided only
with a limited warranty  and the software's author,  the holder of the
economic rights,  and the successive licensors  have only  limited
liability.

In this respect, the user's attention is drawn to the risks associated
with loading,  using,  modifying and/or developing or reproducing the
software by the user in light of its specific status of free software,
that may mean  that it is complicated to manipulate,  and  that  also
therefore means  that it is reserved for developers  and  experienced
professionals having in-depth computer knowledge. Users are therefore
encouraged to load and test the software's suitability as regards their
requirements in conditions enabling the security of their systems and/or
data to be ensured and,  more generally, to use and operate it in the
same conditions as regards security.

The fact that you are presently reading this means that you have had
knowledge of the CeCILL license and that you accept its terms.

==========================================================================
"""

"""
TODO :

Autoscale : Distinguer les options : pour les pages et global ? Pas sûr que ce soit utile.
Quand un répertoire est sélectionné, avertir
quand on ouvre un fichier, et puis ensuite un projet qui a plusieurs fichiers, pdfshuffler n'est pas bien mis à jour
popumenu rotate : les valeurs de la fenêtre transformations ne sont pas mises à jour.

bugs
fichier ini : ouvrir un fichier, ouvrir le fichier ini correspondant. Ne rien changer, fermer, le fichier ini est mis à jour à un moment quelconque et souvent toutes les transformations sont remises à zéro.
Dans la même manipulation , quand on ouvre, il arrive que les modifications d'une page soient conservées et pas celle de l'autre page (en cahier)


petits défauts
A propos : le lien vers le site ne marche pas

améliorations
Le tooltip pour le nom de fichier pourrait afficher les valeurs réelles que donneront les différents paramètres

"""

import time, math, ConfigParser, string, os, sys, re, shutil
import StringIO
from collections import defaultdict
import subprocess
from subprocess import Popen, PIPE
from ctypes import *
import threading
import tempfile, cStringIO

from optparse import OptionParser
import traceback

import pygtk
import gtk
import pango
import poppler
import gio          #to inquire mime types information

gtk.rc_parse("./gtkrc")


#from pypdf113_3.pdf import PdfFileReader, PdfFileWriter        Pas bon. Les fichiers ne s'ouvrent pas
#import pypdf113_3.generic as generic

from pypdf113.pdf import PdfFileReader, PdfFileWriter
import pypdf113.generic as generic

from files_chooser import Chooser

import locale       #for multilanguage support
import gettext
import elib_intl
elib_intl.install("pdfbooklet", "share/locale")

debug_b = 0



def writeOption(filename, section, option, value) :
    configtemp = ConfigParser.RawConfigParser()
    configtemp.read(filename)

    if configtemp.has_section(section) == False :
        configtemp.add_section(section)
    configtemp.set(section,option,value)

    f = open(filename,"wb")
    configtemp.write(f)
    f.close()


def join_list(my_list, separator) :
    data = ""
    if isinstance(my_list, list) :
        for s in my_list :
            data += str(s) + separator
    elif isinstance(my_list, dict) :
        for s in my_list :
            data += str(my_list[s]) + separator
    crop = len(separator) * -1
    data = data[0:crop]
    return data

def get_value(dictionary, key, default = 0) :

    if not key in dictionary :
        dictionary[key] = default
        return default
    else :
        return dictionary[key]


def unicode2(string, dummy = "") :
    if isinstance(string,unicode) :
        return string
    else :
        try :
            return unicode(string,"utf_8")
        except :
            try :
#               print string, " est ecrit en cp1252"
                return unicode(string,"cp1252")
            except :
                return string       # Is this the good option ? Return False or an empty string ?
                return u"inconnu"

def printExcept() :
    a,b,c = sys.exc_info()
    for d in traceback.format_exception(a,b,c) :
        print d,

class gtkGui:
    # parameters :
    # render is an instance of pdfRenderer
    # pdfList is a dictionary of path of pdf files : { 1:"...", 2:"...", ... }
    # pageSelection is a list of pages in the form : ["w:x", ... , "y:z"]
    def __init__(self,
                    render,
                    pdfList = None,
                    pageSelection = None):

        global config, rows_i, columns_i, step_i, sections, output, input1, adobe_l, inputFiles_a, inputFile_a
        global numfolio, prependPages, appendPages, ref_page, selection, PSSelection
        global numPages, pagesSel, llx_i, lly_i, urx_i, ury_i, mediabox_l
        global ouputFile, optionsDict, selectedIndex_a, selected_page, deletedIndex_a, app
        elib_intl.install("pdfbooklet", "share/locale")

        if None != pdfList :
            inputFiles_a = pdfList
            self.loadPdfFiles()
        else :
            inputFiles_a = {}
            inputFile_a = {}
        self.permissions_i = -1     # all permissions
        self.password_s = ""
        rows_i = 1
        columns_i = 2
        urx_i = 200
        ury_i = 200
        optionsDict = {}
        adobe_l = 0.3527


        thumbnail = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, 1 , 1)
        areaAllocationH_i = 400
        areaAllocationW_i = 400

        #previewtempfile = tempfile.SpooledTemporaryFile(max_size = 10000000)  # max

        selectedIndex_a = {}
        selected_page = None
        deletedIndex_a = {}


        app = self
        self.render = render
        self.ar_pages = []
        self.ar_layout = []
        self.previewPage = 0
        self.clipboard= {}
        self.shuffler = None


        self.widgets = gtk.Builder()
        self.widgets.add_from_file(sfp('data/pdfbooklet2.glade'))
        arWidgets = self.widgets.get_objects()
        self.arw = {}
        for z in arWidgets :
            try :
                name = gtk.Buildable.get_name(z)
                self.arw[name]= z
                z.set_name(name)
            except :
                pass


        #autoconnect signals for self functions
        self.widgets.connect_signals(self)


        window1 = self.arw["window1"]
        window1.show_all()
        window1.set_title("Pdf-Booklet  [ " + PB_version + " ]")
        window1.connect("destroy", lambda w: gtk.main_quit())

        self.mru_items = {}
        self.menuAdd()


        self.selection_s = ""

        self.radioSize = 1
        self.radioDisp = 1
        self.autoscale = self.arw["autoscale"]
        self.repeat = 0
        self.booklet = 1
        self.area = self.arw["drawingarea1"]
        self.settings = self.arw["settings"]
        self.overwrite = self.arw["overwrite"]
        self.noCompress = self.arw["noCompress"]
        self.righttoleft = self.arw["righttoleft"]
        self.status = self.arw["status"]

        # Global transformations
        self.Vtranslate1 = self.arw["Vtranslate1"]
        self.scale1 = self.arw["scale1"]
        self.rotation1 = self.arw["rotation1"]
        self.thispage = self.arw["thispage"]
        self.evenpages = self.arw["evenpages"]
        self.oddpages = self.arw["oddpages"]

        self.area.show()
        self.area.connect("expose-event", self.area_expose)

        self.pagesTr = {}




    # this small function returns the type of a widget
    def widget_type(self, widget) :
        try :
            z = widget.class_path()
            z2 = z.split(".")[-1]
            return z2
        except:
            return False


    def gtk_delete(self, source=None, event=None):
        gtk.main_quit()

    def close_application(self, widget, event=None, data=None):
        """Termination"""
        if self.shuffler != None :
            self.shuffler.close_application("")
            self.shuffler = None

        if gtk.main_level():
            self.arw["window1"].destroy()
            gtk.main_quit()
            gtk.gdk.threads_leave()

        os._exit(0)
        return False

    def file_manager(self,widget):
        global inputFiles_a
        mrudir = self.read_mru2()
        if mrudir == "" :
            mrudir = prog_path_u
        self.chooser = Chooser(inputFiles_a, prog_path_u, mrudir)
        inputFiles_a = self.chooser.inputFiles_a
        if len(inputFiles_a) == 0 :
            return
        # add file(s) to most recently used
        self.mru(inputFiles_a)
        self.chooser.chooser.destroy()
        self.chooser = None
        if self.shuffler:
            self.shuffler.model.clear()
            self.shuffler.pdfqueue = []
            self.shuffler.nfile = 0
            for key in inputFiles_a :
                self.shuffler.add_pdf_pages(inputFiles_a[key])
            # TODO : N'est à faire que si la liste des fichiers a changé
            self.shuffler.rendering_thread.pdfqueue = self.shuffler.pdfqueue
##            self.closePS()
##            self.runPS()
        self.loadPdfFiles()
        app.selection_s = ""
        self.previewUpdate()


    def FormatPath (
            self,
            path,
            typePath = 0) :

        if path[0:2] == "//" or path[0:2] == ["\\"] :
            prefix_s = "//"
            path = path[2:]
        else :
            prefix_s = ""

        if typePath == 1 :
            path = path.replace(":", "")
            prefix_s = ""
        path = path.replace("\\", "/")
        path = path.replace("//", "/")
        return(prefix_s + path)

    def loadPdfFiles(self) :
        global inputFile_a, inputFiles_a, pagesIndex_a

        i = 1
        inputFile_a = {}
        inputFile_details = {}
        for key in inputFiles_a :
            val = inputFiles_a[key]
            if os.path.isfile(val) :
                inputFile_a[val] = PdfFileReader(file(val, "rb"))
                inputFile_details[val] = {}
                if inputFile_a[val].getIsEncrypted() :
                    inputFile_details[val]["encrypt"] = True
                    if not hasattr(inputFile_a[val], "_decryption_key") :   # if not already decrypted
                        password = self.get_text(None, _("Please, enter the password for this file"))
                        if password != None :
                            password = password.encode("utf8")
                            inputFile_a[val].decrypt(password)     # Encrypted file
                            if key == 1 :           # we get permissions and password from the first file
                                (a,b,self.permissions_i) = inputFile_a[val].getPermissions()
                                self.password_s = password
                        inputFile_details[val]["password"] = password
                selectedIndex_a = {}
                deletedIndex_a = {}

                i += 1



    def openProject(self, widget, name = "") :
        global config, openedProject_u, preview_b, project_b



        old_dir = self.read_mru2()

        gtk_chooser = gtk.FileChooserDialog(title=_('Import...'),
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,
                                                  gtk.RESPONSE_CANCEL,
                                                  gtk.STOCK_OPEN,
                                                  gtk.RESPONSE_OK))
        gtk_chooser.set_current_folder(old_dir)
        gtk_chooser.set_select_multiple(False)

        filter_all = gtk.FileFilter()
        filter_all.set_name(_('All files'))
        filter_all.add_pattern('*')
        gtk_chooser.add_filter(filter_all)

        filter_ini = gtk.FileFilter()
        filter_ini.set_name(_('INI files'))
        filter_ini.add_pattern('*.ini')
        gtk_chooser.add_filter(filter_ini)
        gtk_chooser.set_filter(filter_ini)

        response = gtk_chooser.run()
        if response == gtk.RESPONSE_OK:
            filename = gtk_chooser.get_filename()
            filename_u = unicode2(filename, "utf-8")
            self.mru(filename)
            self.openProject2(filename_u)
            self.write_mru2(filename_u)       # write the location of the opened directory in the cfg file



##        elif response == gtk.RESPONSE_CANCEL:
##            print(_('Closed, no files selected'))
        gtk_chooser.destroy()

    def openMru(self, widget) :
        global config, openedProject_u, preview_b, project_b
        global inputFiles_a

        widget_name = widget.get_name()
        filenames_list_s = self.mru_items[widget_name][1]

        # are we opening a project file ?
        filename_u = unicode2(filenames_list_s[0], "utf-8")
        extension_s = os.path.splitext(filename_u)[1]
        if extension_s == ".ini" :
            self.openProject2(filename_u)
            return
        else :
            self.parseIniFile("pdfbooklet.cfg")     # reset transformations

        inputFiles_a = {}

        for filename_s in filenames_list_s :
            filename_u = unicode2(filename_s, "utf-8")
            extension_s = os.path.splitext(filename_u)[1]
            i = len(inputFiles_a)
            inputFiles_a[i + 1] = filename_u


        self.loadPdfFiles()
        app.selection_s = ""
        self.previewUpdate()


        if self.shuffler:
            self.shuffler.model.clear()
            self.shuffler.pdfqueue = []
            self.shuffler.nfile = 0
            self.shuffler.npage = 0
            for key in inputFiles_a :
                self.shuffler.add_pdf_pages(inputFiles_a[key])
            # TODO : N'est à faire que si la liste des fichiers a changé
            self.shuffler.rendering_thread.pdfqueue = self.shuffler.pdfqueue
            #for row in self.shuffler.model:
            #        row[6] = False



    def openProject2(self, filename_u) :
        # Called by OpenProject and OpenMru (in case the selected item was a project)
        global config, openedProject_u, preview_b, project_b

        if os.path.isfile(filename_u):
            openedProject_u = filename_u
            self.arw["window1"].set_title(u"Pdf-Booklet  [ " + PB_version + " ] - " + filename_u)
            preview_b = False
            project_b = True
            self.parseIniFile(filename_u)
            preview_b = True
            project_b = False


            # Update gui before updating preview, since preview takes its data from the gui
            while gtk.events_pending():
                        gtk.main_iteration()

            if ("options" in self.pagesTr
                and "presets" in self.pagesTr["options"]
                and self.pagesTr["options"]["presets"] == "radiopreset8") :
                    self.user_defined(False)
            else :
                self.previewUpdate()



    def saveProject(self, widget) :
        global openedProject_u

        if openedProject_u :
            self.saveProjectAs("", openedProject_u)
        else :
            self.saveProjectAs("")


    def saveProjectAs(self, widget, filename_u = "") :
        global config, openedProject_u

        if filename_u == "" :

            old_dir = self.read_mru2()

            gtk_chooser = gtk.FileChooserDialog(title=_('Save project...'),
                                            action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                            buttons=(gtk.STOCK_CANCEL,
                                                      gtk.RESPONSE_CANCEL,
                                                      gtk.STOCK_SAVE,
                                                      gtk.RESPONSE_ACCEPT))
            gtk_chooser.set_do_overwrite_confirmation(True)
            gtk_chooser.set_current_folder(old_dir)
            gtk_chooser.set_current_name("untitled document")
            # or chooser.set_filename("untitled document")

            response = gtk_chooser.run()

            if response == gtk.RESPONSE_CANCEL:
##                print(_('Closed, no files selected'))
                gtk_chooser.destroy()
                return

            elif response == gtk.RESPONSE_ACCEPT:
                filename = gtk_chooser.get_filename()
                filename_u = unicode2(filename, "utf-8")
                if filename_u[-4:] != ".ini" :
                    filename_u += u".ini"
                gtk_chooser.destroy()
                self.mru(filename_u)



        openedProject_u = filename_u

        iniFile = open(filename_u, "w")
        for section in self.pagesTr :
            if not config.has_section(section) :
                config.add_section(section)
            for option in self.pagesTr[section] :
                value = self.pagesTr[section][option]
                config.set(section,option,value)

        # update with last selections in the gui
        # perhaps we could also update first pagesTr
        out_a = self.makeIniFile()
        for section in out_a :
            if not config.has_section(section) :
                config.add_section(section)
            for option in out_a[section] :
                value = out_a[section][option]
                config.set(section,option,value)


        config.write(iniFile)
        iniFile.close()
        self.write_mru2(filename_u)        # write the location of the opened directory in the cfg file


    def mru(self, filenames_a) :

        mrudir = ""
        if isinstance(filenames_a, dict) :
            filenames = join_list(filenames_a, "|")
            if 1 in filenames_a :
                mrudir = os.path.split(filenames_a[1])[0]
        else :
            filenames = filenames_a
            mrudir = os.path.split(filenames_a)[0]

        configtemp = ConfigParser.RawConfigParser()
        configtemp.read(sfp2("pdfbooklet.cfg"))

##    if configtemp.has_section(section) == False :
##        configtemp.add_section(section)
##    configtemp.set(section,option,value)

##
        if configtemp.has_section("mru") == False :
            configtemp.add_section("mru")
        if configtemp.has_section("mru2") == False :
            configtemp.add_section("mru2")

        # cancel if already present
        temp_a = []
        for index in ["mru1", "mru2", "mru3", "mru4"] :
            if configtemp.has_option("mru",index) :
                if filenames == configtemp.get("mru",index) :
                    return


        # shift mru
        if configtemp.has_option("mru","mru3") :
            configtemp.set("mru","mru4",configtemp.get("mru","mru3"))
        if configtemp.has_option("mru","mru2") :
            configtemp.set("mru","mru3",configtemp.get("mru","mru2"))
        if configtemp.has_option("mru","mru1") :
            configtemp.set("mru","mru2",configtemp.get("mru","mru1"))
        # set the new value
        configtemp.set("mru","mru1",filenames)
        configtemp.set("mru2","mru2",mrudir)
        f = open(sfp2("pdfbooklet.cfg"),"wb")
        configtemp.write(f)
        f.close()
        configtemp = None
        self.menuAdd()


    def read_mru2(self) :

        if os.path.isfile(sfp2("pdfbooklet.cfg")) :
            configtemp = ConfigParser.RawConfigParser()
            configtemp.read(sfp2("pdfbooklet.cfg"))

            try :
                mru_dir = configtemp.get("mru2","mru2")
            except :
                mru_dir = ""

            configtemp = None
            return mru_dir


    def write_mru2(self, filename_u) :

        configtemp = ConfigParser.RawConfigParser()
        if os.path.isfile(sfp2("pdfbooklet.cfg")) :
            configtemp.read(sfp2("pdfbooklet.cfg"))

        if configtemp.has_section("mru2") == False :
            configtemp.add_section("mru2")

        (path_u, file_u) = os.path.split(filename_u)
        configtemp.set("mru2","mru2",path_u)
        f = open(sfp2("pdfbooklet.cfg"),"wb")
        configtemp.write(f)
        f.close()





    def menuAdd(self) :
        # Called by function mru, adds an entry to the menu

        configtemp = ConfigParser.RawConfigParser()
        configtemp.read(sfp2("pdfbooklet.cfg"))

        # TODO : voir pour unicode (filepath_s ou filepath_u ?)
        if configtemp.has_section("mru") :
            for item in ["mru1", "mru2", "mru3", "mru4"] :
                if configtemp.has_option("mru", item) :
                    filepath_list_s = configtemp.get("mru", item)
                    filepath_list = filepath_list_s.split("|")
                    temp1 = []
                    for filepath_s in filepath_list :
                        filepath_s = self.FormatPath(filepath_s)
                        path_s,filename_s = os.path.split(filepath_s)
                        temp1 += [filename_s]
                    menu_entry_s = join_list(temp1, ", ")


                    self.mru_items[item] = [menu_entry_s, filepath_list]
                    self.arw[item].set_label(menu_entry_s)


    def saveDefaults(self, dummy) :

        out_a = self.makeIniFile()
        iniFile = open(sfp2("pdfbooklet.cfg"), "w")
        for a in out_a :
            iniFile.write("[" + a + "]\n")
            for b in out_a[a] :
                value = out_a[a][b]
                if value == True :
                    value = '1'
                elif value == False :
                    value = '0'
                iniFile.write(b + " = " + value + "\n")
            iniFile.write("\n")
        iniFile.close()


    def pdfBooklet_doc(self, widget) :

        userGuide_s = "documentation/" + _("Pdf-Booklet_User's_Guide.pdf")
        if sys.platform == 'linux2':
            subprocess.call(["xdg-open", userGuide_s])
        else:
            os.startfile(sfp(userGuide_s))


    def popup_rotate(self, widget):
        # Called by popup menu (right clic on preview)
        global selected_page, rows_i


        # We get the value from the widget name (the 3 menu options use the same function)
        wname = widget.get_name()
        match = re.match("rotate(\d*)", wname)
        value = match.group(1)

        # Code below is just an adaptation of function "transormationsApply"
        if selected_page == None :
            self.showwarning(_("No selection"), _("There is no selected page. \nPlease select a page first. "))
            return
        # selected_page 4 and 5 contain the correct page reference, including the global rotation.
        humanReadableRow_i = rows_i - selected_page[4]
        Id = str(str(humanReadableRow_i) + "," + str(selected_page[5] + 1))

        pageId = str(selected_page[2]) + ":" + str(selected_page[3])

##        # if transformation is for this page only, use page ref instead of position ref
##        if self.thispage.get_active() == 1 :
##            Id = pageId
        if self.pagesTr.has_key(Id) == False :
            self.pagesTr[Id] = {}
            self.pagesTr[Id]["htranslate"] = 0
            self.pagesTr[Id]["vtranslate"] = 0
            self.pagesTr[Id]["scale"] = 1
            self.pagesTr[Id]["htranslate1"] = "0"
            self.pagesTr[Id]["vtranslate1"] = "0"
            self.pagesTr[Id]["scale1"] = "100"
            self.pagesTr[Id]["xscale"] = 1
            self.pagesTr[Id]["yscale"] = 1
            self.pagesTr[Id]["xscale1"] = '100'
            self.pagesTr[Id]["yscale1"] = '100'
            self.pagesTr[Id]["vflip"] = False
            self.pagesTr[Id]["hflip"] = False


        self.pagesTr[Id]["rotate"] = int(value)
        self.pagesTr[Id]["rotate1"] = value

        self.preview(self.previewPage, 0)



    def __________________INI_FILE() :
        pass

    def saveSettings(self, filename) :
        # This function is no longer used, probably
        out_a = self.makeIniFile()
        iniFile = open(filename + ".ini", "wb")
        for a in out_a :
            iniFile.write("[" + a + "]\n")
            for b in out_a[a] :
                try :
                    str_s = b + " = " + out_a[a][b] + "\n"
                    out_s = str_s.decode("utf-8")
                    iniFile.write(out_s)
                except :
                    pass
            iniFile.write("\n")
        iniFile.close()


    def readNumEntry(self, entry, widget_s = "") :
        value = entry.get_text()
        if value == "" : value = 0
        try :
            value = float(value)
        except :
            self.showwarning(_("Invalid data"), _("Invalid data for %s - must be numeric. Aborting \n") % widget_s)
            return None

        return value


    def readmmEntry(self, entry, widget_s = "", default = 0) :
        global adobe_l
        value = entry.get_text()
        value = value.replace(",", ".")
        if (value == "") :
            value = default
        else :
            try :
                value = float(value) / adobe_l
            except :
                self.showwarning(_("Invalid data"), _("Invalid data for %s - must be numeric. Aborting \n") % widget_s)
                return None
        return value

    def readPercentEntry(self, entry, widget_s = "") :
        value = entry.get_text()
        value = value.replace(",", ".")
        if (value == "") :
            value = 100
        else :
            value.replace("%", "")
            try :
                value = float(value) / 100
                if value < 0 :
                    self.showwarning(_("Invalid data"), _("Invalid data for %s - must be > 0. Aborting \n") % widget_s)
                    return None
            except :
                self.showwarning(_("Invalid data"), _("Invalid data for %s - must be numeric. Aborting \n") % widget_s)
                return None
        return value

    def readIntEntry(self, entry, widget_s = "", type_i = 0) :
        # type = 0 : accepts all values >= 0
        # type = 1 : accepts all values > 0
        # type = -1 : accepts any integer, positive or negative
        # type = 2 : optional. Don't warn if missing, but warn if invalid (not integer)
        value = entry.get_text()


        try :
            value = int(value)
            if type_i == 0 :
                if value < 0 :
                    self.showwarning(_("Invalid data"), _("Invalid data for %s - must be >= 0. Aborting \n") % widget_s)
                    return None
            elif type_i == 1 :
                if value < 1 :
                    self.showwarning(_("Invalid data"), _("Invalid data for %s - must be > 0. Aborting \n") % widget_s)
                    return None
        except :
            if value == "" :
                if type_i == 2 :
                    pass
                else :
                    self.showwarning(_("Invalid data"), _("Invalid data for %s - must be numeric. Aborting \n") % widget_s)
                    return None
            else :
                self.showwarning(_("Invalid data"), _("Invalid data for %s - must be numeric. Aborting \n") % widget_s)
                return None
        return value

    def readBoolean(self, entry) :
        value = entry.get_text()
        try :
            if int(value) < 1 :
                return False
            else :
                return True
        except :
            self.showwarning(_("Invalid data"), _("Invalid data for %s - must be 0 or 1. Aborting \n") % widget_s)


    def readGui(self, logdata = 1) :
        global config, rows_i, columns_i, step_i, sections, output, input1, input2, adobe_l, inputFiles_a, inputFile_a
        global numfolio, prependPages, appendPages, ref_page, selection
        global numPages, pagesSel, llx_i, lly_i, urx_i, ury_i, mediabox_l, outputScale, refPageSize_a



        outputFile = self.arw["entry2"].get_text()
        #iniFile = self.arw["entry3.get()
        outputScale = 1

        rows_i = self.readIntEntry(self.arw["entry11"], _("rows"), 1)
        #if rows_i == None : return False
        columns_i = self.readIntEntry(self.arw["entry12"], _("columns"), 1)
        #if columns_i == None : return False
        if (rows_i < 1) :
                rows_i = 1
        if (columns_i < 1) :
                columns_i = 1


        if self.repeat == 1 :
            step_i = self.readIntEntry(self.arw["entry15"], _("step"), 1)
            if step_i == None : return False
            if (step_i < 1) :
                step_i = 1
        else :
            step_i = rows_i * columns_i



        numfolio = self.readIntEntry(self.arw["entry13"], _("folios"))
        prependPages = self.readIntEntry(self.arw["entry32"], _("Leading blank pages"))
        if prependPages == None : return False
        appendPages = self.readIntEntry(self.arw["entry33"], _("Trailing blank pages"))
        if appendPages == None : return False
        ref_page = self.readIntEntry(self.arw["entry31"], _("Reference page"),1)
        if ref_page == None : return False
        else : ref_page -= 1
        selection = self.selection_s


        # Ouput page size
        if inputFiles_a.has_key(1) :
            fileName = inputFiles_a[1]
            page0 = inputFile_a[fileName].getPage(ref_page)   # TODO : page ref sur autres fichiers
            llx_i=page0.mediaBox.getLowerLeft_x()
            lly_i=page0.mediaBox.getLowerLeft_y()
            urx_i=page0.mediaBox.getUpperRight_x()
            ury_i=page0.mediaBox.getUpperRight_y()

            urx_i=float(urx_i) - float(llx_i)
            ury_i=float(ury_i) - float(lly_i)

            refPageSize_a = [urx_i, ury_i]


        #££self.print2 (_("Size of source file =    %s mm x %s mm ") % (int(urx_i * adobe_l), int(ury_i * adobe_l)), 1)

        oWidth_i = urx_i * columns_i
        oHeight_i = ury_i * rows_i

        if self.arw["radiosize1"].get_active() == 1 :
            mediabox_l = [oWidth_i, oHeight_i]
        elif self.arw["radiosize2"].get_active() == 1 :                         # size = no change
            if oWidth_i < oHeight_i :                           # set orientation
                mediabox_l = [urx_i, ury_i]
            else :
                mediabox_l = [ury_i, urx_i]

            # calculate  the scale factor
            deltaW = mediabox_l[0] / oWidth_i
            deltaH = mediabox_l[1] / oHeight_i
            if deltaW < deltaH :
                outputScale = deltaW
            else :
                outputScale = deltaH


        elif self.arw["radiosize3"].get_active() == 1 :         # user defined

                customX = self.readNumEntry(self.arw["outputWidth"], _("Width"))
                if customX == None : return False
                customY = self.readNumEntry(self.arw["outputHeight"], _("Height"))
                if customY == None : return False


                mediabox_l = [ customX * (1 / adobe_l), customY * (1 / adobe_l)]


                # calculate  the scale factor
                deltaW = mediabox_l[0] / oWidth_i
                deltaH = mediabox_l[1] / oHeight_i
                if deltaW < deltaH :
                    outputScale = deltaW
                else :
                    outputScale = deltaH


        outputUrx_i = mediabox_l[0]
        outputUry_i = mediabox_l[1]
        if logdata == 0 :
            self.print2 (_("Size of output file =    %s mm x %s mm ") % (int(outputUrx_i * adobe_l), int(outputUry_i * adobe_l)), 1)


        return True


    def setOption(self, option, widget, section = "options") :
        global config

        if config.has_option(section, option) :
            z = widget.class_path()
            z2 = z.split(".")
            z3 = z2[-1]
            if z3 == "GtkSpinButton" :
                data = config.get(section, option)
                data = data.replace(",",".")
                widget.set_value(float(data))
            elif z3 == "GtkTextView" :
                widget.get_buffer().set_text(config.get(section, option))
            elif z3 == "GtkCheckButton" :
                if config.getboolean(section, option) == 1 :
                    widget.set_active(True)

            else :
                widget.set_text(config.get(section, option))




    def parseIniFile(self, inifile = "") :

        global config, rows_i, columns_i, step_i, cells_i, input1, adobe_l
        global numfolio, prependPages, appendPages, ref_page, selection
        global numPages, pagesSel, llx_i, lly_i, urx_i, ury_i, inputFile, inputFiles_a
        global startup_b

        config = ConfigParser.RawConfigParser()
        config.readfp(open(inifile))

        # store in dictionary
        self.pagesTr = {}
        for section in config.sections() :
            self.pagesTr[section] = {}
            for option, value in config.items(section) :
                if value == 'False' :
                    value = False
                elif value == 'True' :
                    value = True
                self.pagesTr[section][option] = value


        self.setOption("rows", self.arw["entry11"])
        self.setOption("columns", self.arw["entry12"])
        self.setOption("step", self.arw["entry15"])
        self.setOption("numfolio", self.arw["entry13"])
        self.setOption("prependPages", self.arw["entry32"])
        self.setOption("appendPages", self.arw["entry33"])
        self.setOption("referencePage", self.arw["entry31"])
        self.setOption("output", self.arw["entry2"])
        self.setOption("width", self.arw["outputWidth"])
        self.setOption("height", self.arw["outputHeight"])
        self.setOption("userLayout", self.arw["user_layout"])

        self.setOption("Htranslate", self.arw["Htranslate2"], "output")
        self.setOption("Vtranslate", self.arw["Vtranslate2"], "output")
        self.setOption("Scale", self.arw["scale2"], "output")
        self.setOption("Rotate", self.arw["rotation2"], "output")
        self.setOption("xscale", self.arw["xscale2"], "output")
        self.setOption("yscale", self.arw["yscale2"], "output")
        self.setOption("vflip", self.arw["vflip2"], "output")
        self.setOption("hflip", self.arw["hflip2"], "output")


        # inputs

        if startup_b == 0 :
            if config.has_option("options", "input1") :         # no longer used.
                temp1 = config.get("options", "input1")
                self.filesList.delete(0)
                self.filesList.insert(0,temp1)

            if config.has_option("options", "inputs") :
                temp1 = config.get("options", "inputs")
                inputFiles_a = {}
                for a in temp1.split("|") :
                    if os.path.isfile(unicode2(a,"utf-8")) :
                        filename = unicode2(a,"utf-8")
                        pdfFile = PdfFileReader(file(filename, "rb"))
                        numpages = pdfFile.getNumPages()
                        path, shortFileName = os.path.split(filename)
                        i = len(inputFiles_a)
                        inputFiles_a[i + 1] = filename

                self.loadPdfFiles()
                if config.has_option("options", "pageselection") :
                    self.selection_s = config.get("options", "pageselection")



        # variables
        if config.has_option("options", "booklet") :
            self.booklet = int(config.get("options", "booklet"))

        # set radio buttons

        if config.has_option("options", "presets") :
            temp1 = config.get("options", "presets")
            self.arw[temp1].set_active(True)

        if config.has_option("options", "size") :
            temp1 = config.get("options", "size")
            self.arw[temp1].set_active(True)

        if config.has_option("options", "presetOrientation") :
            temp1 = config.get("options", "presetOrientation")
            self.arw[temp1].set_active(True)

        if config.has_option("options", "globalRotation") :
            temp1 = config.get("options", "globalRotation")
            self.arw[temp1].set_active(True)

        # set check boxes

        if config.has_option("options", "advanced") :
            if config.getint("options", "advanced") == 1 : self.advanced.set_active(1)
            else : self.advanced.set_active(0)
            self.guiAdvanced()
        if config.has_option("options", "autoScale") :
            if config.getboolean("options", "autoScale") == 1 : self.autoscale.set_active(1)
            else : self.autoscale.set_active(0)
        if config.has_option("options", "autoRotate") :
            if config.getint("options", "autoRotate") == 1 : self.autorotate.set_active(1)
            else : self.autorotate.set_active(0)

        if config.has_option("options", "showPdf") :
            if config.getboolean("options", "showPdf") == 1 : self.arw["show"].set_active(1)
            else : self.arw["show"].set_active(0)
        if config.has_option("options", "saveSettings") :
            if config.getboolean("options", "saveSettings") == 1 : self.settings.set_active(1)
            else : self.settings.set_active(0)

        if config.has_option("options", "noCompress") :
            if config.getboolean("options", "noCompress") == 1 : self.noCompress.set_active(1)
            else : self.noCompress.set_active(0)
        if config.has_option("options", "overwrite") :
            if config.getboolean("options", "overwrite") == 1 : self.overwrite.set_active(1)
            else : self.overwrite.set_active(0)

        if config.has_option("options", "righttoleft") :
            if config.getboolean("options", "righttoleft") == 1 : self.righttoleft.set_active(1)
            else : self.righttoleft.set_active(0)




    def makeIniFile(self, inifile = "") :

        global config, rows_i, columns_i, step_i, cells_i, input1, adobe_l
        global numfolio, prependPages, appendPages, ref_page, selection
        global numPages, pagesSel, inputFile
        global out_a

        out_a = {}
        out_a["options"] = {}
        out_a["output"] = {}
        out_a["mru"] = {}
        options_l = []


        out_a["options"]["rows"] = self.arw["entry11"].get_text()
        out_a["options"]["columns"] = self.arw["entry12"].get_text()
        out_a["options"]["booklet"] = str(self.booklet)
        out_a["options"]["step"] = self.arw["entry15"].get_text()
        out_a["options"]["numfolio"] = self.arw["entry13"].get_text()
        out_a["options"]["prependPages"] = self.arw["entry32"].get_text()
        out_a["options"]["appendPages"] = self.arw["entry33"].get_text()
        out_a["options"]["referencePage"] = self.arw["entry31"].get_text()
        out_a["options"]["pageSelection"] = self.selection_s
        buf = self.arw["user_layout"].get_buffer()
        start, end  = buf.get_bounds()
        layout_s = buf.get_text(start, end)
        out_a["options"]["userLayout"] = layout_s

        temp1 = ""
        for key in inputFiles_a :
                val = inputFiles_a[key]
                temp1 += val + '|'

        out_a["options"]["inputs"] = temp1
        out_a["options"]["output"] = self.arw["entry2"].get_text()
        out_a["options"]["repeat"] = str(self.arw["entry15"].get_text())
        out_a["options"]["showPdf"] = str(self.arw["show"].get_active())
        out_a["options"]["saveSettings"] = str(self.settings.get_active())
        out_a["options"]["autoScale"] = str(self.autoscale.get_active())
    ##    out_a["options"]["autoRotate"] = str(self.autorotate.get_active())
        out_a["options"]["width"] = str(self.arw["outputWidth"].get_text())
        out_a["options"]["height"] = str(self.arw["outputHeight"].get_text())

        out_a["options"]["noCompress"] = str(self.noCompress.get_active())
        out_a["options"]["righttoleft"] = str(self.righttoleft.get_active()) # Gaston - 14 Sep 2013
        out_a["options"]["overwrite"] = str(self.overwrite.get_active())

        out_a["output"]["Htranslate"] = self.arw["Htranslate2"].get_text()
        out_a["output"]["Vtranslate"] = self.arw["Vtranslate2"].get_text()
        out_a["output"]["Scale"] = self.arw["scale2"].get_text()
        out_a["output"]["Rotate"] = self.arw["rotation2"].get_text()
        out_a["output"]["xScale"] = self.arw["xscale2"].get_text()
        out_a["output"]["yScale"] = self.arw["yscale2"].get_text()
        out_a["output"]["vflip"] = self.arw["vflip2"].get_active()
        out_a["output"]["hflip"] = self.arw["vflip2"].get_active()


        # radio buttons

        group = self.arw["radiopreset1"].get_group()
        for a in group :
            if a.get_active() == True :
                out_a["options"]["presets"] = a.get_name()

        group = self.arw["radiosize1"].get_group()
        for a in group :
            if a.get_active() == True :
                out_a["options"]["size"] = a.get_name()

        group = self.arw["presetOrientation1"].get_group()
        for a in group :
            if a.get_active() == True :
                out_a["options"]["presetOrientation"] = a.get_name()

        group = self.arw["globalRotation0"].get_group()
        for a in group :
            if a.get_active() == True :
                out_a["options"]["globalRotation"] = a.get_name()

        # most recently used

        # TODO : if file exists (ici et ailleurs)
        configtemp = ConfigParser.RawConfigParser()
        configtemp.read(sfp2("pdfbooklet.cfg"))

        if configtemp.has_section("mru"):
            if configtemp.has_option("mru","mru1") :
                out_a["mru"]["mru1"] = configtemp.get("mru","mru1")
            if configtemp.has_option("mru","mru2") :
                out_a["mru"]["mru2"] = configtemp.get("mru","mru2")
            if configtemp.has_option("mru","mru3") :
                out_a["mru"]["mru3"] = configtemp.get("mru","mru3")
            if configtemp.has_option("mru","mru4") :
                out_a["mru"]["mru4"] = configtemp.get("mru","mru4")




        return out_a


    def _______________________PRESETS() :
        pass


    def guiPresets(self, radiobutton = 0, event = None) :

        global startup_b, project_b, preview_b

        if radiobutton != 0 :
            if radiobutton.get_active() == 0 :  # signal is sent twice, ignore one of them
                return
        if project_b == True :  # Don't change values if we are loading a project
            return

        preview_b = False   # prevent multiple preview commands due to signals emitted by controls
        presetOrientation_i = self.arw["presetOrientation1"].get_active()

        if self.arw["radiopreset1"].get_active() == 1 : # single booklet
            if presetOrientation_i == 1 :
                self.presetBooklet(0,0)
            else :
                self.presetBooklet(0,1)
            self.guiPresetsShow("booklet")


        elif self.arw["radiopreset2"].get_active() == 1 :    # Multiple booklets
            if presetOrientation_i == 1 :
                self.presetBooklet(5,0)
            else :
                self.presetBooklet(5,1)
            self.guiPresetsShow("booklet")

        elif self.arw["radiopreset3"].get_active() == 1 :    # 2-up
            if presetOrientation_i == 1 :
                self.presetUp(1,2)
            else :
                self.presetUp(2,1)
            self.guiPresetsShow("")

        elif self.arw["radiopreset4"].get_active() == 1 :   # 4-up in lines
            if presetOrientation_i == 1 :
                self.presetUp(2,2,1)
            else :
                self.presetUp(2,2,1)
            self.guiPresetsShow("")

        elif self.arw["radiopreset5"].get_active() == 1 :   # 4-up in columns
            if presetOrientation_i == 1 :
                self.presetUp(2,2,2)
            else :
                self.presetUp(2,2,2)
            self.guiPresetsShow("")

        elif self.arw["radiopreset6"].get_active() == 1 :   # x copies
            if presetOrientation_i == 1 :
                self.presetCopies(1,2)
            else :
                self.presetCopies(2,1)
            self.guiPresetsShow("copies")

        elif self.arw["radiopreset7"].get_active() == 1 :
            if presetOrientation_i == 1 :
                self.presetMerge()
            else :
                self.presetMerge()
            self.guiPresetsShow("")

        elif self.arw["radiopreset8"].get_active() == 1 :   # User defined
            return      # This button launchs the function "user_defined" which will handle the request


        preview_b = True
        if radiobutton != 0 and startup_b == False :
            self.preview(self.previewPage)

    def user_defined(self, widget) :
        # Called by the "user defined" option button in the main window
        # Gets data from the dialog where user enters the user defined layout
        # Process the text from the TextView and sets controls and variables
        # then update the preview.
        # @widget : if this parameter is False, the dialog is not shown (used by OpenProject)

        global startup_b, project_b, preview_b

        preview_b = False   # prevent multiple preview commands due to signals emitted by controls
        if widget == False :
            response = 1
        else :
            dialog = self.arw["dialog2"]
            response = dialog.run()
            dialog.hide()

        if response == 0 :
            return
        if response == 1 :
            buf = self.arw["user_layout"].get_buffer()
            start, end  = buf.get_bounds()
            layout_s = buf.get_text(start, end)

            lines = layout_s.split("\n")

            imposition = []
            lines2 = []
            for line in lines :
                if line.strip() == "" :     # correct errors : ignore blank lines
                    continue
                if line[0:1] == "#" :       # ignore comments
                    continue
                if line[0:4] == "====" :    # New sheet
                    imposition.append(lines2)
                    lines2 = []
                else :
                    lines2.append(line)
            if len(lines2) > 0 :
                imposition.append(lines2)

            numrows = len(lines2)
            cols = lines2[0].split(",")
            numcols = 0
            for a in cols :
                if a.strip() != "" :
                    numcols += 1

            imposition2 = []
            for lines2 in imposition :
                pages = []
                for line in lines2 :
                    line = line.split(",")
                    for a in line :
                        if a.strip() != "" :         # correct errors : ignore trailing comma
                            pages.append(a.strip())
                imposition2.append(pages)

            self.userpages = imposition2[0]
            self.imposition = imposition2

            # set step
            if self.arw["step_defined"].get_active() == True :
                step_s = self.arw["step_value"].get_text()
                self.presetCopies(numrows,numcols,step_s)
                self.guiPresetsShow("copies")
            else :
                self.presetUp(numrows,numcols)
                self.guiPresetsShow("")

            # TODO message d'erreur
            total_pages = numrows * numcols
            if len(pages) != total_pages :
                print _("Expected page number was : %d. Only %d found. \nThere is an error in your layout, please correct") % (total_pages, len(pages))



            # Update gui before updating preview, since preview takes its data from the gui
            while gtk.events_pending():
                        gtk.main_iteration()

            preview_b = True
            if startup_b == False :
                self.preview(self.previewPage)

    def select_step_value(self, widget, event) :
        # launched when user types something in "step_value" entry
        # Selects the appropriate radio button
        self.arw["step_defined"].set_active(True)

    def guiPresetsShow(self, action_s) :

        StepWidgets = [self.arw["label15"], self.arw["entry15"]]
        LeafsWidgets = [self.arw["label13"], self.arw["entry13"]]
        OrientationWidgets = [self.arw["label11"], self.arw["presetOrientation1"],
                              self.arw["label12"], self.arw["presetOrientation2"]]


        for a in StepWidgets + LeafsWidgets + OrientationWidgets :
            a.hide()

        if action_s == "booklet" :
            for a in LeafsWidgets + OrientationWidgets :
                a.show()

        if action_s == "copies" :
            for a in StepWidgets :
                a.show()


    def presetBooklet(self, leafs_i, orientation) :
        if orientation == 0 :
            self.arw["entry11"].set_value(1)                    # rows
            self.arw["entry12"].set_value(2)                    # columns
        else :
            self.arw["entry11"].set_value(2)                    # rows
            self.arw["entry12"].set_value(1)                    # columns
        self.arw["entry13"].set_text(str(leafs_i))              # leafs in booklet
        self.repeat = 0
        self.booklet = 1

    def presetUp(self, r,c,l=1) :
        self.arw["entry11"].set_value(r)                    # rows
        self.arw["entry12"].set_value(c)                    # columns
        self.booklet = 0                          # checkerboard
        self.radioDisp = l                        # lines / columns
        self.repeat = 0

    def presetCopies(self, r,c, step="1") :
        global step_i
        self.arw["entry11"].set_value(r)                    # rows
        self.arw["entry12"].set_value(c)                    # columns
        self.booklet = 0                          # checkerboard
        self.repeat = 1
        self.arw["entry15"].set_text(step)                   # step

    def presetCopies2(self, r,c,l=1) :
        self.arw["entry11"].set_value(r)                    # rows
        self.arw["entry12"].set_value(c)                    # columns
        self.booklet = 0                          # checkerboard
        self.radioDisp = l                        # lines / columns
        self.repeat = 0


    def presetMerge(self) :
        global outputFile, inputFile_a

        self.arw["entry11"].set_value(1)                    # rows
        self.arw["entry12"].set_value(1)                    # columns
        self.booklet = 0                          # checkerboard
        self.repeat = 0

    def _________________________PREVIEW() :
        pass

    def area_expose(self, area, event, delete = 1) :
        global areaAllocationW_i, areaAllocationH_i

        self.style = self.area.get_style()
        self.gc = self.area.window.new_gc()
        temp_gc = self.style.fg_gc[gtk.STATE_NORMAL]
        self.gc.copy(temp_gc)   # make a copy of the graphic context
        self.gc.line_width = 3
        fgcolor = self.area.get_colormap().alloc_color(0xFFFF, 0x0000, 0x0000)
        bgcolor = self.area.get_colormap().alloc_color(0x0000, 0x0000, 0x0000)
        # Was the size changed ?
        if (areaAllocationW_i == self.area.allocation.width
            and areaAllocationH_i  == self.area.allocation.height) :
                nochange_b = True
        else :
            nochange_b = False
            areaAllocationW_i = self.area.allocation.width
            areaAllocationH_i  = self.area.allocation.height

        # use this color for drawing
        self.gc.foreground = bgcolor

        if delete == 1 :
            self.area.window.draw_rectangle(self.gc, True, 0, 0, areaAllocationW_i, areaAllocationH_i)
        self.gc.foreground = fgcolor
        self.pangolayout = self.area.create_pango_layout("")

        self.draw_pixmap(event, delete, nochange_b)
        #self.area.window.draw_line(self.gc, 0, 0, 70, 45)





    def draw_pixmap(self, event, delete, nochange_b):
        global previewColPos_a, previewRowPos_a, pageContent_a, previewPagePos_a, thumbnail

        #print "===> draw pixmap"
        if event != 0 and nochange_b == False :
            thumbnail = self.createThumbnail()   # TODO : ce n'est pas toujours nécessaire : seulement en cas de redimensionnment de la fenêtre
        if thumbnail == False or thumbnail == "" :
            return False
        heightPoints  = thumbnail.get_height()
        widthPoints = thumbnail.get_width()

        Hoffset_i = int((areaAllocationW_i - widthPoints) /2)
        Voffset_i = int((areaAllocationH_i - heightPoints)/2)

        self.area.window.draw_pixbuf(self.gc, thumbnail, 0, 0, Hoffset_i, Voffset_i, -1, -1)

        # if the output is turned, swap rows and cols numbers
        if app.arw["globalRotation90"].get_active() == 1 \
          or  app.arw["globalRotation270"].get_active() == 1:
            preview_cols = rows_i
            preview_rows = columns_i
        else :
            preview_cols = columns_i
            preview_rows = rows_i

        # show page numbers
        columnWidth = widthPoints / preview_cols
        rowHeight = heightPoints / preview_rows
        #center position of columns
        previewColPos_a = []
        previewRowPos_a = []
        previewPagePos_a = {}


        for a1 in range(preview_cols) :
            #left of the column
            previewColPos_a += [int((a1 * columnWidth) + Hoffset_i)]
        for a2 in range(preview_rows) :
            #top of the row
            # rows count starts from bottom => areaAllocationH_i - ...
            previewRowPos_a += [areaAllocationH_i - (int((a2 * rowHeight) + Voffset_i ))]
        # add the right pos of the last col
        previewColPos_a += [int(previewColPos_a[a1] + columnWidth)]
        previewRowPos_a += [int(previewRowPos_a[a2] - rowHeight)]

        i = 0
        pageContent_a = {}

        for a in self.rotate_layout() :
            # human readable page number
            pageRef_s = self.ar_pages[0][i]
            file_number, page_number = string.split(pageRef_s, ":")
            page_number = int(page_number) + 1
            if file_number == "1" :
                pageNumber = str(page_number)
            else :
                pageNumber = str(file_number) + ":" + str(page_number)


            fontsize_i = int(columnWidth / 4)
            if fontsize_i < 10 :
                fontsize_i = 10
            colpos_i = previewColPos_a[a[1]] + (columnWidth / 2)
            rowpos_i = previewRowPos_a[a[0]] - (rowHeight / 2)



            font1 = pango.FontDescription("Sans " + str(fontsize_i))
            self.pangolayout.set_font_description(font1)
            self.pangolayout.set_markup('<span foreground="red">' + pageNumber + '</span>')

            txtWidth, txtHeight = self.pangolayout.get_pixel_size()
            colpos_i -= int(txtWidth / 2)
            rowpos_i -= int(txtHeight / 2)
            toto = self.pangolayout.get_pixel_extents()
            toto = self.pangolayout.get_pixel_extents()

            self.area.window.draw_layout(self.gc, colpos_i, rowpos_i, self.pangolayout)
            pageId = str(a[0]) + ":" + str(a[1])
            pageContent_a[pageId] = [file_number, page_number]

            # store page position
            bottom = previewRowPos_a[a[0]]
            top = previewRowPos_a[a[0]] - rowHeight
            left = previewColPos_a[a[1]]
            right = previewColPos_a[a[1]] + columnWidth
            previewPagePos_a[pageRef_s] = [left, right, top, bottom, ]


            # draw rectangle if selected
            pagePosition_s = str(a[0]) + ":" + str(a[1])

            if pagePosition_s + "selected" in selectedIndex_a :
                if selectedIndex_a[pagePosition_s + "selected"] == 1 :
                    coord = previewPagePos_a[pageRef_s]
                    self.drawRectangle(coord[0] + 1, coord[1] - 2, coord[2], coord[3] - 2)

            # mark if deleted

            if pageRef_s + "deleted" in deletedIndex_a :
                if deletedIndex_a[pageRef_s + "deleted"] == 1 :
                    coord = previewPagePos_a[pageRef_s]
                    self.drawX(coord[0], coord[1], coord[2], coord[3])
            i += 1
        return


    def draw_image(self, x, y):         # unused
       pixmap, mask = gtk.gdk.pixmap_create_from_xpm(
       self.area.window, self.style.bg[gtk.STATE_NORMAL], "gtk.xpm")

       self.area.window.draw_drawable(self.gc, pixmap, 0, 0, x+15, y+25,
                                      -1, -1)
       self.pangolayout.set_text("Pixmap")
       self.area.window.draw_layout(self.gc, x+5, y+80, self.pangolayout)


    def drawRectangle(self, leftPos_i, rightPos_i, topPos_i, bottomPos_i) :

        width = rightPos_i - leftPos_i
        height = bottomPos_i - topPos_i
        self.area.window.draw_rectangle(self.gc, False, leftPos_i, topPos_i, width, height)

    def rotate_layout(self) :
        rotated_layout= []
        for i in range (len(self.ar_layout)) :
            r, c = self.ar_layout[i]
            # if output page is rotated (global rotation)
            if app.arw["globalRotation270"].get_active() == 1 :
                # invert row; We use columns_i because when rotated 90°,
                # the numbers of rows of the preview is the number of columns of the page
                r = (rows_i - 1) - r
                r,c = c,r       # swap

            elif app.arw["globalRotation90"].get_active() == 1 :
                # invert column; ; We use rows_i because when rotated 90°,
                # the numbers of columns of the preview is the number of rows of the page
                c = (columns_i - 1) - c
                r,c = c,r       # swap

            elif app.arw["globalRotation180"].get_active() == 1 :
                # invert row and column
                r = (rows_i - 1) - r
                c = (columns_i - 1) - c

            rotated_layout.append([r,c])
        return rotated_layout


    def selectPage (self, widget, event=None):
        # Called by a click on the preview or on the radio buttons, this function will :
        #   - Select the appropriate Id
        #   - launch area_expose to update the display
        #   - fill in the gtkEntry widgets which contains the transformations

        global previewColPos_a, previewRowPos_a, canvasId20, pageContent_a, selected_page
        global selectedIndex_a



        if event == None :                  # Click on a radio button
            if self.thispage.get_active() == 1 :
                pageId = str(selected_page[2]) + ":" + str(selected_page[3])
                Id = pageId
            elif self.evenpages.get_active() == 1 :
                Id = "even"
            elif self.oddpages.get_active() == 1 :
                Id = "odd"
            else :         # first button, pages in this position
                humanReadableRow_i = rows_i - selected_page[4]
                Id = str(str(humanReadableRow_i) + "," + str(selected_page[5] + 1))

        elif event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3 :            # right click, runs the context menu
                self.arw["contextmenu1"].popup(None, None, None, event.button, event.time)
                return

            else :
                # get preview area
                left_limit = previewColPos_a[0]
                bottom_limit = previewRowPos_a[-1]
                right_limit = previewColPos_a[-1]
                top_limit = previewRowPos_a[0]

                xpos = event.x
                ypos = event.y

                # check if click is inside preview
                if (xpos < left_limit
                    or xpos > right_limit
                    or ypos < bottom_limit
                    or ypos > top_limit) :

                        return

                # find the row and column
                for c in range(len(previewColPos_a)) :
                    if xpos > previewColPos_a[c] and xpos < previewColPos_a[c + 1]:
                        leftPos_i = previewColPos_a[c]
                        rightPos_i = previewColPos_a[c + 1]
                        break


                for r in range(len(previewRowPos_a)) :
                    if ypos < previewRowPos_a[r] and ypos > previewRowPos_a[r + 1]:
                        bottomPos_i = previewRowPos_a[r]
                        topPos_i = previewRowPos_a[r + 1]
                        break

                r1 = r
                c1 = c

                # if output page is rotated (global rotation)
                if app.arw["globalRotation90"].get_active() == 1 :
                    # invert row; We use columns_i because when rotated 90°,
                    # the numbers of rows of the preview is the number of columns of the page
                    r1 = (columns_i - 1) - r
                    r1,c1 = c,r1       # swap

                elif app.arw["globalRotation270"].get_active() == 1 :
                    # invert column; ; We use rows_i because when rotated 90°,
                    # the numbers of columns of the preview is the number of rows of the page
                    c1 = (rows_i - 1) - c
                    r1,c1 = c1,r       # swap

                elif app.arw["globalRotation180"].get_active() == 1 :
                    # invert row and column
                    r1 = (rows_i - 1) - r
                    c1 = (columns_i - 1) - c

                selected_page = [r, c]
                selected_page += pageContent_a[str(r)  + ":"  + str(c)]
                selected_page += [r1, c1]


                pageRef_s = str(r) + ":" + str(c)
                selectedIndex_a = {}
                selectedIndex_a[pageRef_s + "selected"] = 1


                # This can be used later to allow multiple pages selected.
##                if event.state != gtk.gdk.CONTROL_MASK :
##                    self.area_expose(0,0,0)  # draw again to delete previous rectangles and so on
##                else :
##                    self.drawRectangle(leftPos_i + 1, rightPos_i - 2, topPos_i , bottomPos_i - 2)

                self.area_expose(0,0,0)  # draw again to delete previous rectangles and so on

                # position reference
                humanReadableRow_i = rows_i - r1
                Id = str(str(humanReadableRow_i) + "," + str(c1 + 1))
                pageId = str(selected_page[2]) + ":" + str(selected_page[3])

                # if transformation is for this page only, use page ref instead of position ref
                if self.thispage.get_active() == 1 :
                    Id = pageId

        else :              # unsupported event
            return

        # Load settings in transformation dialogs

        # defaults
        self.arw["Htranslate1"].set_text("0")
        self.Vtranslate1.set_text("0")
        self.scale1.set_text("100")
        self.rotation1.set_text("0")
        self.arw["xscale1"].set_text("100")
        self.arw["yscale1"].set_text("100")
        self.arw["vflip1"].set_active(False)
        self.arw["hflip1"].set_active(False)


        if self.pagesTr.has_key(Id) :
            if "htranslate1" in self.pagesTr[Id] :
                self.arw["Htranslate1"].set_text(str(self.pagesTr[Id]["htranslate1"]))
            if "vtranslate1" in self.pagesTr[Id] :
                self.Vtranslate1.set_text(str(self.pagesTr[Id]["vtranslate1"]))
            if "scale1" in self.pagesTr[Id] :
                self.scale1.set_text(str(self.pagesTr[Id]["scale1"]))
            if "rotate1" in self.pagesTr[Id] :
                self.rotation1.set_text(str(self.pagesTr[Id]["rotate1"]))
            if "xscale1" in self.pagesTr[Id] :
                self.arw["xscale1"].set_text(str(self.pagesTr[Id]["xscale1"]))
            if "yscale1" in self.pagesTr[Id] :
                self.arw["yscale1"].set_text(str(self.pagesTr[Id]["yscale1"]))

            if "vflip" in self.pagesTr[Id] :
                bool_b = self.pagesTr[Id]["vflip"]
                if bool_b == "True" or bool_b == True or bool_b == "1" :           # when parameter comes from the ini file, it is a string
                    bool_b = 1
                elif bool_b == "False" or bool_b == False or bool_b == "0" :
                    bool_b = 0
                self.arw["vflip1"].set_active(bool_b)
            if "hflip" in self.pagesTr[Id] :
                bool_b = self.pagesTr[Id]["hflip"]
                if bool_b == "True" or bool_b == True or bool_b == "1" :           # when parameter comes from the ini file, it is a string
                    bool_b = 1
                elif bool_b == "False" or bool_b == False or bool_b == "0" :
                    bool_b = 0

                self.arw["hflip1"].set_active(bool_b)



    def deletePage (self, widget):
        global pageContent_a, selected_page, deletedIndex_a, previewPagePos_a

        filenum_i = selected_page[2]
        pagenum_i  = selected_page[3]
        pageRef_s = str(filenum_i) + ":" + str(pagenum_i - 1)

        coord = previewPagePos_a[pageRef_s]
        self.drawX(coord[0], coord[1], coord[2], coord[3])

        deletedIndex_a[pageRef_s + "deleted"] = 1

    def drawX(self, leftPos_i, rightPos_i, topPos_i, bottomPos_i) :
        self.area.window.draw_line(self.gc, leftPos_i, topPos_i, rightPos_i, bottomPos_i)
        self.area.window.draw_line(self.gc, rightPos_i, topPos_i, leftPos_i, bottomPos_i)
        self.createSelection()

    def createSelection(self) :
        global inputFiles_a
        i = 1
        x = []
        for f in inputFiles_a :
            fileName = inputFiles_a[f]
            numPages = inputFile_a[fileName].getNumPages()
            for z in range(numPages) :
                pageRef_s = str(i) + ":" + str(z)
                if pageRef_s + "deleted" in deletedIndex_a :
                    if deletedIndex_a[pageRef_s + "deleted"] == 1 :
                        pass
                    else :
                        x += [pageRef_s]
                else :
                    x += [pageRef_s]
            i += 1
        self.selection_s = self.compressSelection(x)

    def compressSelection(self, x) :
        i = 0
        temp = {}
        out = ""
        for a in x :
            b = a.split(":")
            if len(b) == 1 :
                npage = b[0]
                nfile = 1
            else :
                npage = b[1]
                nfile = b[0]

            if i == 0 :
                temp["file"] = nfile
                temp["first"] = npage
                temp["last"] = npage
            else :
                if nfile == temp["file"] and int(npage) == int(temp["last"]) + 1  :
                    temp["last"] = npage            # on continue
                else :                              # sinon on écrit
                    if temp["first"] == "-1":
                        out += "b"
                    else :
                        out += str(temp["file"]) + ":" + str(temp["first"])
                        if temp["last"] != temp["first"] :
                            out += "-" + str(temp["last"])
                    out += "; "
                    # et on mémorise
                    temp["file"] = nfile
                    temp["first"] = npage
                    temp["last"] = npage
            i += 1

        if temp["first"] == "-1":
            out += "b"
        else :
            out += str(temp["file"]) + ":" + str(temp["first"])
        if temp["last"] != temp["first"] :
            out += "-" + str(temp["last"])

        # compress blank pages
        temp1 = out.split(";")
        out = ""
        blank_count = 0
        for a in temp1 :
            if a.strip() == "b" :
                blank_count += 1
            else :
                if blank_count > 0 :
                    out += str(blank_count) + "b;"
                    blank_count = 0
                out += a + ";"
        if blank_count > 0 :
            out += str(blank_count) + "b"

        return out

    def edit_selection(self, widget) :
        dialog = self.arw["dialog1"]
        TextBuffer = self.arw["textview1"].get_buffer()
        selection1 = self.selection_s.replace(";","\n")
        TextBuffer.set_text(selection1)
        choice = dialog.run()
        if choice == 1 :
            start_iter = TextBuffer.get_start_iter()
            end_iter = TextBuffer.get_end_iter()
            selection2 = TextBuffer.get_text(start_iter, end_iter, False)
            selection2 = selection2.replace("\n",";")
            self.selection_s = selection2
            if self.shuffler:
                self.shuffler.model.clear()
                self.shuffler.pdfqueue = []
                self.shuffler.nfile = 0
                self.loadShuffler()
                # TODO : N'est à faire que si la liste des fichiers a changé
                self.shuffler.rendering_thread.pdfqueue = self.shuffler.pdfqueue
        # TODO : update preview
        dialog.hide()


    def preview(self, previewPage, delete = 1) :


        global mediabox_l0, columns_i, rows_i, step_i, urx_i, ury_i, mediabox_l
        global outputScale, pageContent_a
        global selectedIndex_a, deletedIndex_a, previewPagePos_a
        global areaAllocationW_i, areaAllocationH_i
        global preview_b


        if preview_b == False :
            return


    ##    try :

        if self.readGui(0) :
            if self.render.parsePageSelection() :
                #self.readConditions()
                ar_pages, ar_layout = self.render.createPageLayout(0)
                if ar_pages != None :
                    if previewPage > len(ar_pages) - 1 :
                        previewPage = len(ar_pages) - 1
                        self.previewPage = previewPage
                    self.arw["previewEntry"].set_text(str(previewPage + 1))
                    mem = ar_pages[previewPage]
                    ar_pages = {}
                    ar_pages[0] = mem

                    if self.render.createNewPdf(ar_pages, ar_layout, previewPage) :

                        thumbnail = self.createThumbnail()
                        self.ar_pages = ar_pages
                        self.ar_layout = ar_layout
                        self.area_expose(0,0,delete)
    ##    except :
    ##        pass


    def createThumbnail(self) :
        global areaAllocationW_i, areaAllocationH_i, previewtempfile, thumbnail


        try :
            document = poppler.document_new_from_file("file:///" + os.path.join(temp_path_u, "preview.pdf"), None)
            #self.document= document
        except :
            print "Error in function createThumbnails"
            return False
        #f1 = file(os.path.join(temp_path_u, "preview.pdf"))
        #data = f1.read()
        #f1.close()

        #document2 = poppler.document_new_from_data(data, len(data), None)  #Does not work due to this bug : https://bugs.launchpad.net/poppler-python/+bug/312462
        page = document.get_page(0)
        pix_w, pix_h = page.get_size()

        # calculate the preview size

        A = int((areaAllocationH_i * pix_w) / pix_h)    # width of preview if full height
        B = int((areaAllocationW_i * pix_h) / pix_w)    # height of preview if full width


        if A < areaAllocationW_i :                      # if full height is OK
            heightPoints = areaAllocationH_i
            widthPoints = A
            scale = areaAllocationH_i / pix_h
        else :
            widthPoints = areaAllocationW_i
            heightPoints = B
            scale = areaAllocationW_i / pix_w

        """
        thumbnail = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False,
                                           8, widthPoints , heightPoints)
        time3 = time.time()
        page.render_to_pixbuf(0,0,int(pix_w),int(pix_h),scale,0,thumbnail)
        time4 = time.time()
        """
        # fix ? =====================================================================

        # Render to a pixmap
        pixmap = gtk.gdk.Pixmap(None, widthPoints, heightPoints, 24) # FIXME: 24 or 32?
        cr = pixmap.cairo_create()
        cr.set_source_rgb(1, 1, 1)
        #scale = min(ww/pw, wh/ph)
        cr.scale(scale, scale)
        cr.rectangle(0, 0, areaAllocationW_i, areaAllocationH_i)
        cr.rectangle(0, 0, pix_w, pix_h)
        cr.fill()
        page.render(cr)
        # Convert pixmap to pixbuf
        thumbnail = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, widthPoints, heightPoints)
        thumbnail.get_from_drawable(pixmap, gtk.gdk.colormap_get_system(), 0, 0, 0, 0, widthPoints, heightPoints)


        # endfix ? =================================================================

        del document
        del pixmap



        #print str(time4 - time3)[0:4]

        return thumbnail



    def previewNext(self, dummy) :
        global selected_page, selectedIndex_a
        selected_page = None
        selectedIndex_a = {}
        self.previewPage += 1
        self.preview(self.previewPage)

    def previewPrevious(self, dummy) :
        global selected_page, selectedIndex_a
        selected_page = None
        selectedIndex_a = {}
        self.previewPage -= 1
        if self.previewPage < 0 :
            self.previewPage = 0
        self.preview(self.previewPage)

    def previewFirst(self, widget) :
        global selected_page, selectedIndex_a
        selected_page = None
        selectedIndex_a = {}
        self.previewPage = 0
        self.preview(self.previewPage)

    def previewLast(self, widget) :
        global selected_page, selectedIndex_a
        selected_page = None
        selectedIndex_a = {}
        self.previewPage = 1000000    # CreatePageLayout will substitute the right number
        self.preview(self.previewPage)

    def previewUpdate(self, Event = None, data = None) :
        global inputFiles_a
        if len(inputFiles_a) == 0 :
            #self.showwarning(_("No file loaded"), _("Please select a file first"))
            shutil.copy(sfp("data/nofile.pdf"), os.path.join(temp_path_u, "preview.pdf"))
            return False
        if Event != None :
            value_s = self.arw["entry11"].get_text()
            value2_s = self.arw["entry12"].get_text()
            if value_s != "" and value2_s != "" :
                previewPage = int(self.arw["previewEntry"].get_text())
                self.preview(previewPage - 1)
                return
            else :
                return
        self.preview(self.previewPage)


    def previewDelayedUpdate(self, event) :     # Unused : does not work
        return
        print "previewUpdateDelayed"
        try :
            self.t1.cancel()
        except :
            pass
        self.t1 = threading.Timer(1, self.previewUpdate, [event])
        self.t1.start()
        print "timer démarré"

    def preview2(self, widget) :
        global selected_page
        selected_page = None
        previewPage = int(widget.get_text())
        self.preview(previewPage - 1)
        self.previewPage = previewPage - 1

    def _____________________SHUFFLER() :
        pass


    def runPS(self, widget=None) :
        global inputFiles_a, pagesSel

        if len(inputFiles_a) == 0 :
            self.showwarning(_("No selection"), _("There is no selected file. \nPlease select a file first. "))
            return
        if self.shuffler == None :
            self.shuffler = PdfShuffler()
            self.shuffler_window = self.shuffler.uiXML.get_object('main_window')
            self.shuffler.uiXML.get_object('menubar').hide()
            self.shuffler.uiXML.get_object('toolbar1').hide()
            #self.shuffler.uiXML.get_object('menu1_RR').hide()
            #self.shuffler.uiXML.get_object('menu1_RL').hide()
            self.shuffler.uiXML.get_object('menu1_crop').hide()
            self.shuffler.window.set_deletable(False)
            shufflerBB = self.arw['shufflerbuttonbox']
            shufflerBB.unparent()
            vbox = self.shuffler.uiXML.get_object('vbox1')
            vbox.pack_start(shufflerBB, expand=False, fill=True)

            self.loadShuffler()

        else :
            self.shuffler_window.show()


    def loadShuffler(self) :
            render.parsePageSelection("", 0)

            for key in inputFiles_a :
                pdfdoc = PDF_Doc(inputFiles_a[key], self.shuffler.nfile, self.shuffler.tmp_dir)
                if pdfdoc.nfile != 0 and pdfdoc != []:
                    self.shuffler.nfile = pdfdoc.nfile
                    self.shuffler.pdfqueue.append(pdfdoc)

            angle=0
            crop=[0.,0.,0.,0.]
            for page in pagesSel :
                file1, page1 = page.split(":")
                npage = int(page1) + 1
                filenumber = int(file1) - 1
                pdfdoc = self.shuffler.pdfqueue[filenumber]
                if npage > 0 :
                    docPage = pdfdoc.document.get_page(npage-1)
                else :
                    docPage = pdfdoc.document.get_page(0)
                w, h = docPage.get_size()

                # blank page
                if npage == 0 :
                    descriptor = 'Blank'
                    width = self.shuffler.iv_col_width
                    row =(descriptor,         # 0
                          None,               # 1
                          1,                  # 2
                          -1,                 # 3
                          self.zoom_scale,    # 4
                          "",                 # 5
                          0,                  # 6
                          0,0,                # 7-8
                          0,0,                # 9-10
                          w,h,                # 11-12
                          2.              )  # 13 FIXME

                    self.shuffler.model.append(row)
                else :





                    descriptor = ''.join([pdfdoc.shortname, '\n', _('page'), ' ', str(npage)])
                    iter = self.shuffler.model.append((descriptor,         # 0
                                              None,               # 1
                                              pdfdoc.nfile,       # 2
                                              npage,              # 3
                                              self.shuffler.zoom_scale,    # 4
                                              pdfdoc.filename,    # 5
                                              angle,              # 6
                                              crop[0],crop[1],    # 7-8
                                              crop[2],crop[3],    # 9-10
                                              w,h,                # 11-12
                                              2.              ))  # 13 FIXME
                    self.shuffler.update_geometry(iter)
                    res = True

            self.shuffler.reset_iv_width()
            if res:
                self.shuffler.render()
            return res



    def closePS(self) :
        if self.shuffler :
            self.shuffler.rendering_thread.quit = True
            #gtk.gdk.threads_enter()

            if self.shuffler.rendering_thread.paused == True:
                 self.shuffler.rendering_thread.evnt.set()
                 self.shuffler.rendering_thread.evnt.clear()
            self.shuffler_window.destroy()
            self.shuffler= None
            self.shuffler
            self.runPS()

    def getShufflerSel(self, widget):

        selection = []
        for row in self.shuffler.model:
            Id = str(row[2]) + ":" + str(row[3])
            selection += [Id]
            angle = row[7]

            if angle != 0 :
                if angle == 90 :        # In Pdf format, global rotation rotates clockwise,
                    angle = 270         # fine rotation (used by PdfBooklet) rotates counterclockwise.

                elif angle == -90 :
                    angle = 90


            if not Id in self.pagesTr and angle != 0 :
                self.pagesTr[Id] = {}
                # defaults
                self.pagesTr[Id]["htranslate"] = 0
                self.pagesTr[Id]["vtranslate"] = 0
                self.pagesTr[Id]["scale"] = 1
                self.pagesTr[Id]["rotate"] = 0

            if angle != 0 :
                self.pagesTr[Id]["shuffler_rotate"] = angle
##                if angle == 270 :
##                    self.pagesTr[Id]["vtranslate"] = pix_w
##                elif angle == 90 :
##                    self.pagesTr[Id]["htranslate"] = pix_h





        self.selection_s = self.compressSelection(selection)
        self.shuffler_window.hide()
        self.previewUpdate()


    def closeShuffler(self, widget) :
        self.shuffler_window.hide()


    def ________________TRANSFORMATIONS() :
        pass

    def showTransformations(self, widget) :

        if widget.get_active() == True :
            self.arw["transformWindow"].show_all()
            self.arw["transformWindow"].set_keep_above(True)
        else :
            self.arw["transformWindow"].hide()

    def hideTransformations(self, widget) :
            self.arw["transformWindow"].hide()
            self.arw["transformationsbutton"].set_active(False)

    def ta2(self, widget, event = "") :
        print "ta2", event
        self.transformationsApply("")

    def transformationsApply(self, widget, event="", force_update = False) :
        global selected_page, rows_i
        #print "transformations apply"

        if selected_page == None :
            self.showwarning(_("No selection"), _("There is no selected page. \nPlease select a page first. "))
            return
        # selected_page 4 and 5 contain the correct page reference, including the global rotation.
        humanReadableRow_i = rows_i - selected_page[4]
        Id = str(str(humanReadableRow_i) + "," + str(selected_page[5] + 1))

        pageId = str(selected_page[2]) + ":" + str(selected_page[3])

        # if transformation is for this page only, use page ref instead of position ref
        if self.thispage.get_active() == 1 :
            Id = pageId
        if self.evenpages.get_active() == 1 :
            Id = "even"
        if self.oddpages.get_active() == 1 :
            Id = "odd"

        self.pagesTr[Id] = {}
        self.pagesTr[Id]["htranslate"] = self.readmmEntry(self.arw["Htranslate1"])
        self.pagesTr[Id]["vtranslate"] = self.readmmEntry(self.Vtranslate1)
        self.pagesTr[Id]["scale"] = self.readPercentEntry(self.scale1)
        self.pagesTr[Id]["rotate"] = self.readNumEntry(self.rotation1)
        self.pagesTr[Id]["vflip"] = self.arw["vflip1"].get_active()
        self.pagesTr[Id]["hflip"] = self.arw["hflip1"].get_active()
        self.pagesTr[Id]["xscale"] = self.readPercentEntry(self.arw["xscale1"])
        self.pagesTr[Id]["yscale"] = self.readPercentEntry(self.arw["yscale1"])

        self.pagesTr[Id]["htranslate1"] = self.arw["Htranslate1"].get_text()     # data from the gui unmodified
        self.pagesTr[Id]["vtranslate1"] = self.Vtranslate1.get_text()
        self.pagesTr[Id]["scale1"] = self.scale1.get_text()
        self.pagesTr[Id]["rotate1"] = self.rotation1.get_text()
        self.pagesTr[Id]["xscale1"] = self.arw["xscale1"].get_text()
        self.pagesTr[Id]["yscale1"] = self.arw["yscale1"].get_text()

        if not force_update :
            # prevent useless update. If no change, return.
            a = repr(self.pagesTr[Id])
            if self.pagesTr.has_key("memory1") :
                b = self.pagesTr["memory1"]
                if a == b :
                    return
            else :
                self.pagesTr["memory2"] = 0
            self.pagesTr["memory1"] = a
            self.pagesTr["memory2"] += 1

        self.preview(self.previewPage, 0)


    def resetTransformations(self, event = 0) :
        self.arw["Htranslate1"].set_value(0)
        self.arw["Vtranslate1"].set_value(0)
        self.arw["scale1"].set_value(100)
        self.arw["xscale1"].set_value(100)
        self.arw["yscale1"].set_value(100)
        self.arw["rotation1"].set_value(0)
        self.arw["vflip1"].set_active(False)
        self.arw["hflip1"].set_active(False)

        if event != 0 : self.transformationsApply("dummy", force_update = True)
        pass

    def resetTransformations2(self, event = 0) :
        # reset default values for global transformations
        self.arw["Htranslate2"].set_value(0)
        self.arw["Vtranslate2"].set_value(0)
        self.arw["scale2"].set_value(100)
        self.arw["xscale2"].set_value(100)
        self.arw["yscale2"].set_value(100)
        self.arw["rotation2"].set_value(0)
        self.arw["vflip2"].set_active(False)
        self.arw["hflip2"].set_active(False)
        if event != 0 :
            self.arw["globalRotation0"].set_active(1)
            self.previewUpdate()
        pass

    def copy_transformations(self, event) :          # called by context menu
        self.clipboard["htranslate1"] = self.arw["Htranslate1"].get_text()     # data from the gui unmodified
        self.clipboard["vtranslate1"] = self.Vtranslate1.get_text()
        self.clipboard["scale1"] = self.scale1.get_text()
        self.clipboard["rotate1"] = self.rotation1.get_text()
        self.clipboard["this_page"] = self.thispage.get_active()
        self.clipboard["xscale1"] = self.arw["xscale1"].get_text()
        self.clipboard["yscale1"] = self.arw["yscale1"].get_text()
        self.clipboard["vflip1"]  = self.arw["vflip1"].get_active()
        self.clipboard["hflip1"]  = self.arw["hflip1"].get_active()

    def paste_transformations(self, event) :          # called by context menu
         self.arw["Htranslate1"].set_text(self.clipboard["htranslate1"])
         self.Vtranslate1.set_text(self.clipboard["vtranslate1"])
         self.scale1.set_text(self.clipboard["scale1"])
         self.rotation1.set_text(self.clipboard["rotate1"])
         self.thispage.set_active(self.clipboard["this_page"])
         self.arw["xscale1"].set_text(self.clipboard["xscale1"])
         self.arw["yscale1"].set_text(self.clipboard["yscale1"])
         self.arw["vflip1"].set_active(self.clipboard["vflip1"])
         self.arw["hflip1"].set_active(self.clipboard["hflip1"])

         self.transformationsApply("", force_update = True)


    def showwarning(self, title, message) :
        """
          GTK_MESSAGE_INFO,
          GTK_MESSAGE_WARNING,
          GTK_MESSAGE_QUESTION,
          GTK_MESSAGE_ERROR,
          GTK_MESSAGE_OTHER
        """

        resetTransform_b = False
        message = message.encode("utf-8")
        title = title.encode("utf-8")
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING,
                                   gtk.BUTTONS_CLOSE, title)
        dialog.format_secondary_text(message)
        if "transformWindow" in self.arw :
            self.arw["transformWindow"].set_keep_above(False)
            resetTransform_b = True
        dialog.set_keep_above(True)
        dialog.run()
        dialog.destroy()
        if resetTransform_b == True :
            self.arw["transformWindow"].set_keep_above(True)


    def askyesno(self, title, string) :

        string2 = string.encode("utf-8")
        title2 = title.encode("utf-8")

        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_NONE, title2)
        dialog.add_button(gtk.STOCK_YES, True)
        dialog.add_button(gtk.STOCK_NO, False)
        dialog.format_secondary_text(string2)
        dialog.set_keep_above(True)
        rep = dialog.run()
        dialog.destroy()
        return rep

    def get_text(self, parent, message, default=''):
        """
        Display a dialog with a text entry.
        Returns the text, or None if canceled.
        """
        d = gtk.MessageDialog(parent,
                              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                              gtk.MESSAGE_QUESTION,
                              gtk.BUTTONS_OK_CANCEL,
                              message)
        entry = gtk.Entry()
        entry.set_text(default)
        entry.show()
        d.vbox.pack_end(entry)
        entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
        d.set_default_response(gtk.RESPONSE_OK)

        r = d.run()
        text = entry.get_text().decode('utf8')
        d.destroy()
        if r == gtk.RESPONSE_OK:
            return text
        else:
            return None


    def version21(self, widget) :
        self.showwarning("Not yet implemented", "This feature will be implemented in version 2.2")

    def aboutPdfbooklet(self, widget) :
        self.arw["Pdf-Booklet"].show()

    def aboutdialog1_close(self, widget,event) :
        self.arw["Pdf-Booklet"].hide()

    def print2(self, string, cr=0) :        # no  longer used
        global editIniFile

        return
        editIniFile = 0
        enditer = self.text1.get_end_iter()
        self.text1.insert(enditer, string)
        if cr == 1 :
            self.text1.insert(enditer, chr(10))
        iter0 = self.text1.get_end_iter()
        self.arw["text1"].scroll_to_iter(iter0,0)
        #  TODO : bug
        # This command hangs the program (the interface remains blank) when :
        #   a file has been loaded
        #   The page selector has been used
        #   a second file is loaded.
        #while gtk.events_pending():
        #            gtk.main_iteration()

    def test(self,event, dummy = None) :
        print "test"

    def destroyWindow() :
        pass        # commande encore présente dans Glade, à supprimer

    def go(self, button, preview = -1) :

        if self.readGui() :
            if self.render.parsePageSelection() :
                self.readConditions()
                ar_pages, ar_layout = self.render.createPageLayout()
                if ar_pages != None :
                    if self.render.createNewPdf(ar_pages, ar_layout, preview) :
                        if self.arw["show"].get_active() == 1 :

                            if sys.platform == 'linux2':
                                subprocess.call(["xdg-open", outputFile])
                            else:
                                os.startfile(outputFile)

        return [ar_pages, ar_layout]




    def readConditions(self) :
        global optionsDict, config

        return
        if app.arw["entry3"].get() == "" :
            return
        else :
            inifile = app.arw["entry3"].get()
            config = ConfigParser.RawConfigParser()
            config.readfp(open(inifile))
            optionsDict = {}
            optionsDict["pages"] = {}
            optionsDict["conditions"] = {}

            if config.has_section("pages") :
                for a in config.options("pages") :
                    optionsDict["pages"][a] = config.get("pages", a)

            if config.has_section("conditions") :
                for a in config.options("conditions") :
                    optionsDict["conditions"][a] = config.get("conditions", a)


    def test1(self, widget) :
        print "input"
    def test2(self, widget) :
        print "output"
    def test3(self, widget) :
        print "value_changed"
    def test4(self, widget) :
        print "change value"
    def test5(self, widget) :
        print "test5"




class pdfRender():

    def transform(self, row, column, page_number, output_page_number, file_number) :
        global optionsDict, config, rows_i

        # init variables

        V_offset = row * ury_i
        H_offset = column * urx_i
        cos_l = 1
        sin_l = 0

        transform_s = " %s %s %s %s %s %s cm  \n" % (cos_l , sin_l, -sin_l, cos_l , H_offset , V_offset)
        transformations = []

        # Transformations defined in gui

        # Transformations for page in position (row, col)
        section_s = str(rows_i - row) + "," + str(column + 1)
        if app.pagesTr.has_key(section_s) :
            transform_s += self.transform2(section_s)

        # Transformations for page #:#
        pageId = str(file_number) + ":" + str(page_number + 1)
        if app.pagesTr.has_key(pageId) :
            transform_s += self.transform2(pageId)


        # Transformations for even and odd pages
        if page_number % 2 == 1 :
            transform_s += self.transform2("even")
        if page_number % 2 == 0 :
            transform_s += self.transform2("odd")



        # Transformations defined in ini file

        if config.has_section("pages") :
            pages_a = config.options("pages")
            if section_s in pages_a :               # If the layout page presently treated is referenced in [pages]
                temp1 = config.get("pages", section_s)
                transformations += string.split(temp1, ", ")

            if str(page_number + 1) in pages_a :    # If the page presently treated is referenced in [pages]
                temp1 = config.get("pages", str(page_number + 1))
                transformations += string.split(temp1, ", ")


        if config.has_section("conditions") :
            conditions_a = config.options("conditions")
            for line1 in conditions_a :
                condition_s = config.get("conditions", line1)
                command_s, filters_s = string.split(condition_s, "=>")
                if (eval(command_s)) :
                    transformations += string.split(filters_s, ", ")

        for a in transformations :

            transform_s += self.calcMatrix(a)

        return (transform_s)

    def transform2(self, Id) :
        # Calculates matrix for a given section
        matrix_s = ""
        if app.pagesTr.has_key(Id) :
            if not "pdfRotate" in app.pagesTr[Id] :
                app.pagesTr[Id]["pdfRotate"] = 0
            if not "rotate" in app.pagesTr[Id] :
                app.pagesTr[Id]["rotate"] = 0

            if "shuffler_rotate" in app.pagesTr[Id] :
                # we need the page size
                pdfDoc = app.shuffler.pdfqueue[file_number-1]
                page = pdfDoc.document.get_page(page_number)
                pix_w, pix_h = page.get_size()

                angle = int(app.pagesTr[Id]["shuffler_rotate"])
                pdfrotate += angle
                if angle == 270 :
                    vtranslate = float(vtranslate) + float(pix_w)
                elif angle == 90 :
                    htranslate = float(htranslate) + float(pix_h)
                elif angle == 180 :
                    htranslate = float(htranslate) + float(pix_w)
                    vtranslate = float(vtranslate) + float(pix_h)


            matrix_s = self.calcMatrix2(app.pagesTr[Id]["htranslate"],
                                       app.pagesTr[Id]["vtranslate"],
                                       cScale = app.pagesTr[Id]["scale"],
                                       xscale = app.pagesTr[Id]["xscale"],
                                       yscale = app.pagesTr[Id]["yscale"],
                                       cRotate = app.pagesTr[Id]["rotate"],
                                       Rotate = app.pagesTr[Id]["pdfRotate"],
                                       vflip = app.pagesTr[Id]["vflip"],
                                       hflip = app.pagesTr[Id]["hflip"])



        return matrix_s


    def calcMatrix(self, data, myrows_i = 1, mycolumns_i = 1) :
            # Calculate matrix for transformations defined in the configuration
            global config

            trans = string.strip(data)
            cos_l = 1
            cos2_l = 1
            sin_l = 0
            Htranslate = 0
            Vtranslate = 0


            if config.has_option(trans, "PdfRotate") :
                Rotate = config.getint(trans, "PdfRotate")
                sin_l = math.sin(math.radians(Rotate))
                cos_l = math.cos(math.radians(Rotate))
                cos2_l = cos_l

            if config.has_option(trans, "Rotate") :
                try :
                    Rotate = config.getfloat(trans, "Rotate")
                except :
                    pass

                sin_l, cos_l, HCorr, VCorr = self.centeredRotation(Rotate, myrows_i, mycolumns_i)
                cos2_l = cos_l

                Htranslate += HCorr
                Vtranslate += VCorr


            if config.has_option(trans, "Scale") :
                Scale_f = config.getfloat(trans, "Scale")
                cos_l = cos_l * Scale_f
                cos2_l = cos_l

                HCorr = (urx_i * mycolumns_i * (Scale_f - 1)) / 2
                VCorr = (ury_i * myrows_i * (Scale_f - 1)) / 2
                Htranslate -= HCorr
                Vtranslate -= VCorr

            if config.has_option(trans, "xscale") :
                Scale_f = config.getfloat(trans, "xscale")
                cos_l = cos_l * Scale_f

                HCorr = (urx_i * mycolumns_i * (Scale_f - 1)) / 2
                Htranslate -= HCorr

            if config.has_option(trans, "yScale") :
                Scale_f = config.getfloat(trans, "yScale")
                cos2_l = cos2_l * Scale_f

                VCorr = (ury_i * myrows_i * (Scale_f - 1)) / 2
                Vtranslate -= VCorr

            # Vertical flip  : 1 0 0 -1 0 <height>
            if config.has_option(trans, "vflip") :
                cos2_l = cos2_l * (-1)
                Vtranslate += ury_i * myrows_i

            # Horizontal flip  : -1 0 0 1 0 <width>
            if config.has_option(trans, "hflip") :
                cos_l = cos_l * (-1)
                Htranslate += urx_i * mycolumns_i


            if config.has_option(trans, "Htranslate") :
                Htranslate += config.getfloat(trans, "Htranslate") / adobe_l

            if config.has_option(trans, "Vtranslate") :
                Vtranslate += config.getfloat(trans, "Vtranslate") / adobe_l



            if abs(sin_l) < 0.00001 : sin_l = 0          # contournement d'un petit problème : sin 180 ne renvoie pas 0 mais 1.22460635382e-16
            if abs(cos_l) < 0.00001 : cos_l = 0



            transform_s = " %s %s %s %s %s %s cm  \n" % (cos_l , sin_l, -sin_l, cos2_l , Htranslate , Vtranslate)


            if config.has_option(trans, "Matrix") :
                Matrix = config.get(trans, "Matrix")
                transform_s = " %s  cm  \n" % (Matrix)


            return transform_s


    def calcMatrix2(self, Htranslate, Vtranslate,
                          cScale = 1, Scale = 1,
                          Rotate = 0, cRotate = 0,
                          vflip = 0, hflip = 0,
                          xscale = 1, yscale = 1,
                          global_b = False) :
            # calculate matrix for transformations defined in parameters

            Htranslate = float(Htranslate)
            Vtranslate = float(Vtranslate)
            cos_l = 1
            sin_l = 0

            if global_b == True :   # for global transformations, reference for centered scale, rotation and flip is the output page
                myrows_i = rows_i
                mycolumns_i = columns_i
            else :                  # for page transformations, reference is the active source page
                myrows_i = 1
                mycolumns_i = 1

            if Scale != 1:
                Scale_f = float(Scale)
            elif cScale != 1 :
                Scale_f = float(cScale)
            else :
                Scale_f = 1

            if Rotate != 0 :
                sin_l = math.sin(math.radians(float(Rotate)))
                cos_l = math.cos(math.radians(float(Rotate)))
            # TODO Rotate and cRotate are not compatible.
            elif cRotate != 0 :
                sin_l, cos_l, HCorr, VCorr = self.centeredRotation(float(cRotate), myrows_i, mycolumns_i)
                Htranslate += (HCorr * Scale_f)
                Vtranslate += (VCorr * Scale_f)

            if Scale != 1 :
                sin_l = sin_l * Scale_f
                cos_l = cos_l * Scale_f
                HCorr = (urx_i * (Scale_f - 1)) / 2
                VCorr = (ury_i * (Scale_f - 1)) / 2

            if cScale != 1 :
                sin_l = sin_l* Scale_f
                cos_l = cos_l * Scale_f
                HCorr = (urx_i * mycolumns_i * (Scale_f - 1)) / 2
                VCorr = (ury_i * myrows_i * (Scale_f - 1)) / 2

                Htranslate -= HCorr
                Vtranslate -= VCorr


            if abs(sin_l) < 0.00001 : sin_l = 0          # contournement d'un petit problème : sin 180 ne renvoie pas 0 mais 1.22460635382e-16
            if abs(cos_l) < 0.00001 : cos_l = 0

            transform_s = " %s %s %s %s %s %s cm  \n" % (cos_l , sin_l, -sin_l, cos_l , Htranslate , Vtranslate)


            Htranslate = 0
            Vtranslate = 0
            cos_l = 1
            cos2_l = 1
            sin_l = 0


            if xscale != '1' and xscale != 1 :
                xscale = float(xscale)
                cos_l = cos_l * xscale

                HCorr = (urx_i * mycolumns_i * (xscale - 1)) / 2
                Htranslate -= HCorr

            if yscale != '1' and yscale != 1:
                yscale = float(yscale)
                cos2_l = cos2_l * yscale

                VCorr = (ury_i * myrows_i * (yscale - 1)) / 2
                Vtranslate -= VCorr

            if abs(sin_l) < 0.00001 : sin_l = 0          # contournement d'un petit problème : sin 180 ne renvoie pas 0 mais 1.22460635382e-16
            if abs(cos_l) < 0.00001 : cos_l = 0

            transform_s += " %s %s %s %s %s %s cm  \n" % (cos_l , sin_l, -sin_l, cos2_l , Htranslate , Vtranslate)


            Htranslate = 0
            Vtranslate = 0
            cos_l = 1
            cos2_l = 1
            sin_l = 0

            # Vertical flip  : 1 0 0 -1 0 <height>
            if vflip != 0 and vflip != False  :
                cos2_l = cos2_l * (-1)
                Vtranslate += ury_i * myrows_i

            # Horizontal flip  : -1 0 0 1 0 <width>
            if hflip != 0 and hflip != False :
                cos_l = cos_l * (-1)
                Htranslate += urx_i * mycolumns_i



            if abs(sin_l) < 0.00001 : sin_l = 0          # contournement d'un petit problème : sin 180 ne renvoie pas 0 mais 1.22460635382e-16
            if abs(cos_l) < 0.00001 : cos_l = 0
            if abs(cos2_l) < 0.00001 : cos2_l = 0

            transform_s += " %s %s %s %s %s %s cm  \n" % (cos_l , sin_l, -sin_l, cos2_l , Htranslate , Vtranslate)
            return transform_s

    def centeredRotation_old(self, Rotate) :

        Rotate = math.radians(Rotate)
        sin_l = math.sin(Rotate)
        cos_l = math.cos(Rotate)

        # If a is the angle of the diagonale, and R the rotation angle, the center of the rectangle moves like this :
        # Horizontal move = sin(a + R) - sin(a)
        # Vertical move   = cos(a + R) - cos(a)
        #Hence, corrections are sin(a) - sin(a+R) and cos(a) - cos(a-R)

        diag = math.pow((urx_i * urx_i) + (ury_i * ury_i), 0.5)
        alpha = math.atan2(ury_i, urx_i)

        S1 = math.sin(alpha)
        S2 = math.sin(alpha + Rotate)

        C1 = math.cos(alpha)
        C2 = math.cos(alpha + Rotate)

        Vcorr = (S1 - S2) * diag / 2
        Hcorr = (C1 - C2) * diag / 2

        return (sin_l, cos_l, Hcorr, Vcorr)

    def centeredRotation(self, Rotate, myrows_i = 1, mycolumns_i = 1) :

        Rotate = math.radians(Rotate)
        sin_l = math.sin(Rotate)
        cos_l = math.cos(Rotate)

        # If a is the angle of the diagonale, and R the rotation angle, the center of the rectangle moves like this :
        # Horizontal move = sin(a + R) - sin(a)
        # Vertical move   = cos(a + R) - cos(a)
        #Hence, corrections are sin(a) - sin(a+R) and cos(a) - cos(a-R)

        oWidth_i = urx_i * mycolumns_i
        oHeight_i = ury_i * myrows_i

        diag = math.pow((oWidth_i * oWidth_i) + (oHeight_i * oHeight_i), 0.5)
        alpha = math.atan2(oHeight_i, oWidth_i)

        S1 = math.sin(alpha)
        S2 = math.sin(alpha + Rotate)

        C1 = math.cos(alpha)
        C2 = math.cos(alpha + Rotate)

        Vcorr = (S1 - S2) * diag / 2
        Hcorr = (C1 - C2) * diag / 2

        return (sin_l, cos_l, Hcorr, Vcorr)

    def autoScaleAndRotate(self, fileNum, page) :
        global inputFiles_a, inputFile_a, refPageSize_a

        fileName = inputFiles_a[fileNum]
        page0 = inputFile_a[fileName].getPage(page)
        llx_i=page0.mediaBox.getLowerLeft_x()
        lly_i=page0.mediaBox.getLowerLeft_y()
        urx_i=page0.mediaBox.getUpperRight_x()
        ury_i=page0.mediaBox.getUpperRight_y()

        page_width = float(urx_i) - float(llx_i)
        page_height =  float(ury_i) - float(lly_i)

        (ref_width, ref_height) = refPageSize_a

        # check source orientation
        if ref_height > ref_width :
            ref_orientation = "portrait"
        else :
            ref_orientation = "paysage"

        # check page orientation
        if page_height > page_width :
            page_orientation = "portrait"
        else :
            page_orientation = "paysage"


##    if ref_orientation == page_orientation :     # orientation is the same
        delta1 = ref_height / page_height
        delta2 = ref_width  / page_width

        if delta1 < delta2 :
            Scale = delta1
        else:
            Scale = delta2

        return Scale




    def parsePageSelection(self, selection = "", append_prepend = 1) :
        global pagesSel, totalPages, pgcount, input1, numPages, step_i, blankPages
        global inputFiles_a, inputFile_a

        if len(inputFiles_a) == 0 :
            app.showwarning(_("No file loaded"), _("Please select a file first"))
            return False

        if selection == "" :
            selection = app.selection_s

        if selection.strip() == "" :
            i = 1
            for f in inputFiles_a :
                fileName = inputFiles_a[f]
                numPages = inputFile_a[fileName].getNumPages()
                selection += str(i) + ":1-%s;" % (numPages)
                i += 1
            app.selection_s = selection

        if selection == "" :
            app.showwarning(_("No selection"), _("There is no selection"))
            return False

        syntax_s = re.sub("[0-9,;:b\-\s]*", "", selection)    # TODO s'il y a deux virgules (ou ;) successifs, l'erreur n'est pas détectée
        syntax_s = syntax_s.strip()
        if syntax_s != "" :
            app.showwarning(_("Invalid data"), _("Invalid data for Selection : %s. Aborting \n") % syntax_s)
            return False

        if append_prepend == 1 :
            pagesSel = prependPages * ["1:-1"]
        else :
            pagesSel = []


        selection = selection.replace(";", ",")
        selection = selection.strip()
        if selection[-1:] == "," :      # remove the trailing ,
            selection = selection[0:-1]
        list1 = string.split(selection, ",")

        for a in list1 :
            a = a.strip()
            b = a.split(":")
            if (len(b) == 1) :
                docId_s = "1:"
            else :
                docId_s = b[0] + ":"
                a = b[1]

            if string.count(a, "-") > 0:
                list2 = string.split(a, "-")
                serie = range(int(list2[0]) - 1, int(list2[1]) )
                for x in serie :
                    page_s = docId_s + str(x)
                    pagesSel = pagesSel + [page_s]
            elif a[-1:] == "b" :
                if a[0:-1].strip() == "" :
                    blank_pages_i = 1
                else :
                    blank_pages_i = int(a[0:-1])
                pagesSel = pagesSel + (["1:-1"] * blank_pages_i)
            else :
                try :
                    a = str(int(a) - 1)
                    pagesSel = pagesSel + [docId_s + a]
                except :
                    print "Invalid selection ", a
                # TODO : error window : invalid selection
        if append_prepend == 1 :
            pagesSel = pagesSel + appendPages * ["1:-1"]

            if app.booklet > 0 :
                step_i = 2
                blankPages = (len(pagesSel) % -4) * -1
                app.print2(_("Blank pages to be added : %s") % (blankPages) , 1)

            else :
                if step_i < 1 :
                    step_i = 1
                blankPages = (len(pagesSel) % (step_i * -1)) * -1

            pagesSel += ["1:-1"] * blankPages



        totalPages = len(pagesSel)
        pgcount = totalPages

        return True


    def createPageLayout(self, logdata = 1) :
        global config, rows_i, columns_i, cells_i, step_i, sections, output, input1, adobe_l
        global numfolio,prependPages, appendPages, ref_page, selection
        global numPages, blankPages, pagesSel, llx_i, lly_i, urx_i, ury_i, mediabox_l, pgcount

        ar_pages = {}
        index=0
        last=0
        cells_i = columns_i * rows_i


        # Create booklets
        if app.booklet > 0 :

    ##        if cells_i % 2 == 1 :             # booklets must have a total layout multiple of 2
    ##            app.showwarning(_("Invalid data"), _("Columns and rows are incoherent for booklets. \ncolumns x rows must be a multiple of 2"))
    ##            return [None, None]


            multiple_bkt = int(cells_i / 2)
            app.radioDisp= 1


            folios =  pgcount / 4
            if numfolio == 0 :
                numcahiers = 1
            else :
                numcahiers = int(folios / numfolio)

                # equilibrate booklets size

                if (folios % numfolio > 0) :
                    numcahiers = numcahiers + 1

            minfolios = int(folios / numcahiers)
            restefolios = folios - (minfolios * numcahiers)


            ar_cahiers = {}


            for k in range(numcahiers) :

                if (k < restefolios) :
                    ar_cahiers[k] = minfolios + 1
                else :
                    ar_cahiers[k] = minfolios

                first = last + 1
                last = first + (ar_cahiers[k] * 4) - 1

                if logdata == 1 :
                    app.print2(_( "Booklet %s : pages %s - %s") % (k + 1, first, last), 1)

                bkltPages = (last - first) + 1
                for i in range (bkltPages / 2) :


                    if ((i % 2) == 0) :   # Page paire à gauche
                        pg2 = (i + first)
                        pg1 = (last - i)
                    else :
                        pg1 = (i + first)
                        pg2 = (last - i)

                    ar_pages[index] = [pagesSel[pg1 - 1], pagesSel[pg2 - 1]] * multiple_bkt
                    index += 1

        else :
            while index < (pgcount / step_i) :
                start = last          # Start to the last defined position
                last += step_i        # Prepare position for the next loop

                if step_i >= cells_i :
                    last2 = last
                else :
                    last2 = start + cells_i         # this happens for multiple copies of the same page
                                                    # We must have an array of at least (cells_i) elements
                pages = []
                for a in range(start, last2) :
                    PageX = start + (a % step_i)
                    if PageX >= totalPages :
                        pages = pages + [-1]          # ajouter une page blanche
                    else :
                        pages = pages + [pagesSel[PageX]]
                ar_pages[index] = pages
                index += 1


        # create layout
        ar_layout = []
        if app.radioDisp == 1 :
            for r in range(rows_i) :
                r2 = rows_i - (r + 1)       # rows are counted from bottom because reference is lower left in pdf so we must invert
                for c in range (columns_i) :
                    ar_layout += [[r2, c]]
        elif app.radioDisp == 2 :
            for c in range(columns_i) :
                for r in range(rows_i) :
                    r2 = rows_i - (r + 1)   # rows are counted from bottom so we must invert
                    ar_layout += [[r2, c]]

        # If option "Right to left" has been selected creates inverted layout (which will overwrite the previous one)

        if app.righttoleft.get_active() == 1 :

            # create inverted layout
            ar_layout = []
            if app.radioDisp == 1 :
                for r in range(rows_i) :
                    r2 = rows_i - (r + 1)         # rows are counted from bottom because reference is lower left in pdf so we must invert
                    for c in range (columns_i) :
                        c2 = columns_i - (c + 1)  # Invert for right to left option
                        ar_layout += [[r2, c2]]
            elif app.radioDisp == 2 :
                for c in range(columns_i) :
                    c2 = columns_i - (c + 1)      # Invert for right to left optionInvert for right to left option Invert for right to left option
                    for r in range(rows_i) :
                        r2 = rows_i - (r + 1)     # rows are counted from bottom so we must invert
                        ar_layout += [[r2, c2]]

            # End of inverted layout


        # User defined layout
        if app.arw["radiopreset8"].get_active() == 1 :

            # number of sheets of this layout
            sheets = len(app.imposition)

            # create blank pages if necessary
            rest = len(ar_pages) % sheets

            if rest > 0 :
                blank = []
                for i in range(len(ar_pages[0])) :
                    blank.append(["1:-1"])
                for i in range(rest) :
                    ar_pages[len(ar_pages) + i] = blank


            # create a copy of ar_pages

            ar_pages1 = {}
            for key in ar_pages :
                pages1 = ar_pages[key]
                temp = []
                for a in pages1 :
                    temp.append(a)
                ar_pages1[key] = temp


            if sheets == 1 :
                userpages = app.imposition[0]

                for key in ar_pages :
                    pages = ar_pages[key]
                    pages1 = ar_pages1[key]

                    i = 0
                    # we reorder the pages following the order given in userpages
                    for value in userpages :
                        if value == "b" :
                            pages[i] = "1:-1"
                        else :
                            row = int(value) - 1
                            pages[i] = pages1[row]
                        i += 1
                    ar_pages[key] = pages

            elif sheets == 2 :              # more complicated...

                userpagesA = app.imposition[0]
                userpagesB = app.imposition[1]
                step = len(userpagesA)

                for key in range(0,len(ar_pages),2) :

                    pagesA = ar_pages[key]
                    pages1A = ar_pages1[key]
                    pagesB = ar_pages[key + 1]
                    pages1B = ar_pages1[key + 1]


                    i = 0
                    # we reorder the pages following the order given in userpages
                    for value in userpagesA :
                        if value == "b" :
                            pagesA[i] = "1:-1"
                        else :
                            row = int(value) - 1
                            if row < step :
                                index = pages1A[row]
                            else :
                                rowB = row % step
                                index = pages1B[rowB]
                            pagesA[i] = index
                        i += 1
                    i = 0
                    for value in userpagesB :
                        if value == "b" :
                            pagesB[i] = "1:-1"
                        else :
                            row = int(value) - 1
                            if row < step :
                                index = pages1A[row]
                            else :
                                rowB = row % step
                                index = pages1B[rowB]
                            pagesB[i] = index
                        i += 1
                    ar_pages[key] = pagesA
                    ar_pages[key + 1] = pagesB


        return (ar_pages, ar_layout)



    def createNewPdf(self, ar_pages, ar_layout, preview = -1) :
        global outputFile, debug_b, inputFile_a, inputFiles_a, previewtempfile, result

        if debug_b == 1 :
            logfile_f = open ("log.txt", "wb")
        # status
        statusTotal_i = len(ar_pages)
        statusValue_i = 1


        time_s=time.time()
        output = PdfFileWriter()
        # Verify that the output file may be written to

        if app.arw["entry2"].get_text() == "" :
            inputFile = inputFiles_a[1]
            inputFile_name = os.path.splitext(inputFile)[0]
            outputFile = inputFile_name + "-bklt.pdf"
        else :
            outputFile = app.arw["entry2"].get_text()
            inputFile = inputFiles_a[1]
            inputFile_wo_ext = os.path.splitext(inputFile)[0]
            (inputFile_path, inputFile_name) = os.path.split(inputFile)
            (inputFile_basename, inputFile_ext) = os.path.splitext(inputFile_name)
            inputFile_path += "/"
            inputFile_ext = inputFile_ext[1:]


            outputFile = outputFile.replace("%F", inputFile_wo_ext)
            outputFile = outputFile.replace("%N", inputFile_name)
            outputFile = outputFile.replace("%B", inputFile_basename)
            outputFile = outputFile.replace("%P", inputFile_path)
            outputFile = outputFile.replace("%E", inputFile_ext)


        if preview >= 0 :
            outputStream = file(os.path.join(temp_path_u, "preview.pdf"), "wb")
        else :
            if os.path.isfile(outputFile) :
                if app.overwrite.get_active() == 0 :
                    answer_b = app.askyesno(_("File existing"), _("The outputfile already exists \n" \
                    "overWrite ? " ))
                    if False == answer_b :
                        return False

            try :
                outputStream = file(outputFile, "wb")
            except :
                app.showwarning(_("File already open"), _("The output file is already opened \n" \
                "probably in Adobe Reader. \n" \
                "Close the file and start again"))
                return

        if preview >= 0 :
            output_page_number = preview + 1
        else :
            output_page_number = 1
            # encryption
            if app.permissions_i != -1 and app.password_s != "" :       # if permissions or password were present in the file
                output.encrypt("", app.password_s, P = app.permissions_i)     # TODO : there may be two passwords (user and owner)
        for a in ar_pages :
            # create the output sheet
            page2 = output.addBlankPage(100,100)
            newSheet = page2.getObject()
            newSheet.mediaBox.upperRight = mediabox_l       # output page size
            newSheet.cropBox.upperRight = mediabox_l
            if app.arw["globalRotation0"].get_active() == 0 :
                if app.arw["globalRotation90"].get_active() == 1 :
                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(90)
                elif app.arw["globalRotation180"].get_active() == 1 :
                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(180)
                else :
                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(270)

            i = 0
            ar_data = []


            if outputScale <> 1 and app.autoscale.get_active() == 1 :
                temp1 = "%s 0 0 %s 0 0 cm \n" % (str(outputScale), str(outputScale))
                ar_data.append([temp1])

            #Output page transformations
            OHShift = app.readmmEntry(app.arw["Htranslate2"],
                                  _("Output page Horizontal Shift"))
            if OHShift == None : return False
            OVShift = app.readmmEntry(app.arw["Vtranslate2"],
                                  _("Output page Vertical Shift"))
            if OVShift == None : return False
            OScale  = app.readPercentEntry(app.arw["scale2"],
                                       _("Output page Scale"))
            if OScale == None : return False

            ORotate = app.readNumEntry(app.arw["rotation2"],
                                   _("Output page Rotation"))
            if ORotate == None : return False

            Ovflip = app.arw["vflip2"].get_active()
            Ohflip = app.arw["hflip2"].get_active()

            Oxscale = app.readPercentEntry(app.arw["xscale2"],
                                   _("Output page scale horizontally"))
            if Oxscale == None : return False

            Oyscale = app.readPercentEntry(app.arw["yscale2"],
                                   _("Output page scale vertically"))
            if Oyscale == None : return False



            temp1 = self.calcMatrix2(OHShift, OVShift,
                                     cScale = OScale,
                                     cRotate = ORotate,
                                     vflip = Ovflip,
                                     hflip = Ohflip,
                                     xscale = Oxscale,
                                     yscale = Oyscale,
                                     global_b = True)
            ar_data.append([temp1])



            # Transformations defined in ini file


            if config.has_section("pages") :
                pages_a = config.options("pages")
                if "@" + str(output_page_number) in pages_a :               # If the output page presently treated is referenced in [pages]
                    temp1 = config.get("pages", "@" + str(output_page_number))
                    transformations = string.split(temp1, ", ")
                    for name_s in transformations :
                        if config.has_option(name_s, "globalrotation") :
                            gr_s = config.get(name_s.strip(), "globalrotation")
                            gr_i = int(gr_s)
                            if gr_i == 90 :
                                newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(90)
                            elif gr_i == 180 :
                                newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(180)
                            elif gr_i == 270 :
                                newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(270)
                        else :
                            transform_s = self.calcMatrix(name_s, rows_i, columns_i)
                            ar_data.append([transform_s])




            if config.has_section("output_conditions") :
                conditions_a = config.options("output_conditions")
                for line1 in conditions_a :
                    condition_s = config.get("output_conditions", line1)
                    command_s, filters_s = string.split(condition_s, "=>")
                    if (eval(command_s)) :
                        transformations = string.split(filters_s, ", ")
                        for name_s in transformations :
                            if config.has_option(name_s.strip(), "globalrotation") :
                                gr_s = config.get(name_s.strip(), "globalrotation")
                                gr_i = int(gr_s)
                                if gr_i == 90 :
                                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(90)
                                elif gr_i == 180 :
                                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(180)
                                elif gr_i == 270 :
                                    newSheet[generic.NameObject("/Rotate")] = generic.NumberObject(270)
                            else :
                                transform_s = self.calcMatrix(name_s, rows_i, columns_i)
                                ar_data.append([transform_s])


            oString = ""

            for r, c in ar_layout :
                data_x = []
                if ar_pages[0] == [] :      # system not yet initialised
                    return
                file_number, page_number = string.split(ar_pages[a][i], ":")
                file_number = int(file_number)
                page_number = int(page_number)
                if (page_number < 0) :
                    i += 1
                    continue          # blank page


                data_x.append("q\n")
                matrix_s = self.transform(r, c, page_number, output_page_number, file_number)
                if matrix_s == False : return False
                data_x.append(matrix_s)

                if app.autoscale.get_active() == 1 :
                    scaleFactor_f = self.autoScaleAndRotate(file_number, page_number)
                    matrix1_s = self.calcMatrix2(0, 0, Scale = scaleFactor_f)
                    data_x.append(matrix1_s)

                file_name = inputFiles_a[file_number]
                newPage = inputFile_a[file_name].getPage(page_number)

                data_x.append(newPage)
                data_x.append("Q\n")
                ar_data.append(data_x)

                i += 1



            datay = []
            for datax in ar_data :
                datay += datax + ["\n"]
            newSheet.mergePage3(datay)


            if app.noCompress.get_active() == 0 :
                newSheet.compressContentStreams()


            if preview == -1 :      # if we are creating a real file (not a preview)
                message_s = _("Assembling pages: %s ")   % (ar_pages[a])
                app.print2( message_s , 1)
                app.status.set_text("page " + str(statusValue_i) + " / " + str(statusTotal_i))
                statusValue_i += 1
            output_page_number += 1
            while gtk.events_pending():
                            gtk.main_iteration()

        time_e=time.time()

        app.print2(_("Total length : %s ") % (time_e - time_s), 1)

        output.write(outputStream)
        outputStream.close()
        del output


        if debug_b == 1 :
            logfile_f.close()

        if preview == -1 :      # if we are creating a real file (not a preview)
            if app.settings.get_active() == 1 :
                app.saveProjectAs("",inputFile + u".ini")

        return True




def printTree(source,page,out) :

        curPage = source.getPage(page)
        keys_a = curPage.keys()
        #temp1 = curPage["/Parent"].getObject()
        for j in keys_a :
            #if j in ["/Parent", "/Rotate", "/MediaBox", "/Type", "/Annots", "/Contents"] :
            if j in ["/Parent"] :
                continue
            temp1 = curPage[j].getObject()
            print >> out, "======> page "  + str(page) + "  " + j
            print >> out, temp1
            if isinstance(temp1, dict) :
                for k in temp1 :
                    temp2 = temp1[k].getObject()
                    print >> out, str(k) + " : ",
                    print >> out, temp2
                    if isinstance(temp2, dict) :
                        for l in temp2 :
                            temp3 = temp2[l].getObject()
                            print >> out, str(l) + " : ",
                            print >> out, temp3
                            if isinstance(temp3, dict) :
                                for m in temp3 :
                                    temp4 = temp3[m].getObject()
                                    print >> out, str(m) + " : ",
                                    print >> out, temp4
                                    if isinstance(temp4, dict) :
                                        for n in temp4 :
                                            temp5 = temp4[n].getObject()
                                            print >> out, str(n) + " : ",
                                            print >> out, temp5

    #out.close()


def parseOptions() :
    global arg_a
    parser = OptionParser()
    parser.add_option("-f", "--file", dest="filename",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-r", "--rows", dest="rows_i",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-c", "--columns", dest="columns_i",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-n", "--numfolio", dest="numfolio",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-b", "--booklet", dest="booklet",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-a", "--appendPages", dest="appendPages",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-p", "--prependPages", dest="prependPages",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-s", "--selection", dest="selection",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-o", "--output", dest="outputFile",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-i", "--iniFile", dest="iniFile",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("-e", "--referencePage", dest="referencePage",
                      help="write report to FILE", metavar="FILE")

    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")

    (option_v, arg_a) = parser.parse_args()


##    if None != option_v.iniFile :
##            ini_s = option_v.iniFile
##            parseIniFile(ini_s)


def extractBase() :
    """
    extract absolute path to script
    @return prog_s : absolute program path
    @return pwd_s : current working dir
    @return base_s : dirname of prog_s
    """

    # read current dir
    prog_s = sys.argv[0]
    pwd_s = os.path.abspath(".")
    name_s = os.path.basename(prog_s)
    _sep_s = '\\'

    # extract program path
    # if path starts with \ or x:\ absolute path
    if _sep_s == prog_s[0] or \
       (2 < len(prog_s) and \
        ":" == prog_s[1] and
        _sep_s == prog_s[2]) :
        base_s = os.path.dirname(prog_s)
    # if it starts with ./  , relative path
    elif 1 < len(prog_s) and \
         "." == prog_s[0] and \
         _sep_s == prog_s[1] :
        path_s = os.path.abspath(prog_s)
        base_s = os.path.dirname(path_s)
    # if it is in the active directory
    elif os.path.exists(os.path.join(pwd_s, prog_s)) or \
        os.path.exists(os.path.join(pwd_s, prog_s) + ".exe"):       # Necessary if the user starts the program without the extension (maggy, without .exe)
        path_s = os.path.join(pwd_s, prog_s)
        base_s = os.path.dirname(path_s)
    else :
        tab_a = os.environ["PATH"].split(":")
        limit = len(tab_a)
        found = False
        for scan in range(limit) :
            path_s = os.path.join(tab_a[scan], prog_s)
            if os.path.exists(path_s) :
                base_s = os.path.dirname(path_s)
                found = True
                break
        if not found :
            raise ScriptRt("path to program is undefined")

    # application base import
    return(name_s, pwd_s, base_s)


def sfp(path) :
    # sfp = set full path
    return os.path.join(prog_path_u, path)

def sfp2(file) :
    # sfp2 = set full path, used for temporary directory
    return os.path.join(cfg_path_u, file)



def close_applicationx(self, widget, event=None, data=None):

    if gtk.main_level():
        app.arw["window1"].destroy()
        gtk.main_quit()
    else:
        sys.exit(0)

    return False

###########################################################################
# MAIN ####################################################################
###########################################################################

def main() :

    global PdfShuffler, PDF_Doc

    from pdfshuffler_g import PdfShuffler, PDF_Doc

    global isExcept
    global startup_b
    global preview_b
    global project_b
    global openedProject_u
    global thumbnail
    global areaAllocationW_i
    global areaAllocationH_i

    global base_a
    global prog_path_u
    global temp_path_u
    global cfg_path_u

    isExcept = False
    startup_b = True
    preview_b = True
    project_b = False
    openedProject_u = ""
    thumbnail = ""
    areaAllocationW_i = 1
    areaAllocationH_i = 1

    base_a = extractBase()
    prog_path_u = unicode2(base_a[2])


    errorLog = sys.argv[0] + ".log"
    argv_a = sys.argv
    sys.argv = [sys.argv[0]]            # remove any parameter because they are not supported by PdfShuffler
    if os.path.exists(sfp(errorLog)) :
        try :           # Sometimes the file may be locked
            os.remove(sfp(errorLog))
        except :
            pass

    # set directories for Linux and Windows

    if sys.platform == 'linux2':
        if os.path.isdir("/var/tmp/pdfbooklet") == False :
            os.mkdir("/var/tmp/pdfbooklet")
        temp_path_u = u"/var/tmp/pdfbooklet"
        cfg_path_u = temp_path_u
        if prog_path_u[-4:] == "/bin" :
            temp_u = prog_path_u[0:-4]
        else :
            temp_u = prog_path_u
        if os.path.isdir(os.path.join(temp_u,"share/pdfbooklet/data")) :
            prog_path_u = os.path.join(temp_u, "share/pdfbooklet")
        elif os.path.isdir("/usr/share/pdfbooklet/data") :
            prog_path_u = "/usr/share/pdfbooklet"
        elif os.path.isdir("/usr/local/share/pdfbooklet/data") :
            prog_path_u  = "/usr/local/share/pdfbooklet"

        if os.path.isfile(sfp("data/nofile.pdf")) :
            shutil.copy(sfp("data/nofile.pdf"), "/var/tmp/pdfbooklet/preview.pdf")



    else:
        if os.path.isdir(sfp("tempfiles")) == False :
            os.mkdir(sfp("tempfiles"))
        temp_path_u = os.path.join(prog_path_u, "tempfiles")
        cfg_path_u = prog_path_u
        if os.path.isfile(sfp("data/nofile.pdf")) :
            shutil.copy(sfp("data/nofile.pdf"), os.path.join(temp_path_u, "preview.pdf"))




    #parseOptions()

    try:


        global render, app
        global inputFiles_a

        render = pdfRender()
        app = gtkGui(render)

        app.guiPresetsShow("booklet")
        app.resetTransformations(0)
        app.resetTransformations2(0)
        app.guiPresets(0)



        if os.path.isfile(sfp2("pdfbooklet.cfg")) == False :
            f1 = open(sfp2("pdfbooklet.cfg"), "w")
            f1.close()
        app.parseIniFile(sfp2("pdfbooklet.cfg"))


        if len(argv_a) > 1 :
            if len(argv_a[1]) > 0 :
                inputFiles_a = {}
                inputFiles_a[1] = argv_a[1]
                app.loadPdfFiles()
                app.selection_s = ""
                app.arw["previewEntry"].set_text("1")
                while gtk.events_pending():
                            gtk.main_iteration()
                app.previewUpdate()

        ##if len(arg_a) > 0 :
        ##    app.treestore.clear()
        ##    app.treestore.append([arg_a[0], ""])


##        if len(inputFiles_a) > 0 :
##            app.preview(0)



        startup_b = False

        gtk.gdk.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()

        os._exit(0) # required because pdf-shuffler does not close correctly



    except :
        isExcept = True
        excMsg_s = "unexpected exception"
        (excType, excValue, excTb) = sys.exc_info()
        tb_a = traceback.format_exception(excType, excValue, excTb)
        for a in tb_a :
            print a

    # handle eventual exception
    if isExcept :

        if app.shuffler != None :
            app.shuffler.window.destroy()
        if gtk.main_level():
            gtk.gdk.threads_enter()
            gtk.main_quit()
            gtk.gdk.threads_leave()
            #os._exit(0)
            sys.exit(1)
        else:
            sys.exit(1)




if __name__ == '__main__' :
    main()
