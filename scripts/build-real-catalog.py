"""Build the reviewed source inventory into 700 schema-validated, reproducible entries.

This script writes files only. It never connects to MongoDB or claims live availability.
"""
from app.modules.catalog.unified import release, write_release
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from app.modules.catalog.schemas import Content

VERSION = 'real_catalog_v1'
DATE = '2026-11-14'
INTENTS = {
    'detachment': 'اجرای تجربه بیرونیِ مشخص در گام دوم، فرصتی برای فاصله‌گرفتن از کار روزمره فراهم می‌کند؛ نتیجه برای همه تضمین نیست.',
    'relaxation': 'قدم‌زدن یا مکث آرامِ گام دوم، فشار اجرای کار را کم نگه می‌دارد؛ این هدف محتوایی است و ادعای درمان نیست.',
    'autonomy': 'انتخاب جزئیات اجرا و شکل نتیجه در گام‌های دوم و سوم به خود فرد واگذار شده است.',
    'mastery': 'تمرین عملی و بررسی نتیجه در گام‌های دوم و سوم، یک مهارت مشخص را قابل تکرار می‌کند.',
    'meaning': 'ساخت یادگاری و ثبت ارتباط آن با فرد یا سابقه واقعی در گام‌های دوم و سوم، دلیل شخصیِ انجام کار را مشخص می‌کند.',
    'affiliation': 'اجرای نوبتی و همکاری واقعی با همراه در گام‌های دوم و سوم، بخش ضروری خود تجربه است.',
}
OUTDOOR = {'park','garden','walk','view','bridge','bazaar','heritage','literature','cable','ride','golf','archery','zipline','paintball','karting','football'}
SPORTS = {'tennis','padel','billiards','golf','basketball','volleyball','futsal','badminton','archery','squash','table_tennis','skate','bowling','climbing','gym','football'}
GROUP_SPORTS = {'padel': (4,4), 'billiards':(2,4), 'basketball':(4,10), 'volleyball':(4,12), 'futsal':(6,10), 'badminton':(2,4), 'squash':(2,2), 'table_tennis':(2,4), 'football':(6,12), 'paintball':(4,12)}


def stable_key(prefix, *parts):
    return 'real:' + prefix + '-' + hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]


def alignment(dimension, intent=None):
    return {'version':'dramma_v1', 'mechanisms':[{'dimension':dimension,
        'intent':intent or INTENTS[dimension], 'step_indexes':[2,3] if dimension != 'detachment' else [2]}]}


def base(title, steps, dimension, minutes, items, materials, tags, together=False, energy='low', mobility='seated', cost='free'):
    return dict(title=title, teaser='یک تجربهٔ عملی با نتیجهٔ مشخص؛ وسایل و مراحل را پیش از شروع ببین.',
        first_step=steps[0], steps=steps, lighter_version='فقط بخش اول کار را با اندازه یا تعداد کمتر انجام بده؛ ادامه‌دادن اجباری نیست.',
        materials_note=materials, accessibility_note='با توجه به توان دست و بدن، نشسته یا با همراه کمک‌کننده اجرا کن.',
        conditions_note='وسایل نام‌برده باید از قبل موجود باشند؛ اگر نداری، این مورد را برای بعد نگه دار.',
        requires_venue_check=False, place=None, primary_dimension=dimension, secondary_dimensions=[], dramma=alignment(dimension), tags=tags,
        active_minutes=minutes, setup_minutes=5, travel_minutes=0, energy_required=energy, mobility_required=mobility,
        supported_social_modes=['together'] if together else ['solo','together'], min_people=2 if together else 1, max_people=12,
        venue='home', required_items=items, requires_async_contact=False, step_free=True,
        quiet_compatible=True, weather_requirement='any', daylight_requirement='any',
        cost=dict(kind=cost, min_toman=0 if cost=='free' else None, max_toman=0 if cost=='free' else None,
            basis='per_group', verified_at=None, valid_until=None,
            note='با وسایل موجود و بدون خرید تازه؛ خرید وسیله در این پیشنهاد حساب نشده است.' if cost=='free' else 'مواد مصرفی، انرژی و خرید احتمالی هزینه دارند؛ قیمت روز تأیید نشده و سقف مشخصی وعده داده نمی‌شود.'),
        safety_notes=[])


