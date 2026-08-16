#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""古籍现代化增量模块 — BFFT v7.18（第二轮精读八书的代码级沉淀）。

本轮从八部古籍再精读中提取三个此前只停留在文档层、未代码化的规则：

1. 源流分析（《滴天髓》源流章："何处起根源，流到何方住"）
   —— 全局最旺五行为源头，沿相生链看流到何处、以何五行收束。
2. 通关检测（《滴天髓》通关章："关内有织女，关外有牛郎，此关若通也"）
   —— 相克五行交战对（金木/木土/土水/水火/火金），检测柱中有无
   通关之神（生我克方之五行），有则"战局可通"，无则"战局硬磕"。
3. 行运长生读法（《三命通会》卷二论大运）
   —— 十二长生状态 → 行运读法标签（长生创建/临官帝旺兴发/衰病退败/
   死绝凶险/墓库收藏/胎养冠带安康）。

均为 S 级结构化规则（由干支生克直接推导），不涉及神煞与断语。
"""

from __future__ import annotations

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
WUXING = ["木", "火", "土", "金", "水"]

# 十二长生读法（《三命通会》论大运）
CHANGSHENG_READ = {
    "长生": "创建作新",
    "沐浴": "桃花败地",
    "冠带": "安康平易",
    "临官": "兴盛发福",
    "帝旺": "发福进财",
    "衰": "退败",
    "病": "疾病退败",
    "死": "骨肉死丧",
    "墓": "收藏入库",
    "绝": "蹇塞凶险",
    "胎": "怀胎成形",
    "养": "养育安康",
}


def source_flow(counts: dict) -> dict:
    """源流分析（滴天髓源流章）。

    counts: 五行计数 {"木": n, ...}（含藏干）。返回源头、流向链、收束方。
    """
    if not counts:
        return {"source": "", "chain": [], "sink": "", "note": "无数据"}
    source = max(counts, key=counts.get)
    # 相生链：从源头出发沿生链走到哪一行
    chain = [source]
    cur = source
    seen = set()
    while cur not in seen:
        seen.add(cur)
        nxt = SHENG[cur]
        if counts.get(nxt, 0) >= counts.get(cur, 0):
            chain.append(nxt)
            cur = nxt
        else:
            break
    # 收束：链尾行若为全局最弱则"流而不收"，否则"流至 X 收束"
    weakest = min(counts, key=counts.get)
    sink = chain[-1]
    note = (f"{source}为源, 流经{'→'.join(chain)}"
            + (f", 止于{sink}" if sink == weakest else f", 收于{sink}"))
    return {"source": source, "chain": chain, "sink": sink, "note": note}


def tongguan(counts: dict) -> list[dict]:
    """通关检测（滴天髓通关章）：相克对 + 通关神存在性。"""
    out = []
    for a in WUXING:
        b = KE[a]
        key = a + b
        # 通关神 = 生 b 之五行（泄 a 生 b，即 a 所生者）
        bridge = SHENG[a]
        has_bridge = counts.get(bridge, 0) > 0
        out.append({
            "war": f"{a}{b}交战",
            "bridge": bridge,
            "bridge_present": has_bridge,
            "read": (f"得{bridge}通关, 战局可通" if has_bridge
                     else f"无{bridge}通关, 战局硬磕"),
        })
    return out


def changsheng_read(pos: str) -> str:
    """十二长生 → 行运读法（三命通会论大运）。未知返回空串。"""
    return CHANGSHENG_READ.get(pos, "")


# ============================================================================
# 第二轮精读增量（v7.18 追加）：滴天髓从化/清浊/众寡/真神假神/隐显/岁运、
# 子平真诠生克先后与吉凶神破格成格、三命通会小运与太岁。
# 模块保持自包含（常量与 pai_pan.py 同源），供独立加载与测试。
# ============================================================================

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
YANG_GAN = set("甲丙戊庚壬")

WX = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}
CANG = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
# 五合与合化结果（滴天髓化象：甲己化土、乙庚化金、丙辛化水、丁壬化木、戊癸化火）
WUHE = {frozenset(p): h for p, h in
        [("甲己", "土"), ("乙庚", "金"), ("丙辛", "水"), ("丁壬", "木"), ("戊癸", "火")]}
LIUHE = {"子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"}
CHONG_PAIRS = frozenset(frozenset(x) for x in
                        ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"))
SHENG_FANG = set("寅申巳亥")   # 四生方：冲则动
SIKU = set("辰戌丑未")         # 四库：冲则开
SIBAI = set("子午卯酉")        # 四败/四正：逢冲仔细推

SHI_GROUP = {
    "比肩": "比劫", "劫财": "比劫",
    "食神": "食伤", "伤官": "食伤",
    "正财": "财", "偏财": "财",
    "正官": "官杀", "七杀": "官杀",
    "正印": "印", "偏印": "印",
}


def _shishen(day_gan: str, other: str) -> str:
    """十神（与 pai_pan.shishen 同源，供自包含使用）。"""
    if other == day_gan:
        return "比肩"
    d, o = WX[day_gan], WX[other]
    same = (day_gan in YANG_GAN) == (other in YANG_GAN)
    if o == d:
        return "劫财"
    if SHENG[d] == o:
        return "食神" if same else "伤官"
    if KE[d] == o:
        return "偏财" if same else "正财"
    if SHENG[o] == d:
        return "偏印" if same else "正印"
    return "七杀" if same else "正官"


def _he_pair(a: str, b: str) -> str:
    """两干是否五合，返回合化五行（不合返回空串）。"""
    return WUHE.get(frozenset((a, b)), "")


def _idx60(gan: str, zhi: str) -> int:
    """六十甲子索引：甲子=0。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for n in range(60):
        if n % 10 == gi and n % 12 == zi:
            return n
    return 0


