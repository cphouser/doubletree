#!/usr/bin/env python3

import os
import time
import pickle
from datetime import datetime

from rdflib.namespace import RDF, RDFS, OWL, XSD
from beets.library import Library
from pyswip.prolog import Prolog

from rdf_util import discogs
from rdf_util.namespaces import B3, XCAT
from rdf_util.b3 import file_hash, hashlist_hash
from rdf_util.pl import query, xsd_type, rdf_find, new_bnode, LDateTime, TrackList

release_dict = {}

def discogs_url(key, value):
    base = "http://www.discogs.com/"
    if 'label' in key:
        return (base + 'label/' + str(value))
    elif 'artist' in key:
        return (base + 'artist/' + str(value))
    elif 'release' in key:
        return (base + 'release/' + str(value))


def mb_url(key, value):
    base = "http://musicbrainz.org/"
    if 'track' in key:
        return (base + 'recording/' + str(value))
    elif 'artist' in key:
        return (base + 'artist/' + str(value))
    elif 'release' in key:
        return (base + 'release/' + str(value))


def nometa_file_node(pl, data):
    file_path = xsd_type(data['path'], 'string')
    file_URN = B3[data['_hash']]
    query(pl, (('rdf_assert', (file_URN, RDF.type, XCAT.File)),
               ('rdf_assert', (file_URN, XCAT.path, file_path))
               ))
    return file_URN


def entries_to_dir(pl, dir_hash, dir, dir_entries, subdir_hashes):
    path = xsd_type(dir, 'string')
    dir_URN = B3[dir_hash]

    query(pl, [('rdf_assert', (dir_URN, RDF.type, XCAT.Directory)),
               ('rdf_assert', (dir_URN, XCAT.path, path)),
               ('rdf_assert', (dir_URN, XCAT.hash, dir_hash))]
          + [('rdf_assert', (dir_URN, XCAT.dirEntry, entry))
             for entry in dir_entries]
          + [('rdf_assert', (dir_URN, XCAT.dirEntry, B3[subdir_hash]))
             for subdir_hash in subdir_hashes])


def release_from_beets(pl, release_uri, source, _beets):
    global release_dict
    release_dict[release_uri] = []
    release_lbl = xsd_type(_beets['album'], 'string')
    query(pl, (('rdf_assert', (release_uri, RDF.type, XCAT.Release)),
               ('rdf_assert', (release_uri, XCAT.title, release_lbl))
               ))

    albumartist_lbl = xsd_type(_beets['albumartist'], 'string')
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
            albumartist = _beets['mb_albumartistid']
        else:
            label_uri = _beets['mb_albumartistid']
    elif source == 'MusicBrainz':
        if _beets['albumartist']:
            albumartist = mb_url('artist', _beets['mb_albumartistid'])
        elif (albumartist_credit := _beets['albumartist_credit']):
            albumartist_lbl = xsd_type(albumartist_credit, "string")
    else:
        print("what source?", source, release_uri)

    if not albumartist:
        albumartist = (rdf_find(pl,
                                ((None, RDF.type, XCAT.Artist),
                                 (None, XCAT.name, albumartist_lbl)))
                       or new_bnode(pl))

    query(pl, (('rdf_assert', (albumartist, RDF.type, XCAT.Artist)),
               ('rdf_assert', (albumartist, XCAT.name, albumartist_lbl)),
               ('rdf_assert', (release_uri, XCAT.maker, albumartist)),
               ('rdf_assert', (albumartist, XCAT.made, release_uri))
               ))

    if (year := _beets['year']):
        month = _beets.get('month')
        day = _beets.get('day')
        published_in = LDateTime(pl, year=year, month=month, day=day)
        query(pl, [('rdf_assert',
                    (release_uri, XCAT.published_during, published_in))])

    add_genres(pl, release_uri, _beets)

    if label_uri:
        label_lbl = xsd_type(_beets['label'], 'string')
        query(pl, (('rdf_assert', (label_uri, RDF.type, XCAT.MusicLabel)),
                ('rdf_assert', (label_uri, XCAT.name, label_lbl)),
                ('rdf_assert', (label_uri, XCAT.published, release_uri)),
                ('rdf_assert', (release_uri, XCAT.publisher, label_uri))
                ))

        if _beets['catalognum']:
            cat_num = xsd_type(_beets['catalognum'], 'string')
            query(pl, [('rdf_assert',
                        (release_uri, XCAT.catalog_num, cat_num))])


