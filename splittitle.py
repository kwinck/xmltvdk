#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re, sys

try:
    data = open(sys.argv[1]).read()
except IOError, message:
    sys.stderr.write(str(message)+"\n")
    sys.exit()
    
pattern = r"<title(.*?)>(.*?)\s*:\s+(.*?)</title>"
replacement = r"<title\1>\2</title><sub-title\1>\3</sub-title>"
result = re.sub(pattern, replacement, data)

print result
