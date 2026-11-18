#!/usr/bin/env python3
"""Billy's project mistake scanner.
Usage: python3 qa.py [--fix] [--json out.json] DIR [DIR ...]
Scans html/md/txt/json/js/webmanifest files for typos, banned words,
wording rules, broken internal links, wrong prices and test-mode payment links.
--fix applies only safe, deterministic fixes (known misspellings, doubled words,
"Headphones recommended" -> "Headphones required", brand capitalisation)."""
import re, os, sys, json, html, glob

EXT = ('.html', '.htm', '.md', '.txt', '.json', '.js', '.webmanifest', '.xml')
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'out'}
SKIP_FILES = {'words.txt', 'whitelist.txt', 'README.md', 'uploads.json', 'drafts.json', 'plan.json', 'package-lock.json', 'qa.py'}

# ---- safe auto-fixes -------------------------------------------------------
MISSPELL = {
 'teh':'the','recieve':'receive','recieved':'received','seperate':'separate','definately':'definitely',
 'occured':'occurred','untill':'until','wich':'which','accross':'across','alot':'a lot','goverment':'government',
 'beleive':'believe','freind':'friend','thier':'their','tommorow':'tomorrow','tomorow':'tomorrow','acheive':'achieve',
 'adress':'address','begining':'beginning','calender':'calendar','comming':'coming','concious':'conscious',
 'enviroment':'environment','existance':'existence','foward':'forward','gaurd':'guard','happend':'happened',
 'immediatly':'immediately','independant':'independent','meditaion':'meditation','medatation':'meditation',
 'neccessary':'necessary','necessery':'necessary','noticable':'noticeable','occassion':'occasion','persue':'pursue',
 'posession':'possession','prefered':'preferred','publically':'publicly','realy':'really','reccomend':'recommend',
 'recomend':'recommend','relaxtion':'relaxation','succesful':'successful','suprise':'surprise','truely':'truly',
 'wierd':'weird','writting':'writing','breating':'breathing','breahting':'breathing','breathign':'breathing',
 'frequncy':'frequency','frequecy':'frequency','frequancy':'frequency','binuaral':'binaural','binarual':'binaural',
 'biniaural':'binaural','chackra':'chakra','chakara':'chakra','vibraton':'vibration','subcribe':'subscribe',
 'subsribe':'subscribe','subscibe':'subscribe','unlimted':'unlimited','unlimitted':'unlimited','monthy':'monthly',
 'lifetiem':'lifetime','yuo':'you',
 'headhpones':'headphones','headphoens':'headphones','hedphones':'headphones','solfegio':'solfeggio','solfeggeio':'solfeggio',
}
CASE_FIX = [  # (regex, replacement) brand rules
 (re.compile(r'\b(?:BioVagal|bioVagal|BIOvagal)\b'), 'Biovagal'),
 (re.compile(r'\b(?:PunSnup|punSnup|PunsNup|PUNsnup)\b'), 'Punsnup'),
 (re.compile(r'\b(Headphones?) recommended\b', re.I), lambda m: m.group(1) + ' required'),
 (re.compile(r'\b(headphones?) are recommended\b', re.I), lambda m: m.group(1) + ' are required'),
]
DOUBLE = re.compile(r'\b(the|a|an|and|to|of|in|is|it|for|on|with|your|you|this|that|be|The|A|And|To|It|You|This)[ \t]+\1\b')

# ---- report-only rules -----------------------------------------------------
BANNED = [(re.compile(r'greenock', re.I), 'Mentions Greenock (Billy wants no mention anywhere)')]
HEALTH = re.compile(r'\b(cures?|cured|heals? (?:your|the|all)|treats? (?:anxiety|depression|insomnia|pain)|guaranteed|clinically proven|scientifically proven|proven to|will fix|reverses?|traditionally associated with|Intention:)', re.I)
OLD_PRICE = re.compile(r'£\s?2\.99')
STRIPE = re.compile(r'https://buy\.stripe\.com/[A-Za-z0-9_]+')
LIVE_STRIPE = {'https://buy.stripe.com/5kQ7sNaf20ppdi9f4x0Ny02', 'https://buy.stripe.com/fZufZjbj61tt6TLbSl0Ny03'}