def venue_content(city, name, kind, focus, source):
    public_name = name if city in name else f'{name}، {city}'
    title = public_name if len(public_name)<=60 else name
    steps = [f'در منبع معرفی، نشانی و راه ارتباطی {name} را پیدا کن؛ بازبودن، هزینه، مسیر و شرایط بازدید روز موردنظر را از مجموعه بررسی کن.',
        f'در بخش‌های مجاز و باز مجموعه، برای این تجربه وقت بگذار: {focus}. مسیر رسمی و مقررات همان محل را رعایت کن.',
        'پیش از خروج، بخش دلخواهت را با فرصت باقی‌مانده کامل کن و زمان برگشت را در نظر بگیر؛ ورود به بخش بسته یا خصوصی جزو برنامه نیست.']
    dimension, minutes, tags = 'detachment',60,['culture','discovery']
    materials = 'کفش و پوشش مناسب محل؛ بلیت یا هزینه احتمالی را پیش از رفتن بررسی کن.'
    lighter = 'به‌جای دیدن همه بخش‌ها، فقط یک بخش عمومی و باز را انتخاب کن؛ اگر بسته بود برنامه را به روز دیگری موکول کن.'
    if kind in {'park','garden','walk','view','bridge'}:
        dimension,tags='relaxation',['nature','walking']
        steps[1]=f'در مسیر عمومی و باز، این کار را انجام بده: {focus}. سرعت و فاصله را در حد راحتی نگه دار و در جای مجاز مکث کن.'
        steps[2]='در نقطه‌ای که هنوز انرژی برگشت داری مسیر را برگرد و اگر خواستی چند دقیقه نشسته استراحت کن؛ لازم نیست کل محوطه را ببینی.'
    elif kind in {'restaurant','fastfood','cafe'}:
        dimension,minutes,tags='autonomy',60,['food','choice']
        steps[1]='منوی جاری و قیمت نهایی را ببین؛ درباره مواد حساسیت‌زا بپرس و یک غذا یا نوشیدنی متناسب با اشتها و بودجه‌ات انتخاب کن.'
        steps[2]='سفارش را نشسته و با فرصت کافی میل کن؛ انتخاب طعم، اندازه و همراهی غذا با خودت است و خرید چند قلم لازم نیست.'
        lighter='فقط یک سفارش کوچک و روشن از نظر قیمت بگیر؛ اگر منو مناسب نبود، خرید اجباری نیست.'
        materials='هزینه سفارش و رفت‌وآمد؛ برای رستوران، پذیرش مراجعه‌کننده و رزرو احتمالی را بررسی کن.'
    elif kind in {'cinema','theatre','concert'}:
        minutes=150 if kind=='concert' else 120
        label={'cinema':'فیلم','theatre':'نمایش','concert':'اجرای موسیقی'}[kind]
        tags=['culture','listening'] if kind!='cinema' else ['culture','storytelling']
        steps[0]=f'برنامه معتبر {name} را برای روز موردنظر ببین؛ {label}، مدت کامل، قیمت نهایی و صندلی را بررسی و فقط از مسیر معتبر بلیت تهیه کن.'
        steps[1]=f'با زمان کافی برای ورود حاضر شو و {label} انتخابی را کامل تماشا یا گوش کن؛ گوشی را مطابق مقررات ساکت نگه دار.'
        steps[2]='پس از پایان از مسیر مجاز خارج شو و برای برگشت عجله نکن؛ اگر زمان اجرای کامل در وقتت جا نمی‌شود، سانس دیگری انتخاب کن.'
        lighter='یک برنامه کوتاه‌ترِ واقعاً در حال اجرا انتخاب کن؛ کوتاه‌کردن خودسرانه زمان فیلم یا اجرای زنده جزو این برنامه نیست.'
        materials='بلیت معتبر همان روز و سانس؛ این لینک معرفی محل است و وجود یک اجرای مشخص را تأیید نمی‌کند.'
    elif kind in SPORTS or kind=='paintball':
        dimension,minutes,tags='mastery',60,['movement','play']
        steps[1]=f'بعد از آموزش مسئول مجموعه، {focus} را در سطح مبتدی و متناسب با توان خودت اجرا کن؛ قواعد و تجهیزات همان بخش را رعایت کن.'
        steps[2]='یک بخش کوتاه از مهارت یا بازی را دوباره امتحان کن و نتیجه را مقایسه کن؛ در پایان وسایل امانی را تحویل بده و استراحت کن.'
        materials='پوشش ورزشی مناسب؛ درباره وسایل امانی، مربی، شرایط پذیرش و مجوز یک جلسه پیشاپیش بپرس.'
        if kind in GROUP_SPORTS:
            dimension='affiliation'
            steps[1]=f'با همراهان هماهنگ‌شده و پس از آموزش مسئول، {focus}؛ نوبت‌ها و نقش‌ها را قبل از شروع مشخص کنید.'
            steps[2]='یک دور کوتاه دیگر با جابه‌جایی نقش یا نوبت انجام دهید؛ درباره ادامه بازی با هم توافق کنید و وسایل امانی را تحویل بدهید.'
        lighter='یک جلسه آشنایی یا بخش مقدماتی را فقط در صورت ارائه واقعی مجموعه انتخاب کن؛ خرید دوره چندجلسه‌ای اجباری نیست.'
    elif kind in {'cable','ride','zipline','karting','vr','amusement','cave','aquarium'}:
        minutes=45 if kind!='cave' else 120
        tags=['play','discovery']
        steps[1]=f'پس از پذیرش شرایط اپراتور و آموزش لازم، {focus}؛ فقط از تجهیزات و مسیر فعال همان مجموعه استفاده کن.'
        steps[2]='نوبت یا مسیر مجاز را کامل کن و در خروجی تعیین‌شده خارج شو؛ اگر شرایط پذیرش را نداری، این تجربه را انجام نده.'
        lighter='فقط یک نوبت یا مسیر کوتاه‌ترِ واقعاً ارائه‌شده بگیر؛ اگر مجموعه تعطیل است، تجربه جایگزین را جدا انتخاب کن.'
    elif kind in {'shopping','bookshop','bazaar'}:
        dimension,tags='autonomy',['discovery','choice']
        steps[1]=f'از میان بخش‌های عمومی، بخش دلخواهت را برای {focus} انتخاب کن؛ قیمت را قبل از هر خرید بپرس.'
        steps[2]='گردش را با یک انتخاب شخصی مثل دیدن کتاب، صنایع دستی یا ویترین دلخواه کامل کن؛ خریدکردن شرط این تجربه نیست.'
    elif kind=='gallery':
        steps[1]='فقط نمایشگاه واقعاً باز همان روز را ببین؛ میان آثار با ریتم خودت حرکت کن و مقررات عکاسی را رعایت کن.'
    elif kind=='literature':
        steps[1]=f'در محوطه مجاز، {focus}؛ اگر متن شعر همراهت نیست، فقط بازدید محوطه را انجام بده.'
    content=base(title,steps,dimension,minutes,[],materials,tags,kind in GROUP_SPORTS,
        'medium' if kind in SPORTS or kind=='paintball' else 'low',
        'active' if kind in SPORTS or kind=='paintball' else 'light', 'unknown')
    content.update(teaser=f'{focus} در {city}؛ پیش از رفتن، برنامه و شرایط روز را بررسی کن.',
        first_step=steps[0], lighter_version=lighter, venue='outdoor' if kind in OUTDOOR else 'indoor_public',
        setup_minutes=20,travel_minutes=60,requires_venue_check=True,
        place={'name':name,'city':city,'source_url':source['url'],'source_name':source['publisher'],
            'researched_on':DATE,'evidence_scope':'place_and_activity_type_only'},
        conditions_note='وجود محل و نوع تجربه در منبع معرفی آمده؛ بازبودن، ظرفیت، محدودیت سن/قد/وزن، شرایط پذیرش و قیمت روز را خودت بررسی کن. زمان رفت‌وبرگشت این برنامه حداکثر ۶۰ دقیقه فرض شده؛ اگر مسیرت طولانی‌تر است مناسب وقتت نیست.',
        accessibility_note='دسترسی بدون پله، جای نشستن و امکانات مناسب نیاز تو تأیید نشده؛ پیش از تهیه بلیت از مسئول مجموعه بپرس.',
        step_free=None, quiet_compatible=None)
    if content['venue']=='outdoor': content['weather_requirement']='fair'
    if kind in GROUP_SPORTS:
        content['min_people'],content['max_people']=GROUP_SPORTS[kind]
    content['dramma']=alignment(dimension,
        'فرد در گام دوم غذای متناسب با اشتها و سلیقه‌اش را انتخاب می‌کند و در گام سوم اندازه و شیوه همراهی آن را خودش تعیین می‌کند.' if kind in {'restaurant','fastfood','cafe'} else None)
    return content