def cong_hua_judge(day_gan: str, month_zhi: str, pillars: list,
                   counts: dict | None = None) -> dict:
    """从化判定 — 滴天髓从象/化象/假从/假化/顺局 + 千里命稿从财/从杀/从儿构成。

    pillars: [{"gan","zhi","canggan"(可选)}] 四柱；counts: 五行计数（含藏干，可选）。
    返回 {"verdict", "use", "basis"}。S 级：全部由干支旺衰与生克推导。
    """
    basis = []
    if counts is None:
        counts = {}
        for p in pillars:
            counts[WX[p["gan"]]] = counts.get(WX[p["gan"]], 0) + 1
            for g in p.get("canggan", CANG[p["zhi"]]):
                counts[WX[g]] = counts.get(WX[g], 0) + 1
    d_wx = WX[day_gan]
    # 根气：本气藏干为强根，余气/库根为弱根（千里命稿"无一点生旺之气"只计真根）
    strong_root = 0
    weak_root = 0
    yin_count = 0
    shi = {"比劫": 0, "食伤": 0, "财": 0, "官杀": 0, "印": 0}
    for p in pillars:
        cang = p.get("canggan", CANG[p["zhi"]])
        for i, g in enumerate(cang):
            g_wx = WX[g]
            if g_wx == d_wx:
                if i == 0:
                    strong_root += 1
                else:
                    weak_root += 1
            elif SHENG[g_wx] == d_wx:
                yin_count += 1
                if i == 0:
                    strong_root += 1
                else:
                    weak_root += 1
        for g in [p["gan"]] + cang:
            shi[SHI_GROUP[_shishen(day_gan, g)]] += 1
    has_strong = strong_root > 0
    has_weak = weak_root > 1
    root_ok = (not has_strong) and (not has_weak)

    month_wx = WX[CANG[month_zhi][0]]
    month_shi = _shishen(day_gan, CANG[month_zhi][0])
    gans = [p["gan"] for p in pillars]

    # 化格优先（"化得真者只论化"）：日干与月干/时干五合 + 化神当令 + 见辰（龙）
    for other in (gans[1], gans[3]):
        hua = _he_pair(day_gan, other)
        if not hua:
            continue
        if month_wx == hua and "辰" in [p["zhi"] for p in pillars]:
            basis.append(f"日干{day_gan}与{other}合, 化神{hua}当令且见辰(龙), 化得真")
            return {"verdict": f"真化{hua}", "use": hua,
                    "basis": basis + ["既化则只论化神, 甲乙再见亦不作争合妒合论"]}
        basis.append(f"日干{day_gan}与{other}合, 化神{hua}" +
                     ("不当令" if month_wx != hua else "当令") +
                     ("且无龙(辰)运之" if "辰" not in [p["zhi"] for p in pillars]
                      else ""))
        return {"verdict": f"假化{hua}", "use": hua,
                "basis": basis + ["合而不真, 岁运扶起合神亦可取贵, 人多执滞偏拗"]}

    # 从财（千里命稿）：日主衰弱 + 生当财月 + 财势满盘 + 无一点生旺之气
    if SHI_GROUP[month_shi] == "财" and shi["财"] == max(shi.values()):
        if root_ok and shi["财"] >= 5:
            basis.append(f"生当财月({month_zhi}月), 财势{shi['财']}满盘, "
                         f"日主无根(强根{strong_root}弱根{weak_root}), 不能任财只得从之")
            return {"verdict": "真从财", "use": "财",
                    "basis": basis + ["喜食伤财之帮扶, 忌比劫印之助身, 逢官不妨"]}
        if (not root_ok) and shi["财"] >= 5:
            basis.append(f"财势{shi['财']}满盘但日主有暗根, 从之不真")
            return {"verdict": "假从财", "use": "财",
                    "basis": basis + ["岁运财官得地亦可取富贵, 但祸福参半"]}

    # 从杀/从官（千里命稿）：日主衰弱 + 杀旺而多 + 无印滋身 + 身不能任杀
    if (SHI_GROUP[month_shi] == "官杀" or shi["官杀"] >= 6) and shi["印"] == 0:
        if root_ok and shi["官杀"] >= 4:
            basis.append(f"杀旺而多({shi['官杀']}), 无印滋身, 日主无根, 只得从杀")
            return {"verdict": "真从杀", "use": "杀",
                    "basis": basis + ["喜财杀滋生, 忌印之泄杀生身, 劫比抗杀亦非宜"]}
        if (not root_ok) and shi["官杀"] >= 4:
            basis.append(f"杀势{shi['官杀']}但日主有暗生, 从之不真")
            return {"verdict": "假从杀", "use": "杀",
                    "basis": basis + ["岁运杀旺亦可发, 但心术不端或不能免祸"]}

    # 从儿/顺局（千里命稿从儿 + 滴天髓顺局"从儿不管身强弱, 只要吾儿又得儿"）
    if SHI_GROUP[month_shi] == "食伤" and shi["食伤"] == max(shi.values()):
        if shi["印"] == 0 and shi["食伤"] >= 4:
            er_you_er = shi["财"] > 0
            basis.append(f"伤食当旺({shi['食伤']}), 无印生身, 从之" +
                         (", 儿又得儿(食伤生财)为流通" if er_you_er
                          else ", 惜儿不得儿(无财)气不流通"))
            return {"verdict": "真从儿", "use": "食伤",
                    "basis": basis + ["不怕比劫(比劫仍生伤食), 喜财(儿又生儿), 忌印"]}
        if shi["印"] >= 1 and shi["食伤"] >= 4:
            basis.append(f"伤食旺({shi['食伤']})而印暗滋身, 从之不真")
            return {"verdict": "假从儿", "use": "食伤",
                    "basis": basis + ["岁运制印助食伤亦可发, 但格局不纯"]}

    basis.append(f"日主有{strong_root}强根{weak_root}弱根(或势不专一), 不入从化")
    return {"verdict": "普通格局", "use": "月令用神", "basis": basis}


