// Public labels for the existing taxonomy_v1 API values.
export const itemOptions = [
  ['paper','کاغذ'], ['pen','قلم'], ['phone','گوشی'], ['internet','اینترنت'],
  ['book','کتاب'], ['playing_cards','ورق بازی'], ['board_game','بازی رومیزی'],
  ['colored_pencils','مدادرنگی'], ['ball','توپ'], ['kitchen','آشپزخانه'],
  ['food_ingredients','مواد غذایی'], ['headphones','هدفون'],
] as const;

export const interestOptions = [
  ['games','بازی'], ['puzzles','معما'], ['drawing','نقاشی'], ['music','موسیقی'],
  ['storytelling','قصه و نمایش'], ['photography','عکاسی'], ['reading','کتاب'],
  ['craft','ساختنی'], ['nature','طبیعت'], ['humor','طنز'], ['dance','رقص و حرکت'],
  ['walking','قدم‌زدن'], ['food','خوراکی و آشپزی'], ['culture','گشت فرهنگی'],
] as const;

export const goalOptions = [
  ['any','غافلگیرم کن'], ['unwind','یه مکث آروم'], ['switch_off','فاصله از روزمرگی'],
  ['learn','یه چالش کوچیک'], ['connect','وقت مشترک'], ['meaning','یه چیز موندنی'],
  ['choose','یه کار به سلیقهٔ خودم'],
] as const;

export const needNowOptions = [
  ['switch_off','فاصله از فکر کار و روزمرگی'], ['unwind','استراحت و آرامش'],
  ['choose','وقت و آزادی برای خودم'], ['learn','چالش و کشف چیز تازه'],
  ['meaning','یه وقت باارزش و به‌یادموندنی'], ['connect','همراهی و هم‌صحبتی'],
  ['any','مطمئن نیستم'],
] as const;

export const outcomeOptions = [
  ['switch_off','ذهنم از کارهای روزمره فاصله بگیره'], ['unwind','یه مکث آروم داشته باشم'],
  ['choose','یه کار کاملاً به سلیقهٔ خودم کرده باشم'], ['learn','یه چیز تازه کشف کرده باشم'],
  ['meaning','یه چیز کوچیک و موندنی بسازم'], ['connect','یه لحظهٔ خوب با همراه‌هام بسازم'],
  ['any','فرقی نداره؛ غافلگیرم کن'],
] as const;