def track_from_beets(pl, beets_lib, data):
    file_URN = B3[data['_hash']]
    file_path = xsd_type(data['path'], 'string')
    encoding = xsd_type(data['format'], 'string')
    track_num = data['track']
    mtime = datetime.fromtimestamp(data['_mtime'])

    ## Add the file
    query(pl, (('rdf_assert', (file_URN, RDF.type, XCAT.AudioFile)),
               ('rdf_assert', (file_URN, XCAT.encoding, encoding)),
               ('rdf_assert', (file_URN, XCAT.path, file_path)),
               ('rdf_assert', (file_URN, XCAT.hash, xsd_type(data['_hash'],
                                                             'string')))))

    ## Define resources URI's depending on data source
    source = data['data_source']
    track_lbl = xsd_type(data['title'], 'string')
    artist_lbl = xsd_type(data['artist'], 'string')
    rel_lbl = xsd_type(data['album'], 'string')
    if source == 'Discogs':
        artist = discogs_url('artist', data['discogs_artistid'])
        release = discogs_url('release', data['discogs_albumid'])
        # Not a useful URL but discogs doesn't uniquely identify
        # individual tracks.
        track = release + '#' + str(track_num)
    elif source == 'MusicBrainz':
        artist = mb_url('artist', data['mb_artistid'])
        release = mb_url('release', data['mb_albumid'])
        track = mb_url('track', data['mb_trackid'])
    elif source == 'bandcamp':
        # url for albumartistid can be artist or label
        # bandcamp parser uniquely always fills label field
        if data['label'] == data['artist']:
            artist = data['mb_artistid']
        else:
            artist = (rdf_find(pl,
                               ((None, RDF.type, XCAT.Artist),
                                (None, XCAT.name, artist_lbl)))
                      or new_bnode(pl))
        release = data['mb_albumid']
        track = data['mb_trackid']

    ## Add the artist
    query(pl, (('rdf_assert', (artist, RDF.type, XCAT.Artist)),
               ('rdf_assert', (artist, XCAT.name, artist_lbl))
               ))

    ## Add the mtime
    mtime_term = LDateTime(pl, year=mtime.year, month=mtime.month,
                           day=mtime.day, hour=mtime.hour)

    ## Add the track
    query(pl, (('rdf_assert', (track, RDF.type, XCAT.Track)),
               ('rdf_assert', (track, XCAT.file, file_URN)),
               ('rdf_assert', (track, XCAT.title, track_lbl)),
               ('rdf_assert', (track, XCAT.added_during, mtime_term)),
               ('rdf_assert', (track, XCAT.released_on, release)),
               ('rdf_assert', (track, XCAT.maker, artist)),
               ('rdf_assert', (artist, XCAT.made, track))
               ))

    ## Add the genres
    add_genres(pl, track, data)

    ## Add the release
    if not (res := query(pl, [('rdf', (release, RDF.type, XCAT.Release))])):
        beetz_release = beets_lib.get_album(data['album_id'])
        release_from_beets(pl, release, source, beetz_release)

    tracklist = release_dict[release]
    tracklist += [(data['track'], track)]

    ## Add the tracklist if it's full
    if len(tracklist) == data['tracktotal']:
        # add tracklist to release
        tracklist.sort()
        for idx, (track_num, track) in enumerate(tracklist):
            if idx + 1 != track_num:
                raise Exception(f"Tracklist Misaligned\nTrack {idx + 1}"
                                f" has track num {data['track']}\n{track}")
        # extract list of only second value in list of tuples
        sorted_tracks = list(tuple(zip(*tracklist))[1])
        tlist_node = TrackList(pl, sorted_tracks)
        query(pl, [('rdf_assert', (release, XCAT.tracklist, tlist_node))])
        del release_dict[release]

    query(pl, [('rdf_assert', (track, XCAT.released_on, release))])

    return file_URN


