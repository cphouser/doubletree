#!/usr/bin/env python3

import os
import logging
import functools
from datetime import datetime

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog
import urwid as ur

import mpd_util
from palette import palette
from log_util import LogFormatter
from mpd_player import MpdPlayer

from rdf_util.namespaces import XCAT
from rdf_util.pl import (query, mixed_query, xsd_type, rdf_find, new_bnode,
                         LDateTime, TrackList, direct_subclasses, fill_query,
                         query_gen, all_classes)

class_hierarchy = {
    'value_q': ('xcat_label', ('_k:key', '_v:Label')),
    'child_q': ('rdf', ('_v:Subclass', RDFS.subClassOf, '_k:key'))
}

tree_views = {
    'instance_list': {
        'leaf': RDFS.Class,
        'root': RDFS.Resource,
        'value_q': [
            (('xcat_print', ('_k:key', '_v:Class', '_v:Print')),
             ('rdf_equal', ('_k:key', '_v:URI'))),
            ('xcat_label', ('_k:key', '_v:Label')),
        ], 'child_q': [
            ('rdfs_individual_of', ('_v:Instance', '_k:key'))
        ]},
    'artist_releases': {
        'leaf': XCAT.Release,
        'root': XCAT.Artist,
        'value_q': [
            ('xcat_print', ('_k:key', '_', '_v:Print')),
            ('xcat_print', ('_k:key', '_', '_v:Print')),
            ('xcat_label', ('_k:key', '_v:Label')),
        ], 'child_q': [
            (('rdf', ('_k:key', XCAT.made, '_v:Album')),
             ('rdfs_individual_of', ('_v:Album', XCAT.Release))),
            ('rdfs_individual_of', ('_v:Instance', '_k:key')#),
             #('xcat_has_releases', ['_v:Instance'])
             ),
        ]},
    'artist_release_tracks': {
        'leaf': XCAT.Recording,
        'root': XCAT.Artist,
        'value_q': [
            ('xcat_print', ('_k:key', '_', '_v:Print')),
            (('xcat_print', ('_k:key', '_', '_v:Print')),
             ('rdf', ('_k:key', XCAT.published_during, '_v:Date'))),
            ('xcat_print', ('_k:key', '_', '_v:Print')),
            ('xcat_label', ('_k:key', '_v:Label')),
        ], 'child_q': [
            ('xcat_tracklist', ('_k:key', '_v:List' )),
            (('rdf', ('_k:key', XCAT.made, '_v:Album')),
             ('rdfs_individual_of', ('_v:Album', XCAT.Release))),
            ('rdfs_individual_of', ('_v:Instance', '_k:key'))
        ]},
}

