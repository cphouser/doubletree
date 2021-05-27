#!/usr/bin/env python3


import rdflib as rdf
import os


def conjunct(path=None, *args):
    #graphs = []
    conj_g = rdf.ConjunctiveGraph()
    if path and os.path.isdir(path):
        for entry in os.scandir(path):
            if os.path.isfile(entry.path) and entry.name[-3:] == '.nt':
                graph = rdf.Graph()
                graph.parse(entry.path, format='turtle')
                conj_g += graph
    print(list(conj_g.namespace_manager.namespaces()))
    #for obj in set(conj_g.objects()):
    #    if isinstance(obj, rdf.URIRef):
    #        print(obj)
    #for pred in set(conj_g.predicates()):
    #    print(pred)


if __name__ == '__main__':
    full_graph = conjunct('../data/nt/')
