#!/usr/bin/env python3
"""Speed optimiser for The Andorra Edit.

Run it on every page before each deploy:
    python3 /home/claude/tools/opt/optimize.py            # optimise all pages
    python3 /home/claude/tools/opt/optimize.py page.html  # optimise some pages
    python3 /home/claude/tools/opt/optimize.py restore    # put the full CSS back in every page

What it does to each page (all steps are repeatable and safe to run again):
  1. Puts back the page's full CSS, kept in _build/css/<hash>.css and _build/cssmap.json.
  2. Menu photos: load only when the navigation is used (data-msrc).
  3. Photos in <main> marked loading="lazy" load as they scroll near (data-lsrc / data-lsrcset).
  4. Drops CSS rules the page can never use (prune.js), keeping the full CSS on file.

Before a sitewide CSS edit, run `restore` first, edit, then run the optimiser again.
"""
import os, re, sys, json, hashlib, subprocess, glob

SITE = '/home/claude/andorra-edit'
B = os.path.join(SITE, '_build')
CSSD = os.path.join(B, 'css')
MAP = os.path.join(B, 'cssmap.json')
HERE = os.path.dirname(os.path.abspath(__file__))
PRUNE = os.path.join(HERE, 'prune.js')
STYLE = re.compile(r'(<style[^>]*>)(.*?)(</style>)', re.S)
PIX = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

MENU_JS = ("<script id=\"mtile-load\">(function(){var d=0;function go(){if(d)return;d=1;"
           "document.querySelectorAll('img[data-msrc]').forEach(function(i){i.src=i.getAttribute('data-msrc');i.removeAttribute('data-msrc');});}"
           "var m=document.querySelector('.mast nav');if(m){m.addEventListener('pointerover',go,{once:true});m.addEventListener('focusin',go,{once:true});m.addEventListener('touchstart',go,{once:true,passive:true});}"
           "})();</script>")

LAZY_JS = ("<script id=\"lz-io\">(function(){var L=document.querySelectorAll('[data-lsrc],[data-lsrcset]');if(!L.length)return;"
           "function one(el){var p=el.tagName==='IMG'&&el.parentNode&&el.parentNode.tagName==='PICTURE'?el.parentNode:null;"
           "(p?p.querySelectorAll('[data-lsrcset],[data-lsrc]'):[el]).forEach(function(n){if(n.dataset.lsrcset){n.srcset=n.dataset.lsrcset;n.removeAttribute('data-lsrcset');}if(n.dataset.lsrc){n.src=n.dataset.lsrc;n.removeAttribute('data-lsrc');}});}"
           "function show(el){one(el);for(var a=el.parentElement,k=0;a&&k<5;a=a.parentElement,k++){if(a.scrollWidth>a.clientWidth+8){a.querySelectorAll('img[data-lsrc],img[data-lsrcset]').forEach(function(i){io&&io.unobserve(i);one(i);});break;}}}"
           "var io=null;if(!('IntersectionObserver' in window)){L.forEach(one);return;}"
           "io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){io.unobserve(e.target);show(e.target);}});},{rootMargin:'250px'});"
           "document.querySelectorAll('img[data-lsrc],img[data-lsrcset]').forEach(function(i){io.observe(i);});"
           "addEventListener('beforeprint',function(){document.querySelectorAll('[data-lsrc],[data-lsrcset]').forEach(one);});})();</script>")


def h(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:16]


def load_map():
    return json.load(open(MAP)) if os.path.exists(MAP) else {}


def save_map(mp):
    os.makedirs(CSSD, exist_ok=True)
    json.dump(mp, open(MAP, 'w'), indent=0, sort_keys=True)


def save_css(css):
    os.makedirs(CSSD, exist_ok=True)
    p = os.path.join(CSSD, h(css) + '.css')
    if not os.path.exists(p):
        open(p, 'w', encoding='utf-8').write(css)
    return h(css)


def read_css(hh):
    return open(os.path.join(CSSD, hh + '.css'), encoding='utf-8').read()


def global_pruned(mp):
    g = {}
    for recs in mp.values():
        for full, pr in recs:
            g.setdefault(pr, full)
    return g


