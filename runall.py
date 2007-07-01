#!/usr/bin/python
# -*- coding: UTF-8 -*-
#
# $Id$

# Køres f.eks. som:
# python runall.py \
# 'echo -e "\n\n === TDC === \n" > log.tdc' \
# '$tdcgrabber $xmldir/tdc 2>> log.tdc' \
# 'echo -e "\n\n === TV2 === \n" > log.tv2' \
# '$tv2grabber $xmldir/tv2 2>> log.tv2' \
# 'echo -e "\n\n === Tvguiden === \n" > log.tvg' \
# '$tvggrabber $xmldir/tvg 2>> log.tvg' \
# 'echo -e "\n\n === Ahot === \n" > log.ahot' \
# '$ahotgrabber $xmldir/ahot 2>> log.ahot' \
# 'echo -e "\n\n === Jubii === \n" > log.jub' \
# '$jubgrabber $xmldir/jub 2>> log.jub'

import sys, os, time, threading
from threading import Thread

class commandThread(Thread):
    def __init__(self, command):
        self.command = command
        Thread.__init__(self)
    def run(self):
        os.system(self.command)

def runEm (commands, fromFolder = "."):
    for command in commands:
        thread = commandThread(command)
        thread.start()
    
    while threading.activeCount() > 1:
        time.sleep(1) #Temmelig grimt. Ved ikke lige om man kan gøre det anderledes
        #Måske noget med at alle trådene kaldte noget notify, når de afsluttede,
        #så der løkken kun blev kørt, når en tråd var slut...

if __name__ == "__main__":
    runEm(sys.argv[1:])
