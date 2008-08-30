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

import sys, os
from Queue import Queue
from threading import Thread

class commandThread(Thread):
    def __init__(self, command, queue):
        self.command = command
        self.queue = queue
        Thread.__init__(self)
    
    def run(self):
        os.system(self.command)
        self.queue.put(self)

def runEm (commands, fromFolder = "."):
    q = Queue()
    
    for command in commands:
        thread = commandThread(command, q)
        thread.start()
    
    count = 0
    while count < len(commands):
        q.get()
        count += 1

if __name__ == "__main__":
    runEm(sys.argv[1:])
