#!/usr/bin/env python3
import logging as log
#
from rdflib import Namespace, Graph, URIRef
from rdflib.namespace import RDF, RDFS, XSD

#MO = Namespace('http://purl.org/ontology/mo/')
B3 = Namespace('hash://blake3/')
LOCAL = Namespace('PSEUDOCRAFT:')
XCAT = Namespace('http://xeroxc.at/schema#')


class ShortURI:
    def __init__(self):
        ns_graph = Graph()
        ns_graph.bind('blake3', B3)
        ns_graph.bind('xcat', XCAT)
        ns_graph.bind('rdf', RDF)
        ns_graph.bind('rdfs', RDFS)
        ns_graph.bind('xsd', XSD)
        self.graph = ns_graph

    def __call__(self, uri):
        if isinstance(uri, URIRef):
            return uri.n3(self.graph.namespace_manager)
        elif isinstance(uri, str):
            try:
                return URIRef(uri).n3(self.graph.namespace_manager)
            except Exception as e:
                log.warn(e)
                return str(uri)
