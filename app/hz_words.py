"""HotZone FM — 文字找圖 without AI.

Every picture gets a lowercase "words" text: its folder path + file name + any text embedded in the file
(ComfyUI / A1111 prompts, PNG Description/Comment/Title, EXIF ImageDescription, Windows 標籤/主旨/註解 (XP*),
XMP dc:subject / description).  A search word is expanded with a hand-written bilingual dictionary
(聖誕節 -> christmas, xmas, santa, 聖誕 ...), and holiday words also match the date the photo was taken
(聖誕節 -> taken 12/20 - 12/26, 春節 -> around that year's Lunar New Year).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import time

import hz_win as W

# ---------------------------------------------------------------------------- dictionary
# Each line is one concept; every word on the line finds the others.  Lowercase, English matches as substring.
_GROUPS = """
聖誕 聖誕節 耶誕 耶誕節 christmas xmas x'mas santa 聖誕老人 聖誕樹 reindeer 麋鹿 noel クリスマス サンタ gingerbread mistletoe
新年 跨年 元旦 new year newyear new_year 正月 お正月 countdown
春節 過年 農曆新年 除夕 lunar new year chinese new year 紅包 舞獅 lion dance 春聯 年夜飯
萬聖節 萬聖 halloween 南瓜 pumpkin jack-o-lantern ハロウィン witch 女巫 vampire 吸血鬼
情人節 valentine 바렌타인 バレンタイン
生日 birthday 蛋糕 cake 慶生 誕生日
婚禮 婚紗 結婚 wedding bride 新娘 groom 新郎 bridal 婚紗照 ウェディング
畢業 graduation 學士服 卒業
煙火 煙花 fireworks firework 花火
海邊 海灘 沙灘 beach seaside 海 ocean sea shore 海岸 coast 浜辺
山 mountain mountains 登山 hiking 山頂 peak 山岳
雪 下雪 snow snowy snowing 雪景 winter 冬天 冬 雪人 snowman
雨 下雨 rain rainy raining 雨天 umbrella 雨傘
夜景 夜晚 night nighttime 夜 city lights 夜空 night sky
夕陽 日落 sunset dusk 黃昏 夕焼け golden hour
日出 sunrise dawn 朝日
天空 sky 雲 cloud clouds blue sky
森林 樹林 forest woods 樹 tree trees jungle 森
花 flower flowers 花朵 bouquet 花束 blossom
櫻花 sakura cherry blossom 桜
楓葉 楓 maple autumn leaves 紅葉 秋天 autumn fall
城市 都市 city urban 街 街道 street downtown cityscape
室內 indoor indoors interior room 房間
臥室 bedroom 床 bed
咖啡廳 咖啡 cafe café coffee coffee shop
餐廳 restaurant 用餐 dining
教室 classroom school 學校 校園 学校
辦公室 office
教堂 church cathedral chapel
神社 寺廟 寺 shrine temple 鳥居 torii
城堡 castle palace 宮殿
游泳池 泳池 pool swimming pool
食物 美食 food meal 料理 dish 便當
貓 cat cats kitten 貓咪 猫 neko
狗 dog dogs puppy 狗狗 犬
車 汽車 car cars vehicle 跑車 sports car 車子 auto
機車 摩托車 motorcycle motorbike scooter bike
腳踏車 自行車 bicycle bike
飛機 airplane plane aircraft 機場 airport
火車 train 電車 railway 鐵路 地鐵 subway metro
船 boat ship 遊艇 yacht
人 人物 person people portrait 人像 肖像 1girl 1boy girl boy woman man
女生 女孩 女性 girl woman female 1girl 2girls 少女 lady
男生 男孩 男性 boy man male 1boy
小孩 兒童 child children kid kids baby 嬰兒 寶寶
自拍 selfie
合照 團體照 group photo group multiple girls multiple boys 2girls 3girls
和服 kimono yukata 浴衣 着物
旗袍 cheongsam qipao
西裝 suit 正裝 tuxedo business suit
洋裝 連身裙 dress gown 禮服 evening dress
裙子 skirt 短裙 miniskirt
制服 uniform 校服 school uniform serafuku 水手服 sailor
女僕 maid 女僕裝 maid outfit メイド
泳裝 泳衣 swimsuit bikini 比基尼 swimwear 水着
運動服 sportswear 運動 sport sports gym 健身
戲服 cosplay costume 角色扮演 コスプレ
帽子 hat cap 帽
眼鏡 glasses eyewear 墨鏡 sunglasses
長髮 long hair
短髮 short hair
金髮 blonde hair blond hair
黑髮 black hair
紅髮 red hair
銀髮 白髮 silver hair white hair
雙馬尾 twintails
馬尾 ponytail
微笑 笑 smile smiling laugh 笑顏
裝飾 decoration decorations ornament ornaments 佈置 燈飾 lights string lights
禮物 gift present gifts presents
燈籠 lantern lanterns 提燈
手機 手機拍的 phone iphone smartphone 스마트폰
單眼 相機 camera dslr canon nikon sony fujifilm olympus panasonic leica
截圖 螢幕截圖 screenshot スクリーンショット
""".strip().splitlines()

# English words that are too short / too common to match as substrings on their own
_WHOLE_WORD = {'sea', 'man', 'cat', 'dog', 'car', 'sky', 'bed', 'hat', 'cap', 'sun', 'boy', 'kid', 'fall', 'bike', 'auto', 'room', 'tree', 'pool', 'gift', 'dish', 'suit', 'lady', 'rain', 'snow', 'peak', 'ship', 'boat', 'cake', 'smile', 'night', 'woods', 'group', 'sport', 'phone', 'sony', 'canon'}

# multi-word phrases kept together when a line is split on spaces
_PHRASES = sorted(['new year', 'lunar new year', 'chinese new year', 'lion dance', 'blue sky', 'city lights', 'night sky', 'golden hour',
                   'cherry blossom', 'autumn leaves', 'coffee shop', 'swimming pool', 'sports car', 'group photo', 'multiple girls', 'multiple boys',
                   'business suit', 'evening dress', 'school uniform', 'maid outfit', 'long hair', 'short hair', 'blonde hair', 'black hair',
                   'red hair', 'blond hair', 'silver hair', 'white hair', 'string lights'], key=len, reverse=True)
GROUPS = []
for _ln in _GROUPS:
    _ln = _ln.lower()
    for _ph in _PHRASES: _ln = _ln.replace(_ph, _ph.replace(' ', '\x01'))
    GROUPS.append([w.replace('\x01', ' ') for w in _ln.split() if w])

COLOR_WORDS = {'紅': ['紅', '紅色', 'red'], '橙': ['橙', '橘', '橙色', '橘色', 'orange'], '黃': ['黃', '黃色', 'yellow'],
               '綠': ['綠', '綠色', 'green'], '青': ['青', '青色', 'cyan', 'teal'], '藍': ['藍', '藍色', 'blue'],
               '紫': ['紫', '紫色', 'purple', 'violet'], '粉': ['粉', '粉紅', '粉紅色', 'pink'], '棕': ['棕', '棕色', '咖啡色', 'brown'],
               '黑': ['黑', '黑色', 'black'], '白': ['白', '白色', 'white'], '灰': ['灰', '灰色', 'gray', 'grey']}

# ---------------------------------------------------------------------------- holidays (date taken)
_LUNAR_NY = {2005: '02-09', 2006: '01-29', 2007: '02-18', 2008: '02-07', 2009: '01-26', 2010: '02-14', 2011: '02-03', 2012: '01-23',
             2013: '02-10', 2014: '01-31', 2015: '02-19', 2016: '02-08', 2017: '01-28', 2018: '02-16', 2019: '02-05', 2020: '01-25',
             2021: '02-12', 2022: '02-01', 2023: '01-22', 2024: '02-10', 2025: '01-29', 2026: '02-17', 2027: '02-06', 2028: '01-26',
             2029: '02-13', 2030: '02-03', 2031: '01-23', 2032: '02-11', 2033: '01-31', 2034: '02-19', 2035: '02-08'}
HOLIDAYS = {  # concept head word -> fixed month-day window (inclusive) or 'lunar'
    '聖誕': ('12-20', '12-26'), '新年': ('12-31', '01-01'), '萬聖節': ('10-28', '11-01'), '情人節': ('02-13', '02-15'), '春節': 'lunar',
}


def holiday_ranges(head):
    """-> [(t0, t1)] local-time epoch ranges, or a (md0, md1) window for fixed dates."""
    h = HOLIDAYS.get(head)
    if h == 'lunar':
        out = []
        for y, md in _LUNAR_NY.items():
            d = _dt.datetime.strptime(f'{y}-{md}', '%Y-%m-%d')
            out.append((time.mktime((d - _dt.timedelta(days=2)).timetuple()), time.mktime((d + _dt.timedelta(days=6)).timetuple())))
        return out
    return h


def expand(term):
    """one search word -> (synonyms, concept head or None, colour or None)"""
    t = term.strip().lower()
    syn = {t}; head = None
    for g in GROUPS:
        if t in g or any(len(t) >= 2 and not t.isascii() and t in w for w in g if not w.isascii()):
            syn.update(g); head = head or g[0]
    col = None
    for c, ws in COLOR_WORDS.items():
        if t in ws: col = c; syn.update(w for w in ws if len(w) > 1)
    return sorted(syn, key=len), head, col


_NONWORD = re.compile(r"[^0-9a-z\u00c0-\u024f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+")


def normalize(text):
    """lowercase, every run of punctuation / separators -> one space, padded with spaces."""
    return ' ' + _NONWORD.sub(' ', str(text or '').lower()).strip() + ' '


def like_patterns(w):
    """SQL LIKE patterns for one synonym against normalize()d text (short English words must stand alone)."""
    n = normalize(w).strip()
    if not n: return []
    if n.isascii() and (n in _WHOLE_WORD or len(n) <= 4 or ' ' in n):
        return [f'% {n} %']
    return [f'%{n}%']


# ---------------------------------------------------------------------------- text extraction
def _xp(v):
    if isinstance(v, (bytes, bytearray)):
        try: return bytes(v).decode('utf-16-le', 'ignore').strip('\x00 ')
        except Exception: return ''
    if isinstance(v, (tuple, list)):
        try: return bytes(v).decode('utf-16-le', 'ignore').strip('\x00 ')
        except Exception: return ''
    return str(v or '')


def meta_text(path, im=None):
    """Every human text embedded in the picture, joined.  Never raises."""
    parts = []
    try:
        if path.lower().endswith('.png'):
            import hz_comfy as CF
            texts, _ = CF.png_texts(path)
            if 'prompt' in texts:
                p = CF.parse_comfy(texts['prompt'])
                if p.get('positive'): parts.append(str(p['positive']))
                if p.get('loras'): parts.append(str(p['loras']))
                if not p.get('positive'):   # unusual graphs: take every longer string input
                    try:
                        g = json.loads(texts['prompt'])
                        for node in g.values():
                            if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict): continue
                            for v in node['inputs'].values():
                                if isinstance(v, str) and len(v) > 12 and ' ' in v: parts.append(v)
                    except Exception:
                        pass
            elif 'parameters' in texts:
                parts.append(texts['parameters'].split('Negative prompt:')[0])
            for k in ('Description', 'Comment', 'Title', 'Subject', 'Keywords', 'Author'):
                if texts.get(k): parts.append(texts[k])
    except Exception:
        pass
    own = im is None
    try:
        if own:
            from PIL import Image
            im = Image.open(W.lp(path))
        try:
            ex = im.getexif()
            if ex:
                for tag in (270,):                                          # ImageDescription
                    if ex.get(tag): parts.append(str(ex.get(tag)).strip('\x00 '))
                for tag in (0x9C9B, 0x9C9C, 0x9C9D, 0x9C9E, 0x9C9F):       # XPTitle XPComment XPAuthor XPKeywords XPSubject
                    if ex.get(tag): parts.append(_xp(ex.get(tag)))
                if not path.lower().endswith('.png'):                       # A1111 / Forge JPEG / WebP: prompt in UserComment
                    import hz_comfy as CF
                    t, _wh = CF.exif_parameters(path)
                    if t: parts.append(t.split('Negative prompt:')[0])
        except Exception:
            pass
        xmp = im.info.get('xmp') or im.info.get('XML:com.adobe.xmp')
        if xmp:
            if isinstance(xmp, bytes): xmp = xmp.decode('utf-8', 'ignore')
            for m in re.finditer(r'<(?:dc:subject|dc:description|dc:title|lr:hierarchicalSubject)>(.*?)</', xmp, re.S):
                parts += re.findall(r'<rdf:li[^>]*>([^<]+)</rdf:li>', m.group(1))
    except Exception:
        pass
    finally:
        if own and im is not None:
            try: im.close()
            except Exception: pass
    txt = '\n'.join(x for x in parts if x)
    return txt[:20000]


def words_of(path, meta):
    """-> (normalized text, length of the path part)"""
    pn = normalize(path)
    return pn + normalize(meta).lstrip(), len(pn)


def why(words, syns, path_len):
    """First synonym found and whether it was in the path/name or the embedded text."""
    for w in sorted(syns, key=lambda x: -len(x)):
        for pat in like_patterns(w):
            needle = pat.strip('%')
            i = words.find(needle)
            if i >= 0:
                return f'「{w}」' + ('在檔名／資料夾' if i < path_len else '在圖片內嵌文字（提示詞／標籤）')
    return ''
