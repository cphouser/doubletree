#!/usr/bin/env python3
import os
import logging as log

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog
import urwid as ur

from palette import palette
from rdf_util.namespaces import XCAT
from rdf_util.pl import (query, xsd_type, rdf_find, new_bnode, LDateTime,
                         TrackList, direct_subclasses, fill_query, query_gen)


tree_views = {
    'class_hierarchy': {
        'leaf': RDFS.Class,
        'root': RDFS.Resource,
        'value_q': ('xcat_label', ('_k:key', '_v:Label')),
        'child_q': ('rdf', ('_v:Subclass', RDFS.subClassOf, '_k:key'))
    }
}


class RDF_NodeText(ur.TreeWidget):
    unexpanded_icon = ur.wimp.SelectableIcon('\u25B6', 0)
    expanded_icon = ur.wimp.SelectableIcon('\u25B7', 0)
    leaf_icon = ur.wimp.SelectableIcon('-', 0)

    def __init__(self, node):
        """Override TreeWidget's initializer to collapse nodes"""
        self._node = node
        self._innerwidget = None
        self.is_leaf = not hasattr(node, 'child_query')
        log.debug(f'{node.get_key()} {self.is_leaf}')
        self.expanded = False
        widget = self.get_indented_widget()
        super(ur.TreeWidget, self).__init__(widget)


    def get_display_text(self):
        return str(list(self.get_node().get_value()))


    def selectable(self):
        return True

    def get_indented_widget(self):
        if self.is_leaf:
            icon = self.leaf_icon
        elif self.expanded:
            icon = self.expanded_icon
        else:
            icon = self.unexpanded_icon

        widget = ur.Columns([('fixed', 1, icon), self.get_inner_widget()],
                               dividechars=1)
        indent_cols = self.get_indent_cols()
        return ur.Padding(widget, width=('relative', 100), left=indent_cols)


class RDF_ParentNode(ur.ParentNode):
    """Node class for a tree representing a set of RDF relationships

    value_q and child_q are each lists of queries or a single query as
    defined in rdf_util.pl.query.


    """
    def __init__(self, pl, key, parent, value_q=None, child_q=None, **kwargs):
        key_dict = {"key": key}
        if child_q:
            if isinstance(child_q, list):
                self.child_query = fill_query(child_q.pop(), key_dict)
            else:
                self.child_query = fill_query(child_q, key_dict)
        else:
            self.child_query = None

        if value_q:
            if isinstance(value_q, list):
                self.value_query = fill_query(value_q.pop(), key_dict)
            else:
                self.value_query = fill_query(value_q, key_dict)
        else:
            self.value_query = None

        self.descendant_queries = (value_q, child_q)
        self.pl = pl
        log.debug(self.value_query)
        result = query_gen(pl, self.value_query)
        value = next(result, None)
        super().__init__(value, parent=parent, key=key)


    def load_child_keys(self):
        # gonna have to do something complicated to actually sort these
        if self.child_query:
            children = [res[0] for res in query_gen(self.pl, self.child_query)]
            log.debug(children)
            return children


    def load_child_node(self, key):
        if (grandchild_template := self.descendant_queries[1]):
            if isinstance(grandchild_template, list):
                grandchild_template = grandchild_template[-1]
            grandchild_query = fill_query(grandchild_template, {"key": key})
            result = query_gen(self.pl, grandchild_query)
            if (res := next(result, False)):
                # TODO: make this log statement non-loadbearing
                log.debug(list(result))
                return RDF_ParentNode(self.pl, key, self,
                                      *self.descendant_queries)
        return RDF_TreeNode(self.pl, key, self,
                            self.descendant_queries[0])


    def load_widget(self):
        return RDF_NodeText(self)


class RDF_TreeNode(ur.TreeNode):
    def __init__(self, pl, key, parent, value_q=None):
        key_dict = {"key": key}
        if value_q:
            if isinstance(value_q, list):
                self.value_query = fill_query(value_q.pop(), key_dict)
            else:
                self.value_query = fill_query(value_q, key_dict)
            result = query_gen(pl, self.value_query)
            value = next(result) if result else None
        else:
            value = tuple([key])
        super().__init__(value, parent=parent, key=key)


    def load_widget(self):
        return RDF_NodeText(self)


class Window(ur.WidgetWrap):
    def __init__(self, pl):
        classtree_root = RDF_ParentNode(pl, RDFS.Resource, None,
                                      **tree_views['class_hierarchy'])
        classtreewin = ur.TreeListBox(ur.TreeWalker(classtree_root))
        classtreewin.offset_rows = 1

        instancetree_root = RDF_ParentNode(pl, RDFS.Resource, None,
                                      **tree_views['class_hierarchy'])
        instancetreewin = ur.TreeListBox(ur.TreeWalker(instancetree_root))
        instancetreewin.offset_rows = 1

        pile = ur.Pile([classtreewin, instancetreewin])

        ur.WidgetWrap.__init__(self, pile)


def global_control(k):
    if k in ['q', 'Q']: raise ur.ExitMainLoop()

def doubletree():
    pl = Prolog()
    pl.consult('init.pl')

    window = Window(pl)
    ur.MainLoop(window, palette, unhandled_input=global_control).run()

if __name__ == "__main__":
    log.basicConfig(filename='dbltree.log', encoding='utf-8', level=log.DEBUG,
                    format='%(levelname)s: %(funcName)s:%(lineno)d: %(message)s')
    doubletree()
