#!/usr/bin/env python3
"""Build web/index.html from tracker_template.html.

Transforms the artifact template into the hosted app:
- data loaded from data.json (fetch) instead of baked in
- live price overlay fetched client-side from api.pokemontcg.io
- external card images (imgS/imgL) instead of base64
- Supabase-backed collection sync + view-only share links
"""
import os, re

here = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(here, 'tracker_template.html'), encoding='utf-8').read()

SUPA_URL = "https://qtrminzcfwmrbblagvma.supabase.co"
SUPA_KEY = "sb_publishable_wRO5R7LI3zfB371N-tPVQQ_yucckato"

# --- 1. data placeholder -> mutable globals ---
t = t.replace("const DATA = __DATA__;",
"""let DATA = {cards: [], species: null};
let LIVE = false, READONLY = false, VIEWNAME = null;""")

# --- 2. species init becomes boot-time ---
t = t.replace("""const SPECIES = DATA.species || [{key:"goodra",label:"Goodra",dex:"#706"}];
let activeSpecies = localStorage.getItem("tracker.species") || SPECIES[0].key;
if(!SPECIES.some(s=>s.key===activeSpecies)) activeSpecies = SPECIES[0].key;""",
"""let SPECIES = [{key:"goodra",label:"Goodra",dex:"#706"}];
let activeSpecies = "goodra";""")

# --- 3. remove top-level calls that move into boot() ---
t = t.replace("}\nrebuildVariants();\nfunction renderSpecies(){", "}\nfunction renderSpecies(){")
t = t.replace("let portHist = recordPortfolio();", "let portHist = [];")

# --- 4. external images ---
t = t.replace('${c.img}', '${c.imgS}').replace('${x.c.img}', '${x.c.imgS}')
t = t.replace('c.img ?', 'c.imgS ?').replace('x.c.img ?', 'x.c.imgS ?')
# modal uses hi-res
t = t.replace('const art = c.imgS ? `<img src="${c.imgS}" alt="">`',
              'const art = c.imgS ? `<img src="${c.imgL||c.imgS}" alt="" loading="lazy">`')

# --- 5. updated-note gets an id; footer sync state ---
t = t.replace("Updated __UPDATED__.", '<span id="updNote">Updated __UPDATED__.</span>')
t = t.replace("collection saved in this browser (localStorage).",
              'collection <span id="syncState">syncing&hellip;</span>')

# --- 6. share button + dialog ---
t = t.replace('<button data-act="backup" title="Export or restore your collection">&#8645; Backup / restore</button>'
              if '&#8645;' in t else '<button data-act="backup" title="Export or restore your collection">⇅ Backup / restore</button>',
"""<button data-act="share" title="Get a view-only link to your collection">🔗 Share</button>
    <button data-act="backup" title="Export or restore your collection">⇅ Backup / restore</button>""")

t = t.replace("</dialog>\n\n<dialog id=\"bkModal\"", "</dialog>\n\n<dialog id=\"bkModal\"")  # anchor sanity
t = t.replace("""</dialog>
</div>""", """</dialog>
</div>""")

share_dialog = """
<dialog id="shModal"><button class="mclose" id="shCloseBtn" aria-label="Close">✕</button>
  <div class="bkbody">
    <h3 class="disp" style="margin:0">Share your collection</h3>
    <p class="cardmeta" style="margin:6px 0 10px">Anyone with this link sees a live, view-only copy of your collection — they can't change anything.</p>
    <label class="cardmeta" style="display:block;margin-bottom:8px">Display name
      <input id="shName" type="text" placeholder="Hector" style="font:inherit;width:100%;background:var(--surface2);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;margin-top:3px"></label>
    <input id="shLink" readonly style="font:12px ui-monospace,monospace;width:100%;background:var(--surface2);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:8px 9px" aria-label="Share link">
    <div class="buy" style="margin-top:10px"><a href="#" class="solid" data-act="shcopy">Copy link</a></div>
    <div id="shMsg" class="cardmeta" style="margin-top:8px"></div>
  </div>
</dialog>"""
t = t.replace('<script>', share_dialog + '\n<script>', 1)

