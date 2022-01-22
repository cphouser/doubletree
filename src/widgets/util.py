#!/usr/bin/env python3

from collections import namedtuple
from pprint import pformat
import logging as log

import urwid as ur

from util.table import balance_columns
#from util.palette import WidgetStyle


class ExpandingList(ur.WidgetWrap):
    def __init__(self):
        walker = ur.SimpleFocusListWalker(
                [ur.Columns([ur.Text("-"), ur.Text("-")])])
        self.listbox = ur.ListBox(walker)
        self.summary = WidgetStyle(ListSummary(self.selected()))
        #ur.Columns(
        #    [("pack", ur.AttrMap(ur.SelectableIcon("\u2261 "),
        #                         "listicon")),
        #      ur.AttrMap(ur.Text(self.selected()), "listitem_select")])
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
            [ur.Columns([("pack", ur.AttrMap(ur.SelectableIcon('- '),
                                             "listicon", "listitem_focus")),
                         ur.AttrMap(ur.Text(string), "listitem", "listitem_focus")])
             for string in str_list])
        self.load_summary()


    def selected(self):
        return self.listbox.focus[1].get_text()[0]


    def load_summary(self):
        self.summary.set_text(self.selected())
        self._w = self.summary


class TableList(ur.ListBox):
    """Table with a header"""
    def __init__(self, col_header):
        header_widgets = []
        for header in col_header:
            header_widgets.append(TableItem(header, wrap="clip"))
        self.header = TableRow("header", header_widgets)
        self.balanced = True
        super().__init__(ur.SimpleFocusListWalker([self.header]))


    def render(self, size, focus=False):
        if not self.balanced:
            cols, _ = size
            self.balance(cols)
        return super().render(size, focus)


    def add_row(self, key, contents):
        self.body.append(TableRow(key, contents))
        self.balanced = False


    def balance(self, width):
        width_data = [[] for _ in self.header]
        for row in self.body:
            for col_idx, width_list in enumerate(width_data):
                cell_width, _ = row[col_idx].pack()
                if col_idx != len(width_data) - 1:
                    cell_width += 1
                width_list.append(cell_width)
        for col in width_data:
            col.sort(reverse=True)
        col_widths = balance_columns(width_data, width)
        if col_widths:
            for row in self.body:
                for idx, width in enumerate(col_widths):
                    row.contents[idx] = (row.contents[idx][0],
                                         row.options("given", width))
        else:
            log.warn(f"could not size columns to {width}")
        self.balanced = True


    def selected(self):
        if self.focus:
            if self.focus.key == "header":
                return (None, self.focus.focus.key)
            else:
                return (self.focus.key, self.focus.focus.key)
        return (None, None)


    def selected_col(self):
        """return header key of currently selected column"""
        if self.focus:
            focus_idx = self.focus.find(self.focus.focus.key)
            return self.header[focus_idx].key


    def __getitem__(self, key):
        """return the row with the given key"""
        if key is None:
            return self.header
        for item in self.body:
            if item.key == key:
                return item


    def index(self, key):
        """return the index of the row with the given key."""
        if key is None:
            return 0
        for idx, item in enumerate(self.body):
            if item.key == key:
                return idx


    def sort_by(self, column):
        """Use the given column key to sort the table.

        Should preserve existing order among entries w/ an equal val in that
        column.
        """
        rows = []
        col_idx = self.body[0].find(column)
        for row in self.body[1:]:
            col_val = row[col_idx].sort
            rows.append((col_val, row))
        self.body = ur.SimpleFocusListWalker(
                [self.body[0]]
                + [row[1] for row in sorted(rows, key=lambda r: r[0])])


class TableItem(ur.WidgetWrap):
    def __init__(self, key, text=None, sort=None, selectable=True,
                 align="left", wrap="ellipsis"):
        self.key = key
        if text is None:
            text = str(key)
        if selectable:
            widget = SelectableText(text, align=align, wrap=wrap)
        else:
            widget = ur.Text(text, align=align, wrap=wrap)
        if sort is None:
            sort = text
        self.sort = sort
        super().__init__(widget)


class SelectableText(ur.SelectableIcon):
    def __init__(self, text, *args, **kwargs):
        super(ur.SelectableIcon, self).__init__(text, *args, **kwargs)
        if isinstance(text, str):
            length = len(text)
        else:
            length = sum([len(t) for t in text])
        self._cursor_position = length + 1


class ListSummary(SelectableText):
    list_icon = ("listicon", "\u2261 ")

    def __init__(self, text, *args, **kwargs):
        self.item = text
        super().__init__([self.list_icon, text], *args, **kwargs)


    def set_text(self, text):
        super().set_text([self.list_icon, text])


class TableRow(ur.Columns):
    def __init__(self, key, widget_list):
        self.key = key
        super().__init__(widget_list)


    def find(self, key):
        for idx, (item, _) in enumerate(self.contents):
            if item.key == key:
                return idx


    def __getitem__(self, idx):
        return self.contents[idx][0]

WHITE = '#ffffff'
LGRAY = '#c0c0c0'
DGRAY = '#808080'
BLACK = '#000000'

ORNG1 = '#ffdfaf'
ORNG2 = '#ffaf5f'
ORNG3 = '#ff8700'
ORNG4 = '#d75f00'

CYAN1 = '#dfffff'
CYAN2 = '#afffff'
CYAN3 = '#00d7d7'
CYAN4 = '#008787'

LPRPL = '#d700ff'
DPRPL = '#870087'

LPINK = '#ff87af'
DPINK = '#ff005f'

def bd(style):
    return style + ', bold'
def ul(style):
    return style + ', underline'

class WidgetStyle(ur.AttrMap):
    palette = [
        ('listicon',        'yellow' , 'black', '',             ORNG3, BLACK),
        ('listitem',        'yellow', 'black', '',              CYAN4, BLACK),
        ('listitem_focus',  'light gray', 'dark blue', '',      ORNG3, BLACK),
        ('listitem_select', 'dark blue', 'light gray', '',      ORNG4, BLACK),
        ('bar',             'yellow, bold', 'black', '',    bd(CYAN3), BLACK),
        ('bar_done', 'dark red, bold', 'dark blue', '',     bd(LPINK), ORNG4),
        ('treeopen',        'yellow' , 'black', '',             ORNG1, BLACK),
        ('treefold',        'yellow' , 'black', '',             CYAN2, BLACK),
        ('treeleaf',        'yellow' , 'black', '',             CYAN1, BLACK),
        ('tree_text',       'yellow' , 'black', '',             LGRAY, BLACK),
        ('tree_select',     'yellow' , 'black', '',             WHITE, BLACK),
    ]

    def __init__(self, widget):
        if isinstance(widget, ur.TreeWidget):
            w, *attrs = self.tree_style(widget)
        elif isinstance(widget, ListSummary):
            w, *attrs = self.list_summary_style(widget)
        else:
            w = ur.Text("TODO")
            attrs = []

        super().__init__(w, *attrs)


    def tree_style(self, widget):
        text = widget.get_display_text()
        indent_cols = widget.get_indent_cols()
        full_widget = ur.Padding(SelectableText([widget.get_icon(), text]),
                                 width=('relative', 100), left=indent_cols)
        return full_widget, 'tree_text', 'tree_select'


    def list_summary_style(self, widget):
        return widget, "listitem_select"

    def set_text(self, text):
        # FIXME maybe make another mixin factory for delegating other
        # common functions
        self._original_widget.set_text(text)
