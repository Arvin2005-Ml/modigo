"""Build hand-authored solo and shared experiences with explicit DRAMMA steps."""
from app.modules.catalog.unified import release, write_release
import json
from pathlib import Path
from app.modules.catalog.schemas import Content

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'everyday_activities_v1'

def build():
    entries=[]
    for line in (ROOT/'content/everyday-activities.txt').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        key,dimension,minutes,items,tag,quiet,title,teaser,s1,s2,s3=line.split('|')
        group=key.startswith('group-')
        required=items.split(',') if items else []
        people_max=2 if key in ('group-002','group-019','group-021','group-022','group-026') else 12 if group else 1
        intent={
            'mastery':'با تمرین، ساختن یا حل کردن، یک مهارت کوچک را به کار می‌بری.',
            'autonomy':'با انتخاب و تغییر طرح یا شیوه اجرا، تجربه را خودت شکل می‌دهی.',
            'detachment':'با درگیر شدن در خواندن یا ساختن، مدتی از کار جاری فاصله می‌گیری.',
            'relaxation':'با گوش دادن در زمانی کوتاه فرصتی برای استراحت فراهم می‌شود.',
            'meaning':'با ثبت یک خاطره ارزشمند به چیزی که برایت مهم است توجه می‌کنی.',
            'affiliation':'با نوبت‌گرفتن و مشارکت در انجام فعالیت، همراهان در تجربه مشترک سهیم می‌شوند.',
        }[dimension]
        minutes=int(minutes)
        conditions='در فضای امن خانه و با وسایل موجود انجام بده.'
        if key=='solo-018': conditions+=' یک قطعه موسیقی از قبل در دسترس لازم است.'
        if key=='group-023': conditions+=' فقط در محدوده امن و در دسترس خانه انجام بده.'
        content=dict(title=title,teaser=teaser,first_step=s1,steps=[s1,s2,s3],
            lighter_version='بخشی از فعالیت را با سرعت و مدت دلخواه انجام بده و هر زمان خواستی متوقف شو.',
            materials_note='وسایل مورد نیاز از قبل در دسترس باشند؛ خرید لازم نیست.' if required else 'وسیله یا خریدی لازم نیست.',
            accessibility_note='نشسته و در سطح در دسترس انجام‌پذیر است؛ اگر اجرای گام‌ها برایت راحت نیست، متوقف شو.',
            conditions_note=conditions,requires_venue_check=False,place=None,
            primary_dimension=dimension,secondary_dimensions=[],
            dramma={'version':'dramma_v1','mechanisms':[{'dimension':dimension,'intent':intent,'step_indexes':[2,3]}]},
            tags=[tag],active_minutes=minutes-2 if required else minutes,setup_minutes=2 if required else 0,
            travel_minutes=0,energy_required='low',mobility_required='light' if key=='group-023' else 'seated',
            supported_social_modes=['together'] if group else ['solo'],min_people=2 if group else 1,max_people=people_max,
            venue='home',required_items=required,requires_async_contact=False,step_free=None if key=='group-023' else True,
            quiet_compatible=(quiet=='yes'),weather_requirement='any',daylight_requirement='any',
            cost={'kind':'free','min_toman':0,'max_toman':0,'basis':'per_group','verified_at':None,'valid_until':None,
                  'note':'بدون خرید؛ با وسایل موجود.'},safety_notes=['فعالیت را با وسایل امن و مناسب خود انجام بده.'])
        entries.append({'key':'real:everyday-'+key,'category':'shared' if group else 'solo',
            'source_ids':[],'availability_verified':False,'price_verified':False,
            'content':Content.model_validate(content).model_dump(mode='json')})
    if len(entries)!=60 or len({e['key'] for e in entries})!=len(entries):
        raise ValueError('Expected 60 unique activities')
    return {'version':VERSION,'researched_on':'2026-11-14','publication_basis':'owner_requested_authored_activities',
            'evidence_scope':'authored activity; no venue or live availability claim','sources':{},'entries':entries}

if __name__=='__main__':
    data=build()
    write_release(data)
    print(f"Built {len(data['entries'])} activities")
