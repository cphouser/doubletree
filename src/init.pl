#!/usr/bin/env swipl

:- use_module(library('apply')).
:- use_module(library('semweb/rdf11')).
:- use_module(library('semweb/rdfs')).
:- use_module(library('semweb/rdf11_containers'), except([rdfs_member/2])).
:- use_module(library('semweb/rdf_persistency')).
:- use_module(library('semweb/rdf_portray')).%doesn't seem to work with swipl
:- use_module(library('solution_sequences')).

:- rdf_load('../data/vocab/xcat.rdfs').
:- rdf_load('../data/vocab/rdfs.rdfs').
:- rdf_load('../data/vocab/xsd.rdfs').
:- rdf_attach_db('../data/pl_store', [access(read_only)]).
:- rdf_register_prefix(xcat, 'http://xeroxc.at/schema#').

:- ensure_loaded('dates.pl').

rdf_read :-
    rdf_detach_db(),
    rdf_attach_db('../data/pl_store', [access(read_only)]).

rdf_write :-
    rdf_detach_db(),
    rdf_attach_db('../data/pl_store', [access(read_write)]).

xcat_filepath(Resource, Filepath) :-
    rdf(Resource, xcat:file, File),
    rdf(File, xcat:path, Filepath^^xsd:string).

xcat_maybe_filepath(Resource, Filepath) :-
    xcat_filepath(Resource, Filepath)
    ;            \+   rdf(Resource, xcat:file, _).


xcat_tracklist(Release, RecordingList) :-% FileList) :-
    rdf(Release, rdf:type, xcat:'Release'),
    rdf(Release, xcat:tracklist, Tracklist),
    rdf_seq(Tracklist, RecordingList).%,

xcat_tracklist_filepaths(Release, FileList) :-
    xcat_tracklist(Release, RecordingList),
    maplist(xcat_filepath, RecordingList, FileList).

xcat_missing_filepath(Recording) :-
    rdf(Recording, rdf:type, xcat:'Recording'),
    \+ rdf(Recording, xcat:file, _File).

xcat_incomplete_tracklist(Release, Tracklist) :-
    xcat_tracklist(Release, RecordingList),
    rdf(Release, xcat:tracklist, Tracklist),
    maplist(xcat_missing_filepath, RecordingList).

xcat_apply_recording_path(Recording, Filepath, Encoding) :-
    rdf(Recording, xcat:file, File),
    rdf(File, xcat:path, Filepath),
    rdf(File, xcat:encoding, Encoding^^xsd:string), !.
xcat_apply_recording_path(Recording, Filepath, Encoding) :-
    xcat_missing_filepath(Recording),
    rdf(File, xcat:path, Filepath),
    rdf_update(File, rdf:type, xcat:'File', object(xcat:'AudioFile')),
    rdf_assert(File, xcat:encoding, Encoding^^xsd:string),
    rdf_assert(File, xcat:recording, Recording),
    rdf_assert(Recording, xcat:file, File).

xcat_type(Resource, Class) :-
    Resource = _^^Class, !.
xcat_type(Resource, Class) :-
    rdf(Resource, rdf:type, Class).

xcat_label(Resource, Label) :-
    rdf(Resource, rdfs:label, Label^^xsd:string).

xcat_print(Resource, Class, Value) :-
    Resource = Value^^ClassURI,
    xcat_print(ClassURI, Class), !.
xcat_print(LDateTime, Class, Print) :-
    exists_source('dates.pl'),
    rdf(LDateTime, rdf:type, xcat:'LDateTime'),
    xcat_print_date(LDateTime, Print),
    Class = 'LDateTime'.
xcat_print(AudioFile, Encoding, Value) :-
    rdf(AudioFile, rdf:type, xcat:'AudioFile'),
    rdf(AudioFile, xcat:encoding, EncodingLiteral),
    xcat_print(EncodingLiteral, Encoding),
    rdf(Recording, xcat:file, AudioFile),
    xcat_print(Recording, Value).
xcat_print(Resource, Class, Value) :-
    (   rdf(Resource, xcat:name, Value^^xsd:string);
        rdf(Resource, xcat:title, Value^^xsd:string);
        rdf(Resource, rdfs:label, Value^^xsd:string)
    ),
    rdf(Resource, rdf:type, ClassURI),
    xcat_label(ClassURI, Class).

xcat_print(Resource, Value) :-
    xcat_print(Resource, _, Value).

xcat_has_releases(Resource, Release) :-
    rdf(Release, rdf:type, xcat:'Release'),
    rdf(Resource, xcat:made, Release).

% write operations; might need to complicate for supporting
% predicate modifications, might break already if changing
% literals.

xcat_merge_into(This, That) :-
    rdf_update(This, _, _, subject(That)),
    rdf_update(_, _, This, object(That)).

xcat_retract(Resource) :-
    rdf_retractall(Resource, _, _),
    rdf_retractall(_, _, Resource).
