r"""
Logourile brandurilor fara logo, luate de pe SITE-UL OFICIAL al fiecarui brand (campul site_oficial din
rezultate\toate.jsonl). Pe pagina principala cauta, in ordine:
  1. o imagine cu „logo” in src / class / id / alt (de preferat in <header>), inclusiv SVG;
  2. un <svg> inline cu „logo” in class / id / aria-label (salvat ca fisier .svg);
  3. apple-touch-icon / icon mare (ultima varianta, marcata „icon”).
Folosire:  python logouri_site.py      (fara cheie API; ~10-20 minute)
Rezultat:  logouri_site\<id>.<ext>  si  logouri_site\raport.txt
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
AICI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AICI, 'logouri_site')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,image/avif,image/webp,image/svg+xml,*/*;q=0.8',
      'Accept-Language': 'ro,en;q=0.8'}

date = {b['id']: b for b in json.load(open(os.path.join(AICI, 'branduri_date.json'), encoding='utf-8'))}
site = {}
for linie in open(os.path.join(AICI, 'rezultate', 'toate.jsonl'), encoding='utf-8'):
    try:
        p = json.loads(linie)
    except Exception:
        continue
    if p.get('site_oficial'):
        site[int(p['id'])] = p['site_oficial'].strip()


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get('Content-Type', ''), r.geturl()


class Cauta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.imagini, self.icoane, self.svguri = [], [], []
        self.in_header = 0
        self._svg = None
        self._adanc = 0
        self.stiva = []          # (tag, are „logo”) - parintii imaginii (ex. <a class="logo"><img src="x.svg">)

    def in_logo(self):
        return any(l for _, l in self.stiva)

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or '') for k, v in attrs}
        if tag == 'header':
            self.in_header += 1
        if self._svg is not None:
            self._svg.append(self.get_starttag_text())
            self._adanc += 1
            return
        text = ' '.join([a.get('class', ''), a.get('id', ''), a.get('alt', ''), a.get('aria-label', ''),
                         a.get('title', '')]).lower()
        if tag not in ('img', 'link', 'meta', 'br', 'input', 'source', 'hr', 'svg'):
            self.stiva.append((tag, 'logo' in text or 'brand' in a.get('class', '').lower()))
        if tag == 'img':
            src = a.get('src') or a.get('data-src') or a.get('data-lazy-src') or ''
            if not src and a.get('srcset'):
                src = a['srcset'].split(',')[0].split()[0]
            if src and ('logo' in src.lower() or 'logo' in text or self.in_logo()):
                scor = 3 if self.in_header else 1
                if self.in_logo():
                    scor += 1
                if 'logo' in src.lower():
                    scor += 1
                if any(x in src.lower() for x in ('footer', 'partner', 'client', 'payment', 'white', 'alb', 'negativ')):
                    scor -= 2
                self.imagini.append((scor, src))
        elif tag == 'svg' and ('logo' in text or self.in_logo()):
            self._svg = [self.get_starttag_text()]
            self._adanc = 1
        elif tag == 'link':
            rel = a.get('rel', '').lower()
            if 'apple-touch-icon' in rel or ('icon' in rel and re.search(r'(192|180|256|512)', a.get('sizes', '') + a.get('href', ''))):
                if a.get('href'):
                    self.icoane.append(a['href'])
        elif tag == 'meta' and a.get('property', a.get('name', '')).lower() in ('og:logo',):
            if a.get('content'):
                self.imagini.append((2, a['content']))

    def handle_startendtag(self, tag, attrs):
        if self._svg is not None:
            self._svg.append(self.get_starttag_text())
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'header' and self.in_header:
            self.in_header -= 1
        if self._svg is None and any(x == tag for x, _ in self.stiva):
            while self.stiva:
                if self.stiva.pop()[0] == tag:
                    break
        if self._svg is not None:
            self._svg.append(f'</{tag}>')
            self._adanc -= 1
            if self._adanc == 0:
                s = ''.join(self._svg)
                if 'xmlns' not in s[:200]:
                    s = s.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
                self.svguri.append(s)
                self._svg = None

    def handle_data(self, data):
        if self._svg is not None:
            self._svg.append(data)


def ext_din(ct, url):
    ct = (ct or '').lower()
    for k, e in (('svg', 'svg'), ('png', 'png'), ('webp', 'webp'), ('jpeg', 'jpg'), ('jpg', 'jpg'), ('gif', 'gif'),
                 ('icon', 'ico')):
        if k in ct:
            return e
    m = re.search(r'\.(svg|png|webp|jpe?g|gif|ico)(\?|#|$)', url.lower())
    return m.group(1).replace('jpeg', 'jpg') if m else None


raport = open(os.path.join(OUT, 'raport.txt'), 'a', encoding='utf-8')
deja = {int(n.split('.')[0]) for n in os.listdir(OUT) if re.match(r'\d+\.', n)}
try:
    for l in open(os.path.join(OUT, 'raport.txt'), encoding='utf-8'):
        if l.split('\t')[0].isdigit():
            deja.add(int(l.split('\t')[0]))
except Exception:
    pass
de_facut = sorted(i for i, b in date.items() if not b.get('are_logo') and i in site and i not in deja)
print(f'{len(de_facut)} branduri fara logo, cu site oficial')
for k, i in enumerate(de_facut, 1):
    nume, url = date[i]['nume'], site[i]
    try:
        html, ct, final = get(url)
        p = Cauta()
        p.feed(html.decode('utf-8', 'ignore'))
        candidati = [(s, urllib.parse.urljoin(final, src)) for s, src in sorted(p.imagini, key=lambda x: -x[0])]
        salvat = None
        for scor, cu in candidati[:4]:
            if cu.startswith('data:'):
                continue
            try:
                b, ct2, _ = get(cu)
                e = ext_din(ct2, cu)
                if not e or len(b) < 300:
                    continue
                open(os.path.join(OUT, f'{i}.{e}'), 'wb').write(b)
                salvat = ('img', cu)
                break
            except Exception:
                continue
        if not salvat and p.svguri:
            s = max(p.svguri, key=len)
            if len(s) > 200:
                open(os.path.join(OUT, f'{i}.svg'), 'w', encoding='utf-8').write(s)
                salvat = ('svg-inline', final)
        if not salvat and p.icoane:
            for cu in p.icoane[:2]:
                cu = urllib.parse.urljoin(final, cu)
                try:
                    b, ct2, _ = get(cu)
                    e = ext_din(ct2, cu)
                    if e and len(b) > 300:
                        open(os.path.join(OUT, f'{i}.icon.{e}'), 'wb').write(b)
                        salvat = ('icon', cu)
                        break
                except Exception:
                    continue
        if salvat:
            raport.write(f'{i}\t{nume}\tOK\t{salvat[0]}\t{salvat[1]}\n')
            print(f'[{k}/{len(de_facut)}] OK {i} {nume} ({salvat[0]})')
        else:
            raport.write(f'{i}\t{nume}\tNIMIC\t\t{final}\n')
            print(f'[{k}/{len(de_facut)}] nimic {i} {nume}')
    except Exception as e:
        raport.write(f'{i}\t{nume}\tEROARE\t\t{url}\t{str(e)[:150]}\n')
        print(f'[{k}/{len(de_facut)}] EROARE {i} {nume}: {str(e)[:80]}')
    raport.flush()
    time.sleep(0.3)
raport.close()
print('Gata. Vezi logouri_site\\raport.txt')
