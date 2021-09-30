#!/usr/bin/env python3

import os
import logging
from sys import stdout
from datetime import datetime
from pprint import pformat

from rdflib.namespace import RDF, RDFS, OWL, XSD

from rdf_util.pl import RPQ, _utf8, xsd_type, entries_to_dir, nometa_file_node
from rdf_util.namespaces import B3, XCAT

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('oldpath',
                        help='old common root directory')
    parser.add_argument('newpath',
                        help='new common root directory')
    args = parser.parse_args()

    rpq = RPQ('init.pl', write_mode=True)#, log=log)
    print("loaded rdf db")

    file_uris = rpq.uns_query(
        #f"rdfs_individual_of(File_URI, '{XCAT.DirEntry}'), "
        f"rdf(_, '{XCAT.path}', Path^^'{XSD.string}')"
    )
    assertions = []
    for res in file_uris:
        filepath = _utf8(res['Path'])
        if args.oldpath in filepath:
            newpath = filepath.replace(args.oldpath, args.newpath)
            assertions.append(
                f"rdf_update(_, _, {xsd_type(filepath, 'string')}, "
                f"object({xsd_type(newpath, 'string')}))"
            )
        else:
            print(filepath, "does not contain", args.oldpath)

    rpq.rassert(*assertions)
