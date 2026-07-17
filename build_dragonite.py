#!/usr/bin/env python3
"""Build the Dragonite species dataset: xlsx checklist (authoritative variant list)
enriched with live prices/images from the Pokemon TCG API, merged into goodra_data.json."""
import json, re, os, base64, subprocess
import openpyxl

here = os.path.dirname(os.path.abspath(__file__))

# ---- API cards indexed by (normalized set, number) ----
api = json.load(open(os.path.join(here, 'dragonite.json')))['data']
SETMAP = {  # xlsx set name -> API set name
    'fossil':'Fossil','team rocket':'Team Rocket','neo destiny':'Neo Destiny',
    'legendary collection':'Legendary Collection','wizards promos':'Wizards Black Star Promos',
    'wizards black star promos':'Wizards Black Star Promos','expedition':'Expedition Base Set',
    'ex dragon':'Dragon','dragon':'Dragon','ex team rocket returns':'Team Rocket Returns',
    'ex delta species':'Delta Species','ex dragon frontiers':'Dragon Frontiers',
    'legends awakened':'Legends Awakened','supreme victors':'Supreme Victors',
    'triumphant':'HS—Triumphant','dragon vault':'Dragon Vault','plasma freeze':'Plasma Freeze',
    'furious fists':'Furious Fists','roaring skies':'Roaring Skies','evolutions':'Evolutions',
    'sun & moon':'Sun & Moon','sun & moon base set':'Sun & Moon','dragon majesty':'Dragon Majesty',
    'team up':'Team Up','unified minds':'Unified Minds','evolving skies':'Evolving Skies',
    'pokemon go':'Pokémon GO','silver tempest':'Silver Tempest',
    'swsh promos':'SWSH Black Star Promos','swsh black star promos':'SWSH Black Star Promos',
    'sm promos':'SM Black Star Promos','obsidian flames':'Obsidian Flames',
    '151':'151','pokemon card 151':'151','ascended heroes':'Ascended Heroes',
}
api_ix = {}
for c in api:
    api_ix[(c['set']['name'].lower(), c['number'].lower())] = c

def era_for(year, series=None):
    S = {'Base':'Vintage Era (1999-2002)','Neo':'Vintage Era (1999-2002)','E-Card':'Vintage Era (1999-2002)',
         'EX':'EX Era (2003-2007)','Diamond & Pearl':'DP / HGSS Era (2008-2011)','Platinum':'DP / HGSS Era (2008-2011)',
         'HeartGold & SoulSilver':'DP / HGSS Era (2008-2011)','Black & White':'BW Era (2012-2013)',
         'XY':'XY Era (2014-2016)','Sun & Moon':'Sun & Moon Era (2017-2019)',
         'Sword & Shield':'Sword & Shield Era (2020-2023)','Scarlet & Violet':'Scarlet & Violet Era (2023-2025)',
         'Mega Evolution':'Mega Evolution Era (2025-2026)'}
    if series in S: return S[series]
    y = int(year) if year else 2020
    if y <= 2002: return 'Vintage Era (1999-2002)'
    if y <= 2007: return 'EX Era (2003-2007)'
    if y <= 2011: return 'DP / HGSS Era (2008-2011)'
    if y <= 2013: return 'BW Era (2012-2013)'
    if y <= 2016: return 'XY Era (2014-2016)'
    if y <= 2019: return 'Sun & Moon Era (2017-2019)'
    if y <= 2022: return 'Sword & Shield Era (2020-2023)'
    if y <= 2024: return 'Scarlet & Violet Era (2023-2025)'
    return 'Mega Evolution Era (2025-2026)'

def parse_est(s):
    if not s or not isinstance(s,str): return (None,None)
    nums = [float(n.replace(',','')) for n in re.findall(r'[\d,]+(?:\.\d+)?', s)]
    if not nums: return (None,None)
    if len(nums)==1: return (nums[0], None)
    return (nums[0], nums[1])

def price_keys(variant, holo):
    v = variant.lower()
    if 'reverse' in v: return ['reverseHolofoil']
    if '1st' in v: return ['1stEditionHolofoil','1stEdition'] if holo else ['1stEdition','1stEditionHolofoil']
    if 'unlimited' in v and '©' not in variant and 'c)' not in v:
        return ['unlimitedHolofoil','unlimited'] if holo else ['unlimited','unlimitedHolofoil']
    if v in ('standard','full art','promo','holo'): return ['holofoil','normal'] if holo else ['normal','holofoil']
    return []  # specialty variants (errors, stamps, copyright, cosmos...) -> est range only

wb = openpyxl.load_workbook(os.path.join(here,'dragonite_tracker.xlsx'))
rows = [r for r in wb.active.iter_rows(values_only=True)]
data_rows = [r for r in rows[1:] if r[1] is not None and r[1] != 'Card Name']

