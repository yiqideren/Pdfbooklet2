#!/usr/bin/python

#
# 
import os
import re
import glob
from ftplib import FTP


version = "2.3.2"



ftp = FTP('privftp.pro.proxad.net')     # connect to host, default port
x = ftp.login('webmaster@chartreux.org', '-esoJnaS@')                     # user anonymous, passwd anonymous@
print x
ftp.cwd('transit')               # change into "debian" directory
#ftp.retrlines('LIST')           # list directory contents
#ftp.retrbinary('RETR Archeotes.sqlite', open('Archeotes.sqlite', 'wb').write)
x = ftp.storbinary('STOR ' + deb_file[2:], open(deb_file, 'rb'))
print x
ftp.quit()



  





#os.system('rpmrebuild -b -R --change-spec-requires rebuild.py -p ' + new_file )


"""
# Clean up temporary files
if os.path.isdir('mo/'):
    os.system ('rm -r mo/')
if os.path.isdir('build/'):
    os.system ('rm -r build/')
"""
