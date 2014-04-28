#!/usr/bin/python

# Simple wrapper for repo_sync. Saves a datestamped log to LOGDIR, and e-mails the log if
# the log contains the string '.pkg'. (ie. if a new product was replicated). The log will
# also contain the contents of English.dist for any new products.
#
# Additional requirements:
# - 'psutil' module, available from PyPi, minimum version 2.0.0

import os
import sys
import subprocess
import plistlib
from time import strftime, localtime
import re
import psutil		# psutil is used to more easily detect whether repo_sync is already running

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import formatdate
from email import Encoders

LOGDIR = '/var/log/reposado'
REPO_SYNC = '/home/reposado/git/reposado/code/repo_sync'
REPO_PREFS = '/home/reposado/git/reposado/code/preferences.plist'
prefs = plistlib.readPlist(REPO_PREFS)



mail_from = "reposado@my.org"
mail_to = ["admin@my.org"]
smtpserver = "smtp.my.org"

def reposync_is_running():
    proclist = psutil.get_process_list()
    for p in proclist:
        for arg in p.cmdline():
            if os.path.split(arg)[1] == 'repo_sync':
                return True
    return False

# E-mail code largely based on http://code.google.com/p/munki/wiki/PreflightAndPostflightScripts
def send_mail(send_from, send_to, subject, text, files=[], server="localhost"):
    assert type(send_to) == list
    assert type(files) == list

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = ", ".join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(f, "rb").read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                      'attachment; filename="%s"' % os.path.basename(f))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()

if reposync_is_running():
    print "repo_sync is already running. Exiting.."
    sys.exit(1)

if not os.path.exists(LOGDIR):
    os.mkdir(LOGDIR)

logfile = os.path.join(LOGDIR, strftime('%Y-%m-%d_%H%M.log', localtime()))

# do the repo_sync
cmd = [REPO_SYNC, '--log=%s' % logfile]
subprocess.call(cmd)

try:
    lfb = open(logfile)
    logfile_contents = lfb.read()
    lfb.close()
except:
    print "Can't read the logfile"
    sys.exit(1)

if logfile_contents.find('pkg') != -1:
    meta = plistlib.readPlist(os.path.join(prefs['UpdatesMetadataDir'], 'ProductInfo.plist'))
    distpaths = re.findall("content/.*English.dist", logfile_contents)
    localdists = [os.path.join(prefs['UpdatesRootDir'], p) for p in distpaths]
    subject = "Reposado log"
    body = logfile_contents
    body += "\n\n"
    for dist in localdists:
        distcontent = open(dist, 'r')
        body += distcontent.read()
        distcontent.close()
        body += "\n\n\n"
    send_mail(mail_from, mail_to, subject, body, files=[], server=smtpserver)
