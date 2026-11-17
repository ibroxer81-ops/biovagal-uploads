import json, os, subprocess, sys, textwrap
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
F = '/usr/share/fonts/opentype/inter/'
BLACK, BOLD, MED = F + 'Inter-Black.otf', F + 'Inter-Bold.otf', F + 'Inter-Medium.otf'
INK, CREAM, ORANGE = '#1f1a17', '#f6efe2', '#e2632a'
OUT = '/home/claude/shorts/out'


def font(p, s): return ImageFont.truetype(p, s)


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines


def block(d, text, path, size, fill, y_center, maxw=900, lh=1.12):
    while True:
        f = font(path, size)
        lines = wrap(d, text, f, maxw)
        if len(lines) <= 5 or size < 50: break
        size -= 6
    h = len(lines) * size * lh
    y = y_center - h / 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=fill)
        y += size * lh
    return y


def logo(d, dark_bg, bg=None):
    f = font(BLACK, 44); x = 60; base = CREAM if dark_bg else INK
    for part, col in (('PUN', base), ('S', INK if bg == ORANGE else ORANGE), ('NUP', base)):
        d.text((x, 70), part, font=f, fill=col); x += d.textlength(part, font=f)


def frame(bg, kind, setup, punch, accent):
    im = Image.new('RGB', (W, H), bg); d = ImageDraw.Draw(im)
    dark = bg in ('#1d2a3a', '#2f7d79', '#1f1a17')
    ink = CREAM if dark else INK
    logo(d, dark, bg)
    if kind == 'end':
        f = font(BLACK, 150)
        parts = (('PUN', ink), ('S', accent), ('NUP', ink)); f = font(BLACK, 170)
        x = (W - sum(d.textlength(p, font=f) for p, _ in parts)) / 2
        for p, col in parts:
            d.text((x, 760), p, font=f, fill=col); x += d.textlength(p, font=f)
        block(d, 'Infinite puns on any word', MED, 54, ink, 1120)
        block(d, 'punsnup.com', BOLD, 72, accent, 1240)
        return im
    block(d, setup, BOLD, 84, ink, 640)
    if kind == 'punch':
        block(d, punch, BLACK, 118, accent, 1150)
    return im


def encode(png, dur, out, fade_in=0.3, fade_out=0.0):
    vf = f'format=yuv420p,loop=-1:1,trim=duration={dur},fade=t=in:st=0:d={fade_in}'
    if fade_out: vf += f',fade=t=out:st={dur - fade_out}:d={fade_out}'
    tmp = out.replace('.mp4', '.tmp.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', png, '-vf', vf,
                    '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', '30', tmp], check=True)
    os.replace(tmp, out)


def make(i, p, preview=False):
    os.makedirs(OUT, exist_ok=True)
    d = f'{OUT}/w{i}'; os.makedirs(d, exist_ok=True)
    for k in ('setup', 'punch', 'end'):
        frame(p['bg'], k, p['setup'], p['punch'], p['accent']).save(f'{d}/{k}.png')
    if preview: return
    encode(f'{d}/setup.png', 2.6, f'{d}/a.mp4')
    encode(f'{d}/punch.png', 4.2, f'{d}/b.mp4', fade_in=0.25)
    encode(f'{d}/end.png', 2.4, f'{d}/c.mp4', fade_out=0.3)
    open(f'{d}/list.txt', 'w').write("file 'a.mp4'\nfile 'b.mp4'\nfile 'c.mp4'\n")
    v = f'{d}/v.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/list.txt', '-c', 'copy', v], check=True)
    # silent AAC track so every platform accepts the upload
    final = f"{OUT}/{p['slug']}.mp4"; tmp = final.replace('.mp4', '.tmp.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', v, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-shortest', tmp], check=True)
    os.replace(tmp, final)


if __name__ == '__main__':
    puns = json.load(open('/home/claude/shorts/puns.json'))
    preview = '--preview' in sys.argv
    for i, p in enumerate(puns):
        make(i, p, preview)
        print('done', p['slug'])
