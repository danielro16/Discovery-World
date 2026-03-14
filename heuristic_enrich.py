#!/usr/bin/env python3
"""
Heuristic enrichment pipeline — no API key required.
Fetches website content and extracts structured fields using regex/keyword patterns.
Handles all 5 verticals: attorneys, dentists, gyms, therapists, restaurants.
"""
import json
import re
import ssl
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent / "data"

# ─── HTTP fetch ───────────────────────────────────────────────────────────────

def fetch_page(url: str, timeout: int = 10) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    raw = resp.read(400_000)
    ct = resp.headers.get('Content-Type', '')
    enc = 'utf-8'
    if 'charset=' in ct:
        enc = ct.split('charset=')[-1].split(';')[0].strip()
    try:
        return raw.decode(enc, errors='replace')
    except (UnicodeDecodeError, LookupError):
        return raw.decode('utf-8', errors='replace')


def clean_text(html: str) -> str:
    html = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&nbsp;', ' ').replace('&#39;', "'").replace('&quot;', '"') \
               .replace('&ldquo;', '"').replace('&rdquo;', '"').replace('&mdash;', '-')
    return re.sub(r'\s+', ' ', html).strip().lower()


def fetch_text(website: str) -> str:
    """Fetch main page + about/contact page. Returns cleaned lowercase text."""
    if not website.startswith('http'):
        website = 'https://' + website

    text = ''
    try:
        html = fetch_page(website)
        text = clean_text(html)
    except Exception:
        pass

    # Try secondary pages for more content
    if len(text) < 1000:
        parsed = urlparse(website)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in ['/about', '/about-us', '/our-firm', '/services', '/contact']:
            try:
                html2 = fetch_page(base + path, timeout=7)
                text2 = clean_text(html2)
                if len(text2) > len(text):
                    text = text2
                break
            except Exception:
                continue

    return text[:12000]  # Cap at 12K chars


# ─── Generic helpers ──────────────────────────────────────────────────────────

def find_languages(text: str) -> list:
    langs = []
    patterns = [
        (r'\benglish\b', 'English'),
        (r'\bspanish\b|hablamos espa[ñn]ol|se habla espa[ñn]ol', 'Spanish'),
        (r'\bmandarin\b|\bchinese\b|\bcantonese\b', 'Chinese/Mandarin'),
        (r'\bfrench\b|\bfrançais\b', 'French'),
        (r'\bkorean\b|\b한국어\b', 'Korean'),
        (r'\bportugues[e]?\b|\bportuguês\b', 'Portuguese'),
        (r'\bitalian\b|\bitaliano\b', 'Italian'),
        (r'\brussian\b|\bрусский\b', 'Russian'),
        (r'\barabic\b|\bعربي\b', 'Arabic'),
        (r'\bhindi\b|\bहिंदी\b', 'Hindi'),
        (r'\bjapanese\b|\b日本語\b', 'Japanese'),
        (r'\bvietnamese\b|\btiếng việt\b', 'Vietnamese'),
        (r'\bpolish\b|\bpolski\b', 'Polish'),
        (r'\bgerman\b|\bdeutsch\b', 'German'),
        (r'\bgreek\b|\bελληνικά\b', 'Greek'),
        (r'\bhebrew\b|\bעברית\b', 'Hebrew'),
        (r'\btagalog\b|\bfilipino\b', 'Filipino/Tagalog'),
        (r'\bpersian\b|\bfarsi\b|\bفارسی\b', 'Persian/Farsi'),
        (r'\burdu\b', 'Urdu'),
        (r'\bhaitian creole\b|\bcréole\b', 'Haitian Creole'),
        (r'\byiddish\b', 'Yiddish'),
        (r'\bbengli\b|\bbangla\b', 'Bengali'),
    ]
    for pattern, lang in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            langs.append(lang)
    if not langs:
        langs = ['English']
    return langs


def find_years_experience(text: str):
    patterns = [
        r'(\d{2,3})\+?\s*years?\s*(?:of\s*)?(?:combined\s*)?experience',
        r'(?:over|more than|with)\s*(\d{2,3})\s*years?\s*(?:of\s*)?(?:legal|law|practice|combined)',
        r'(\d{2,3})\s*years?\s*(?:in|serving|helping|practicing)',
        r'since\s*(\d{4})',
        r'established\s*(?:in\s*)?(\d{4})',
        r'founded\s*(?:in\s*)?(\d{4})',
    ]
    current_year = 2026
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val > 1900:  # It's a year
                years = current_year - val
                if 1 <= years <= 150:
                    return years
            elif 1 <= val <= 120:
                return val
    return None


