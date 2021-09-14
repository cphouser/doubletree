#!/home/xeroxcat/venvs/doubletree/bin/python
#
import time
from datetime import datetime

import musicpd
from pyswip.prolog import Prolog

from rdf_util.pl import LDateTime, xsd_type, query
from rdf_util.namespaces import XCAT

def mpd_monitor(client, client_kwargs):
    status = {}
    song = None
    end_ts = None
    try:
        client.connect(**client_kwargs)
        client.idle('player')
        status = client.status()
        currentsong = client.currentsong()
        client.disconnect()
    except Exception as e:
        print("Couldn't query MPD:", e)
    if status.get('state') == "play":
        song = currentsong['file']
        end_ts = time.time() + float(status['duration'])
    return end_ts, song


def save_play(playing):
    ts = datetime.now()
    now = LDateTime(pl, year=ts.year, month=ts.month, day=ts.day, hour=ts.hour,
                    minute=ts.minute)
    X = None
    res = query(pl, write=True, query=(
        ('rdf', ('_v:File', XCAT.path, xsd_type(playing, 'string'))),
        ('rdf_assert', ('_v:File', XCAT.accessed_during, now))
    ))


if __name__ == "__main__":
    client = musicpd.MPDClient()
    client_kwargs = dict(host='/run/mpd/socket')
    pl = Prolog()
    pl.consult('init.pl')
    playing = None
    end_ts = None
    while True:
        new_end_ts, new_playing = mpd_monitor(client, client_kwargs)
        if new_playing:
            if playing == new_playing:
                if time.time() > end_ts:
                    save_play(playing)
            else:
                save_play(new_playing)
            playing, end_ts = new_playing, new_end_ts
        time.sleep(1)