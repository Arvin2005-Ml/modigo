"""Build the authored short-activity release; all plans require no purchased materials."""
from app.modules.catalog.unified import release, write_release
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Each row is an independent activity, not the same activity copied across venues.
ROWS = [
('home','بازی ضرب‌آهنگ با کف دست','play','mastery','یک الگوی کوتاه ضربه را بساز و تغییر بده.','دو ضربه آرام روی کف دست بزن.','الگو را با مکث یا جابه‌جایی دست‌ها عوض کن.','الگوی تازه را چند بار تکرار کن و یکی را انتخاب کن.'),
('home','پانتومیم اشیای خانه','games','detachment','بدون حرف‌زدن کاربرد یک وسیله را با حرکت نشان بده.','حرکت استفاده از یک وسیله را انتخاب کن.','بدون برداشتن وسیله حرکت را آرام اجرا کن.','یک وسیله دیگر انتخاب کن؛ همراهان می‌توانند حدس بزنند.'),
('home','بازی تعادل دست‌ها','play','mastery','حرکت‌های کوچک دست را با ترتیب دلخواه تمرین کن.','کف یک دست را باز و دست دیگر را مشت کن.','آرام جای دست باز و بسته را عوض کن.','سرعت و ترتیب را به اندازه راحتی خودت تغییر بده.'),
('home','تئاتر انگشتی کوتاه','storytelling','detachment','با انگشت‌ها یک صحنه کوتاه و بازیگوشانه بساز.','دو انگشت را به جای دو شخصیت انتخاب کن.','با حرکت دست‌ها دیدار کوتاهی میان آن‌ها اجرا کن.','پایان صحنه را با یک حرکت تازه عوض کن.'),
('home','رقص نشسته دست‌ها','movement','autonomy','یک حرکت نشسته و کوتاه با دست‌ها طراحی کن.','در وضعیت راحت بنشین و دست‌ها را روی پا بگذار.','دو حرکت آرام دست را به ترتیب دلخواه انجام بده.','ترتیب حرکت‌ها را عوض کن و هر وقت خواستی متوقف شو.'),
('home','بازی شکل‌سازی با انگشت‌ها','creativity','mastery','با دست‌ها شکل بساز و شکل تازه‌ای امتحان کن.','با انگشت‌ها یک دایره یا مثلث بساز.','شکل را آرام به شکل دیگری تبدیل کن.','یک ترکیب تازه پیدا کن و چند بار بساز.'),
('outdoor','کشف بافت‌های دیدنی فضای باز','discovery','detachment','در جای امن، تفاوت بافت‌های اطراف را پیدا کن.','در محل امن و مجاز از قبل در دسترس بمان.','سه بافت متفاوت مانند آجر، برگ یا سنگ را از دور پیدا کن.','یکی را انتخاب کن و طرح‌های ریز آن را بررسی کن.'),
('outdoor','شکار شکل‌ها در محیط باز','games','mastery','با نگاه‌کردن شکل‌های هندسی را در اطراف پیدا کن.','در یک جای امن و مجاز قرار بگیر.','یک دایره و یک خط شکسته در محیط پیدا کن.','شکل دیگری انتخاب کن و نمونه‌اش را پیدا کن.'),
('outdoor','بازی سایه‌های موجود','play','detachment','طرح سایه‌های موجود را در محیط کشف کن.','در جای امنی که از قبل در دسترس است قرار بگیر.','یک سایه موجود روی زمین یا دیوار پیدا کن.','مرز و شکل آن را دنبال کن و سایه متفاوتی پیدا کن.'),
('outdoor','ردیابی رنگ در فضای باز','discovery','autonomy','رنگی انتخاب کن و چند نمونه آن را پیدا کن.','در محل امن و مجاز خودت بمان.','یک رنگ دلخواه انتخاب کن و دو نمونه از آن ببین.','رنگ دیگری انتخاب کن و نمونه‌هایش را مقایسه کن.'),
('outdoor','تماشای حرکت محیط','observation','relaxation','چند حرکت آرام محیط را از جای امن تماشا کن.','جایی امن و در دسترس برای توقف انتخاب کن.','حرکتی مانند برگ، ابر یا رفت‌وآمد دوردست پیدا کن.','چند لحظه حرکت را دنبال کن و سپس حرکت دیگری ببین.'),
('indoor_public','بازی پیدا کردن الگو در ساختمان','games','mastery','طرح‌های تکراری یک فضای عمومی در دسترس را پیدا کن.','در فضای مجاز و در دسترس فعلی خود بمان.','یک طرح تکراری روی دیوار یا کف پیدا کن.','تعداد یا ترتیب تکرار آن را بررسی کن.'),
('indoor_public','کشف جزئیات معماری','culture','detachment','یک جزئیات معماری را از جای خودت کشف کن.','در محل مجاز و در دسترس فعلی توقف کن.','یک در، پنجره یا نقش معماری انتخاب کن.','دو جزئیات متفاوت آن را پیدا و با هم مقایسه کن.'),
('indoor_public','بازی رنگ‌ها در فضای سرپوشیده','play','autonomy','در محیط سرپوشیده چند نمونه از رنگ دلخواهت پیدا کن.','در محل مجاز فعلی خودت بمان.','یک رنگ انتخاب کن و دو نمونه آن را در فضا پیدا کن.','رنگ دیگری انتخاب کن و نمونه‌های متفاوتش را ببین.'),
('indoor_public','کشف شکل‌های اطراف','discovery','mastery','شکل‌های متفاوت را در فضای سرپوشیده پیدا کن.','در یک نقطه مجاز و در دسترس بمان.','یک شکل گرد و یک شکل گوشه‌دار پیدا کن.','شکل سومی انتخاب کن و نمونه‌ای از آن را ببین.'),
('indoor_public','بازی ترکیب نقش‌ها','creativity','detachment','از نقش‌های موجود در فضا یک ترکیب دیداری بساز.','در جای مجاز فعلی خود بنشین یا بایست.','دو نقش یا بافت متفاوت را در اطراف پیدا کن.','ترتیب دلخواهی برای کنار هم دیدن آن‌ها انتخاب کن.'),
]