def generate_description(name: str, vertical: str, data: dict, place: dict) -> str:
    """Generate a short AI-style description from extracted data."""
    addr_parts = place.get('address', '').split(',')
    city = addr_parts[-3].strip() if len(addr_parts) >= 3 else (addr_parts[-2].strip() if len(addr_parts) >= 2 else '')
    rating = place.get('rating') or 0
    reviews = place.get('review_count') or 0

    if vertical == 'attorneys':
        areas = data.get('practice_areas', [])
        areas_str = ', '.join(areas[:3]) if areas else 'legal'
        years = data.get('years_experience')
        free = data.get('free_consultation')
        langs = data.get('languages_spoken', ['English'])
        desc = f"{name} is a {city} law firm specializing in {areas_str}."
        if years:
            desc += f" With {years} years of experience,"
        if rating >= 4.5:
            desc += f" they hold a {rating}-star rating from {reviews}+ clients."
        if free:
            desc += " Free initial consultations available."
        if len(langs) > 1:
            desc += f" Services available in {', '.join(langs[:3])}."

    elif vertical == 'dentists':
        specs = data.get('specialties', [])
        specs_str = ', '.join(specs[:3]) if specs else 'general dentistry'
        insurance = data.get('insurance_accepted', [])
        desc = f"{name} is a dental practice in {city} offering {specs_str}."
        if rating >= 4.5:
            desc += f" Rated {rating}/5 by {reviews}+ patients."
        if insurance:
            desc += f" Accepts {', '.join(insurance[:3])}."
        if data.get('free_consultation'):
            desc += " Free consultations available."

    elif vertical == 'gyms':
        gtype = data.get('gym_type', 'fitness center')
        classes = data.get('classes_offered', [])
        desc = f"{name} is a {gtype} in {city}."
        if classes:
            desc += f" Classes include {', '.join(classes[:3])}."
        if data.get('open_24h'):
            desc += " Open 24 hours."
        if data.get('personal_training'):
            desc += " Personal training available."
        if rating >= 4.5:
            desc += f" Rated {rating}/5 stars."

    elif vertical == 'therapists':
        ttypes = data.get('therapy_types', [])
        specs = data.get('specialties', [])
        desc = f"{name} is a mental health practice in {city}."
        if ttypes:
            desc += f" Offering {', '.join(ttypes[:3])}."
        if specs:
            desc += f" Specializes in {', '.join(specs[:2])}."
        if data.get('telehealth'):
            desc += " Telehealth sessions available."
        if data.get('free_consultation'):
            desc += " Free initial consultation offered."

    elif vertical == 'restaurants':
        cuisine = data.get('cuisine_types', [])
        cuisine_str = ', '.join(cuisine[:2]) if cuisine else 'cuisine'
        desc = f"{name} is a {cuisine_str} restaurant in {city}."
        if data.get('reservations'):
            desc += " Accepts reservations."
        if data.get('delivery'):
            desc += " Delivery available."
        if data.get('private_dining'):
            desc += " Private dining options available."
        if rating >= 4.5:
            desc += f" Rated {rating}/5 by {reviews}+ diners."
    else:
        desc = f"{name} in {city}."

    return desc.strip()


def calc_completeness(place: dict) -> int:
    score = 0
    if place.get('name'): score += 10
    if place.get('address'): score += 10
    if place.get('phone'): score += 10
    if place.get('website'): score += 10
    if place.get('rating'): score += 10
    if place.get('review_count', 0) > 10: score += 10
    if place.get('hours'): score += 10
    if place.get('photos'): score += 5
    if place.get('email'): score += 5
    if place.get('enriched'):
        score += 10
        if place.get('languages_spoken'): score += 5
        if place.get('ai_description'): score += 5
    return min(score, 100)


# ─── Vertical extractors ──────────────────────────────────────────────────────

