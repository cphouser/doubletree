#!/usr/bin/env python3

import os
import logging
import pickle
from sys import stdout
from datetime import datetime
from pprint import pformat

from rdflib.namespace import RDF, RDFS, OWL, XSD

from log_util import LogFormatter
from rdf_util.b3 import file_hash, hashlist_hash
from rdf_util.pl import RPQ, _utf8, xsd_type, entries_to_dir, nometa_file_node
from rdf_util.namespaces import B3, XCAT

def rec_file_hash(path):
    # path: hash (?)
    dirpaths = {}
    for dirpath, subdirs, filenames in os.walk(path, topdown=False):
        entry_hashes = []
        for subdir in subdirs:
            subdir_path = os.path.join(dirpath, subdir)
            if not (subdir_hash := dirpaths.get(subdir_path)):
                raise Exception(f"{subdir_path}\n not encountered"
                                f"before\n{dirpath}")
            entry_hashes.append(subdir_hash)

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            filehash = file_hash(fullpath, interactive=True)
            entry_hashes.append(filehash)
            dirpaths[fullpath] = filehash

        if entry_hashes:
            dirpaths[dirpath] = hashlist_hash(entry_hashes)

    return dirpaths


def child_entries(dirpaths, dirpath):
    if os.path.isdir(dirpath):
        hashes = []
        for entry in os.listdir(dirpath):
            entry = os.path.join(dirpath, entry)
            if entry not in dirpaths:
                print(entry)
                for path, phash in list(dirpaths.items())[:10]:
                    print(phash, path)
                raise Exception("Something wrong w/ bottom-up assumptions?")
            hashes.append(dirpaths[entry])
        if hashes:
            return hashes
        else:
            raise Exception("are empty directories handled upstream now?")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='folder(s) to scan', nargs="+")
    parser.add_argument('--log', '-l', type=int, default=20, help=
                        'output logging level (0-50), 0 prints all output')
    parser.add_argument('--pickle-cache', '-p', action='store_true',
                        help='use a cache of the filedata from the last run')
    args = parser.parse_args()

    log = logging.getLogger('update_paths')
    # why am i doing this twice?
    log.setLevel(args.log)
    log_handler = logging.StreamHandler(stdout)
    log_handler.setLevel(args.log)
    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)
    log.info(f"\n\t\tRDF Path Updater {datetime.now()}")

    cache_file = '../data/cache/updated_paths.pickle'
    if not args.pickle_cache:
        dirpaths = {}
        for path in args.input:
            path = os.path.abspath(path)
            dirpaths.update(rec_file_hash(path))
    else:
        dirpaths = pickle.load(open(cache_file, 'rb'))
        log.info(f"loaded {cache_file}")

    pickle.dump(dirpaths, open(cache_file, 'wb+'))

    rpq = RPQ('init.pl', write_mode=True)#, log=log)

    dirhashes = {}
    for path, pathhash in dirpaths.items():
        pathlist = dirhashes.get(pathhash, [])
        pathlist.append(path)
        dirhashes[pathhash] = pathlist

    for b3hash, paths in dirhashes.items():
        assertions = []
        if len(paths) > 1:
            log.debug(f"duplicate: {b3hash} (" + str(os.stat(paths[0]).st_size)
                      + ")\n" + pformat(paths, width=170))
        file_uri = B3[b3hash]
        if (old_paths := rpq.uns_query(
                f"rdf('{file_uri}', '{XCAT.path}', Path^^'{XSD.string}')"
        )):
            old_paths = [_utf8(res['Path']) for res in old_paths]
            new_paths = []
            for path in paths:
                if path in old_paths:
                    old_paths.remove(path) # nothing changed
                else:
                    new_paths.append(path) # new path
            for path in old_paths:
                assertions.append(f"rdf_retractall('{file_uri}', '{XCAT.path}'"
                                  f", {xsd_type(path, 'string')})")
            for path in new_paths:
                assertions.append(f"rdf_assert('{file_uri}', '{XCAT.path}'"
                                  f", {xsd_type(path, 'string')})")
            if old_paths or new_paths:
                log.debug("old: " + pformat(old_paths, width=150))
                log.debug("new: " + pformat(new_paths, width=150))
        else:
            log.debug(f"new direntry: {file_uri}\n{pformat(paths, width=160)}")
            if (child_hashes := child_entries(dirpaths, paths[0])):
                child_uris = [B3[child_hash] for child_hash in child_hashes]
                log.debug("it is a directory")
                [entries_to_dir(rpq, b3hash, path, child_uris)
                 for path in paths]
            else:
                log.debug("it is a file")
                [nometa_file_node(rpq, {'path': path, '_hash': b3hash})
                 for path in paths]

        if assertions:
            rpq.uns_query(", ".join(assertions))

    # for uris in pl store if not in dirhashes: remove uri
    file_uris = rpq.uns_query(
        f"rdfs_individual_of(File_URI, '{XCAT.DirEntry}'), "
        f"rdf(File_URI, '{XCAT.hash}', EntryHash^^'{XSD.string}')"
    )
    for res in file_uris:
        file_hash = _utf8(res['EntryHash'])
        file_uri = _utf8(res['File_URI'])
        if file_hash in dirhashes:
            continue
        else:
            rpq.uns_query(f"xcat_retract('{file_uri}')")
            log.info(f"{file_uri} has been removed")

#            # for path in old_paths:
#            #   if path in dirpaths and dirpaths[path]
#            if len(old_paths) > 1:
#                log.debug(f"multiple locations:\n{pformat(old_paths, width=160)}")
#            if path not in old_paths:
#                log.info(f"{old_paths} is now at {path}")
