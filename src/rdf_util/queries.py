#!/usr/bin/env python3

import mpd_util
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import XCAT
from rdf_util.pl import ParentVar, ChildVar

printed_resource = [
    'Res',
    'xcat_print(Resource, Class, String), Res=Resource',
    '{Class}: {String} <{Res}>',
    ParentVar('Resource'),
]

class_hierarchy = [
    'ChildClass',
    f"rdf(ChildClass, '{RDFS.subClassOf}', ParentClass), "
    'xcat_label(ChildClass, Label)',
    '{Label}',
    ParentVar('ParentClass', resource=RDFS.Resource),
    dict(recursive=True)
]

class_instances = [
    ChildVar("Instance", rdf_type=False),
    f"rdfs_individual_of(Instance, InstanceClass), "
    f"xcat_print(Instance, Label)",
    "{Label} <{Instance}>",
    ParentVar('InstanceClass')
]

tree_views = {
    'instance_list': {
        'query': [
            ['URI',
             f"rdfs_individual_of(URI, InstanceClass)",
             '[{Class}] {Label} <{URI}>',
             ParentVar('InstanceClass', RDFS.Resource),
             'xcat_print(URI, Class, Label)',
             dict(null=True)]
        ], 'root': RDFS.Resource},
    'artist_releases': {
        'query': [
            [ChildVar('Artist', rdf_type=False),
             f'rdfs_individual_of(Artist, Class), xcat_print(Artist, Name)',
             '{Name}',
             ParentVar('Class', resource=XCAT.Artist),
             f'xcat_has_releases(Artist, _)',
            ],
            [f'Album::{XCAT.Release}',
             f"rdf(Artist, '{XCAT.made}', Album), xcat_print(Album, Name)",
             '{Name}',
             ParentVar('Artist')
            ],
            [ChildVar('Track', unpack_list=True),
             "xcat_tracklist(Release, Track)",
             '{TLabel}',
             ParentVar('Release'),
             f"xcat_print(Track, TLabel)",
             dict(q_by=False)],
        ], 'root': XCAT.Artist,
        },
    'dates': {
        'query': [
            [ChildVar('DateTime', rdf_type=False),
             'rdfs_individual_of(DateTime, InstanceClass), '
             f"xcat_print_year(DateTime, YLabel)",
             '{YLabel}',
             ParentVar('InstanceClass', resource=XCAT.LDateTime),
             dict(unique=True)],
            ['DateTime',
             "xcat_same_year(ParentDT, DateTime), "
             "xcat_print_month(DateTime, MLabel, MInt)",
             ("{MLabel}"),
             ParentVar('ParentDT'),
             dict(unique=True, q_by="{MInt}")],
            ['DateTime',
             "xcat_same_month(ParentDT, DateTime), "
             f"rdf(DateTime, '{XCAT.day}', Day), "
             "xcat_print_day(DateTime, DLabel)",
             ("{DLabel}"),
             ParentVar('ParentDT'),
             dict(unique=True, q_by='{DateTime}')],
            ['DateTime',
             "xcat_same_day(ParentDT, DateTime), "
             f"rdf(DateTime, '{XCAT.hour}', Hour),"
             " xcat_print_hour(DateTime, HLabel)",
             ("{HLabel}:00"),
             ParentVar('ParentDT'),
             dict(unique=True, q_by='{DateTime}')],
            ['DateTime',
             "xcat_same_hour(ParentDT, DateTime),"
             " rdf(DateTime, '{XCAT.minute}', Minute),"
             " xcat_print(DateTime, DTLabel)",
             ("{DTLabel}"),
             ParentVar('ParentDT'),
             dict(unique=True, q_by='{DateTime}')],
        ], 'root': XCAT.LDateTime
    }
}

track_format_query = [
    "RecURI",
    "xcat_filepath(RecURI, FilePathStr), xcat_print(RecURI, Recording)",
    ['Recording', 'Artist', 'Release', 'Year'],
    ParentVar("FilePathStr"),
    "rdf(RecURI, xcat:maker, ArtistURI), xcat_print(ArtistURI, Artist), "
    "rdf(RecURI, xcat:released_on, RelURI), xcat_print(RelURI, Release), "
    "rdf(RelURI, xcat:published_during, DateTime), "
    "rdf(DateTime, xcat:year, YearLit), xcat_print(YearLit, Year)",
    dict(null=True)
]

instance_ops = {
    str(XCAT.Recording): {
        'a': ("xcat_filepath('{}', Path)", mpd_util.add_to_list),
        },
    str(XCAT.Release): {
        'a': ("xcat_tracklist_filepaths('{}', Paths)", mpd_util.add_to_list)
        }
    }
