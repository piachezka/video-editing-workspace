import json,re
W=json.load(open('/tmp/claude-0/-home-user-video-editing-workspace/dfd9379c-97ce-5a90-a259-cc1dd4b7edee/scratchpad/align/words.json'))
lines=[l.strip() for l in open('../caption-script.txt') if l.strip()]
# display tokens: split on spaces; hyphenated words map to 2 aligned tokens
disp=[]  # (text, start, end, clause_end)
k=0
for line in lines:
    for clause in re.split(r'(?<=[.,?!])\s+',line):
        ws=clause.split()
        for i,wd in enumerate(ws):
            parts=[p for p in re.findall(r"[A-Za-z']+",wd.replace('-',' '))]
            s=W[k]['s']; e=W[k+len(parts)-1]['e']; k+=len(parts)
            disp.append([re.sub(r"[^A-Za-z0-9'\-]","",wd).upper(),s,e,i==len(ws)-1])
assert k==len(W),(k,len(W))
# chunk: within clause, groups of 2-3 (avoid 1)
chunks=[];cur=[]
clause=[]
PH=[["BLACK","FRIDAY"],["NEW","YEAR'S"],["BUTCHER'S","BROOM"],["PINE","BARK"],["STRAWBERRY","GUMMY"],["SIXTY","DAYS"],["MARITIME","PINE"],["COMPRESSION","SOCKS"],["TWELVE-HOUR","SHIFTS"],["EIGHTY-DOLLAR","CLOGS"],["FOUR","WEEKS"],["WEEK","ONE"],["WEEK","TWO"],["WEEK","FOUR"],["ONE","PACK"],["LINK","BELOW"]]
ENDBAD=set("THE A AN IN ON AND TO OF MY YOUR I I'M IT'S AT FOR FROM WITH SO BUT OR IS ARE THAT THIS IT".split())
def splits(cl,i):
    a=cl[i-1][0]; b=cl[i][0] if i<len(cl) else None
    return b is not None and any(p[0]==a and p[1]==b for p in PH)
def flush(cl):
    n=len(cl);i=0
    while i<n:
        rem=n-i
        if rem<=3:
            if rem==1 and chunks and False: pass
            chunks.append(cl[i:]);break
        opts=[]
        for size in (3,2,4):
            if rem-size==1 or size>rem: continue
            j=i+size
            sc=2*splits(cl,j)+(cl[j-1][0] in ENDBAD)
            opts.append((sc,(0 if size==3 else 1 if size==2 else 2),size))
        best=min(opts)[2] if opts else rem
        chunks.append(cl[i:i+best]);i+=best
for d in disp:
    clause.append(d)
    if d[3]: flush(clause);clause=[]
if clause: flush(clause)
# merge lone 1-word chunks into previous if same sentence gap small
KEY=["BLACK FRIDAY","BUTCHER'S BROOM","PINE BARK","STRAWBERRY GUMMY","NEW YEAR'S","BUY ONE","GET ONE FREE","SIXTY DAYS","FEELORA","ORA","HESPERIDIN","CENTELLA","LEGS","THIGHS","CALVES","ANKLES","SLUDGE","GUNK","TRASH","DRESS","NURSE","FAT","HEAVY"]
STOP=set("A AN THE AND OR BUT TO OF IN ON AT IS IT IT'S I I'M MY YOUR YOU THEY THEY'RE SO THIS THAT WITH FOR FROM AS BE ARE WAS DON'T NOT NO".split())
def color(ch):
    words=[c[0] for c in ch]; txt=" ".join(words)
    hi=set()
    for kw in KEY:
        m=re.search(r'(^| )'+re.escape(kw)+r'( |$)',txt)
        if m:
            kws=kw.split()
            for j in range(len(words)-len(kws)+1):
                if words[j:j+len(kws)]==kws: hi=set(range(j,j+len(kws))); break
            if hi: break
    if not hi:
        cand=[(len(w),j) for j,w in enumerate(words) if w not in STOP]
        if cand: hi={max(cand)[1]}
    return " ".join(("{\\c&H00F2FF&}"+w+"{\\c&HFFFFFF&}") if j in hi else w for j,w in enumerate(words))
def ts(t):
    h=int(t//3600);m=int(t%3600//60);s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
ev=[]
for i,ch in enumerate(chunks):
    s=ch[0][1]; e=ch[-1][2]
    if i+1<len(chunks):
        ns=chunks[i+1][0][1]
        e = ns if ns-e<0.45 else e+0.15
    else: e+=0.3
    ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{color(ch)}")
for lab,a,b in [("WEEK 1",86.60,90.47),("WEEK 2",90.47,93.50),("WEEK 4",93.50,97.17)]:
    ev.append(f"Dialogue: 1,{ts(a+0.03)},{ts(b-0.03)},Week,,0,0,0,,{{\\an7\\pos(44,150)}}{lab}")
hdr="""[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1288
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,4,3,5,30,30,0,1
Style: Week,Anton,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,3.5,3,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open('captions.ass','w').write(hdr+"\n".join(f.replace(",,{",",,{\\an5\\pos(360,945)}{",1) if ",Cap," in f and False else f for f in ev)+"\n")
# put position on caption lines
txt=open('captions.ass').read()
txt=re.sub(r"(Dialogue: 0,[^\n]*?,Cap,,0,0,0,,)",r"\1{\\an5\\pos(360,945)}",txt)
open('captions.ass','w').write(txt)
print(len(chunks),"chunks")
for c in chunks[:12]: print(" ".join(x[0] for x in c), round(c[0][1],2))
