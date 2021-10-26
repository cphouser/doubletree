#!/usr/bin/env python3
# BSD-0 LICENSE
# Calvin Houser cphouser@gmail.com

from pprint import pformat
import logging as log

def trim_col(widths, max_width, prev_trim=0):
    """given a reverse-sorted list of child widths and a max width, return the
    number of elements that must be trimmed and min(max_width, max(widths))"""
    ret_width = min(max_width, widths[prev_trim])
    trimmed = prev_trim
    for width in widths[prev_trim:]:
        if width <= ret_width:
            break
        trimmed += 1
    return trimmed, ret_width


def trim(col_widths, fill_width, minimized=None, widths=None, num_cut=None,
         restrict=False):
    minimized = minimized or set()
    widths = widths or []
    num_cut = num_cut or []
    remaining_cols = len(col_widths) - len(minimized)
    if not remaining_cols:
        return minimized, widths, num_cut
    for idx, width in enumerate(widths):
        if idx in minimized:
            fill_width -= width

    # biggest col if all other cols were 2 cells wide
    max_col_width = fill_width - (remaining_cols - 1) * 2
    even_col_width = fill_width / remaining_cols
    new_widths = []
    new_num_cut = []
    last_trim = all([num_cut[i] == max(num_cut) for i in range(len(num_cut))
                     if i not in minimized])
    for idx, col_rows in enumerate(col_widths):
        if idx in minimized and idx < len(widths):
            new_widths.append(widths[idx])
            new_num_cut.append(num_cut[idx])
        else:
            if restrict and last_trim and num_cut[idx] == max(num_cut):
                trimmed, width = trim_col(col_rows, int(even_col_width))
    #            log.debug(f"last col ({idx}): {trimmed} {width}")
            else:
                trimmed, width = trim_col(col_rows, max_col_width)
                if restrict and (width > widths[idx] or trimmed < num_cut[idx]):
                    width = widths[idx]
                    trimmed = num_cut[idx]
            new_widths.append(width)
            new_num_cut.append(trimmed)
            if width < even_col_width:
                minimized.add(idx)
    #log.debug(f"{pformat(new_widths, width=160)}{sum(new_widths)}~{fill_width}")
    #log.debug(pformat(new_num_cut, width=160))
    #log.debug(pformat(minimized, width=160))
    return minimized, new_widths, new_num_cut


def balance_columns(col_widths, fill_width):
    minimized, widths, num_cut = trim(col_widths, fill_width)
    last_added = 0
    restrict = False
    stage_two = False
    for i in range(100):
        log.debug(f"{widths},\t {sum(widths)}~{fill_width}, restrict: "
                  f"{restrict},\tstage_2: {stage_two},\tminimized: {minimized}")
        if sum(widths) == fill_width:
            return widths
        elif sum(widths) < fill_width:
            #log.debug(f"\n{i} PAD~~~")
            if not last_added:
                last_added = len(widths) - 1
                pad_width = ((fill_width - sum(widths)) // len(widths)) or 1
            else:
                last_added -= 1
            #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
            #log.debug(f"  ~IDX {last_added}")
            widths[last_added] += pad_width
        elif not stage_two:
            #log.debug(f"\n{i} TRIM-1~~~")
            #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
            old_minimized_count = len(minimized)
            minimized, new_widths, num_cut = trim(col_widths, fill_width,
                                                  minimized, widths, num_cut,
                                                  restrict=restrict)
            if new_widths == widths and old_minimized_count == len(minimized):
                #log.debug("  ~DONE")
                stage_two = True
                restrict = True
            else:
                widths = new_widths
        else:
            #log.debug(f"\n{i} TRIM-2~~~")
            min_trim = min([trim_num for idx, trim_num in enumerate(num_cut)
                            if idx not in minimized]) + 1
            for idx, col_rows in enumerate(col_widths):
                #log.debug(f"min_trim: {min_trim}, {idx} trim: {num_cut[idx]}")
                if idx not in minimized and num_cut[idx] < min_trim:
                    trimmed, width = trim_col(col_rows, widths[idx] - 1,
                                              prev_trim=min_trim)
                    #log.debug(f"{idx}: {min_trim}, {trimmed}, {width}")
                    if trimmed - min_trim > 1:
                        # keep the original width for now but store how many we
                        # would trim if this changes.
                        width = widths[idx]
                    num_cut[idx] = trimmed
                    widths[idx] = width
                    # might be quicker to stay in stage two if we kept the orig
                    # width above.
                    stage_two = False
                    #log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
                    #log.debug(pformat(num_cut, width=160))
                    #log.debug(pformat(minimized, width=160))
                    break
    log.debug(f"{pformat(widths, width=160)} {sum(widths)} {fill_width}")
