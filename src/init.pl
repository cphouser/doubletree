#!/usr/bin/env swipl

:- use_module(library('apply')).
:- use_module(library('strings')).
:- use_module(library('semweb/rdf11')).
:- use_module(library('semweb/rdfs')).
:- use_module(library('semweb/rdf11_containers'), except([rdfs_member/2])).
:- use_module(library('semweb/rdf_persistency')).
:- use_module(library('semweb/rdf_portray')).%doesn't seem to work with swipl

:- rdf_load('../data/vocab/xcat.rdfs').
:- rdf_load('../data/vocab/rdfs.rdfs').
:- rdf_attach_db('../data/pl_store', [access(read_write)]).
:- rdf_register_prefix(xcat, 'http://xeroxc.at/schema#').

xcat_filepath(Resource, Filepath) :-
    rdf(Resource, xcat:file, File),
    rdf(File, xcat:path, Filepath^^xsd:string).

xcat_tracklist_files(Release, FileList) :-
    rdf(Release, rdf:type, xcat:'Release'),
    rdf(Release, xcat:tracklist, Tracklist),
    rdf_seq(Tracklist, RecordingList),
    maplist(xcat_filepath, RecordingList, FileList).

xcat_label(Resource, Label) :-
    rdf(Resource, rdfs:label, Label^^xsd:string).

xcat_print(Resource, Property, Value) :-
    (   rdf(Resource, xcat:name, Value^^xsd:string);
        rdf(Resource, xcat:title, Value^^xsd:string);
        rdf(Resource, rdfs:label, Value^^xsd:string)
    ),
    rdf(Resource, Property, Value)
    .

mpd_add_file(FileURN, Result) :-
    rdf(FileURN, xcat:path, Path^^xsd:string),
    interpolate_string("mpc add '{PATH}'", Cmd, [PATH=Path], _),
    shell(Cmd, Result).

mpd_play(Result) :-
    shell("mpc play", Result).
