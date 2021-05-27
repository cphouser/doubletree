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
            if interactive:
                print(f'\thashing {file_path[-80:]} {fullsize//1024}KiB ',
                      end='\r')
            while True:
                some_bytes = f.read(chunksize)
                chunk += 1
                if interactive:
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
    return hasher.hexdigest()
