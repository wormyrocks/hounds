"""Generate lighting for the first 60 s (beats 0-192 on the Tempora grid) of hounds.

Usage: python3 gen_lights.py MAP_DIR
Replaces every basic event before END in Expert.lightshow.dat; events after END are kept.

Beats here are Tempora-grid beats (~192 BPM over this section: 6 beats per bar, bars start
at beats 1, 7, 13, ...). Notes are expected to be snapped to the grid already (retime.py --snap).
"""
import json, sys, os

MAP = sys.argv[1]
END = 192.0

# Default environment event types
BACK, RING, LEFT, RIGHT, CENTER, SPIN, ZOOM, LSPD, RSPD = 0, 1, 2, 3, 4, 8, 9, 12, 13
LIGHTS = (BACK, RING, LEFT, RIGHT, CENTER)
# values: off / on / flash / fade / transition for blue, red, white
OFF = 0
B = dict(on=1, fl=2, fd=3, tr=4)
R = dict(on=5, fl=6, fd=7, tr=8)
W = dict(on=9, fl=10, fd=11, tr=12)
COL = {0: R, 1: B}  # note color -> palette

events = []


def ev(b, t, v, f=1.0):
    events.append((round(b, 3), t, v, round(f, 3)))


def all_lights(b, v, f=1.0, which=LIGHTS):
    for t in which:
        ev(b, t, v, f)


def speed(b, l, r=None):
    ev(b, LSPD, l)
    ev(b, RSPD, l if r is None else r)


# ---- load notes, grouped by time ----
bm = json.load(open(os.path.join(MAP, 'ExpertStandard.dat')))
nd = bm['colorNotesData']
groups = {}
for n in bm['colorNotes']:
    if n['b'] >= END + 0.75:
        continue
    groups.setdefault(round(n['b'], 3), []).append(nd[n['i']])
NOTE_TIMES = sorted(groups)


def notes_in(a, b):
    return [(t, groups[t]) for t in NOTE_TIMES if a <= t < b]


def is_downbeat(t):  # bars start at 1, 7, 13, ...
    return abs((t - 1) / 6 - round((t - 1) / 6)) < 1e-3


def riff(a, b, prim, alt, f=1.0, center_doubles=True):
    """Note-driven section: left-hand notes pulse left lasers, right-hand notes pulse right lasers,
    bar downbeats hit the back lasers + spin the rings, double hits pop the center lights."""
    for i, (t, ns) in enumerate(notes_in(a, b)):
        cs = {d['c'] for d in ns}
        if 0 in cs:
            ev(t, LEFT, R['fd'], f)
        if 1 in cs:
            ev(t, RIGHT, B['fd'], f)
        if is_downbeat(t):
            ev(t, BACK, prim['fd'], f)
            ev(t, SPIN, 0)
        elif center_doubles and len(cs) == 2:
            ev(t, CENTER, alt['fd'], 0.8 * f)


def column_chase(a, b, f=1.0):
    """Fast runs: light follows the note's column across the stage (left->right)."""
    stage = {0: LEFT, 1: BACK, 2: RING, 3: RIGHT}
    for t, ns in notes_in(a, b):
        for d in ns:
            ev(t, stage[d['x']], COL[d['c']]['fd'], f)


def big_hit(t, col, spin=True, zoom=True, spd=None):
    ev(t, BACK, col['fl'], 1.2)
    ev(t, RING, col['fd'], 1.0)
    ev(t, LEFT, col['fd'], 1.0)
    ev(t, RIGHT, col['fd'], 1.0)
    ev(t, CENTER, W['fd'], 1.2)
    if spin:
        ev(t, SPIN, 0)
    if zoom:
        ev(t, ZOOM, 0)
    if spd is not None:
        speed(t, spd)


# ======================================================================
# 0 - 7  silence: blackout
all_lights(0, OFF)
speed(0, 0)

# 7  opening chord (loudest moment of the intro), rings out until 19
big_hit(7, R, spd=2)
ev(7, BACK, R['fl'], 1.3)
ev(17.75, BACK, R['tr'], 0.12)      # slow fade of the back lasers while the chord rings
ev(13, SPIN, 0)