# --- 7. readonly CSS ---
t = t.replace("</style>", """
body.readonly .ownbtn,body.readonly .editbtn,body.readonly .qty,body.readonly .priobtn,
body.readonly [data-act="backup"],body.readonly [data-act="share"],body.readonly .planner,body.readonly #newBanner{display:none!important}
.viewbar{background:var(--accent-soft);border:1px solid var(--accent);border-radius:12px;color:var(--accent-ink);
  padding:9px 14px;font-size:13.5px;margin-bottom:12px;display:none}
body.readonly .viewbar{display:block}
</style>""")
t = t.replace('<div id="newBanner"', '<div class="viewbar" id="viewBar"></div>\n<div id="newBanner"')

# --- 8. replace bootstrap with sync + boot code ---
old_boot = """checkNewCards();

renderSpecies(); refreshHeader(); renderCollection();"""
new_boot = r"""
/* ================= hosted-app boot: data, live prices, sync, share ================= */
const SUPA_URL = "%SUPA_URL%";
const SUPA_KEY = "%SUPA_KEY%";
async function rpc(fn, args){
  const res = await fetch(`${SUPA_URL}/rest/v1/rpc/${fn}`, {
    method:"POST", headers:{"Content-Type":"application/json","apikey":SUPA_KEY,"Authorization":"Bearer "+SUPA_KEY},
    body: JSON.stringify(args)});
  if(!res.ok) throw new Error("rpc "+fn+" "+res.status);
  return res.json();
}
function idKeys(){
  let sid = localStorage.getItem("ct.shareId"), ekey = localStorage.getItem("ct.editKey");
  if(!sid || !ekey){
    sid = crypto.randomUUID().replace(/-/g,"").slice(0,12);
    ekey = crypto.randomUUID().replace(/-/g,"");
    localStorage.setItem("ct.shareId", sid); localStorage.setItem("ct.editKey", ekey);
  }
  return {sid, ekey};
}
function collectionPayload(){
  return {owned, prio, budget: localStorage.getItem("goodra.budget")||""};
}
let syncTimer = null, lastPushed = "";
function syncState(txt, ok){ const el=$("#syncState"); if(el){ el.innerHTML = txt; el.style.color = ok===false?"var(--loss)":""; } }
function schedulePush(){
  if(READONLY) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(pushCollection, 1200);
}
async function pushCollection(){
  if(READONLY) return;
  const body = JSON.stringify(collectionPayload());
  const sig = body + "|" + (localStorage.getItem("ct.name")||"");
  if(sig === lastPushed) return;
  const {sid, ekey} = idKeys();
  try{
    const out = await rpc("ct_save_collection", {p_id:sid, p_key:ekey,
      p_name: localStorage.getItem("ct.name")||null, p_data: JSON.parse(body)});
    if(out === "ok"){ lastPushed = sig; syncState("synced to cloud ✓", true); }
    else syncState("sync refused ("+out+")", false);
  }catch(e){ syncState("offline — saved in this browser only", false); }
}
const _save = save0 => () => { save0(); schedulePush(); };
async function fetchSpeciesPrices(q, tries){
  for(let i=0;i<tries;i++){
    try{
      const r = await fetch(`https://api.pokemontcg.io/v2/cards?q=name:*${q}*&pageSize=250&select=id,tcgplayer,cardmarket`,
        {signal: AbortSignal.timeout(12000)});
      if(r.ok) return (await r.json()).data || [];
    }catch(e){ /* retry */ }
  }
  return [];
}
async function applyLiveOverlay(){
  try{
    const res = await Promise.all(["goodra","dragonite"].map(q => fetchSpeciesPrices(q, 2)));
    const ix = {};
    res.flat().forEach(c=>ix[c.id]=c);
    const today = new Date().toISOString().slice(0,10).replace(/-/g,"/");
    let n = 0;
    DATA.cards.forEach(c=>{
      const a = ix[c.apiId]; if(!a) return;
      const tp = (a.tcgplayer||{}).prices||{}, cm = (a.cardmarket||{}).prices||{};
      c.variants.forEach(v=>{
        if(!v.pk || !tp[v.pk]) return;
        const p = tp[v.pk];
        v.market=p.market; v.low=p.low; v.mid=p.mid; v.high=p.high; n++;
        if(v.cmRole==="main"){ v.cmAvg1=cm.avg1; v.cmAvg7=cm.avg7; v.cmAvg30=cm.avg30; }
        if(v.cmRole==="rev"){ v.cmAvg1=cm.reverseHoloAvg1; v.cmAvg7=cm.reverseHoloAvg7; v.cmAvg30=cm.reverseHoloAvg30; }
        if(p.market!=null){
          const h = v.hist || (v.hist=[]);
          if(!h.length || h[h.length-1].d!==today) h.push({d:today, p:p.market});
          else h[h.length-1].p = p.market;
        }
      });
    });
    LIVE = n > 0;
    if(LIVE){ const el=$("#updNote"); if(el) el.innerHTML = "Live prices &middot; updated just now."; }
  }catch(e){ LIVE = false; }
}
async function boot(){
  DATA = await (await fetch("data.json")).json();
  SPECIES = DATA.species || SPECIES;
  activeSpecies = localStorage.getItem("tracker.species") || SPECIES[0].key;
  if(!SPECIES.some(s=>s.key===activeSpecies)) activeSpecies = SPECIES[0].key;

  const viewId = new URLSearchParams(location.search).get("u");
  const myId = localStorage.getItem("ct.shareId");
  const overlayP = applyLiveOverlay();

  if(viewId && viewId !== myId){
    READONLY = true;
    document.body.classList.add("readonly");
    try{
      const col = await rpc("ct_get_collection", {p_id: viewId});
      if(col && col.data){
        owned = {}; prio = {};
        Object.assign(owned, col.data.owned||{}); Object.assign(prio, col.data.prio||{});
        Object.keys(owned).forEach(k=>{ if(typeof owned[k]==="number") owned[k]={q:owned[k]}; });
        VIEWNAME = col.name || "a collector";
        $("#viewBar").innerHTML = `You're viewing <b>${VIEWNAME}</b>'s collection (read-only). Want your own tracker? <a href="${location.pathname}">Start here</a>.`;
      } else {
        $("#viewBar").textContent = "Collection not found — the link may be wrong.";
      }
    }catch(e){ $("#viewBar").textContent = "Couldn't load that collection right now."; }
    syncState("view-only", true);
  } else {
    // owner: reconcile with cloud copy
    try{
      const {sid} = idKeys();
      const col = await rpc("ct_get_collection", {p_id: sid});
      const localTs = parseInt(localStorage.getItem("ct.lastLocalEdit")||"0");
      if(col && col.data && col.data.owned &&
         (!Object.keys(owned).length || new Date(col.updated_at).getTime() > localTs)){
        owned = col.data.owned; prio = col.data.prio||{};
        Object.keys(owned).forEach(k=>{ if(typeof owned[k]==="number") owned[k]={q:owned[k]}; });
        if(col.data.budget != null) localStorage.setItem("goodra.budget", col.data.budget);
        localStorage.setItem("goodra.owned", JSON.stringify(owned));
        localStorage.setItem("goodra.prio", JSON.stringify(prio));
      }
      syncState("synced to cloud ✓", true);
      pushCollection();
    }catch(e){ syncState("offline — saved in this browser only", false); }
  }

  // render immediately with baked prices; live overlay re-renders when it lands
  rebuildVariants();
  if(!READONLY) checkNewCards();
  renderSpecies(); refreshHeader(); renderCollection();
  overlayP.then(()=>{
    if(!LIVE) return;
    if(!READONLY) portHist = recordPortfolio();
    refreshHeader();
    const visible = ["collection","market","showcase","binder"].find(s=>!$("#"+s).hidden);
    ({collection:renderCollection, market:renderMarket, showcase:renderShowcase, binder:renderBinder})[visible]();
  });
  if(!READONLY && !LIVE) portHist = recordPortfolio();
}
boot();"""
new_boot = new_boot.replace("%SUPA_URL%", SUPA_URL).replace("%SUPA_KEY%", SUPA_KEY)
assert old_boot in t
t = t.replace(old_boot, new_boot)

