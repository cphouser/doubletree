#!/usr/bin/env python3

def load_graph(infile):
    from rdflib import Graph as RDFGraph
    g = RDFGraph()

    g.parse(infile, format='turtle')

    return g


def make_graph(rdf_g, base_ns, level_limit=None, stable_only=False,
               debug=False):
    import networkx as nx
    from rdflib.extras.external_graph_libs import rdflib_to_networkx_graph
    from rdflib.namespace import RDFS, RDF, OWL
    from rdflib.namespace import FOAF, NamespaceManager
    from rdflib import URIRef, BNode, Namespace
    from rdflib.collection import Collection
    import rdflib_ext as rdfe
    import uuid

    NODE = dict(style='filled', margin='0.02;0.01',
            width=0.01,
            height=0.01,
                )
    EDGE = dict()
    CLASS = dict(
        shape='box',
        **NODE)
    EXTERNAL_CLASS = dict(
        fillcolor='sandybrown',
        **CLASS)
    EXTERNAL_SUPERCLASS = dict(
        fillcolor='darkorange',
        **CLASS)
    INTERNAL_CLASS = dict(
        fillcolor='palevioletred1',
        **CLASS)
    META_CLASS = dict(
        fillcolor='darkorange3',
        shape='ellipse',
        **NODE)
    META_CLASS_EDGE = dict(
        fillcolor='darkorange3',
        color='darkorange3',
        **EDGE)
    SUBCLASS_EDGE = dict(
        weight=10,
        fillcolor='palevioletred1',
        color='palevioletred1',
        **EDGE)
    DOMAIN_RANGE_EDGE = dict(
        fillcolor='cyan',
        **EDGE)
    PROPERTY_NODE = dict(
        fillcolor='cyan',
        shape='plain',
        **NODE)
    INTERNAL_TYPE_NODE = dict(
        fillcolor='teal',
        fontcolor='lightcyan1',
        shape='plain',
        **NODE)
    INTERNAL_TYPE_EDGE = dict(
        fillcolor='teal',
        color='teal',
        **EDGE)
    SUBPROPERTY_NODE = dict(
        fillcolor='paleturquoise1',
        shape='plain',
        **NODE)
    SUBPROPERTY_EDGE = dict(
        fillcolor='paleturquoise1',
        color='teal',
        **EDGE)
    RESTRICTION = dict(
        fillcolor='darkmagenta',
        color='darkmagenta',
        minlen=0,
        **EDGE)
    EXTERNAL_RESTRICTION = dict(
        fillcolor='navajowhite',
        shape='plain',
        **NODE)

    def name(uri_ref):
        if not uri_ref:
            return 'None'
        else:
            return uri_ref.n3(rdf_g.namespace_manager)

    def label(node, use_name=True):
        if (label := rdf_g.value(node, RDFS.label, None, any=False)):
            return label
        elif use_name:
            return name(node)

    def get_union_node(parent_node):
        _union = rdf_g.value(parent_node, OWL.unionOf, None)
        c = Collection(rdf_g, _union)
        _node = 'union:' + str(list(sorted(c)))
        return _node, c

    def add_union_node(parent_node, **item_attrs):
        _node, c = get_union_node(parent_node)
        for item in c:
            item_node = _node + str(item_attrs) + str(item)
            if rdfe.namespace(item, rdf_g)[0] == base_ns:
                g.add_node(item_node, label=name(item),
                            uri=str(item), **INTERNAL_CLASS)
            else:
                g.add_node(item_node, label=name(item),
                            uri=str(item), **EXTERNAL_CLASS)

            if item_attrs.get('dir') == 'back':
                g.add_edge(item_node, _node, **item_attrs,
                            **META_CLASS_EDGE)
            else:
                g.add_edge(_node, item_node, **item_attrs,
                            **META_CLASS_EDGE)
        return _node

    def graph_domain_range(subj):
        domain = rdf_g.value(subj, RDFS.domain, None, any=False)
        range = rdf_g.value(subj, RDFS.range, None, any=False)
        if (isinstance(domain, URIRef)
                and rdfe.namespace(domain, rdf_g)[0] != base_ns):
            domain_node = name(domain) + name(subj) + name(range)
            domain_attrs = dict(label=name(domain), uri=str(domain),
                                    **EXTERNAL_CLASS)
        elif isinstance(domain, BNode):
            if rdf_g.value(domain, OWL.unionOf, None):
                domain_node = add_union_node(domain, dir='back')
                domain_attrs = dict(label='union of',
                                    uri=str(domain_node),
                                    **META_CLASS)
            else:
                domain_node = str(domain)
        else:
            domain_node = domain
            domain_attrs = {}

        if (isinstance(range, URIRef)
                and rdfe.namespace(range, rdf_g)[0] != base_ns):
            range_node = name(range) + name(subj) + name(range)
            range_attrs = dict(label=name(range), uri=str(range),
                                    **EXTERNAL_CLASS)
        elif isinstance(range, BNode):
            if rdf_g.value(range, OWL.unionOf, None):
                range_node = add_union_node(range)
                range_attrs = dict(label='union of',
                                   uri=str(range_node),
                                   **META_CLASS)
            else:
                range_node = str(range)
        else:
            range_node = range
            range_attrs = {}

        g.add_node(subj, label=name(subj), uri=str(subj),
                   **PROPERTY_NODE)
        if range:
            g.add_node(range_node, **range_attrs)
            g.add_edge(subj, range_node,
                        **DOMAIN_RANGE_EDGE)
        if domain:
            g.add_node(domain_node, **domain_attrs)
            if range:
                g.add_edge(domain_node, subj, arrowhead='none',
                           **DOMAIN_RANGE_EDGE)
            else:
                g.add_edge(domain_node, subj,
                           **DOMAIN_RANGE_EDGE)


    if level_limit:
        print(f'Restricting graph to {level_limit}')

    g = nx.DiGraph()

    #rdf_g.bind(base_ns, URIRef('http://purl.org/ontology/mo/'))
    #rdf_g.bind('foaf', FOAF)

    mo = Namespace('http://purl.org/ontology/mo/')
    vs = Namespace('http://www.w3.org/2003/06/sw-vocab-status/ns#')

    for subj in set(rdf_g.subjects()):
        if level_limit and (level := rdf_g.value(subj, mo.level)):
            if int(level) > level_limit:
                continue
        if stable_only and (term_status := rdf_g.value(subj, vs.term_status)):
            if str(term_status) == 'stable':
                continue
            elif debug:
                print(f'{subj} is {term_status}')

        if any([str(obj) == 'deprecated' for obj in rdf_g.objects(subject=subj)]):
            continue
        elif (rdf_g.value(subj, RDFS.domain, None, any=False)
              or rdf_g.value(subj, RDFS.range, None, any=False)):
            graph_domain_range(subj)
        elif ((subj, RDF.type, OWL.Class) in rdf_g
              or (subj, RDF.type, RDFS.Class) in rdf_g):
            if (isinstance(subj, BNode)
                    and rdf_g.value(subj, OWL.unionOf, None)):
                class_node, _ = get_union_node(subj)
            else:
                class_node = subj
                class_attrs = dict(label=name(class_node),
                        **INTERNAL_CLASS, uri=str(class_node))
                g.add_node(class_node, **class_attrs)

            for superclass in rdf_g.objects(subj, RDFS.subClassOf):
                if rdfe.namespace(superclass, rdf_g)[0] == base_ns:
                    superclass_node = superclass
                    superclass_attrs = dict(label=name(superclass),
                                       uri=str(superclass),
                                       **INTERNAL_CLASS)
                else:
                    if debug:
                        print(rdfe.namespace(superclass, rdf_g)[0])

                    superclass_node = name(superclass) + name(subj)
                    superclass_attrs = dict(label=name(superclass),
                                       uri=str(superclass),
                                       **EXTERNAL_SUPERCLASS)
                g.add_node(superclass_node, **superclass_attrs)
                g.add_edge(superclass_node, class_node, **SUBCLASS_EDGE)
        else:
            if (type := rdf_g.value(subj, RDF.type)):
                if (rdfe.namespace(type, rdf_g)[0] == base_ns
                    or type == RDFS.Datatype):
                    g.add_node(subj, label=name(subj),
                               **INTERNAL_TYPE_NODE)
                    if rdfe.namespace(type, rdf_g)[0] == base_ns:
                        g.add_edge(type, subj, **INTERNAL_TYPE_EDGE)
                    continue
                elif type in (OWL.ObjectProperty, OWL.DatatypeProperty):
                    if (superprop := rdf_g.value(subj,
                                                 RDFS.subPropertyOf)):
                        g.add_node(subj, label=name(subj),
                                   **SUBPROPERTY_NODE)
                        g.add_edge(subj, superprop, **SUBPROPERTY_EDGE)
                        continue
                elif type == OWL.Restriction:
                    if ((src := rdf_g.value(subj, OWL.someValuesFrom))
                            and (dst := rdf_g.value(subj, OWL.onProperty))):
                        if rdfe.namespace(src, rdf_g)[0] != base_ns:
                            g.add_node(str(subj) + str(src),
                                       label=name(src),
                                       **EXTERNAL_RESTRICTION)
                            src = str(subj) + str(src)
                        if rdfe.namespace(dst, rdf_g)[0] != base_ns:
                            g.add_node(str(subj) + str(dst),
                                       label=name(dst),
                                       **EXTERNAL_RESTRICTION)
                            dst = str(subj) + str(dst)

                        g.add_edge(src, dst, **RESTRICTION)
                        continue
            if debug:
                print(f'*** {subj} {type}')
                for pred, obj in rdf_g.predicate_objects(subj):
                    print(f'\t{name(pred)}, {name(obj)}')
    return g


