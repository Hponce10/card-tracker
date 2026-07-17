#!/usr/bin/env python3
"""Export web/data.json for the hosted app:
- strips base64 images, adds external image URLs (imgS/imgL) for API-matched cards
- annotates each card with apiId and each variant with pk (TCGplayer price key)
  and cmRole (main/rev) so the browser can overlay live prices client-side.
Requires goodra_refresh.json / dragonite_refresh.json (written by fetch_data.py)."""
import json, os, re, unicodedata

here = os.path.dirname(os.path.abspath(__file__))

def norm_set(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    s = s.replace(' (jp)','').replace('-',' ')
    for junk in (' black star',' base set',' the'):
        s = s.replace(junk,'')
    s = re.sub(r'\bhs\b','',s)
    return re.sub(r'\s+',' ',s).strip()
def sets_match(a,b):
    na, nb = norm_set(a), norm_set(b)
    return na==nb or na in nb or nb in na

from species_config import SPECIES as SPECIES_CFG
api = {}
for s in SPECIES_CFG:
    sp = s['key']
    path = os.path.join(here, f'{sp}_refresh.json')
    if not os.path.exists(path): continue
    for c in json.load(open(path))['data']:
        api.setdefault(sp,[]).append(c)

def variant_price_key(v, tp_keys):
    k, lbl = v['key'], v['label'].lower()
    if k in ('normal','holofoil','reverseHolofoil') and k in tp_keys: return k
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

d = json.load(open(os.path.join(here,'goodra_data.json')))
matched = 0
for card in d['cards']:
    sp = card.get('species','goodra')
    apic = None
    for a in api.get(sp,[]):
        if a['id']==card['id'] or (sets_match(a['set']['name'], card['set']) and
            a['number'].lower()==card['number'].split('/')[0].lower()):
            apic = a; break
    card.pop('img', None)
    if not apic:
        card['apiId'] = None; card['imgS'] = None; card['imgL'] = None
        continue
    matched += 1
    card['apiId'] = apic['id']
    card['imgS'] = apic['images']['small']
    card['imgL'] = apic['images']['large']
    tp = apic.get('tcgplayer',{}).get('prices',{})
    claimed, cm_main, cm_rev = set(), False, False
    for v in card['variants']:
        pk = variant_price_key(v, [k for k in tp if k not in claimed])
        v['pk'] = pk
        v['cmRole'] = None
        if pk:
            claimed.add(pk)
            if pk=='reverseHolofoil' and not cm_rev: v['cmRole']='rev'; cm_rev=True
            elif pk!='reverseHolofoil' and not cm_main: v['cmRole']='main'; cm_main=True

os.makedirs(os.path.join(here,'web'), exist_ok=True)
json.dump(d, open(os.path.join(here,'web','data.json'),'w'))
print(f"web/data.json: {os.path.getsize(os.path.join(here,'web','data.json'))//1024} KB, api-matched cards: {matched}/{len(d['cards'])}")
