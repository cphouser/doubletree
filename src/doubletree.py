#!/usr/bin/env python3

import os
import logging
from datetime import datetime

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog
import urwid as ur

from palette import palette
from log_util import LogFormatter
from rdf_util.namespaces import XCAT
from rdf_util.pl import (query, xsd_type, rdf_find, new_bnode, LDateTime,
                         TrackList, direct_subclasses, fill_query, query_gen)

tree_views = {
    'class_hierarchy': {
        #'leaf': RDFS.Class,
        #'root': RDFS.Resource,
        'value_q': ('xcat_label', ('_k:key', '_v:Label')),
        'child_q': ('rdf', ('_v:Subclass', RDFS.subClassOf, '_k:key'))},
    'instance_list': {
        #'leaf': RDFS.Class,
        #'root': RDFS.Resource,
        'value_q': [
            (('xcat_print', ('_k:key', '_v:Property', '_v:Print')),
             ('rdf_equal', ('_k:key', '_v:URI'))),
            ('xcat_label', ('_k:key', '_v:Label')),
        ], 'child_q': [
            ('rdfs_individual_of', ('_v:Instance', '_k:key'))
        ]},
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
        if (value := self.get_node().get_value()):
            return str(list(value))
        elif (key := self.get_node().get_key()):
            return str(key)


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
                child_q = list(child_q)
                self.child_query = fill_query(child_q.pop(), key_dict)
            else:
                self.child_query = fill_query(child_q, key_dict)
        else:
            self.child_query = None

        if value_q:
            if isinstance(value_q, list):
                value_q = list(value_q)
                self.value_query = fill_query(value_q.pop(), key_dict)
            else:
                self.value_query = fill_query(value_q, key_dict)
        else:
            self.value_query = None

        self.descendant_queries = (value_q, child_q)
        self.pl = pl
        log.debug(f"{key}: {self.value_query}")
        result = query_gen(pl, self.value_query)
        value = next(result, None)
        super().__init__(value, parent=parent, key=key)


    def load_child_keys(self):
        # gonna have to do something complicated to actually sort these
        if self.child_query:
            children = [res[0] for res in query_gen(self.pl, self.child_query)]
            log.debug(children)
            return children
        else:
            return []


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
        return RDF_TreeNode(self.pl, key, self, self.descendant_queries[0])


    def load_widget(self):
        return RDF_NodeText(self)


class RDF_TreeNode(ur.TreeNode):
    def __init__(self, pl, key, parent, value_q=None):
        key_dict = {"key": key}
        if value_q:
            if isinstance(value_q, list):
                value_q = list(value_q)
                self.value_query = fill_query(value_q.pop(), key_dict)
            else:
                self.value_query = fill_query(value_q, key_dict)
            result = query_gen(pl, self.value_query)
            value = next(result, None)
        else:
            value = tuple([key])
        super().__init__(value, parent=parent, key=key)


    def load_widget(self):
        return RDF_NodeText(self)


class Window(ur.WidgetWrap):
    def __init__(self, pl):
        class_root = RDF_ParentNode(pl, RDFS.Resource, None,
                                        **tree_views['class_hierarchy'])
        classtreewin = ur.TreeListBox(ur.TreeWalker(class_root))
        classtreewin.offset_rows = 1

        instance_root = ur.TreeNode(None, key="")
        instancetreewin = ur.TreeListBox(ur.TreeWalker(instance_root))
        instancetreewin.offset_rows = 1

        instance_views = self.load_instance_views(tree_views.keys())
        instancelistwin = ur.ListBox(instance_views)
        instancelistwin.offset_rows = 1

        top_frame = ur.Columns([classtreewin, instancelistwin])

        pile = ur.Pile([top_frame, instancetreewin])

        self.frames = {
            "class": classtreewin,
            "browse": instancetreewin,
            "view": instancelistwin,
            #"ops":
            #"now":
        }
        self.pl = pl
        ur.WidgetWrap.__init__(self, pile)


    def keypress(self, size, key):
        if (key := self.__super.keypress(size, key)):
            log.debug(f'size:{size}, key:{key},'
                      f' focus:{self._w._get_focus_position()}')
            focus_widget, focus_widget_name = self.focus_frame()
            if focus_widget_name == "class":
                if key == 'enter':
                    log.debug(f'sel:{focus_widget.focus.get_node().get_key()}')
                    sel_class = focus_widget.focus.get_node().get_key()
                    browse_root = self.new_tree(sel_class, 'instance_list')
                    self.frames["browse"].body = ur.TreeWalker(browse_root)
            return key


    def focus_frame(self):
        if self._w.focus_position == 0:
            if self._w.focus.focus_position == 0:
                return self.frames["class"], "class"
            else:
                return self.frames["view"], "view"
        else:
            return self.frames["browse"], "browse"


    def load_instance_views(self, keys):
        return ur.SimpleFocusListWalker([ur.SelectableIcon(key) for key in keys])


    def new_tree(self, selected, view):
        view_data = tree_views[view]
        if isinstance(value_q := view_data['value_q'], list):
            value_q = list(value_q) # shallow copy since ParentNode will pop it
        if isinstance(child_q := view_data['child_q'], list):
            child_q = list(child_q)
        return RDF_ParentNode(self.pl, selected, None, value_q, child_q)


def global_control(k):
    if k in ['q', 'Q']: raise ur.ExitMainLoop()


def doubletree():
    pl = Prolog()
    pl.consult('init.pl')

    window = Window(pl)
    ur.MainLoop(window, palette, unhandled_input=global_control).run()


if __name__ == "__main__":
    log = logging.getLogger('doubletree')
    log.setLevel(logging.DEBUG)
    log_handler = logging.FileHandler('dbltree.log', encoding='utf-8')
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)

    log.debug(f"\n\t\tDoubletree {datetime.now()}")

    doubletree()