def extract_attorneys(text: str) -> dict:
    data = {}

    # Practice areas
    area_keywords = {
        'Immigration Law': [r'\bimmigration\b', r'\bvisa\b', r'\bdeportation\b', r'\basylum\b', r'\bgreen card\b', r'\bnaturalization\b'],
        'Personal Injury': [r'\bpersonal injury\b', r'\baccident\b', r'\bnegligence\b', r'\bcar accident\b', r'\bslip and fall\b'],
        'Family Law': [r'\bfamily law\b', r'\bdivorce\b', r'\bcustody\b', r'\balimony\b', r'\badoption\b', r'\bseparation\b'],
        'Criminal Defense': [r'\bcriminal\b', r'\bdefense\b', r'\bDUI\b', r'\bDWI\b', r'\barrest\b', r'\bfelony\b', r'\bmisdemeanor\b'],
        'Real Estate': [r'\breal estate\b', r'\bproperty\b', r'\bclosing\b', r'\btitle\b', r'\blandlord\b', r'\btenant\b'],
        'Corporate/Business': [r'\bcorporate\b', r'\bbusiness law\b', r'\bcontract\b', r'\bLLC\b', r'\bmerger\b', r'\bacquisition\b'],
        'Estate Planning': [r'\bestate planning\b', r'\bwill\b', r'\btrust\b', r'\bprobate\b', r'\binheritance\b'],
        'Employment Law': [r'\bemployment\b', r'\bworkplace\b', r'\bwrongful termination\b', r'\bdiscrimination\b', r'\bharassment\b'],
        'Bankruptcy': [r'\bbankruptcy\b', r'\bchapter 7\b', r'\bchapter 13\b', r'\bdebt relief\b'],
        'Medical Malpractice': [r'\bmedical malpractice\b', r'\bmedical negligence\b', r'\bhospital error\b'],
        'Intellectual Property': [r'\bintellectual property\b', r'\btrademark\b', r'\bcopyright\b', r'\bpatent\b'],
        'Social Security': [r'\bsocial security\b', r'\bdisability\b', r'\bSSI\b', r'\bSSDI\b'],
        'Workers Compensation': [r'\bworkers.{0,5}comp\b', r'\bwork injury\b', r'\bon.the.job\b'],
        'Civil Litigation': [r'\blitigation\b', r'\bcivil\b', r'\blawsuit\b', r'\btrial\b'],
    }
    found_areas = []
    for area, patterns in area_keywords.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            found_areas.append(area)
    data['practice_areas'] = found_areas[:8] if found_areas else ['General Practice']

    # Free consultation
    data['free_consultation'] = bool(re.search(
        r'free\s*(?:initial\s*)?consultation|no\s*cost\s*consultation|complimentary\s*consultation|free\s*case\s*(?:review|evaluation)',
        text, re.IGNORECASE
    ))

    # Fee structure
    if re.search(r'\bcontingency\b|\bno\s*fee\s*unless\b|\bno\s*win\s*no\s*fee\b', text, re.IGNORECASE):
        data['fee_structure'] = 'contingency'
    elif re.search(r'\bflat\s*fee\b|\bfixed\s*fee\b', text, re.IGNORECASE):
        data['fee_structure'] = 'flat fee'
    elif re.search(r'\bhourly\b|\bper\s*hour\b|\b\$/hr\b', text, re.IGNORECASE):
        data['fee_structure'] = 'hourly'
    elif re.search(r'\bretainer\b', text, re.IGNORECASE):
        data['fee_structure'] = 'retainer'
    else:
        data['fee_structure'] = None

    # Hourly rate
    m = re.search(r'\$(\d{2,4})\s*(?:to|-)\s*\$?(\d{2,4})\s*(?:per\s*)?hour', text, re.IGNORECASE)
    if m:
        data['hourly_range'] = f"${m.group(1)}-${m.group(2)}/hr"
    else:
        m2 = re.search(r'\$(\d{2,4})\s*(?:per\s*)?hour', text, re.IGNORECASE)
        if m2:
            data['hourly_range'] = f"${m2.group(1)}/hr"
        else:
            data['hourly_range'] = None

    # Bar admissions
    us_states = [
        'New York', 'California', 'Texas', 'Florida', 'Illinois', 'New Jersey',
        'Connecticut', 'Pennsylvania', 'Massachusetts', 'Washington', 'Colorado',
        'Georgia', 'North Carolina', 'Virginia', 'Maryland', 'Michigan', 'Ohio',
        'Nevada', 'Arizona', 'Minnesota', 'Tennessee', 'Missouri', 'Indiana',
        'Wisconsin', 'Oregon', 'Louisiana', 'Kentucky', 'Oklahoma', 'Utah',
        'Iowa', 'Arkansas', 'Mississippi', 'Kansas', 'Nevada', 'Nebraska',
        'Idaho', 'Hawaii', 'Maine', 'New Hampshire', 'Rhode Island', 'Montana',
        'Delaware', 'South Dakota', 'North Dakota', 'Alaska', 'Wyoming', 'Vermont',
        'New Mexico', 'West Virginia', 'South Carolina', 'Alabama'
    ]
    bar_admissions = []
    for state in us_states:
        if re.search(rf'\b{re.escape(state)}\b', text, re.IGNORECASE):
            bar_admissions.append(state)
    if re.search(r'\bfederal\b|\bsupreme court\b|\b2nd circuit\b|\bdistrict court\b', text, re.IGNORECASE):
        bar_admissions.append('Federal Courts')
    data['bar_admissions'] = list(set(bar_admissions))[:6] if bar_admissions else None

    # Team size
    m = re.search(r'(?:team of|over|more than|(\d+))\s*(\d+)?\s*(?:experienced\s*)?(?:attorneys|lawyers|partners|counsel)', text, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2)
        if val and val.isdigit():
            data['team_size'] = int(val)
        else:
            data['team_size'] = None
    else:
        data['team_size'] = None

    # Awards
    award_patterns = [r'super lawyers?', r'avvo\s*rat', r'martindale', r'best lawyers?', r'top\s*\d+\s*attorney', r'AV\s*rated', r'best law firm']
    awards = []
    for p in award_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            awards.append(m.group(0).strip().title())
    data['awards'] = list(set(awards)) if awards else None

    # Languages
    data['languages_spoken'] = find_languages(text)

    # Years experience
    data['years_experience'] = find_years_experience(text)

    # Tags
    tags = ['law firm', 'attorney', 'legal services']
    for area in (data['practice_areas'] or [])[:3]:
        tags.append(area.lower())
    if data['free_consultation']:
        tags.append('free consultation')
    data['tags'] = tags

    return data


