"""Generate lighting for the first 60 s (beats 0-128 @ 128 BPM) of hounds.

Usage: python3 gen_lights.py . onsets_low.txt
Replaces every basic event before END in Expert.lightshow.dat; events after END are kept.
"""
import json, sys, os

MAP = sys.argv[1]
ONSETS = [float(l) for l in open(sys.argv[2]) if l.strip()]
END = 128.0

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


def snap(b):
    """Snap a note time onto the nearest audio onset (if close), then onto a clean grid."""
    g3 = round(b * 3) / 3
    if abs(g3 - b) <= 0.04:          # on-grid note (most are 0.033 late)
        return round(g3, 3)
    near = min(ONSETS, key=lambda o: abs(o - b))
    if abs(near - b) <= 0.15:
        b = near
    g12 = round(b * 12) / 12
    return g12 if abs(g12 - b) <= 0.035 else round(b * 48) / 48


# ---- load notes, grouped by snapped light time ----
bm = json.load(open(os.path.join(MAP, 'ExpertStandard.dat')))
nd = bm['colorNotesData']
groups = {}
for n in bm['colorNotes']:
    if n['b'] >= END + 0.5:
        continue
    d = nd[n['i']]
    groups.setdefault(snap(n['b']), []).append(d)
NOTE_TIMES = sorted(groups)


def notes_in(a, b):
    return [(t, groups[t]) for t in NOTE_TIMES if a <= t < b]


def is_downbeat(t):  # bars start at 4.667, 8.667, ...
    return abs(((t - 2 / 3) / 4) - round((t - 2 / 3) / 4)) < 1e-3


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
# 0 - 4.667  silence: blackout
all_lights(0, OFF)
speed(0, 0)

# 4.667  opening chord (loudest moment of the intro), rings out until 12.667
big_hit(4.667, R, spd=2)
ev(4.667, BACK, R['fl'], 1.3)
ev(11.9, BACK, R['tr'], 0.12)       # slow fade of the back lasers while the chord rings
ev(8.667, SPIN, 0)

# 12.667 - 24.667  quiet single-note riff; lasers answer each note, the stage swells toward the band entry
speed(12.667, 1)
for t, ns in notes_in(12.0, 24.6):
    k = (t - 12.667) / 12            # 0 -> 1 across the section
    lvl = 0.45 + 0.45 * k
    for d in ns:
        ev(t, LEFT if d['c'] == 0 else RIGHT, COL[d['c']]['fd'], lvl)
ev(16.667, RING, R['on'], 0.0)
ev(24.5, RING, R['tr'], 0.5)
ev(20.667, CENTER, R['on'], 0.0)
ev(24.5, CENTER, R['tr'], 0.6)
ev(22.667, SPIN, 0)

# 24.667 - 27.667  band enters: triplet pickup ripples across the ring, then the lasers
ev(24.667, RING, R['fl'])
ev(25.0, RING, B['fl'])
ev(25.333, RING, R['fd'])
ev(25.333, CENTER, R['fd'], 0.6)
ev(25.667, BACK, B['fd'])
ev(26.0, LEFT, B['fd'])
ev(26.333, RIGHT, B['fd'])
ev(26.333, CENTER, B['fd'], 0.8)
ev(27.333, ZOOM, 0)

# 27.667  big hit, main riff starts
big_hit(27.667, R, spd=3)
ev(28.667, RING, R['on'], 0.25)      # ambient glow under the riff
riff(28.2, 36.6, R, B)

# 36.667 - 40.667  stop + three-step build into the big hit
ev(36.667, BACK, W['fd'])
ev(36.667, CENTER, R['fd'])
ev(36.667, RING, R['fd'], 0.6)       # ambient fades out -> darkness before the build
ev(36.667, LEFT, OFF)
ev(36.667, RIGHT, OFF)
speed(36.667, 0)
ev(38.667, LEFT, R['fl'], 0.7)
speed(38.667, 3, 0)
ev(39.333, RIGHT, B['fl'], 0.85)
speed(39.333, 3, 3)
ev(40.0, BACK, R['fl'], 1.0)
ev(40.0, RING, R['fl'], 0.6)
speed(40.0, 5)
big_hit(40.667, W, spd=4)
ev(40.667, RING, R['fl'], 1.0)

# 40.667 - 48.667  riff, blue variation
ev(42.667, RING, B['tr'], 0.25)
riff(42.9, 48.6, B, R)
big_hit(48.667, B, spd=2)

# 48.667 - 64.667  sparse passage: slow colour drift, accents on note pairs
ev(49.5, BACK, B['tr'], 0.35)
ev(56.667, BACK, R['tr'], 0.35)
ev(64.4, BACK, R['tr'], 0.6)
ev(50.667, RING, B['tr'], 0.2)
speed(52.667, 1)
for t, ns in notes_in(49.0, 64.6):
    cs = {d['c'] for d in ns}
    for c in cs:
        ev(t, LEFT if c == 0 else RIGHT, COL[c]['fd'], 0.8)
    if len(cs) == 2:
        ev(t, CENTER, B['fd'], 0.6)
