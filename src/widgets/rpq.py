#!/usr/bin/env python3
import logging as log

import urwid as ur

from widgets.util import WidgetStyle

class RPQ_ListElem(ur.Columns):
    def __init__(self, key, query_result, reverse=False, selectable=True):
        width = 1 if reverse else 2
        if not selectable:
            widget_list = [ur.Text(str(query_result))]
        else:
            widget_list = [('fixed', width, ur.SelectableIcon('-')),
                           ur.Text(str(query_result))]

        self.elem = key
        super().__init__(widget_list)


class RPQ_NodeText(ur.TreeWidget):
    unexpanded_icon = ('treefold', '\u25B6 ')
    expanded_icon = ('treeopen', '\u25B7 ')
    leaf_icon = ('treeleaf', '- ')

    def __init__(self, node):
        super().__init__(node)
        self.expanded = False
        self.update_expanded_icon()


    def get_icon(self):
        if self.is_leaf:
            return self.leaf_icon
        elif self.expanded:
            return self.expanded_icon
        else:
            return self.unexpanded_icon


    def selectable(self):
        return True


    def get_display_text(self):
        return str(self.get_node().get_value())


    def get_indented_widget(self):
        return WidgetStyle(self)


    def update_expanded_icon(self):
        log.debug(self._w.base_widget)
        self._w.base_widget.set_text([self.get_icon(), self.get_display_text()])
        #self._w.base_widget.widget_list[0] = self.get_icon()


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
            key = self.parent_query.keys()[next_key_idx]
            self._prev_sibling = RPQ_Node(self.parent_query, key,
                                          self.get_parent())
            self._prev_sibling._next_sibling = self
            return self._prev_sibling


    def load_widget(self):
        return RPQ_NodeText(self)


class RPQ_ParentNode(RPQ_TreeNode, ur.ParentNode):
    def load_child_keys(self):
        keys = self.parent_query.child_query(self.get_key()).keys()
        self._child_keys = keys
        return keys


    def load_child_node(self, key):
        #log.debug(self.parent_query)
        #log.debug(self.get_key())
        #log.debug(key)
        node = RPQ_Node(self.parent_query.child_query(self.get_key()),
                        key, self)
        self._children[key] = node
        return node


def RPQ_Node(parent_query, key, parent):
    if len(parent_query.child_query(key)):
        return RPQ_ParentNode(parent_query, key, parent)
    else:
        return RPQ_TreeNode(parent_query, key, parent)


class EditWindow(ur.WidgetWrap):
    def __init__(self, widget, update_resource):
        # function to pass the new instance to
        self.update_resource = update_resource
        super().__init__(widget)


    def load_instance(self, instance_key):
        raise NotImplementedError


def EditWindows(root=None):
    import widgets.edit
    try:
        import user_py.edit
    except ImportError:
        pass
    if root:
        return {subcls.name: subcls for subcls in EditWindow.__subclasses__()
                if str(subcls.root) == str(root)}
    return {subcls.name: subcls for subcls in EditWindow.__subclasses__()}


class SearchableTreeWalker(ur.TreeWalker):
    def __init__(self, first_node):
        """
        NOT GREAT search. in particualar there's an issue using the search field in this
        naive recursive form. if theres a repeated string value, we stop recursing.
        possible fixup would be to store a list of (node, searched) tuples as the search_field
        values.
        """
        super().__init__(first_node)
        self.search_field = {}
        if isinstance(first_node, RPQ_TreeNode):
            node = first_node
            while node:
                self.search_field[node.get_value().string.lower()] = (node, False)
                node = node.next_sibling()

    def find(self, match_string):
        rec_search = []
        match_string = match_string.lower()
        for string, (node, searched) in self.search_field.items():
            if match_string in string:
                return node
            elif not searched:
                rec_search.append(string)
        for string in rec_search:
            if (result := self._rec_find(string, match_string)):
                return result

    def _rec_find(self, node_string, match_string):
        #log.debug(self.search_field)
        node, _ = self.search_field[node_string]
        new_parents = []
        if isinstance(node, RPQ_ParentNode):
            match_node = None
            #log.debug(list(node.get_child_keys()))
            for key in node.get_child_keys():
                #log.debug(key)
                child_node = node.get_child_node(key)
                new_string = child_node.get_value().string.lower()
                #log.debug(new_string)
                if not (item := self.search_field.get(new_string)):
                    self.search_field[new_string] = (child_node, False)
                    if isinstance(child_node, RPQ_ParentNode):
                        new_parents.append(new_string)
                if match_string in new_string:
                    match_node = child_node
            if match_node:
                return match_node
        self.search_field[node_string] = (node, True)
        for parent_string in new_parents:
            #log.info(parent_string)
            if (match_node := self._rec_find(parent_string, match_string)):
                return match_node

    def match_select(self, string):
        if (key := self.find(string)):
            log.debug(key)
            self.set_focus(key)
