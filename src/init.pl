#!/usr/bin/env swipl

:- use_module(library('semweb/rdf11')).
:- use_module(library('semweb/rdf11_containers')).
:- use_module(library('semweb/rdf_persistency')).


:- rdf_load('../data/vocab/xcat.rdfs').

%:- rdf_load('../data/triples.rdf').
%:- rdf_load_db('../data/pl_store/triples.db').
:- rdf_attach_db('../data/pl_store', [access(read_write)]).
%:- rdf_default_graph(_, '/home/xeroxcat/projects/doubletree/data/triples.rdf').
%:- rdf_default_graph(_, 'file:///home/xeroxcat/projects/doubletree/data/triples.rdf').
%:- rdf_default_graph(_, '../data/triples.rdf').
%
%:- rdf_save_db('../data/some_out.db').
%:- rdf_save_db('../data/pl_store/triples.db').
:- rdf_register_prefix(xcat, 'http://xeroxc.at/schema#').
