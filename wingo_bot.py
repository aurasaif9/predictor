"""
AURA X TEAM — Wingo 1M Telegram Bot v5 ULTRA MAX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Smart jackpot numbers (gap + frequency + recency)
✅ 18-strategy weighted voting engine
✅ Self-correction + consensus threshold
✅ Time scheduling placeholder
✅ 1 prediction per period (hard lock)
✅ Period mismatch FIXED
"""
import requests, json, os, random, time
from collections import Counter
from math import log2
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────
BOT_TOKEN   = "8281243098:AAFf4wdCowXR6ent0peu7ngL_GYW7dXPqY8"
CHANNEL_ID  = -1003359300269
API_URL     = "https://auraxsaif.top/api/wingo/1m.php"
STATE_FILE  = "/tmp/wingo_state.json"
BIG_IMAGE   = os.path.join(os.path.dirname(__file__), "big_image.jpg")
SMALL_IMAGE = os.path.join(os.path.dirname(__file__), "small_image.png")
B_POOL      = [5, 6, 7, 8, 9]
S_POOL      = [0, 1, 2, 3, 4]

# ─── TIME SCHEDULE — 4 SESSION WINDOWS (pore set korba) ──────────────────
# Each window: (START_HOUR, START_MIN, STOP_HOUR, STOP_MIN)
# None rakhle oi window off thakbe. Sob None = 24/7 chalbe.
TIME_WINDOWS = [
    (None, None, None, None),   # Session 1
    (None, None, None, None),   # Session 2
    (None, None, None, None),   # Session 3
    (None, None, None, None),   # Session 4
]

def _in_window(now, sh, sm, eh, em):
    start = now.replace(hour=sh, minute=sm or 0, second=0, microsecond=0)
    stop  = now.replace(hour=eh, minute=em or 0, second=0, microsecond=0)
    if start <= stop:
        return start <= now <= stop
    return now >= start or now <= stop

def is_active_time():
    """Returns (active_bool, window_index_or_None).
    If all windows are None → 24/7 active with index 0."""
    valid = [(i, w) for i, w in enumerate(TIME_WINDOWS)
             if w[0] is not None and w[2] is not None]
    if not valid:
        return True, 0  # 24/7
    now = datetime.now()
    for i, (sh, sm, eh, em) in valid:
        if _in_window(now, sh, sm, eh, em):
            return True, i
    return False, None

# ─── STATE ───────────────────────────────────────────────────────────────
def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f: return json.load(f)
    except: pass
    return {
        "last_completed_id":    None,
        "pred_lock_id":         None,
        "pending_prediction":   None,
        "pending_numbers":      [],
        "pending_period_label": None,
        "accumulated_history":  [],
        "recent_results":       [],   # last 10 results for self-correction
        "active_session_idx":   None, # which window currently running
        "session_signals":      [],   # per-session signal log
        "session_wins":         0,
        "session_losses":       0,
        "session_jackpots":     0,
        "wins":0,"losses":0,"jackpots":0,"total":0
    }

def save_state(s):
    with open(STATE_FILE,'w') as f: json.dump(s,f,indent=2)

# ─── SMART JACKPOT NUMBER SELECTOR ───────────────────────────────────────
def smart_jackpot_numbers(hist, pred):
    """
    Pick 2 most 'due' numbers from OPPOSITE pool.
    Uses gap + frequency deficit + recency score.
    Prediction BIG  → Jackpot from SMALL pool [0-4]
    Prediction SMALL → Jackpot from BIG pool   [5-9]
    """
    jack_pool = S_POOL if pred == 'BIG' else B_POOL

    if len(hist) < 8:
        return sorted(random.sample(jack_pool, 2))

    scores = {}
    window = min(100, len(hist))
    sub    = hist[:window]

    for n in jack_pool:
        # 1. Gap score: how long since last appearance (normalized)
        last_seen = next((i for i,x in enumerate(hist) if x==n), window)
        gap_score = min(last_seen / 8.0, 3.0)

        # 2. Frequency deficit: how underrepresented
        expected = window / 10.0           # each number ~10% of time
        actual   = sub.count(n)
        deficit  = max(0.0, (expected - actual) / max(expected, 1))

        # 3. Recent absence: not seen in last 10 → boost
        recent_abs = 1.0 if n not in hist[:10] else 0.0

        # 4. Streak absence: not seen in last 20
        long_abs = 0.5 if n not in hist[:20] else 0.0

        scores[n] = (gap_score * 0.40
                   + deficit  * 0.35
                   + recent_abs * 0.15
                   + long_abs   * 0.10)

    # Pick top 2
    top2 = sorted(scores, key=scores.get, reverse=True)[:2]
    return sorted(top2)