def extract_dentists(text: str) -> dict:
    data = {}

    # Specialties
    specialty_map = {
        'General Dentistry': [r'\bgeneral dentist\b', r'\bfamily dentist\b', r'\bpreventive\b'],
        'Cosmetic Dentistry': [r'\bcosmetic\b', r'\bveneers?\b', r'\bwhitening\b', r'\bsmile makeover\b', r'\besthetic\b'],
        'Orthodontics': [r'\borthodont\b', r'\bbraces\b', r'\binvisalign\b', r'\baligners?\b'],
        'Implants': [r'\bdental implant\b', r'\bimplant\b'],
        'Oral Surgery': [r'\boral surgery\b', r'\bextraction\b', r'\bwisdom teeth\b'],
        'Endodontics': [r'\bendodont\b', r'\broot canal\b'],
        'Periodontics': [r'\bperiodont\b', r'\bgum disease\b', r'\bgum treatment\b'],
        'Pediatric Dentistry': [r'\bpediatric\b|\bchildren.{0,5}dentist\b|\bkids.{0,5}dentist\b'],
        'Prosthodontics': [r'\bprosthodont\b|\bdentures?\b|\bcrowns?\b|\bbridges?\b'],
        'Sedation Dentistry': [r'\bsedation\b|\banxiety.{0,5}dentist\b|\bsleep dentist\b'],
        'Emergency Dentistry': [r'\bemergency dent\b|\bsame.day\b|\bwalk.in\b'],
        'TMJ Treatment': [r'\bTMJ\b|\bTMD\b|\bjaw pain\b'],
    }
    specs = []
    for spec, patterns in specialty_map.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            specs.append(spec)
    data['specialties'] = specs if specs else ['General Dentistry']

    # Insurance
    insurance_list = [
        'Delta Dental', 'Cigna', 'Aetna', 'MetLife', 'United Concordia',
        'Guardian', 'Humana', 'Anthem', 'Blue Cross', 'Principal',
        'Sun Life', 'Ameritas', 'Dental Select', 'Medicaid', 'Medicare',
    ]
    found_ins = []
    for ins in insurance_list:
        if re.search(re.escape(ins), text, re.IGNORECASE):
            found_ins.append(ins)
    if re.search(r'\bmost\s*(?:major\s*)?insurance\b|\ball\s*(?:major\s*)?insurance\b|\bmost\s*plans?\b', text, re.IGNORECASE):
        found_ins.append('Most Major Insurance')
    data['insurance_accepted'] = list(set(found_ins))[:8] if found_ins else None

    # Free consultation
    data['free_consultation'] = bool(re.search(
        r'free\s*(?:initial\s*)?(?:consultation|exam|x.?ray|cleaning)|no\s*cost\s*(?:consultation|exam)',
        text, re.IGNORECASE
    ))

    # Payment plans
    data['payment_plans'] = bool(re.search(
        r'payment\s*plan|financing|carecredit|cherry\s*financing|monthly\s*payment|interest.free|0%\s*interest',
        text, re.IGNORECASE
    ))

    # Emergency hours
    data['emergency_dentistry'] = bool(re.search(
        r'emergency|same.day|walk.in|urgent|after.hours',
        text, re.IGNORECASE
    ))

    # Technology
    tech = []
    tech_map = {
        'Digital X-Rays': [r'digital x.?ray', r'digital radiograph'],
        'CEREC/Same-Day Crowns': [r'cerec|same.day crown|one.visit crown'],
        'Laser Dentistry': [r'laser dent'],
        'Invisalign': [r'invisalign'],
        '3D Imaging': [r'3d imaging|cone beam|cbct'],
        'Sedation': [r'sedation|nitrous|laughing gas'],
    }
    for t, patterns in tech_map.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            tech.append(t)
    data['technology'] = tech if tech else None

    data['languages_spoken'] = find_languages(text)
    data['years_experience'] = find_years_experience(text)

    tags = ['dentist', 'dental care']
    for s in (data['specialties'] or [])[:3]:
        tags.append(s.lower())
    if data['payment_plans']:
        tags.append('payment plans')
    if data['free_consultation']:
        tags.append('free consultation')
    data['tags'] = tags

    return data


