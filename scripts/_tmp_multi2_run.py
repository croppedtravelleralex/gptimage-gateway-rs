import json, concurrent.futures, time, urllib.request, uuid
BASE="http://127.0.0.1:8013"
EMAILS=["qaflowwrg2ptcd05@proton.me","ivetterock54353@outlook.com"]

def call(method, path, body=None, timeout=80, email=None):
    data=None if body is None else json.dumps(body).encode()
    h={"Content-Type":"application/json"}
    if email: h["X-Preferred-Account-Email"]=email
    req=urllib.request.Request(BASE+path, data=data, method=method, headers=h)
    t0=time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, time.time()-t0, json.loads(r.read()), None
    except Exception as e:
        err=str(e)[:300]
        try:
            if hasattr(e,"read"): err=e.read().decode("utf-8","replace")[:300]
        except Exception: pass
        return getattr(e,"code",None), time.time()-t0, None, err

picked=[]
for email in EMAILS:
    _,el,q,qe=call("POST","/v1/quota/refresh",{},timeout=60,email=email)
    print("QUOTA", email, q, "el", round(el,2), "err", qe)
    if not q or not q.get("imageable"):
        raise SystemExit(2)
    picked.append(email)

def one(i, email):
    time.sleep(i*4.0)
    uid=uuid.uuid4().hex[:6]
    st,el,j,err=call("POST","/v1/images/generations",{"model":"gpt-image-2","prompt":f"green pear still life {uid}","n":1,"size":"1024x1024","response_format":"b64_json"},timeout=80,email=email)
    b64=""
    if isinstance(j,dict):
        try: b64=((j.get("data") or [{}])[0] or {}).get("b64_json") or ""
        except Exception: b64=""
    ok=st==200 and len(b64)>1000
    print(f"IMG[{i}] {email} status={st} ok={ok} el={el:.1f}s b64={len(b64)} err={(err or '')[:140]}")
    return {"i":i,"email":email,"ok":ok,"el":round(el,1),"st":st}

t0=time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    rows=[f.result() for f in [ex.submit(one,i,e) for i,e in enumerate(picked)]]
print("SUMMARY", {"ok":f"{sum(1 for r in rows if r['ok'])}/2","wall":round(time.time()-t0,1),"rows":rows})
raise SystemExit(0 if all(r["ok"] for r in rows) else 1)
