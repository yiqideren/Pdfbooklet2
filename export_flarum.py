#!/usr/bin/python

#
#
import os
import re
import glob
from ftplib import FTP
import zipfile

version = "2.3.2"

# create zipfile

output = zipfile.ZipFile("./essai.zip", "w", zipfile.ZIP_DEFLATED)

files_list1 = []
for files1 in  os.walk(os.path.join("./")) :
    dir1 = files1[0]
    for file1 in files1[2] :
        path1 = os.path.join(dir1,file1)
        if os.path.isfile(path1) :
            output.write(path1, path1)




##files_list = glob.glob(os.path.join("./", u"*"))     # add all config files
##for filename_u in files_list :
##    if os.path.isfile(filename_u) :
##        output.write(filename_u, os.path.split(filename_u)[1])

msg2 = output.namelist()
output.close()

ftp = FTP('privftp.pro.proxad.net')     # connect to host, default port
x = ftp.login('webmaster@chartreux.org', 'esoJnaS')                     # user anonymous, passwd anonymous@
ftp.cwd('transit')               # change into "debian" directory
x = ftp.storbinary('STOR ' + "essai.zip", open("./essai.zip", 'rb'))
ftp.quit()


