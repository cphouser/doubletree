#!/usr/bin/env python3

import urwid as ur

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