def chong_read(z1: str, z2: str, month_zhi: str) -> dict:
    """地支六冲地类读法 — 滴天髓地支章。

    "生方怕动库宜开, 败地逢冲仔细推"；"旺者冲衰衰者拔, 衰神冲旺旺神发"。
    月令本气为旺衰基准。S 级。
    """
    if frozenset((z1, z2)) not in CHONG_PAIRS:
        return {"is_chong": False, "kind": "", "read": "非六冲, 不论"}
    kind = ("生方" if z1 in SHENG_FANG else
            "四库" if z1 in SIKU else "四败")
    m_wx = WX[CANG[month_zhi][0]]
    w1, w2 = WX[z1], WX[z2]

    def is_wang(wx: str) -> bool:
        return wx == m_wx or SHENG[m_wx] == wx

    wang = None
    ba = None
    if is_wang(w1) and not is_wang(w2):
        wang, ba = z1, z2
    elif is_wang(w2) and not is_wang(w1):
        wang, ba = z2, z1
    if kind == "生方":
        read = "生方逢冲, 怕动(生方忌冲动)"
    elif kind == "四库":
        read = "四库逢冲, 宜开(库不冲不开)"
    else:
        read = "败地逢冲, 仔细推(依旺衰与合局分吉凶)"
    if wang is not None:
        read += f"; 旺者{wang}冲衰者{ba}, 衰者被拔"
    elif is_wang(w1) and is_wang(w2):
        read += "; 两皆乘旺, 冲则两旺俱发, 亦防太过"
    else:
        read += "; 旺衰相当, 以邻干与会局分胜负"
    return {"is_chong": True, "kind": kind, "wang": wang, "ba": ba,
            "read": read}