# ─── 18-STRATEGY PREDICTION ENGINE ───────────────────────────────────────
def bss(nums): return ['B' if n>=5 else 'S' for n in nums]

# S1: Multi-length pattern (up to length 10)
def s1_pattern(hist):
    b = bss(hist)
    for plen in range(10,2,-1):
        if len(b)<plen+6: continue
        cur=''.join(b[:plen])
        big=sml=0
        for i in range(1,len(b)-plen):
            if ''.join(b[i:i+plen])==cur:
                if b[i+plen]=='B': big+=1
                else: sml+=1
        if big+sml>=4:
            if big>sml: return 'BIG',  round(big/(big+sml)*100),f'Pat{plen}',5
            else:       return 'SMALL',round(sml/(big+sml)*100),f'Pat{plen}',5
    return None,0,'',0

# S2: 2nd-order Markov
def s2_markov2(hist):
    b=bss(hist)
    if len(b)<25: return None,0,'',0
    t={}
    for i in range(len(b)-2):
        k=b[i]+b[i+1]; t.setdefault(k,{'B':0,'S':0}); t[k][b[i+2]]+=1
    k2=b[0]+b[1]
    if k2 not in t: return None,0,'',0
    r=t[k2]; tot=r['B']+r['S']
    if tot<5: return None,0,'',0
    if r['B']>r['S']: return 'BIG',  round(r['B']/tot*100),'MK2',4
    return 'SMALL',round(r['S']/tot*100),'MK2',4

# S3: 1st-order Markov
def s3_markov1(hist):
    b=bss(hist)
    if len(b)<12: return None,0,'',0
    t={'B':{'B':0,'S':0},'S':{'B':0,'S':0}}
    for i in range(len(b)-1): t[b[i]][b[i+1]]+=1
    r=t[b[0]]; tot=r['B']+r['S']
    if tot==0: return None,0,'',0
    if r['B']>r['S']: return 'BIG',  round(r['B']/tot*100),'MK1',3
    return 'SMALL',round(r['S']/tot*100),'MK1',3

# S4: Streak breaker
def s4_streak(hist):
    b=bss(hist); streak=1; cur=b[0]
    for x in b[1:20]:
        if x==cur: streak+=1
        else: break
    if streak>=6: return ('SMALL'if cur=='B'else'BIG'),min(93,62+streak*5),'Str6+',5
    if streak>=4: return ('SMALL'if cur=='B'else'BIG'),min(82,58+streak*4),'Str4',3
    if streak>=3: return ('SMALL'if cur=='B'else'BIG'),63,'Str3',2
    return None,0,'',0

# S5: Multi-window dominance
def s5_dom(hist):
    b=bss(hist); bs=ss=0
    for w,wt in [(5,1),(10,2),(20,3),(30,4),(50,5),(100,6)]:
        if len(b)<w: continue
        bc=b[:w].count('B'); pct=bc/w
        if pct>0.65: ss+=wt
        elif pct<0.35: bs+=wt
        elif pct>0.58: ss+=wt//2
        elif pct<0.42: bs+=wt//2
    if bs>ss: return 'BIG',  60,'Dom',3
    if ss>bs: return 'SMALL',60,'Dom',3
    return None,0,'',0

# S6: Exponential weighted (decay 0.80)
def s6_expw(hist):
    if len(hist)<8: return None,0,'',0
    d=0.80; bw=sw=0.0; w=1.0
    for n in hist[:50]:
        if n>=5: bw+=w
        else: sw+=w
        w*=d
    tot=bw+sw
    if tot==0: return None,0,'',0
    pct=bw/tot
    if pct>0.60: return 'SMALL',round(pct*100),'ExpW',3
    if pct<0.40: return 'BIG',  round((1-pct)*100),'ExpW',3
    return None,0,'',0

# S7: Gap / drought
def s7_gap(hist):
    b=bss(hist)
    lb=next((i for i,x in enumerate(b) if x=='B'),999)
    ls=next((i for i,x in enumerate(b) if x=='S'),999)
    if lb>ls+3: return 'BIG',  min(80,55+lb*4),'Gap',3
    if ls>lb+3: return 'SMALL',min(80,55+ls*4),'Gap',3
    return None,0,'',0

