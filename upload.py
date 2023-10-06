#!/usr/bin/env python3

"""
A simple CGI script to accept uploaded files.

Written by Andrew Plotkin and many contributors.
Originally adapted from a script by Tim Middleton.

This script must run in a UTF-8 locale, or Unicode input will cause horrible
errors. The Apache config contains the line "SetEnv LANG en_US.UTF-8", which
takes care of this.
"""

# Andrew Plotkin (6 Oct 2023):
#   - Read a config file for configurable (and nonpublic) info.
# Andrew Plotkin (30 Sep 2023):
#   - Improved the filename-cleaning code.
#   - Bumped upload-dir limit.
# Andrew Plotkin (27 May 2018):
#   - Added an "accept the terms of service" checkbox.
# Andrew Plotkin (23 November 2017):
#   - Update to use subprocess instead of os.popen.
# Andrew Plotkin (25 July 2017):
#   - Rewrote the whole script in Python 3.
#   - Put all the HTML templates in /var/ifarchive/lib/uploader.
#   - Added the "right to use" checkboxes.
#   - Cleaned up lots of grotty old code.
# Andrew Plotkin (18 June 2017):
#   - Uploaded file details are logged to web-upload.log as well as being
#     emailed to webuploader@ifarchive.org.
# Doug Orleans (22 Feb 2017):
#   - Added my name to the footer, to match the footer everywhere else.
# Stephen Granade (3 May 2010):
#   - Added support for storing IDs from IFDB
#   - Filename-mangling code now allows spaces
# Goob (10 July 2008):
#   - repointed mail to webuploader@ifarchive.org
# Stephen Granade (27 March 2006):
#   - Added "Suggested Directory" to form
# Stephen Granade (13 September 2004):
#   - Filename-mangling code had an error that only showed up when
#     given a filename from Internet Explorer
# Stephen Granade (22 June 2004):
#   - Email now lists filename in the subject line
# Further Stephen Granade edits (18 April 2004):
#   - Filename-mangling code now much more paranoid
# Stephen Granade edits (28 Feb 2004):
#   - Form now includes uploader's name, email address, and file description
#   - Notification email has Reply-To: set to uploader's email
#   - Notification email includes uploader's name, email, and file desc
#   - Removed any mention of exact upload limits
#   - Overall look & feel closer to IF Archive standard
#   - Logs all uploads
#   - New uploads don't clobber old ones. Instead, a timestamp is
#     appended to the new upload's filename
#   - Upload errors are caught and logged
# Hacked a bit for the ifarchive server by Goob, 2/25/04

import sys
import os
import io
import subprocess
import cgi
import configparser
import string
import logging
import time
import traceback
import re
import shelve
import hashlib

# First, some constants. Some of these are taken from a config file.

configpath = '/var/ifarchive/lib/ifarch.config'
config = configparser.ConfigParser()
config.read(configpath)

# Directory in which to find template files.
dirLibFiles = "/var/ifarchive/lib/uploader"

# Directory for upload; will be created if doesn't exist.
dirUpload = "/var/ifarchive/incoming"

# Logs will be written here. The file must be chown www-data.
logfile = "/var/ifarchive/logs/web-upload.log"

# Database of IFDB IDs.
ifdbIdFile = config['DEFAULT']['IFDBIdMapFile']

# Maximum size of upload directory (in bytes) before no more files
# are accepted.
maxdirsize = config['DEFAULT'].getint('MaxIncomingDirSize')

# Current size of upload directory (in bytes). Will compute before
# running the form.
totaldirsize = None

# Where to email upload reports.
email = "webuploader@ifarchive.org"

# Mail-sending tool.
sendmail = "/usr/sbin/sendmail"

# Utility functions...

def write_template(filename, map):
    """Read a template file from the lib directory, perform the
    substitutions in the map file, and print the result.

    This is a very simple substitution engine. I know, we have a much
    nicer one in ifmap.py, but this is a CGI script and I want to keep
    it simple.
    """
    text = get_template(filename)

    for (key, val) in map.items():
        key = '{'+key+'}'
        text = text.replace(key, val)

    print(text)

def get_template(filename):
    """Read a template file from the lib directory and return its contents.
    """
    fl = open(os.path.join(dirLibFiles, filename), encoding='utf-8')
    text = fl.read()
    fl.close()
    return text
    
def plural(s,num):
    """
    Make plural words as nicely as possible.
    """
    if num != 1:
        if s[-1] == "s" or s[-1] == "x":
            s = s + "e"
        s = s + "s"
    return s

def fix_line_endings(val):
    """
    Cheap attempt to repair DOS-style strings.
    """
    return val.replace('\r', '')