def build():
    sources, entries, current = {},[],None
    for line in (ROOT/'content/real-places.txt').read_text().splitlines():
        if not line or line.startswith('#'):continue
        if line.startswith('@'):
            current,url,publisher=line[1:].split('|')
            sources[current]={'url':url,'publisher':publisher,'researched_on':DATE,
                'scope':'place_and_activity_type_only','availability_verified':False,'price_verified':False}
            continue
        city,name,kind,focus=line.split('|')
        content=venue_content(city,name,kind,focus,sources[current])
        entries.append(dict(key=stable_key('place',city,name,kind),category=kind,source_ids=[current],
            availability_verified=False,price_verified=False,content=content))
    if len(entries)!=400:raise ValueError('Expected 400 researched venue experiences')
    config=None
    for line in (ROOT/'content/real-recipes.txt').read_text().splitlines():
        if not line or line.startswith('#'):continue
        if line.startswith('@'):
            config=line[1:].split('|');continue
        title,*steps=line.split('|')
        group,dimension,minutes,items,materials,tags,social,energy,mobility,cost=config
        content=base(title,steps,dimension,int(minutes),items.split(',') if items else [],materials,tags.split(','),social=='together',energy,mobility,cost)
        content['teaser']=f'{title}؛ با وسایل مشخص و سه مرحلهٔ عملی، در اندازه‌ای که به وقتت بخورد.'
        content['quiet_compatible']=False if group in {'music','movement','cards','groupgames'} else True
        if group in {'cooking','baking','snacks','dessert'}:
            if title=='پخت لبو در قابلمه':content['active_minutes']=120
            content['conditions_note']='فقط با مواد سالم، ابزار نام‌برده و مهارت پایه آشپزخانه اجرا کن؛ حساسیت غذایی و زمان واقعی پخت را در نظر بگیر. مواد مصرفی رایگان فرض نشده‌اند.'
            content['lighter_version']='نصف مقدار مواد را با حفظ پخت کامل آماده کن؛ اگر ابزار یا مواد را نداری، دستور دیگری انتخاب کن.'
            content['safety_notes']=['مواد حساسیت‌زا را بررسی کن؛ تخم‌مرغ و آرد خام را نچش و مواد لبنی و باقی‌مانده غذا را درست سرد نگه دار.']
            content['accessibility_note']='نیازمند کار با ابزار آشپزخانه و گاهی حرارت است؛ در صورت نیاز با همراه کمک‌کننده انجام بده.'
        if group=='garden':
            content['dramma']=alignment(dimension,'رسیدگی آهسته و ملموس به گیاه در گام‌های دوم و سوم، ریتم آرامی دارد؛ رشد گیاه یا بهبود حال تضمین نشده است.')
            # Some recipes need no plant, but keeping broad owned supplies avoids
            # promising unavailable seed/cutting; exact recipe names the extra item.
            content['materials_note']+=' بذر، قلمه یا پارچه ذکرشده در همان دستور هم باید از قبل موجود باشد.'
        if group=='cards' and 'حکم' in title:content.update(min_people=4,max_people=4)
        if group=='groupgames' and 'مافیای' in title:content.update(min_people=6,max_people=10)
        if group in {'paperbuild','sewing','yarn','printart'}:content['safety_notes']=['قیچی و سوزن را متناسب با توان دست استفاده کن و پس از کار دور از دسترس کودک جمع کن.']
        entries.append(dict(key=stable_key('home',group,title),category=group,source_ids=[],
            availability_verified=False,price_verified=False,content=content))
    if len(entries)!=700:raise ValueError('Expected exactly 700 distinct experiences')
    for entry in entries:
        entry['content']=Content.model_validate(entry['content']).model_dump(mode='json')
    if len({e['key'] for e in entries})!=700 or len({e['content']['title'] for e in entries})!=700:
        raise ValueError('Duplicate key/title')
    return dict(version=VERSION,researched_on=DATE,publication_basis='owner_request_2026_11_14',
        evidence_scope='editorial_research_not_live_availability_or_empirical_dramma_validation',sources=sources,entries=entries)