# 19 - 37  quiet single-note riff; lasers answer each note, the stage swells toward the band entry
speed(19, 1)
for t, ns in notes_in(18, 36.9):
    k = (t - 19) / 18                # 0 -> 1 across the section
    lvl = 0.45 + 0.45 * k
    for d in ns:
        ev(t, LEFT if d['c'] == 0 else RIGHT, COL[d['c']]['fd'], lvl)
ev(25, RING, R['on'], 0.0)
ev(36.75, RING, R['tr'], 0.5)
ev(31, CENTER, R['on'], 0.0)
ev(36.75, CENTER, R['tr'], 0.6)
ev(34, SPIN, 0)

# 37 - 41.5  band enters: pickup ripples across the ring, then the lasers
ev(37, RING, R['fl'])
ev(37.5, RING, B['fl'])
ev(38, RING, R['fd'])
ev(38, CENTER, R['fd'], 0.6)
ev(38.5, BACK, B['fd'])
ev(39, LEFT, B['fd'])
ev(39.5, RIGHT, B['fd'])
ev(39.5, CENTER, B['fd'], 0.8)
ev(41, ZOOM, 0)

# 41.5  big hit, main riff starts
big_hit(41.5, R, spd=3)
ev(43, RING, R['on'], 0.25)          # ambient glow under the riff
riff(42.3, 54.9, R, B)

# 55 - 61  stop + three-step build into the big hit
ev(55, BACK, W['fd'])
ev(55, CENTER, R['fd'])
ev(55, RING, R['fd'], 0.6)           # ambient fades out -> darkness before the build
ev(55, LEFT, OFF)
ev(55, RIGHT, OFF)
speed(55, 0)
ev(58, LEFT, R['fl'], 0.7)
speed(58, 3, 0)
ev(59, RIGHT, B['fl'], 0.85)
speed(59, 3, 3)
ev(60, BACK, R['fl'], 1.0)
ev(60, RING, R['fl'], 0.6)
speed(60, 5)
big_hit(61, W, spd=4)
ev(61, RING, R['fl'], 1.0)

# 61 - 73  riff, blue variation
ev(64, RING, B['tr'], 0.25)
riff(64.3, 72.9, B, R)
big_hit(73, B, spd=2)

# 73 - 97  sparse passage: slow colour drift, accents on note pairs
ev(74.25, BACK, B['tr'], 0.35)
ev(85, BACK, R['tr'], 0.35)
ev(96.5, BACK, R['tr'], 0.6)
ev(76, RING, B['tr'], 0.2)
speed(79, 1)
for t, ns in notes_in(73.5, 96.9):
    cs = {d['c'] for d in ns}
    for c in cs:
        ev(t, LEFT if c == 0 else RIGHT, COL[c]['fd'], 0.8)
    if len(cs) == 2:
        ev(t, CENTER, B['fd'], 0.6)
ev(85, SPIN, 0)
ev(91, SPIN, 0)

# 97 - 115  riff returns; arpeggiated singles 108.5-115 chase by column
big_hit(97, R, spd=3)
ev(98.5, RING, R['on'], 0.25)
riff(97.5, 108.6, R, B)
ev(101.5, CENTER, W['fd'], 0.9)      # strong snare accent in the audio
ev(108.5, RING, B['tr'], 0.3)
column_chase(108.6, 114.9)
ev(109, ZOOM, 0)

# 115 - 127  riff
ev(115, RING, R['tr'], 0.25)
speed(115, 4)
riff(114.9, 126.9, R, B)
ev(121, ZOOM, 0)

# 127 - 133  walls: the side of the wall lights up
ev(127, LEFT, W['fl'], 1.0)
ev(127, RIGHT, OFF)
ev(127, BACK, R['fd'])
ev(127, LSPD, 7)
ev(128.5, LEFT, R['fd'], 0.8)
ev(128.5, CENTER, R['fd'], 0.6)
ev(130, RIGHT, W['fl'], 1.0)
ev(130, LEFT, OFF)
ev(130, BACK, B['fd'])
ev(130, RSPD, 7)
ev(131.5, RIGHT, B['fd'], 0.8)
ev(131.5, CENTER, B['fd'], 0.6)
speed(132.75, 3)

