#!/usr/bin/env python3
from rdflib import Namespace, Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

#MO = Namespace('http://purl.org/ontology/mo/')
B3 = Namespace('hash://blake3/')
LOCAL = Namespace('PSEUDOCRAFT:')
XCAT = Namespace('http://xeroxc.at/schema#')

ns_graph = Graph()

ns_graph.bind('blake3', B3)
ns_graph.bind('xcat', XCAT)
ns_graph.bind('rdf', RDF)
ns_graph.bind('rdfs', RDFS)
ns_graph.bind('owl', OWL)
ns_graph.bind('xsd', XSD)

#def prefix_str(uri):
#    if isinstance(uri, URIRef):
#        return uri.n3(ns_graph.namespace_manager)
#    elif isinstance(uri, str):
#        try:
#            return URIRef(
#            except Exception:
#        return str(uri)