ev(56.667, SPIN, 0)
ev(60.667, SPIN, 0)

# 64.667 - 76.667  riff returns; arpeggiated singles 72-76 chase by column
big_hit(64.667, R, spd=3)
ev(65.667, RING, R['on'], 0.25)
riff(65.0, 72.4, R, B)
ev(67.667, CENTER, W['fd'], 0.9)    # strong snare accent in the audio
ev(72.4, RING, B['tr'], 0.3)
column_chase(72.4, 76.6)
ev(72.667, ZOOM, 0)

# 76.667 - 84.667  riff
ev(76.667, RING, R['tr'], 0.25)
speed(76.667, 4)
riff(76.6, 84.6, R, B)
ev(80.667, ZOOM, 0)

# 84.667 - 88.667  walls: the side of the wall lights up
ev(84.667, LEFT, W['fl'], 1.0)
ev(84.667, RIGHT, OFF)
ev(84.667, BACK, R['fd'])
ev(84.667, LSPD, 7)
ev(85.667, LEFT, R['fd'], 0.8)
ev(85.667, CENTER, R['fd'], 0.6)
ev(86.667, RIGHT, W['fl'], 1.0)
ev(86.667, LEFT, OFF)
ev(86.667, BACK, B['fd'])
ev(86.667, RSPD, 7)
ev(87.667, RIGHT, B['fd'], 0.8)
ev(87.667, CENTER, B['fd'], 0.6)
speed(88.5, 3)

# 88.667 - 99  riff, blue colour
ev(88.667, RING, B['on'], 0.25)
riff(88.6, 99.0, B, R)
ev(92.667, ZOOM, 0)
ev(94.667, CENTER, W['fd'], 0.8)
ev(97.667, BACK, W['fd'], 0.8)       # strong hit in the audio with no note

# 99 - 104.667  syncopated lead fill: center + lasers trade on every note
ev(99.0, RING, B['tr'], 0.1)
speed(99.0, 2)
for t, ns in notes_in(99.0, 104.6):
    for d in ns:
        ev(t, LEFT if d['c'] == 0 else RIGHT, COL[d['c']]['fd'], 0.9)
        ev(t, CENTER, COL[d['c']]['fd'], 0.7)
ev(103.667, BACK, R['fd'])
ev(103.667, SPIN, 0)

# 104.667 - 108.667  triplet runs
ev(104.667, RING, R['on'], 0.3)
speed(104.667, 5)
column_chase(104.6, 108.6)

# 108.667 / 112.667 / 116.667  huge sustained chords every bar; side matches the notes' column
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
    end = nxt - 0.2
    for typ, lvl in ((side, 0.2), (BACK, 0.25), (RING, 0.15)):
        ev(end, typ, col['tr'], lvl)

chord(108.667, RIGHT, R, 112.667)
chord(112.667, LEFT, B, 116.667)
chord(116.667, RIGHT, R, 120.667)
# drum hits between the chords (no notes there)
for t in (110.0, 111.333, 111.667, 114.0, 115.667, 118.0, 119.333, 119.667):
    ev(t, CENTER, R['fd'], 0.6 if t not in (111.667, 119.667) else 0.9)

# 120.667 - 128  fast runs + walls
ev(120.667, LEFT, W['fl'], 1.0)   # left wall
ev(120.667, LSPD, 6)
ev(121.4, LEFT, R['tr'], 0.0)
ev(122.667, RIGHT, W['fl'], 1.0)  # right wall
ev(122.667, RSPD, 6)
ev(123.4, RIGHT, B['tr'], 0.0)
ev(120.667, BACK, R['on'], 0.3)
column_chase(121.0, 120.667 + 2)  # (runs during the walls)
column_chase(123.0, END)
for t in (124.667, 126.0, 127.667):
    ev(t, CENTER, W['fd'], 0.9)
    ev(t, SPIN, 0)
ev(126.0, ZOOM, 0)

# leave a steady state so the rest of the (unlit) song isn't dark
ev(END, BACK, R['on'], 0.7)
ev(END, RING, R['on'], 0.35)
ev(END, CENTER, R['on'], 0.4)
speed(END, 2)

# ======================================================================
# Write: drop the old (misaligned) events before END, keep anything after.
lp = os.path.join(MAP, 'Expert.lightshow.dat')
ls = json.load(open(lp))
old_data = ls['basicEventsData']
kept = [(e['b'], old_data[e['i']]) for e in ls['basicEvents'] if e['b'] >= END + 0.5]

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
