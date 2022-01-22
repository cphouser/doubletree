#!/usr/bin/env python3

from pyswip.prolog import Prolog
from rdflib import Graph
from util.rdf.namespaces import XCAT
from rdflib.namespace import RDF, RDFS, OWL, XSD

prolog = Prolog()

prolog.consult('init.pl')

subjects_result = prolog.query("rdf_current_prefix(X, Y)")

for i, result in enumerate(subjects_result):
    print(i, result)

print("rdf_assert('https://vantanarow.bandcamp.com',"
      f"'{RDF.type}', '{XCAT.Artist}')")
triple_add = prolog.query("rdf_assert('https://vantanarow.bandcamp.com',"
                          f"'{RDF.type}', '{XCAT.Artist}')")
for idx, result in enumerate(triple_add):
    print(idx, type(result), result)

for i, result in enumerate(prolog.query(f"rdf(W, X, '{XCAT.Artist}', Y)")):
    print(i, result)

for i, result in enumerate(prolog.query(f"rdf('{XCAT.TrackList}', X, Y, Z)")):
    print(i, result)