def strip_dirs(fn):
    """Remove directory names from a path.
    """
    # Strip out the directory part of any filename (up to the last slash).
    # We consider both Windows and regular slashes here, although
    # only regular slashes should turn up.
    # (Old code also considered the colon, which was a path separator in
    # classic MacOS. I've dropped that.)
    _, _, fn = fn.rpartition('/');
    _, _, fn = fn.rpartition('\\');
    if not fn:
        fn = 'file'
    return fn

def clean_filename(fn):
    """Clean a filename from the HTML form. We replace characters considered
    unsafe with underscores. Safe is alphanumerics plus [+-=_. ].
    """
    fn = re.sub('[^a-zA-Z0-9 +=_.-]+', lambda ch:'_', fn)
    return fn

def mailme(msg="", name="", nemail="", mailsubj="Upload Report"):
    """Quick and dirty, pipe a message to sendmail, appending
    various environmental variables to the message. Also log the
    same information.
    """
    headerlist = [ 'REQUEST_URI','HTTP_USER_AGENT','REMOTE_ADDR','HTTP_FROM','REMOTE_HOST','REMOTE_PORT','SERVER_SOFTWARE','HTTP_REFERER','REMOTE_IDENT','REMOTE_USER','QUERY_STRING','DATE_LOCAL' ]
    
    if email:
        try:
            fl = io.StringIO()
            fl.write("To: %s\n" % email)
            fl.write("From: %s\n" % email)
            fl.write("Subject: %s\n" % mailsubj)
            if (nemail != ""):
                tempstr = "<" + nemail + ">"
                if (name != ""):
                    tempstr = name + " " + tempstr
                fl.write("Reply-To: %s\n" % tempstr)
            fl.write("\n")
            fl.write("%s\n" % msg)
            fl.write("---------------------------------------\n")
            for x in headerlist:
                if x in os.environ:
                    fl.write("%s: %s\n" % (x, os.environ[x]))
            fl.write("---------------------------------------\n")
            bytemsg = fl.getvalue().encode('utf-8')
            fl.close()
            subprocess.run([sendmail, '-t'], input=bytemsg, check=True)
        except IOError:
            pass                                        

    logger.info('Upload subject: %s' % (mailsubj,))
    logger.info('Upload message: %s' % (msg,))
    for x in headerlist:
        if x in os.environ:
            logger.info('Upload env: %s: %s' % (x, os.environ[x],))
            
def errpage(message):
    """Print a generic error page.
    The message must be HTML-escaped and preferably wrapped with <p>
    tags.
    """
    footer = get_template('footer.html')
    map = { 'errorparas':message, 'footer':footer }
    write_template('error.html', map)

