#!/usr/bin/env python3

from inspect import getmembers
import urwid as ur
import musicpd
import time

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

    def __init__(self, column_func=format_track, refresh=5,
                 screen_refresh=1, log=None):
        self.log = log
        self.refresh = refresh
        self.screen_refresh = screen_refresh

        self.client.iterate = True

        col_headings = list(column_func({}).keys())
        col_headings.remove('key')
        col_headings.insert(0, ' ')
        self.header = ur.Columns([ur.Text(key) for key in col_headings],
                                 dividechars=1)
        col_widths = [len(heading) for heading in col_headings]

        self.footer = CurrentSong(self.client, log)
        self.body = Queue(self.client, column_func, col_widths, log)
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
        #if self.log:
        #    self.log.debug(self.body.playing)
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
        for idx, (widget, _) in enumerate(self.header.contents):
            self.header.contents[idx] = widget, ur.Columns.options(
                    width_amount=self.body.col_widths[idx])


    def toggle_play(self):
        if self.client.status().get('state') != 'play':
            self.client.play()
        else:
            self.client.pause()


    def play_selected(self):
        idx = int(self.body.focus.key)
        if self.log: self.log.debug(f"playing {idx}")
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
    def __init__(self, client, log=None):
        self.log = log
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
        if self.log: self.log.debug(status)
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
        #if self.log: self.log.debug((self.current_sec, self.total_sec, self.start_time))
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
    def __init__(self, client, column_func, header_widths, log=None):
        self.column_func = column_func
        self.log = log
        self.client = client
        self.walker = ur.SimpleFocusListWalker([])
        self.header_widths = header_widths
        self._playing = None
        self.paused = False
        super().__init__(self.walker)


    @property
    def playing(self):
        return self._playing


    @playing.setter
    def playing(self, idx):
        #if self.log: self.log.debug((idx, self._playing))
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
        self.col_widths = self.header_widths
        self.walker.clear()
        for song in self.client.playlistinfo():
            #if self.log: self.log.debug(song)
            item = ListItem(self.log, **self.column_func(song))
            self.col_widths = [max(col, item.min_widths[i])
                               for i, col in enumerate(self.col_widths)]
            self.walker.append(item)
        if self.focus and len(self.walker) > focused_idx:
            self.focus_position = focused_idx
        self.reflow()


    def reflow(self):
        #if self.log: self.log.debug(self.col_widths)
        for listitem in self.walker:
            for i, w in enumerate(self.col_widths):
                listitem.contents[i] = (listitem.contents[i][0],
                                        ur.Columns.options(width_amount=w))


class ListItem(ur.Columns):
    NOT_PLAYING = ur.wimp.SelectableIcon(' ', 0)
    PLAYING = {False: ur.wimp.SelectableIcon('\u23F5', 0),
               True: ur.wimp.SelectableIcon('\u23F8', 0)}

    def __init__(self, log=None, key=None, **kwargs):
        widget_list = [self.NOT_PLAYING]
        self.log = log
        self.key = key
        self._playing = False
        self.min_widths = [1]
        self.paused = False
        for arg, val in kwargs.items():
            #if log: log.debug(f'{arg}: {val}')
            self.min_widths += [len(val)]
            widget_list.append(ur.Text(val))
        #if log: log.debug(self.min_widths)
        super().__init__(widget_list, dividechars=1)


    @property
    def playing(self):
        return self._playing


    @playing.setter
    def playing(self, value):
        #if self.log: self.log.debug((self._playing, value))
        if value:
            self.contents[0] = (self.PLAYING[self.paused], self.contents[0][1])
        else:
            self.contents[0] = (self.NOT_PLAYING, self.contents[0][1])
        self._playing = bool(value)


