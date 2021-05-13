#!/usr/bin/env python3

import os
import time
import urllib.parse as url
from collections import Hashable

import rdflib as rdf
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, OWL, FOAF, DC, PROV, XSD, TIME
from blake3 import blake3
from beets.library import Library

FRBR = rdf.Namespace('http://purl.org/vocab/frbr/core')
MO = rdf.Namespace('http://purl.org/ontology/mo/')
EVENT = rdf.Namespace('http://purl.org/NET/c4dm/event.owl#')

B3 = rdf.Namespace('hash://blake3/')
LOCAL = rdf.Namespace('PSEUDOCRAFT:')
XCAT = rdf.Namespace('http://xeroxc.at/schema#')

release_dict = {}

def rdf_match(query, graph, unique=False):
    matching_values = set()
    matching_triples = graph.triples(query[0])
    blank_idx = query[0].index(None)
    for match in matching_triples:
        matching_values.add(match[blank_idx])
    for triple in query[1:]:
        if not matching_values:
            return None if unique else set()
        else:
            triple = list(triple)
            blank_idx = triple.index(None)
            for value in tuple(matching_values):
                triple[blank_idx] = value
                if not tuple(graph.triples(triple)):
                    matching_values.remove(value)

    if unique:
        if not matching_values:
            return None
        elif len(matching_values) == 1:
            return matching_values.pop()
        else:
            raise Exception(f'Result from query:\n {query}\n '
                            f'is non-unique. Results: {matching_values}')
    else:
        return matching_values


