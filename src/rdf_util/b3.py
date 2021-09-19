#!/usr/bin/env python3

import os
import time

from blake3 import blake3


def file_hash(file_path, chunksize=65536, interactive=False):
    hasher = blake3()
    chunk = 0
    with open(file_path, "rb") as f:
        try:
            fullsize = os.path.getsize(file_path)
            if interactive and fullsize:
                print(f'\thashing {file_path[-80:]} {fullsize//1024}KiB ',
                      end='\r')
            while True:
                some_bytes = f.read(chunksize)
                chunk += 1
                if interactive and fullsize:
                    print(f'{int(((chunk*chunksize)/fullsize)*100)}% ',
                          end='\r')
                if not some_bytes:
                    break
                hasher.update(some_bytes)
            if interactive:
                print(' ' * 120, end='\r')
        except KeyboardInterrupt:
            time.sleep(2)
            return None
    print('\r\033[K', end="")
    return hasher.hexdigest()

def hashlist_hash(hashlist):
    """Hash a list of hash hexdigests, return the hexdigest.

    result should be unique for a given list
    """
    list_bytes = b''.join(sorted([bytes.fromhex(_hash) for _hash in hashlist]))
    hasher = blake3()
    hasher.update(list_bytes)
    return hasher.hexdigest()
