#!/usr/bin/python
# -*- coding: UTF-8 -*-

#Tilføj flere filer, om nødvendigt
filer = ("tv_grab_dk_ahot.py", "tv_grab_dk_jubii", "tv_grab_dk_ontv",
"tv_grab_dk_tdc.py", "tv_grab_dk_tvguiden.py", "analyzeformater.py",
"channelid.py", "channelidparsefiler.zip", "timefix.py", "tv_grab_dk_ahot.py",
"tv_grab_dk_jubii.py", "tv_grab_dk_ontv.py", "tv_grab_dk_tdckabeltv",
"tv_grab_dk_tvguiden.py", "xmltvanalyzer.py", "xmltvmerger.py", "splittitle.py",
"runall.py")

extra = ("filegrabber.py", "tv_grab_dk_all.py")

def downloadFilesToFolder(files, folder = "."):
           
    import os, sys
    if os.path.exists(folder):
        if not os.path.isdir(folder):
            print "Mappen findes allerede"
            sys.exit()
    else: os.makedirs(folder)
    if not folder.endswith(os.path.sep): folder += os.path.sep

    passwordfil = folder+"password"
    if os.path.isfile(passwordfil):
        passdata = open(passwordfil).readlines()
        username, password = [l.strip() for l in passdata if len(l.strip()) > 0]
    else:
        print "Indtast dit yahoo brugernavn og password"
        username = raw_input("Username: ")
        from getpass import getpass
        password = getpass("Password: ")
        f = open(passwordfil,"w")
        f.write(username+"\n")
        f.write(password+"\n")
        f.close()

    print "Henter login side"
    import urllib2
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor)
    d = opener.open("http://login.yahoo.com/").read()
    
    vars = {}
    import re
    p = re.compile(r'<input type="hidden" name="(.*?)" value="(.*?)">')
    for k, v in p.findall(d):
        vars[k] = v
    vars["login"] = username
    vars["passwd"] = password
    vars[".done"] = "http://uk.groups.yahoo.com/group/xmltvdk/files"
    
    print "Logger ind"
    from urllib import urlencode
    login = opener.open("https://login.yahoo.com/config/login?", urlencode(vars)).read()
    if login.find("Invalid ID or password") >= 0:
        raise TypeError, "Brugername/password blev ikke godkendt"
    
    print "Henter fil side"
    data = opener.open("http://uk.groups.yahoo.com/group/xmltvdk/files").read()

    s = data.find("<!-- start content include -->")+len("<!-- start content include -->")
    e = data.find("<!-- end content include -->",s)
    data = data[s:e]
    p = re.compile(r'class="title"(?:.*?)href="(.*?)">(.*?)</a>(?:.*?)',re.DOTALL)
    
    from time import mktime, localtime, gmtime, time, strftime
    from os.path import getmtime
    def getTime (filename):
        t = getmtime(folder+filename)
        t += mktime(localtime()) - mktime(gmtime(time()))
        return strftime("%a, %d %b %Y %X %Z", gmtime(t))
    
    print "Downloader"
    dirfiles = os.listdir(folder)
    for url, name in p.findall(data):
        if name in files:
            request = urllib2.Request(url)
            if name in dirfiles:
                request.add_header('If-Modified-Since', getTime(name))
            try:
                data = opener.open(request).read()
                f = open(folder+name,"wb")
                f.write(data)
                f.close()
            except urllib2.HTTPError, message:
                if str(message) == "HTTP Error 304: Not Modified":
                    print "Ingen nyere end", name
                else: print message
            else: print "Henter", name
    
    print "Udpakker"
    import zipfile
    for file in [f for f in dirfiles if f.endswith(".zip")]:
        z = zipfile.ZipFile(folder+file,"r",compression=zipfile.ZIP_DEFLATED)
        for name in z.namelist():
            f = open(folder+name,"w")
            f.write(z.read(name))
            f.close()

if __name__ == "__main__":
    downloadFilesToFolder(filer+extra, "xmltv")
