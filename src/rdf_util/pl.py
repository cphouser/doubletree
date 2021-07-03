#!/usr/bin/env python3

from pyswip.prolog import Prolog
from rdf_util.namespaces import XCAT
from rdflib.namespace import RDF, RDFS, OWL, XSD

from frozendict import frozendict

def query(pl=None, query=None, unique=False, debug=False):
    """
    Query the prolog rdf store.

    query takes either of the following forms:
    ((predicate1, (arg1, arg2, ...)),
     (predicate2, (...)),
     ...
    )
    or:
    (predicate, (arg1, arg2, ...))
    where each arg is either a term or variable (prefixed by '_v:').
    RDF terms will be passed as their string value,
    prolog terms as tuples are TODO
    """
    _, results = _query(pl, query, debug=debug)
    result_list = []
    for result in results:
        result_list += [frozendict(result)]
    return set(result_list) if unique else result_list


def query_gen(pl=None, query=None, debug=False, result_type='tuple'):
    #print(query)
    varlist, results = _query(pl=pl, query=query, debug=debug)
    #print('ffffff', varlist, list(results))
    for result in results:
        if debug:
            print(result)
        if result_type == 'tuple':
            #print([_utf8(result[var]) for var in varlist if var in result])
            yield tuple(_utf8(result[var]) for var in varlist if var in result)


def fill_query(query, key_dict):
    """
    Returns a query which can be passed to query(). The query passed
    to this function fits that form except may include variables
    prefixed by '_k:'. These variables are replaced by the value in
    key_dict corresponding to the variable name (excluding the '_k:')

    therefore fill_query(('rdf', ('_k:Resource', RDF.type, '_v:Class')),
                         {'Resource': XCAT.Artist})
    will return ('rdf', (XCAT.Artist, RDF.type, '_v:Class'))
    """
    if isinstance(query[0], str):
        query = [query]
    new_query = []
    for pred, args in query:
        #print(pred, args)
        for key, value in key_dict.items():
            replaced = '_k:' + key
            if args.count(replaced):
                index = args.index(replaced)
                new_query += [(pred,
                    (args[:index] + tuple([value]) + args[index+1:]))]
            #else:
                #print(replaced, args.count(replaced))
            #print(new_query)
    #print(query, new_query, key_dict)
    return tuple(new_query)

def _utf8(var):
    if isinstance(var, str):
        return var
    elif isinstance(var, bytes):
        return var.decode('utf-8')
    else:
        raise Exception(f"implement {type(var)}")


def _query(pl=None, query=None, debug=False):
    #print('-----', query)
    if not query:
        return
    if not pl:
        pl = Prolog()
        pl.consult('init.pl')
    if isinstance(query[0], str):
        query = [query]
    query_list = []
    var_list = []
    for pred, args in query:
        arg_list = []
        for arg in args:
            if (isinstance(arg, str) and arg[:3] == '_v:'):
                # and arg[0] == arg[0].upper()
                var = arg[3:]
                var_list += [var]
                arg_list += [var]
            elif (isinstance(arg, str) and '^^' in arg):
                arg_list += [arg]
            elif (isinstance(arg, list)):
                arg_list += [f"{arg}"]
            else:
                arg_list += [f"'{arg}'"]
        arg_str = ','.join(arg_list)
        query_list += [pred + '(' + arg_str + ')']
    query_str = ','.join(query_list)
    if debug:
        print(query_str, end="\n\n")
    return var_list, pl.query(query_str)



def rdf_find(pl, triples):
    q = tuple((('rdf'), tuple(term if term else '_v:X' for term in triple))
              for triple in triples)
    result = query(pl, q)
    if not result:
        return None
    elif len(result) > 1:
        raise Exception(f"Multiple terms fit the query pattern:\n{q}\n"
                        f"They are:\n{result}\n")
    return result[0]['X']


def new_bnode(pl):
    return query(pl, [('rdf_create_bnode', ['_v:X'])])[0]['X']


def xsd_type(literal, xsd_t):
    if isinstance(literal, str):
        literal = "'" + literal.replace("'", "\\'") + "'"
    elif isinstance(literal, int):
        pass
    else:
        raise Exception(f"implement {type(literal)}")
    return f"{literal}^^'{XSD[xsd_t]}'"


def xsd_untype(rdf_literal):
    print(rdf_literal, type(rdf_literal))
    if isinstance(rdf_literal, str):
        return rdf_literal,
    elif isinstance(literal, int):
        pass
    else:
        raise Exception(f"implement {type(literal)}")
    return f"{literal}^^'{XSD[xsd_t]}'"


def LDateTime(pl, **kwargs):
    argnames = ('year', 'month', 'day', 'hour', 'minute', 'second')
    xsdtypes = ('gYear', 'gMonth', 'gDay', *(['nonNegativeInteger'] * 3))

    dt_uri = "ldatetime"
    dt_preds = []
    for arg, xsd_t in zip(argnames, xsdtypes):
        if (dt_frag := kwargs.get(arg)):
            dt_preds += [(XCAT[arg], xsd_type(dt_frag, xsd_t))]
            dt_uri += '.' + str(dt_frag)
        else:
            break
    if not query(pl, [('rdf', (dt_uri, RDF.type, XCAT.LDateTime))]):
        query(pl, [('rdf_assert', (dt_uri, RDF.type, XCAT.LDateTime))]
              + [('rdf_assert', (dt_uri, pred, obj)) for pred, obj in dt_preds])
    return dt_uri


def TrackList(pl, term_list, debug=False):
    seq = query(pl, debug=debug,
                query=[('rdf_assert_seq', ('_v:X', term_list))])[0]['X']
    query(debug=debug, query=(('rdf_retractall', (seq, RDF.type, RDF.Seq)),
                              ('rdf_assert', (seq, RDF.type, XCAT.TrackList))
                              ))
    return seq


def direct_subclasses(pl, resource=RDFS.Resource):
    res = query(pl, [('rdf', ('_v:Subclass', RDFS.subClassOf, resource)),
                     ('xcat_label', ('_v:Subclass', '_v:Label'))])
    return sorted([(r['Subclass'], r['Label'].decode('utf-8')) for r in res],
                  key=lambda x: x[1])