# --- 9. save()/savePrio() also push to cloud; record local edit time; readonly guards ---
t = t.replace('const save = () => localStorage.setItem("goodra.owned", JSON.stringify(owned));',
"""const save = () => { if(READONLY) return;
  localStorage.setItem("goodra.owned", JSON.stringify(owned));
  localStorage.setItem("ct.lastLocalEdit", String(Date.now()));
  schedulePush(); };""")
t = t.replace('const savePrio = () => localStorage.setItem("goodra.prio", JSON.stringify(prio));',
"""const savePrio = () => { if(READONLY) return;
  localStorage.setItem("goodra.prio", JSON.stringify(prio));
  localStorage.setItem("ct.lastLocalEdit", String(Date.now()));
  schedulePush(); };""")

# --- 10. share dialog actions ---
t = t.replace("""    if(a==="backup") openBackup();""",
"""    if(a==="backup") openBackup();
    else if(a==="share"){
      const {sid} = idKeys();
      $("#shName").value = localStorage.getItem("ct.name")||"";
      $("#shLink").value = location.origin + location.pathname + "?u=" + sid;
      $("#shMsg").textContent = ""; $("#shModal").showModal();
      pushCollection();
    }
    else if(a==="shcopy"){
      localStorage.setItem("ct.name", $("#shName").value.trim());
      pushCollection();
      navigator.clipboard.writeText($("#shLink").value).then(
        ()=>{ $("#shMsg").textContent = "Link copied — send it to anyone."; $("#shMsg").className="cardmeta ok"; },
        ()=>{ $("#shMsg").textContent = "Copy failed — select the link and copy manually."; });
    }""")
