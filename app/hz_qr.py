"""HotZone FM — tiny QR code generator (byte mode, error correction M, versions 1-9) -> SVG.
Used for "scan with the phone" on the settings page; no extra library needed."""
from __future__ import annotations

# version -> (ec codewords per block, [(blocks, data codewords per block), ...])   level M
_EC = {1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
       6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)])}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46]}
_VERINFO = {7: 0x07C94, 8: 0x085BC, 9: 0x09A99}

_EXP = [0] * 512; _LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x; _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100: _x ^= 0x11D
for _i in range(255, 512): _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs(data, n):
    gen = [1]
    for i in range(n):
        g2 = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            g2[j] ^= c; g2[j + 1] ^= _gmul(c, _EXP[i])
        gen = g2
    res = [0] * n
    for d in data:
        f = d ^ res[0]
        res = res[1:] + [0]
        for j in range(n): res[j] ^= _gmul(gen[j + 1], f)
    return res


def _codewords(data: bytes):
    for v in range(1, 10):
        ec, groups = _EC[v]
        cap = sum(b * d for b, d in groups)
        if 4 + 8 + 8 * len(data) <= cap * 8: break
    else:
        raise ValueError('網址太長，無法做成 QR code')
    bits = [0, 1, 0, 0] + [int(b) for b in format(len(data), '08b')]
    for c in data: bits += [int(b) for b in format(c, '08b')]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    cw = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]; k = 0
    while len(cw) < cap: cw.append(pad[k % 2]); k += 1
    blocks = []; pos = 0
    for nb, nd in groups:
        for _ in range(nb): blocks.append(cw[pos:pos + nd]); pos += nd
    ecb = [_rs(b, ec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b): out.append(b[i])
    for i in range(ec):
        for e in ecb: out.append(e[i])
    return v, out


def _bch_format(mask):
    d = (0 << 3) | mask                                                     # level M = 00
    v = d << 10
    for i in range(14, 9, -1):
        if v & (1 << i): v ^= 0x537 << (i - 10)
    return ((d << 10) | v) ^ 0x5412


def matrix(text: str):
    v, cw = _codewords(text.encode('utf-8'))
    n = 17 + 4 * v
    M = [[None] * n for _ in range(n)]

    def put(r, c, val):
        if 0 <= r < n and 0 <= c < n: M[r][c] = val
    for (r0, c0) in ((0, 0), (0, n - 7), (n - 7, 0)):                         # finders + separators
        for r in range(-1, 8):
            for c in range(-1, 8):
                inside = 0 <= r <= 6 and 0 <= c <= 6
                dark = inside and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                put(r0 + r, c0 + c, 1 if dark else 0)
    for i in range(8, n - 8):                                                 # timing
        M[6][i] = M[i][6] = 1 if i % 2 == 0 else 0
    al = _ALIGN[v]
    for r in al:
        for c in al:
            if (r < 9 and c < 9) or (r < 9 and c > n - 10) or (r > n - 10 and c < 9): continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    M[r + dr][c + dc] = 1 if max(abs(dr), abs(dc)) != 1 else 0
    M[4 * v + 9][8] = 1                                                       # dark module
    fmt_cells = [(8, i) for i in list(range(0, 6)) + [7, 8]] + [(i, 8) for i in (7, 5, 4, 3, 2, 1, 0)]
    fmt_cells2 = [(n - 1 - i, 8) for i in range(7)] + [(8, n - 8 + i) for i in range(8)]
    for r, c in fmt_cells + fmt_cells2:
        if M[r][c] is None: M[r][c] = 0
    ver_cells = []
    if v >= 7:
        for i in range(18):
            a, b = i // 3, n - 11 + i % 3
            ver_cells += [(a, b, i), (b, a, i)]
        for a, b, i in ver_cells: M[a][b] = (_VERINFO[v] >> i) & 1
    reserved = [[M[r][c] is not None for c in range(n)] for r in range(n)]
    bits = []
    for c in cw: bits += [(c >> (7 - i)) & 1 for i in range(8)]
    k = 0; up = True; col = n - 1
    while col > 0:
        if col == 6: col -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for r in rows:
            for c in (col, col - 1):
                if not reserved[r][c]:
                    M[r][c] = bits[k] if k < len(bits) else 0; k += 1
        up = not up; col -= 2
    masks = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
             lambda r, c: (r // 2 + c // 3) % 2 == 0, lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
             lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0, lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]
    best = None
    for m, fn in enumerate(masks):
        X = [[(M[r][c] ^ 1) if (not reserved[r][c] and fn(r, c)) else M[r][c] for c in range(n)] for r in range(n)]
        f = _bch_format(m)
        for i, (r, c) in enumerate(fmt_cells): X[r][c] = (f >> (14 - i)) & 1
        for i, (r, c) in enumerate(fmt_cells2): X[r][c] = (f >> (14 - i)) & 1
        p = _penalty(X)
        if best is None or p < best[0]: best = (p, X)
    return best[1]


def _penalty(X):
    n = len(X); p = 0
    for line in X + [list(col) for col in zip(*X)]:
        run = 1
        for i in range(1, n):
            if line[i] == line[i - 1]: run += 1
            else:
                if run >= 5: p += run - 2
                run = 1
        if run >= 5: p += run - 2
        s = ''.join(map(str, line))
        p += 40 * (s.count('10111010000') + s.count('00001011101'))
    for r in range(n - 1):
        for c in range(n - 1):
            if X[r][c] == X[r + 1][c] == X[r][c + 1] == X[r + 1][c + 1]: p += 3
    dark = sum(map(sum, X)) * 100 // (n * n)
    p += abs(dark - 50) // 5 * 10
    return p


def svg(text: str, scale=6, border=4, dark='#000', light='#fff'):
    X = matrix(text); n = len(X); size = (n + 2 * border) * scale
    rects = ''.join(f'<rect x="{(c + border) * scale}" y="{(r + border) * scale}" width="{scale}" height="{scale}"/>'
                    for r in range(n) for c in range(n) if X[r][c])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
            f'<rect width="100%" height="100%" fill="{light}"/><g fill="{dark}">{rects}</g></svg>')