def qingzhuo_check(day_gan: str, pillars: list) -> dict:
    """清浊检测 — 滴天髓清气/浊气章（+ 官杀章/伤官章可混不可混之辨）。

    浊 = 混杂：官杀混杂、伤官见官无财、食枭并透、财印相戕、印绶双透、双财争合。
    S 级。返回 {"checks", "turbid", "grade"}。
    """
    gans = [p["gan"] for p in pillars]
    gan_shi = {g: _shishen(day_gan, g) for g in gans}
    names = set(gan_shi.values())
    checks = []

    def add(name, present, read):
        checks.append({"name": name, "present": present, "read": read})

    hun = "正官" in names and "七杀" in names
    add("官杀混杂", hun, "官杀两见, 各自为政, 去一取清方贵" if hun else "")

    shang_guan = "伤官" in names
    guan = "正官" in names
    cai = "正财" in names or "偏财" in names
    add("伤官见官", shang_guan and guan and not cai,
        "伤官见官无财通关, 祸" if shang_guan and guan and not cai else
        ("伤官见官而有财, 财通关可解" if shang_guan and guan and cai else ""))

    xiao = "偏印" in names
    shi = "食神" in names
    add("食枭并透", xiao and shi and not cai,
        "枭神夺食无财制枭" if xiao and shi and not cai else
        ("枭食并透而有财, 财制枭存食" if xiao and shi and cai else ""))

    yin = "正印" in names or "偏印" in names
    cai_gan = [g for g, s in gan_shi.items() if s in ("正财", "偏财")]
    yin_gan = [g for g, s in gan_shi.items() if s in ("正印", "偏印")]
    guan_gan = [g for g, s in gan_shi.items() if s in ("正官", "七杀")]
    add("财印相戕", bool(cai_gan) and bool(yin_gan) and not guan_gan,
        "财坏印无官通关, 印格遇之破" if cai_gan and yin_gan and not guan_gan else
        ("财印并透而有官, 官通关财不坏印" if cai_gan and yin_gan and guan_gan else ""))

    add("印绶双透", "正印" in names and "偏印" in names,
        "偏正叠出, 反为不秀(印重则浊)" if "正印" in names and "偏印" in names else "")

    zheng_cai = len(cai_gan) >= 2 and any(
        _he_pair(day_gan, g) for g in cai_gan)
    add("双财争合", zheng_cai,
        "财星两透争合日主, 主财来财去" if zheng_cai else "")

    turbid = sum(1 for c in checks if c["present"])
    grade = "清" if turbid == 0 else ("半清半浊" if turbid == 1 else "浊")
    return {"checks": checks, "turbid": turbid, "grade": grade}


