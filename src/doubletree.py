#!/usr/bin/env python3

import os
from collections import namedtuple
import logging as log

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog
import urwid as ur
import urwidtrees as ur_tree

#from rdf_util import discogs
from rdf_util.namespaces import B3, XCAT
#from rdf_util.b3 import file_hash, hashlist_hash
from rdf_util.pl import (query, xsd_type, rdf_find, new_bnode, LDateTime,
                         TrackList, direct_subclasses)


Content = namedtuple('Content', ['label', 'parent', 'children'])


class FocusableText(ur.WidgetWrap):
    def __init__(self, label):
        #url, label = item
        t = ur.Text(label)
        w = ur.AttrMap(t, 'body', 'focus')
        ur.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class RDF_ClassTree(ur_tree.tree.Tree):
    root = RDFS.Resource

    def __init__(self, pl_store):
        self.pl = pl_store
        # Cache for the tree. Schema is {rdf_uri: (label, parent, children)}
        self.content = {self.__class__.root: Content('Resource', None, None)}

    def __getitem__(self, rdf_uri):
        return FocusableText(self.content[rdf_uri].label)

    def _direct_subclasses(self, rdf_uri):
        """Return the direct subclasses of an RDF class

        Caches results from the prolog store.
        """
        if (content := self.content[rdf_uri]).children is None:
            subclasses = []
            if len(subclass_tuples := direct_subclasses(self.pl, rdf_uri)):
                # List of the subclass urls (first tuple entry of each)
                subclasses = list(list(zip(*subclass_tuples))[0])
                for subclass, label in subclass_tuples:
                    self.content[subclass] = Content(label, rdf_uri, None)
            self.content[rdf_uri] = content._replace(children=subclasses)
        return self.content[rdf_uri].children

    def _get_siblings(self, rdf_uri):
        parent = self.content[rdf_uri].parent
        if parent:
            return self.content[parent].children

    # Tree API
    def parent_position(self, rdf_uri):
        return self.content[rdf_uri].parent

    def first_child_position(self, rdf_uri):
        children = self._direct_subclasses(rdf_uri)
        return children[0] if len(children) else None

    def last_child_position(self, rdf_uri):
        children = self._direct_subclasses(rdf_uri)
        return children[-1] if len(children) else None

    def next_sibling_position(self, rdf_uri):
        candidate = None
        if (siblings := self._get_siblings(rdf_uri)):
            index = siblings.index(rdf_uri)
            if index + 1 < len(siblings):
                candidate = siblings[index + 1]
        return candidate

    def prev_sibling_position(self, rdf_uri):
        candidate = None
        if (siblings := self._get_siblings(rdf_uri)):
            index = siblings.index(rdf_uri)
            if index > 0:
                candidate = siblings[index - 1]
        return candidate


class Welcome(ur.WidgetWrap):
    def __init__(self):
        self.options = []

        #display_widget = ur.

def unhandled_input(k):
    #exit on q
    if k in ['q', 'Q']: raise ur.ExitMainLoop()

def doubletree():
    #Initialize Prolog Session
    pl = Prolog()
    pl.consult('init.pl')

    palette = [
        ('body', 'black', 'light gray'),
        ('focus', 'light gray', 'dark blue', 'standout'),
        ('bars', 'dark blue', 'light gray', ''),
        ('arrowtip', 'light blue', 'light gray', ''),
        ('connectors', 'light red', 'light gray', ''),
    ]
    dtree = RDF_ClassTree(pl)
    decorated_tree = ur_tree.decoration.CollapsibleArrowTree(
            dtree, is_collapsed=(lambda x: dtree.parent_position(x)),
            arrow_tip_char=None,
            icon_frame_left_char=None, icon_frame_right_char=None,
            icon_collapsed_char=u'\u25B6', icon_expanded_char=u'\u25B7',)

    # stick it into a ur_tree.widgets.TreeBox and use 'body' color attribute for gaps
    tb = ur_tree.widgets.TreeBox(decorated_tree, focus=RDF_ClassTree.root)
    root_widget = ur.AttrMap(tb, 'body')
    ur.MainLoop(root_widget, palette,
                unhandled_input=unhandled_input).run() # go

if __name__ == "__main__":
    log.basicConfig(filename='dbltree.log', encoding='utf-8', level=log.DEBUG)
    doubletree()
