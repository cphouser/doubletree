#!/usr/bin/env python3

import musicpd

import logging as log

def add_to_list(*filepaths, **filepath_dict):
    if (path := filepath_dict.get('Path')):
        filepaths += [path]
    client = musicpd.MPDClient()
    client.connect('/run/mpd/socket')
    for path in filepaths:
        #with open("whatsgoingon.txt", 'a') as f:
        #    f.write(f'{str(path)} {type(path)}\n')
        client.add(path)
    client.disconnect()