def build():
    entries=[]
    for i,(venue,title,tag,dimension,teaser,s1,s2,s3) in enumerate(ROWS,1):
        content=dict(title=title,teaser=teaser,first_step=s1,steps=[s1,s2,s3],
            lighter_version='فقط یک دور کوتاه را با سرعت خودت انجام بده و هر زمان خواستی متوقف شو.',
            materials_note='وسیله یا خریدی لازم نیست.',
            accessibility_note='نشسته هم قابل انجام است؛ وضعیت بدن و دامنه حرکت را با راحتی خودت تنظیم کن.',
            conditions_note=('در محیط فعلیِ امن، مجاز و از قبل در دسترس انجام بده؛ برای ورود یا رفت‌وآمد برنامه‌ریزی نشده است.' if venue!='home' else 'در فضای امن خانه و با رعایت راحتی خودت انجام بده.'),
            requires_venue_check=False,place=None,primary_dimension=dimension,secondary_dimensions=[],
            dramma={'version':'dramma_v1','mechanisms':[{'dimension':dimension,'intent':{'mastery':'با آزمودن و تغییر دادن الگو، مهارت را در مقیاس کوچک تمرین می‌کنی.','detachment':'با تمرکز بر بازی یا جزئیات محیط از کار جاری فاصله می‌گیری.','autonomy':'با انتخاب آزادانه حرکت یا موضوع، شکل تجربه را خودت تعیین می‌کنی.','relaxation':'تماشای آرام و بدون عجله فرصتی کوتاه برای استراحت فراهم می‌کند.'}[dimension],'step_indexes':[2,3]}]},
            tags=[tag],active_minutes=5,setup_minutes=0,travel_minutes=0,energy_required='low',mobility_required='seated',
            supported_social_modes=['solo','together'],min_people=1,max_people=12,venue=venue,required_items=[],
            requires_async_contact=False,step_free=True,quiet_compatible=True,weather_requirement='any',daylight_requirement='any',
            cost={'kind':'free','min_toman':0,'max_toman':0,'basis':'per_group','verified_at':None,'valid_until':None,'note':'بدون خرید؛ در مکان عمومیِ از قبل در دسترس.' if venue!='home' else 'بدون خرید و بدون وسیله.'},safety_notes=['فقط در شرایط امن و راحت خودت انجام بده.'])
        entries.append({'key':f'real:short-{i:03}', 'category':'short', 'availability_verified':False,'price_verified':False,'source_ids':[],'content':content})
    return {'version':'short_activities_v1','researched_on':'2026-11-14','publication_basis':'owner_requested_authored_short_activities','evidence_scope':'authored activity; no venue or live availability claim','sources':{},'entries':entries}

if __name__=='__main__':
    from app.modules.catalog.schemas import Content
    data=build()
    for e in data['entries']: Content.model_validate(e['content'])
    write_release(data)
    print(f"Built {len(data['entries'])} authored activities")
