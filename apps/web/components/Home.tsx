import {Button} from './ui';
import Icon from './Icon';
import MomentArt from './MomentArt';

export default function Home({start}: {start: () => void}) {
  return <>
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <span className="hero-badge"><span className="status-dot"/>وقتِ یک حال‌وهوای تازه‌ست</span>
        <h1 id="hero-title"><span className="hero-title-wide">یه کم از روزمرگی فاصله بگیر.</span><span className="hero-title-small">یه فاصله از روزمرگی.</span><br/><em>این چند دقیقه، برای تو.</em></h1>
        <p>وقت آزادت هرقدر که باشه، یه چیزی هست که بهت بچسبه.<br className="desktop-break"/> با چند سؤال کوتاه، پیداش می‌کنیم.</p>
        <div className="hero-actions"><Button onClick={start}>ببینیم چی می‌چسبه <Icon name="arrow" size={20}/></Button><a className="how-link" href="#how-it-works">فانیلو چطور کار می‌کنه؟ <span aria-hidden="true">↙</span></a></div>
        <div className="hero-reassurance"><span><Icon name="clock" size={15}/>کمتر از یک دقیقه سؤال</span><span><Icon name="leaf" size={15}/>با ریتم خودت، بدون فشار</span></div>
      </div>
      <div className="moment-showcase">
        <div className="showcase-orbit" aria-hidden="true"/>
        <span className="floating-note note-right"><Icon name="sun" size={18}/> یه مکث کوچیک، وسط روز</span>
        <div className="preview-cards">
          {[{title:'یه نقاشی با یه خط بکش',subtitle:'یه چیز تازه، با سلیقهٔ خودت',time:'۱۵',variant:2},{title:'یه مکث آروم، همین‌جا',subtitle:'چند دقیقه فقط برای خودت',time:'۱۰',variant:0},{title:'صدای خونه رو پیدا کن',subtitle:'یه فاصلهٔ کوتاه از شلوغی‌ها',time:'۵',variant:1}].map((item,i)=><article className={`preview-card preview-${i}`} key={item.title}>
            <MomentArt variant={item.variant}/><div className="preview-card-copy"><span className="preview-category">{['کمی خلاقیت','وقتِ خودت','یه حال‌وهوای تازه'][i]}</span><h2>{item.title}</h2><p>{item.subtitle}</p><div className="preview-card-bottom"><span><Icon name="clock" size={14}/>{item.time} دقیقه <span className="meta-separator">·</span> رایگان</span><span className="preview-arrow"><Icon name="arrow" size={17}/></span></div></div>
          </article>)}
        </div>
        <span className="floating-note note-left"><Icon name="heart" size={17}/> قرار نیست کار بزرگی باشه</span>
        <p className="showcase-caption">چند نمونه از حال‌وهوای فانیلو؛ انتخاب‌های تو با شرایطت جور می‌شن.</p>
      </div>
    </section>
    <section className="how-section" id="how-it-works" aria-labelledby="how-title"><span className="eyebrow">به همین سادگی</span><h2 id="how-title">از «چی کار کنم؟» تا یه وقتِ خوب.</h2><div className="how-grid">
      <article><span className="how-number">۰۱</span><h3>از الانت بگو</h3><p>چقدر وقت داری، کجایی و چه حال‌وهوایی داری؟ همین چندتا سؤال.</p></article>
      <article><span className="how-number">۰۲</span><h3>پیشنهادت رو ببین</h3><p>یک پیشنهاد متناسب می‌بینی؛ اگه نچسبید، تا شش بار عوضش کن.</p></article>
      <article><span className="how-number">۰۳</span><h3>این وقت رو مال خودت کن</h3><p>شروع کن و هر وقت برات کافی بود، تمومش کن. بدون عجله.</p></article>
    </div></section>
    <section className="home-invitation"><div><Icon name="spark" size={28}/><h2>لازم نیست روز خاصی باشه.</h2><p>همین حالا هم می‌شه یه وقت کوچیک برای خودت ساخت.</p></div><Button onClick={start}>وقتِ خودمه <Icon name="arrow" size={19}/></Button></section>
  </>;
}
