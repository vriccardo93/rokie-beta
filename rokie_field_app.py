from __future__ import annotations
import json, os, re, html
from datetime import date
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

PORT = int(os.getenv('PORT', '8080'))
BASE = 'https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1'

COMMON_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://dati.normattiva.it',
    'Referer': 'https://dati.normattiva.it/',
    'User-Agent': (
        'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 '
        'Mobile/15E148 Safari/604.1 ROKIE/0.2.1'
    ),
    'Connection': 'close',
}
CDS = 'urn:nir:stato:decreto.legislativo:1992-04-30;285'
L120 = 'urn:nir:stato:legge:2010-07-29;120'

RULES = [
    (('targhino','vecchio contrassegno','vecchia targa ciclomotore'), [(L120,14,'L. 120/2010 art. 14','Disciplina transitoria dei vecchi contrassegni'),(CDS,97,'CdS art. 97','Targa e certificato ciclomotori'),(CDS,193,'CdS art. 193','RCA: da verificare autonomamente')]),
    (('stupefacenti','droga','test salivare','sostanze'), [(CDS,187,'CdS art. 187','Guida dopo assunzione di sostanze stupefacenti')]),
    (('alcol','alcool','etilometro','ebbrezza'), [(CDS,186,'CdS art. 186','Guida sotto influenza dell’alcol')]),
    (('senza assicurazione','assicurazione scaduta','non assicurato','rca'), [(CDS,193,'CdS art. 193','Obbligo RCA')]),
    (('senza patente','patente mai conseguita','patente sospesa','patente revocata'), [(CDS,116,'CdS art. 116','Patenti e abilitazioni')]),
    (('revisione','revisione scaduta'), [(CDS,80,'CdS art. 80','Revisioni')]),
    (('senza documenti','non ha i documenti','carta di circolazione'), [(CDS,180,'CdS art. 180','Documenti di circolazione e guida')]),
    (('incidente','sinistro','omissione di soccorso','fuga dopo incidente'), [(CDS,189,'CdS art. 189','Comportamento in caso di incidente')]),
]

class Extractor(HTMLParser):
    def __init__(self): super().__init__(); self.p=[]
    def handle_data(self,d):
        s=' '.join(d.split())
        if s:self.p.append(s)

def clean_html(s):
    x=Extractor(); x.feed(html.unescape(s or '')); return ' '.join(x.p)

def first_key(obj, names):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k in names and v not in (None,'',[]): return v
        for v in obj.values():
            r=first_key(v,names)
            if r not in (None,'',[]): return r
    elif isinstance(obj,list):
        for v in obj:
            r=first_key(v,names)
            if r not in (None,'',[]): return r
    return None

def api(path, payload=None, timeout=18):
    url=f"{BASE}/{path.lstrip('/')}"
    data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers=dict(COMMON_HEADERS)
    if payload is not None:
        headers['Content-Type']='application/json'
    req=Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    try:
        with urlopen(req,timeout=timeout) as r:
            raw=r.read().decode('utf-8', errors='replace')
            return json.loads(raw) if raw.strip() else {}
    except HTTPError as e:
        try:
            body=e.read().decode('utf-8', errors='replace')
        except Exception:
            body=''
        body=' '.join(body.split())[:500]
        raise RuntimeError(f"Normattiva HTTP {e.code} su {path}" + (f" · {body}" if body else '')) from e
    except URLError as e:
        raise RuntimeError(f"Connessione Normattiva fallita: {e.reason}") from e

def article(urn, art, ref):
    full=f"{urn.split('!vig=',1)[0]}~art{art}!vig={ref}"
    d=api('atto/dettaglio-atto-urn', {'urn':full})
    raw=first_key(d, {'articoloHtml','testoArticolo','articolo'})
    if isinstance(raw,dict): raw=first_key(raw, {'articoloHtml','testo','html'})
    if not isinstance(raw,str): raise RuntimeError('Testo articolo non trovato')
    text=clean_html(raw)
    if len(re.sub(r'\s+','',text))<30: raise RuntimeError('Testo articolo vuoto')
    return {'text':text,'url':f"https://www.normattiva.it/uri-res/N2Ls?{quote(full,safe=':;~!=@')}"}

def plan(case):
    s=' '.join(case.lower().split()); out=[]; seen=set()
    for needles, targets in RULES:
        if any(n in s for n in needles):
            for t in targets:
                key=(t[0],t[1])
                if key not in seen: seen.add(key); out.append(t)
    return out

