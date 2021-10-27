#!/usr/bin/env python3

import os
import time
import pickle
from datetime import datetime
import logging
from sys import stdout
from pprint import pformat

from rdflib.namespace import RDF, RDFS, OWL, XSD
from beets.library import Library
from pyswip.prolog import Prolog

from util.rdf import discogs
from util.rdf.namespaces import B3, XCAT
from util.rdf.b3 import file_hash, hashlist_hash
from util.rdf.pl import (xsd_type, LDateTime, entries_to_dir,
                         TrackList, rdf_unify, RPQ, nometa_file_node)
from util.log import LogFormatter

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


def release_from_beets(rpq, release_uri, source, _beets):
    release_lbl = xsd_type(_beets['album'], 'string')
    rpq.rassert(*[
        f"rdf_assert('{release_uri}', '{RDF.type}', '{XCAT.Release}')",
        f"rdf_assert('{release_uri}', '{XCAT.title}', {release_lbl})",
    ])

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
        albumartist = rpq.simple_query(
                f"rdf(X, '{RDF.type}', '{XCAT.Artist}'), "
                f"rdf(X, '{XCAT.Name}', {albumartist_lbl})") or rpq.new_bnode()
        if isinstance(albumartist, list):
            albumartist = rdf_unify(rpq, albumartist)

    rpq.rassert(*[
        f"rdf_assert('{albumartist}', '{RDF.type}', '{XCAT.Artist}')",
        f"rdf_assert('{albumartist}', '{XCAT.name}', {albumartist_lbl})",
        f"rdf_assert('{release_uri}', '{XCAT.maker}', '{albumartist}')",
        f"rdf_assert('{albumartist}', '{XCAT.made}', '{release_uri}')"
    ])

    if (year := _beets['year']):
        month = _beets.get('month')
        day = _beets.get('day')
        published_in = LDateTime(rpq, year=year, month=month, day=day)
        rpq.rassert(
            f"rdf_assert('{release_uri}', '{XCAT.published_during}', "
            f"'{published_in}')"
        )

    add_genres(rpq, release_uri, _beets)

    if label_uri:
        label_lbl = xsd_type(_beets['label'], 'string')
        rpq.rassert(*[
            f"rdf_assert('{label_uri}', '{RDF.type}', '{XCAT.MusicLabel}')",
            f"rdf_assert('{label_uri}', '{XCAT.name}', {label_lbl})",
            f"rdf_assert('{label_uri}', '{XCAT.published}', '{release_uri}')",
            f"rdf_assert('{release_uri}', '{XCAT.publisher}', '{label_uri}')",
        ])

        if _beets['catalognum']:
            cat_num = xsd_type(_beets['catalognum'], 'string')
            rpq.rassert(f"rdf_assert('{release_uri}', '{XCAT.catalog_num}',"
                        f" {cat_num})")


def track_from_beets(rpq, beets_lib, data):
    # check if track is already in db

    global release_dict
    file_URN = B3[data['_hash']]
    file_path = xsd_type(data['path'], 'string')
    encoding = xsd_type(data['format'], 'string')
    track_num = data['track']
    mtime = datetime.fromtimestamp(data['_mtime'])

    ## Add the file
    rpq.rassert(*[
        f"rdf_assert('{file_URN}', '{RDF.type}', '{XCAT.AudioFile}')",
        f"rdf_assert('{file_URN}', '{XCAT.encoding}', {encoding})",
        f"rdf_assert('{file_URN}', '{XCAT.path}', {file_path})",
        f"rdf_assert('{file_URN}', '{XCAT.hash}',"
        f" {xsd_type(data['_hash'], 'string')})"
    ])

    ## Define resources URI's depending on data source
    source = data.get('data_source')
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
            artist = rpq.simple_query(
                    f"rdf(X, '{RDF.type}', '{XCAT.Artist}'), "
                    f"rdf(X, '{XCAT.name}', {artist_lbl})") or rpq.new_bnode()
            if isinstance(artist, list):
                artist = rdf_unify(rpq, artist)
        release = data['mb_albumid']
        track = data['mb_trackid']
    elif data_source is None:
        # Something else...
        pass

    ## Add the mtime
    mtime_term = LDateTime(rpq, year=mtime.year, month=mtime.month,
                           day=mtime.day, hour=mtime.hour)

    rpq.rassert(*[
        f"rdf_assert('{artist}', '{RDF.type}', '{XCAT.Artist}')",
        f"rdf_assert('{artist}', '{XCAT.name}', {artist_lbl})",
        f"rdf_assert('{track}', '{RDF.type}', '{XCAT.Recording}')",
        f"rdf_assert('{track}', '{XCAT.file}', '{file_URN}')",
        f"rdf_assert('{file_URN}', '{XCAT.recording}', '{track}')",
        f"rdf_assert('{track}', '{XCAT.title}', {track_lbl})",
        f"rdf_assert('{track}', '{XCAT.added_during}', '{mtime_term}')",
        f"rdf_assert('{track}', '{XCAT.released_on}', '{release}')",
        f"rdf_assert('{track}', '{XCAT.maker}', '{artist}')",
        f"rdf_assert('{artist}', '{XCAT.made}', '{track}')",
    ])

    ## Add the genres
    add_genres(rpq, track, data)

    ## Add the release
    if (not rpq.boolquery(f"rdf('{release}', '{RDF.type}', '{XCAT.Release}')")
            and data['album_id']):
        beetz_release = beets_lib.get_album(data['album_id'])
        release_from_beets(rpq, release, source, beetz_release)

    tracklist = release_dict.get(release, [])
    tracklist.append((data['track'], track))
    release_dict[release] = tracklist

    ## Add the tracklist if it's full
    if len(release_dict[release]) == data['tracktotal']:
        # add tracklist to release
        # vv maybe get rid of this line? vv
        tracklist = release_dict[release]
        tracklist.sort()
        for idx, (track_num, track) in enumerate(tracklist):
            if idx + 1 != track_num:
                log.warning(f"Tracklist Misaligned\nTrack {idx + 1}"
                            f" has track num {track_num}: {track}")
        # extract list of only second value in list of tuples
        sorted_tracks = list(tuple(zip(*tracklist))[1])
        tlist_node = TrackList(rpq, sorted_tracks)
        rpq.rassert(
            f"rdf_assert('{release}', '{XCAT.tracklist}', '{tlist_node}')"
        )
        del release_dict[release]

    rpq.rassert(f"rdf_assert('{track}', '{XCAT.released_on}', '{release}')")

    return file_URN