def extract_gyms(text: str) -> dict:
    data = {}

    # Gym type
    if re.search(r'\bcrossfit\b', text, re.IGNORECASE):
        data['gym_type'] = 'CrossFit'
    elif re.search(r'\byoga\b|\bpilates\b', text, re.IGNORECASE) and not re.search(r'\bweight\b|\bstrength\b', text, re.IGNORECASE):
        data['gym_type'] = 'Yoga/Pilates Studio'
    elif re.search(r'\bboxing\b|\bmuay thai\b|\bkickboxing\b|\bMMA\b|\bmartial arts\b', text, re.IGNORECASE):
        data['gym_type'] = 'Boxing/Martial Arts'
    elif re.search(r'\bboutique\b|\bstudio\b', text, re.IGNORECASE):
        data['gym_type'] = 'Boutique Studio'
    elif re.search(r'\bspin\b|\bcycling\b|\bsoulcycle\b', text, re.IGNORECASE):
        data['gym_type'] = 'Cycling Studio'
    else:
        data['gym_type'] = 'Full-Service Gym'

    # Classes
    class_map = {
        'Yoga': r'\byoga\b', 'Pilates': r'\bpilates\b', 'CrossFit': r'\bcrossfit\b',
        'HIIT': r'\bHIIT\b|\bhigh.intensity\b', 'Spin/Cycling': r'\bspin\b|\bcycling\b',
        'Zumba': r'\bzumba\b', 'Boxing': r'\bboxing\b', 'Kickboxing': r'\bkickboxing\b',
        'Strength Training': r'\bstrength training\b|\bweight training\b|\bpowerlifting\b',
        'Cardio': r'\bcardio\b|\baerobic\b', 'Bootcamp': r'\bbootcamp\b|\bboot camp\b',
        'Dance': r'\bdance\b|\bzumba\b|\bballet\b', 'Swimming': r'\bswimming\b|\bpool\b',
        'TRX': r'\bTRX\b', 'Barre': r'\bbarre\b', 'Rock Climbing': r'\bclimbing\b',
        'Martial Arts': r'\bkarate\b|\bjudo\b|\bjiu.?jitsu\b|\bmuay thai\b|\bMMA\b',
        'Group Fitness': r'\bgroup\s*(?:fitness|class|exercise)\b',
    }
    classes = [name for name, p in class_map.items() if re.search(p, text, re.IGNORECASE)]
    data['classes_offered'] = classes[:10] if classes else None

    # Amenities
    amenity_map = {
        'Sauna': r'\bsauna\b', 'Steam Room': r'\bsteam room\b',
        'Pool': r'\bpool\b|\bswimming\b', 'Locker Rooms': r'\blocker\b',
        'Showers': r'\bshower\b', 'Childcare': r'\bchildcare\b|\bdaycare\b|\bkids?\s*club\b',
        'Parking': r'\bparking\b', 'Café/Juice Bar': r'\bjuice bar\b|\bcafé\b|\bsmoothie\b',
        'Racquetball': r'\bracquetball\b|\bsquash\b', 'Basketball': r'\bbasketball\b',
        'Tanning': r'\btanning\b', 'Massage': r'\bmassage\b',
    }
    amenities = [name for name, p in amenity_map.items() if re.search(p, text, re.IGNORECASE)]
    data['amenities'] = amenities if amenities else None

    # Membership
    m = re.search(r'\$(\d{1,3}(?:\.\d{2})?)\s*(?:per|/)\s*month|(\d{1,3}(?:\.\d{2})?)\s*(?:per|/)\s*(?:mo|month)', text, re.IGNORECASE)
    data['membership_price_monthly'] = f"${m.group(1) or m.group(2)}/mo" if m else None

    data['personal_training'] = bool(re.search(r'personal training|personal trainer|one.on.one', text, re.IGNORECASE))
    data['open_24h'] = bool(re.search(r'24.?hour|open 24|24/7', text, re.IGNORECASE))
    data['free_trial'] = bool(re.search(r'free\s*trial|free\s*(?:first\s*)?class|complimentary\s*(?:visit|session|class)', text, re.IGNORECASE))

    data['languages_spoken'] = find_languages(text)
    data['years_experience'] = find_years_experience(text)

    tags = ['gym', 'fitness']
    if data['gym_type']:
        tags.append(data['gym_type'].lower())
    if data['open_24h']:
        tags.append('open 24 hours')
    if data['personal_training']:
        tags.append('personal training')
    data['tags'] = tags

    return data


