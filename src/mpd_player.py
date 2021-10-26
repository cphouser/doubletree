#!/usr/bin/env python3

import logging as log
from inspect import getmembers
import urwid as ur
import musicpd
import time
from table_util import balance_columns

def format_track(dictlike):
    return {
        'key': dictlike.get('id', ""),
        'track': dictlike.get('title', ""),
        'artist': dictlike.get('artist', ""),
        'album': dictlike.get('album', ""),
        'year': dictlike.get('date', "")
    }


class MpdPlayer(ur.Frame):
    client = musicpd.MPDClient()

    def __init__(self, column_func=format_track, refresh=5, screen_refresh=1):
        self.refresh = refresh
        self.screen_refresh = screen_refresh

        self.client.iterate = True

        col_headings = list(column_func({}).keys())
        col_headings.remove('key')
        col_headings.insert(0, ' ') # FIXME create list with this
        self.header = ur.Columns([ur.Text(key, wrap="ellipsis")
                                  for key in col_headings], dividechars=1)
        col_widths = [len(heading) for heading in col_headings[1:]]

        self.footer = CurrentSong(self.client)
        self.body = Queue(self.client, column_func, col_widths,
                          self.size_heading)
        self.reload()

        super().__init__(self.body, self.header, self.footer)


    def keypress(self, size, key):
        if not self.body.keypress(size, key):
            return
        if (operation := OPERATION_MAP.get(key)):
            self.client.connect(host="localhost")
            operation(self)
            self.client.disconnect()
            self.reload()
        else:
            return key


    def reload(self):
        self.client.connect(host="localhost")
        self.body.load_queue()
        paused = self.client.status().get('state') == 'pause'
        if (current := self.client.currentsong()):
            current_idx = int(current['pos'])
        else:
            current_idx = None
        self.body.paused = paused
        self.body.playing = current_idx
        self.footer.load_progress()
        self.footer.load_bar()
        self.footer.update_bar()
        self.client.disconnect()


    def size_heading(self, col_widths):
        for idx, (widget, _) in enumerate(self.header.contents[1:]):
            self.header.contents[idx+1] = widget, ur.Columns.options(
                    width_amount=col_widths[idx])


    def toggle_play(self):
        if self.client.status().get('state') != 'play':
            self.client.play()
        else:
            self.client.pause()


    def play_selected(self):
        idx = int(self.body.focus.key)
        log.debug(f"playing {idx}")
        self.client.playid(idx)


    def deleteid(self):
        idx = int(self.body.focus.key)
        self.client.deleteid(idx)


    def reload_screen(self):
        if self.footer.update_bar():
            self.reload()


OPERATION_MAP = {
    ' ': MpdPlayer.toggle_play,
    'enter': MpdPlayer.play_selected,
    '>': lambda player: player.client.next(),
    '<': lambda player: player.client.previous(),
    'D': lambda player: player.client.clear(),
    'd': MpdPlayer.deleteid,
    'r': lambda player: None
}

class CurrentSong(ur.ProgressBar):
    def __init__(self, client):
        self.client = client
        self.current_sec = 0
        self.total_sec = 1
        self.start_time = 0
        self.playing = False
        self.load_bar()


    def load_bar(self):
        super().__init__("body", "focus", current=self.current_sec,
                         done=self.total_sec)


    def load_progress(self):
        status = self.client.status()
        log.debug(status)
        self.playing = status['state'] == 'play'
        if status.get('time'):
            self.current_sec, self.total_sec = [
                    int(i) for i in status['time'].split(':')]
            self.start_time = int(time.time()) - self.current_sec


    def update_bar(self):
        if self.playing:
            self.current_sec = int(time.time()) - self.start_time
            if self.current_sec > self.total_sec:
                return True
            else:
                self.set_completion(self.current_sec)
        #log.debug((self.current_sec, self.total_sec, self.start_time))
        return False

    def get_text(self):
        return f"{sec_format(self.current_sec)} / {sec_format(self.total_sec)}"


def sec_format(total_seconds):
    text = []
    for i in range(2):
        text += [str(total_seconds % 60).rjust(2, '0')]
        total_seconds //= 60
        if not total_seconds:
            break
    return ":".join(reversed(text))


class Queue(ur.ListBox):
    def __init__(self, client, column_func, header_widths, resize_func):
        self.column_func = column_func
        self.client = client
        self.walker = ur.SimpleFocusListWalker([])
        self.header_widths = header_widths
        self.resize_func = resize_func
        self._playing = None
        self.paused = False
        self.balanced = True # whether columns have been spaced
        self.col_widths = None
        super().__init__(self.walker)


    @property
    def playing(self):
        return self._playing


    @playing.setter
    def playing(self, idx):
        #log.debug((idx, self._playing))
        if isinstance(self._playing, int) and self.walker:
            self.walker[self._playing].playing = False
        if idx is None:
            self._playing = None
        elif idx in range(len(self.walker)):
            self.walker[idx].paused = self.paused
            self.walker[idx].playing = True
            self._playing = idx


    def load_queue(self):
        focused_idx = self.focus_position if self.focus else 0
        self.walker.clear()
        for song in self.client.playlistinfo():
            item = ListItem(**self.column_func(song))
            self.walker.append(item)
        if self.focus and len(self.walker) > focused_idx:
            self.focus_position = focused_idx
        self.balanced = False


    def reflow(self, table_width):
        widths = [[width] for width in self.header_widths]
        for listitem in self.walker:
            for i, w in enumerate(listitem.min_widths):
                widths[i].append(w)
        [width.sort(reverse=True) for width in widths]
        col_widths = [w - 1 for w in balance_columns(widths, table_width)]
        for listitem in self.walker:
            for i, w in enumerate(col_widths):
                listitem.contents[i+1] = (listitem.contents[i+1][0],
                                          ur.Columns.options(width_amount=w))
        self.resize_func(col_widths)
        balanced = True


    def render(self, size, focus=False ):
        if not self.balanced:
            cols, _ = size
            self.reflow(cols)
        return super().render(size, focus)


class ListItem(ur.Columns):
    NOT_PLAYING = ur.wimp.SelectableIcon(' ', 0)
    PLAYING = {False: ur.wimp.SelectableIcon('\u23F5', 0),
               True: ur.wimp.SelectableIcon('\u23F8', 0)}

    def __init__(self, key=None, **kwargs):
        widget_list = [self.NOT_PLAYING]
        self.key = key
        self._playing = False
        self.min_widths = []
        self.paused = False
        for arg, val in kwargs.items():
            #log.debug(f'{arg}: {val}')
            self.min_widths += [len(val) + 1]
            widget_list.append(ur.Text(val, wrap="ellipsis"))
        #log.debug(self.min_widths)
        super().__init__(widget_list, dividechars=1)


    @property
    def playing(self):
        return self._playing


    @playing.setter
    def playing(self, value):
        #log.debug((self._playing, value))
        if value:
            self.contents[0] = (self.PLAYING[self.paused], self.contents[0][1])
        else:
            self.contents[0] = (self.NOT_PLAYING, self.contents[0][1])
        self._playing = bool(value)


