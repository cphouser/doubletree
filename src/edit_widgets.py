#!/usr/bin/env python3
import logging as log
from pprint import pformat

import urwid as ur
from rdflib.namespace import RDF, RDFS, XSD

from rdf_util.namespaces import XCAT, ShortURI
from rdf_util.rpq_widgets import RPQ_ListElem, EditWindow
from rdf_util.pl import xsd_type, escape_string
from util_widgets import TableList, TableRow, TableItem, SelectableText
from mutagen_util import TagData

instance_properties = [
    'ObjURI',
    "rdf(Subject, PredURI, ObjURI), "
    "xcat_label(PredURI, Predicate), "
    "xcat_print(ObjURI, Class, Object)",
    "--{Predicate}--> {Object} <{Class}>",
    ('Subject', None),
    #dict(child_type=False)
]

instance_is_property = [
    'SubjURI',
    "rdf(SubjURI, PredURI, ObjURI), "
    "xcat_label(PredURI, Predicate), "
    "xcat_print(SubjURI, Class, Subject)",
    "{Subject} <{Class}> --{Predicate}--> ",
    ('ObjURI', None),
    #dict(child_type=False)
]

class RelatedTerms(EditWindow, ur.WidgetWrap):
    root = RDFS.Resource
    name = "Related Terms"

    def __init__(self, rpq, update_resource):
        self.has_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.is_props = ur.ListBox(ur.SimpleFocusListWalker([]))
        self.prop_query = rpq.query(*instance_properties)
        self.rev_prop_query = rpq.query(*instance_is_property)
        super().__init__(ur.Columns([self.is_props, self.has_props]),
                         update_resource)


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


audiofile_data = [
    "Path",
    "xcat_filepath(FileURI, Path), "
    f"rdf(FileURI, '{XCAT.recording}', RecordingURI)",
    dict(q_where=
         f"rdf(RecordingURI, '{XCAT.release}', Release), "
         f"rdf(RecordingURI, '{XCAT.maker}', Artist)"
         f"rdf(RecordingURI, '{XCAT.title}', Title)" ,
         child_type=False,
         parent=("FileURI", None),
         null=True)
]


release_tracks = [
    'Track',
    f"rdf(Track, '{XCAT.released_on}', Release), "
    f"xcat_filepath(Track, Path)",
    "{TLabel} {Artist} {Path}",
    dict(
        parent=('Release', None),
        q_where=f"xcat_print(Track, TLabel), "
                f"rdf(Track, '{XCAT.maker}', Maker), "
                "xcat_print(Maker, Artist), "
                "xcat_print(Release, RLabel)",
        q_by=False, null=True)]


class PropertyEdit(ur.Columns):
    def __init__(self, prop, prop_lbl, val, val_type, alt_val=None):
        self.short = ShortURI()
        self.prop = prop
        self.val = val
        self.val_type = val_type
        self.alt_val = alt_val or ""
        prop_lbl = f"{prop_lbl}:"
        if alt_val:
            prop_lbl = SelectableText(prop_lbl + f" [{alt_val}]")
        else:
            prop_lbl = ur.Text(prop_lbl)
        self.val_edit = ur.Edit("", val, wrap="clip")
        super().__init__([("pack", prop_lbl), self.val_edit,
                          ("pack", ur.Text(self.short(val_type)))],
                         dividechars=1)

    @property
    def text(self):
        return self.val_edit.edit_text


    def keypress(self, size, key):
        if self.focus_position == 0 and key == "enter":
            self.val_edit.edit_text = self.alt_val
            return
        if (res := super().keypress(size, key)):
            return res