INDEX='''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1020"><title>ROKIE Field Beta</title><style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#080b12;color:#eef2ff}.wrap{max-width:760px;margin:auto;padding:22px 16px 50px}.brand{font-size:34px;font-weight:900;letter-spacing:-1px}.tag{color:#9aa7bd;margin:4px 0 22px}.card{background:#111725;border:1px solid #27314a;border-radius:18px;padding:16px;margin:12px 0}textarea,input{width:100%;background:#090d17;border:1px solid #33405e;color:#fff;border-radius:14px;padding:14px;font-size:16px}textarea{min-height:150px;resize:vertical}button{width:100%;padding:15px;border:0;border-radius:14px;font-size:17px;font-weight:800;background:#6d5efc;color:white;margin-top:12px}.status{font-size:14px}.ok{color:#73e2a7}.bad{color:#ff8b8b}.src h3{margin:0 0 7px}.src p{color:#cbd5e1;line-height:1.45}.reason{color:#93a4bd;font-size:14px}.warn{background:#251b0c;border-color:#6b4d18}.small{font-size:13px;color:#93a4bd}a{color:#aab6ff}</style></head><body><main class="wrap"><div class="brand">ROKIE</div><div class="tag">Field Beta · fonti prima, risposta dopo · build 0.2.1</div><div class="card"><div id="health" class="status">Controllo Normattiva…</div></div><div class="card"><label>Data di riferimento</label><input id="ref" type="date"><br><br><label>Descrivi il caso operativo</label><textarea id="case" placeholder="Es. Conducente sottoposto a test salivare per stupefacenti…"></textarea><button onclick="analyze()">Analizza fonti</button><div class="small" style="margin-top:10px">Non inserire nomi, targhe, CF o altri dati personali reali.</div></div><div id="out"></div></main><script>
ref.value=new Date().toISOString().slice(0,10); fetch('/api/health').then(r=>r.json()).then(x=>{health.innerHTML=x.normattiva?'<span class="ok">● Normattiva live</span>':'<span class="bad">● Normattiva non raggiungibile</span> · '+x.message}).catch(()=>health.innerHTML='<span class="bad">● Health check fallito</span>');
async function analyze(){const c=document.getElementById('case').value.trim(); if(!c)return; out.innerHTML='<div class="card">Ricerca delle fonti ufficiali…</div>'; try{let r=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case:c,reference_date:ref.value})}); let x=await r.json(); if(!r.ok)throw new Error(x.error||'Errore'); let h=''; if(x.sources.length===0)h='<div class="card warn"><b>Nessuna fonte determinata con sufficiente confidenza.</b><p>Questa beta non completa a intuito: il caso va ampliato o gestito dalla ricerca libera della futura versione AI.</p></div>'; for(const s of x.sources){h+=`<div class="card src"><h3>${esc(s.label)}</h3><div class="reason">${esc(s.reason)}</div>${s.error?`<p class="bad">${esc(s.error)}</p>`:`<p>${esc(s.text)}</p><a href="${s.url}" target="_blank">Apri su Normattiva ↗</a>`}</div>`} out.innerHTML=h;}catch(e){out.innerHTML='<div class="card warn"><b>Errore</b><p>'+esc(e.message)+'</p></div>'}}
function esc(s){return String(s||'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}</script></body></html>'''

class H(BaseHTTPRequestHandler):
    def sendj(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=='/':
            b=INDEX.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path=='/api/health':
            try: api('tipologiche/estensioni'); self.sendj({'app':'ok','normattiva':True,'message':'Normattiva Open Data raggiungibile','build':'0.2.1'})
            except Exception as e: self.sendj({'app':'ok','normattiva':False,'message':str(e),'build':'0.2.1'})
            return
        self.sendj({'error':'not found'},404)
    def do_POST(self):
        if self.path!='/api/analyze': return self.sendj({'error':'not found'},404)
        try:
            n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n) or b'{}'); case=str(data.get('case','')).strip(); ref=str(data.get('reference_date') or date.today().isoformat())
            if not case: return self.sendj({'error':'Caso vuoto'},400)
            sources=[]
            for urn,art,label,reason in plan(case):
                try: x=article(urn,art,ref); sources.append({'label':label,'reason':reason,**x})
                except Exception as e: sources.append({'label':label,'reason':reason,'error':f'{type(e).__name__}: {e}'})
            self.sendj({'case':case,'reference_date':ref,'sources':sources,'principle':'source-first'})
        except Exception as e: self.sendj({'error':f'{type(e).__name__}: {e}'},500)
    def log_message(self,fmt,*args): print(fmt%args,flush=True)

if __name__=='__main__':
    print(f'ROKIE listening on 0.0.0.0:{PORT}',flush=True)
    ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