def main():
    catalog=build()
    write_release(catalog)
    rows=['# فهرست ۷۰۰ تفریح عملی','', 'گردآوری در ۲۳ آبان ۱۴۰۵؛ لینک‌ها معرفی مکان‌اند، نه تضمین سانس یا قیمت روز.','',
        '| ردیف | تفریح | شهر | منبع |','|---|---|---|---|']
    for index,entry in enumerate(catalog['entries'],1):
        c=entry['content'];p=c['place']
        rows.append(f"| {index} | {c['title']} | {p['city'] if p else 'در خانه'} | {'[معرفی محل]('+p['source_url']+')' if p else 'تألیفی؛ بی‌نیاز از مکان عمومی'} |")
    (ROOT/'content/real-catalog-index.md').write_text('\n'.join(rows)+'\n')
    export=ROOT/'exports/real-activities-700.csv';export.parent.mkdir(exist_ok=True)
    with export.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['key','title','city','source_url','primary_dimension','steps','materials','cost_kind'])
        for e in catalog['entries']:
            c=e['content'];p=c['place'] or {};writer.writerow([e['key'],c['title'],p.get('city',''),p.get('source_url',''),c['primary_dimension'],'\n'.join(c['steps']),c['materials_note'],c['cost']['kind']])
    cities=sorted({e['content']['place']['city'] for e in catalog['entries'] if e['content']['place']})
    (ROOT/'apps/web/lib/activity-cities.json').write_text(json.dumps(cities,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'entries':len(catalog['entries']),'venue_entries':400,'home_entries':300,'cities':len(cities),
        'sources':len(catalog['sources']),'dimensions':Counter(e['content']['primary_dimension'] for e in catalog['entries'])},ensure_ascii=False))

if __name__=='__main__':main()