def zhonggua_read(day_gan: str, counts: dict) -> dict:
    """众寡读法 — 滴天髓众寡章："强众而敌寡者, 势在去其寡;
    强寡而敌众者, 势在成乎众"。S 级。
    """
    d_wx = WX[day_gan]
    top_wx = max(counts, key=counts.get) if counts else ""
    top_n = counts.get(top_wx, 0)
    lone = [x for x in WUXING if counts.get(x, 0) == 1]
    foe_top = [x for x in WUXING
               if x != top_wx and counts.get(x, 0) >= 6]
    if top_n >= 6 and foe_top:
        read = f"强众({top_wx}{top_n})敌众({foe_top}), 势在成乎众"
    elif top_n >= 6 and lone:
        read = f"强众({top_wx}{top_n})敌寡({lone}), 势在去其寡"
    elif lone and top_n >= 4:
        read = f"众({top_wx}{top_n})与孤寡({lone})相持, 去寡成众两可, 以月令定去留"
    else:
        read = "众寡不显, 无孤字可去, 按常格论"
    help_n = counts.get(d_wx, 0)
    yin_wx = next((x for x in WUXING if SHENG[x] == d_wx), "")
    help_n += counts.get(yin_wx, 0)
    return {"top": top_wx, "top_n": top_n, "lone": lone,
            "self_side": help_n, "read": read}


def zhenjia_check(month_zhi: str, pillars: list) -> dict:
    """真神假神 — 滴天髓真神/假神章："令上寻真聚得真, 假神休要乱真神;
    提纲不与真神照, 暗处寻真也有真"。S 级。
    """
    ren_yuan = CANG[month_zhi]
    gans = [p["gan"] for p in pillars]
    zhen = [g for g in ren_yuan if g in gans]
    zhen_primary = ren_yuan[0] in gans
    jia = []
    seen = set()
    for g in gans:
        if g in ren_yuan or g in seen:
            continue
        seen.add(g)
        if sum(1 for x in gans if WX[x] == WX[g]) >= 2:
            jia.append(g)
    if zhen:
        read = f"真神({''.join(zhen)})透干得用, 生平贵" + (
            "（本气得令透出, 为真之最）" if zhen_primary else "（中余气透干, 真而不全）")
    elif jia:
        read = f"提纲不照, 假神({''.join(jia)})透干党多乱真, 碌碌困顿"
    else:
        read = "提纲不照, 亦无假神乱局, 暗处寻真, 观其会局与岁运"
    return {"zhen": zhen, "zhen_primary": zhen_primary, "jia": jia,
            "read": read}


