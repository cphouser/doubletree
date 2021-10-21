#!/usr/bin/env python3

from typing import Optional, Union
from frozendict import frozendict
import logging as log
import re
from functools import total_ordering
from collections import namedtuple
from dataclasses import dataclass, replace

from pyswip.prolog import Prolog
from pyswip import easy
from rdflib.namespace import RDF, RDFS, XSD
from indexed import IndexedOrderedDict

from rdf_util.namespaces import XCAT, B3

@dataclass
class ParentVar:
    variable: str
    rdf_type: Union[str, bool] = True
    resource: Optional[str] = None

    def __str__(self):
        if self.rdf_type is True:
            eq = str(self.resource)
        else:
            eq = f"{self.resource}::{self.rdf_type}"
        return f"{self.variable} EQUALS {eq}"

    @classmethod
    def parse(cls, string_expr):
        var, val_expr = string_expr.split(" EQUALS ")
        if val_expr:
            index = val_expr.find("::")
            if index == -1:
                return cls(var, val_expr)
            resource, typ_expr = val_expr.split("::")
            if not resource:
                return cls(var, None, typ_str)
            if typ_expr == "False":
                return cls(var, resource, False)
            return cls(var, resource, typ_expr)
        else:
            # right error?
            raise TypeError(f'Invalid Parent Syntax: {string_expr}')


    def copy(self):
        return replace(self)


class RPQuery:
    """
    [WITH Parent EQUALS <RDF_Resource>::<RDF_Type>|<RDF_Resource>|::<RDF_Type>]
    SELECT Child[::<RDF_Type>|False] [AS <Format Expression>]
    FROM <Prolog Query> [BY <Format Expression>]
    [WHERE <Prolog Query>]
    [RECURSIVE] [NULL] [UNIQUE]
                [... <Descendant Queries>]
    """
    def __init__(self, pl, key, q_from, q_as=None, parent=None,
                 q_where=None, q_by=None, unique=False, recursive=False,
                 desc_q=None, null=False, child_type=None):
        if isinstance(parent, str):
            self.parent = TypedVar.parse(parent)
        else:
            self.parent = parent
        self.q_from = q_from
        self.q_where = q_where
        self.q_as = q_as
        self.q_by = q_by
        self.key = key
        self.unique = unique
        self.recursive = recursive
        self.null = null
        self.desc_q = desc_q
        self.pl = pl
        self._results = None
        self._children = {}
        # TODO add verify
        self.child_type = child_type


    def copy(self, par_ref=None):
        parent = self.parent.copy()
        if par_ref:
            parent.resource = par_ref
        copy = RPQuery(self.pl, self.key, self.q_from, self.q_as, parent,
                       self.q_where, self.q_by, self.unique, self.recursive,
                       self.desc_q, self.null, self.child_type)
        return copy

    #@property
    #def parent(self):
    #    return self._parent[1]

    #@parent.setter
    #def parent(self, value):
    #    self._parent = (self._parent[0], value)

    def _query(self):
        if self._results is not None:
            return self._results
        # replace parent variable w/ its value
        q_from, q_where = (None, None)
        if self.parent:
            if self.parent.resource:
                p_value_str = self.parent.resource.replace("'", "\\'")
                q_from = self.q_from.replace(self.parent.variable,
                                            f"'{p_value_str}'")
                if self.q_where:
                    q_where = self.q_where.replace(self.parent.variable,
                                                f"'{p_value_str}'")
            if self.parent.rdf_type:
                pass #(prepend a typedef query)
        else:
            q_from = self.q_from
            if self.q_where:
                q_where = self.q_where

        # if key is a list we need to retrieve the elements
        if self.key[0] == '[' and self.key[-1] == ']':
            key = self.key[1:-1]
            process_list = True
        else:
            key = self.key
            process_list = False

        # add term querying type of the key
        if self.child_type is not False:
            if process_list and self.q_where:
                q_where += f", xcat_type({key}, RPQ_KeyType)."
            else:
                q_from += f", xcat_type({key}, RPQ_KeyType)."

        # retrieve q_from results
        results = {}
        log.debug(q_from)
        for from_result in self.pl.query(q_from):
            if process_list:
                list_result = from_result.pop(key)
                for result in list_result:
                    result = _utf8(result)
                    results[result] = {**from_result, key: result}
            else:
                results[from_result[key]] = from_result
        log.debug(f"{len(results)} results")
        # query q_where using each key
        if self.q_where:
            for k, result in dict(results).items():
                k_value_str = _utf8(k).replace("'", "\\'")
                this_q_where = q_where.replace(key, f"'{k_value_str}'")
                where_query = self.pl.query(this_q_where)
                if (where_result := next(where_query, False)) is not False:
                    result.update(where_result)
                elif not self.null:
                    del results[k]
                list(where_query)
        log.debug(f"now {len(results)} results")

        self._results = IndexedOrderedDict()
        q_as = VarList(self.q_as) if self.q_as else VarList(key)
        # sort results using q_by varlist
        if self.q_by is None:
            q_by = q_as
        else:
            q_by = self.q_by

        val_set = set()
        if q_by:
            q_by = VarList(q_by)
            for key in sorted(results, key=lambda k: q_by.result(**results[k])):
                result = q_as.result(**results[key])
                # if unique delete keys with identical print forms
                if self.unique and str(result) in val_set:
                    continue
                val_set.add(str(result))
                self._results[key] = result
        else:
            for key in results:
                result = q_as.result(**results[key])
                if self.unique and str(result) in val_set:
                    continue
                val_set.add(str(result))
                self._results[key] = result

        return self._results


    def items(self):
        return self._query().items()


    def values(self):
        return self._query().values()


    def keys(self):
        return self._query().keys()


    def __iter__(self):
        yield from self._query().keys()


    def __getitem__(self, key):
        return self._query()[key]


    def __len__(self):
        return len(self._query())


    def first_item(self):
        if len(self):
            return self[self.keys()[0]]
        else:
            return {}


    def child_query(self, key):
        if key in self._children:
            return self._children[key]
        if key not in self._results:
            log.debug(self.parent)
            log.debug(key)
            raise KeyError("Should i handle this?")
        if self.recursive:
            self._children[key] = self.copy(key)
        elif self.desc_q is not None:
            self._children[key] = self.desc_q.copy(key)
        else:
            self._children[key] = {}
        return self._children[key]


    def __str__(self):
        parent = f"WITH {self.parent}\n" if self.parent else ""
        string = '\n\t'.join([f'RPQuery:\n\t{parent}',
                              f'SELECT {self.key} AS "{self.q_as}"',
                              f'FROM {self.q_from} '])
        if self.q_by:
            string += f'BY: {self.q_by}'
        if self.q_where:
            string += f'\n\tWHERE: {self.q_where}'
        flag_string = []
        if self.recursive:
            flag_string += ['(recursive)']
        if self.unique:
            flag_string += ['(unique)']
        if self.null:
            flag_string += ['(null)']
        if self.child_type is False:
            flag_string += ['(no child type)']
        if self._results is not None:
            flag_string += [f'({len(self._results)} results)']
        if flag_string:
            string += '\n\t' + ' '.join(flag_string)
        if self.desc_q is not None:
            desc_str = str(self.desc_q)
            for line in desc_str.splitlines()[1:]:
                string += f'\n\t{line}'
        return string