class RecordingImport(ur.Columns):
    tagdata = TagData()
    tag_mapping = {
        f"{XCAT.title}": lambda d: (d.get("title") or [""])[0]
    }

    def __init__(self, rpq, path, release, update_resource):
        self.rpq = rpq
        prop_query = self.rpq.query(*release_tracks)
        prop_query.parent = release
        self.new_rec = dict(rec_props={}, rec_is_prop={}, encoding=None)
        self.recording_node = prop_query.first_item()
        self.path_tagdata = self.tagdata.match_path(path)
        self.file_resource = self.rpq.simple_query(
                f"rdf(X, '{XCAT.path}', {xsd_type(path, 'string')})")
        self.update_resource = update_resource
        super().__init__([self._recording_is_property(),
                          self._recording_properties(),
                          ("weight", 0.5, self._fill_options())],
                         dividechars=1)


    def add_recording(self):
        rec_uri = self.rpq.new_bnode()
        rec_props = self.new_rec["rec_props"]
        rec_is_prop = self.new_rec["rec_is_prop"]
        encoding, field_type = self.new_rec['encoding']
        if (file_prop := rec_props.get(f"{XCAT.file}")):
            file_uri, _ = file_prop
            file_uri = file_uri.text
            if self.rpq.boolquery(f"xcat_type('{file_uri}', '{XCAT.File}')"):
                self.rpq.rassert(f"rdf_update('{file_uri}', '{RDF.type}', "
                                 f"'{XCAT.File}', object('{XCAT.AudioFile}'))",
                                 f"rdf_assert('{file_uri}', '{XCAT.encoding}'"
                                 f", {xsd_type(encoding.text, 'string')})")
        assertlist = []
        for prop, (field, valtype) in rec_props.items():
            assertlist.extend(self._assert(rec_uri, prop, field.text, valtype))
        for prop, (field, valtype) in rec_is_prop.items():
            assertlist.extend(self._assert(rec_uri, prop, field.text, is_obj=True))
            assertlist.append(
                f"rdf_assert('{rec_uri}', '{RDF.type}', '{XCAT.Recording}')")
        self.rpq.rassert(*assertlist)
        self.update_resource()


    def _assert(self, rec, prop, field, valtype=None, is_obj=False):
        if is_obj:
            return [f"rdf_assert('{field}', '{prop}', '{rec}')"]
        if not valtype:
            return [f"rdf_assert('{rec}', '{prop}', '{field}')"]
        if "http://www.w3.org/2001/XMLSchema#" in valtype:
            return [f"rdf_assert('{rec}', '{prop}',"
                    f" {escape_string(field)}^^'{valtype}')"]
        else:
            if self.rpq.boolquery(f"xcat_type('{field}', '{valtype}')"):
                return [f"rdf_assert('{rec}', '{prop}', '{field}')"]
            else:
                log.warning(f"{field} is not a {valtype}")
        return []


    def _recording_is_property(self):
        rev_prop_query = self.rpq.query(
                *instance_is_property).copy(self.recording_node["Track"])
        fields = []
        for sbj, res in rev_prop_query.items():
            if (tag_func := self.tag_mapping.get(res["PredURI"])):
                alt_val = tag_func(self.path_tagdata)
                log.debug(alt_val)
            else:
                alt_val = ""
            if res["PredURI"] == str(XCAT.recording):
                sbj = self.file_resource
            prop = PropertyEdit(res["PredURI"], res["Predicate"],
                                sbj, res.type, alt_val)
            fields.append(prop)
            self.new_rec['rec_is_prop'][res["PredURI"]] = (prop, res.type)

        return ur.ListBox(ur.SimpleFocusListWalker(fields))


    def _recording_properties(self):
        prop_query = self.rpq.query(
                *instance_properties).copy(self.recording_node["Track"])
        fields = []
        for obj, res in prop_query.items():
            if (tag_func := self.tag_mapping.get(res["PredURI"])):
                alt_val = tag_func(self.path_tagdata)
                #log.debug(alt_val)
            else:
                alt_val = ""
            if res["PredURI"] == str(XCAT.file):
                obj = self.file_resource
            if "http://www.w3.org/2001/XMLSchema#" in res.type:
                obj = self.rpq.simple_query(
                        f"rdf('{self.recording_node['Track']}', "
                        f"'{res['PredURI']}', X^^'{res.type}')")
                #log.debug(obj)
            if alt_val:
                obj = alt_val
                alt_val = ""
            prop = PropertyEdit(res["PredURI"], res["Predicate"],
                                obj, res.type, alt_val)
            fields.append(prop)
            self.new_rec['rec_props'][res["PredURI"]] = (prop, res.type)
        if (encoding := self.path_tagdata.get("encoding")):
            prop = PropertyEdit(XCAT.encoding, "encoding", encoding, XSD.string)
            fields.append(prop)
            self.new_rec["encoding"] = (prop, XSD.string)
        return ur.ListBox(ur.SimpleFocusListWalker(fields))


    def _fill_options(self):
        fill_options = [SelectableText("add recording")]
        return ur.ListBox(ur.SimpleFocusListWalker(fill_options))


    def keypress(self, size, key):
        if self.focus_position == 2 and key == "enter":
            if self.focus.focus.get_text()[0] == "add recording":
                self.add_recording()
                return
            log.debug(self.focus.focus.get_text()[0] )
        if (res := super().keypress(size, key)):
            return res