def yinxian_read(day_gan: str, pillars: list, use_wx: str) -> dict:
    """隐显读法 — 滴天髓隐显章："吉神太露, 起争夺之风; 凶物深藏,
    成养虎之患"。S 级（结构性注记）。
    """
    gans = [p["gan"] for p in pillars]
    use_exposed = any(WX[g] == use_wx for g in gans)
    ji_wx = next((x for x in WUXING if KE[x] == use_wx), "")
    ji_hidden = []
    for p in pillars:
        for g in p.get("canggan", CANG[p["zhi"]]):
            if WX[g] == ji_wx and not any(WX[x] == ji_wx for x in gans):
                ji_hidden.append(g)
    parts = []
    if use_exposed:
        parts.append(f"用神{use_wx}透干而露, 岁运忌神必起争夺, 藏用为妙")
    else:
        parts.append(f"用神{use_wx}藏支不露, 不招争夺, 为暗用吉神")
    if ji_hidden:
        parts.append(f"忌神{ji_wx}({''.join(sorted(set(ji_hidden)))})深藏于支, "
                     "伏而待发, 岁运冲扶之则为患(养虎之患), 宜制化")
    else:
        parts.append(f"忌神{ji_wx}不藏或已透, 明透者制化得宜则吉")
    return {"use_exposed": use_exposed, "ji_hidden": ji_hidden,
            "read": "；".join(parts)}


def suiyun_relation(yun_gz: str, nian_gz: str) -> dict:
    """岁运战冲和好 — 滴天髓岁运章："战冲视孰降, 和好视孰切"。
    战=干相克, 冲=支六冲, 和=干五合, 好=同类比助。S 级。
    """
    yg, yz = yun_gz[0], yun_gz[1]
    ng, nz = nian_gz[0], nian_gz[1]
    gan_rel, zhi_rel = "", ""
    if _he_pair(yg, ng):
        # 五合优先于相克（滴天髓：乙运庚年、庚运乙则和）
        gan_rel = f"和(干合, {yg}{ng}合)"
    elif KE[WX[yg]] == WX[ng]:
        gan_rel = "战(运伐岁)"
    elif KE[WX[ng]] == WX[yg]:
        gan_rel = "战(岁伐运)"
    elif WX[yg] == WX[ng]:
        gan_rel = "好(同类比助)" if yg != ng else "并(同字)"
    else:
        gan_rel = "生克不涉, 平行"
    if frozenset((yz, nz)) in CHONG_PAIRS:
        zhi_rel = "冲(支六冲)"
    elif frozenset((yz, nz)) in frozenset(frozenset(x) for x in LIUHE):
        zhi_rel = f"六合({''.join(sorted((yz, nz)))})"
    elif WX[yz] == WX[nz]:
        zhi_rel = "同类"
    else:
        zhi_rel = "无冲合"
    read = f"天干{gan_rel}; 地支{zhi_rel}"
    if "战" in gan_rel or "冲" in zhi_rel:
        read += "。战冲以众寡旺衰定孰降孰胜"
    elif "和" in gan_rel or "合" in zhi_rel:
        read += "。和好以日主喜忌定孰切孰利"
    return {"gan": gan_rel, "zhi": zhi_rel, "read": read}


def _first_pos(gans: list, day_gan: str, groups: tuple) -> int | None:
    """干序列中第一个属于指定十神组的干的位置。"""
    for i, g in enumerate(gans):
        if SHI_GROUP[_shishen(day_gan, g)] in groups:
            return i
    return None