class RPQ:
    def __init__(self, *consult_files, write_mode=False):
        self._pl = Prolog()
        self.write_mode = write_mode
        for consult_file in consult_files:
            self._pl.consult(consult_file)
        if write_mode is True:
            list(self._pl.query(RPAssert._enter))


    def query(self, *args, **kwargs):
        args = list(args)
        kwargs = dict(kwargs)
        for idx, arg in enumerate(args):
            if isinstance(arg, dict):
                more_kwargs = args.pop(idx)
                kwargs.update(more_kwargs)
        return RPQuery(self._pl, *args, **kwargs)


    def querylist(self, queries):
        desc_query = None
        for query in reversed(queries):
            args = []
            kwargs = {}
            if isinstance(query, dict):
                kwargs = dict(query)
            if isinstance(query, list):
                args = list(query)
                for idx, obj in enumerate(args):
                    if isinstance(obj, dict):
                        kwargs = obj
                        args.pop(idx)
            desc_query = RPQuery(self._pl, *args, desc_q=desc_query, **kwargs)
        return desc_query


    def boolquery(self, *queries):
        query = self._pl.query(" ,".join(queries))
        if (result := next(query, False)) is not False:
            list(query)
            return True
        return False


    def simple_query(self, query, unique=False):
        results = self.uns_query(query)
        if len(results) > 1:
            results = [_utf8(result.pop(next(iter(result))))
                       for result in results]
            if unique:
                raise Exception(f"Multiple terms fit the query pattern:\n"
                                f"{query}\nThey are:\n{results}\n")
            return results
        elif results:
            return _utf8(results[0].pop(next(iter(results[0])), None))


    def rassert(self, *statements):
        return RPAssert(self._pl, *statements, write_mode=self.write_mode
                        ).execute()


    def new_bnode(self):
        result = RPAssert(self._pl, "rdf_create_bnode(X)",
                          write_mode=self.write_mode).execute()
        return result[0]['X']


    def new_seq(self, term_list):
        result = RPAssert(self._pl, f"rdf_assert_seq(X, {term_list})",
                          write_mode=self.write_mode).execute()
        return result[0]['X']


    def TrackList(self, release, term_list):
        seq = self.new_seq(term_list)
        return RPAssert(self._pl,
                f"rdf_retractall('{seq}', '{RDF.type}', '{RDF.Seq}')",
                f"rdf_assert('{seq}', '{RDF.type}', '{XCAT.TrackList}')",
                f"rdf_assert('{release}', '{XCAT.tracklist}', '{seq}')"
        ).execute()


    def uns_query(self, query):
        return list(self._pl.query(query))


