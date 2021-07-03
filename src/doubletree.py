#!/usr/bin/env python3
import os
from collections import namedtuple
import logging as log

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog
import urwid as ur
import urwidtrees as ur_tree

from palette import palette
#from rdf_util.namespaces import B3, XCAT
from rdf_util.pl import (query, xsd_type, rdf_find, new_bnode, LDateTime,
                         TrackList, direct_subclasses, fill_query, query_gen)


Content = namedtuple('Content', ['label', 'parent', 'children'])


class RDF_NodeText(ur.TreeWidget):
    def __init__(self, node):
        """Override TreeWidget's initializer to collapse nodes"""
        self._node = node
        self._innerwidget = None
        self.is_leaf = not hasattr(node, 'get_first_child')
        self.expanded = False
        widget = self.get_indented_widget()
        #log.debug(super(ur.TreeWidget, self))
        super(ur.TreeWidget, self).__init__(widget)


    def get_display_text(self):
        return str(list(self.get_node().get_value()))


class RDF_ParentNode(ur.ParentNode):
    """Node class for a tree representing a set of RDF relationships

    value_q and child_q are each lists of queries or a single query as
    defined in rdf_util.pl.query.


    """
    def __init__(self, pl, key, parent, value_q=None, child_q=None):
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
        log.debug(value_q)
        result = query_gen(pl, self.value_query)#, debug=True)
        #log.debug(list(result))
        value = next(result) if result else None
        #log.debug(parent)
        super().__init__(value, parent=parent, key=key)


    def load_child_keys(self):
        # gonna have to do something complicated to actually sort these
        if self.child_query:
            result = list(res[0] for res in query_gen(self.pl, self.child_query))
            log.debug(result)
            return result


    def load_child_node(self, key):
        if (grandchild_template := self.descendant_queries[1]):
            if isinstance(grandchild_template, list):
                grandchild_template = grandchild_template[-1]
            grandchild_query = fill_query(grandchild_template, {"key": key})
            result = query_gen(self.pl, grandchild_query)#, debug=True)
            if result:
                return RDF_ParentNode(self.pl, key, self,
                                      *self.descendant_queries)
        return RDF_TreeNode(self.pl, key, self,
                            self.descendant_queries[0])


    def load_widget(self):
        log.debug(self.get_depth())
        return RDF_NodeText(self)


class RDF_TreeNode(ur.TreeNode):
    def __init__(self, pl, key, parent, value_q=None):
        key_dict = {"key": key}
        if value_q:
            if isinstance(value_q, list):
                self.value_query = fill_query(value_q.pop(), key_dict)
            else:
                self.value_query = fill_query(value_q, key_dict)
            result = query_gen(pl, self.value_query, debug=True)
            value = next(result) if result else None
        else:
            value = tuple([key])
        super().__init__(self, value, parent=parent, key=key)


    def load_widget(self):
        return RDF_NodeText(self)


class FocusableText(ur.WidgetWrap):
    def __init__(self, label):
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


class Window(ur.WidgetWrap):
    def __init__(self, pl):
        #dtree = RDF_ClassTree(pl)
        #decorated_tree = ur_tree.decoration.CollapsibleArrowTree(
        #        dtree, is_collapsed=(lambda x: dtree.parent_position(x)),
        #        arrow_tip_char=None,
        #        icon_frame_left_char=None, icon_frame_right_char=None,
        #        icon_collapsed_char=u'\u25B6', icon_expanded_char=u'\u25B7')

        # stick it into a ur_tree.widgets.TreeBox and use 'body' color
        # attribute for gaps
        #tb = ur_tree.widgets.TreeBox(decorated_tree, focus=RDF_ClassTree.root)
        #display_widget = ur.AttrMap(tb, 'body')
        child_queries = ('rdf', ('_v:Subclass', RDFS.subClassOf, '_k:key'))
        value_queries = ('xcat_label', ('_k:key', '_v:Label'))
        topkey = RDFS.Resource
        self.topnode = RDF_ParentNode(pl, topkey, None,
                                      value_q=value_queries,
                                      child_q=child_queries)
        treewindow = ur.TreeListBox(ur.TreeWalker(self.topnode))
        treewindow.offset_rows = 1

        ur.WidgetWrap.__init__(self, treewindow)

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