instance_ops = {
    XCAT.Recording: {
        'enter': (('xcat_filepath', ('_k:key', '_v:Path')),
                  mpd_util.add_to_list),
        },
    XCAT.Release: {
        'enter': (('xcat_tracklist_filepaths', ('_k:key', '_v:Paths')),
                  mpd_util.add_to_list),
        }
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
        self._expanded = False
        self.widths = widths
        widget = self.get_indented_widget()
        super(ur.TreeWidget, self).__init__(widget)


    @property
    def expanded(self):
        return self._expanded

    @expanded.setter
    def expanded(self, val):
        self._expanded = val
        if self._expanded:
            self.get_node().resort()
            #if (parent := self.get_node().get_parent()):
            #    parent.resort()

        

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
            result = query_gen(pl, self.value_query, log=log)
            value = next(result, None)
        else:
            value = tuple([key])
        log.debug(f"{key}: {self.value_query}")
        self.widths = [len(val_elem) for val_elem in value] if value else [0]
        super().__init__(value, parent=parent, key=key)


    def load_widget(self):
        if (parent := self.get_parent()):
            col_widths = parent.child_widths()
        else:
            col_widths = [0]
        log.debug(self.get_value())
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
                self.child_query = fill_query(child_q.pop(), key_dict, log=log)
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
        #log.debug(f"{key}: {self.value_query}")
        result = query_gen(pl, self.value_query, log=log)
        value = next(result, None)
        self.widths = [len(val_elem) for val_elem in value] if value else [0]
        self.sorted = False
        self.leaf = kwargs.get('leaf')
        super().__init__(value, parent=parent, key=key)


    def load_child_keys(self):
        # gonna have to do something complicated to actually sort these
        children = []
        if self._child_keys and len(self._children) == len(self._child_keys):
            children = self.get_child_keys()
            children.sort(key=lambda k: self.get_child_node(k).get_value()
                          if self.get_child_node(k).get_value() else k)

        elif self.child_query:
            #log.debug(self.child_query)
            children = [res[0] for res in query_gen(self.pl, self.child_query,
                                                    log=log)]
            #log.debug(children)
        return children


    def resort(self):
        if self._child_keys and len(self._children) == len(self._child_keys):
            for key in self.get_child_keys(reload=True):
                child = self.get_child_node(key)
                if isinstance(child, RDF_ParentNode):
                    child.resort()


    def load_child_node(self, key):
        if (grandchild_template := self.descendant_queries[1]):
            if isinstance(grandchild_template, list):
                grandchild_template = grandchild_template[-1]
            grandchild_query = fill_query(grandchild_template, {"key": key})
            result = query_gen(self.pl, grandchild_query, log=log)
            if (res := next(result, False)):
                # better way to exhaust this iterator? (the other func)
                list(result)
                return RDF_ParentNode(self.pl, key, self,
                                      *self.descendant_queries, leaf=self.leaf)
        #elif self.leaf and not (
        #        query(pl, ('rdfs_individual_of', (key, self.leaf)))):
        #    return
        return RDF_TreeNode(self.pl, key, self, self.descendant_queries[0])


    def child_widths(self):
        widths = [0]
        for key in self.get_child_keys():
            if (value := self.get_child_node(key).get_value()):
                while len(widths) < len(value):
                    widths.append(0)
                for idx, val_elem in enumerate(value):
                    widths[idx] = max(widths[idx], len(val_elem))
        log.debug(widths)
        return widths


class ClassView(ur.TreeListBox):
    def __init__(self, window, root):
        super().__init__(ur.TreeWalker(root))
        root.get_widget().expanded = True
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
    def __init__(self, window, pl, root=None, mpd_client=None, mpd_kwargs=None):
        if not root:
            root = ur.TreeNode(None, key="")
        super().__init__(ur.TreeWalker(root))
        self.window = window
        self.pl = pl

        self.instance_view = 'instance_list'
        self.root = root


    def keypress(self, size, key):
        if (operation := instance_ops.get(
                tree_views[self.instance_view]['leaf'], {}).get(key)):
            selected = self.focus.get_node().get_key()
            key_dict = {"key": selected}
            log.debug(f"{selected} {key} {operation}")
            mixed_query(self.pl, fill_query(operation, key_dict))
            self.window.frames['now'].reload()
        elif (res := super().keypress(size, key)):
            return res


    def new_tree(self):
        instance_tree = new_tree(self.pl, self.root, self.instance_view)
        instance_tree.get_widget().expanded = True
        self.body = ur.TreeWalker(instance_tree)


    def new_root(self, root):
        self.root = root
        self.new_tree()


    def new_view(self, view):
        self.instance_view = view
        self.new_tree()


class ViewList(ur.ListBox):
    def __init__(self, window, pl, root_class=RDFS.Resource):
        walker = ur.SimpleFocusListWalker([])
        super().__init__(walker)
        self.pl = pl
        self.load_views(root_class)
        self.window = window


    def keypress(self, size, key):
        if key == "enter":
            selected = self.focus.get_text()[0]
            self.window.load_view(selected)
        elif (res := super().keypress(size, key)):
            return res


    def load_views(self, leaf_class):
        #log.debug(leaf_class)
        classes = all_classes(self.pl, leaf_class)
        log.debug(classes)
        views = []
        for rdfs_class in classes:
            for view_name, view in tree_views.items():
                if str(view['root']) == rdfs_class:
                    views.append(view_name)
        #log.debug(views)
        self.body = ur.SimpleFocusListWalker(
            [ur.SelectableIcon(view) for view in views]
        )


class Window(ur.WidgetWrap):
    def __init__(self, pl, update_rate=5):
        class_root = RDF_ParentNode(pl, RDFS.Resource, None, **class_hierarchy)
        classtreewin = ClassView(self, class_root)

        instancetreewin = InstanceView(self, pl)

        instancelistwin = ViewList(self, pl)

        operationgrid = ur.WidgetPlaceholder(ur.SolidFill('.'))

        operationview = MpdPlayer(self.format_track, log=log)

        top_frame = ur.Columns([classtreewin, instancelistwin, operationgrid])
        bottom_frame = ur.Columns([instancetreewin, operationview])
        pile = ur.Pile([top_frame, bottom_frame])

        self.update_rate = update_rate
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
        if key in ['esc', 'q', 'Q']: raise ur.ExitMainLoop()
        if (key := self.__super.keypress(size, key)):
            key_list = key.split(' ')
            if key_list[0] == 'shift':
                if key_list[1] in ['up', 'down', 'left', 'right']:
                    self.focus_frame(key_list[1])
                    return None
            log.info(f'size:{size}, key:{key_list},'
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


    def load_instances(self, sel_class):
        self.frames["browse"].new_root(sel_class)
        self.frames["view"].load_views(sel_class)


    def load_view(self, sel_view):
        self.frames["browse"].new_view(sel_view)
        log.debug(sel_view)


    def format_track(self, dictlike):
        return {
            'key': dictlike.get('id', ""),
            'track': dictlike.get('title', ""),
            'artist': dictlike.get('artist', ""),
            'album': dictlike.get('album', ""),
            'year': dictlike.get('date', "")
        }


    def update_dynamic(self, main_loop, *args):
        self.frames['now'].reload_screen()
        main_loop.set_alarm_in(self.update_rate, self.update_dynamic)


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

    window = Window(pl, update_rate=1)
    event_loop = ur.MainLoop(window, palette, unhandled_input=unhandled_input)
    event_loop.set_alarm_in(1, window.update_dynamic)
    event_loop.run()


if __name__ == "__main__":
    log = logging.getLogger('doubletree')
    log.setLevel(logging.DEBUG)
    log_handler = logging.FileHandler('dbltree.log', encoding='utf-8')
    log_handler.setLevel(logging.DEBUG)

    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)

    log.info(f"\n\t\tDoubletree {datetime.now()}")

    doubletree()
