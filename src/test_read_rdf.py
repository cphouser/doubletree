#!/usr/bin/env python3


import os

import rdflib as rdf
from rdflib.container import Seq
from rdflib.namespace import RDF, RDFS, OWL, FOAF, DC, PROV, XSD, TIME

from rdf_util import graphs as rdfg
from rdf_util.namespaces import MO, B3, LOCAL, XCAT

def conjunct(path=None, *args):
    conj_g = rdf.ConjunctiveGraph()
    if path and os.path.isdir(path):
        for entry in os.scandir(path):
            if os.path.isfile(entry.path) and entry.name[-3:] == '.nt':
                graph = rdf.Graph()
                graph.parse(entry.path, format='turtle')
                conj_g += graph
    return conj_g


if __name__ == '__main__':
    full_graph = conjunct('../data/nt/')

    artist = full_graph.value(None, FOAF.name, rdf.Literal('Иванушки International'))
    for work in rdfg.match(((artist, FOAF.made, None),
                            (None, RDF.type, MO.Release)), full_graph):
        print(full_graph.value(work, DC.title, None))
        tracklist = full_graph.value(work, XCAT.tracklist, None)
        for track in Seq(full_graph, tracklist).items():
            print('\t', track, full_graph.value(track, MO.track_number, None))
            print('\t\t', rdfg.file_node_path(full_graph, track))
