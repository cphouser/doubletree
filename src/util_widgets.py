#!/usr/bin/env python3

from collections import namedtuple
from pprint import pformat
import logging as log

import urwid as ur


def trim_col(widths, max_width, prev_trim=0):
    """given a reverse-sorted list of child widths and a max width, return the
    number of elements that must be trimmed and min(max_width, max(widths))"""
    ret_width = min(max_width, widths[prev_trim])
    trimmed = prev_trim
    for width in widths[prev_trim:]:
        if width <= ret_width:
            break
        trimmed += 1
    return trimmed, ret_width


def trim(col_widths, fill_width, minimized=None, widths=None, num_cut=None,
         restrict=False):
    minimized = minimized or set()
    widths = widths or []
    num_cut = num_cut or []
    remaining_cols = len(col_widths) - len(minimized)
    if not remaining_cols:
        return minimized, widths, num_cut
    for idx, width in enumerate(widths):
        if idx in minimized:
            fill_width -= width

    # biggest col if all other cols were 2 cells wide
    max_col_width = fill_width - (remaining_cols - 1) * 2
    even_col_width = fill_width / remaining_cols
    #log.debug((max_col_width, even_col_width))
    new_widths = []
    new_num_cut = []
    last_trim = all([num_cut[i] == max(num_cut) for i in range(len(num_cut))
                     if i not in minimized])
    for idx, col_rows in enumerate(col_widths):
        if idx in minimized and idx < len(widths):
            new_widths.append(widths[idx])
            new_num_cut.append(num_cut[idx])
        else:
            if restrict and last_trim and num_cut[idx] == max(num_cut):
                trimmed, width = trim_col(col_rows, int(even_col_width))
    #            log.debug(f"last col ({idx}): {trimmed} {width}")
            else:
                trimmed, width = trim_col(col_rows, max_col_width)
                if restrict and (width > widths[idx] or trimmed < num_cut[idx]):
                    width = widths[idx]
                    trimmed = num_cut[idx]
            new_widths.append(width)
            new_num_cut.append(trimmed)
            if width < even_col_width:
                minimized.add(idx)
    #log.debug(f"{pformat(new_widths, width=160)}{sum(new_widths)}~{fill_width}")
    #log.debug(pformat(new_num_cut, width=160))
    #log.debug(pformat(minimized, width=160))
    return minimized, new_widths, new_num_cut


def table_wrap(col_widths, fill_width):
    #log.debug("\n"+pformat(col_widths, width=160))
    minimized, widths, num_cut = trim(col_widths, fill_width)
    last_added = 0
    restrict = False
    stage_two = False
    for i in range(100):
        log.debug(f"{widths},\t {sum(widths)}~{fill_width}, restrict: "
                  f"{restrict},\tstage_2: {stage_two},\tminimized: {minimized}")
        if sum(widths) == fill_width:
            return widths
        elif sum(widths) < fill_width:
            #log.debug(f"\n{i} PAD~~~")
            if not last_added:
                last_added = len(widths) - 1
            else:
                last_added -= 1
            #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
            #log.debug(f"  ~IDX {last_added}")
            widths[last_added] += 1
        elif not stage_two:
            #log.debug(f"\n{i} TRIM-1~~~")
            #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
            old_minimized_count = len(minimized)
            minimized, new_widths, num_cut = trim(col_widths, fill_width,
                                                  minimized, widths, num_cut,
                                                  restrict=restrict)
            if new_widths == widths and old_minimized_count == len(minimized):
                #log.debug("  ~DONE")
                stage_two = True
                restrict = True
            else:
                widths = new_widths
        else:
            #log.debug(f"\n{i} TRIM-2~~~")
            min_trim = min([trim_num for idx, trim_num in enumerate(num_cut)
                            if idx not in minimized]) + 1
            for idx, col_rows in enumerate(col_widths):
                #log.debug(f"min_trim: {min_trim}, {idx} trim: {num_cut[idx]}")
                if idx not in minimized and num_cut[idx] < min_trim:
                    #log.debug(f"{idx}: {min_trim}, {trimmed}, {width}")
                    trimmed, width = trim_col(col_rows, widths[idx] - 1,
                                              prev_trim=min_trim)
                    #log.debug(f"{idx}: {min_trim}, {trimmed}, {width}")
                    #if trimmed - min_trim == 1:
                    if trimmed - min_trim > 1:
                        width = widths[idx]
                    num_cut[idx] = trimmed
                    widths[idx] = width
                    stage_two = False
                    #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
                    #log.debug(pformat(num_cut, width=160))
                    #log.debug(pformat(minimized, width=160))
                    break
    log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")


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


class TableList(ur.ListBox):
    """Table with a header"""
    def __init__(self, col_header):
        header_widgets = []
        for header in col_header:
            header_widgets.append(TableItem(header, wrap="clip"))
        self.header = TableRow("header", header_widgets)
        self.balanced = True
        super().__init__(ur.SimpleFocusListWalker([self.header]))


    def render(self, size, focus=False ):
        """
        Render ListBox and return canvas.
        """
        if not self.balanced:
            cols, _ = size
            self.balance(cols)
        return super().render(size, focus)

    def add_row(self, key, contents):
        self.body.append(TableRow(key, contents))
        self.balanced = False


    def balance(self, width):
        # for each column get the minimum width of all cells (without wrapping).
        #
        #width_data = {
        #    self.header[col].key: {'lengths': []} for col in self.header
        #}
        width_data = [[] for _ in self.header]
        for row in self.body:
            for col_idx, width_list in enumerate(width_data):
                cell_width, _ = row[col_idx].pack()
                if col_idx != len(width_data) - 1:
                    cell_width += 1
                width_list.append(cell_width)
        for col in width_data:
            col.sort(reverse=True)
        col_widths = table_wrap(width_data, width)
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
    def __init__(self, text, *args, cursor_position=0, **kwargs):
        super(ur.SelectableIcon, self).__init__(text, *args, **kwargs)
        self._cursor_position = cursor_position


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
