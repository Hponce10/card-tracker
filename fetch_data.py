#!/usr/bin/env python3
"""Refresh live prices in goodra_data.json from the Pokemon TCG API.

- Updates market/low/mid/high + Cardmarket avgs for every API-matched variant
- APPENDS a dated point to each variant's hist (real price history accumulates)
- Detects brand-new cards (new API ids) and adds them with added=<today>,
  downloading + embedding their image, so the app's new-release banner fires
- Never touches est ranges, JP/spreadsheet-only rows, or user data

Run: python3 fetch_data.py && python3 build.py   (then republish the artifact)
"""
import json, os, re, sys, base64, subprocess, datetime

here = os.path.dirname(os.path.abspath(__file__))
today = datetime.date.today().strftime('%Y/%m/%d')

def fetch(q, out):
    subprocess.run(['curl','-sf','--max-time','90',
        f'https://api.pokemontcg.io/v2/cards?q=name:*{q}*&pageSize=250','-o',out], check=True)
    return json.load(open(out))['data']

def embed_img(url, cid, folder, quality=64):
    from PIL import Image
    os.makedirs(os.path.join(here,folder), exist_ok=True)
    png = os.path.join(here,folder,cid+'.png'); jpg = png.replace('.png','.jpg')
    if not os.path.exists(jpg):
        subprocess.run(['curl','-s','--max-time','30','-A','Mozilla/5.0 (Macintosh)','-o',png,url],check=True)
        Image.open(png).convert('RGB').save(jpg,'JPEG',quality=quality,optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(open(jpg,'rb').read()).decode()

VKEY = {'normal':'normal','holofoil':'holofoil','reverseHolofoil':'reverseHolofoil'}

import unicodedata
def norm_set(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    s = s.replace(' (jp)','').replace('—',' ').replace('-',' ')
    for junk in (' black star',' base set',' the'):
        s = s.replace(junk,'')
    s = re.sub(r'\bhs\b','',s)
    return re.sub(r'\s+',' ',s).strip()
def sets_match(a, b):
    na, nb = norm_set(a), norm_set(b)
    return na==nb or na in nb or nb in na

def era_for(year, series=None):
    S = {'XY':'XY Era (2014-2016)','Sun & Moon':'Sun & Moon Era (2017-2019)',
         'Sword & Shield':'Sword & Shield Era (2020-2023)','Scarlet & Violet':'Scarlet & Violet Era (2023-2025)',
         'Mega Evolution':'Mega Evolution Era (2025-2026)','EX':'EX Era (2003-2007)'}
    if series in S: return S[series]
    y = int(str(year)[:4]) if year else 2020
    if y <= 2002: return 'Vintage Era (1999-2002)'
    if y <= 2007: return 'EX Era (2003-2007)'
    if y <= 2011: return 'DP / HGSS Era (2008-2011)'
    if y <= 2013: return 'BW Era (2012-2013)'
    if y <= 2016: return 'XY Era (2014-2016)'
    if y <= 2019: return 'Sun & Moon Era (2017-2019)'
    if y <= 2022: return 'Sword & Shield Era (2020-2023)'
    if y <= 2024: return 'Scarlet & Violet Era (2023-2025)'
    return 'Mega Evolution Era (2025-2026)'

def variant_price_key(v, tp_keys):
    """Map an app variant to its TCGplayer price key (mirrors build logic)."""
    k, lbl = v['key'], v['label'].lower()
    if k in VKEY and k in tp_keys: return k
    if 'reverse' in lbl and 'reverseHolofoil' in tp_keys: return 'reverseHolofoil'
    if '1st' in lbl:
        for c in ('1stEditionHolofoil','1stEdition'):
            if c in tp_keys: return c
    if 'unlimited' in lbl and '©' not in v['label']:
        for c in ('unlimitedHolofoil','unlimited'):
            if c in tp_keys: return c
    if lbl in ('standard','promo','holo','full art'):
        for c in ('holofoil','normal'):
            if c in tp_keys: return c
    return None

from species_config import SPECIES as SPECIES_CFG
d = json.load(open(os.path.join(here,'goodra_data.json')))
api_cards = {}
for s in SPECIES_CFG:
    sp, q = s['key'], s['query']
    for c in fetch(q, os.path.join(here,f'{sp}_refresh.json')):
        api_cards.setdefault(sp, {})[c['id']] = c

# index existing cards by API id where derivable
def api_id_of(card):
    if card['id'] in api_cards.get(card.get('species','goodra'),{}): return card['id']
    return None

updated = 0
claimed_by_card = {}
for card in d['cards']:
    sp = card.get('species','goodra')
    # dragonite cards use dr-* ids; match via set+number against API
    apic = None
    if card['id'] in api_cards.get(sp,{}):
        apic = api_cards[sp][card['id']]
    else:
        for a in api_cards.get(sp,{}).values():
            if sets_match(a['set']['name'], card['set']) and \
               a['number'].lower() == card['number'].split('/')[0].lower():
                apic = a; break
    if not apic: continue
    tp = apic.get('tcgplayer',{}).get('prices',{})
    cm = apic.get('cardmarket',{}).get('prices',{}) or {}
    claimed = set()
    cm_main = cm_rev = False
    for v in card['variants']:
        pk = variant_price_key(v, [k for k in tp if k not in claimed])
        if not pk: continue
        claimed.add(pk)
        p = tp[pk]
        v['market'], v['low'], v['mid'], v['high'] = p.get('market'), p.get('low'), p.get('mid'), p.get('high')
        rev = pk == 'reverseHolofoil'
        if rev and not cm_rev:
            v['cmAvg1'],v['cmAvg7'],v['cmAvg30'] = cm.get('reverseHoloAvg1'),cm.get('reverseHoloAvg7'),cm.get('reverseHoloAvg30'); cm_rev=True
        elif not rev and not cm_main:
            v['cmAvg1'],v['cmAvg7'],v['cmAvg30'] = cm.get('avg1'),cm.get('avg7'),cm.get('avg30'); cm_main=True
        if v.get('market') is not None:
            hist = v.setdefault('hist',[])
            if not hist or hist[-1]['d'] != today:
                hist.append({'d':today,'p':v['market']})
            else:
                hist[-1]['p'] = v['market']
            if len(hist) > 260: v['hist'] = hist[-260:]
        updated += 1

# detect brand-new API cards (goodra only auto-adds; dragonite list is checklist-driven,
# but new API cards there get added too so nothing slips through)
known_api_ids = set()
for card in d['cards']:
    known_api_ids.add(card['id'])
VLABEL = {'normal':'Non-Holo','holofoil':'Holo','reverseHolofoil':'Reverse Holo',
          '1stEdition':'1st Edition','1stEditionHolofoil':'1st Edition Holo',
          'unlimited':'Unlimited','unlimitedHolofoil':'Unlimited Holo'}
added_new = []
for sp in api_cards:
    for cid, c in api_cards[sp].items():
        if cid in known_api_ids: continue
        # skip if a spreadsheet row already covers it (dragonite set+number match)
        if any(x.get('species')==sp and sets_match(c['set']['name'], x['set']) and
               x['number'].split('/')[0].lower()==c['number'].lower() for x in d['cards']):
            continue
        tp = c.get('tcgplayer',{}).get('prices',{})
        cm = c.get('cardmarket',{}).get('prices',{}) or {}
        variants = []
        for key, p in (tp.items() or {'holofoil':{}}.items()):
            rev = key=='reverseHolofoil'
            variants.append({'key':key,'label':VLABEL.get(key,key),
                'market':p.get('market'),'low':p.get('low'),'mid':p.get('mid'),'high':p.get('high'),
                'cmAvg1':cm.get('reverseHoloAvg1') if rev else cm.get('avg1'),
                'cmAvg7':cm.get('reverseHoloAvg7') if rev else cm.get('avg7'),
                'cmAvg30':cm.get('reverseHoloAvg30') if rev else cm.get('avg30'),
                'hist':[{'d':today,'p':p['market']}] if p.get('market') is not None else []})
        if not variants:
            variants = [{'key':'holofoil','label':'Holo','market':None,'low':None,'mid':None,'high':None,
                         'cmAvg1':None,'cmAvg7':None,'cmAvg30':None,'hist':[]}]
        try:
            img = embed_img(c['images']['small'], cid, 'img_new')
        except Exception:
            img = None
        d['cards'].append({'id':cid,'name':c['name'],'set':c['set']['name'],
            'series':c['set']['series'],'era':era_for(c['set']['releaseDate'][:4], c['set']['series']),
            'number':c['number']+'/'+str(c['set'].get('printedTotal','?')),
            'rarity':c.get('rarity','—'),'date':c['set']['releaseDate'],'lang':'EN','species':sp,
            'added':today,'tcgUrl':c.get('tcgplayer',{}).get('url'),'img':img,'variants':variants})
        added_new.append(f"{sp}: {c['name']} ({c['set']['name']} #{c['number']})")

d['updatedAt'] = today
json.dump(d, open(os.path.join(here,'goodra_data.json'),'w'))
print(f"updated {updated} variants; new cards: {len(added_new)}")
for n in added_new: print("  NEW:", n)