class RPAssert:
    _enter = "rdf_write"
    _exit = "rdf_read"
    def __init__(self, pl, *statements, write_mode=False):
        self.statements = statements
        self.write_mode = write_mode
        self.pl = pl


    def execute(self):
        if not self.write_mode:
            log.debug(list(self.pl.query(self._enter)))
        log.debug("ASSERT\n" + ",\n".join(self.statements))
        res = list(self.pl.query(", ".join(self.statements)))
        log.debug(res)
        if not self.write_mode:
            log.debug(list(self.pl.query(self._exit)))
        return res


class VarList:
    _var = 'RPQ_A'

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
            if (var := self._var[:-1] + chr(ord(self._var[-1])
                                            + self._start + i)
                    ) not in self.var_list:
                self._start = self._start + i + 1
                return var
        raise Exception(f"out of anonymous variables (total: {self._start})")


    def result(self, *args, **kwargs):
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
        return QueryResult(self.print_str.format(*val_dict.values()), val_dict)


    def __repr__(self):
        return self.print_str.format(*self.var_list)


@total_ordering
class QueryResult:
    def __init__(self, string, vals):
        self.string = string
        self.vals = vals
        self.type = vals.get('RPQ_KeyType')


    def __str__(self):
        return self.string


    def __repr__(self):
        return f'<{self.__class__.__name__} "{self.string}" {self.type}>'


    def __getitem__(self, key):
        return self.vals[key]


    def get(self, key, defaut=None):
        try:
            return self.vals[key]
        except KeyError:
            return default


    def __lt__(self, other):
        return self.string < other.string


    def __eq__(self, other):
        return self.string == other.string


def rdf_unify(rpq, terms):
    bnodes = [t for t in terms if '_:genid' == t[:7]]
    uris = [t for t in terms if '_:genid' != t[:7]]
    log.debug(f"unifying: {bnodes} with {uris}")
    if len(uris) > 1:
        #raise Exception("probably need to handle this interactively")
        uris = sort_uris(uris)
    elif not uris:
        raise Exception("not sure if this is gonna happen")
    uri = uris[0]
    update_list = []
    for node in bnodes + uris[1:]:
        update_list += [
            f"rdf_update('{node}', _, _, subject('{uri}'))",
            f"rdf_update(_, _, '{node}', object('{uri}'))"
        ]
    rpq.rassert(*update_list)
    return uri


def sort_uris(uri_list):
    mb_uris = []
    dg_uris = []
    bc_uris = []
    for uri in uri_list:
        if "musicbrainz.org" in uri:
            mb_uris.append(uri)
        elif "discogs.com" in uri:
            dg_uris.append(uri)
        elif "bandcamp.com" in uri:
            bc_uris.append(uri)
        else:
            raise Exception(f"where is {uri} from?")
    for uris in [mb_uris, dg_uris, bc_uris]:
        if len(uris) > 1:
            log.warning(f"how to merge {uris}?")
    return mb_uris + dg_uris + bc_uris


def all_classes(rpq, subj_class):
    classes = [str(subj_class)]
    while subj_class:
        if (superclass := rpq.simple_query(
                f"rdf('{subj_class}', '{RDFS.subClassOf}', X)", unique=True)):
            classes += [superclass]
        subj_class = superclass
    return classes


