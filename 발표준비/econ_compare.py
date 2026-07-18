def won(x):
    s = "-" if x<0 else ""
    return f"{s}{abs(round(x)):,}원"

# ── 공통 가정 (평균 추정) ─────────────────────────────
FEE=0.15; INGRED=9000; SUPPORT=40000; CONSUM=8000; HOST=55000
OVERHEAD=150000      # 월 간접비(마케팅·관리)/호스트
CLS=15               # 월 수업수/호스트(평균 가동)
AMORT=24             # CAPEX 상각(개월)

# 시나리오 파라미터
# name, 단가, 정원, 회당공간, 초기CAPEX, 연보험/등록
scn = {
 "공유주방":       dict(price=62000, occ=5, venue=75000, capex=0,       ins=600000),
 "집(동일단가)":   dict(price=62000, occ=4, venue=0,     capex=1500000, ins=900000),
 "집(프리미엄가)": dict(price=75000, occ=4, venue=0,     capex=1500000, ins=900000),
}

def per_class(p):
    gross=p['price']*p['occ']
    return gross - gross*FEE - INGRED*p['occ'] - SUPPORT - p['venue'] - CONSUM - HOST

def monthly(p):  # 상각·보험 포함 월 운영이익(호스트1)
    return per_class(p)*CLS - OVERHEAD - p['ins']/12 - p['capex']/AMORT

print("="*78); print("[0] 공통 가정 (평균 추정)"); print("="*78)
print(f"  수수료15% | 식재료9,000/인 | 서포터40,000 | 소모품8,000 | 호스트임금55,000/회 | 월간접비150,000 | 월15회")
print(f"  공유주방=단가62,000·정원5·회당임대75,000 | 집=단가62~75,000·정원4·임대0·초기150만·연보험90만\n")

print("="*78); print("[1] 회당 단위경제성 (운영주체 마진)"); print("="*78)
print(f"  {'시나리오':16s}{'매출':>12}{'수수료':>10}{'식재료':>10}{'서포터':>9}{'공간':>10}{'소모품':>9}{'호스트':>10}{'=회당마진':>12}")
for n,p in scn.items():
    g=p['price']*p['occ']
    print(f"  {n:16s}{won(g):>12}{won(-g*FEE):>10}{won(-INGRED*p['occ']):>10}{won(-SUPPORT):>9}{won(-p['venue']):>10}{won(-CONSUM):>9}{won(-HOST):>10}{won(per_class(p)):>12}")
print("  → 집은 임대료(회당 75,000) 절약 + 프리미엄단가로 회당마진 우위 (정원 1명 적어도 상쇄)\n")

print("="*78); print("[2] 월 손익 (호스트 1인 · 15회 · 상각·보험 포함)"); print("="*78)
for n,p in scn.items():
    m=monthly(p)
    print(f"  {n:16s} 월매출 {won(p['price']*p['occ']*CLS):>12} | 호스트급여 {won(HOST*CLS):>10} | 운영주체 월이익 {won(m):>12}")
print()

print("="*78); print("[3] 연 손익 (호스트 1인)"); print("="*78)
for n,p in scn.items():
    base=per_class(p)*CLS*12 - OVERHEAD*12 - p['ins']    # 상각 아닌 실비: 1년차 CAPEX 전액
    y1=base - p['capex']; y2=base
    print(f"  {n:16s} 1년차 {won(y1):>12} | 2년차~ {won(y2):>12}")
print("  (1년차는 초기 CAPEX 전액 반영, 2년차부터 제외)\n")

print("="*78); print("[4] 확장 시나리오 — 프로그램 목표 6명 (총 운영이익/월)"); print("="*78)
print(f"  {'시나리오':16s}{'6명 월이익 합':>16}{'필요 인프라':>34}")
inf={"공유주방":"공유주방 1~2곳 순환(용이)","집(동일단가)":"자격 단독주택 6채+등록+보험(비현실)","집(프리미엄가)":"자격 단독주택 6채+등록+보험(비현실)"}
for n,p in scn.items():
    print(f"  {n:16s}{won(monthly(p)*6):>16}   {inf[n]:>32}")
print()

print("="*78); print("[5] ★리스크(실현가능성) 조정 기대값 — 6명 월이익 × 성립확률"); print("="*78)
# 성립확률: 파일럿 기간 내 '해당 호스트 셋업(법·보험·안전·자격주택·의향)'이 실제 성사될 확률
prob={"공유주방":0.95, "집(동일단가)":0.20, "집(프리미엄가)":0.20}
print(f"  {'시나리오':16s}{'6명 월이익':>14}{'성립확률':>9}{'리스크조정 기대값':>18}")
for n,p in scn.items():
    ev=monthly(p)*6*prob[n]
    print(f"  {n:16s}{won(monthly(p)*6):>14}{int(prob[n]*100):>7}%{won(ev):>18}")
print("  (집은 호스트마다 자격 단독주택+외도민/샌드박스+보험+안전을 모두 갖춰야 성립 → 확률 낮음)\n")

print("="*78); print("[6] 민감도 — 정원·단가가 바뀌면 (집 프리미엄가 기준)"); print("="*78)
base=scn["집(프리미엄가)"]
for occ in [3,4,5]:
    row=f"  정원 {occ}명 |"
    for pr in [65000,75000,85000]:
        pp=dict(base); pp['occ']=occ; pp['price']=pr
        row+=f"  단가{pr//1000}k→월{won(monthly(pp))}"
    print(row)
print()

print("="*78); print("[7] 결론 요약"); print("="*78)
print("""  • 회당·호스트1인 관점: 집이 우월 (임대료 회당 75,000 절약 + 프리미엄) 
  • 프로그램(6명)·확장·리스크 관점: 공유주방이 우월 (집은 자격주택 6채 확보 비현실)
  • 리스크조정 기대값에서 공유주방이 역전 → 시범/확장 코어는 공유주방
  • 집은 '고마진 프리미엄 단일 상품'으로만 경제성 있음(성립 시)""")