def render(networkx_graph, outfile, out_format='png'):
    import pygraphviz
    import networkx as nx
    import timeit

    layouts = {
        #nop, wc, acyclic, gvpr, gvcolor, ccomps, sccmap, tred, unflatten
        'dot': dict(packmode='array', mclimit='2.0'),
        #'twopi': dict(),
        #'acyclic': dict(),
        #'wc': dict(),
        #'gvpr': dict(),
        #        'circo': dict(),
        #        'fdp': dict(),
        #        'sfdp': dict(),
        #'neato': dict(mode='hier')
    }
    for layout, attrs in layouts.items():
        start = timeit.default_timer()
        graphviz_g = nx.nx_agraph.to_agraph(networkx_graph)
        graphviz_g.graph_attr.update(**attrs)
        graphviz_g.layout(layout)
        graphviz_g.draw(f'{outfile}_{layout}.{out_format}', out_format)
        print(f'rendered {layout} in {timeit.default_timer() - start} seconds')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='input rdf file')
    parser.add_argument('--base-ns', '-n', type=str, default='xsd',
                        help='namespace prefix of the schema (ex: "xsd")')
    parser.add_argument('--level-limit', '-l', type=int,
                        help='limits graph to specified level (and lower)')
    parser.add_argument('--stable-only', '-s', action='store_true',
                        help='excludes notes with vs:term_status "unstable"')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='include debug output')
    args = parser.parse_args()

    print(f'rendering {args.input} as a networkx graph')

    rdf = load_graph(args.input)
    nxg = make_graph(rdf,
                     level_limit=args.level_limit,
                     stable_only=args.stable_only,
                     base_ns=args.base_ns,
                     debug=args.debug)
    infile_split = args.input.rsplit('.', maxsplit=1)
    if len(infile_split) == 2:
        outfile = f'{infile_split[0]}_networkx_image'
    else:
        outfile = f'{args.input}_networkx_image'
    render(nxg, outfile)