class FindTracklist(EditWindow, ur.WidgetWrap):
    root = XCAT.Release
    name = "Find Tracklist"
    columns = ["#", "Tag Release", "Tag Title", "Title", "Artist", "Encoding",
               "Path"]
    tagdata = TagData()

    def __init__(self, rpq, update_resource):
        self.rpq = rpq
        self.moving = None
        self.add_mode = False
        widget = TableList(self.columns)
        super().__init__(widget, update_resource)


    def keypress(self, size, key):
        if not self.add_mode:
            row, col = self._w.selected()
            if col:
                if key == "enter":
                    if self.moving:
                        self.move_row(row)
                    elif row:
                        if self._w.selected_col() == "#":
                            self.move_row(row)
                    return
                if key == 'a':
                    self.add_mode = True
                    self._w = RecordingImport(self.rpq, row, self.parent,
                                              self.update_resource)
                    return
                if key == 't':
                    self.add_tracklist()
                    return
        if (res := super().keypress(size, key)):
            return res


    def move_row(self, row_key):
        if self.moving:
            # put row_widget after row_key
            if row_key:
                new_sortval = self._w[row_key][0].sort + 1
            else:
                new_sortval = self._w.body[1][0].sort
            move_start = self._w.index(row_key) + 1
            move_sortval = new_sortval + 1
            for row in self._w.body[move_start:]:
                row[0].sort = max(row[0].sort, move_sortval)
                move_sortval = row[0].sort + 1
            self._w[self.moving][0].sort = new_sortval
            self._w.sort_by("#")
            self.moving = None
        else:
            self.moving = row_key


    def add_tracklist(self):
        tracklist = []
        for row in self._w.body[1:]:
            item = row[3]
            if item.key:
                tracklist.append(item.key)
                log.debug((item.key, item._w.get_text()))
        res = self.rpq.TrackList(self.parent, tracklist)
        log.debug(res)


    @staticmethod
    def stringint(string):
        intval = ord(string[0])
        for char in string[1:]:
            intval = intval * 0x110000
            intval += ord(char)
        return intval


    def load_instance(self, instance_key):
        prop_query = self.rpq.query(*release_tracks)
        prop_query.parent = instance_key
        self.parent = instance_key

        paths = set()
        for obj, res in prop_query.items():
            tags = self.tagdata.match_path(res["Path"])
            track = (tags.get("track") or ["."])[0]
            widget_list = [TableItem(track,
                                     sort=self.stringint(track.rjust(4, "0"))),
                           TableItem((tags.get("release") or ["."])[0]),
                           TableItem((tags.get("title") or ["."])[0]),
                           TableItem(obj, res["TLabel"]),
                           TableItem(res["Artist"]),
                           TableItem(tags.get("encoding", "???")),
                           TableItem(res["Path"])]
            self._w.add_row(res["Path"], widget_list)
            paths.add(res["Path"])

        release_lbl = prop_query.first_item()["RLabel"]
        for path, tags in self.tagdata.match_data(release=release_lbl).items():
            if path not in paths:
                track = (tags.get("track") or ["."])[0]
                widget_list = [TableItem(track,
                                         sort=self.stringint(track.rjust(4, "0"))),
                               TableItem((tags.get("release") or ["."])[0]),
                               TableItem((tags.get("title") or ["."])[0]),
                               TableItem(None, "."), TableItem("."),
                               TableItem(tags.get("encoding", "???")),
                               TableItem(path)]
                self._w.add_row(path, widget_list)

        self._w.align()
        self._w.sort_by("#")