# group by (set, number)
groups, order = {}, []
for r in data_rows:
    name, st, num, variant, rarity, year, lang, est = r[1], r[2], str(r[3]), r[4], r[5], r[6], r[7], r[8]
    if name and 'TOTAL' in str(name).upper(): continue
    key = (st, num)
    if key not in groups:
        groups[key] = {'name':name,'set':st,'number':num,'rarity':rarity,'year':year,'lang':lang,'rows':[]}
        order.append(key)
    groups[key]['rows'].append(r)

cards, matched_imgs = [], {}
for key in order:
    g = groups[key]
    name, st, num = g['name'], g['set'], g['number']
    year = g['year'] or 2020
    lang = 'JP' if g['lang']=='Japanese' else ('EN' if g['lang'] in ('English', None) else 'INT')
    apic = api_ix.get((SETMAP.get(str(st).lower(), str(st)).lower(), str(num).split('/')[0].lower()))
    holo = ('holo' in str(name).lower() and 'non-holo' not in str(name).lower()) or 'holo' in str(g['rarity'] or '').lower()
    tp = (apic or {}).get('tcgplayer',{}).get('prices',{})
    cm = (apic or {}).get('cardmarket',{}).get('prices',{}) or {}
    claimed = set()
    cm_claimed = {'main':False,'rev':False}
    variants = []
    for r in g['rows']:
        variant, est, notes = r[4] or 'Standard', r[8], r[15]
        lo, hi = parse_est(est)
        pk = None
        for k in price_keys(variant, holo):
            if k in tp and k not in claimed: pk = k; break
        p = tp.get(pk, {}) if pk else {}
        if pk: claimed.add(pk)
        rev = pk == 'reverseHolofoil'
        a1=a7=a30=None
        if pk and rev and not cm_claimed['rev']:
            a1,a7,a30 = cm.get('reverseHoloAvg1'),cm.get('reverseHoloAvg7'),cm.get('reverseHoloAvg30'); cm_claimed['rev']=True
        elif pk and not rev and not cm_claimed['main']:
            a1,a7,a30 = cm.get('avg1'),cm.get('avg7'),cm.get('avg30'); cm_claimed['main']=True
        v = {'key': re.sub(r'[^a-z0-9]+','-',str(variant).lower()).strip('-') or 'std',
             'label': str(variant),
             'market': p.get('market'), 'low': p.get('low'), 'mid': p.get('mid'), 'high': p.get('high'),
             'cmAvg1':a1,'cmAvg7':a7,'cmAvg30':a30,
             'estLow': lo, 'estHigh': hi,
             'hist': [{'d':'2026/07/17','p':p['market']}] if p.get('market') is not None else []}
        if notes: v['note'] = str(notes)
        if notes and ('GRAIL' in str(notes).upper() or 'grail' in str(notes).lower()): v['grail'] = True
        variants.append(v)
    cid = 'dr-' + re.sub(r'[^a-z0-9]+','-',f"{st}-{num}".lower()).strip('-')
    card = {'id': cid, 'name': str(name), 'set': str(st) + (' (JP)' if lang=='JP' else ''),
            'series': (apic or {}).get('set',{}).get('series'),
            'era': era_for(year, (apic or {}).get('set',{}).get('series')),
            'number': str(num), 'rarity': str(g['rarity'] or '—'), 'date': str(year), 'lang': lang,
            'jpExclusive': lang=='JP', 'species':'dragonite', 'added':'2026/07/17',
            'tcgUrl': (apic or {}).get('tcgplayer',{}).get('url'), 'img': None, 'variants': variants}
    if apic: matched_imgs[cid] = apic['images']['small']
    cards.append(card)

# download + embed images for API-matched cards
os.makedirs(os.path.join(here,'img_dr'), exist_ok=True)
from PIL import Image
for cid, url in matched_imgs.items():
    png = os.path.join(here,'img_dr',cid+'.png'); jpg = png.replace('.png','.jpg')
    if not os.path.exists(jpg):
        if not os.path.exists(png):
            subprocess.run(['curl','-s','--max-time','30','-A','Mozilla/5.0 (Macintosh)','-o',png,url],check=True)
        Image.open(png).convert('RGB').save(jpg,'JPEG',quality=62,optimize=True)
    for c in cards:
        if c['id']==cid:
            c['img'] = 'data:image/jpeg;base64,' + base64.b64encode(open(jpg,'rb').read()).decode()

d = json.load(open(os.path.join(here,'goodra_data.json')))
for c in d['cards']: c.setdefault('species','goodra')
d['cards'] = [c for c in d['cards'] if c.get('species')!='dragonite'] + cards
d['species'] = [{'key':'goodra','label':'Goodra','dex':'#706'},{'key':'dragonite','label':'Dragonite','dex':'#149'}]
json.dump(d, open(os.path.join(here,'goodra_data.json'),'w'))
nmatched = len(matched_imgs)
print(f"dragonite cards: {len(cards)}, variants: {sum(len(c['variants']) for c in cards)}, API-matched: {nmatched}")
print("json KB:", os.path.getsize(os.path.join(here,'goodra_data.json'))//1024)
