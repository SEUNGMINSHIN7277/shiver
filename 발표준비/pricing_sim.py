# 서울 이모삼촌 — 쿠킹클래스 단가 시뮬레이션
def won(x): return f"{round(x):,}원"

# ── 기준선(시장 comp, 리서치 확인) ─────────────────────────────
print("="*72)
print("[1] 시장 시세 기준선 (리서치 확인)")
print("="*72)
comps = [
 ("얌이랩(원데이 한식)", "평일 45,000 / 주말 60,000"),
 ("글로벌 플랫폼 서울 쿠킹클래스(제안서)", "50,000 ~ 90,000"),
 ("cooKorean (3.5h·3요리·시장투어·레시피북)", "고가·외국인 인기(콤보형)"),
 ("에어비앤비 김치+시장투어(4.9★ 다수)", "체험 카테고리 최상위"),
]
for a,b in comps: print(f"  · {a:38s} : {b}")
print("  → 2~2.5h 핸즈온+식사 단품 기준 '중심가격대 55,000~70,000원' 추정\n")

# ── 원가 가정 (모두 조정 가능, 명시적으로 출력) ────────────────
FEE      = 0.15      # 플랫폼 수수료 blended(에어비앤비20%+마리트/클룩15~18%+직판0% 혼합)
INGRED   = 9000      # 1인 식재료(시장 조달, 한 끼 완식)
SUPPORT  = 45000     # 회당 청년 서포터 수당(통역·촬영·결제·정리, ~3h)
VENUE_P  = 80000     # 회당 공유주방(시범: 연남 시간제 25,000/h × ~3h)
VENUE_S  = 40000     # 회당 공간(정착: 망원시장/식당 제휴·공공주방)
CONSUM   = 8000      # 회당 소모품·가스·수도·세탁
HOST     = 50000     # 회당 호스트(이모) 임금 — 지급 목표
CAP      = 6         # 정원

print("="*72); print("[2] 원가 가정 (회당)"); print("="*72)
print(f"  플랫폼수수료 {FEE*100:.0f}% | 식재료 {won(INGRED)}/인 | 서포터 {won(SUPPORT)} | "
      f"공유주방 시범 {won(VENUE_P)}/정착 {won(VENUE_S)} | 소모품 {won(CONSUM)} | 호스트임금 {won(HOST)} | 정원 {CAP}\n")

def classpl(price, n, venue, host=HOST):
    gross = price*n
    fee = gross*FEE
    ing = INGRED*n
    contrib = gross - fee - ing - SUPPORT - venue - CONSUM   # 호스트 임금 전 공헌이익
    op = contrib - host                                       # 운영주체 마진
    return gross, fee, ing, contrib, op

# ── 회당 손익: 가격 × 정원 (시범 공유주방 기준) ────────────────
print("="*72); print("[3] 회당 운영주체 마진 — 가격 × 정원 (시범 공유주방 80,000)"); print("="*72)
prices = [45000,55000,65000,75000,89000]
occ = [3,4,5,6]
head = "가격\\정원 |" + "".join(f"{n}명".rjust(12) for n in occ)
print(head); print("-"*len(head))
for p in prices:
    row=f"{won(p):>8} |"
    for n in occ:
        _,_,_,_,op = classpl(p,n,VENUE_P)
        row += (("+" if op>=0 else "")+won(op)).rjust(12)
    print(row)
print("  (호스트 임금 50,000원 지급 후 남는 운영주체 몫. +면 흑자)\n")

# ── 손익분기 정원 ─────────────────────────────────────────────
print("="*72); print("[4] 손익분기 정원 (운영주체 마진 ≥ 0에 필요한 최소 인원)"); print("="*72)
def be(price, venue, host=HOST):
    denom = price*(1-FEE) - INGRED
    need = (SUPPORT+venue+CONSUM+host)/denom
    return need
print(f"{'가격':>8} | {'시범주방(80k)':>14} | {'정착제휴(40k)':>14}")
print("-"*44)
for p in prices:
    print(f"{won(p):>8} | {be(p,VENUE_P):>13.1f}명 | {be(p,VENUE_S):>13.1f}명")
print()

# ── 월간 롤업: 추천가에서 호스트 소득 & 운영주체 이익 ──────────
print("="*72); print("[5] 월간 시뮬레이션 — 추천가 65,000원(외국인·평일 기준)"); print("="*72)
P=65000
for venue,label in [(VENUE_P,"시범(공유주방)"),(VENUE_S,"정착(시장/식당 제휴)")]:
    print(f"\n  [{label} · 회당공간 {won(venue)}]  정원 평균 5명 가정")
    print(f"   {'월 수업수':>7}{'월매출':>12}{'호스트월소득':>13}{'운영주체 월이익':>16}")
    for C in [8,12,17,22]:
        n=5
        gross=P*n*C
        host_month=HOST*C
        # 운영주체: 회당 op × C  - 월 간접비(마케팅/보험/관리)
        _,_,_,_,op=classpl(P,n,venue)
        overhead=150000
        op_month=op*C-overhead
        print(f"   {C:>6}회{won(gross):>12}{won(host_month):>13}{('+'if op_month>=0 else '')+won(op_month):>16}")
    print(f"   (호스트 월소득 목표 854,000원 ≈ 월 17회 × 50,000원)")

# ── 수수료 민감도 ─────────────────────────────────────────────
print("\n"+"="*72); print("[6] 플랫폼 수수료 민감도 (가격 65,000 · 정원 5 · 시범주방)"); print("="*72)
for f in [0.0,0.15,0.20]:
    gross=65000*5; fee=gross*f
    op=gross-fee-INGRED*5-SUPPORT-VENUE_P-CONSUM-HOST
    tag={0.0:"직판/게하/B2B",0.15:"blended",0.20:"에어비앤비 단독"}[f]
    print(f"  수수료 {f*100:>4.0f}% ({tag:14s}) → 회당 운영마진 {('+'if op>=0 else '')+won(op)}")

print("\n"+"="*72); print("[7] 권장 단가 (결론)"); print("="*72)
rec=[
 ("외국인·평일(플랫폼)","65,000원","comp 중심가+핸즈온·식사·레시피카드·시장재료"),
 ("외국인·주말/프리미엄","75,000원","주말 수요·성수기"),
 ("내국인 주말(할머니집밥)","55,000원","가격민감·직판(수수료↓)"),
 ("B2B 단체(1인 환산)","50,000원~","정원↑·수수료0·마진 최상"),
]
for a,b,c in rec: print(f"  · {a:22s} {b:>10}  — {c}")