# ---- dictionary for unknown-word report -------------------------------------
WL = set()
for p in ['/usr/share/hunspell/en_US.dic', '/usr/share/hunspell/en_GB.dic']:
    if os.path.exists(p):
        for ln in open(p, encoding='latin-1'):
            w = ln.split('/')[0].strip().lower()
            if w and not w[0].isdigit(): WL.add(w)
HERE = os.path.dirname(os.path.abspath(__file__))
for p in [os.path.join(HERE, 'words.txt'), os.path.join(HERE, 'whitelist.txt')]:
    if os.path.exists(p):
        WL |= {w.strip().lower() for w in open(p) if w.strip() and not w.startswith('#')}

def known(w):
    w = w.lower().strip("'")
    if len(w) < 4 or not WL or w in WL: return True
    if w.endswith("'s") and w[:-2] in WL: return True
    for suf, rep in [('s',''),('es',''),('ies','y'),('ed',''),('ed','e'),('ing',''),('ing','e'),('ly',''),('er',''),
                     ('er','e'),('est',''),('ers',''),('ness',''),('ful',''),('less',''),('ment',''),('able',''),('d',''),
                     ('ise','ize'),('ised','ized'),('ising','izing'),('isation','ization'),('our','or'),('ours','ors'),
                     ('tre','ter'),('ence','ense'),('ogue','og'),('lled','led'),('lling','ling'),('ller','ler')]:
        if w.endswith(suf):
            b = w[:-len(suf)] + rep
            if b in WL: return True
            if len(b) > 2 and b[-1] == b[-2] and b[:-1] in WL: return True
    if '-' in w: return all(known(x) for x in w.split('-') if x)
    return False

def prose(x):
    x = x.strip()
    return ' ' in x and not re.search(r'[;{}=()<>]|=>|\.\w+\(', x)

TAG = re.compile(r'<script\b[^>]*>(.*?)</script>|<style\b.*?</style>|<[^>]+>', re.S | re.I)
STRLIT = re.compile(r'"((?:[^"\\\n]|\\.){3,})"|\'((?:[^\'\\\n]|\\.){3,})\'|`([^`]{3,})`')

def visible_text(src, ext):
    if ext in ('.html', '.htm'):
        out = []
        def rep(m):
            if m.group(1): out.append(' ¶ '.join(x for x in (a or b or c for a, b, c in STRLIT.findall(m.group(1))) if prose(x)))
            return ' ¶ '
        t = TAG.sub(rep, src)
        return html.unescape(t + ' ¶ ' + ' ¶ '.join(out))
    if ext == '.js':
        return ' ¶ '.join(x for x in (a or b or c for a, b, c in STRLIT.findall(src)) if prose(x))
    if ext in ('.json', '.webmanifest'):
        return ' ¶ '.join(re.findall(r'"([^"]{3,})"', src))
    return src

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")

