"""Reusable, deterministic, unit-tested parser library for the U.S. CPSC
SaferProducts Recall Census (2000-2026).

Incorporates all 7 Wave-3 forensic audit fixes plus deep second-round parser hardening:
  1. Entity extraction across ALL 4 structured fields (Importers, Manufacturers,
     Distributors, Retailers), catching late-2026 Retailers-nested foreign entities,
     handling multi-comma & "of the UK" foreign addresses, "of"-less U.S. addresses,
     and filtering platform corporate-office co-listings (AliExpress/Woot/Amazon
     distributor entries co-listed alongside Chinese 3P sellers).
  2. Domain-stripped & online-phrase-stripped Brick-and-Mortar matching (zero .com
     false positives; full coverage of branded stores, independent shops/outlets/
     galleries nationwide, and commercial distributors), keeping 4_DTC_Online_Only
     strictly pure first-party DTC brand websites.
  3. Clean 6-Archetype taxonomy:
       1_Mkt_FD_China, 2_Mkt_FD_NonChina, 3_Mkt_True_US,
       4_DTC_Online_Only, 5_Omnichannel, 6_Brick_and_Mortar
     (plus 7_Other_Unclear tracked transparently).
  4. Sentence-level negation-aware direct_return parser, gerund-complete photo_verify
     and generalized physical_mutilate parsers, noun-inclusive disposal ("disposal")
     matching, and hazard-gated lithium-ion hazardous-waste classification (zero
     mechanical e-bike/scooter brake/bolt false positives).
  5. Double-count-free injury parser stripping subordinate/breakdown clauses and
     property-damage clauses without dropping co-occurring burn/shock/cut injuries.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Retail Channel & Platform Patterns
# ---------------------------------------------------------------------------
# Major 3P e-commerce marketplaces AND multi-brand online retail intermediaries
# (distinct from first-party DTC brand websites!)
MARKETPLACE_PAT = re.compile(
    r"(?:amazon\.com\b|\b(?:"
    r"amazon(?:\.com)?|"
    r"temu(?:\.com)?|"
    r"shein(?:\.com)?|"
    r"aliexpress(?:\.com)?|"
    r"alibaba(?:\.com)?|"
    r"banggood(?:\.com)?|"
    r"walmart\.com|"
    r"ebay(?:\.com)?|"
    r"etsy(?:\.com)?|"
    r"tiktok\s*shop|"
    r"wish\.com|"
    r"wayfair(?:\.com)?|"
    r"overstock\.com|"
    r"newegg(?:\.com)?|"
    r"dhgate(?:\.com)?|"
    r"rakuten(?:\.com)?|"
    r"mercari(?:\.com)?|"
    r"poshmark(?:\.com)?|"
    r"target\.com|"
    r"homedepot\.com|"
    r"lowes\.com|"
    r"costco\.com|"
    r"samsclub\.com|"
    r"bestbuy\.com|"
    r"bjs\.com|"
    r"bedbathandbeyond\.com|"
    r"kohls\.com|"
    r"macys\.com|"
    r"nordstrom\.com|"
    r"qvc\.com|"
    r"hsn\.com|"
    r"qvc\s+televised|"
    r"hsn\s+television|"
    r"woot(?:\.com)?|"
    r"zulily(?:\.com)?|"
    r"houzz(?:\.com)?|"
    r"chewy(?:\.com)?|"
    r"iherb(?:\.com)?|"
    r"whatnot(?:\.com)?|"
    r"cymax(?:\.com)?|"
    r"sears\.com|"
    r"kmart\.com"
    r")\b)",
    re.IGNORECASE,
)

# Core 3P platform detectors (for Pillar 2 platform generality & Pillar 3 Amazon HAC)
PLAT_PATTERNS: dict[str, re.Pattern[str]] = {
    "plat_amazon": re.compile(r"(?:amazon\.com\b|\bamazon(?:\.com)?\b)", re.IGNORECASE),
    "plat_walmart_com": re.compile(r"\bwalmart\.com\b", re.IGNORECASE),
    "plat_temu": re.compile(r"\btemu(?:\.com)?\b", re.IGNORECASE),
    "plat_shein": re.compile(r"\bshein(?:\.com)?\b", re.IGNORECASE),
    "plat_wayfair": re.compile(r"\bwayfair(?:\.com)?\b", re.IGNORECASE),
    "plat_aliexpress": re.compile(r"\baliexpress(?:\.com)?\b", re.IGNORECASE),
    "plat_ebay_etsy": re.compile(r"\b(?:ebay|etsy)(?:\.com)?\b", re.IGNORECASE),
    "plat_tiktok_wish": re.compile(r"\b(?:tiktok\s*shop|wish\.com|dhgate(?:\.com)?)\b", re.IGNORECASE),
    "plat_target_com": re.compile(r"\btarget\.com\b", re.IGNORECASE),
}

# Strip URLs / e-commerce domains BEFORE testing physical brick-and-mortar patterns
DOMAIN_STRIP_PAT = re.compile(
    r"(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.(?:com|net|org|us|shop|io|co|biz|store|events|tv)(?:/[^\s,.;)]*)?",
    re.IGNORECASE,
)

# Strip non-brick phrases containing "store"/"shop"/"retailer" before physical-store matching
NON_BRICK_PHRASE_STRIP_PAT = re.compile(
    r"(?:"
    r"\bnot\s+sold\s+in\s+stores?\b|"
    r"\btiktok\s+shop\b|"
    r"\betsy(?:\.com)?\s+shop\b|"
    r"\b(?:authorized\s+|other\s+)?online\s+(?:stores?|retailers?|shops?|sellers?|distributors?|marketplaces?|shopping\s+platforms?)\b|"
    r"\b(?:apple\s+|google\s+)?(?:app|play)\s+store\b|"
    r"\bamazon\s+store(?:front)?\b|"
    r"\bweb\s+store\b|"
    r"\be-?commerce\s+stores?\b|"
    r"\bdigital\s+shopping\s+platforms?\b|"
    r"\b(?:dba|doing\s+business\s+as)\s+[a-z0-9\s\-&']{1,35}\s+store\b|"
    r"\bin\s+gap,\s+pennsylvania\b|"
    r"\b(?:bob|betsy|diana)\s+ross\b"
    r")",
    re.IGNORECASE,
)

ONLINE_ONLY_PAT = re.compile(
    r"(?:"
    r"exclusively\s+online|"
    r"only\s+online|"
    r"sold\s+online\s+at|"
    r"online\s+at\s+(?:www\.|[a-z0-9\-]+\.(?:com|net|org|us|shop|co|events))|"
    r"online\s+sales\s+at|"
    r"direct(?:ly)?\s+to\s+consumers\s+online|"
    r"through\s+(?:the\s+firm'?s\s+)?website|"
    r"on\s+its\s+website"
    r")",
    re.IGNORECASE,
)

# Physical brick-and-mortar stores (applied ONLY to domain- & online-phrase-stripped sales text!)
BRICK_PAT = re.compile(
    r"\b(?:"
    r"stores?,?\s+(?:nationwide|in|located\s+in|across|throughout|including|and\s+online)|"
    r"(?:department|specialty|retail|grocery|drug|hardware|home\s+improvement(?:\s+and\s+hardware)?|"
    r"clothing|apparel|furniture|mattress|window\s+treatment|design|supplement|fitness|toy|baby|"
    r"children'?s|sporting\s+goods|pet|book|shoe|bike|bicycle|dive|tack|golf|craft|fabric|outlet|"
    r"discount|dollar|thrift|auto\s+parts|automotive|pool|spa|appliance|electronics|lighting|garden|"
    r"outdoor|camping|hunting|ski|beauty|kitchen|bath|home|gift|party|fireworks|marine|powersports|"
    r"equipment|supply|building\s+supply|plumbing\s+supply|electrical\s+supply|restaurant)\s+"
    r"(?:stores?|shops?|outlets?|centers?|galleries|warehouses?|dealers?)|"
    r"(?:shops?|outlets?|galleries|boutiques?|showrooms?|warehouses?|dealers?|dealerships?|"
    r"wholesalers?|suppliers?|clinics?|salons?|centers?|clubs?|gyms?|facilities|alleys|cafes?|"
    r"installers?|contractors?|national\s+accounts)\s*,?\s*"
    r"(?:nationwide|across|throughout|in\s+[a-z]+|and\s+online)|"
    r"(?:certified|independent|local|regional|authorized|specialty|national|major|various|participating|"
    r"select|commercial|industrial|wholesale)\s+(?:[a-z&'\-]+\s+){0,3}"
    r"(?:stores?|shops?|outlets?|dealers?|dealerships?|retailers?|distributors?|wholesalers?|"
    r"suppliers?|contractors?|installers?|showrooms?|boutiques?|centers?|sporting\s+goods)|"
    r"supermarkets?|"
    r"pharmacies|"
    r"mass\s+merchandisers?|"
    r"warehouse\s+clubs?|"
    r"in-?store|"
    r"brick[\s\-]and[\s\-]mortar|"
    r"walmart(?:\s+stores?)?|"
    r"target(?:\s+stores?)?|"
    r"aldi|"
    r"jc\s*penney|"
    r"j\.?\s*c\.?\s*penney|"
    r"kohl'?s|"
    r"macy'?s|"
    r"costco|"
    r"sam'?s\s+club|"
    r"bj'?s\s+wholesale|"
    r"home\s+depot|"
    r"lowe'?s|"
    r"best\s+buy|"
    r"walgreens|"
    r"cvs|"
    r"rite\s+aid|"
    r"meijer|"
    r"kroger|"
    r"t\.?\s*j\.?\s*maxx|"
    r"tj\s*maxx|"
    r"marshall'?s|"
    r"homegoods|"
    r"nordstrom|"
    r"bloomingdale'?s|"
    r"dillard'?s|"
    r"belk|"
    r"neiman\s+marcus|"
    r"saks\s+fifth|"
    r"dick'?s\s+sporting|"
    r"rei|"
    r"academy(?:\s+sports|\s+stores)?|"
    r"bass\s+pro|"
    r"cabela'?s|"
    r"scheel'?s|"
    r"harbor\s+freight|"
    r"tractor\s+supply|"
    r"ace\s+hardware|"
    r"true\s+value|"
    r"menards|"
    r"dollar\s+tree|"
    r"dollar\s+general|"
    r"family\s+dollar|"
    r"five\s+below|"
    r"big\s+lots|"
    r"burlington|"
    r"ross(?:\s+stores|\s+dress\s+for\s+less)?|"
    r"ikea|"
    r"sephora|"
    r"ulta|"
    r"petco|"
    r"petsmart|"
    r"autozone|"
    r"o'?reilly\s+auto|"
    r"advance\s+auto|"
    r"napa\s+auto|"
    r"sears|"
    r"kmart|"
    r"toys\s*\"?r\"?\s*us|"
    r"babies\s*\"?r\"?\s*us|"
    r"bed\s+bath|"
    r"buybuy\s+baby|"
    r"hobby\s+lobby|"
    r"michaels|"
    r"joann|"
    r"l\.?\s*l\.?\s*bean|"
    r"crate\s+(?:and|&)\s+barrel|"
    r"pottery\s+barn|"
    r"williams[\s\-]sonoma|"
    r"anthropologie|"
    r"urban\s+outfitters|"
    r"gap(?:\s+stores|\s+kids|\s+factory)?|"
    r"old\s+navy|"
    r"banana\s+republic|"
    r"carter'?s|"
    r"gymboree|"
    r"oshkosh|"
    r"wegman'?s|"
    r"food\s+markets?|"
    r"primark|"
    r"publix|"
    r"safeway|"
    r"albertsons|"
    r"h-e-b|"
    r"whole\s+foods|"
    r"trader\s+joe'?s|"
    r"sprouts|"
    r"office\s+depot|"
    r"staples|"
    r"sherwin[\s\-]williams|"
    r"grainger|"
    r"fastenal|"
    r"rooms\s+to\s+go|"
    r"build[\s\-]a[\s\-]bear|"
    r"rh\s+(?:galleries|outlets|baby)|"
    r"vevorstores|"
    r"play\s+it\s+again\s+sports|"
    r"army\s+and\s+air\s+force\s+exchange|"
    r"the\s+restaurant\s+store|"
    r"in\s+stores?|"
    r"(?:sold|distributed)\s+(?:to|through|by)\s+(?:authorized\s+|independent\s+|third-party\s+|commercial\s+|installing\s+|factory\s+)?"
    r"(?:dealers?|contractors?|distributors?|wholesalers?|representatives?|installers?|plumbers?|businesses|fitness\s+facilities)|"
    r"contractors?\s+nationwide|"
    r"retailers?\s+nationwide|"
    r"distributors?\s+(?:of\s+[^\n.]{1,40}\s+)?nationwide"
    r")\b",
    re.IGNORECASE,
)

# Case-sensitive branded physical-store & brick city-location detector (applied to stripped sales text)
BRANDED_PHYSICAL_STORE_PAT = re.compile(
    r"(?:"
    r"\b[A-Z][A-Za-z0-9&'\-]+(?:\s+[A-Za-z0-9&'\-]+){0,4}\s+(?:Stores?|Outlets?|Galleries|Workshop\s+stores?|Tack\s+Shop|Climbing\s+Center)\b|"
    r"\bin\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s+(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New\s+Hampshire|New\s+Jersey|New\s+Mexico|New\s+York|North\s+Carolina|North\s+Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode\s+Island|South\s+Carolina|South\s+Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West\s+Virginia|Wisconsin|Wyoming)\b"
    r")"
)

# ---------------------------------------------------------------------------
# 2. Entity Origin Patterns (ALL 4 Fields: Importers, Manufacturers,
#    Distributors, Retailers)
# ---------------------------------------------------------------------------
US_FULL_STATES_REGEX = (
    r"California|New\s+York|New\s+Jersey|Texas|Illinois|Florida|Washington|"
    r"Pennsylvania|Ohio|Georgia|Massachusetts|Minnesota|Michigan|Colorado|Arizona|Virginia|"
    r"Maryland|North\s+Carolina|South\s+Carolina|Wisconsin|Indiana|Missouri|Tennessee|Oregon|"
    r"Utah|Connecticut|Nevada|Kentucky|Louisiana|Alabama|Iowa|Kansas|Arkansas|Mississippi|"
    r"Nebraska|Oklahoma|Idaho|West\s+Virginia|Maine|New\s+Hampshire|Rhode\s+Island|Montana|"
    r"Delaware|South\s+Dakota|North\s+Dakota|Alaska|Vermont|Wyoming|Hawaii|New\s+Mexico|"
    r"District\s+of\s+Columbia|Puerto\s+Rico"
)

US_STATES_REGEX = (
    r"Calif\.?|N\.Y\.?|N\.J\.?|Tex\.?|Ill\.?|Fla\.?|Wash\.?|Pa\.?|Ga\.?|Mass\.?|"
    r"Minn\.?|Mich\.?|Colo\.?|Ariz\.?|Va\.?|Md\.?|N\.C\.?|S\.C\.?|Wis\.?|Ind\.?|"
    r"Mo\.?|Tenn\.?|Ore\.?|Conn\.?|Nev\.?|Ky\.?|La\.?|Ala\.?|Kan\.?|Ark\.?|Miss\.?|"
    r"Neb\.?|Okla\.?|W\.Va\.?|N\.H\.?|R\.I\.?|Mont\.?|Del\.?|S\.D\.?|N\.D\.?|Vt\.?|"
    r"Wyo\.?|N\.M\.?|D\.C\.?|"
    + US_FULL_STATES_REGEX
    + r"|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
    r"MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
)

# Entity-anchored U.S. location: "[Company], of [City], [State]" OR "[Company], [City], [Full State]"
US_ENTITY_PAT = re.compile(
    rf"(?:"
    rf"(?:,\s*|\s+)of\s+[A-Za-z][A-Za-z0-9\s\.\-']{{1,45}},\s*(?:{US_STATES_REGEX})\b|"
    rf",\s*[A-Z][A-Za-z\.\-']+(?:\s+[A-Z][A-Za-z\.\-']+){{0,3}},\s*(?:{US_FULL_STATES_REGEX}|Calif\.|Ill\.|Fla\.|Mass\.|Minn\.|Mich\.|Pa\.|Tex\.|Wash\.|N\.Y\.|N\.J\.)\b"
    rf")"
)
US_ENTITY_STATE_ONLY_PAT = re.compile(
    rf"(?:,\s*|\s+)of\s+(?:{US_FULL_STATES_REGEX}|the\s+United\s+States|U\.S\.A\.?)\b",
    re.IGNORECASE,
)

# Comprehensive China / Hong Kong foreign-entity detection
CN_PLACES = (
    r"china|hong\s+kong|macau|shenzhen|shenzen|wuhan|zhongshan|guangzhou|"
    r"hangzhou|ningbo|dongguan|xiamen|yiwu|foshan|suzhou|hefei|changsha|"
    r"chengdu|nanjing|qingdao|tianjin|shanghai|beijing|wenzhou|jinhua|"
    r"quanzhou|putian|fuzhou|zhuhai|huizhou|shantou|chaozhou|jiangmen|"
    r"shaoxing|taizhou|jiaxing|huzhou|nantong|wuxi|changzhou|yangzhou|"
    r"xuzhou|jinan|yantai|weifang|zhengzhou|luoyang|xi'?an|chongqing|"
    r"kunming|shenyang|dalian|harbin|changchun|nanchang|guiyang|nanning|"
    r"hengqin|guangdong|zhejiang|fujian|jiangsu|shandong|hebei|henan|"
    r"hunan|hubei|sichuan|anhui|jiangxi|shanxi|shaanxi|liaoning|jilin|"
    r"heilongjiang|guangxi|yunnan|guizhou"
)
CN_ENTITY_PAT = re.compile(
    rf"(?:"
    rf"(?:,\s*|\s+)of\s+(?:[A-Za-z\s\.\-']{{0,35}},\s*){{0,2}}(?:{CN_PLACES})\b|"
    rf"\b(?:{CN_PLACES})\b[^\n;]{{0,80}}\b(?:co\.?,?\s*ltd\.?|limited|technology|trading|e-?commerce|cross-?border|gongsi|maoyi|keji)\b|"
    rf"\b(?:youxian\s*gongsi|maoyi\s*youxian|keji\s*youxian|shangmao|cross-?border\s+information\s+technology|trading\s+co\.?,?\s*ltd\.?)\b"
    rf")",
    re.IGNORECASE,
)

NONCN_FOREIGN_PLACES = (
    r"canada|ontario|quebec|british\s+columbia|alberta|manitoba|montreal|toronto|vancouver|"
    r"united\s+kingdom|u\.k\.?|england|scotland|wales|london|manchester|"
    r"germany|france|italy|spain|netherlands|holland|sweden|denmark|norway|finland|"
    r"switzerland|austria|belgium|poland|ireland|portugal|czech\s+republic|czechia|"
    r"hungary|romania|greece|slovakia|slovenia|croatia|estonia|latvia|lithuania|"
    r"south\s+korea|korea|seoul|japan|tokyo|osaka|australia|sydney|melbourne|"
    r"new\s+zealand|taiwan|taipei|vietnam|thailand|malaysia|indonesia|philippines|"
    r"singapore|india|bangladesh|pakistan|sri\s+lanka|cambodia|armenia|ukraine|serbia|"
    r"bulgaria|cyprus|iceland|luxembourg|malta|"
    r"mexico|brazil|argentina|chile|colombia|peru|israel|turkey|south\s+africa|"
    r"united\s+arab\s+emirates|dubai"
)
# Allow optional "the " and up to 2 comma-separated sub-locations (e.g. "of Laval, QC, Canada" or "of the United Kingdom")
NONCN_FOREIGN_ENTITY_PAT = re.compile(
    rf"(?:,\s*|\s+)of\s+(?:the\s+)?(?:[A-Za-z\s\.\-']{{0,35}},\s*){{0,2}}(?:{NONCN_FOREIGN_PLACES})\b",
    re.IGNORECASE,
)

# 3P marketplace platform corporate office entries (NOT a domestic product brand/importer when
# co-listed alongside a foreign 3P seller!)
PLATFORM_US_OFFICE_PAT = re.compile(
    r"^(?:aliexpress|woot|temu|whaleco|shein|ebay|etsy|wish|dhgate)\b",
    re.IGNORECASE,
)
AMAZON_DIST_ONLY_PAT = re.compile(r"^amazon(?:\.com)?,?\s+of\s+seattle", re.IGNORECASE)
AMAZON_1P_BRAND_PAT = re.compile(r"\bamazon\s*(?:basics|essentials|commercial|collection)\b", re.IGNORECASE)

# Suspected U.S.-registered shell front LLC naming heuristic (for robustness audit)
SHELL_NAME_PAT = re.compile(
    r"\b(?:e-?commerce|trading|import\s*(?:and|&)\s*export|cross-?border|international\s+trading|"
    r"global\s+trading|supply\s+chain|amazon\s+seller|online\s+store|commerce\s+llc|"
    r"technology\s+llc|tech\s+llc|trade\s+llc|enterprises\s+llc|group\s+llc)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 3. Contract Design, Contact Infrastructure, Safety & Hazmat Patterns
# ---------------------------------------------------------------------------
PHOTO_VERIFY_PAT = re.compile(
    r"(?:"
    r"(?:photo(?:graph)?s?|images?|pictures?)\s+(?:of\s+the\s+(?:destroyed|cut|marked|disabled|disposed|disassembled|removed|empty|recalled|defaced|product|item|cord|plug|unit|label|serial|model|garment|cover|bottle|can|canister|scooter|crib)|(?:clearly\s+)?(?:showing|demonstrating)\s+(?:the\s+)?(?:destroyed|cut|marked|disabled|disposed|disassembled|recalled|defaced|product|item|word|lot|upc|dispos|destruct))|"
    r"(?:send(?:ing)?|upload(?:ing)?|email(?:ing)?|submit(?:ting)?|provid(?:e|ing)|includ(?:e|ing)|attach(?:ing)?|text(?:ing)?)\s+(?:(?:their\s+|your\s+)?(?:amazon\s+)?order\s+number\s+(?:and|or)\s+)?(?:the\s+|a\s+|an\s+|two\s+|three\s+|written\s+and\s+)?(?:clear\s+)?(?:photo(?:graph)?s?|images?|pictures?|photo\s+proof)|"
    r"(?:along\s+with|using\s+(?:either\s+)?)\s*(?:a\s+|an\s+)?(?:photo(?:graph)?|image|picture)\s+of\b|"
    r"submission\s+of\s+(?:a\s+|an\s+)?(?:photo(?:graph)?s?|images?|pictures?)|"
    r"(?:proof|evidence)\s+of\s+(?:destruction|disposal|cutting|disablement)|"
    r"photographic\s+(?:proof|evidence)|"
    r"photo\s+proof|"
    r"take\s+(?:a\s+|an\s+)?(?:photo(?:graph)?|image|picture)\b[^\n.]{0,90}\b(?:send|email|submit|upload|provide|destroy|cut|mark|dispos|remov|label|code|serial|model|receipt|refund|replacement|empty|bottle|cover|trash)\b"
    r")",
    re.IGNORECASE,
)

PHYSICAL_MUTILATE_PAT = re.compile(
    r"(?:"
    r"cut(?:ting)?\s+(?:off\s+|out\s+|through\s+|up\s+)?(?:the\s+|a\s+|an\s+)?[^\n.;]{0,55}?\b(?:cord|cords|wire|wires|plug|strap|straps|string|strings|tie|ties|drawstring|drawstrings|loop|loops|tail|pom[\s\-]poms?|fabric|cloth|padding|skirt|dress|pajamas?|nightgowns?|robes?|clothing|garment|garments|mattress|pad|cover|foam|belt|belts|tether|hose|tube|battery\s+compartment|power\s+supply|webbing|harness|handle|mesh|liner|pillow|lounger|bouncer|net|band|bands|suction\s+cups?|wick|wicks|in\s+half|into\s+(?:two|several|pieces|halves)|vertically\s+and\s+horizontally|with\s+(?:a\s+pair\s+of\s+)?scissors|large\s+[\"\'\u201c]?x[\"\'\u201d]?|an\s+[\"\'\u201c]?x[\"\'\u201d]?)\b|"
    r"\b(?:garment|product|item|unit|mattress|cord|strap|power\s+cord|robe|nightgown|pajamas?|skirt|dress|cover)\s+cut\s+(?:in\s+half|off|into)\b|"
    r"permanent\s+mar?ker|indelible\s+(?:\(permanent\)\s+)?mar?ker|"
    r"writ(?:e|ing)\s+(?:in\s+permanent\s+mar?ker\s+)?[\"\'\u201c]?recall(?:ed)?|"
    r"\binitial\s+and\s+date\b|"
    r"permanently\s+mark|"
    r"mark(?:ing)?\s+(?:the\s+)?(?:product|unit|item|helmet|mattress|fabric|label|charger|power\s+bank|battery|container|package|plastic\s+\w+)\s+with|"
    r"(?:render|make)\s+(?:it|them|the\s+[^\n.;]{1,35})\s+unusable|"
    r"deface|"
    r"destroy(?:ing)?\s+(?:it\b|them\b|(?:the\s+)?[a-z0-9\s\-]{1,42}\b)|"
    r"disable\s+(?:it\b|them\b|the\s+[a-z0-9\s\-]{1,35})|"
    r"disassemble\s+(?:it\b|them\b|the\s+[^\n.;]{1,35})[^\n.;]{0,75}\b(?:dispose|discard|trash|waste|photo)\b|"
    r"disassembled\s+[a-z0-9\s\-]{1,25}\s+in\s+(?:an\s+)?(?:outdoor\s+)?(?:waste|trash|garbage)|"
    r"pour(?:ing)?\s+(?:out\s+)?the\s+contents[^\n.;]{0,45}\b(?:trash|garbage|drain|sink|dispos)|"
    r"puncture|crush|smash|saw\s+(?:in\s+half|through)|dismantle\s+and\s+dispose|"
    r"submerge\s+(?:in\s+)?(?:salt\s+)?water|"
    r"break\s+(?:the\s+)?(?:product|item|unit|handle|prong|blade)"
    r")",
    re.IGNORECASE,
)

# Sentence-level negation-aware physical return detector
NEG_RETURN_SENT_PAT = re.compile(
    r"\b(?:do\s+not|should\s+not|must\s+not|never|cannot|can'?t|not\s+to)\s+(?:attempt\s+to\s+|mail\s+or\s+)?return\b",
    re.IGNORECASE,
)
POS_RETURN_SENT_PAT = re.compile(
    r"(?:"
    r"pre-?paid\s+(?:return\s+)?(?:shipping\s+|postage\s+)?(?:label|mailer|box|packaging|envelope|postage|kit|shipping)|"
    r"free\s+return\s+(?:shipping|postage|label|mailer)|"
    r"\breturn\s+(?:it|them|their\s+[^\n.;]{1,40}|(?:the|any)\s+[^\n.;]{1,65}?)\s+(?:(?:to|at)\s+(?:any|the|a|an|your)?\s*(?:nearest\s+)?(?:[a-z0-9&'\-.,]+\s+){0,7}?(?:stores?|place\s+of\s+purchase|place\s+where\s+(?:it|they)\s+(?:was|were)\s+purchased|retailers?|dealers?|dealerships?|warehouses?|service\s+centers?|shops?|distributors?|manufacturers?|importers?|firms?|compan(?:y|ies)|walmart|target|costco|home\s+depot|lowe'?s|best\s+buy|aldi|ikea|sephora|ulta|petco|petsmart|kohl'?s|macy'?s|nordstrom|ross|tj\s*maxx|t\.j\.\s*maxx|marshalls|homegoods|burlington|dollar|walgreens|cvs|kroger|meijer|bass\s+pro|cabela'?s|rei|dick'?s|harbor\s+freight|tractor\s+supply|sam'?s\s+club|bj'?s|anthropologie|carter'?s|michaels|hobby\s+lobby|staples|office\s+depot|five\s+below|primark|wegmans|publix|safeway|whole\s+foods|trader\s+joe'?s|menards|ace\s+hardware|true\s+value)|by\s+mail|using\s+a\s+pre-?paid|with\s+a\s+pre-?paid|for\s+free|for\s+a\s+(?:full\s+|free\s+)?(?:refund|replacement|repair|credit)|and\s+receive\s+a\s+(?:full\s+|free\s+)?(?:refund|replacement|repair))|"
    r"\breturn\s+(?:it|them|the\s+recalled\s+[^\n.;]{1,40})\s+to\s+receive\s+a\s+free\s+replacement[^\n.;]{0,40}shipping|"
    r"\breturn\s+to\s+(?:any\s+|the\s+|a\s+)?(?:stores?|place\s+of\s+purchase|retailers?|dealers?|warehouses?)|"
    r"\b(?:bring|take)\s+(?:it|them|the\s+[^\n.;]{1,50}?)\s+(?:back\s+)?to\s+(?:any|the|a|an\s+authorized)?\s*(?:[a-z0-9&'\-.,]+\s+){0,5}?(?:stores?|dealers?|dealerships?|service\s+centers?|retailers?|shops?|place\s+of\s+purchase|warehouses?)|"
    r"\bmail\s+(?:it|them|the\s+recalled\s+[^\n.;]{1,40})\s+back\b"
    r")",
    re.IGNORECASE,
)
POS_RETURN_BRAND_PAT = re.compile(
    r"\breturn\s+(?:it|them|the\s+[a-z0-9\s\-]{1,35})\s+to\s+[A-Z][A-Za-z0-9&'\-]+(?:\s+[A-Z][A-Za-z0-9&'\-]+){0,2}\s+for\s+(?:a\s+)?(?:full\s+|free\s+)?(?:refund|replacement|repair|credit)\b"
)


def parse_direct_return(rem_txt: str) -> int:
    """Sentence-level negation-aware physical return detector."""
    if not rem_txt or not rem_txt.strip():
        return 0
    for sent in re.split(r"(?<=[.!?])\s+", rem_txt):
        s = sent.strip()
        if not s:
            continue
        if NEG_RETURN_SENT_PAT.search(s):
            # Allow only if sentence explicitly instructs prepaid return shipping elsewhere
            if re.search(r"pre-?paid\s+(?:return\s+)?(?:shipping|postage|label|mailer|packaging)", s, re.IGNORECASE):
                return 1
            continue
        if POS_RETURN_SENT_PAT.search(s) or POS_RETURN_BRAND_PAT.search(s):
            return 1
    return 0


TOLLFREE_PAT = re.compile(r"\b(?:800|888|877|866|855|844|833)[-\s\.]\d{3}[-\s\.]\d{4}\b")
ANY_PHONE_PAT = re.compile(r"\b(?:\+?1[-\s\.]?)?(?:\(?\d{3}\)?)[-\s\.]\d{3}[-\s\.]\d{4}\b")
EMAIL_PAT = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", re.IGNORECASE)
FREE_WEBMAIL_PAT = re.compile(
    r"@(?:gmail|outlook|hotmail|yahoo|live|msn|qq|163|126|foxmail|icloud|me|aol|proton|protonmail|sina|yeah|sohu|gmx|zoho|yandex)\.(?:com|net|cn|me|org)",
    re.IGNORECASE,
)
DIRECT_CONTACT_PAT = re.compile(
    r"(?:contacting\s+all\s+known\s+purchasers\s+directly|amazon\s+is\s+contacting|"
    r"direct(?:ly)?\s+contacting\s+known\s+purchasers|emailing\s+all\s+known\s+purchasers)",
    re.IGNORECASE,
)

# Mandatory Federal Safety-Rule Violations
MANDATORY_RULE_PAT = re.compile(
    r"(?:"
    r"violat(?:e|es|ed|ing|ion\s+of)\s+(?:the\s+)?(?:federal|mandatory|cpsc|virginia\s+graeme\s+baker|poison\s+prevention)|"
    r"federal\s+(?:safety\s+)?(?:standard|regulation|rule|ban|flammability|lead|phthalate|crib|infant\s+sleep|toy|mattress|bunk\s+bed|clothing\s+storage|tip-?over|button\s+cell|magnet|poison\s+prevention|child-?resistant)|"
    r"mandatory\s+(?:federal\s+)?(?:safety\s+)?(?:standard|regulation|rule|requirement)|"
    r"sturdy\s+act|reese'?s\s+law|virginia\s+graeme\s+baker|pool\s+and\s+spa\s+safety\s+act|"
    r"cpsia|fhsa|pppa|flammable\s+fabrics\s+act|"
    r"child[\s\-]resistant\s+packaging\s+(?:requirement|standard)|"
    r"exceed(?:s|ing)?\s+(?:the\s+)?federal\s+(?:lead|phthalate|cadmium)|"
    r"fail(?:s|ed|ing|ure)?\s+to\s+meet\s+(?:the\s+)?(?:federal|mandatory|child[\s\-]resistant)|"
    r"banned\s+hazardous\s+substance|"
    r"16\s*c\.?f\.?r\.?"
    r")",
    re.IGNORECASE,
)

# Hazardous-Waste Externalization Categories (hazard-gated lithium-ion avoids mechanical brake/bolt FPs!)
HAZWASTE_LITHIUM_EXPLICIT_PAT = re.compile(
    r"\b(?:lithium[\s\-]ion|li[\s\-]ion|lithium\s+batter(?:y|ies)|lithium\s+cell)\b",
    re.IGNORECASE,
)
HAZWASTE_LITHIUM_DEVICE_PAT = re.compile(
    r"\b(?:power\s+bank|portable\s+charger|e[\s\-]?bike|electric\s+bike|electric\s+bicycle|electric\s+scooter|hoverboard|portable\s+power\s+station|rechargeable\s+hand\s+warmer)\b",
    re.IGNORECASE,
)
LITHIUM_THERMAL_HAZ_PAT = re.compile(
    r"\b(?:battery|batteries|lithium|overheat|fire|burn|thermal|ignit|explod|smoke|charging)\b",
    re.IGNORECASE,
)
HAZWASTE_BUTTON_PAT = re.compile(
    r"\b(?:button\s+cell|coin\s+cell|coin\s+battery|coin\s+batteries|button\s+battery|button\s+batteries|reese'?s\s+law)\b",
    re.IGNORECASE,
)
HAZWASTE_CHEMICAL_LEAD_PAT = re.compile(
    r"\b(?:lead\s+paint|levels?\s+of\s+lead|exceed(?:s|ing)?\s+the\s+federal\s+lead|phthalates?|cadmium|mercury|arsenic|bisphenol|toxic\s+chemical|poisonous|hydrofluoric|sulfuric|drain\s+cleaner|pesticide|ethylene\s+glycol|methanol|sodium\s+hydroxide|caustic)\b",
    re.IGNORECASE,
)
SELF_DISPOSE_PAT = re.compile(
    r"(?:\bdispos(?:e|ed|ing|al)\b|\bdiscard(?:ed|ing)?\b|\bthrow\s+(?:it|them|away)\b|\bhousehold\s+trash\b|"
    r"\bhazardous\s+waste\b|\blocal\s+and\s+state\s+(?:regulations|laws|requirements)\b|"
    r"\brecycling\s+(?:facility|center|program)\b|\bdestroy(?:ed|ing)?\b)",
    re.IGNORECASE,
)
EXPLICIT_HHW_PAT = re.compile(
    r"(?:hazardous\s+waste|local\s+and\s+state\s+(?:regulations|laws|requirements)|"
    r"state\s+and\s+local\s+(?:regulations|laws|requirements)|"
    r"municipal\s+(?:hazardous|recycling|waste)|recycling\s+(?:facility|center|location)|"
    r"do\s+not\s+(?:throw|place|dispose)[^\n.]{0,40}(?:trash|garbage|curbside))",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 4. Units, Price, Months-on-Sale, and Double-Count-Free Injury Parsers
# ---------------------------------------------------------------------------
UNIT_PAT = re.compile(r"(?:about\s+|approximately\s+)?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|thousand)?", re.IGNORECASE)

PRICE_PAT = re.compile(
    r"(?:(?:for|from)\s+(?:between\s*(?:about\s+|approximately\s+|[a-z]\s+)?|about\s+|approximately\s+|around\s+)?|between\s*(?:about\s+|approximately\s+)?)\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)"
    r"(?:\s*(?:\([^)]*\)\s*)?(?:for\s+[^\$\n]{1,20}\s+)?(?:and|to|-|\u2013)\s*\$\s*([0-9][0-9,]*(?:\.[0-9]+)?))?",
    re.IGNORECASE,
)

MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MONTH_NAMES_RE = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))
SALE_RANGE_PAT = re.compile(
    rf"(?:from\s+|in\s+)({MONTH_NAMES_RE})\.?\s+(19\d\d|20\d\d)"
    rf"(?:\s+(?:through|to|until|-|\u2013)\s+({MONTH_NAMES_RE})\.?\s+(19\d\d|20\d\d))?",
    re.IGNORECASE,
)

WORD_NUMS = {
    "zero": 0, "no": 0, "none": 0, "one": 1, "a": 1, "an": 1, "two": 2, "both": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

NO_INJURY_SENT_PAT = re.compile(
    r"\b(?:"
    r"none\s+reported|"
    r"no\s+(?:reports?\s+of\s+)?(?:known\s+)?(?:reported\s+)?(?:[a-z\-]+\s+(?:[a-z\-]+\s+)?(?:or|and)\s+)?(?:reported\s+)?(?:choking\s+|burn\s+|serious\s+|minor\s+)?injur(?:y|ies)|"
    r"0\s+injur(?:y|ies)|"
    r"none\s+of\s+the\s+reported\s+incidents.{0,95}(?:required\s+medical|resulted\s+in\s+(?:an\s+)?injur)"
    r")\b",
    re.IGNORECASE,
)
DEATH_PAT = re.compile(
    r"\b(?:death|deaths|died|fatal|fatality|fatalities|killed)\b",
    re.IGNORECASE,
)
NO_DEATH_PAT = re.compile(
    r"\b(?:no\s+(?:reports?\s+of\s+)?(?:deaths?|fatalities|injuries\s+or\s+deaths?)|without\s+(?:any\s+)?death)\b",
    re.IGNORECASE,
)

NUM_TOKEN_RE = (
    r"([0-9][0-9,]*|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)"
)

# Direct injury-count pattern (handles optional "a/an", comma-adjectives, "resulting in ...", "involving ...")
EXPLICIT_INJURY_COUNT_PAT = re.compile(
    rf"\b{NUM_TOKEN_RE}\s+(?:(?:reports?|incidents?)\s+of\s+(?:a\s+|an\s+)?|resulting\s+in\s+(?:a\s+|an\s+)?|involving\s+(?:a\s+|an\s+)?|reported\s+|additional\s+|separate\s+|confirmed\s+)?"
    rf"(?:minor,?\s+|superficial\s+|serious\s+|severe\s+|mild\s+|burn\s+|minor\s+burn\s+|smoke\s+inhalation\s+|entrapment\s+|choking\s+|fall\s+|impact\s+|eye\s+|head\s+|hand\s+|finger\s+|foot\s+|facial\s+|laceration\s+|concussion\s+|skin\s+|non-?fatal\s+|electri(?:c|cal)\s+){{0,3}}"
    rf"(?:injur(?:y|ies)|injured\s+(?:consumers?|children|infants?|riders?|users?|people)|burns?|lacerations?|fractures?|concussions?|amputations?|hospitalizations?|deaths?|fatalities|shocks?|smoke\s+inhalation|skin\s+irritation|cuts?\s+(?:to|on))\b",
    re.IGNORECASE,
)
# Also catch verb/person injury reports ("four flight attendants transported to hospital", "two reports involving children who ingested...", "five reports of consumers who swallowed... sought medical")
VERB_INJURY_PAT = re.compile(
    rf"\b{NUM_TOKEN_RE}\s+(?:(?:reports?|incidents?)\s+(?:of\s+(?:a\s+|an\s+)?|involving\s+(?:a\s+|an\s+)?))?"
    rf"(?:children|infants?|babies|toddlers?|consumers?|riders?|users?|people|persons?|adults?|individuals?|flight\s+attendants?|operators?)\s+"
    rf"(?:who\s+|being\s+)?(?:were\s+injured|suffered\s+(?:burns?|injur|fractur|lacerat|concuss|bruis)|"
    rf"received\s+(?:burns?|injur|medical|second-degree|first-degree|third-degree)|"
    rf"reported\s+(?:burns?|injur|bruis|lacerat|receiving\s+(?:burns?|second-degree|minor))|"
    rf"experienc(?:ed|ing)\s+(?:a\s+)?(?:minor\s+)?(?:electri(?:c|cal)\s+shock|symptoms|burns?)|"
    rf"swallowed\s+[^\n.]{{1,35}}\s+and\s+(?:sought\s+medical|required)|"
    rf"were\s+able\s+to\s+remove\s+and\s+ingest|"
    rf"transported\s+to\s+(?:the\s+)?hospital|"
    rf"required\s+(?:surgery|medical|hospital|stitches)|fractur(?:ed|ing)|died|were\s+hospitalized)\b",
    re.IGNORECASE,
)
INJURY_KEYWORD_PAT = re.compile(
    r"\b(?:injur(?:y|ies|ed)|burn(?:s|ed)?|lacerat(?:ion|ions|ed)|fractur(?:e|es|ed)|"
    r"concuss(?:ion|ions)|amputat(?:ion|ions|ed)|bruis(?:e|es|ed|ing)|scrape(?:s|d)?|"
    r"stitch(?:es)?|hospitaliz(?:ed|ation)|medical\s+(?:attention|treatment|professional)|surgery|chok(?:ed|ing)|"
    r"asphyxiat(?:ed|ion)|suffocat(?:ed|ion)|strangul(?:ated|ation)|poison(?:ed|ing)|"
    r"swallow(?:ed|ing)|ingest(?:ed|ion)|electri(?:c|cal)\s+shock|electrocut(?:ed|ion)|"
    r"broken\s+(?:bone|bones|rib|ribs|arm|leg|wrist|finger|nose|tooth|teeth)|"
    r"skin\s+irritation|blister|respiratory\s+infections?|sprain(?:s|ed)?|cut(?:s)?\s+(?:to|on)|"
    r"death|deaths|died|fatal(?:ity|ities)?)\b",
    re.IGNORECASE,
)
PROP_DAMAGE_SUBCLAUSE_PAT = re.compile(
    r"\b(?:[0-9,]+|one|two|three|four|five|six|seven|eight|nine|ten|several|multiple|minor|substantial)\s+"
    r"(?:reports?\s+of\s+)?(?:minor\s+|substantial\s+|residential\s+)?property\s+damage\b",
    re.IGNORECASE,
)


def _word_or_int(tok: str) -> int:
    t = tok.strip().lower().replace(",", "")
    if t.isdigit():
        return int(t)
    return WORD_NUMS.get(t, 0)


def parse_units(products: list[dict[str, Any]] | None) -> float:
    total = 0.0
    found = False
    for p in products or []:
        s = str(p.get("NumberOfUnits") or "")
        s_main = re.split(r"\(in\s+addition|\(plus|and\s+about\s+[0-9,\.]+\s+(?:in\s+canada|in\s+mexico)", s, flags=re.IGNORECASE)[0]
        m = UNIT_PAT.search(s_main)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                mult = (m.group(2) or "").lower()
                if mult == "million":
                    val *= 1e6
                elif mult == "thousand":
                    val *= 1e3
                if val > 0:
                    total += val
                    found = True
            except ValueError:
                continue
    return total if found else float("nan")


def parse_price(ret_txt: str, desc_txt: str) -> float:
    txt = f"{ret_txt} {desc_txt}"
    m = PRICE_PAT.search(txt)
    if m:
        try:
            v1 = float(m.group(1).replace(",", ""))
            if m.group(2):
                v2 = float(m.group(2).replace(",", ""))
                val = v2 if v1 == 0.0 else 0.5 * (v1 + v2)
            else:
                val = v1
            if 0.5 <= val <= 250_000:
                return val
        except ValueError:
            return float("nan")
    return float("nan")


def parse_months_on_sale(ret_txt: str, desc_txt: str, recall_date: pd.Timestamp) -> tuple[float, float]:
    """Return (months_from_sale_start_to_recall, sale_window_months)."""
    txt = f"{ret_txt} {desc_txt}"
    m = SALE_RANGE_PAT.search(txt)
    if not m or pd.isna(recall_date):
        return float("nan"), float("nan")
    try:
        m1 = MONTH_MAP[m.group(1).lower()]
        y1 = int(m.group(2))
        start_dt = pd.Timestamp(year=y1, month=m1, day=1)
        months_to_recall = (recall_date.year - start_dt.year) * 12 + (recall_date.month - start_dt.month)
        if months_to_recall < 0 or months_to_recall > 480:
            months_to_recall = float("nan")
        if m.group(3) and m.group(4):
            m2 = MONTH_MAP[m.group(3).lower()]
            y2 = int(m.group(4))
            sale_window = (y2 - y1) * 12 + (m2 - m1) + 1
            if sale_window < 1 or sale_window > 480:
                sale_window = float("nan")
        else:
            sale_window = 1.0
        return float(months_to_recall), float(sale_window)
    except (ValueError, KeyError):
        return float("nan"), float("nan")


def parse_injuries_clean(inj_txt: str) -> dict[str, int]:
    """Double-count-free CPSC injury parser."""
    raw = (inj_txt or "").strip()
    if not raw:
        return {"has_injury": 0, "clean_injuries": 0, "has_death": 0}

    if re.match(r"^none\s+reported\.?\s*(?:cpsc\s+(?:estimates|is\s+aware)|$)", raw, re.IGNORECASE):
        return {"has_injury": 0, "clean_injuries": 0, "has_death": 0}

    # Protect abbreviations (U.S., Inc., Ltd., Co., No., Dr., St.) from premature sentence splitting
    safe_raw = re.sub(r"\b(U\.S|Inc|Ltd|Co|No|Dr|St)\.", r"\1<DOT>", raw)
    sentences = [s.replace("<DOT>", ".").strip() for s in re.split(r"(?<=[.!?])\s+", safe_raw) if s.strip()]

    has_death = 0
    total_injuries = 0
    any_injury_flag = 0

    for sent in sentences:
        s_clean = re.sub(r"\([^)]*\)", " ", sent)
        if re.match(r"^(?:in\s+addition,?\s*)?cpsc\s+(?:estimates|is\s+aware\s+of\s+(?:other\s+reports|.*since\s+20\d\d))", s_clean, re.IGNORECASE):
            continue

        if DEATH_PAT.search(s_clean) and not NO_DEATH_PAT.search(s_clean):
            has_death = 1

        if NO_INJURY_SENT_PAT.search(s_clean) and not re.search(
            r"\b(?:but|however|except|one\s+report\s+of\s+(?:a\s+)?(?:minor\s+|burn\s+)?injur)",
            s_clean,
            re.IGNORECASE,
        ):
            continue

        # Strip age and burn-degree adjectives BEFORE matching counts
        s_prep = re.sub(r"\b\d+[\s\-]year[\s\-]old\b", " ", s_clean, flags=re.IGNORECASE)
        s_prep = re.sub(r"\b(?:first|second|third)[\s\-]?(?:or\s+(?:second|third)[\s\-]?)?degree\b", " ", s_prep, flags=re.IGNORECASE)
        s_prep = PROP_DAMAGE_SUBCLAUSE_PAT.sub(" ", s_prep)

        # Truncate subordinate breakdown clauses AFTER the first explicit injury count
        m_first_inj = EXPLICIT_INJURY_COUNT_PAT.search(s_prep)
        if m_first_inj:
            tail = s_prep[m_first_inj.end() :]
            m_brk = re.search(
                r"(?:,?\s*\bincluding\b|,?\s*\bconsisting\s+of\b|,?\s*\bof\s+which\b|,?\s*\bwhich\s+includes?\b|,?\s*\bamong\s+(?:them|these)\b|;\s*(?:these|which)\s+include)",
                tail,
                re.IGNORECASE,
            )
            s_eval = s_prep[: m_first_inj.end() + m_brk.start()] if m_brk else s_prep
        else:
            s_eval = s_prep

        # Avoid double-counting subset follow-up sentences ("Three consumers reported second-degree burns." or "including the two fatalities")
        is_subset_followup = (
            total_injuries > 0
            and bool(
                re.search(
                    r"\b(?:first|second|third)[\s\-]degree|these\s+include|of\s+these|of\s+those|both\s+incidents\s+resulted|including\s+the\s+(?:two|three|four|\d+)\s+(?:fatalit(?:y|ies)|deaths?|injur(?:y|ies))\b",
                    s_clean,
                    re.IGNORECASE,
                )
            )
            and not bool(re.search(r"\b(?:additional|separate|also\s+received|another)\b", s_clean, re.IGNORECASE))
        )
        if is_subset_followup:
            continue

        is_cumulative_restatement = (
            total_injuries > 0
            and bool(re.match(r"^(?:approximately|about|a\s+total\s+of|in\s+total|overall)\s+[0-9,]+", s_eval, re.IGNORECASE))
            and not bool(re.search(r"\badditional\b", s_eval, re.IGNORECASE))
        )

        sent_cnt = 0
        explicit_matches = list(EXPLICIT_INJURY_COUNT_PAT.finditer(s_eval))
        if explicit_matches:
            for m in explicit_matches:
                prefix = s_eval[max(0, m.start() - 12) : m.start()].lower()
                if re.search(r"\bno\s+$", prefix):
                    continue
                val = _word_or_int(m.group(1))
                if val > 0:
                    sent_cnt += val
        else:
            verb_matches = list(VERB_INJURY_PAT.finditer(s_eval))
            for m in verb_matches:
                val = _word_or_int(m.group(1))
                if val > 0:
                    sent_cnt += val
            if sent_cnt == 0:
                # Handle paired singular victims: "A 4-year-old girl and a 6-year-old girl ... died"
                pair_deaths = re.search(
                    r"\b(?:a|an)\s+(?:[a-z]+\s+){0,2}(?:woman|man|child|infant|baby|toddler|consumer|rider|boy|girl|person)\s+and\s+(?:a|an)\s+(?:[a-z]+\s+){0,2}(?:woman|man|child|infant|baby|toddler|consumer|rider|boy|girl|person)[^\n.]{0,110}\b(?:died|were\s+injured|suffered|sustained)\b",
                    s_eval,
                    re.IGNORECASE,
                )
                if pair_deaths:
                    sent_cnt = 2
                else:
                    sing_deaths = re.findall(
                        r"\b(?:a|an)\s+(?:woman|man|child|infant|baby|toddler|consumer|rider|boy|girl|person)\s+(?:died|was\s+injured|suffered|sustained)\b",
                        s_eval,
                        re.IGNORECASE,
                    )
                    if sing_deaths:
                        sent_cnt = len(sing_deaths)

        if sent_cnt > 0:
            if is_cumulative_restatement:
                total_injuries = max(total_injuries, sent_cnt)
            else:
                total_injuries += sent_cnt
            any_injury_flag = 1
        elif (
            INJURY_KEYWORD_PAT.search(s_eval)
            and not NO_INJURY_SENT_PAT.search(s_clean)
            and not re.search(r"\b(?:burning\s+or\s+melting|burning\s+odor|no\s+injur|did\s+not\s+require\s+medical|none\s+of\s+the\s+reported)\b", s_clean, re.IGNORECASE)
            and re.search(
                r"\b(?:injur(?:y|ies|ed)|lacerat|fractur|concuss|amputat|bruis|scrape|stitch|hospitaliz|medical\s+(?:attention|treatment|professional)|surgery|death|died|fatal|burn\s+(?:to|injur)|minor\s+burn|cut\s+(?:on|to)|electri(?:c|cal)\s+shock|skin\s+irritation|blister|swallow(?:ed|ing)\s+metal|ingest\s+magnets)\b",
                s_eval,
                re.IGNORECASE,
            )
        ):
            any_injury_flag = 1
            if total_injuries == 0:
                total_injuries = 1

    if has_death == 1 and any_injury_flag == 0:
        any_injury_flag = 1
        total_injuries = max(total_injuries, 1)

    return {
        "has_injury": int(any_injury_flag),
        "clean_injuries": int(total_injuries),
        "has_death": int(has_death),
    }


# ---------------------------------------------------------------------------
# 5. Entity Origin, Channel, and 6-Archetype Classifier
# ---------------------------------------------------------------------------
def _is_pure_entity_entry(entry: str) -> bool:
    """Detect late-2026 Retailers entries that are legal seller names rather than retail sales channels."""
    low = entry.strip().lower()
    if re.match(r"^(?:sold\s+(?:online\s+)?at:?|online\s+at\s|exclusively\s+online|stores?\s+nationwide)", low):
        return False
    has_sales_date_or_price = bool(re.search(r"(?:from\s+[a-z]+\s+\d{4}|for\s+(?:about|between)\s*\$|nationwide)", low))
    has_entity_loc = bool(CN_ENTITY_PAT.search(entry) or US_ENTITY_PAT.search(entry) or NONCN_FOREIGN_ENTITY_PAT.search(entry))
    return has_entity_loc and not has_sales_date_or_price


def parse_entity_fields(rec: dict[str, Any]) -> dict[str, Any]:
    """Parse recalling entity origin across ALL 4 structured fields:
    Importers + Manufacturers + Distributors + Retailers.
    """
    importers = [str(x.get("Name") or "").strip() for x in (rec.get("Importers") or []) if str(x.get("Name") or "").strip()]
    mfrs = [str(x.get("Name") or "").strip() for x in (rec.get("Manufacturers") or []) if str(x.get("Name") or "").strip()]
    dists = [str(x.get("Name") or "").strip() for x in (rec.get("Distributors") or []) if str(x.get("Name") or "").strip()]
    retailers_raw = [str(x.get("Name") or "").strip() for x in (rec.get("Retailers") or []) if str(x.get("Name") or "").strip()]

    retailer_entity_entries = []
    for entry in retailers_raw:
        if not re.match(r"^(?:sold\s+(?:online\s+)?at:|online\s+at\s|stores?\s+nationwide)", entry, re.IGNORECASE) or re.search(r",\s*of\s+(?:china|hong\s+kong|[A-Z][a-z]+)", entry, re.IGNORECASE):
            retailer_entity_entries.append(entry)

    primary_ent_txt = " | ".join(importers + mfrs + dists)
    all4_list = importers + mfrs + dists + retailer_entity_entries
    all4_ent_txt = " | ".join(all4_list)

    rescued_from_retailers = int((not primary_ent_txt.strip()) and bool(retailer_entity_entries))

    has_cn_entity = int(bool(CN_ENTITY_PAT.search(all4_ent_txt)))
    has_noncn_foreign_entity = int(bool(NONCN_FOREIGN_ENTITY_PAT.search(all4_ent_txt)))

    # Exclude pure 3P platform corporate offices (AliExpress San Mateo CA, Woot Carrollton TX,
    # Amazon Seattle distributor-only co-listing) from masking a foreign cross-border seller!
    title_txt = str(rec.get("Title") or "")
    is_amz_1p = bool(AMAZON_1P_BRAND_PAT.search(title_txt))
    non_plat_entries = []
    for entry in all4_list:
        if (has_cn_entity == 1 or has_noncn_foreign_entity == 1) and (
            PLATFORM_US_OFFICE_PAT.search(entry)
            or (AMAZON_DIST_ONLY_PAT.search(entry) and not is_amz_1p and entry in dists)
        ):
            continue
        non_plat_entries.append(entry)

    us_check_txt = " | ".join(non_plat_entries)
    has_us_entity = int(
        bool(US_ENTITY_PAT.search(us_check_txt))
        or bool(US_ENTITY_STATE_ONLY_PAT.search(us_check_txt))
    )

    if has_us_entity == 0 and has_cn_entity == 0 and has_noncn_foreign_entity == 0:
        desc_title = f"{title_txt} {rec.get('Description') or ''}"
        if CN_ENTITY_PAT.search(desc_title):
            has_cn_entity = 1
        elif US_ENTITY_PAT.search(desc_title):
            has_us_entity = 1
        elif NONCN_FOREIGN_ENTITY_PAT.search(desc_title):
            has_noncn_foreign_entity = 1

    is_fd_china = int(has_cn_entity == 1 and has_us_entity == 0)
    is_fd_nonchina = int(has_noncn_foreign_entity == 1 and has_us_entity == 0 and has_cn_entity == 0)
    is_foreign_direct_any = int(is_fd_china == 1 or is_fd_nonchina == 1)

    # Firm cluster identifier across all 4 fields (skipping pure platform office if foreign seller exists)
    firm_cluster = "unknown"
    for candidate_list in (importers, mfrs, dists, retailer_entity_entries):
        filtered = [
            c for c in candidate_list
            if not ((has_cn_entity == 1 or has_noncn_foreign_entity == 1) and PLATFORM_US_OFFICE_PAT.search(c))
        ] or candidate_list
        if filtered:
            nm = re.split(r",|\bof\b|\bdoing\s+business\b|\bdba\b", filtered[0], flags=re.IGNORECASE)[0].strip().lower()
            toks = re.sub(r"[^a-z0-9\s]", "", nm).split()[:2]
            if toks:
                firm_cluster = "_".join(toks)
                break
    if firm_cluster == "unknown":
        t = re.sub(r"[^a-z0-9\s]", "", title_txt.lower()).split()[:2]
        firm_cluster = "_".join(t) if t else "unknown"

    return {
        "entity_text_all4": all4_ent_txt[:400],
        "rescued_from_retailers": rescued_from_retailers,
        "has_us_entity": has_us_entity,
        "has_cn_entity": has_cn_entity,
        "has_noncn_foreign_entity": has_noncn_foreign_entity,
        "is_fd_china": is_fd_china,
        "is_fd_nonchina": is_fd_nonchina,
        "is_foreign_direct_any": is_foreign_direct_any,
        "firm_cluster": firm_cluster,
    }


def parse_channel_and_archetype(rec: dict[str, Any], ent: dict[str, Any], free_webmail: int, no_phone: int) -> dict[str, Any]:
    """Classify retail channel (zero .com Brick-and-Mortar false positives; clean
    physical-store detection; pure first-party DTC Online-Only) and assign clean
    6-archetype supply-chain taxonomy + shell-front sensitivity flag.
    """
    ret_entries = [str(x.get("Name") or "").strip() for x in (rec.get("Retailers") or []) if str(x.get("Name") or "").strip()]
    sales_entries = [e for e in ret_entries if not _is_pure_entity_entry(e)]
    ret_txt = " ".join(sales_entries if sales_entries else ret_entries)
    desc_txt = str(rec.get("Description") or "")
    ret_all = ret_txt if ret_txt.strip() else desc_txt

    has_mkt = int(bool(MARKETPLACE_PAT.search(ret_all)))
    plat_flags = {k: int(bool(pat.search(ret_all))) for k, pat in PLAT_PATTERNS.items()}

    # Strip all web domains AND non-brick online/person phrases BEFORE physical-store detection!
    ret_stripped = DOMAIN_STRIP_PAT.sub(" [ONLINE_DOMAIN] ", ret_all)
    ret_stripped = NON_BRICK_PHRASE_STRIP_PAT.sub(" [ONLINE_PHRASE] ", ret_stripped)
    has_brick = int(bool(BRICK_PAT.search(ret_stripped)) or bool(BRANDED_PHYSICAL_STORE_PAT.search(ret_stripped)))

    has_domain_mention = bool(DOMAIN_STRIP_PAT.search(ret_all))
    has_online_only = int((bool(ONLINE_ONLY_PAT.search(ret_all)) or has_domain_mention) and has_brick == 0)

    if has_mkt == 1 and has_brick == 0:
        channel = "Marketplace_Only"
    elif has_online_only == 1 and has_brick == 0:
        channel = "DTC_Online_Only"
    elif has_mkt == 1 and has_brick == 1:
        channel = "Omnichannel"
    elif has_brick == 1:
        channel = "Brick_and_Mortar"
    else:
        channel = "Other_Unclear"

    # Clean 6-Archetype Taxonomy (3_Mkt_True_US strictly requires verified U.S. entity!)
    if channel == "Marketplace_Only":
        if ent["is_fd_china"] == 1:
            archetype_6 = "1_Mkt_FD_China"
        elif ent["is_fd_nonchina"] == 1:
            archetype_6 = "2_Mkt_FD_NonChina"
        elif ent["has_us_entity"] == 1:
            archetype_6 = "3_Mkt_True_US"
        else:
            archetype_6 = "7_Other_Unclear"
    elif channel == "DTC_Online_Only":
        archetype_6 = "4_DTC_Online_Only"
    elif channel == "Omnichannel":
        archetype_6 = "5_Omnichannel"
    elif channel == "Brick_and_Mortar":
        archetype_6 = "6_Brick_and_Mortar"
    else:
        archetype_6 = "7_Other_Unclear"

    # Suspected U.S.-Registered Shell Front sensitivity flag (strictly inside 3_Mkt_True_US)
    cc_rem_txt = f"{rec.get('ConsumerContact') or ''} {' '.join(str(x.get('Name') or '') for x in (rec.get('Remedies') or []))}"
    has_cn_webmail = int(bool(re.search(r"@(?:qq|163|126|foxmail|sina|yeah|sohu)\.(?:com|cn|net)", cc_rem_txt, re.IGNORECASE)))
    has_shell_name = int(bool(SHELL_NAME_PAT.search(ent["entity_text_all4"])))
    shell_suspected = int(
        archetype_6 == "3_Mkt_True_US"
        and (
            has_cn_webmail == 1
            or free_webmail == 1
            or (no_phone == 1 and has_shell_name == 1)
        )
    )

    out = {
        "channel": channel,
        "archetype_6": archetype_6,
        "has_mkt": has_mkt,
        "has_brick": has_brick,
        "has_online_only": has_online_only,
        "shell_suspected": shell_suspected,
        "amazon_only_mkt": int(channel == "Marketplace_Only" and plat_flags["plat_amazon"] == 1),
        "nonamazon_mkt_only": int(channel == "Marketplace_Only" and plat_flags["plat_amazon"] == 0),
    }
    out.update(plat_flags)
    return out


# ---------------------------------------------------------------------------
# 6. Product Category (15 Granular), Fine Product Noun (~26), & Hazard (9)
# ---------------------------------------------------------------------------
def classify_product_15(title_txt: str, prod_txt: str) -> str:
    t = f"{title_txt} {prod_txt}".lower()
    rules = [
        ("Infant_Sleep_Crib", ["crib", "bassinet", "lounger", "inclined sleeper", "play yard", "sleep sack", "infant mattress", "crib mattress"]),
        ("Stroller_HighChair", ["stroller", "high chair", "bouncer", "walker", "carrier", "car seat", "booster seat"]),
        ("Child_Sleepwear_Apparel", ["sleepwear", "pajama", "nightgown", "robe", "children's", "infant", "toddler", "youth", "kids'", "baby"]),
        ("Toys_Magnets", ["toy", "plush", "rattle", "doll", "magnet", "water bead", "playset", "figurine", "slime"]),
        ("Lithium_Battery_PowerBank", ["power bank", "lithium", "battery", "charger", "e-bike", "ebike", "scooter", "hoverboard", "portable power"]),
        ("Furniture_Dresser_Chair", ["dresser", "chest of drawers", "wardrobe", "cabinet", "bookcase", "chair", "stool", "table", "bed frame", "bunk bed", "sofa", "couch", "mattress"]),
        ("Heater_HVAC_Fan", ["heater", "air conditioner", "dehumidifier", "humidifier", "fan", "furnace", "thermostat", "fireplace"]),
        ("Kitchen_SmallAppliance", ["blender", "air fryer", "coffee", "kettle", "toaster", "pressure cooker", "slow cooker", "cooktop", "range", "oven", "microwave", "refrigerator", "dishwasher", "mug", "cookware", "faucet"]),
        ("Bike_Helmet_Sports", ["bicycle", "bike", "helmet", "trampoline", "treadmill", "exercise", "kayak", "golf", "pool", "life jacket"]),
        ("PowerTools_Outdoor", ["saw", "drill", "mower", "trimmer", "chainsaw", "ladder", "generator", "pressure washer", "grill", "fire pit", "tractor", "atv", "utility vehicle", "snowblower"]),
        ("Electrical_Lighting", ["extension cord", "power strip", "lamp", "light", "candle", "outlet", "surge protector", "plug", "breaker"]),
        ("Safety_Locks_Alarms", ["smoke alarm", "carbon monoxide", "fire extinguisher", "safe", "gun safe", "lock", "gate", "window blind", "cord"]),
        ("Chemicals_Medicine_Packaging", ["supplement", "vitamin", "oil", "cleaner", "detergent", "poison", "child-resistant", "bottle", "fuel", "drain"]),
        ("Adult_Apparel_Footwear", ["jacket", "coat", "shoe", "boot", "sandal", "shirt", "sweatshirt", "hoodie", "apparel"]),
    ]
    for cat, kws in rules:
        if any(k in t for k in kws):
            return cat
    return "Other_Product"


def classify_fine_product_noun(title_txt: str, prod_txt: str) -> str:
    """Finer 26-level product noun classification for Fine-Product-Noun x Year FE."""
    t = f"{title_txt} {prod_txt}".lower()
    fine_rules = [
        ("Power_Bank", ["power bank", "portable charger", "portable power"]),
        ("Ebike_Scooter", ["e-bike", "ebike", "electric bike", "electric bicycle", "scooter", "hoverboard"]),
        ("Battery_Charger", ["lithium", "battery", "charger"]),
        ("Dresser_Chest", ["dresser", "chest of drawers", "clothing storage", "wardrobe", "armoire"]),
        ("Mattress_Bedding", ["crib mattress", "mattress", "bed frame", "bunk bed"]),
        ("Chair_Stool_Table", ["chair", "stool", "table", "desk", "sofa", "couch", "cabinet", "bookcase", "shelf"]),
        ("Infant_Lounger_Crib", ["lounger", "inclined sleeper", "bassinet", "crib", "play yard", "sleep sack"]),
        ("Stroller_Bouncer", ["stroller", "high chair", "bouncer", "walker", "carrier", "car seat", "booster seat"]),
        ("Child_Sleepwear", ["sleepwear", "pajama", "nightgown", "robe"]),
        ("Child_Apparel_Shoes", ["children's", "infant", "toddler", "youth", "kids'", "baby"]),
        ("Magnet_WaterBead", ["magnet", "water bead", "magnetic"]),
        ("Toy_Plush_Doll", ["toy", "plush", "rattle", "doll", "playset", "figurine", "slime"]),
        ("Bike_Helmet", ["helmet"]),
        ("Bicycle_Fitness", ["bicycle", "bike", "trampoline", "treadmill", "exercise", "kayak", "golf", "pool", "life jacket"]),
        ("Space_Heater_Fan", ["heater", "fan", "dehumidifier", "humidifier", "air conditioner", "fireplace"]),
        ("Hair_Dryer_PersonalCare", ["hair dryer", "curling", "straightener", "shaver", "clipper", "massager"]),
        ("AirFryer_Oven_Range", ["air fryer", "oven", "range", "cooktop", "microwave", "toaster", "pressure cooker", "slow cooker"]),
        ("Coffee_Blender_Kitchen", ["coffee", "blender", "kettle", "refrigerator", "dishwasher", "mug", "cookware", "faucet"]),
        ("ATV_Mower_OutdoorVeh", ["atv", "utility vehicle", "rov", "tractor", "mower", "snowblower", "golf car"]),
        ("Power_Tool_Ladder", ["saw", "drill", "trimmer", "chainsaw", "ladder", "generator", "pressure washer", "grill", "fire pit"]),
        ("Lamp_Light_Candle", ["lamp", "light", "candle", "flashlight", "lantern"]),
        ("Cord_Outlet_Breaker", ["extension cord", "power strip", "outlet", "surge protector", "plug", "breaker"]),
        ("Alarm_Safe_Gate", ["smoke alarm", "carbon monoxide", "fire extinguisher", "safe", "gun safe", "lock", "gate"]),
        ("Window_Blind_Shade", ["window blind", "window covering", "shade"]),
        ("Supplement_Bottle_Chem", ["supplement", "vitamin", "oil", "cleaner", "detergent", "poison", "child-resistant", "bottle", "fuel", "drain"]),
        ("Adult_Apparel_Footwear", ["jacket", "coat", "shoe", "boot", "sandal", "shirt", "sweatshirt", "hoodie", "apparel"]),
    ]
    for noun, kws in fine_rules:
        if any(k in t for k in kws):
            return noun
    return "Other_Noun"


def classify_hazard_9(haz_txt: str) -> str:
    t = haz_txt.lower()
    if any(k in t for k in ["fire", "burn", "thermal", "overheat", "lithium", "explod", "smoke"]):
        return "Fire_Burn"
    if any(k in t for k in ["chok", "aspiration", "small part"]):
        return "Choking"
    if any(k in t for k in ["button", "coin cell", "magnet", "ingestion"]):
        return "Ingestion_Battery_Magnet"
    if any(k in t for k in ["lead", "phthalate", "poison", "toxic", "chemical", "cadmium", "bisphenol", "poisoning"]):
        return "Toxicity_Lead_Poison"
    if any(k in t for k in ["suffocat", "entrap", "strangul", "asphyx", "drown"]):
        return "Suffocation_Entrapment"
    if any(k in t for k in ["tip-over", "tip over", "fall", "collaps", "crash", "impact"]):
        return "Fall_TipOver_Crash"
    if any(k in t for k in ["shock", "electrocut"]):
        return "Electric_Shock"
    if any(k in t for k in ["lacerat", "cut", "amputat", "pinch", "sharp"]):
        return "Laceration_Pinch"
    return "Other_Hazard"


# ---------------------------------------------------------------------------
# 7. Master Single-Record Parser
# ---------------------------------------------------------------------------
def parse_recall_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    rdate = pd.to_datetime(rec.get("RecallDate"), errors="coerce")
    if pd.isna(rdate):
        return None

    rid = int(rec.get("RecallID") or 0)
    rnum = str(rec.get("RecallNumber") or "")
    title_txt = str(rec.get("Title") or "")
    desc_txt = str(rec.get("Description") or "")
    ret_txt = " ".join(str(x.get("Name") or "") for x in (rec.get("Retailers") or []))
    rem_txt = " ".join(str(x.get("Name") or "") for x in (rec.get("Remedies") or []))
    rem_opts = [str(x.get("Option") or "").strip().lower() for x in (rec.get("RemedyOptions") or [])]
    cc_txt = str(rec.get("ConsumerContact") or "")
    haz_txt = " ".join(str(x.get("Name") or "") for x in (rec.get("Hazards") or []))
    inj_txt = " ".join(str(x.get("Name") or "") for x in (rec.get("Injuries") or []))
    prod_txt = " ".join(
        f"{x.get('Name') or ''} {x.get('Type') or ''}" for x in (rec.get("Products") or [])
    )
    countries = [str(x.get("Country") or "").strip().lower() for x in (rec.get("ManufacturerCountries") or [])]

    # Contact infrastructure
    contact_all = f"{cc_txt} {rem_txt}"
    no_tollfree = int(not bool(TOLLFREE_PAT.search(contact_all)))
    no_phone = int(not bool(ANY_PHONE_PAT.search(contact_all)))
    has_email = int(bool(EMAIL_PAT.search(contact_all)))
    email_only = int(has_email == 1 and no_phone == 1)
    free_webmail = int(bool(FREE_WEBMAIL_PAT.search(contact_all)))

    # Entity & Channel / 6-Archetype
    ent = parse_entity_fields(rec)
    ch = parse_channel_and_archetype(rec, ent, free_webmail=free_webmail, no_phone=no_phone)

    # Remedy options & Contract design
    opt_set = set(rem_opts)
    has_refund = int(("refund" in opt_set) or ("refund" in rem_txt.lower() and not opt_set))
    has_repair = int(("repair" in opt_set) or ("repair" in rem_txt.lower() and not opt_set))
    has_replace = int(("replace" in opt_set) or ("replace" in rem_txt.lower() and not opt_set))
    refund_only = int(has_refund == 1 and has_repair == 0 and has_replace == 0)
    repair_or_replace = int(has_repair == 1 or has_replace == 1)

    photo_verify = int(bool(PHOTO_VERIFY_PAT.search(rem_txt)))
    physical_mutilate = int(bool(PHYSICAL_MUTILATE_PAT.search(rem_txt)))
    direct_return = parse_direct_return(rem_txt)
    direct_contact = int(bool(DIRECT_CONTACT_PAT.search(f"{rem_txt} {cc_txt}")))

    # Mandatory federal safety rule violation
    mandatory_rule = int(bool(MANDATORY_RULE_PAT.search(f"{title_txt} {haz_txt} {desc_txt}")))

    # Hazardous-waste externalization indicators (hazard-gated lithium prevents mechanical brake/bolt FPs!)
    haz_prod_all = f"{title_txt} {prod_txt} {haz_txt}"
    haz_rem_all = f"{haz_txt} {rem_txt}"
    haz_lithium = int(
        bool(HAZWASTE_LITHIUM_EXPLICIT_PAT.search(f"{haz_prod_all} {rem_txt}"))
        or (bool(HAZWASTE_LITHIUM_DEVICE_PAT.search(haz_prod_all)) and bool(LITHIUM_THERMAL_HAZ_PAT.search(haz_rem_all)))
    )
    haz_button = int(bool(HAZWASTE_BUTTON_PAT.search(haz_prod_all)))
    haz_chemical_lead = int(bool(HAZWASTE_CHEMICAL_LEAD_PAT.search(haz_prod_all)))
    haz_waste_product = int(haz_lithium == 1 or haz_button == 1 or haz_chemical_lead == 1)
    self_dispose_instructed = int(bool(SELF_DISPOSE_PAT.search(rem_txt)) and direct_return == 0)
    explicit_hhw_warning = int(bool(EXPLICIT_HHW_PAT.search(rem_txt)))
    haz_household_disposal = int(haz_waste_product == 1 and self_dispose_instructed == 1)
    haz_photo_disposal = int(haz_waste_product == 1 and photo_verify == 1 and direct_return == 0)

    # Structured traceability & international coordination
    has_upc = int(len(rec.get("ProductUPCs") or []) > 0)
    inconj = rec.get("Inconjunctions") or []
    has_inconjunction = int(len(inconj) > 0)
    inconj_countries = ",".join(sorted({str(x.get("Country") or "").strip() for x in inconj if x.get("Country")}))

    # Numeric attributes & clean injuries
    units = parse_units(rec.get("Products"))
    price = parse_price(ret_txt, desc_txt)
    months_on_sale, sale_window_months = parse_months_on_sale(ret_txt, desc_txt, rdate)
    inj_parsed = parse_injuries_clean(inj_txt)

    is_china_mfr = int(any(("china" in c or "hong kong" in c) for c in countries))

    row = {
        "recall_id": rid,
        "recall_number": rnum,
        "recall_date": rdate.strftime("%Y-%m-%d"),
        "year": int(rdate.year),
        "quarter": int(rdate.quarter),
        "yq": f"{rdate.year}Q{rdate.quarter}",
        "ym": rdate.strftime("%Y-%m"),
        "is_china_mfr": is_china_mfr,
        "units": units,
        "price": price,
        "months_on_sale": months_on_sale,
        "sale_window_months": sale_window_months,
        "prod_cat": classify_product_15(title_txt, prod_txt),
        "fine_noun": classify_fine_product_noun(title_txt, prod_txt),
        "hazard_cat": classify_hazard_9(haz_txt),
        "has_refund": has_refund,
        "has_repair": has_repair,
        "has_replace": has_replace,
        "refund_only": refund_only,
        "repair_or_replace": repair_or_replace,
        "photo_verify": photo_verify,
        "physical_mutilate": physical_mutilate,
        "direct_return": direct_return,
        "direct_contact": direct_contact,
        "no_tollfree": no_tollfree,
        "no_phone": no_phone,
        "has_email": has_email,
        "email_only": email_only,
        "free_webmail": free_webmail,
        "mandatory_rule": mandatory_rule,
        "haz_lithium": haz_lithium,
        "haz_button": haz_button,
        "haz_chemical_lead": haz_chemical_lead,
        "haz_waste_product": haz_waste_product,
        "self_dispose_instructed": self_dispose_instructed,
        "explicit_hhw_warning": explicit_hhw_warning,
        "haz_household_disposal": haz_household_disposal,
        "haz_photo_disposal": haz_photo_disposal,
        "has_upc": has_upc,
        "has_inconjunction": has_inconjunction,
        "inconj_countries": inconj_countries,
        "has_injury": inj_parsed["has_injury"],
        "clean_injuries": inj_parsed["clean_injuries"],
        "has_death": inj_parsed["has_death"],
        "title_snip": title_txt[:140],
        "retailer_snip": ret_txt[:180],
        "remedy_snip": rem_txt[:220],
        "injury_snip": inj_txt[:180],
        "contact_snip": cc_txt[:140],
    }
    row.update(ent)
    row.update(ch)
    return row
