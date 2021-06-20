#!/usr/bin/env swipl

:- use_module(library('semweb/rdf11')).
:- use_module(library('semweb/rdf11_containers')).
:- use_module(library('semweb/rdf_persistency')).


:- rdf_load('../data/vocab/xcat.rdfs').

:- rdf_attach_db('../data/pl_store', [access(read_write)]).

:- rdf_register_prefix(xcat, 'http://xeroxc.at/schema#').