def mixed_query(rpq, query, key):
    # gotta do more if we're returning antything
    # TODO silly bad interface should be refactored
    partial_query = []
    for statement in query:
        if callable(statement):
            if partial_query:
                res_args, res_kwargs = query_to_args(rpq, partial_query)
                statement(*res_args, **res_kwargs)
            else:
                statement()
            partial_query = []
        elif isinstance(statement, str):
            partial_query += [statement.format(key)]
        else: log.warn(f'bad type: {type(statement)} {statement}')
    if partial_query:
        res_args, res_kwargs = query_to_args(rpq, partial_query)


def query_to_args(rpq, query):
    result_args = []
    result_kwargs = {}
    results = rpq.uns_query(", ".join(query))
    for result in results:
        log.debug(result)
        for var, val in result.items():
            if isinstance(val, list):
                log.debug(f'{var} is list: {val}')
                for list_elem in val:
                    result_args += [_utf8(list_elem)]
            else:
                result_kwargs[var] = _utf8(val)
    return result_args, result_kwargs


def _utf8(var):
    if isinstance(var, str):
        return var
    elif isinstance(var, bytes):
        return var.decode('utf-8')
    elif isinstance(var, int):
        return var
    elif isinstance(var, easy.Atom):
        return str(var)
    if var is None:
        return ""
    else:
        raise Exception(f"implement {type(var)}")


def xsd_type(literal, xsd_t):
    if isinstance(literal, str):
        literal = escape_string(literal)
    elif isinstance(literal, int):
        pass
    else:
        raise Exception(f"implement {type(literal)}")
    return f"{literal}^^'{XSD[xsd_t]}'"


def escape_string(literal):
    return "'" + literal.replace("'", "\\'") + "'"


def LDateTime(rpq, **kwargs):
    argnames = ('year', 'month', 'day', 'hour', 'minute', 'second')
    xsdtypes = ('gYear', 'gMonth', 'gDay', *(['nonNegativeInteger'] * 3))

    dt_uri = "ldatetime"
    dt_preds = []
    for arg, xsd_t in zip(argnames, xsdtypes):
        if (dt_frag := kwargs.get(arg)):
            dt_preds += [(XCAT[arg], xsd_type(dt_frag, xsd_t))]
            dt_uri += '.' + str(dt_frag).rjust(2, '0')
        else:
            break
    if not rpq.boolquery(f"rdf('{dt_uri}', '{RDF.type}', '{XCAT.LDateTime}')"):
        assert_list = [
            f"rdf_assert('{dt_uri}', '{RDF.type}', '{XCAT.LDateTime}')"
        ] + [
            f"rdf_assert('{dt_uri}', '{pred}', {obj})" for pred, obj in dt_preds
        ]
        rpq.rassert(*assert_list)
    return dt_uri


def TrackList(rpq, term_list):
    seq = rpq.new_seq(term_list)
    rpq.rassert(f"rdf_retractall('{seq}', '{RDF.type}', '{RDF.Seq}')",
                f"rdf_assert('{seq}', '{RDF.type}', '{XCAT.TrackList}')")
    return seq


def nometa_file_node(rpq, data):
    #TODO fix this bad gross interface
    file_path = xsd_type(data['path'], 'string')
    _hash = xsd_type(data['_hash'], 'string')
    file_URN = B3[data['_hash']]
    rpq.rassert(*[
        f"rdf_assert('{file_URN}', '{RDF.type}', '{XCAT.File}')",
        f"rdf_assert('{file_URN}', '{XCAT.path}', {file_path})",
        f"rdf_assert('{file_URN}', '{XCAT.hash}', {_hash})",
    ])
    return file_URN


def entries_to_dir(rpq, dir_hash, dirpath, dir_entries):
    #, subdir_hashes):
    path = xsd_type(dirpath, 'string')
    dir_URN = B3[dir_hash]
    dir_hash = xsd_type(dir_hash, 'string')
    assert_list = [
        f"rdf_assert('{dir_URN}', '{RDF.type}', '{XCAT.Directory}')",
        f"rdf_assert('{dir_URN}', '{XCAT.path}', {path})",
        f"rdf_assert('{dir_URN}', '{XCAT.hash}', {dir_hash})",
    ] + [f"rdf_assert('{dir_URN}', '{XCAT.dirEntry}', '{entry}')"
         for entry in dir_entries
    ] # i swear this is redundant but didn't re-test
    #+ [f"rdf_assert('{dir_URN}', '{XCAT.dirEntry}', '{B3[subdir_hash]}')"
    #     for subdir_hash in subdir_hashes
    #]
    rpq.rassert(*assert_list)
