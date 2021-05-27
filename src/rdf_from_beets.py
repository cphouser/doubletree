#!/usr/bin/env python3

import os
import time
import urllib.parse as url
#from collections import Hashable
import pickle

import rdflib as rdf
from rdflib.container import Seq
from rdflib.namespace import RDF, RDFS, OWL, FOAF, DC, PROV, XSD, TIME
from beets.library import Library

from rdf_util import discogs
from rdf_util import graphs as rdfg
from rdf_util.namespaces import MO, B3, LOCAL, XCAT
from rdf_util import files

release_dict = {}

def discogs_url(key, value):
    base = "http://www.discogs.com/"
    if 'label' in key:
        return rdf.URIRef(base + 'label/' + str(value))
    elif 'artist' in key:
        return rdf.URIRef(base + 'artist/' + str(value))
    elif 'release' in key:
        return rdf.URIRef(base + 'release/' + str(value))


def mb_url(key, value):
    base = "http://musicbrainz.org/"
    if 'track' in key:
        return rdf.URIRef(base + 'recording/' + str(value))
    elif 'artist' in key:
        return rdf.URIRef(base + 'artist/' + str(value))
    elif 'release' in key:
        return rdf.URIRef(base + 'release/' + str(value))

    
def add_namespaces(*graphs):
    for graph in graphs:
        graph.bind('mo', rdf.URIRef('http://purl.org/ontology/mo/'))
        graph.bind('b3', rdf.URIRef('hash://blake3/'))
        graph.bind('event', rdf.URIRef('http://purl.org/NET/c4dm/event.owl#'))
        graph.bind('rdf', RDF)
        graph.bind('owl', OWL)
        graph.bind('prov', PROV)
        graph.bind('foaf', FOAF)
        graph.bind('xsd', XSD)
        graph.bind('dc', DC)
        graph.bind('time', TIME)
        graph.bind('xcat', XCAT)


def release_from_beets(data_g, time_g, release_uri, source, _beets):
    release_dict[release_uri] = []
    data_g.add((release_uri, DC.title, rdf.Literal(_beets['album'])))
    data_g.add((release_uri, RDF.type, MO.Release))
    albumartist_lbl = rdf.Literal(_beets['albumartist'])
    label_uri = None
    albumartist = None
    if source == 'Discogs':
        albumartist = discogs_url('artist', _beets['discogs_artistid'])
        # www.discogs.com/label/1818 is the "Not On Label" placeholder
        if not (label_id := _beets['discogs_labelid']) == 1818:
            label_uri = discogs_url('label', label_id)
    elif source == 'bandcamp':
        # url for albumartistid can be artist or label
        # bandcamp parser uniquely always fills label field
        if _beets['label'] == _beets['albumartist']:
            albumartist = rdf.URIRef(_beets['mb_albumartistid'])
        else:
            label_uri = rdf.URIRef(_beets['mb_albumartistid'])
    elif source == 'MusicBrainz':
        if albumartist_lbl:
            albumartist = mb_url('artist', _beets['mb_albumartistid'])
        elif (albumartist_credit := _beets['albumartist_credit']):
            albumartist_lbl = rdf.Literal(albumartist_credit)
    else:
        print("what source?", source, release_uri)

    albumartist = rdfg.matchorinit(((None, RDF.type, MO.MusicArtist),
                                   (None, FOAF.name, albumartist_lbl)),
                                  data_g, albumartist)
    data_g.add((release_uri, FOAF.maker, albumartist))
    data_g.add((albumartist, FOAF.made, release_uri))

    if (year := _beets['year']):
        month = _beets.get('month')
        day = _beets.get('day')
        published_in = rdfg.time_node(time_g, year=year, month=month, day=day)
        data_g.add((release_uri, XCAT.published_during, published_in))

    add_genres(release_uri, data_g, _beets)

    if label_uri:
        data_g.add((label_uri, RDF.type, MO.Label))
        data_g.add((label_uri, FOAF.name, rdf.Literal(_beets['label'])))
        data_g.add((label_uri, MO.published, release_uri))
        data_g.add((release_uri, MO.publisher, label_uri))
        if cat_num := _beets['catalognum']:
            data_g.add((release_uri, MO.catalogue_number, rdf.Literal(cat_num)))


