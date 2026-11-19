"""Move the map onto a new tempo map (e.g. one exported by Tempora), then optionally snap notes to the grid.

Usage:
  python3 retime.py OLD_MAP_DIR NEW_AUDIODATA OUT_DIR [--snap] [--report report.txt]

Why this is needed: v4 note .dat files store *beats*, and AudioData.dat's bpmData decides
which beat plays at which sample. Copying the old .dat next to a new AudioData.dat keeps the
beat numbers but changes what they mean, so everything drifts. Here each object goes
old beat -> seconds (old bpmData) -> new beat (new bpmData).

--snap moves each distinct note time onto the 1/4-beat grid of the new tempo map. A Viterbi
pass picks one candidate per note. It favours (a) the nearest grid point, (b) whole and half
beats, (c) an audio onset at that point, and (d) keeping the same offset as the previous note,
so a run of notes moves as one block instead of splitting up. Notes never swap order or merge.
"""
import json, os, shutil, sys, subprocess
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith('--')]
SNAP = '--snap' in sys.argv
REPORT = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else None
if REPORT in args:
    args.remove(REPORT)
OLD, NEW_AD, OUT = args

GRID = 4            # snap resolution: 1/GRID beat
ONSET_BIAS = 0.020  # spectral-flux peaks come ~20 ms before the transient


def load_segs(p):
    d = json.load(open(p))
    f = d['songFrequency']
    return d, [(r['si'] / f, r['ei'] / f, r['sb'], r['eb']) for r in d['bpmData']]


def b2t(b, S):
    for s in S:
        t0, t1, b0, b1 = s
        if b <= b1 or s is S[-1]:
            return t0 if b1 == b0 else t0 + (b - b0) * (t1 - t0) / (b1 - b0)


def t2b(t, S):
    for s in S:
        t0, t1, b0, b1 = s
        if t <= t1 or s is S[-1]:
            return b0 if t1 == t0 else b0 + (t - t0) * (b1 - b0) / (t1 - t0)


old_info = json.load(open(os.path.join(OLD, 'Info.dat')))
_, O = load_segs(os.path.join(OLD, old_info['audio']['audioDataFilename']))
new_ad, N = load_segs(NEW_AD)
conv = lambda b: t2b(b2t(b, O), N)
diff = old_info['difficultyBeatmaps'][0]
bm = json.load(open(os.path.join(OLD, diff['beatmapDataFilename'])))
ls = json.load(open(os.path.join(OLD, diff['lightshowDataFilename'])))

# ---------- note snapping ----------
all_old = sorted({n['b'] for n in bm['colorNotes']} | {n['b'] for n in bm.get('bombNotes', [])})
snapped = {b: conv(b) for b in all_old}
# Notes meant to be simultaneous are sometimes saved a hair apart (691.092 vs 691.093);
# treat times within MERGE beats of each other as one chord.
MERGE = 0.02
groups = []
for b in all_old:
    if groups and snapped[b] - snapped[groups[-1][-1]] < MERGE:
        groups[-1].append(b)
    else:
        groups.append([b])
old_times = [g[0] for g in groups]
new_times = [float(np.mean([snapped[b] for b in g])) for g in groups]
log = []

if SNAP:
    song = os.path.join(OLD, old_info['audio']['songFilename'])
    sr, hop, n = 22050, 110, 1024
    x = np.frombuffer(subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', song, '-ac', '1', '-ar', str(sr),
                                      '-f', 'f32le', '-'], capture_output=True, check=True).stdout, np.float32)
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n).astype(np.float32)
    mag = np.log1p(100 * np.abs(np.fft.rfft(fr, axis=1)))
    flux = np.concatenate([[0], np.maximum(0, np.diff(mag, axis=0)).sum(1)])
    from scipy.ndimage import uniform_filter1d, maximum_filter1d
    flux = np.maximum(0, flux - uniform_filter1d(flux, 600))
    flux /= maximum_filter1d(flux, 600) + 1e-9
    ft = (np.arange(len(flux)) * hop + n / 2) / sr + ONSET_BIAS

    def onset(b):
        t = b2t(b, N)
        lo, hi = np.searchsorted(ft, [t - 0.02, t + 0.02])
        return float(flux[lo:hi].max()) if hi > lo else 0.0

    W_DIST, W_HALF, W_AUDIO, W_SHIFT = 1.0, 0.6, 1.2, 2.0
    cands, costs = [], []
    for nb in new_times:
        c = [k / GRID for k in range(int(np.floor((nb - 0.4) * GRID)), int(np.ceil((nb + 0.4) * GRID)) + 1)
             if abs(k / GRID - nb) <= 0.4]
        cands.append(c)
        costs.append([W_DIST * abs(ci - nb) / (1 / GRID) - W_HALF * ((ci * 2) % 1 == 0) - W_AUDIO * onset(ci)
                      for ci in c])
    # Viterbi
    acc = [list(costs[0])]
    back = [[None] * len(cands[0])]
    for i in range(1, len(new_times)):
        gap = new_times[i] - new_times[i - 1]
        row, brow = [], []
        for j, cj in enumerate(cands[i]):
            best, bk = float('inf'), None
            for k, ck in enumerate(cands[i - 1]):
                if cj <= ck:
                    continue
                shift = abs((cj - new_times[i]) - (ck - new_times[i - 1])) / (1 / GRID)
                v = acc[-1][k] + (W_SHIFT * shift if gap < 4 else 0)
                if v < best:
                    best, bk = v, k
            row.append(best + costs[i][j])
            brow.append(bk)
        acc.append(row)
        back.append(brow)
    j = int(np.argmin(acc[-1]))
    path = [0] * len(new_times)
    for i in range(len(new_times) - 1, -1, -1):
        path[i] = cands[i][j]
        j = back[i][j]
    for g, ob, nb, sb in zip(groups, old_times, new_times, path):
        for b in g:
            snapped[b] = sb
        nearest_half = round(nb * 2) / 2
        log.append((b2t(ob, O), ob, nb, sb, sb - nb, sb != nearest_half))


