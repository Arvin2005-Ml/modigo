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

export const activityIntentOptions = [
  ['unwind','یه مکث آروم'], ['switch_off','یه فاصله از روزمرگی'],
  ['learn','یه چالش یا کشف تازه'], ['connect','یه وقت خوب با همراه'],
  ['meaning','یه تجربهٔ موندنی'], ['choose','یه کار به سلیقهٔ خودم'],
  ['any','فرقی نداره'],
] as const;