# 133 - 148.5  riff, blue colour
ev(133, RING, B['on'], 0.25)
riff(132.9, 148.5, B, R)
ev(139, ZOOM, 0)
ev(142, CENTER, W['fd'], 0.8)
ev(146.5, BACK, W['fd'], 0.8)        # strong hit in the audio with no note

# 148.5 - 157  syncopated lead fill: center + lasers trade on every note
ev(148.5, RING, B['tr'], 0.1)
speed(148.5, 2)
for t, ns in notes_in(148.5, 156.9):
    for d in ns:
        ev(t, LEFT if d['c'] == 0 else RIGHT, COL[d['c']]['fd'], 0.9)
        ev(t, CENTER, COL[d['c']]['fd'], 0.7)
ev(155.5, BACK, R['fd'])
ev(155.5, SPIN, 0)

# 157 - 163  fast runs
ev(157, RING, R['on'], 0.3)
speed(157, 5)
column_chase(156.9, 162.9)

# 163 / 169 / 175  huge sustained chords every bar; side matches the notes' column
def chord(t, side, col, nxt):
    ev(t, side, W['fl'], 1.2)
    ev(t, LEFT if side == RIGHT else RIGHT, col['fd'], 0.6)
    ev(t, BACK, col['fl'], 1.2)
    ev(t, RING, col['fl'], 1.0)
    ev(t, CENTER, W['fd'], 1.2)
    ev(t, SPIN, 0)
    ev(t, ZOOM, 0)
    ev(t, LSPD if side == LEFT else RSPD, 8)
    ev(t, RSPD if side == LEFT else LSPD, 2)
    # let the chord decay over the bar
    end = nxt - 0.25
    for typ, lvl in ((side, 0.2), (BACK, 0.25), (RING, 0.15)):
        ev(end, typ, col['tr'], lvl)

chord(163, RIGHT, R, 169)
chord(169, LEFT, B, 175)
chord(175, RIGHT, R, 181)
# drum hits between the chords (no notes there)
for t in (165, 167, 167.5, 171, 173.5, 177, 179, 179.5):
    ev(t, CENTER, R['fd'], 0.6 if t not in (167.5, 179.5) else 0.9)

# 181 - 192  fast runs + walls
ev(181, LEFT, W['fl'], 1.0)   # left wall
ev(181, LSPD, 6)
ev(182, LEFT, R['tr'], 0.0)
ev(184, RIGHT, W['fl'], 1.0)  # right wall
ev(184, RSPD, 6)
ev(185, RIGHT, B['tr'], 0.0)
ev(181, BACK, R['on'], 0.3)
column_chase(181.5, 184)      # (runs during the walls)
column_chase(184.5, END)
for t in (187, 189, 191.5):
    ev(t, CENTER, W['fd'], 0.9)
    ev(t, SPIN, 0)
ev(189, ZOOM, 0)

# leave a steady state so the rest of the (unlit) song isn't dark
ev(END, BACK, R['on'], 0.7)
ev(END, RING, R['on'], 0.35)
ev(END, CENTER, R['on'], 0.4)
speed(END, 2)

# ======================================================================
# Write: drop the old events before END, keep anything after.
lp = os.path.join(MAP, 'Expert.lightshow.dat')
ls = json.load(open(lp))
old_data = ls['basicEventsData']
kept = [(e['b'], old_data[e['i']]) for e in ls['basicEvents'] if e['b'] >= END + 0.75]

# if a light type gets two events at the exact same time, keep the last one written
seen = {}
for e in events:
    seen[(e[0], e[1])] = e
events = sorted(seen.values(), key=lambda e: (e[0], e[1]))

data, idx, basic = [], {}, []
def intern(d):
    key = (d['t'], d['i'], d['f'])
    if key not in idx:
        idx[key] = len(data)
        data.append(d)
    return idx[key]

for b, t, v, f in events:
    basic.append({'b': b, 'i': intern({'t': t, 'i': v, 'f': f})})
for b, d in kept:
    basic.append({'b': b, 'i': intern(d)})

ls['basicEvents'] = basic
ls['basicEventsData'] = data
with open(lp, 'w') as fh:
    json.dump(ls, fh, separators=(',', ':'))
print(f'{len(events)} events written for beats 0-{END}, {len(kept)} later events kept, {len(data)} unique event datas')