def shengke_order(gans: list, day_gan: str, ge: str) -> dict:
    """生克先后分吉凶 — 子平真诠"论生克先后分吉凶"：
    同此生克, 先后之间遂分吉凶。gans=[年,月,日,时]干序列。
    ge: 官格/印格/食格/杀格。S 级。
    """
    RULES = {
        "官格": (("食伤",), ("财",), "伤官先破官, 财后通关"),
        "印格": (("财",), ("印",), "财先坏印, 印后复原"),
    }
    if ge == "食格":
        # 食格之破为枭（偏印），非泛印组；正印不夺食
        p_b = next((i for i, g in enumerate(gans)
                    if _shishen(day_gan, g) == "偏印"), None)
        p_r = _first_pos(gans, day_gan, ("财",))
        if p_b is None or p_r is None:
            return {"ge": ge, "verdict": "不构成先后, 按常态论",
                    "detail": f"枭位{p_b} 财位{p_r}"}
        if p_b < p_r:
            return {"ge": ge, "verdict": "先凶后吉", "detail":
                    "枭先夺食在前, 财后制枭在后, 早年受损, 晚运必亨"}
        return {"ge": ge, "verdict": "先吉后凶", "detail":
                "财先枭后: 财前成局, 枭后夺食, 早年亨通, 晚运必淡"}
    if ge == "杀格":
        # 杀格特例（原文）：财先食后贵（财助杀而后食制杀）；食先财后不贵（食制杀而财党煞）
        p_cai = _first_pos(gans, day_gan, ("财",))
        p_shi = _first_pos(gans, day_gan, ("食伤",))
        if p_cai is None or p_shi is None:
            return {"ge": ge, "verdict": "不构成先后, 按常态论",
                    "detail": f"财位{p_cai} 食位{p_shi}"}
        if p_cai < p_shi:
            return {"ge": ge, "verdict": "吉", "detail":
                    "财先食后: 财以助用(生杀)在前, 食以制杀在后, 不失大贵"}
        return {"ge": ge, "verdict": "凶", "detail":
                "食先财后: 食先制杀而财后转食党煞, 非特不贵, 后运萧索"}
    if ge not in RULES:
        return {"ge": ge, "verdict": "", "detail": "非先后法所论之格"}
    (breaker,), (reliever,), note = RULES[ge]
    p_b = _first_pos(gans, day_gan, (breaker,))
    p_r = _first_pos(gans, day_gan, (reliever,))
    if p_b is None or p_r is None:
        return {"ge": ge, "verdict": "不构成先后, 按常态论",
                "detail": f"{breaker}位{p_b} {reliever}位{p_r}"}
    if p_b < p_r:
        return {"ge": ge, "verdict": "先凶后吉",
                "detail": f"{note}: {breaker}在前为害在先, {reliever}在后有救, "
                          "早年受损, 后运有结局"}
    return {"ge": ge, "verdict": "先吉后凶",
            "detail": f"{note}: {reliever}在前成局在先, {breaker}在后破局在晚, "
                      "早年稍顺, 终无结局"}


def jixiong_ge_check(day_gan: str, pillars: list, ge: str) -> dict:
    """吉神破格 / 凶神成格 — 子平真诠"论四吉神能破格""论四凶神能成格"：
    官忌食伤, 财畏比劫, 印惧财破, 食畏枭夺; 煞伤枭刃施之得宜亦能成格。
    S 级。ge: 官格/财格/印格/食格/杀格。
    """
    gans = [p["gan"] for p in pillars]
    names = {_shishen(day_gan, g) for g in gans}
    has = lambda grp: any(SHI_GROUP[s] == grp for s in names)
    breaks, saves = [], []

    if ge == "官格":
        if has("食伤") and not has("财"):
            breaks.append("官忌食伤, 无财通关则破")
        if has("食伤") and has("财"):
            saves.append("财泄伤生官, 通关成格")
    elif ge == "财格":
        if has("比劫") and not (has("食伤") or has("官杀")):
            breaks.append("财畏比劫, 无救则破")
        if has("比劫") and has("食伤"):
            saves.append("伤官泄劫生财, 解厄成格")
        if has("比劫") and has("官杀"):
            saves.append("官杀制劫护财, 成格")
    elif ge == "印格":
        if has("财") and not (has("比劫") or has("官杀")):
            breaks.append("印惧财破, 无救则破")
        if has("财") and has("比劫"):
            saves.append("劫财制财护印, 成格")
        if has("财") and has("官杀"):
            saves.append("财生官, 官生印, 通关成格")
        if "七杀" in names:
            saves.append("印绶根轻, 透煞为助, 煞能成格")
    elif ge == "食格":
        if "偏印" in names and not has("财"):
            breaks.append("食畏枭夺, 无财制枭则破")
        if "偏印" in names and has("财"):
            saves.append("财制枭存食, 成格")
        if "七杀" in names:
            saves.append("食神带煞, 食制杀为权")
    elif ge == "杀格":
        if has("食伤"):
            saves.append("煞用食制, 上也")
        if has("印") and not has("财"):
            saves.append("煞用印化, 杀印相生")
        if "偏印" in names and has("食伤"):
            breaks.append("枭夺食而杀无制, 破")
        if has("财") and has("食伤"):
            breaks.append("财转食党煞, 破")
    else:
        return {"ge": ge, "breaks": breaks, "saves": saves,
                "read": "非吉凶神破成法所论之格"}
    read = ("；".join(breaks) if breaks else "无破格之虞") + \
        ("；救应: " + "；".join(saves) if saves else "")
    return {"ge": ge, "breaks": breaks, "saves": saves, "read": read}


