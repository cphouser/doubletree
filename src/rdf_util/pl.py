#!/usr/bin/env python3

from pyswip.prolog import Prolog
from pyswip import easy
from rdf_util.namespaces import XCAT
from rdflib.namespace import RDF, RDFS, OWL, XSD
#from rdflib import URIRef

from frozendict import frozendict
import re


class RPQuery():
    #def __init__(self, pl, parent, keyname, from_query, varlist,
    #             descendants=None, recursive=False):
    def __init__(self, pl, key, q_from, q_as=None, parent=('', None),
                 q_where=None, q_by=None, unique=False, recursive=False,
                 descendants=None):
        if q_as is None:
            q_as = key
        self.parent = parent
        self.q_from = q_from
        self.q_where = q_where
        self.q_as = VarList(q_as)
        if not q_by:
            q_by = self.q_as
        self.q_by = VarList(q_by)
        self._results = None
        self.key = key
        self.unique = unique
        self.recursive = recursive
        self.descendants = descendants
        self.pl = pl


    def _items(self):
        if self._results is not None:
            return self._results
        p_key, p_value = self.parent
        if p_value:
            p_value_str = str(p_value).replace("'", "\\'")
            q_from = self.q_from.replace(p_key, f"'{p_value_str}'")
            #print(q_from)
        results = {}
        self._results = {}
        #print(f'executing\nSELECT {self.keyname} AS "{self.varlist}"\n'
        #      f'FROM {self.q_from}')
        if isinstance(self.key, list):
            print("this key is a list")
        for result in self.pl.query(q_from):
            results[result[self.key]] = result
        for key in sorted(results,
                          key=lambda k: self.q_by.format(**results[k])):
            self._results[key] = self.q_as.format(**results[key])
        return self._results


    def items(self):
        return self._items().items()


    def values(self):
        return self._items().values()


    def __iter__(self):
        yield from self._items().keys()


    def __getitem__(self, key):
        return self._items()[key]


    def child_query(self, key):
        if key not in self._results:
            raise KeyError("Should i handle this?")
        if self.recursive:
            par_ref = (self.parent[0], key)
            return RPQuery(self.pl, self.key, self.q_from, self.q_as, par_ref,
                           self.q_where, self.q_by, self.unique, self.recursive)


class RPQ():
    def __init__(self, *consult_files):
        self._pl = Prolog()
        for consult_file in consult_files:
            self._pl.consult(consult_file)


    def query(self, *args, **kwargs):
        return RPQuery(self._pl, *args, **kwargs)


class VarList():
    _var = 'A'

    def __init__(self, *args, var_list=None, print_str=None):
        if args and isinstance(args[0], VarList):
            self.print_str = args[0].print_str
            self.var_list = args[0].var_list
            return
        for arg in args:
            if isinstance(arg, list):
                var_list = arg
            elif isinstance(arg, str):
                print_str = arg
        if not print_str:
            self.print_str = "{" + "} | {" * (len(var_list) - 1) + "}"
            self.var_list = var_list
        elif not var_list:
            self._start = 0
            self.var_list = []
            new_str = ""
            for i, frag in enumerate(re.split(r'(\{[^\{\}]*\})', print_str)):
                if (i % 2):
                    new_str += "{}"
                    if not frag[1:-1]:
                        # append anonymous var to varlist
                        self.var_list += [self.anonymous_var()]
                    elif not frag[1:-1].isidentifier():
                        raise NameError(f"{frag} not a valit python id")
                    else:
                        self.var_list += [frag[1:-1]]
                else:
                    new_str += frag
            self.print_str = new_str
        else:
            self.print_str = print_str
            self.var_list = var_list


    def anonymous_var(self):
        for i in range(25 - self._start):
            if (var := chr(ord(self._var) + self._start + i)
                    ) not in self.var_list:
                self._start = self._start + i + 1
                return var
        raise Exception(f"out of anonymous variables (total: {self._start})")


    def format(self, *args, **kwargs):
        val_dict = {key: None for key in self.var_list}
        for key, value in kwargs.items():
            val_dict[key] = _utf8(value)
        for value in args:
            for val in val_dict:
                if not isinstance(val_dict[val], str):
                    val_dict[val] = _utf8(value)
                    break
        for key, val in val_dict.items():
            if val is None:
                val_dict[key] = "."
            #val_dict[key] = _utf8(val_dict[key])
        #print(val_dict)
        return self.print_str.format(*val_dict.values())


    def __repr__(self):
        return self.format(*self.var_list)



def rdf_unify(pl, terms, log=None):
    bnodes = [t for t in terms if '_:genid' == t[:7]]
    uris = [t for t in terms if '_:genid' != t[:7]]
    if log: log.debug(f"unifying: {bnodes} with {uris}")
    if len(uris) > 1:
        raise Exception("probably need to handle this interactively")
    elif not uris:
        raise Exception("not sure if this is gonna happen")
    uri = uris[0]
    for node in bnodes:
        query(pl, (('rdf_update', (node, '_', '_', f"subject('{uri}')")),
                   ('rdf_update', ('_', '_', node, f"object('{uri}')"))),
              write=True, log=log)
    return uri


def all_classes(pl, subject_class):
    classes = [str(subject_class)]
    while subject_class:
        superclass = next(query_gen(pl,
            ('rdf', (subject_class, RDFS.subClassOf, '_v:Superclass'))
                                    ), None)
        if superclass:
            superclass = superclass[0]
            classes += [superclass]
        subject_class = superclass
    return classes


