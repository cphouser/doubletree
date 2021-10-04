#!/usr/bin/env python3

import os
import logging
import functools
from datetime import datetime
import traceback

from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyswip.prolog import Prolog, PrologError
import urwid as ur

import mpd_util
from palette import palette
from log_util import LogFormatter
from mpd_player import MpdPlayer

from rdf_util.namespaces import XCAT
from rdf_util.pl import mixed_query, all_classes, RPQ, VarList
from rdf_util.queries import (tree_views, instance_ops, class_hierarchy,
                              instance_properties, instance_is_property,
                              track_format_query, printed_resource)

class RPQ_NodeText(ur.TreeWidget):
    unexpanded_icon = ur.wimp.SelectableIcon('\u25B6', 0)
    expanded_icon = ur.wimp.SelectableIcon('\u25B7', 0)
    leaf_icon = ur.wimp.SelectableIcon('-', 0)

    def __init__(self, node):
        super().__init__(node)
        self.expanded = False
        self.update_expanded_icon()


    def selectable(self):
        return True


    def get_display_text(self):
        return str(self.get_node().get_value())


    def get_indented_widget(self):
        inner = self.get_inner_widget()
        widget = ur.Columns([('fixed', 1, self.get_icon()), inner],
                            dividechars=1)
        indent_cols = self.get_indent_cols()
        return ur.Padding(widget, width=('relative', 100), left=indent_cols)


    def get_icon(self):
        if self.is_leaf:
            return self.leaf_icon
        elif self.expanded:
            return self.expanded_icon
        else:
            return self.unexpanded_icon


    def update_expanded_icon(self):
        """Update display widget text for parent widgets"""
        # icon is first element in columns indented widget
        self._w.base_widget.widget_list[0] = self.get_icon()


    def keypress(self, size, key):
        if key == "tab":
            if not self.is_leaf:
                self.expanded = not self.expanded
                self.update_expanded_icon()
        else:
            return key


class RPQ_TreeNode(ur.TreeNode):
    def __init__(self, parent_query, key, parent=None):
        value = parent_query[key]
        self.parent_query = parent_query
        self._prev_sibling = None
        self._next_sibling = None
        super().__init__(value, parent=parent, key=key)


    def next_sibling(self):
        if self._next_sibling is False:
            return None
        if self._next_sibling:
            return self._next_sibling
        next_key_idx = self.parent_query.keys().index(self.get_key()) + 1
        if next_key_idx < len(self.parent_query.keys()):
            #log.debug(next_key_idx)
            #log.debug(self.get_key())
            #log.debug(self.parent_query.keys())
            key = self.parent_query.keys()[next_key_idx]
            self._next_sibling = RPQ_Node(self.parent_query, key,
                                          self.get_parent())
            self._next_sibling._prev_sibling = self
            return self._next_sibling


    def prev_sibling(self):
        if self._prev_sibling is False:
            return None
        if self._prev_sibling:
            return self._prev_sibling
        next_key_idx = self.parent_query.keys().index(self.get_key()) - 1
        if (next_key_idx + 1):
            #log.debug(next_key_idx)
            #log.debug(self.get_key())
            #log.debug(self.parent_query.keys())
            key = self.parent_query.keys()[next_key_idx]
            self._prev_sibling = RPQ_Node(self.parent_query, key,
                                          self.get_parent())
            self._prev_sibling._next_sibling = self
            return self._prev_sibling


    def load_widget(self):
        return RPQ_NodeText(self)


class RPQ_ParentNode(RPQ_TreeNode, ur.ParentNode):
    def load_child_keys(self):
        return self.parent_query.child_query(self.get_key()).keys()


    def load_child_node(self, key):
        return RPQ_Node(self.parent_query.child_query(self.get_key()),
                        key, self)


def RPQ_Node(parent_query, key, parent):
    if len(parent_query.child_query(key)):
        return RPQ_ParentNode(parent_query, key, parent)
    else:
        return RPQ_TreeNode(parent_query, key, parent)


class ClassView(ur.TreeListBox):
    def __init__(self, window, rpquery):
        first_node = RPQ_Node(rpquery, rpquery.keys()[0], None)
        super().__init__(ur.TreeWalker(first_node))
        self.window = window


    def keypress(self, size, key):
        if key == "enter":
            selected = self.focus.get_node().get_key()
            self.window.load_instances(selected)
        elif (res := super().keypress(size, key)):
            return res


