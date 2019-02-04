#!/usr/bin/python3

import sys
import os
import json
import argparse

def convert(data):
    # transform    
    data['anchors'] = [ 'sha256:' + h for h in data['anchors'] ]    
    # print(json.dumps(data, indent=4))



parser = argparse.ArgumentParser(description='HashGet convert HashDB')

parser.add_argument('dir', default=None, metavar='DIR', help='directory')
parser.add_argument('--write', '-w', default=False, action='store_true', help='write changes to files')
parser.add_argument('--stdout', '-o', default=False, action='store_true', help='show to stdout')

args = parser.parse_args()


for basename in os.listdir(args.dir):
    path = os.path.join(args.dir, basename)
    print(path)
    
    # load
    with open(path, 'r') as f:
        data = json.load(f)
    
    convert(data)
    if args.stdout:
        print(json.dumps(data, indent=4))        

    if args.write:
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
            
