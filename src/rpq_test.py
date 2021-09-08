#!/usr/bin/env python3
#
from rdf_util.pl import RPQ, VarList
from rdflib.namespace import RDF, RDFS, OWL, XSD

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

subclasses = rpq.query(
        'ChildClass',
        f"rdf(ChildClass, '{RDFS.subClassOf}', ParentClass), "
        'xcat_label(ChildClass, Label)',
        '~{Label}~',
        ('ParentClass', RDFS.Resource),
        recursive=True)

print_tree(subclasses)
