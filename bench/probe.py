#!/usr/bin/env python3
"""Local probe battery. Runs prompt-rule variants against the real patient over a long
conversation of realistic clinical questions and scores the replies with word rules.
Ollama only, no cloud cost.  python3 bench/probe.py [--runs 3] [--variants V0,Vnone] [--temp 0.6]
"""
import argparse, hashlib, json, os, random, re, subprocess, sys, time, urllib.request
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
OLLAMA="http://127.0.0.1:11434"
CASES=["graham","travis","lewis","springfield"]
CANNED=re.compile(r"don'?t know that word|not following you",re.I)
ASK_MEANING=re.compile(r"what (does|do) (that|it|you) mean|not sure what (that|it|those) (is|are|means)|never heard|what is that|what'?s that|don'?t know what|not familiar",re.I)
DENIAL=re.compile(r"that'?s all",re.I)
JARGON_RX=re.compile(r"cholelith|cholang|biliary|icterus|hematemesis|melena|nsaid|dyspep|peritonit|anhedonia|polyuria|dyspareunia|diaphoresis|menorrhagia|intermenstrual|vasomotor|dexa|hepatomeg|murphy|scleral|pruritus|dysuria|hematuria|orthopnea",re.I)
SPECIFIC=re.compile(r"\d|last year|years ago|every (day|year)|normal range|checked",re.I)
LEAK={"graham":r"\btea\b|lighter|pale|operation|frightened",
      "travis":r"ibuprofen|\bblack\b|greenish|coffee ground",
      "lewis":r"suicide|harm(ing)? (my|any)|more than (i|you) used to|sexually",
      "springfield":None}
def rules_variant(system, name):
    lines=system.split("\n"); i=lines.index("RULES")
    head, rules = lines[:i+1], lines[i+1:]
    # strip by content, not by number: the live numbering has changed since 1 September
    keep=[r for r in rules if not re.search(r"word you would not know|medical term|not following|anything else|nowhere in your story|not in WHAT YOU KNOW|two-part",r)]
    if name=="V0": return system
    add=[]
    if name=="Vnone": pass
    else:
        add.append('5. If the doctor uses a word you would not know, ask what it means, in your own words.')
        add.append('6. To an open question such as "anything else?", give one more line from WHAT YOU KNOW, or say nothing else comes to mind. Never a line from WHAT YOU DO NOT VOLUNTEER.')
        if name.startswith("Vown"):
            add.append('8. If the doctor asks about something that is not in WHAT YOU KNOW, say you are not sure or have not noticed, in your own words. Add no details.')
        elif name.startswith("Vno"):
            add.append('8. If the doctor asks about something that is not in WHAT YOU KNOW, the answer is no. Add no details.')
        if name.endswith("_parts"):
            add.append('9. Answer each part of a two-part question, in order.')
    return "\n".join(head+keep+add)
def load_case(cid):
    return json.loads(subprocess.run(["node",os.path.join(HERE,"case.js"),os.path.join(ROOT,"index.html"),os.path.join(ROOT,"cases",cid+".txt")],capture_output=True,text=True,check=True).stdout)
def chat(model,msgs,temp):
    b=json.dumps({"model":model,"messages":msgs,"stream":False,"keep_alive":"20m","options":{"temperature":temp,"num_ctx":8192,"num_predict":300}}).encode()
    with urllib.request.urlopen(urllib.request.Request(OLLAMA+"/api/chat",data=b,headers={"Content-Type":"application/json"}),timeout=600) as r:
        return json.load(r)["message"]["content"].strip()
def probes_for(cid, k):
    P=os.path.join(HERE,"probes")
    reg=json.load(open(f"{P}/{cid}-regression.json")); cl=json.load(open(f"{P}/{cid}-claude.json")); hv=json.load(open(f"{P}/{cid}-harvest.json"))
    rnd=random.Random(1000+k); rnd.shuffle(hv); hv=hv[:10]
    rest=cl+hv; rnd.shuffle(rest)
    # key probes go into the second half, spread out
    n=len(rest); order=list(rest); start=n//2; step=max(1,(n-start)//(len(reg)+1))
    for j,r in enumerate(reg): order.insert(min(len(order), start+j*step+j), r)
    return order