def extract_therapists(text: str) -> dict:
    data = {}

    # Therapy types
    therapy_map = {
        'Cognitive Behavioral Therapy (CBT)': [r'\bCBT\b', r'\bcognitive.behavioral\b'],
        'EMDR': [r'\bEMDR\b', r'\beye movement\b'],
        'Psychodynamic Therapy': [r'\bpsychodynamic\b'],
        'DBT': [r'\bDBT\b', r'\bdialectical behavior\b'],
        'Mindfulness-Based': [r'\bmindfulness\b', r'\bmeditation.based\b', r'\bMBSR\b'],
        'Family Therapy': [r'\bfamily therapy\b', r'\bfamily counseling\b'],
        'Couples Therapy': [r'\bcouples\b', r'\bmarriage counseling\b', r'\brelationship therapy\b'],
        'Group Therapy': [r'\bgroup therapy\b', r'\bgroup counseling\b', r'\bsupport group\b'],
        'Play Therapy': [r'\bplay therapy\b'],
        'Art/Music Therapy': [r'\bart therapy\b', r'\bmusic therapy\b'],
        'Trauma Therapy': [r'\btrauma\b', r'\bPTSD\b', r'\btrauma.informed\b'],
        'Somatic Therapy': [r'\bsomatic\b', r'\bbody.based\b'],
        'Psychoanalysis': [r'\bpsychoanalysis\b', r'\bpsychoanalytic\b'],
        'Acceptance Therapy (ACT)': [r'\bACT\b', r'\bacceptance and commitment\b'],
        'Gottman Method': [r'\bgottman\b'],
        'Solution-Focused': [r'\bsolution.focused\b', r'\bSFBT\b'],
        'Narrative Therapy': [r'\bnarrative therapy\b'],
        'Humanistic': [r'\bhumanistic\b', r'\bperson.centered\b', r'\bclient.centered\b'],
    }
    ttypes = []
    for ttype, patterns in therapy_map.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            ttypes.append(ttype)
    data['therapy_types'] = ttypes[:8] if ttypes else ['Individual Therapy']

    # Specialties / issues treated
    specialty_map = {
        'Anxiety': [r'\banxiety\b', r'\bpanic\b', r'\bworry\b'],
        'Depression': [r'\bdepression\b', r'\bdepressive\b', r'\bmood disorder\b'],
        'Trauma/PTSD': [r'\btrauma\b', r'\bPTSD\b', r'\babuse\b'],
        'Relationships': [r'\brelationship\b', r'\bcouple\b', r'\bmarriage\b', r'\binfidelity\b'],
        'Addiction': [r'\baddiction\b', r'\bsubstance\b', r'\balcohol\b', r'\bdrug\b'],
        'Grief': [r'\bgrief\b', r'\bloss\b', r'\bbereavement\b'],
        'ADHD': [r'\bADHD\b', r'\battention deficit\b'],
        'Eating Disorders': [r'\beating disorder\b', r'\banorexia\b', r'\bbulimia\b', r'\bbinge eating\b'],
        'OCD': [r'\bOCD\b', r'\bobsessive.compulsive\b'],
        'Bipolar': [r'\bbipolar\b', r'\bmanic\b'],
        'LGBTQ+': [r'\bLGBTQ\b', r'\bgay\b affirm|\bqueer\b|\btransgender\b'],
        'Life Transitions': [r'\blife transition\b', r'\bcareer\b', r'\bidentity\b'],
        'Parenting': [r'\bparenting\b', r'\bparent\b', r'\bchild\b', r'\bfamily\b'],
        'Stress': [r'\bstress\b', r'\bburnout\b', r'\bwork.life\b'],
        'Self-Esteem': [r'\bself.esteem\b', r'\bself.confidence\b', r'\bself.worth\b'],
    }
    specs = []
    for spec, patterns in specialty_map.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            specs.append(spec)
    data['specialties'] = specs[:8] if specs else None

    # Credentials
    creds = []
    cred_patterns = {
        'Licensed Clinical Social Worker (LCSW)': r'\bLCSW\b',
        'Licensed Professional Counselor (LPC)': r'\bLPC\b',
        'Licensed Marriage and Family Therapist (LMFT)': r'\bLMFT\b',
        'Psychologist (PhD/PsyD)': r'\bPh\.?D\b|\bPsy\.?D\b|\bpsychologist\b',
        'Psychiatrist (MD)': r'\bpsychiatrist\b|\bM\.D\.\b',
        'Licensed Mental Health Counselor (LMHC)': r'\bLMHC\b',
        'Licensed Professional Clinical Counselor (LPCC)': r'\bLPCC\b',
        'Certified in EMDR': r'\bEMDR\s*certified\b|\bcertified\s*EMDR\b',
    }
    for cred, p in cred_patterns.items():
        if re.search(p, text, re.IGNORECASE):
            creds.append(cred)
    data['credentials'] = creds if creds else None

    # Insurance
    ins_list = ['Aetna', 'Cigna', 'United Healthcare', 'Blue Cross', 'Blue Shield',
                'Magellan', 'Optum', 'Beacon Health', 'Humana', 'Anthem', 'Oscar',
                'Medicare', 'Medicaid', 'Tricare']
    found_ins = [i for i in ins_list if re.search(re.escape(i), text, re.IGNORECASE)]
    if re.search(r'\bmost\s*(?:major\s*)?insurance\b|\bmany\s*insurance\b', text, re.IGNORECASE):
        found_ins.append('Most Major Insurance')
    data['insurance_accepted'] = list(set(found_ins))[:8] if found_ins else None

    data['telehealth'] = bool(re.search(r'\btelehealth\b|\bonline therapy\b|\bvirtual\s*(?:session|therapy|appointment)\b|\bvideo\s*(?:session|therapy)\b', text, re.IGNORECASE))
    data['free_consultation'] = bool(re.search(r'free\s*(?:initial\s*)?(?:consultation|session|call|15.min)', text, re.IGNORECASE))
    data['sliding_scale'] = bool(re.search(r'sliding\s*scale|reduced\s*(?:fee|rate)|income.based\b', text, re.IGNORECASE))

    data['languages_spoken'] = find_languages(text)
    data['years_experience'] = find_years_experience(text)

    tags = ['therapist', 'mental health', 'counseling']
    for s in (data['specialties'] or [])[:3]:
        tags.append(s.lower())
    if data['telehealth']:
        tags.append('telehealth')
    if data['sliding_scale']:
        tags.append('sliding scale fees')
    data['tags'] = tags

    return data