def note_beat(ob):
    return round(snapped[ob], 4)


def other_beat(ob):
    """Lights / walls: reuse a note's snap if they coincide, else nearest 1/GRID (or 1/16 if far)."""
    if ob in snapped:
        return round(snapped[ob], 4)
    nb = conv(ob)
    if not SNAP:
        return round(nb, 4)
    g = round(nb * GRID) / GRID
    return g if abs(g - nb) <= 0.08 else round(nb * 16) / 16


for k in ('colorNotes', 'bombNotes'):
    for o in bm.get(k, []):
        o['b'] = note_beat(o['b'])
for k in ('arcs', 'chains'):
    for o in bm.get(k, []):
        for bk in ('hb', 'tb', 'b'):
            if bk in o:
                o[bk] = other_beat(o[bk])
# walls: convert start and end separately (duration in beats changes with tempo)
od = bm['obstaclesData']
new_od = []
for o in bm['obstacles']:
    d = dict(od[o['i']])
    s, e = other_beat(o['b']), other_beat(o['b'] + d['d'])
    if SNAP:
        e = max(round(e * GRID) / GRID, s + 1 / GRID)
    o['b'] = s
    d['d'] = round(e - s, 4)
    o['i'] = len(new_od)
    new_od.append(d)
bm['obstaclesData'] = new_od
for k in ('njsEvents',):
    for o in bm.get(k, []):
        o['b'] = other_beat(o['b'])

for k, v in ls.items():
    if isinstance(v, list):
        for o in v:
            if isinstance(o, dict) and 'b' in o:
                o['b'] = other_beat(o['b'])
for k in ('basicEvents', 'colorBoostEvents', 'eventBoxGroups', 'waypoints'):
    if isinstance(ls.get(k), list):
        ls[k].sort(key=lambda o: o.get('b', 0))

# ---------- write out ----------
os.makedirs(OUT, exist_ok=True)
info = json.loads(json.dumps(old_info))
first_bpm = (N[1][3] - N[1][2]) / (N[1][1] - N[1][0]) * 60 if len(N) > 1 else 120
info['audio']['bpm'] = round(first_bpm)
# Keep the same note jump duration: the game computes half-jump beats from Info bpm.
def jump_secs(bpm, njs, off):
    spb, hj = 60 / bpm, 4.0
    while njs * spb * hj > 17.999:
        hj /= 2
    return 2 * spb * max(hj + off, 0.25)
for d in info['difficultyBeatmaps']:
    target = jump_secs(old_info['audio']['bpm'], d['noteJumpMovementSpeed'], d['noteJumpStartBeatOffset'])
    spb, hj = 60 / info['audio']['bpm'], 4.0
    while d['noteJumpMovementSpeed'] * spb * hj > 17.999:
        hj /= 2
    d['noteJumpStartBeatOffset'] = round(target / (2 * spb) - hj, 3)
json.dump(info, open(os.path.join(OUT, 'Info.dat'), 'w'), indent=2)
json.dump(new_ad, open(os.path.join(OUT, info['audio']['audioDataFilename']), 'w'), indent=2)
json.dump(bm, open(os.path.join(OUT, diff['beatmapDataFilename']), 'w'))
json.dump(ls, open(os.path.join(OUT, diff['lightshowDataFilename']), 'w'))
for f in {info['audio']['songFilename'], info['songPreviewFilename'], info['coverImageFilename']}:
    if not os.path.exists(os.path.join(OUT, f)):
        shutil.copy(os.path.join(OLD, f), os.path.join(OUT, f))
if os.path.isdir(os.path.join(OLD, 'Bookmarks')):
    shutil.copytree(os.path.join(OLD, 'Bookmarks'), os.path.join(OUT, 'Bookmarks'), dirs_exist_ok=True)

if REPORT and log:
    with open(REPORT, 'w') as fh:
        fh.write('time_s   old_beat   new_beat  snapped    moved(beats)  flag=not nearest 1/2\n')
        for t, ob, nb, sb, mv, fl in log:
            fh.write(f'{t:7.3f} {ob:9.3f} {nb:10.3f} {sb:9.3f} {mv:+8.3f}   {"*" if fl else ""}\n')
print(f'wrote {OUT}: {len(bm["colorNotes"])} notes, {len(bm["obstacles"])} walls, '
      f'{len(ls.get("basicEvents", []))} light events, Info bpm {info["audio"]["bpm"]}, '
      f'NJ offset {info["difficultyBeatmaps"][0]["noteJumpStartBeatOffset"]}')