def xiaoyun_pillar(year_gan: str, gender: str, hour_gz: str, age: int,
                   method: str = "zuixingzi") -> str:
    """小运（行年）— 三命通会论小运：补大运之不足, 童限未交大运专用。
    method="zuixingzi"（醉醒子法, 三命通会称屡验）：男女皆由时柱起行,
    阳年男/阴年女顺行, 反则逆行, 一位一年;
    method="gufa"（古法）：男起丙寅顺行, 女起壬申逆行。S 级。
    """
    age = max(1, int(age))
    if method == "gufa":
        # 古法：1 岁即起点（男起丙寅、女起壬申），2 岁走一位
        start = "丙寅" if gender == "male" else "壬申"
        step = 1 if gender == "male" else -1
        n = (_idx60(start[0], start[1]) + step * (age - 1)) % 60
    else:
        # 醉醒子法：堕地即行时柱下一柱（1 岁已走一位）
        start = hour_gz
        forward = (gender == "male") == (year_gan in YANG_GAN)
        step = 1 if forward else -1
        n = (_idx60(start[0], start[1]) + step * age) % 60
    return GAN[n % 10] + ZHI[n % 12]


def taisui_check(day_gz: str, birth_year_gz: str, yun_gz: str | None,
                 liunian_gz: str, day_gan: str) -> dict:
    """太岁关系 — 三命通会论太岁：岁伤日干祸轻, 日犯岁君灾重（有救则免）;
    真太岁（转趾煞）; 征太岁; 岁运并临（羊刃七煞为凶, 财官印绶亦吉）。S 级。
    """
    rels = []
    dg, dz = day_gz[0], day_gz[1]
    lg, lz = liunian_gz[0], liunian_gz[1]
    if KE[WX[lg]] == WX[dg]:
        rels.append("岁伤日干（君治臣, 祸轻）")
    elif KE[WX[dg]] == WX[lg]:
        rels.append("日犯岁君（下凌上, 灾重; 四柱有制日干或合岁干者, 为有救）")
    if frozenset((dz, lz)) in CHONG_PAIRS:
        rels.append("征太岁（日支冲岁支, 其年则凶）")
    if yun_gz:
        if frozenset((yun_gz[1], lz)) in CHONG_PAIRS or KE[WX[yun_gz[0]]] == WX[lg]:
            rels.append("征太岁（运干支伤冲太岁, 其年则凶）")
        if yun_gz == liunian_gz:
            s = _shishen(day_gan, yun_gz[0])
            if s == "七杀":
                rels.append("岁运并临, 七杀为凶")
            elif SHI_GROUP[s] in ("财", "官杀", "印"):
                rels.append("岁运并临, 财官印绶亦吉")
            else:
                rels.append("岁运并临, 喜忌参半, 以原局旺衰定")
    if birth_year_gz == liunian_gz:
        rels.append("真太岁（转趾煞）: 与大运日主相和相顺则吉, 值刑冲破害则凶")
    if not rels:
        rels.append("太岁与命局无直接克冲, 以岁干所透十神论岁喜忌")
    return {"relations": rels, "read": "；".join(rels)}
