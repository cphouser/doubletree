#!/usr/bin/env python3

import os
import re
import sys
import logging as log
from time import sleep
from datetime import datetime
from pprint import pprint, pformat

import mutagen
from sqlitedict import SqliteDict
from conf_file import Config

class TagData:
    DATA_ROOTS = Config["base_paths"]

    TAG_FIELDS = {
        "artist": [
            "TPE1", "TPE2", #mutagen.mp3.MPEGInfo
            "©ART", #:com.apple.iTunes:
            "artist", #mutagen.oggvorbis.OggVorbisInfo
            "Author" #mutagen.asf.ASFInfo
        ], "release": [
            "TALB", #mutagen.mp3.MPEGInfo
            "©alb", #:com.apple.iTunes:
            "album",  #mutagen.oggvorbis.OggVorbisInfo
            "WM/AlbumTitle", #mutagen.asf.ASFInfo
        ], "title": [
            "TIT2", #mutagen.mp3.MPEGInfo
            "©nam", #:com.apple.iTunes:
            "title", #mutagen.oggvorbis.OggVorbisInfo
            "Title", #mutagen.asf.ASFInfo
        ], "track": [
            "TRCK", #mutagen.mp3.MPEGInfo
            "trkn",
            "tracknumber",  #mutagen.oggvorbis.OggVorbisInfo
            "WM/TrackNumber", #mutagen.asf.ASFInfo
        ], "date": [
            "TDRC",#mutagen.mp3.MPEGInfo
            "date"  #mutagen.oggvorbis.OggVorbisInfo
        ], "genre": [
            "TCON", #mutagen.mp3.MPEGInfo
            "genre" #mutagen.oggvorbis.OggVorbisInfo
        ]
    }

    ENCODINGS = {
        ('mutagen.mp3', 'MPEGInfo'): "MP3",
        ('mutagen.flac', 'StreamInfo'): "FLAC",
        ('mutagen.mp4', 'MP4Info'): "MP4"
    }

    def __init__(self, refind=False, stdout=False):
        self._out = stdout
        self.artist_paths = SqliteDict('../data/mutagen_artists.sqlite')
        self.release_paths = SqliteDict('../data/mutagen_releases.sqlite')
        if (not self.release_paths and not self.artist_paths) or refind:
            self.artist_paths.clear()
            self.release_paths.clear()
            self._find_tagged()
            self.artist_paths.commit()
            self.release_paths.commit()
        self._print(f"artists: {len(self.artist_paths)}, "
                    f"releases: {len(self.release_paths)}")


    def _print(self, *args, **kwargs):
        if self._out:
            print(*args, **kwargs)


    def _get_tag(self, mutagen_data, tag):
        results = []
        for field in self.TAG_FIELDS[tag]:
            try:
                if field in mutagen_data.tags:
                    result = mutagen_data[field]
                    if isinstance(result, list):
                        results.extend([str(res) for res in result])
                    else:
                        results.append(str(result))
            except ValueError:
                pass
        return results if results else None


    def _find_tagged(self):
        missing_data = {}
        for base_path in self.DATA_ROOTS:
            for dirpath, _, filenames in os.walk(base_path):
                self._print(" ", datetime.now(), end='\r')
                for filename in filenames:
                    fullpath = os.path.join(dirpath, filename)
                    try:
                        if (mutagen_data := mutagen.File(fullpath)):
                            artists = self._get_tag(mutagen_data, "artist") or []
                            releases = self._get_tag(mutagen_data, "release") or []
                            if not releases and not artists:
                                missing_data[fullpath] = mutagen_data
                            for artist in artists:
                                artist = self._clean(artist)
                                artist_paths = self.artist_paths.get(artist, [])
                                artist_paths.append(fullpath)
                                self.artist_paths[artist] = artist_paths
                            for release in releases:
                                release = self._clean(release)
                                release_paths = self.release_paths.get(release, [])
                                release_paths.append(fullpath)
                                self.release_paths[release] = release_paths
                    except mutagen.MutagenError as e:
                        self._print(e, fullpath)
        #something something missing data?
        self._print('\r\033[K', end="")


    def _match(self, artist=None, release=None):
        matches = set()
        if artist:
            log.debug(self._clean(artist))
            matched = self.artist_paths.get(self._clean(artist), [])
            matches = matches.union(set(matched))
            log.debug((len(matched), "matched"))
        if release:
            log.debug(self._clean(release))
            matched = self.release_paths.get(self._clean(release), [])
            matches = matches.union(set(matched))
            log.debug((len(matched), "matched"))
        self.matches = matches


    @staticmethod
    def _clean(string):
        return re.sub('[^\w]', '', string).lower()


    def match_data(self, artist=None, release=None):
        log.debug((artist, release))
        self._match(artist, release)
        match_data = {}
        for match in self.matches:
            match_data[match] = self.match_path(match)
        return match_data


    def match_path(self, path):
        tag_data = {}
        mutagen_data = mutagen.File(path)
        for field in self.TAG_FIELDS:
            field_results = self._get_tag(mutagen_data, field)
            if not field_results:
                self._print(field)
                self._print(mutagen_data.pprint())
            tag_data[field] = field_results

        if (encoding := self.ENCODINGS.get(
                (mutagen_data.info.__module__,
                 mutagen_data.info.__class__.__name__))):
            tag_data["encoding"] = encoding
        else:
            log.debug(mutagen_data.pprint())
            log.debug(mutagen_data.info.__module__)
            log.debug(mutagen_data.info.__class__.__name__)
        return tag_data


def rdf_find(match):
    print(match[0])
    return match[1].pprint()


if __name__ == "__main__":
    from pprint import pprint
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--clear', '-c', help='clear mutagen cache',
                        action="store_true")
    parser.add_argument('--release', '-r', help='Release to match')
    parser.add_argument('--artist', '-a', help='Artist to match')
    args = parser.parse_args()

    tagdata = TagData(args.clear, True)
    if args.release or args.artist:
        res = tagdata.match_data(args.artist, args.release)
        for path, data in sorted(list(res.items()), key=lambda x: x[1]["track"]):
            pprint(data)
            print(path)
    #pprint(sorted(matches, key=lambda x: str(x[1].get("TRCK", "null"))))