class InstanceView(ur.Pile):
    def __init__(self, window):
        self.window = window
        self.tree = ur.TreeListBox(ur.TreeWalker(ur.TreeNode(None, key="")))
        self.views = ViewList(self)

        self.i_class = None
        self.rpquery = None
        super().__init__([("pack", self.views), self.tree])


    def keypress(self, size, key):
        if self.focus == self.tree:
            focused = self.tree.focus.get_node()
            sel_type = focused.get_value().type
            #log.debug(sel_type)
            #log.debug(instance_ops.keys())
            selected = focused.get_key()
            if (operation := instance_ops.get(sel_type, {}).get(key)):
                log.debug(f"{selected} {key} {operation}")
                mixed_query(self.window.rpq, operation, selected, log=log)
                self.window.frames['now'].reload()
                return
            elif key == 'enter':
                self.window.load_relations(selected)
                return
        if (res := super().keypress(size, key)):
            return res


    def new_tree(self, parent=None, query=None):
        if query is None:
            return
        if parent:
            self.parent = parent
        self.rpquery = query.copy(self.parent)
        if self.rpquery:
            log.debug(self.rpquery)
            first_node = RPQ_Node(self.rpquery, self.rpquery.keys()[0], None)
            self.tree.body = ur.TreeWalker(first_node)
        else:
            log.warning(self.rpquery)


    def load_instances(self, sel_class):
        self.views.load_views(sel_class)
        self.load_view(sel_class)


    def load_view(self, sel_class=None):
        view_query = self.window.rpq.querylist(
                tree_views[self.views.selected()]['query'])
        self.new_tree(sel_class, view_query)


class ExpandingList(ur.WidgetWrap):
    def __init__(self):
        walker = ur.SimpleFocusListWalker(
                [ur.Columns([ur.Text("-"), ur.Text("-")])])
        self.listbox = ur.ListBox(walker)
        self.summary = ur.Columns([("pack", ur.SelectableIcon("\u2261 ")),
                                   ur.Text(self.selected())])
        super().__init__(self.summary)


    def keypress(self, size, key):
        if key == "tab":
            if self._w == self.summary:
                height = min(3, len(self.listbox.body))
                self._w = ur.BoxAdapter(self.listbox, height)
            else:
                self.load_summary()
        elif (res := super().keypress(size, key)):
            return res


    def load_list(self, str_list):
        self.listbox.body = ur.SimpleFocusListWalker(
            [ur.Columns([("pack", ur.SelectableIcon('- ')),
                         ur.Text(string)]) for string in str_list])
        self.load_summary()


    def selected(self):
        return self.listbox.focus[1].get_text()[0]


    def load_summary(self):
        self.summary[1].set_text(self.selected())
        self._w = self.summary


class ViewList(ExpandingList):
    def __init__(self, frame, root_class=RDFS.Resource):
        super().__init__()
        self.frame = frame
        self.load_views(root_class)


    def keypress(self, size, key):
        if key == "enter":
            self.frame.load_view()
        elif (res := super().keypress(size, key)):
            return res


    def load_views(self, leaf_class):
        classes = all_classes(self.frame.window.rpq, leaf_class)
        views = []
        for rdfs_class in classes:
            for view_name, view in tree_views.items():
                if str(view['root']) == rdfs_class:
                    views.append(view_name)
        self.load_list(views)


class RPQ_ListElem(ur.Columns):
    def __init__(self, key, query_result, reverse=False):
        widget_list = [('fixed', 1, ur.SelectableIcon('-')),
                       ur.Text(str(query_result))]
        self.elem = key
        super().__init__(widget_list)


class RelatedTerms(ur.WidgetWrap):
    def __init__(self, window):
        self.window = window
        self.has_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.is_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.prop_query = window.rpq.query(*instance_properties)
        self.rev_prop_query = window.rpq.query(*instance_is_property)
        super().__init__(ur.Columns([self.is_props, self.has_props]))


    def keypress(self, size, key):
        if key == "enter":
            if self._w.focus.focus:
                self.window.load_relations(self._w.focus.focus.elem)
        elif (res := super().keypress(size, key)):
            return res


    def load_instance(self, instance_key):
        prop_query = self.prop_query.copy(instance_key)
        rev_prop_query = self.rev_prop_query.copy(instance_key)
        subj_of = [RPQ_ListElem(obj, res, reverse=True)
                   for obj, res in prop_query.items()]
        obj_of = [RPQ_ListElem(sbj, res) for sbj, res in rev_prop_query.items()]
        self.has_props.body = ur.SimpleFocusListWalker(subj_of)
        self.is_props.body = ur.SimpleFocusListWalker(obj_of)