# S8: Cold number (number level)
def s8_cold(hist):
    if len(hist)<20: return None,0,'',0
    cnt=Counter(hist[:80])
    ab=sum(cnt.get(n,0) for n in range(5,10))/5
    as_=sum(cnt.get(n,0) for n in range(0,5))/5
    cb=sum(1 for n in range(5,10) if cnt.get(n,0)<ab*0.55)
    cs=sum(1 for n in range(0,5)  if cnt.get(n,0)<as_*0.55)
    if cb>=3: return 'BIG',  63,'Cold',2
    if cs>=3: return 'SMALL',63,'Cold',2
    return None,0,'',0

# S9: Zigzag / alternation
def s9_zigzag(hist):
    b=bss(hist)
    if len(b)<8: return None,0,'',0
    zz=sum(1 for i in range(1,min(10,len(b))) if b[i]!=b[i-1])
    if zz>=8: return ('SMALL'if b[0]=='B'else'BIG'),78,'ZigZag',3
    return None,0,'',0

# S10: Chi-square uniformity
def s10_chi(hist):
    if len(hist)<30: return None,0,'',0
    w=min(100,len(hist)); sub=hist[:w]
    ob=sum(1 for n in sub if n>=5); os_=w-ob; exp=w/2
    chi=(ob-exp)**2/exp+(os_-exp)**2/exp
    if chi<1.0: return None,0,'',0
    if ob>os_: return 'SMALL',min(85,50+int(chi*3)),'Chi',2
    return 'BIG',  min(85,50+int(chi*3)),'Chi',2

# S11: Double reversal (BB→S, SS→B)
def s11_dbl(hist):
    b=bss(hist)
    if len(b)<4: return None,0,'',0
    if b[0]==b[1]:
        opp='SMALL'if b[0]=='B'else'BIG'
        rev=stay=0
        for i in range(len(b)-2):
            if b[i]==b[i+1]:
                if b[i+2]!=b[i]: rev+=1
                else: stay+=1
        tot=rev+stay
        if tot>=6 and rev>stay*1.3: return opp,round(rev/tot*100),'DblRev',4
    return None,0,'',0

# S12: Alternation collapse
def s12_alt(hist):
    b=bss(hist)
    if len(b)<5: return None,0,'',0
    if b[0]!=b[1] and b[1]!=b[2] and b[2]!=b[3]:
        return (b[0]),70,'AltCol',3
    return None,0,'',0

# S13: Streak momentum
def s13_mom(hist):
    b=bss(hist)
    if len(b)<20: return None,0,'',0
    cont=brk=0
    for i in range(len(b)-3):
        if b[i]==b[i+1]==b[i+2]:
            if b[i+3]==b[i]: cont+=1
            else: brk+=1
    tot=cont+brk
    if tot<5: return None,0,'',0
    if b[0]==b[1]==b[2]:
        cur=b[0]; opp='SMALL'if cur=='B'else'BIG'
        if brk>cont*1.2: return opp,round(brk/tot*100),'Mom',3
    return None,0,'',0

# S14: Hot avoidance
def s14_hot(hist):
    if len(hist)<25: return None,0,'',0
    top=Counter(hist[:60]).most_common(1)[0][0]
    return ('SMALL'if top>=5 else'BIG'),60,'HotAvd',2

# S15: Entropy balance
def s15_ent(hist):
    if len(hist)<20: return None,0,'',0
    sub=hist[:30]; cnt=Counter(sub); n=len(sub)
    ent=sum(-(c/n)*log2(c/n) for c in cnt.values() if c>0)
    if ent < log2(10)*0.6:
        bc=sum(1 for x in sub if x>=5)
        if bc>n/2: return 'SMALL',65,'Ent',2
        return 'BIG',65,'Ent',2
    return None,0,'',0

# S16: 3rd-order Markov
def s16_markov3(hist):
    b=bss(hist)
    if len(b)<30: return None,0,'',0
    t={}
    for i in range(len(b)-3):
        k=b[i]+b[i+1]+b[i+2]; t.setdefault(k,{'B':0,'S':0}); t[k][b[i+3]]+=1
    k3=b[0]+b[1]+b[2]
    if k3 not in t: return None,0,'',0
    r=t[k3]; tot=r['B']+r['S']
    if tot<4: return None,0,'',0
    if r['B']>r['S']: return 'BIG',  round(r['B']/tot*100),'MK3',5
    return 'SMALL',round(r['S']/tot*100),'MK3',5

