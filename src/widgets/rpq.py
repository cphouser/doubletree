#!/usr/bin/env python3
import urwid as ur

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
