#!/usr/bin/env python3

import urwid as ur

from rdf_util.rpq_widgets import RPQ_ListElem
from rdf_util.queries import instance_properties, instance_is_property

class RelatedTerms(ur.WidgetWrap):
    def __init__(self, rpq, update_resource):
        self.has_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.is_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.prop_query = rpq.query(*instance_properties)
        self.rev_prop_query = rpq.query(*instance_is_property)
        self.update_resource = update_resource
        super().__init__(ur.Columns([self.is_props, self.has_props]))


    def keypress(self, size, key):
        if key == "enter":
            if self._w.focus.focus:
                self.update_resource(self._w.focus.focus.elem)
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
