#!/usr/bin/python
# coding: utf-8 -*-

# version 1.2
# Bug fix : Files with accent in the path were not opened 

import os

import pygtk
import gtk
import pango
import gio

from pdf import PdfFileReader

### If gettext can't load, we must define the _(...) function
##if os.path.isfile("./locale/gui/LC_MESSAGES/pdfBooklet.mo") == False :
##    def _(string) :
##        return string


class Chooser:
    def __init__(self, 
                 inputFiles_a = None,
                 prog_path_u = "",
                 mru_dir = ""):


        self.inputFiles_a = inputFiles_a
        self.chooser1 = gtk.Builder()
        self.chooser1.add_from_file(os.path.join(prog_path_u, 'data/chooser_dialog.glade'))
        self.chooser1.connect_signals(self)
        self.chooser = self.chooser1.get_object("filechooserdialog1")

        # treeview
        self.treeview1 = self.chooser1.get_object("treeview1")

        # create a TreeStore with one string column to use as the model
        #self.treestore = self.treeview1.get_model()
        self.treestore = gtk.ListStore(str,int)
        self.cell = gtk.CellRendererText()

        # set the model for TreeView
        self.treeview1.set_model(self.treestore)
        self.tvcolumn = gtk.TreeViewColumn(_('Filename'))
        self.treeview1.append_column(self.tvcolumn)

        # add the cell to the tvcolumn and allow it to expand
        self.tvcolumn.pack_start(self.cell, True)

        # set the cell "text" attribute to column 0 - retrieve text
        # from that column in treestore
        self.tvcolumn.add_attribute(self.cell, 'text', 0)

##        self.tvcolumn = gtk.TreeViewColumn(_('Pages'))
##        self.treeview1.append_column(self.tvcolumn)
##        self.tvcolumn.pack_start(self.cell, True)
##        self.tvcolumn.add_attribute(self.cell, 'text', 1)

        # Allow drag and drop reordering of rows
        self.treeview1.set_reorderable(True)

        # load files in parameter list
        for key in self.inputFiles_a :
            self.treestore.append([self.inputFiles_a[key], 0])


        old_dir = ""
        old_name = ""


        chooser = self.chooser1.get_object("filechooserdialog1")
        chooser.set_current_folder(mru_dir)
        chooser.set_select_multiple(True)

        filter_all = gtk.FileFilter()
        filter_all.set_name(_('All files'))
        filter_all.add_pattern('*')
        chooser.add_filter(filter_all)

        filter_pdf = gtk.FileFilter()
        filter_pdf.set_name(_('PDF files'))
        filter_pdf.add_mime_type('application/pdf')
        chooser.add_filter(filter_pdf)
        chooser.set_filter(filter_pdf)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            for filename in chooser.get_filenames():
                filename = unicode(filename, "utf-8")
                if os.path.isfile(filename):
                    # FIXME
                    f = gio.File(filename)
                    f_info = f.query_info('standard::content-type')
                    mime_type = f_info.get_content_type()
                    if mime_type == 'application/pdf' or mime_type == '.pdf':
                        self.loadPdfFile(filename)
                    else :
                        print(_('File type not supported!'))
                else:
                    print(_('File %s does not exist') % filename)
        elif response == gtk.RESPONSE_CANCEL:
            print(_('Closed, no files selected'))

    def chooserClose(self, widget) :
        self.chooser.destroy()

    def chooserOK(self, widget) :
        self.treestore.clear()
        self.genFilesArray()
        self.chooser.destroy()

    def pdf_remove(self, widget) :
        selection = self.treeview1.get_selection()
        #sel = selection.get_selected_rows()
        model, iter0 = selection.get_selected()
        model.remove(iter0)

    def pdf_up(self, widget) :
        selection = self.treeview1.get_selection()
        model, iter0 = selection.get_selected()
        string = model.get_string_from_iter(iter0)
        newpos = int(string) - 1
        if newpos < 0 : newpos = 0
        newpos = model.get_iter_from_string(str(newpos))
        model.move_before(iter0, newpos)

    def pdf_down(self, widget) :
        selection = self.treeview1.get_selection()
        model, iter0 = selection.get_selected()
        model.move_after(iter0, model.iter_next(iter0))

    # clears the list and open a file
    def pdf_open(self,widget) :
        self.treestore.clear()
        self.add_file("")

    def add_file(self, widget):

        for filename in self.chooser.get_filenames():
                filename = unicode(filename, "utf-8")
                if os.path.isfile(filename):
                    # FIXME
                    f = gio.File(filename)
                    f_info = f.query_info('standard::content-type')
                    mime_type = f_info.get_content_type()
                    if mime_type == 'application/pdf' or mime_type == '.pdf':
                        self.loadPdfFile(filename)
                    else :
                        print(_('File type not supported!'))
                else:
                    print(_('File %s does not exist') % filename)


    def loadPdfFile(self,filename) :

        pdfFile = PdfFileReader(file(filename, "rb"))
        numpages = pdfFile.getNumPages()
        self.treestore.append([filename, numpages])

    # regenerate the array of files (easier to use than the treestore)
    def genFilesArray(self, dummy = "") :        
        inputFiles_a = {}
        selectedFiles1 = self.chooser.get_filenames()
        # eliminate directories
        selectedFiles = []
        for file_s in selectedFiles1 :
            file_u = unicode(file_s,"utf-8")
            if os.path.isdir(file_u) :
                pass
            else :
                selectedFiles.append(file_u)            

        size_i = len(self.treestore)

        if size_i == 0 :        # nothing in the list
            for i in range(len(selectedFiles)) :
                inputFiles_a[i + 1] = selectedFiles[i]
        else :                      # use the list
            for i in range(size_i) :
                iter0 = self.treestore.get_iter(i)
                filename_s = self.treestore.get_value(iter0,0)
                inputFiles_a[i + 1] = unicode(filename_s, "utf-8")
        self.inputFiles_a = inputFiles_a