# f"rdf_assert('{}', '{}', '{}')"
def add_genres(rpq, subj, beets_dict):
    genres, styles, unmatched = discogs.genre_styles(get_genre_vals(beets_dict),
                                                     get_style_vals(beets_dict))
    assertion_list = []
    for genre_name, genre_uri in genres:
        genre_name = xsd_type(genre_name, 'string')
        assertion_list += [
            f"rdf_assert('{genre_uri}', '{RDF.type}', '{XCAT.Genre}')",
            f"rdf_assert('{genre_uri}', '{XCAT.name}', {genre_name})",
            f"rdf_assert('{subj}', '{XCAT.genre}', '{genre_uri}')"
            ]
    for (style_name, style_uri), (genre_name, genre_uri) in styles:
        genre_name = xsd_type(genre_name, 'string')
        style_name = xsd_type(style_name, 'string')
        assertion_list += [
            f"rdf_assert('{style_uri}', '{RDF.type}', '{XCAT.Style}')",
            f"rdf_assert('{style_uri}', '{XCAT.name}', {style_name})",
            f"rdf_assert('{subj}', '{XCAT.style}', '{style_uri}')",
            f"rdf_assert('{style_uri}', '{XCAT.parent_genre}', '{genre_uri}')",
            f"rdf_assert('{genre_uri}', '{XCAT.genre_style}', '{style_uri}')"
            ]
    if assertion_list:
        rpq.rassert(*assertion_list)
    for unmatched_name in unmatched:
        style_name = xsd_type(unmatched_name, 'string')
        style_uri = rpq.simple_query(
                f"rdf(X, '{RDF.type}', '{XCAT.Style}')",
                f"rdf(X, '{XCAT.name}', {style_name})") or rpq.new_bnode()
        if isinstance(style_uri, list):
            style_uri = rdf_unify(rpq, style_uri)
        rpq.rassert(*[
            f"rdf_assert('{style_uri}', '{RDF.type}', '{XCAT.Style}')",
            f"rdf_assert('{style_uri}', '{XCAT.name}', {style_name})",
            f"rdf_assert('{subj}', '{XCAT.style}', '{style_uri}')",
        ])


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
            # check if subdir is empty before crashing maybe
            if not (subdir_dirpath := dirpaths.get(subdir_path)):
                raise Exception(f"{subdir_path}\n not encountered"
                                f"before\n{dirpath}")
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
            dir_hash = hashlist_hash(entry_hashes + subdir_hashes)
            dirpaths[dirpath] = (in_db, not_in_db, subdir_hashes, dir_hash)

    return dirpaths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='folder(s) to scan', nargs="+")
    parser.add_argument('--beets-library', '-b',
                        help='beets sqlite db to reference')
    parser.add_argument('--pickle-cache', '-p', action='store_true',
                        help='use a cache of the filedata from the last run')
    args = parser.parse_args()
    data_location = '../data/'
    beets_path = args.beets_library or os.path.join(data_location,
                                                    'ext/music.db')
    beets_lib = beets_init(beets_path)
    cache_file = os.path.join(data_location, 'cache/loaded_dir.pickle')

    log = logging.getLogger('beets_to_rdf')
    log.setLevel(logging.DEBUG)
    log_handler = logging.StreamHandler(stdout)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(LogFormatter())
    log.addHandler(log_handler)

    log.info(f"\n\t\tBeets to RDF {datetime.now()}")
    # initialize prolog store
    rpq = RPQ('init.pl', write_mode=True)#, log=log)

    # load files from directory
    if not args.pickle_cache:
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
        dirpaths = {}
        for path in args.input:
            path = os.path.abspath(path)
            dirpaths.update(rec_load_dir(path, beets_lib))

    # cache directory data
    pickle.dump(dirpaths, open(cache_file, 'wb+'))

    # add music data from directory to prolog rdf store
    for idx, (dir, (in_db, not_in_db, subdir_hashes, dir_hash)
              ) in enumerate(dirpaths.items()):
        dir_entries = []
        #log.debug(f"{dir}: {len(in_db)} in beets, {len(not_in_db)} not in beets")
        #if not idx % 10:
        #    log.debug(f"importing directory {idx} of {len(dirpaths)}")
        for entry in in_db.values():
            dir_entries += [track_from_beets(rpq, beets_lib, entry)]
        for entry in not_in_db.values():
            dir_entries += [nometa_file_node(rpq, entry)]
        entries_to_dir(rpq, dir_hash, dir, dir_entries)#, subdir_hashes)
    log.warning("Incomplete tracklists:")
    for release, item in release_dict.items():
        log.warning(':\n'.join([str(release), pformat(item)]))
