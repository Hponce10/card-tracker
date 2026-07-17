#!/usr/bin/env python3
"""Add API-sourced species to goodra_data.json (pseudo-legendary expansion).
Cards are built straight from api.pokemontcg.io — no images embedded (the web
app uses external image URLs via export_web.py; the artifact build filters to
goodra+dragonite). Skips species already present. Idempotent."""
import json, os, subprocess
from species_config import SPECIES

here = os.path.dirname(os.path.abspath(__file__))
BASELINE = '2026/07/17'   # imported backlog: not flagged as "new" beyond today

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

VLABEL = {'normal':'Non-Holo','holofoil':'Holo','reverseHolofoil':'Reverse Holo',
          '1stEdition':'1st Edition','1stEditionHolofoil':'1st Edition Holo',
          'unlimited':'Unlimited','unlimitedHolofoil':'Unlimited Holo'}

d = json.load(open(os.path.join(here,'goodra_data.json')))
have_species = {c.get('species','goodra') for c in d['cards']}

for sp in SPECIES:
    if sp['key'] in have_species:
        continue
    out = os.path.join(here, f"{sp['key']}_refresh.json")
    subprocess.run(['curl','-sf','--max-time','90',
        f"https://api.pokemontcg.io/v2/cards?q=name:*{sp['query']}*&pageSize=250",
        '-o', out], check=True)
    cards = json.load(open(out))['data']
    added = 0
    for c in sorted(cards, key=lambda x: x['set']['releaseDate']):
        tp = c.get('tcgplayer',{}).get('prices',{})
        cm = c.get('cardmarket',{}).get('prices',{}) or {}
        variants = []
        cm_main = cm_rev = False
        for key, p in tp.items():
            rev = key == 'reverseHolofoil'
            a1=a7=a30=None
            if rev and not cm_rev:
                a1,a7,a30 = cm.get('reverseHoloAvg1'),cm.get('reverseHoloAvg7'),cm.get('reverseHoloAvg30'); cm_rev=True
            elif not rev and not cm_main:
                a1,a7,a30 = cm.get('avg1'),cm.get('avg7'),cm.get('avg30'); cm_main=True
            variants.append({'key':key,'label':VLABEL.get(key,key),
                'market':p.get('market'),'low':p.get('low'),'mid':p.get('mid'),'high':p.get('high'),
                'cmAvg1':a1,'cmAvg7':a7,'cmAvg30':a30,
                'hist':[{'d':BASELINE,'p':p['market']}] if p.get('market') is not None else []})
        if not variants:
            variants = [{'key':'holofoil','label':'Holo','market':None,'low':None,'mid':None,'high':None,
                         'cmAvg1':None,'cmAvg7':None,'cmAvg30':None,'hist':[]}]
        d['cards'].append({'id':c['id'],'name':c['name'],'set':c['set']['name'],
            'series':c['set']['series'],'era':era_for(c['set']['releaseDate'][:4], c['set']['series']),
            'number':c['number']+'/'+str(c['set'].get('printedTotal','?')),
            'rarity':c.get('rarity','—'),'date':c['set']['releaseDate'],'lang':'EN',
            'species':sp['key'],'added':BASELINE,
            'tcgUrl':c.get('tcgplayer',{}).get('url'),'img':None,'variants':variants})
        added += 1
    print(f"{sp['label']}: +{added} cards")

d['species'] = [{'key':s['key'],'label':s['label'],'dex':s['dex']} for s in SPECIES]
json.dump(d, open(os.path.join(here,'goodra_data.json'),'w'))
from collections import Counter
print('totals:', dict(Counter(c.get('species') for c in d['cards'])))