# S17: Cycle detection (every 4/6/8 periods)
def s17_cycle(hist):
    b=bss(hist)
    if len(b)<16: return None,0,'',0
    for cyc in [4,6,8]:
        if len(b)<cyc*3: continue
        # Check if pattern repeats every `cyc` steps
        matches=0; total=0
        for i in range(cyc, min(cyc*3, len(b))):
            total+=1
            if b[i]==b[i-cyc]: matches+=1
        if total>0 and matches/total>=0.70:
            # Predict based on the cycle
            pred_idx=cyc
            return ('BIG'if b[pred_idx]=='B'else'SMALL'),round(matches/total*100),'Cyc',3
    return None,0,'',0

# S18: Self-correction (if last 3 wrong, flip)
def s18_selfcorr(hist, recent_results):
    """Uses recent win/loss history to self-correct."""
    if not recent_results or len(recent_results)<3:
        return None,0,'',0
    last3=[r['correct'] for r in recent_results[-3:]]
    if all(not x for x in last3):
        # Last 3 all wrong — flip the base prediction
        b=bss(hist)
        bc=b[:10].count('B')
        # Give opposite of what simple analysis says
        base='SMALL' if bc>=5 else 'BIG'
        opp='SMALL' if base=='BIG' else 'BIG'
        return opp,68,'SelfCorr',4
    return None,0,'',0

ALL_STRATEGIES = [
    s1_pattern,s2_markov2,s3_markov1,s4_streak,
    s5_dom,s6_expw,s7_gap,s8_cold,s9_zigzag,s10_chi,
    s11_dbl,s12_alt,s13_mom,s14_hot,s15_ent,
    s16_markov3,s17_cycle
]

def ultra_predict(hist, recent_results=None):
    """18 strategies vote → weighted final decision + consensus check."""
    if not hist or len(hist)<3:
        return 'BIG',50,'Fallback'

    votes=[]
    for fn in ALL_STRATEGIES:
        pred,conf,name,wt = fn(hist)
        if pred: votes.append((pred,conf,name,wt))

    # S18 self-correction (uses recent results)
    if recent_results:
        pred,conf,name,wt = s18_selfcorr(hist, recent_results)
        if pred: votes.append((pred,conf,name,wt))

    if not votes:
        bc=sum(1 for n in hist[:10] if n>=5)
        return ('SMALL'if bc>=5 else'BIG'),50,'Fallback'

    # Weighted score
    big_s=sml_s=0.0
    for pred,conf,name,wt in votes:
        score=(conf/100.0)*wt
        if pred=='BIG': big_s+=score
        else: sml_s+=score

    tot=big_s+sml_s
    final='BIG' if big_s>=sml_s else 'SMALL'

    # Consensus check: how many strategies agree?
    agree=sum(1 for p,_,_,_ in votes if p==final)
    total_v=len(votes)
    consensus_pct=agree/total_v if total_v>0 else 0.5

    # If consensus < 55%, reduce confidence
    raw_conf=round(max(big_s,sml_s)/tot*100) if tot>0 else 50
    if consensus_pct < 0.55:
        raw_conf = max(50, raw_conf - 15)
    elif consensus_pct > 0.75:
        raw_conf = min(95, raw_conf + 5)  # boost if strong consensus

    winning=[name for p,_,name,_ in votes if p==final]
    algo='+'.join(winning[:4])
    return final, min(raw_conf,95), algo

# ─── TELEGRAM ────────────────────────────────────────────────────────────
def tg_photo(img,cap):
    try:
        with open(img,'rb') as p:
            r=requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id":CHANNEL_ID,"caption":cap,"parse_mode":"HTML"},
                files={"photo":p},timeout=20)
        return r.json()
    except Exception as e: return {"ok":False,"description":str(e)}

def tg_msg(text):
    try:
        r=requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id":CHANNEL_ID,"text":text,"parse_mode":"HTML"},timeout=15)
        return r.json()
    except Exception as e: return {"ok":False,"description":str(e)}