def extract_restaurants(text: str) -> dict:
    data = {}

    # Cuisine types
    cuisine_map = {
        'Italian': [r'\bitalian\b', r'\bpasta\b', r'\bpizza\b', r'\brisotto\b', r'\btrattoria\b'],
        'Mexican': [r'\bmexican\b', r'\btaco\b', r'\bburrito\b', r'\bguacamole\b', r'\btaqueria\b'],
        'Japanese': [r'\bjapanese\b', r'\bsushi\b', r'\bramen\b', r'\budon\b', r'\bhibachi\b'],
        'Chinese': [r'\bchinese\b', r'\bdim sum\b', r'\bcantonese\b', r'\bszechuan\b', r'\bwonton\b'],
        'Indian': [r'\bindian\b', r'\bcurry\b', r'\btandoor\b', r'\bnaan\b', r'\bbiryani\b'],
        'Thai': [r'\bthai\b', r'\bpad thai\b', r'\btom yum\b', r'\bgreen curry\b'],
        'American': [r'\bamerican\b', r'\bburger\b', r'\bbbq\b', r'\bbarbecue\b', r'\bsteakhouse\b'],
        'Mediterranean': [r'\bmediterranean\b', r'\bgreek\b', r'\bhummus\b', r'\bfalafel\b', r'\bgyro\b'],
        'French': [r'\bfrench\b', r'\bbistro\b', r'\bcrepe\b', r'\bcoq au vin\b'],
        'Seafood': [r'\bseafood\b', r'\blobster\b', r'\bshrimp\b', r'\boyster\b', r'\bfish\b'],
        'Steakhouse': [r'\bsteakhouse\b', r'\bsteak\b', r'\bfilet\b', r'\bribeye\b'],
        'Vegan/Vegetarian': [r'\bvegan\b', r'\bvegetarian\b', r'\bplant.based\b'],
        'Korean': [r'\bkorean\b', r'\bbibimbap\b', r'\bKBBQ\b|\bkorean bbq\b'],
        'Vietnamese': [r'\bvietnamese\b', r'\bpho\b', r'\bbanh mi\b'],
        'Middle Eastern': [r'\bmiddle eastern\b', r'\blebanese\b', r'\bpersian\b', r'\bshakshuka\b'],
        'Latin/Peruvian': [r'\bperuvian\b|\blatin\b|\bsouth american\b|\bcolombian\b'],
        'Brunch': [r'\bbrunch\b'],
        'Bakery/Cafe': [r'\bbakery\b', r'\bcafé\b', r'\bcoffee\b', r'\bcroissant\b'],
        'Pizza': [r'\bpizza\b|\bpizzeria\b|\bneapolitan\b'],
    }
    cuisines = []
    for cuisine, patterns in cuisine_map.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            cuisines.append(cuisine)
    data['cuisine_types'] = cuisines[:5] if cuisines else ['American']

    # Dietary options
    dietary = []
    if re.search(r'\bvegan\b|\bvegan.?friendly\b', text, re.IGNORECASE): dietary.append('Vegan')
    if re.search(r'\bvegetarian\b', text, re.IGNORECASE): dietary.append('Vegetarian')
    if re.search(r'\bgluten.free\b', text, re.IGNORECASE): dietary.append('Gluten-Free')
    if re.search(r'\bhalal\b', text, re.IGNORECASE): dietary.append('Halal')
    if re.search(r'\bkosher\b', text, re.IGNORECASE): dietary.append('Kosher')
    if re.search(r'\bdairy.free\b|\blactose.free\b', text, re.IGNORECASE): dietary.append('Dairy-Free')
    if re.search(r'\bnut.free\b|\ballergy.friendly\b', text, re.IGNORECASE): dietary.append('Allergy-Friendly')
    data['dietary_options'] = dietary if dietary else None

    # Features
    data['reservations'] = bool(re.search(r'\breservation\b|\bbook\s*a\s*table\b|\bopentable\b|\bresy\b', text, re.IGNORECASE))
    data['delivery'] = bool(re.search(r'\bdelivery\b|\bdeliver\b|\bdoordash\b|\bubereats\b|\bgrubhub\b', text, re.IGNORECASE))
    data['takeout'] = bool(re.search(r'\btakeout\b|\btake.out\b|\bcarryout\b|\bto.go\b', text, re.IGNORECASE))
    data['catering'] = bool(re.search(r'\bcatering\b|\bcater\b', text, re.IGNORECASE))
    data['private_dining'] = bool(re.search(r'\bprivate\s*dining\b|\bprivate\s*room\b|\bprivate\s*event\b|\bevent\s*space\b', text, re.IGNORECASE))
    data['outdoor_seating'] = bool(re.search(r'\boutdoor\s*seating\b|\bpatio\b|\bterrace\b|\bal\s*fresco\b', text, re.IGNORECASE))
    data['happy_hour'] = bool(re.search(r'\bhappy\s*hour\b|\bspecials?\b', text, re.IGNORECASE))
    data['brunch'] = bool(re.search(r'\bbrunch\b', text, re.IGNORECASE))

    data['languages_spoken'] = find_languages(text)
    data['years_experience'] = find_years_experience(text)

    tags = ['restaurant', 'dining']
    for c in (data['cuisine_types'] or [])[:3]:
        tags.append(c.lower())
    if data['delivery']:
        tags.append('delivery')
    if data['outdoor_seating']:
        tags.append('outdoor seating')
    if data['private_dining']:
        tags.append('private dining')
    data['tags'] = tags

    return data