def scan_file(path, root, fix):
    ext = os.path.splitext(path)[1].lower()
    rel = os.path.relpath(path, root)
    src = open(path, encoding='utf-8', errors='replace').read()
    issues, fixed = [], []
    new = src
    # safe fixes (only in human text, never in URLs)
    if fix:
        for bad, good in MISSPELL.items():
            pat = re.compile(r'(?<![/\w.-])' + re.escape(bad) + r'(?![\w/.-])', re.I)
            def r(m, good=good):
                s = m.group(0)
                return good.capitalize() if s[0].isupper() else good
            new2 = pat.sub(r, new)
            if new2 != new: fixed.append(f'{bad} -> {good}'); new = new2
        for rx, rp in CASE_FIX:
            new2 = rx.sub(rp, new)
            if new2 != new: fixed.append(f'wording/brand: {rx.pattern}'); new = new2
        new2 = DOUBLE.sub(lambda m: m.group(1), new)
        if new2 != new: fixed.append('doubled word'); new = new2
        if new != src: open(path, 'w', encoding='utf-8').write(new)
    else:
        for bad in MISSPELL:
            if re.search(r'(?<![/\w.-])' + re.escape(bad) + r'(?![\w/.-])', src, re.I): issues.append(('typo', f'"{bad}" should be "{MISSPELL[bad]}"'))
        for rx, _ in CASE_FIX:
            m = rx.search(src)
            if m: issues.append(('wording', f'"{m.group(0)}"'))
        for m in DOUBLE.finditer(visible_text(src, ext)): issues.append(('typo', f'doubled word "{m.group(0)}"'))
    text = visible_text(new, ext)
    for rx, msg in BANNED:
        for m in rx.finditer(new): issues.append(('banned', msg + f' (…{new[max(0,m.start()-30):m.end()+30].strip()}…)'))
    if 'biovagal' in (root + rel).lower() or 'biovagal' in new.lower():
        for m in HEALTH.finditer(text): issues.append(('claim', f'possible health/outcome claim: "{m.group(0)}"'))
    if 'punsnup' in new.lower() or 'site' in root:
        for m in OLD_PRICE.finditer(new): issues.append(('price', 'old price £2.99 (now £1.99/month, £7.99 lifetime)'))
    for m in STRIPE.finditer(new):
        u = m.group(0)
        if '/test_' in u: issues.append(('payment', f'TEST-mode Stripe link: {u}'))
        elif u not in LIVE_STRIPE and 'punsnup' in (root + new[:2000]).lower(): issues.append(('payment', f'unknown/old Stripe link: {u}'))
    # broken internal links
    if ext in ('.html', '.htm'):
        for m in re.finditer(r'(?:href|src)\s*=\s*["\']([^"\'#?]+)', new):
            u = m.group(1).strip()
            if re.match(r'^(https?:|mailto:|tel:|data:|javascript:|//|\$|\{)', u) or '${' in u or '+' in u: continue
            base = root if u.startswith('/') else os.path.dirname(path)
            tgt = os.path.normpath(os.path.join(base, u.lstrip('/')))
            if not (os.path.isfile(tgt) or os.path.isfile(os.path.join(tgt, 'index.html'))):
                issues.append(('link', f'broken internal link: {u}'))
        if '<title>' not in new.lower() and '<html' in new.lower(): issues.append(('seo', 'missing <title>'))
    # unknown words
    unk = sorted({w for w in WORD.findall(text) if not w[0].isupper() and not re.search(r'[a-z][A-Z]', w) and not known(w)})
    if unk: issues.append(('spelling?', 'check: ' + ', '.join(unk[:25]) + (' …' if len(unk) > 25 else '')))
    return rel, issues, fixed

def main():
    a = sys.argv[1:]; fix = '--fix' in a; a = [x for x in a if x != '--fix']
    jout = None
    if '--json' in a: i = a.index('--json'); jout = a[i+1]; del a[i:i+2]
    report = {}
    for root in a:
        root = os.path.abspath(root)
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in fn:
                if f.endswith(EXT) and f not in SKIP_FILES:
                    rel, iss, fx = scan_file(os.path.join(dp, f), root, fix)
                    if iss or fx: report[os.path.basename(root) + '/' + rel] = {'issues': iss, 'fixed': fx}
    order = ['payment', 'banned', 'claim', 'price', 'link', 'typo', 'wording', 'seo', 'spelling?']
    for k in sorted(report):
        v = report[k]
        print(f'\n## {k}')
        for x in v['fixed']: print(f'  FIXED   {x}')
        for t, m in sorted(v['issues'], key=lambda z: order.index(z[0])): print(f'  {t.upper():9} {m}')
    tot = sum(len(v['issues']) for v in report.values()); fx = sum(len(v['fixed']) for v in report.values())
    print(f'\nTOTAL: {tot} issues, {fx} fixes applied')
    if jout: json.dump(report, open(jout, 'w'), indent=1)

if __name__ == '__main__': main()
