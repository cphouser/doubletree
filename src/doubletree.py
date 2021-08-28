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

class_hierarchy = {
    'value_q': ('xcat_label', ('_k:key', '_v:Label')),
    'child_q': ('rdf', ('_v:Subclass', RDFS.subClassOf, '_k:key'))
}

tree_views = {
    'instance_list': {
        #'leaf': RDFS.Class,
        #'root': RDFS.Resource,
        'value_q': [
            (('xcat_print', ('_k:key', '_v:Class', '_v:Print')),
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

    def __init__(self, node, widths):
        """Override TreeWidget's initializer to collapse nodes"""
        self._node = node
        self._innerwidget = None
        self.is_leaf = not hasattr(node, 'child_query')
        self.expanded = False
        self.widths = widths
        widget = self.get_indented_widget()
        super(ur.TreeWidget, self).__init__(widget)


    def get_display_text(self):
        if (value := self.get_node().get_value()):
            value_strs = [e.ljust(self.widths[i]) for i, e in enumerate(value)]
            return ' | '.join(value_strs)
        elif (key := self.get_node().get_key()):
            log.warning(f"value query failed: {key}")
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


    def keypress(self, size, key):
        if key == "tab":
            if not self.is_leaf:
                self.expanded = not self.expanded
                self.update_expanded_icon()
        else:
            return key


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
        self.widths = [len(val_elem) for val_elem in value] if value else [0]
        super().__init__(value, parent=parent, key=key)


    def load_widget(self):
        if (parent := self.get_parent()):
            col_widths = parent.child_widths()
        else:
            col_widths = [0]
        return RDF_NodeText(self, col_widths)


class RDF_ParentNode(ur.ParentNode, RDF_TreeNode):
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
        self.widths = [len(val_elem) for val_elem in value]
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
                # better way to exhaust this iterator? (the other func)
                list(result)
                return RDF_ParentNode(self.pl, key, self,
                                      *self.descendant_queries)
        return RDF_TreeNode(self.pl, key, self, self.descendant_queries[0])


    def child_widths(self):
        widths = [0]
        for key in self.get_child_keys():
            if (value := self.get_child_node(key).get_value()):
                while len(widths) < len(value):
                    widths.append(0)
                for idx, val_elem in enumerate(value):
                    widths[idx] = max(widths[idx], len(val_elem))
        return widths


class ClassView(ur.TreeListBox):
    def __init__(self, window, root):
        super().__init__(ur.TreeWalker(root))
        self.window = window
        # does this matter? (how?)
        #self.offset_rows = 1

    #self.focus.get_node().get_key() @property focus_key

    def keypress(self, size, key):
        if key == "enter":
            selected = self.focus.get_node().get_key()
            self.window.load_instances(selected)
        elif (res := super().keypress(size, key)):
            return res


class InstanceView(ur.TreeListBox):
    def __init__(self, window, pl, root=None):
        if not root:
            root = ur.TreeNode(None, key="")
        super().__init__(ur.TreeWalker(root))
        self.window = window
        self.pl = pl
        self.instance_view = 'instance_list'
        self.root = root


    def keypress(self, size, key):
        if key == "enter":
            selected = self.focus.get_node().get_key()
            log.debug(selected)
        elif (res := super().keypress(size, key)):
            return res


    def new_tree(self):
        instance_tree = new_tree(self.pl, self.root, self.instance_view)
        self.body = ur.TreeWalker(instance_tree)


    def new_root(self, root):
        self.root = root
        self.new_tree()


    def new_view(self, view):
        self.instance_view = view
        self.new_tree()


class ViewList(ur.ListBox):
    def __init__(self, window, walker):
        super().__init__(walker)
        self.window = window


    def keypress(self, size, key):
        if key == "enter":
            selected = self.focus.get_text()[0]
            self.window.load_view(selected)
        elif (res := super().keypress(size, key)):
            return res


class Window(ur.WidgetWrap):
    def __init__(self, pl):
        class_root = RDF_ParentNode(pl, RDFS.Resource, None, **class_hierarchy)
        classtreewin = ClassView(self, class_root)

        instancetreewin = InstanceView(self, pl)

        instance_views = self.load_instance_views(tree_views.keys())
        instancelistwin = ViewList(self, instance_views)

        operationgrid = None

        operationview = None

        top_frame = ur.Columns([classtreewin, instancelistwin])
        bottom_frame = ur.Columns([instancetreewin])
        pile = ur.Pile([top_frame, bottom_frame])

        self.frames = {
            "class": classtreewin,
            "browse": instancetreewin,
            "view": instancelistwin,
            "ops": operationgrid,
            "now": operationview
        }
        self.pl = pl
        ur.WidgetWrap.__init__(self, pile)


    def keypress(self, size, key):
        if key == 'esc': raise ur.ExitMainLoop()
        if (key := self.__super.keypress(size, key)):
            key_list = key.split(' ')
            if key_list[0] == 'shift':
                if key_list[1] in ['up', 'down', 'left', 'right']:
                    self.focus_frame(key_list[1])
                    return None
            log.debug(f'size:{size}, key:{key_list},'
                      f' focus:{self.active_frame()[1]}')


    def focus_frame(self, direction):
        if direction == "down":
            if self._w.focus_position == 0:
                self._w.focus_position = 1
        elif direction == "up":
            if self._w.focus_position == 1:
                self._w.focus_position = 0
        elif direction == "left":
            if self._w.focus.focus_position > 0:
                self._w.focus.focus_position -= 1
        else:
            if self._w.focus.focus_position < (len(self._w.focus.contents) - 1):
                self._w.focus.focus_position += 1


    def active_frame(self):
        if self._w.focus_position == 0:
            if self._w.focus.focus_position == 0:
                return self.frames["class"], "class"
            else:
                return self.frames["view"], "view"
        else:
            return self.frames["browse"], "browse"


    def load_instance_views(self, keys):
        return ur.SimpleFocusListWalker([ur.SelectableIcon(key) for key in keys])


    def load_instances(self, sel_class):
        self.frames["browse"].new_root(sel_class)


    def load_view(self, sel_view):
        self.frames["browse"].new_view(sel_view)
        log.debug(sel_view)


def new_tree(pl, selected, view):
    view_data = tree_views[view]
    if isinstance(value_q := view_data['value_q'], list):
        value_q = list(value_q) # shallow copy since ParentNode will pop it
    if isinstance(child_q := view_data['child_q'], list):
        child_q = list(child_q)
    return RDF_ParentNode(pl, selected, None, value_q, child_q)


def unhandled_input(k):
    log.warning(k)


def doubletree():
    pl = Prolog()
    pl.consult('init.pl')

    window = Window(pl)
    ur.MainLoop(window, palette, unhandled_input=unhandled_input).run()


if __name__ == "__main__":
    log = logging.getLogger('doubletree')
    log.setLevel(logging.DEBUG)
    log_handler = logging.FileHandler('dbltree.log', encoding='utf-8')
    log_handler.setLevel(logging.INFO)

    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)

    log.info(f"\n\t\tDoubletree {datetime.now()}")

    doubletree()
