#!/usr/bin/env python3

import mpd_util
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import XCAT

instance_properties = [
    'ObjURI',
    "rdf(Subject, PredURI, ObjURI), "
    "xcat_label(PredURI, Predicate), "
    "xcat_print(ObjURI, Class, Object)",
    "--{Predicate}--> {Object} <{Class}>",
    ('Subject', None),
    dict(child_type=False)
]

instance_is_property = [
    'SubjURI',
    "rdf(SubjURI, PredURI, ObjURI), "
    "xcat_label(PredURI, Predicate), "
    "xcat_print(SubjURI, Class, Subject)",
    "{Subject} <{Class}> --{Predicate}--> ",
    ('ObjURI', None),
    dict(child_type=False)
]

class_hierarchy = [
    'ChildClass',
    f"rdf(ChildClass, '{RDFS.subClassOf}', ParentClass), "
    'xcat_label(ChildClass, Label)',
    '{Label}',
    ('ParentClass', RDFS.Resource),
    dict(recursive=True)]

tree_views = {
    'instance_list': {
        'query': [
            ['URI',
             f"rdfs_individual_of(URI, InstanceClass)",
             '[{Class}] {Label} <{URI}>',
             ('InstanceClass', None),
             'xcat_print(URI, Class, Label)',
             dict(null=True)]
        ], 'root': RDFS.Resource},
    'artist_releases': {
        'query': [
            ['Artist',
             f'rdfs_individual_of(Artist, Class), xcat_print(Artist, Name)',
             '{Name} <{Artist}>',
             ('Class', None),
             f'xcat_has_releases(Artist, _)',
             dict(child_type=False)
            ],
            ['Album',
             f"rdf(Artist, '{XCAT.made}', Album), xcat_print(Album, Name), "
             f"rdf(Album, '{RDF.type}', '{XCAT.Release}')",
             '{Name} <{Album}>',
             ('Artist', None)
            ],
            ['[Track]',
             "xcat_tracklist(Release, Track)",
             '{TLabel} <{Track}>',
             ('Release', None),
             f"xcat_print(Track, TLabel)",
             dict(q_by=False)],
        ], 'root': XCAT.Artist,
        },
    'dates': {
        'query': [
            ['DateTime',
             'rdfs_individual_of(DateTime, InstanceClass), '
             f"xcat_print_year(DateTime, YLabel)",
             '{YLabel}',
             ('InstanceClass', None),
             dict(unique=True, child_type=False)],
            ['DateTime',
             "xcat_same_year(ParentDT, DateTime), "
             "xcat_print_month(DateTime, MLabel, MInt)",
             ("{MLabel}"),
             ('ParentDT', None),
             dict(unique=True, q_by="{MInt}")],
            ['DateTime',
             "xcat_same_month(ParentDT, DateTime), "
             f"rdf(DateTime, '{XCAT.day}', Day), xcat_print(DateTime, DLabel)",
             ("{DLabel}"),
             ('ParentDT', None),
             dict(unique=True, q_by='{DateTime}')],
            ['DateTime',
             "xcat_same_day(ParentDT, DateTime), "
             f"rdf(DateTime, '{XCAT.hour}', Hour), xcat_print(DateTime, HLabel)",
             ("{HLabel}"),
             ('ParentDT', None),
             dict(unique=True, q_by='{DateTime}')],
        ], 'root': XCAT.LDateTime
    }
}

track_format_query = [
    "RecURI",
    "xcat_filepath(RecURI, FilePathStr), xcat_print(RecURI, Recording)",
    ['Recording', 'Artist', 'Release', 'Year'],
    ("FilePathStr", None),
    "rdf(RecURI, xcat:maker, ArtistURI), xcat_print(ArtistURI, Artist), "
    "rdf(RecURI, xcat:released_on, RelURI), xcat_print(RelURI, Release), "
    "rdf(RelURI, xcat:published_during, DateTime), "
    "rdf(DateTime, xcat:year, YearLit), xcat_print(YearLit, Year)",
    dict(null=True)
]

instance_ops = {
    str(XCAT.Recording): {
        'enter': (('xcat_filepath', ('_k:key', '_v:Path')),
                  mpd_util.add_to_list),
        },
    str(XCAT.Release): {
        'enter': (('xcat_tracklist_filepaths', ('_k:key', '_v:Paths')),
                  mpd_util.add_to_list),
        }
    }
