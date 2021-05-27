#!/usr/bin/env python3

import urllib.parse as url
from datetime import datetime

import rdflib as rdf
from rdflib.namespace import RDF, RDFS, OWL, FOAF, DC, PROV, XSD, TIME

from rdf_util.namespaces import MO, B3, LOCAL, XCAT

def match(query, graph, unique=False):
    matching_values = set()
    matching_triples = graph.triples(query[0])
    blank_idx = query[0].index(None)
    for match in matching_triples:
        matching_values.add(match[blank_idx])
    for triple in query[1:]:
        if not matching_values:
            return None if unique else set()
        else:
            triple = list(triple)
            blank_idx = triple.index(None)
            for value in tuple(matching_values):
                triple[blank_idx] = value
                if not tuple(graph.triples(triple)):
                    matching_values.remove(value)

    if unique:
        if not matching_values:
            return None
        elif len(matching_values) == 1:
            return matching_values.pop()
        else:
            raise Exception(f'Result from query:\n {query}\n '
                            f'is non-unique. Results: {matching_values}')
    else:
        return matching_values


def matchorinit(query, graph, node=None):
    if not (result := match(query, graph, unique=True)):
        result = node or rdf.BNode()
        for triple in query:
            blank_idx = triple.index(None)
            triple = list(triple)
            triple[blank_idx] = result
            graph.add(triple)
    elif node and isinstance(result, rdf.BNode):
        #not tested
        for pred, obj in graph.predicate_objects(result):
            graph.remove((result, pred, obj))
            graph.add((node, pred, obj))
        for subj, pred in graph.subject_predicates(result):
            graph.remove((subj, pred, result))
            graph.add((subj, pred, node))
        result = node
    elif (isinstance(result, rdf.URIRef) and isinstance(node, rdf.URIRef)
          and result != node):
        raise Exception("Implement a SameAs?")

    return result


def add_date_added(track, data_g, time_g, timestamp):
    dt = datetime.fromtimestamp(timestamp)
    t_node = time_node(time_g, year=dt.year, month=dt.month, day=dt.day,
                       hour=dt.hour)
    data_g.add((track, XCAT.added_during, t_node))


def time_node(time_g, **kwargs):
    argnames = ('year', 'month', 'day', 'hour', 'minute', 'second')
    properties = (TIME.year, TIME.month, TIME.day,
                  TIME.hour, TIME.minute, TIME.second)
    precisions = (TIME.unitYear, TIME.unitMonth, TIME.unitDay,
                  TIME.unitHour, TIME.unitMinute, TIME.unitSecond)
    triples = [(None, RDF.type, TIME.GeneralDateTimeDescription)]
    precision = None
    for arg, prop, prec in zip(argnames, properties, precisions):
        if (dt_frag := kwargs.get(arg)):
            triples += [(None, prop, rdf.Literal(dt_frag))]
            precision = prec
        else:
            break
    triples += [(None, TIME.unitType, precision)]
    return matchorinit(triples, time_g)


def file_node_path(graph, node):
    if not (file_urn := graph.value(node, MO.item, None)):
        return None
    if not (file_url := graph.value(file_urn, PROV.atLocation, None)):
        return None
    return url.unquote(file_url)

if __name__ == '__main__':
    print('not implemented')