def form(data, posturl):
    """Print the main form. This includes the GET case (no files
    uploaded yet) and the POST case (form submitted with files).
    """
    footer = get_template('footer.html')

    if "file.1" not in data:
        # No files, show the primary form.
        if totaldirsize < maxdirsize:
            button = 'type="submit" value="Upload File"'
        else:
            button = 'type="button" value="Upload Disabled (upload directory is full)"'

        map = { 'footer':footer, 'posturl':posturl, 'button':button }
        write_template('main.html', map)
        return

    # We have uploads!

    tosval = data.getfirst('tos', None)
    if not tosval:
        msg = """You must agree to the Terms of Use in order to upload files to the Archive."""
        errpage('<p>'+msg+'</p>')
        return

    rightsval = data.getfirst('rights', None)
    if not rightsval:
        msg = """Please select whichever of the "Right to use" options applies to your upload."""
        errpage('<p>'+msg+'</p>')
        return

    if totaldirsize >= maxdirsize:
        # We don't publicize the maximum size.
        msg = """There are already too many files in the upload area, preventing your files from being uploaded. We apologize for the inconvenience."""
        errpage('<p>'+msg+'</p>')
        mailme(msg)
        return

    if not os.path.exists(dirUpload):
        os.mkdir(dirUpload, 0o777)

    # This code originally accepted multiple files in a single
    # form submission. The current form does not support this,
    # but we keep the old loop in case we ever put it back.
    fnList = []
    kbList = []
    tsList = []
    kbCount = 0
    f = 1
    while f:
        key = "file.%s" % f
        if key in data:
            fn = data[key].filename
            if not fn:
                f = f + 1
                continue

            # Clean the filename. Strip off the dir part of the path, if
            # any (that's ofn); then clean out unsafe characters (that's fn).
            ofn = strip_dirs(fn)
            fn = clean_filename(fn)

            # If the file already exists, add a timestamp to the new filename
            if os.path.isfile(os.path.join(dirUpload, fn)):
                timestamp = "."+str(time.time())
            else:
                timestamp = ""

            # Try opening the file, exiting on error
            try:
                o = open(os.path.join(dirUpload, fn)+timestamp, "wb")
                o.write(data[key].value)
                o.close()
            except:
                logger.error('ERROR %s' % traceback.format_exc())
                errpage("""<p>We were unable to process your uploaded file
at this time.
We apologize for the inconvenience, and ask that you try again later. If the
problem persists, please contact the archive maintainers.</p>""")
                return

            if fn == ofn:
                logger.info('UPLOAD %s (%s)' % (fn+timestamp, remoteaddr))
                fnList.append(fn)
            else:
                logger.info('UPLOAD %s ORIGINAL NAME %s (%s)' % (fn+timestamp, ofn, remoteaddr))
                fnList.append('%s (originally %s)' % (fn, ofn))

            # If there's an IFDB ID, save it
            if 'ifdbid' in data:
                try:
                    ifdbID = data['ifdbid'].value
                    # Make sure the ifdbID is alnum only
                    if re.search('\W', ifdbID):
                        logger.error("IFDB ID %s isn't alphanumeric" % ifdbID)
                    else:
                        # We gotta play with the umask to open shelve
                        oldmask = os.umask(0)
                        ids = shelve.open(ifdbIdFile, protocol=2)
                        # Get the md5 hash of the file data.
                        hashval = hashlib.md5(data[key].value).hexdigest()
                        ids[hashval] = {"id": ifdbID, "time": time.time()}
                        ids.close()
                        os.umask(oldmask)
                except:
                    logger.error('IFDB ID %s ERROR %s' % (ifdbID, traceback.format_exc))

            tsList.append(timestamp)
            kbList.append(len(data[key].value))
            kbCount = kbCount + len(data[key].value)
            f = f + 1
        else:
            f = 0

    if (not len(fnList)):
        errpage("""<p>No files were received.</p>""")
        return

    fnamesForMailing = []
    htmlfiles = []

    htmlfiles.append('<ul>')
    for x in range(0, len(fnList)):
        htmlfiles.append("<li>%s (%i bytes)</li>" % (fnList[x],kbList[x]))
    htmlfiles.append('</ul>')
    htmlfiles = '\n'.join(htmlfiles)

    msg = []
    msg.append("%s %s totalling %.2f kb uploaded successfully:\n\n" % (len(fnList),plural("file",len(fnList)),kbCount / 1024.0))
    
    for x in range(0, len(fnList)):
        msg.append("  * %s (%.2f kb)\n" % (fnList[x]+tsList[x],kbList[x] / 1024.0))
        fnamesForMailing.append(fnList[x]+tsList[x])

    nameval = data.getfirst('name')
    if not nameval:
        nameval = 'Anonymous'
    emailval = data.getfirst('email')
    if not emailval:
        emailval = '?@???'
    msg.append("\nUploaded by %s <%s>\n\n" % (nameval, emailval,))
    
    if "filedesc" in data:
        msg.append(fix_line_endings(data["filedesc"].value) + "\n")
    if "directory" in data:
        msg.append("Suggested directory: if-archive/%s\n" % (data["directory"].value,))
    msg.append("Permission from: %s\n" % (rightsval,))
    if "ifdbid" in data:
        msg.append("IFDB ID: %s\n" % (data["ifdbid"].value,))
        # Try writing the IFDB ID to a text file
    msg.append('\n\n')
    
    msg = ''.join(msg)
    fnamesForMailing = ' '.join(fnamesForMailing)
        
    mailme(msg, nameval, emailval, "IFArchive Upload "+fnamesForMailing)
    
    map = { 'footer':footer, 'filenames':htmlfiles }
    write_template('accepted.html', map)
    return


# Begin work.

# This ensures that any exception will be nicely formatted.
import cgitb
cgitb.enable()

# Send everything to stdout.
sys.stderr = sys.stdout

# Write the HTTP header.
print("Content-Type: text/html; charset=utf-8")
print()

# Load a logger
logger = logging.getLogger('upload')
hdlr = logging.FileHandler(logfile)
formatter = logging.Formatter('%(asctime)s %(message)s', '%d/%b/%Y:%H:%M:%S')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)

if "HTTP_USER_AGENT" in os.environ:
    browser = os.environ["HTTP_USER_AGENT"]
else:
    browser = "No Known Browser"

if "SCRIPT_NAME" in os.environ:
    posturl = os.environ["SCRIPT_NAME"]
else:
    posturl = ""

if "REMOTE_ADDR" in os.environ:
    remoteaddr = os.environ["REMOTE_ADDR"]
else:
    remoteaddr = "?"

# Figure out the total size (bytes) of files in the incoming directory.
totaldirsize = 0
for ent in os.scandir(dirUpload):
    if ent.is_file():
        totaldirsize += ent.stat().st_size

data = cgi.FieldStorage()
form(data, posturl)

logging.shutdown()