# ─── Main enrichment runner ───────────────────────────────────────────────────

EXTRACTORS = {
    'attorneys': extract_attorneys,
    'dentists': extract_dentists,
    'gyms': extract_gyms,
    'therapists': extract_therapists,
    'restaurants': extract_restaurants,
}


def enrich_place(place: dict, vertical: str) -> dict:
    website = place.get('website', '')
    if not website:
        return place

    text = fetch_text(website)
    if not text:
        return place

    extractor = EXTRACTORS.get(vertical)
    if not extractor:
        return place

    enriched_data = extractor(text)

    # Merge into place
    place.update(enriched_data)
    place['ai_description'] = generate_description(place.get('name', ''), vertical, enriched_data, place)
    place['enriched'] = True
    place['profile_completeness'] = calc_completeness(place)

    return place


def process_file(places_path: Path, vertical: str, workers: int = 15, limit: int = None):
    with open(places_path) as f:
        places = json.load(f)

    to_enrich = [p for p in places if not p.get('enriched') and p.get('website')]
    # Sort by rating × sqrt(reviews) descending
    to_enrich.sort(key=lambda p: (p.get('rating') or 0) * ((p.get('review_count') or 0) ** 0.5), reverse=True)

    if limit:
        to_enrich = to_enrich[:limit]

    if not to_enrich:
        return 0

    already_enriched = sum(1 for p in places if p.get('enriched'))
    print(f"\n  📂 {places_path.parent.name} | already: {already_enriched} | to process: {len(to_enrich)}")

    # Index for fast lookup
    place_by_id = {p.get('id'): p for p in places}

    done = 0
    success = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(enrich_place, p, vertical): p for p in to_enrich}
        for future in as_completed(futures):
            result = future.result()
            if result.get('enriched'):
                success += 1
            done += 1
            if done % 20 == 0 or done == len(to_enrich):
                print(f"    [{done}/{len(to_enrich)}] enriched: {success}")

    with open(places_path, 'w') as f:
        json.dump(places, f, indent=2, ensure_ascii=False)

    return success


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Heuristic enrichment — no API key required')
    parser.add_argument('--vertical', help='Specific vertical or "all"', default='all')
    parser.add_argument('--city', help='Specific city slug (optional)')
    parser.add_argument('--workers', type=int, default=15)
    parser.add_argument('--limit', type=int, help='Max businesses per file (for testing)')
    args = parser.parse_args()

    verticals = list(EXTRACTORS.keys()) if args.vertical == 'all' else [args.vertical]

    total_enriched = 0
    start = time.time()

    for vertical in verticals:
        vdir = DATA_DIR / vertical
        if not vdir.exists():
            print(f"⚠️  Vertical not found: {vertical}")
            continue

        print(f"\n{'='*60}")
        print(f"🏷️  VERTICAL: {vertical.upper()}")
        print(f"{'='*60}")

        city_dirs = sorted(vdir.iterdir())
        for city_dir in city_dirs:
            if not city_dir.is_dir() or city_dir.name.startswith('.'):
                continue
            if args.city and city_dir.name != args.city:
                continue

            places_path = city_dir / 'places.json'
            if not places_path.exists():
                continue

            enriched = process_file(places_path, vertical, args.workers, args.limit)
            total_enriched += enriched

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"✅ DONE — {total_enriched} businesses enriched in {elapsed/60:.1f} minutes")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
