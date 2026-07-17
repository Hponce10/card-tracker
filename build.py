#!/usr/bin/env python3
"""Build goodra-tracker.html from tracker_template.html + goodra_data.json.
Entity-encodes all non-ASCII so the file is encoding-proof."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here,'tracker_template.html'), encoding='utf-8').read()
data = open(os.path.join(here,'goodra_data.json')).read()
assert '</script' not in data.lower()
upd = json.load(open(os.path.join(here,'goodra_data.json')))['updatedAt']
mon = {'01':'January','02':'February','03':'March','04':'April','05':'May','06':'June','07':'July','08':'August','09':'September','10':'October','11':'November','12':'December'}
y,m,d = upd.split('/')
out = tpl.replace('__DATA__', data).replace('__UPDATED__', f"{mon[m]} {int(d)}, {y}")
out = out.encode('ascii','xmlcharrefreplace').decode('ascii')
open(os.path.join(here,'goodra-tracker.html'),'w').write(out)
print('built goodra-tracker.html:', os.path.getsize(os.path.join(here,'goodra-tracker.html')), 'bytes')
