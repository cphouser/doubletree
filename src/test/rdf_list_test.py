#!/usr/bin/env python3

from pyswip.prolog import Prolog
from pyswip.easy import putList

from pl_util import query, xsd_type, rdf_find, new_bnode, LDateTime
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import MO, B3, LOCAL, XCAT

term_list = ['t_one', 't_two', 't_three']

res = query(debug=True, query=[('rdf_assert_seq', ('_v:X', term_list))])
print(list(res))
seq = res[0]['X']

res = query(debug=True, query=
            (('rdf_retractall', (seq, RDF.type, RDF.Seq)),
             ('rdf_assert', (seq, RDF.type, XCAT.TrackList)),
             ('rdf_assert', ('a_list', XCAT.tracklist, seq))
             ))
print(list(res))