def score(cid,p,reply):
    kind=p["kind"]; s={}
    canned=bool(CANNED.search(reply)); is_j = kind=="jargon" or (kind=="harvest" and JARGON_RX.search(p["text"]) is not None)
    s["misfire"]= canned and not is_j
    if kind=="jargon": s["jargon_handled"]= canned or bool(ASK_MEANING.search(reply))
    if kind!="open": s["denial_fallback"]= bool(DENIAL.search(reply))
    if p.get("expect") and kind in ("hidden_direct","compound","lay_medical","scripted"): s["fact_given"]= re.search(p["expect"],reply,re.I) is not None
    if kind=="open" and LEAK.get(cid): s["leak"]= re.search(LEAK[cid],reply,re.I) is not None
    if kind=="exam": s["exam_ok"]= bool(re.search(r"go ahead",reply,re.I))
    if kind=="unscripted": s["specific"]= bool(SPECIFIC.search(reply))
    if p.get("bad"): s["bad_line"]= re.search(p["bad"],reply,re.I) is not None
    s["sentences"]=len([x for x in re.split(r"[.!?]+",reply) if x.strip()])
    return s
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--runs",type=int,default=3); ap.add_argument("--variants",default="V0,Vnone,Vown,Vno,Vown_parts,Vno_parts")
    ap.add_argument("--temp",type=float,default=0.6); ap.add_argument("--model",default="qwen3:4b-instruct"); ap.add_argument("--tag",default="")
    a=ap.parse_args()
    outdir=os.path.join(HERE,"results","probe-"+time.strftime("%Y-%m-%d-%H%M")+a.tag); os.makedirs(outdir,exist_ok=True)
    cases={c:load_case(c) for c in CASES}
    agg={}
    for v in a.variants.split(","):
        for cid in CASES:
            c=cases[cid]; system=rules_variant(c["system"],v)
            for k in range(1,a.runs+1):
                msgs=[{"role":"system","content":system},{"role":"user","content":"Good day. I am the doctor. Why are you here today?"},{"role":"assistant","content":c["opening"]}]
                log=[]
                for pos,p in enumerate(probes_for(cid,k),1):
                    msgs.append({"role":"user","content":p["text"]})
                    r=chat(a.model,msgs,a.temp); msgs.append({"role":"assistant","content":r})
                    sc=score(cid,p,r); log.append({"pos":pos,**p,"reply":r,"score":sc})
                    A=agg.setdefault(v,{})
                    for key,val in sc.items():
                        if key=="sentences": A.setdefault("sent",[]).append(val)
                        elif isinstance(val,bool): d=A.setdefault(key,[0,0]); d[0]+=val; d[1]+=1
                json.dump({"variant":v,"case":cid,"run":k,"temp":a.temp,"prompt_sha":hashlib.sha256(system.encode()).hexdigest()[:12],"system":system,"log":log},
                          open(f"{outdir}/{v}-{cid}-{k}.json","w"),indent=1,ensure_ascii=False)
                print(f"{v} {cid} run{k}: {len(log)} probes, misfire {sum(x['score'].get('misfire',0) for x in log)}, denial {sum(x['score'].get('denial_fallback',0) for x in log)}",flush=True)
        json.dump(agg,open(f"{outdir}/agg.json","w"),indent=1)
    keys=["misfire","denial_fallback","fact_given","jargon_handled","leak","exam_ok","specific","bad_line"]
    L=["| variant | "+" | ".join(keys)+" | avg sentences |","|"+"---|"*(len(keys)+2)]
    for v,A in agg.items():
        row=[]
        for key in keys:
            d=A.get(key); row.append(f"{d[0]}/{d[1]} ({100*d[0]/d[1]:.0f}%)" if d and d[1] else "-")
        row.append(f"{sum(A['sent'])/len(A['sent']):.1f}")
        L.append(f"| {v} | "+" | ".join(row)+" |")
    open(f"{outdir}/summary.md","w").write("\n".join(L)+"\n"); print("\n".join(L)); print("DONE",outdir)
if __name__=="__main__": main()