def add_to_graph(data_g, file_g, time_g, beets_lib, data):
    file_URN = B3[data['_hash']]
    file_path = rdf.Literal(data['path'].decode('utf-8'))
    source = data['data_source']
    track_lbl = rdf.Literal(data['title'])
    artist_lbl = rdf.Literal(data['artist'])
    rel_lbl = rdf.Literal(data['album'])
    track_num = rdf.Literal(data['track'])
    mtime = data['_mtime']
    #print(file_path, mtime)

    file_g.add((file_URN, RDF.type, MO.AudioFile))
    file_g.add((file_URN, MO.encoding, rdf.Literal(data['format'])))
    file_g.add((file_URN, PROV.atLocation, file_path))
    file_g.add((file_path, RDF.type, PROV.Location))

    if source == 'Discogs':
        artist = discogs_url('artist', data['discogs_artistid'])
        release = discogs_url('release', data['discogs_albumid'])
        track = rdfg.match(((None, DC.title, track_lbl),
                           (None, MO.track_number, track_num),
                           (release, MO.track, None)),
                          data_g, unique=True) or rdf.BNode()
    elif source == 'MusicBrainz':
        artist = mb_url('artist', data['mb_artistid'])
        release = mb_url('release', data['mb_albumid'])
        track = mb_url('track', data['mb_trackid'])
    elif source == 'bandcamp':
        # url for albumartistid can be artist or label
        # bandcamp parser uniquely always fills label field
        if data['label'] == artist_lbl:
            artist = rdf.URIRef(_beets['mb_artistid'])
        else:
            artist = None
        release = rdf.URIRef(data['mb_albumid'])
        track = rdf.URIRef(data['mb_trackid'])

    artist = rdfg.matchorinit(((None, RDF.type, MO.MusicArtist),
                              (None, FOAF.name, artist_lbl)), data_g, artist)

    rdfg.add_date_added(track, data_g, time_g, mtime)

    data_g.add((track, RDF.type, MO.Track))
    data_g.add((track, MO.item, file_URN))
    data_g.add((track, MO.track_number, track_num))
    data_g.add((track, DC.title, track_lbl))
    data_g.add((track, FOAF.maker, artist))
    data_g.add((artist, FOAF.made, track))

    add_genres(track, data_g, data)

    if release not in data_g.subjects():
        beetz_release = beets_lib.get_album(data['album_id'])
        release_from_beets(data_g, time_g, release, source, beetz_release)

    tracklist = release_dict[release]
    tracklist += [(data['track'], track)]
    if len(tracklist) == data['tracktotal']:
        #add tracklist to release
        sorted_tracklist = [track[1] for track in sorted(tracklist)]
        tracklist_node = Seq(data_g, None,
                             sorted_tracklist)._get_container()
        data_g.add((release, XCAT.tracklist, tracklist_node))
        data_g.add((tracklist_node, RDF.type, XCAT.Tracklist))
        del release_dict[release]

    data_g.add((release, MO.track, track))
    data_g.add((track, DC.title, track_lbl))


def add_genres(subj, data_g, beets_dict):
    genres, styles, unmatched = discogs.genre_styles(get_genre_vals(beets_dict),
                                                     get_style_vals(beets_dict))
    for genre_name, genre_uri in genres:
        genre_uri = rdf.URIRef(genre_uri)
        genre_name = rdf.Literal(genre_name)
        if genre_uri not in data_g.subjects():
            data_g.add((genre_uri, RDF.type, MO.Genre))
            data_g.add((genre_uri, RDFS.label, genre_name))
        data_g.add((subj, MO.genre, genre_uri))

    for (style_name, style_uri), (genre_name, genre_uri) in styles:
        style_uri = rdf.URIRef(style_uri)
        genre_uri = rdf.URIRef(genre_uri)
        style_name = rdf.Literal(style_name)
        genre_name = rdf.Literal(genre_name)
        if style_uri not in data_g.subjects():
            data_g.add((style_uri, RDF.type, XCAT.Style))
            data_g.add((style_uri, RDFS.label, style_name))
            if genre_uri not in data_g.subjects():
                data_g.add((genre_uri, RDF.type, MO.Genre))
                data_g.add((genre_uri, RDFS.label, genre_name))
            data_g.add((style_uri, XCAT.genre, genre_uri))
        data_g.add((subj, XCAT.style, style_uri))

    for unmatched_name in unmatched:
        style_name = rdf.Literal(unmatched_name)
        rdfg.matchorinit(((None, RDFS.label, rdf.Literal(unmatched_name)),
                         (None, RDF.type, XCAT.Style)), data_g)