def add_genres(pl, subj, beets_dict):
    genres, styles, unmatched = discogs.genre_styles(get_genre_vals(beets_dict),
                                                     get_style_vals(beets_dict))
    for genre_name, genre_uri in genres:
        genre_name = xsd_type(genre_name, 'string')
        query(pl, (('rdf_assert', (genre_uri, RDF.type, XCAT.Genre)),
                   ('rdf_assert', (genre_uri, XCAT.name, genre_name)),
                   ('rdf_assert', (subj, XCAT.genre, genre_uri))
                   ))
    for (style_name, style_uri), (genre_name, genre_uri) in styles:
        genre_name = xsd_type(genre_name, 'string')
        style_name = xsd_type(style_name, 'string')
        query(pl, (('rdf_assert', (style_uri, RDF.type, XCAT.Style)),
                   ('rdf_assert', (style_uri, XCAT.name, style_name)),
                   ('rdf_assert', (subj, XCAT.style, style_uri)),
                   ('rdf_assert', (style_uri, XCAT.parent_genre, genre_uri)),
                   ('rdf_assert', (genre_uri, XCAT.genre_style, style_uri))
                   ))
    for unmatched_name in unmatched:
        style_name = xsd_type(unmatched_name, 'string')
        style_uri = (rdf_find(pl, ((None, RDF.type, XCAT.Style),
                                   (None, XCAT.name, style_name))
                              ) or new_bnode(pl))
        query(pl, (('rdf_assert', (style_uri, RDF.type, XCAT.Style)),
                   ('rdf_assert', (style_uri, XCAT.name, style_name)),
                   ('rdf_assert', (subj, XCAT.style, style_uri))
                   ))


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
        item = dict(item.items())
        item['path'] = item['path'].decode('utf-8')
        return item
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
    for dirpath, subdirs, filenames in os.walk(base_path, onerror=print,
                                                    topdown=False):
        in_db = {}
        not_in_db = {}
        subdir_hashes = []
        entry_hashes = []
        for subdir in subdirs:
            subdir_path = os.path.join(dirpath, subdir)
            if not (subdir_dirpath := dirpaths.get(subdir_path)):
                raise Exception(f"{subdir_path}\nEncountered before\n{dirpath}")
            subdir_hashes += [subdir_dirpath[3]]

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            _mtime = os.stat(fullpath).st_mtime
            _hash = file_hash(fullpath, interactive=True)
            entry_hashes += [_hash]
            if lib and (filedata := beets_find_track(lib, fullpath)):
                in_db[filename] = dict(_hash=_hash, _mtime=_mtime, **filedata)
            else:# 'path' matches respective key name from beets
                not_in_db[filename] = dict(_hash=_hash, _mtime=_mtime,
                                           path=fullpath)
        if entry_hashes or subdir_hashes:
            print(entry_hashes)
            print(subdir_hashes)
            dir_hash = hashlist_hash(entry_hashes + subdir_hashes)
            print(dir_hash)
            print()
            dirpaths[dirpath] = (in_db, not_in_db, subdir_hashes, dir_hash)

    return dirpaths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='folder to scan')
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

    # initialize prolog store
    pl = Prolog()
    pl.consult('init.pl')

    # load files from directory
    if args.reload:
        cache = None
    else:
        try:
            cache = pickle.load(open(cache_file, 'rb'))
        except Exception as e:
            cache = None
            print(f'could not load cache {cache_file}\n{e}')
    if cache:
        dirpaths = cache
    else:
        dirpaths = rec_load_dir(path, beets_lib)

    # cache directory data
    pickle.dump(dirpaths, open(cache_file, 'wb'))

    # add music data from directory to prolog rdf store
    for dir, (in_db, not_in_db, subdir_hashes, dir_hash) in dirpaths.items():
        dir_entries = []
        print(dir)
        for entry in in_db.values():
            dir_entries += [track_from_beets(pl, beets_lib, entry)]
        for entry in not_in_db.values():
            dir_entries += [nometa_file_node(pl, entry)]
            print('\t', entry)
        entries_to_dir(pl, dir_hash, dir, dir_entries, subdir_hashes)