def full_blocks(page, blocks, mp, gp):
    rec = mp.get(page, [])
    out = []
    for i, b in enumerate(blocks):
        hb = h(b)
        if i < len(rec) and hb == rec[i][1] and os.path.exists(os.path.join(CSSD, rec[i][0] + '.css')):
            out.append(read_css(rec[i][0]))
        elif hb in gp and os.path.exists(os.path.join(CSSD, gp[hb] + '.css')):
            out.append(read_css(gp[hb]))
        else:
            out.append(b)
    return out


def put_blocks(s, new):
    it = iter(new)
    return STYLE.sub(lambda m: m.group(1) + next(it) + m.group(3), s)


def menu_convert(s):
    s = re.sub(r'(<a class="mtile" href="[^"]*"><img) src="(?!data:)([^"]+)"',
               lambda m: '%s src="%s" data-msrc="%s"' % (m.group(1), PIX, m.group(2)), s)
    if 'data-msrc' in s and 'id="mtile-load"' not in s:
        k = s.rfind('</body>'); s = s[:k] + MENU_JS + s[k:]
    return s


def lazy_convert(s):
    i = s.find('<main'); j = s.find('</main>')
    if i < 0 or j < 0:
        return s
    main = s[i:j]

    def pic(m):
        block = m.group(0)
        if 'loading="lazy"' not in block or 'data-lsrc' in block:
            return block
        block = re.sub(r'(<source\b[^>]*?) srcset="', r'\1 data-lsrcset="', block)
        block = re.sub(r'(<img\b[^>]*?) srcset="', r'\1 data-lsrcset="', block)
        block = re.sub(r'(<img\b[^>]*?) src="(?!data:)([^"]+)"',
                       lambda mm: '%s src="%s" data-lsrc="%s"' % (mm.group(1), PIX, mm.group(2)), block, count=1)
        return block
    main = re.sub(r'<picture>.*?</picture>', pic, main, flags=re.S)

    def img(m):
        t = m.group(0)
        if 'loading="lazy"' not in t or 'data-lsrc' in t or 'src="data:' in t:
            return t
        t = t.replace(' srcset="', ' data-lsrcset="')
        t = re.sub(r' src="([^"]+)"', lambda mm: ' src="%s" data-lsrc="%s"' % (PIX, mm.group(1)), t, count=1)
        return t
    main = re.sub(r'<img\b[^>]*>', img, main)
    s = s[:i] + main + s[j:]
    if ('data-lsrc' in s) and 'id="lz-io"' not in s:
        k = s.rfind('</body>'); s = s[:k] + LAZY_JS + s[k:]
    return s


def prune(html_wo_style, blocks):
    r = subprocess.run(['node', PRUNE], input=json.dumps({'html': html_wo_style, 'blocks': blocks}),
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        raise SystemExit(r.stderr)
    return json.loads(r.stdout)['pruned']


def pages(args):
    if args:
        return [os.path.basename(a) for a in args]
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(SITE, '*.html')))


def restore_all(names):
    mp = load_map(); gp = global_pruned(mp)
    for name in names:
        p = os.path.join(SITE, name); s = open(p, encoding='utf-8').read()
        blocks = [m.group(2) for m in STYLE.finditer(s)]
        s2 = put_blocks(s, full_blocks(name, blocks, mp, gp))
        if s2 != s:
            open(p, 'w', encoding='utf-8').write(s2)
    print('restored', len(names))


def restore_text(s, name):
    """Return page text with its full CSS (for use as a template)."""
    mp = load_map(); gp = global_pruned(mp)
    blocks = [m.group(2) for m in STYLE.finditer(s)]
    return put_blocks(s, full_blocks(name, blocks, mp, gp))


def optimise(names):
    mp = load_map(); gp = global_pruned(mp)
    before = after = 0
    for name in names:
        p = os.path.join(SITE, name); s = open(p, encoding='utf-8').read()
        blocks = [m.group(2) for m in STYLE.finditer(s)]
        full = full_blocks(name, blocks, mp, gp)
        s = put_blocks(s, full)
        s = menu_convert(s)
        s = lazy_convert(s)
        pr = prune(STYLE.sub('', s), full)
        s = put_blocks(s, pr)
        open(p, 'w', encoding='utf-8').write(s)
        mp[name] = [[save_css(f), h(q)] for f, q in zip(full, pr)]
        before += sum(len(x) for x in full); after += sum(len(x) for x in pr)
    save_map(mp)
    print('optimised %d pages: CSS %d KB -> %d KB' % (len(names), before // 1024, after // 1024))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'restore':
        restore_all(pages(a[1:]))
    else:
        optimise(pages(a))