def get_genre_vals(beets_dict):
    genres = []
    if (genre := beets_dict.get('genre')):
        if ',' in genre:
            genres += [g.strip() for g in genre.split(',')]
        else:
            genres += [genre]
    return genres


def get_style_vals(beets_dict):
    styles = []
    if (style := beets_dict.get('style')):
        if ',' in style:
            styles += [s.strip() for s in style.split(',')]
        else:
            styles += [style]
    return styles


def beets_find_track(lib, path):
    results = lib.items(f'path:"{path}"')
    if (item := results[0] if len(results) else None):
        return dict(item.items())
    else:
        return {}


def beets_find_release(lib, item_id):
    if (result := lib.get_album(item_id)):
        return dict(result.items())
    else:
        return {}


def beets_init(path):
    return Library(path)


def rec_load_dir(base_path, lib=None):
    """Search a file path recursively for files in the beets library"""
    dirpaths = {}
    for dirpath, _, filenames in os.walk(base_path, onerror=print):#,
                                         #topdown=False):
        in_db = {}
        not_in_db = {}
        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            _mtime = os.stat(fullpath).st_mtime
            if lib and (filedata := beets_find_track(lib, fullpath)):
                _hash = files.file_hash(fullpath, interactive=True)
                in_db[filename] = dict(_hash=_hash,
                                       _mtime=_mtime,
                                       _url=url.quote(fullpath), **filedata)
            else:
                not_in_db[filename] = dict(_hash=None,
                                           _mtime=_mtime,
                                           _url=url.quote(fullpath))
        if in_db or not_in_db:
            dirpaths[dirpath] = (in_db, not_in_db)

    return dirpaths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='file or folder to scan')
    parser.add_argument('--beets-library', '-b',
                        help='beets sqlite db to reference')
    parser.add_argument('--reload', '-r', action='store_true',
                        help='beets sqlite db to reference')
    args = parser.parse_args()
    path = os.path.abspath(args.input)
    data_location = '../data/'
    beets_path = args.beets_library or os.path.join(data_location,
                                                    'ext/music.db')
    beets_lib = beets_init(beets_path)
    cache_file = os.path.join(data_location, 'cache/loaded_dir.pickle')
    graph_location = os.path.join(data_location, 'nt/')
    graph_files = ('file_g', 'time_g', 'data_g')

    if args.reload:
        cache = None
    else:
        try:
            cache = pickle.load(open(cache_file, 'rb'))
        except Exception as e:
            cache = None
            print(f'could not load cache {cache_file}')
            print(e)
            print()

    if cache:
        dirpaths = cache
    else:
        dirpaths = rec_load_dir(path, beets_lib)

    pickle.dump(dirpaths, open(cache_file, 'wb'))

    file_g = rdf.Graph()
    time_g = rdf.Graph()
    data_g = rdf.Graph()
    add_namespaces(file_g, data_g, time_g)

    for dir, (in_db, not_in_db) in dirpaths.items():
        for entry in in_db.values():
            add_to_graph(data_g, file_g, time_g, beets_lib, entry)
        print(dir)
        for entry in not_in_db.values():
            print('\t', entry['_url'])

    for graph, filename in zip((file_g, time_g, data_g), graph_files):
        g_path = os.path.join(graph_location, filename)
        graph.serialize(g_path + '.ttl.2', format='turtle')
        graph.serialize(g_path + '.nt.2', format='nt')