def rdf_matchorinit(query, graph, node=None):
    if not (result := rdf_match(query, graph, unique=True)):
        result = node or rdf.BNode()
        for triple in query:
            blank_idx = triple.index(None)
            triple = list(triple)
            triple[blank_idx] = result
            graph.add(triple)
    elif node and isinstance(result, rdf.BNode):
        for pred, obj in data_g.predicate_objects(result):
            graph.remove((result, pred, obj))
            graph.add((node, pred, obj))
        for subj, pred in data_g.subject_predicates(result):
            graph.remove((subj, pred, result))
            graph.add((subj, pred, node))
        result = node
    elif (isinstance(result, rdf.URIRef) and isinstance(node, rdf.URIRef)
          and result != node):
        raise Exception("Implement a SameAs?")

    return result


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

    albumartist = rdf_matchorinit(((None, RDF.type, MO.MusicArtist),
                                   (None, FOAF.name, albumartist_lbl)),
                                  data_g, albumartist)
    data_g.add((release_uri, FOAF.maker, albumartist))
    data_g.add((albumartist, FOAF.made, release_uri))

    if (year := _beets['year']):
        date = str(year)
        date_type = XSD.gYear
        instant_is = TIME.inXSDgYear
        if (month := _beets['month']):
            date += '-' + str(month).rjust(2, '0')
            date_type = XSD.gYearMonth
            instant_is = TIME.inXSDgYearMonth
            if (day := _beets['day']):
                date += '-' + str(day).rjust(2, '0')
                date_type = XSD.date
                instant_is = TIME.inXSDDate
        date = rdf.Literal(date)

        if not (time_node := time_g.value(None, instant_is, date)):
            time_node = rdf.BNode()
            time_g.add((time_node, instant_is, date))
            time_g.add((time_node, RDF.type, TIME.Instant))
            time_g.add((date, RDF.type, date_type))
        data_g.add((release_uri, EVENT.time, time_node))

    for genre_name in get_genre_vals(_beets):
        genre_lbl = rdf.Literal(genre_name)
        genre = rdf_matchorinit(((None, FOAF.name, genre_lbl),
                                 (None, RDF.type, MO.Genre)), data_g)
        data_g.add((release_uri, MO.genre, genre))

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

    file_g.add((file_URN, RDF.type, MO.AudioFile))
    file_g.add((file_URN, MO.encoding, rdf.Literal(data['format'])))
    file_g.add((file_URN, PROV.atLocation, file_path))
    file_g.add((file_path, RDF.type, PROV.Location))

    if source == 'Discogs':
        artist = discogs_url('artist', data['discogs_artistid'])
        release = discogs_url('release', data['discogs_albumid'])
        track = rdf_match(((None, DC.title, track_lbl),
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

    artist = rdf_matchorinit(((None, RDF.type, MO.MusicArtist),
                              (None, FOAF.name, artist_lbl)), data_g, artist)

    data_g.add((track, RDF.type, MO.Track))
    data_g.add((track, MO.item, file_URN))
    data_g.add((track, MO.track_number, track_num))
    data_g.add((track, DC.title, track_lbl))
    data_g.add((track, FOAF.maker, artist))
    data_g.add((artist, FOAF.made, track))

    for genre_name in get_genre_vals(data):
        genre_lbl = rdf.Literal(genre_name)
        genre = rdf_matchorinit(((None, FOAF.name, genre_lbl),
                                 (None, RDF.type, MO.Genre)), data_g)
        data_g.add((track, MO.genre, genre))

    if release not in data_g.subjects():
        beetz_release = beets_lib.get_album(data['album_id'])
        release_from_beets(data_g, time_g, release, source, beetz_release)

    tracklist = release_dict[release]
    tracklist += [(data['track'], track)]
    if len(tracklist) == data['tracktotal']:
        #add tracklist to release
        sorted_tracklist = [track[1] for track in sorted(tracklist)]
        tracklist_node = Collection(data_g, None, sorted_tracklist)._get_container(0)
        data_g.add((release, XCAT.tracklist, tracklist_node))
        #print(release)
        #print(sorted_tracklist)
        del release_dict[release]

    data_g.add((release, MO.track, track))


def get_genre_vals(beets_dict):
    genres = []
    if (genre := beets_dict.get('genre')):
        if ',' in genre:
            genres += [g.strip() for g in genre.split(',')]
        else:
            genres += [genre]
    if (style := beets_dict.get('style')):
        if ',' in style:
            genres += [s.strip() for s in style.split(',')]
        else:
            genres += [genre]
    return genres


def file_hash(file_path, chunksize=65536):
    hasher = blake3()
    chunk = 0
    #no hashing for test speed
    import uuid
    return str(uuid.uuid1())
    with open(file_path, "rb") as f:
        try:
            fullsize = os.path.getsize(file_path)
            print(f'\thashing {file_path[-80:]} {fullsize//1024}KiB ', end='\r')
            while True:
                some_bytes = f.read(chunksize)
                chunk += 1
                print(f'{int(((chunk*chunksize)/fullsize)*100)}% ', end='\r')
                if not some_bytes:
                    break
                hasher.update(some_bytes)
            print(' ' * 120, end='\r')
        except KeyboardInterrupt:
            time.sleep(2)
            return None
    return hasher.hexdigest()


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
            if lib and (filedata := beets_find_track(lib, fullpath)):
                _hash = file_hash(fullpath)
                in_db[filename] = dict(_hash=_hash,
                                       _url=url.quote(fullpath), **filedata)
            else:
                not_in_db[filename] = dict(_hash=None,
                                           _url=url.quote(fullpath))
        if in_db or not_in_db:
            dirpaths[dirpath] = (in_db, not_in_db)

    return dirpaths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='file or folder to scan')
    args = parser.parse_args()
    path = os.path.abspath(args.input)
    beets_lib = beets_init('../data/ext/music.db')

    dirpaths = rec_load_dir(path, beets_lib)
    file_g = rdf.Graph()
    time_g = rdf.Graph()
    data_g = rdf.Graph()
    add_namespaces(file_g, data_g, time_g)

    for dir, (in_db, not_in_db) in dirpaths.items():
        for entry in in_db.values():
            add_to_graph(data_g, file_g, time_g, beets_lib, entry)

    #cereal = file_g.serialize(format='nt').decode('utf-8')
    #print(cereal)
    cereal = data_g.serialize(format='nt')#, all_bnodes=True)#.decode('utf-8')
    print(cereal)
    #cereal = time_g.serialize(format='turtle', all_bnodes=True)#.decode('utf-8')
    #print(cereal)
