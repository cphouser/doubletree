#!/usr/bin/env python3

import mpd_util
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import XCAT
from rdf_util.pl import ParentVar, ChildVar, ProtoQuery

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
    "rdfs_individual_of(Instance, InstanceClass), "
    "xcat_print(Instance, Label)",
    "{Label} <{Instance}>",
    ParentVar('InstanceClass')
]

within_date = [
    ChildVar("OtherDT", rdf_type=XCAT.LDateTime),
    "xcat_within(LDateTime, OtherDT), "
    "rdf_is_iri(OtherDT), xcat_print(OtherDT, DTLabel)",
    "{DTLabel}",
    ParentVar('LDateTime', rdf_type=XCAT.LDateTime),
    dict(q_by="{OtherDT}")
]

during_date = [
    ChildVar("Subject"),
    "rdf(Subject, Predicate, LDateTime), "
    "xcat_print(Subject, SubjClass, SubjLabel), "
    "xcat_label(Predicate, PredLabel)",
    "{SubjLabel} <{SubjClass}> {PredLabel}",
    ParentVar('LDateTime', rdf_type=XCAT.LDateTime),
    dict(q_by="{PredLabel}{SubjLabel}")
]

tree_views = {
    'instance_list': [
        ProtoQuery('URI',
                   "rdfs_individual_of(URI, InstanceClass)",
                   '[{Class}] {Label} <{URI}>',
                   ParentVar('InstanceClass', resource=RDFS.Resource),
                   'xcat_print(URI, Class, Label)',
                   null=True)
    ], 'artist_releases': [
        ProtoQuery(ChildVar('Artist', rdf_type=False),
                   'rdfs_individual_of(Artist, Class), '
                   'xcat_print(Artist, Name)',
                   '{Name}',
                   ParentVar('Class', resource=XCAT.Artist),
                   'xcat_has_releases(Artist, _)'),
        ProtoQuery(f'Album::{XCAT.Release}',
                   f"rdf(Artist, '{XCAT.made}', Album), "
                   "xcat_print(Album, Name)",
                   '{Name}',
                   ParentVar('Artist')),
        ProtoQuery(ChildVar('Track', unpack_list=True),
                   "xcat_tracklist(Release, Track)",
                   '{TLabel}',
                   ParentVar('Release'),
                   f"xcat_print(Track, TLabel)",
                   q_by=False),
    ], 'dates': [
        ProtoQuery(ChildVar('LDT_Year', rdf_type=False),
                   'rdfs_individual_of(DateTime, InstanceClass), '
                   'xcat_year(DateTime, LDT_Year), '
                   "xcat_print_year(LDT_Year, YLabel)",
                   '{YLabel}',
                   ParentVar('InstanceClass', resource=XCAT.LDateTime),
                   unique=True),
        ProtoQuery('LDT_Month',
                   "xcat_same_year(ParentDT, DateTime), "
                   "xcat_month(DateTime, LDT_Month), "
                   "xcat_print_month(LDT_Month, MLabel, MInt)",
                   "{MLabel}",
                   ParentVar('ParentDT'),
                   unique=True, q_by="{MInt}"),
        ProtoQuery('LDT_Day',
                   "xcat_same_month(ParentDT, DateTime), "
                   "xcat_day(DateTime, LDT_Day), "
                   "xcat_print_day(LDT_Day, DLabel)",
                   "{DLabel}",
                   ParentVar('ParentDT'),
                   unique=True, q_by='{DateTime}'),
        ProtoQuery('LDT_Hour',
                   "xcat_same_day(ParentDT, DateTime), "
                   "xcat_hour(DateTime, LDT_Hour), "
                   "xcat_print_hour(LDT_Hour, HLabel)",
                   "{HLabel}:00",
                   ParentVar('ParentDT'),
                   unique=True, q_by='{DateTime}'),
        ProtoQuery('LDT_Minute',
                   "xcat_same_hour(ParentDT, DateTime), "
                   "xcat_minute(DateTime, LDT_Minute), "
                   "xcat_print(LDT_Minute, DTLabel)",
                   "{DTLabel}",
                   ParentVar('ParentDT'),
                   unique=True, q_by='{DateTime}'),
    ]
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