def query(pl=None, query=None, unique=False, write=False, log=None):
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
    if not pl:
        pl = Prolog()
        pl.consult('init.pl')
    if write:
        list(pl.query('rdf_write'))
    _, results = _query(pl, query, log=log)
    result_list = []
    for result in results:
        result_list += [frozendict(result)]
    if write:
        list(pl.query('rdf_read'))
    if log:
        log.debug(f"{query}:\n\t{result_list}")
    return set(result_list) if unique else result_list


def query_gen(pl, query=None, result_type='tuple', unique=False, log=None):
    varlist, results = _query(pl=pl, query=query, unique=unique, log=log)
    for result_expr in results:
        if log:
            log.debug(result_expr)
        if result_type == 'tuple':
            result = []
            for var in varlist:
                if (var_result := result_expr.get(var, None)):
                    if log:
                        log.debug(var_result)
                        log.debug(type(var_result))
                    if isinstance(var_result, list):
                        if log: log.debug('is list')
                        for list_elem in var_result:
                            elem_result = _utf8(list_elem)
                            yield tuple([elem_result])
                        return
                    else:
                        result += [_utf8(var_result)]
            yield tuple(result)


def fill_query(query, key_dict, log=None):
    """
    Returns a query which can be passed to query(). The query passed
    to this function fits that form except may include variables
    prefixed by '_k:'. These variables are replaced by the value in
    key_dict corresponding to the variable name (excluding the '_k:')

    therefore fill_query(('rdf', ('_k:Resource', RDF.type, '_v:Class')),
                         {'Resource': XCAT.Artist})
    will return ('rdf', (XCAT.Artist, RDF.type, '_v:Class'))
    """
    if log:
        log.debug(query)
    if isinstance(query[0], str):
        query = [query]
    new_query = []
    for statement in query:
        if isinstance(statement, tuple):
            pred, args = new_statement = statement
            for key, value in key_dict.items():
                replaced = '_k:' + key
                if args.count(replaced):
                    index = args.index(replaced)
                    new_statement = (pred,
                        (args[:index] + tuple([value]) + args[index+1:]))
            new_query += [new_statement]
        elif callable(statement):
            new_query += [statement]
        elif log: log.warn(f'bad type: {type(statement)} {statement}')
    return tuple(new_query)


def _utf8(var):
    if isinstance(var, str):
        return var
    elif isinstance(var, bytes):
        return var.decode('utf-8')
    elif isinstance(var, easy.Atom):
        return var
    else:
        raise Exception(f"implement {type(var)}")


def _query(pl, query=None, unique=False, log=None):
    if not query:
        return [], []
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
            elif arg == '_':
                arg_list += [arg]
            elif isinstance(arg, str) and ('(' in arg or ')' in arg):
                arg_list += [arg]
            else:
                arg_list += [f"'{arg}'"]
        arg_str = ','.join(arg_list)
        query_list += [pred + '(' + arg_str + ')']
    query_str = ','.join(query_list)
    if unique:
        query_str = f"distinct({query_str})"
    if log: log.debug(query_str)
    return var_list, pl.query(query_str)


def mixed_query(pl, query, log=None):
    partial_query = []
    for statement in query:
        if callable(statement):
            if partial_query:
                res_args, res_kwargs = query_to_args(pl, partial_query, log)
                statement(*res_args, **res_kwargs)
            else:
                statement()
            partial_query = []
        elif isinstance(statement, tuple):
            partial_query += [statement]
        elif log: log.warn(f'bad type: {type(statement)} {statement}')
    if partial_query:
        res_args, res_kwargs = query_to_args(pl, partial_query, log)
    # gotta do more if we're returning antything


def query_to_args(pl, query, log=None):
    result_args = []
    result_kwargs = {}
    varlist, results = _query(pl, query, log)
    for result_expr in results:
        if log: log.debug(result_expr)
        for var in varlist:
            if (var_result := result_expr.get(var, None)):
                if isinstance(var_result, list):
                    if log: log.debug(f'{var} is list')
                    for list_elem in var_result:
                        result_args += [_utf8(list_elem)]
                else:
                    result_kwargs[var] = _utf8(var_result)
    return result_args, result_kwargs


def rdf_find(pl, triples, unique=True):
    q = tuple((('rdf'), tuple(term if term else '_v:X' for term in triple))
              for triple in triples)
    result = query(pl, q)
    if not result:
        return None
    elif len(result) > 1:
        if unique:
            raise Exception(f"Multiple terms fit the query pattern:\n{q}\n"
                            f"They are:\n{result}\n")
        else:
            return [res['X'] for res in result]
    return result[0]['X']


def new_bnode(pl):
    return query(pl, [('rdf_create_bnode', ['_v:X'])], write=True)[0]['X']


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
              + [('rdf_assert', (dt_uri, pred, obj)) for pred, obj in dt_preds],
              write=True)
    return dt_uri


def TrackList(pl, term_list, log=None):
    seq = query(pl, log=log, write=True,
                query=[('rdf_assert_seq', ('_v:X', term_list))])[0]['X']
    query(log=log, query=(('rdf_retractall', (seq, RDF.type, RDF.Seq)),
                          ('rdf_assert', (seq, RDF.type, XCAT.TrackList))
                          ), write=True)
    return seq


def direct_subclasses(pl, resource=RDFS.Resource):
    res = query(pl, [('rdf', ('_v:Subclass', RDFS.subClassOf, resource)),
                     ('xcat_label', ('_v:Subclass', '_v:Label'))])
    return sorted([(r['Subclass'], r['Label'].decode('utf-8')) for r in res],
                  key=lambda x: x[1])