t = t.replace("""$("#bkCloseBtn").addEventListener("click",()=>$("#bkModal").close());""",
"""$("#bkCloseBtn").addEventListener("click",()=>$("#bkModal").close());
$("#shCloseBtn").addEventListener("click",()=>$("#shModal").close());
$("#shModal").addEventListener("click",e=>{ if(e.target===$("#shModal")) $("#shModal").close(); });
document.addEventListener("input", e=>{ if(e.target.id==="shName") localStorage.setItem("ct.name", e.target.value.trim()); });""")

# --- 11. readonly guard in the click handler for edit actions ---
t = t.replace("""  } else if(t.dataset.own){""",
"""  } else if(READONLY && (t.dataset.own||t.dataset.q||t.dataset.ed||t.dataset.pr)){
    return;
  } else if(t.dataset.own){""")

# --- 12. backups carry the sync identity so another device joins the same cloud collection ---
t = t.replace('return JSON.stringify({app:"goodra-tracker", v:2, exported:new Date().toISOString().slice(0,10), owned}, null, 1);',
"""const ids = idKeys();
  return JSON.stringify({app:"goodra-tracker", v:2, exported:new Date().toISOString().slice(0,10), owned,
    sync:{sid:ids.sid, ekey:ids.ekey, name:localStorage.getItem("ct.name")||null}}, null, 1);""")
t = t.replace("""  if(mode==="replace") owned = map;
  else Object.assign(owned, map);
  save(); refreshHeader(); renderCollection();""",
"""  if(mode==="replace") owned = map;
  else Object.assign(owned, map);
  if(parsed.sync && parsed.sync.sid && parsed.sync.ekey){
    localStorage.setItem("ct.shareId", parsed.sync.sid);
    localStorage.setItem("ct.editKey", parsed.sync.ekey);
    if(parsed.sync.name) localStorage.setItem("ct.name", parsed.sync.name);
  }
  save(); refreshHeader(); renderCollection();""")

# --- date + entity-encode ---
import datetime
t = t.replace("__UPDATED__", datetime.date.today().strftime("%B %-d, %Y"))
t = t.encode("ascii", "xmlcharrefreplace").decode("ascii")
open(os.path.join(here, "web", "index.html"), "w").write(t)
print("web/index.html:", os.path.getsize(os.path.join(here,"web","index.html"))//1024, "KB")