class InstanceOps(ur.Frame):
    def __init__(self, window):
        self.window_menu = ur.Text("-related terms-")
        related_terms = RelatedTerms(window)
        self.body_container = ur.WidgetPlaceholder(related_terms)
        super().__init__(self.body_container, self.window_menu)


    def load_instance(self, instance_key):
        self.body_container.original_widget.load_instance(instance_key)


class Header(ur.Columns):
    def __init__(self, window):
        self.resource_print_q = window.rpq.query(*printed_resource)
        self.resource_widget = ur.Text("-None-")
        self.selected_resource = None #???
        self.window_focus = ur.Text("[FOCUS]")
        left = [self.window_focus]
        right = [ur.Padding(ur.Text("&&&&"), align="right", width="pack")]
        center = [ur.Padding(ur.Text("Selected Resource: "), align='right',
                             width='pack'), self.resource_widget]
        super().__init__(left + center + right)


    def select_resource(self, instance_key):
        self.selected_resource = self.resource_print_q.copy(instance_key)
        self.resource_widget.set_text(str(self.selected_resource.first_item()))


class Window(ur.WidgetWrap):
    def __init__(self, rpq, update_rate=5):
        self.rpq = rpq
        self.format_query = rpq.query(*track_format_query)
        self.track_cache = {}
        self.update_rate = update_rate

        header = Header(self)
        classtreewin = ClassView(self, rpq.query(*class_hierarchy))
        instancetree = InstanceView(self)
        operationgrid = InstanceOps(self)
        operationview = MpdPlayer(self.format_track, log=log)
        self.frames = {
            "head": header,
            "class": classtreewin,
            "browse": instancetree,
            "ops": operationgrid,
            "now": operationview
        }
        top_frame = ur.Columns([('fixed', 30, classtreewin), operationgrid])
        bottom_frame = ur.Columns([instancetree, ("weight", 2, operationview)])
        pile = ur.Pile([top_frame, ("weight", 2, bottom_frame)])

        ur.WidgetWrap.__init__(self, ur.Frame(pile, header=header))


    def keypress(self, size, key):
        if key in ['esc', 'q', 'Q']: raise ur.ExitMainLoop()
        if (key := self.__super.keypress(size, key)):
            key_list = key.split(' ')
            if key_list[0] == 'shift':
                if key_list[1] in ['up', 'down', 'left', 'right']:
                    self.focus_frame(key_list[1])
                    return None
            log.info(f'size:{size}, key:{key_list}')


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


    def load_instances(self, sel_class):
        self.frames['head'].select_resource(sel_class)
        self.frames['browse'].load_instances(sel_class)
        self.frames['ops'].load_instance(sel_class)


    def load_relations(self, sel_instance):
        self.frames['head'].select_resource(sel_instance)
        self.frames['ops'].load_instance(sel_instance)



    def format_track(self, dictlike):
        if (path := dictlike.get('file')):
            if (cached := self.track_cache.get(path)):
                dictlike = cached
            else:
                results = self.format_query.copy(path).first_item()
                dictlike['title'] = results.get("Recording", ".")
                dictlike['artist'] = results.get("Artist", ".")
                dictlike['album'] = results.get("Release", ".")
                dictlike['year'] = results.get("Year", ".")
                self.track_cache[path] = dictlike
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


def unhandled_input(k):
    log.warning(k)


def doubletree(rpq):
    window = Window(rpq, update_rate=1)
    event_loop = ur.MainLoop(window, palette, unhandled_input=unhandled_input)
    event_loop.set_alarm_in(1, window.update_dynamic)
    event_loop.run()


if __name__ == "__main__":
    log = logging.getLogger('doubletree')
    log.setLevel(logging.DEBUG)
    log_handler = logging.FileHandler('dbltree.log', encoding='utf-8')

    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)

    log.info(f"\n\t\tDoubletree {datetime.now()}")
    rpq = RPQ('init.pl', log=log)

    doubletree(rpq)