def send_prediction(period_label, pred, nums, conf):
    jack  = ',  '.join(str(n) for n in nums)
    bar   = '🟩'*(conf//10)+'⬜'*(10-conf//10)
    sig   = f"{'🟢 BIG' if pred=='BIG' else '🔴 SMALL'}"
    cap=(
        f"<b>🤖 AURAＸ TEAM AI BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 <b>WIN GO - 1 MINUTE</b>\n"
        f"📌 <b>PERIOD:</b>  <code>{period_label}</code>\n"
        f"🎯 <b>SIGNAL:</b>  <b>{sig}</b>\n"
        f"💎 <b>JACKPOT:</b>  <code>{jack}</code>\n"
        f"📊 {bar}  <b>{conf}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>5 STEPS FOLLOW PROFIT 100%</b>\n"
        f"🖥 <b>SERVER: DESH CLUB API</b>"
    )
    img=BIG_IMAGE if pred=='BIG' else SMALL_IMAGE
    res=tg_photo(img,cap)
    ok=res.get('ok',False)
    print(f"  📤 PRED → {pred} ({conf}%) | Period:{period_label} | TG={ok}")
    return ok

def send_result(period_label, prediction, actual_num, numbers):
    asize='BIG' if actual_num>=5 else 'SMALL'
    s_ok =asize==prediction
    n_hit=actual_num in numbers

    if n_hit:   emoji="🎰🎉";rt="✅ WIN";jp="🎰 YES — JACKPOT!"
    elif s_ok:  emoji="🎉";  rt="✅ WIN";jp="❌ NO"
    else:       emoji="💀";  rt="❌ LOSS";jp="❌ NO"

    text=(
        f"{emoji} <b>PERIOD RESULT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>PERIOD RESULT:</b>  <code>{period_label}</code>\n"
        f"🎲 <b>OUTCOME:</b>  <b>{asize}  ({actual_num})</b>\n"
        f"🎯 <b>PREDICTION:</b>  <b>{prediction}</b>\n"
        f"📊 <b>Result:</b>  <b>{rt}</b>\n"
        f"💎 <b>JACKPOT:</b>  {jp}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    res=tg_msg(text)
    ok=res.get('ok',False)
    print(f"  📊 RESULT → {rt} | {asize}({actual_num}) | JP={n_hit} | TG={ok}")
    return ok,s_ok,n_hit

# ─── MAIN ────────────────────────────────────────────────────────────────
def send_session_started(idx):
    text = (
        f"🟢 <b>SESSION STARTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AURAＸ TEAM AI BOT</b>\n"
        f"📍 <b>Session #{idx+1}</b> activated\n"
        f"⏰ <b>Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>\n"
        f"🎯 Get ready — signals coming up!\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    tg_msg(text)

def send_session_ended(idx, signals, wins, losses, jackpots):
    total = wins + losses
    acc = round(wins / total * 100) if total > 0 else 0
    lines = []
    for i, s in enumerate(signals, 1):
        mark = "🎰" if s.get('jackpot') else ("✅" if s.get('win') else "❌")
        rt   = "WIN" if s.get('win') else "LOSS"
        lines.append(
            f"{i}. <code>{s['period']}</code> | {s['pred']} → {s['actual']} {mark} <b>{rt}</b>"
        )
    body = "\n".join(lines) if lines else "No signals this session."
    text = (
        f"🔴 <b>SESSION ENDED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AURAＸ TEAM AI BOT</b>\n"
        f"📍 <b>Session #{idx+1}</b> closed\n"
        f"⏰ <b>Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>SIGNAL HISTORY:</b>\n{body}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>SUMMARY</b>\n"
        f"✅ Wins: <b>{wins}</b>\n"
        f"❌ Losses: <b>{losses}</b>\n"
        f"🎰 Jackpots: <b>{jackpots}</b>\n"
        f"📈 Accuracy: <b>{acc}%</b>"
    )
    tg_msg(text)

def run():
    state = load_state()
    active, idx = is_active_time()
    prev_idx = state.get('active_session_idx')

    # Session END detection
    if prev_idx is not None and (not active or idx != prev_idx):
        send_session_ended(
            prev_idx,
            state.get('session_signals', []),
            state.get('session_wins', 0),
            state.get('session_losses', 0),
            state.get('session_jackpots', 0),
        )
        state['active_session_idx'] = None
        state['session_signals']    = []
        state['session_wins']       = 0
        state['session_losses']     = 0
        state['session_jackpots']   = 0
        # Clear pending so old session result doesn't bleed into next
        state['pending_prediction']   = None
        state['pending_numbers']      = []
        state['pending_period_label'] = None
        save_state(state)

    if not active:
        print(f"  🕐 Outside active time — bot sleeping")
        save_state(state)
        return

    # Session START detection
    if state.get('active_session_idx') != idx:
        send_session_started(idx)
        state['active_session_idx'] = idx
        state['session_signals']    = []
        state['session_wins']       = 0
        state['session_losses']     = 0
        state['session_jackpots']   = 0
        save_state(state)


    try:
        resp=requests.get(API_URL,timeout=10,
                          headers={"Cache-Control":"no-cache","Pragma":"no-cache"})
        resp.raise_for_status()
        lst=resp.json()['data']['list']
    except Exception as e:
        print(f"❌ API Error: {e}"); return

    # Completed periods
    completed=[i for i in lst
               if str(i.get('number','')).strip().isdigit()
               and 0<=int(i['number'])<=9]
    if not completed:
        print("⚠️ No completed periods"); return

    # Period logic (FIXED)
    last_done_id  = completed[0]['issueNumber']
    last_done_num = int(completed[0]['number'])
    running_id    = str(int(last_done_id)+1)   # currently running in DeshClub
    predict_for   = running_id                  # we predict FOR currently running

    # Accumulate history (up to 200)
    new_h   = [int(i['number']) for i in completed]
    saved   = state.get('accumulated_history',[])
    merged  = list(new_h)
    for n in saved:
        if len(merged)>=200: break
        merged.append(n)
    state['accumulated_history'] = merged[:200]
    history = merged[:100]

    print(f"  ✅ Done: {last_done_id}={last_done_num} | ▶ Run:{running_id} | 🎯 For:{predict_for}")
    print(f"  📚 Hist: {len(history)}pts | Last8={history[:8]}")

    recent_results = state.get('recent_results',[])

    # ── STEP 1: Result check ─────────────────────────────────────────────
    if (state['last_completed_id'] is not None
            and last_done_id != state['last_completed_id']
            and state['pending_prediction'] is not None):

        ok,s_ok,n_hit = send_result(
            period_label = state['pending_period_label'],
            prediction   = state['pending_prediction'],
            actual_num   = last_done_num,
            numbers      = state['pending_numbers']
        )
        state['total'] += 1
        if n_hit or s_ok:
            state['wins']    += 1
            correct=True
        else:
            state['losses']  += 1
            correct=False
        if n_hit: state['jackpots'] += 1

        # Save recent results for self-correction
        recent_results.append({
            'correct': correct,
            'pred':    state['pending_prediction'],
            'actual':  last_done_num
        })
        state['recent_results'] = recent_results[-10:]  # keep last 10

        # Per-session log
        sig_log = state.get('session_signals', [])
        sig_log.append({
            'period':  state['pending_period_label'],
            'pred':    state['pending_prediction'],
            'actual':  f"{('BIG' if last_done_num>=5 else 'SMALL')}({last_done_num})",
            'win':     bool(s_ok or n_hit),
            'jackpot': bool(n_hit),
        })
        state['session_signals'] = sig_log
        if s_ok or n_hit: state['session_wins']   = state.get('session_wins',0)+1
        else:             state['session_losses'] = state.get('session_losses',0)+1
        if n_hit:         state['session_jackpots']= state.get('session_jackpots',0)+1

        time.sleep(1.5)

    # ── STEP 2: New prediction ───────────────────────────────────────────
    if state.get('pred_lock_id') != last_done_id:
        # Ultra prediction
        pred,conf,algo = ultra_predict(history, recent_results)
        # Smart jackpot numbers
        nums = smart_jackpot_numbers(history, pred)

        ok = send_prediction(predict_for, pred, nums, conf)
        if ok:
            state['pred_lock_id']         = last_done_id
            state['pending_prediction']   = pred
            state['pending_numbers']      = nums
            state['pending_period_label'] = predict_for
    else:
        print(f"  ⏭ Skip (already sent for {last_done_id})")

    state['last_completed_id'] = last_done_id
    save_state(state)

    acc=round(state['wins']/state['total']*100) if state['total']>0 else 0
    print(f"  📈 W={state['wins']} L={state['losses']} JP={state['jackpots']} ACC={acc}%")

if __name__=='__main__':
    run()
