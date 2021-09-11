#!/usr/bin/env python3
#
from rdf_util.pl import RPQ, VarList
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdf_util.namespaces import XCAT

def print_tree(query, indent=0):
    for key, display_str in query.items():
        print('\t' * indent + f'{display_str} ({key})')
        descendant = query.child_query(key)
        print_tree(descendant, indent + 1)

a = VarList(['A', 'B', 'C'])

b = VarList('one: {One}. two: {Two}, three: {}')

c = VarList('first: {}. second: {Second}, third: {}')
#VarList('{23}  {} {##} 33')
#VarList('asd{23}  {} {##} 33}')
#for varlist in [a, b, c]:
#    print(varlist.format(2, '56', False))
#    print(varlist.format('x', True, A=90))
#    print(varlist.format(0.35, Two=print, A=90))
#    print()

rpq = RPQ('init.pl')

#subclasses = rpq.query(
#        'ChildClass',
#        f"rdf(ChildClass, '{RDFS.subClassOf}', ParentClass), "
#        'xcat_label(ChildClass, Label)',
#        '~{Label}~',
#        ('ParentClass', RDFS.Resource),
#        recursive=True)
#
#print_tree(subclasses)
#print(subclasses.items())
#
#print(repr(subclasses))
#print("---")
query = rpq.querylist([
            ['Artist',
             f'rdfs_individual_of(Artist, Class), xcat_print(Artist, _, Name)',
             '{Name} <{Artist}>',
             ('Class', XCAT.Artist),
             f'xcat_has_releases(Artist, _)',
            ],
            ['Album',
             f"rdf(Artist, '{XCAT.made}', Album), xcat_print(Album, _, Name), "
             f"rdf(Album, '{RDF.type}', '{XCAT.Release}')",
             '{Name} <{Album}>',
             ('Artist', None)
            ],
            ['[Track]',
             "xcat_tracklist(Release, Track)",
             '{TLabel} <{Track}>',
             ('Release', None),
             f"xcat_print(Track, _, TLabel)",
             dict(q_by=False)
             ]])

query = rpq.querylist([
            ['URI',
             f"rdfs_individual_of(URI, InstanceClass)",
             '[{Class}] {Label} <{URI}>',
             ('InstanceClass', XCAT.LDateTime),
             'xcat_print(URI, Class, Label)',
             dict(null=True)]
    ])

print(query)
print_tree(query)
#print(*query.keys(), sep='\n')
