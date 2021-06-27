#!/usr/bin/env python3

from pyswip.prolog import Prolog
from pyswip.easy import putList

from rdf_util.pl import (query, xsd_type, rdf_find, new_bnode, LDateTime,
                        direct_subclasses)
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import MO, B3, LOCAL, XCAT


pl = Prolog()

pl.consult('init.pl')

res = direct_subclasses(pl)

for j in res:
    for i in j:
        print(i, type(i), end="\t")
    print()
#res = query(debug=True, query=
#            (('rdf_retractall', (seq, RDF.type, RDF.Seq)),
#             ('rdf_assert', (seq, RDF.type, XCAT.TrackList)),
#             ('rdf_assert', ('a_list', XCAT.tracklist, seq))
#             ))
#print(list(res))
