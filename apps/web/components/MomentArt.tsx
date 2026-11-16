import {useId} from 'react';

export default function MomentArt({variant = 0}: {variant?: number}) {
  const id = useId().replace(/:/g, '');
  const kind = variant % 3;
  return <svg className={`moment-art art-${kind}`} viewBox="0 0 360 220" fill="none" aria-hidden="true">
    <defs>
      <linearGradient id={`${id}-bg`} x1="20" y1="0" x2="340" y2="220" gradientUnits="userSpaceOnUse"><stop stopColor={['#e0efe6','#eee8fa','#f8edda'][kind]}/><stop offset="1" stopColor={['#f1f5eb','#f7f1fb','#fbf4e9'][kind]}/></linearGradient>
      <linearGradient id={`${id}-object`} x1="120" y1="55" x2="235" y2="185" gradientUnits="userSpaceOnUse"><stop stopColor={['#73a78b','#ac9aca','#e0ae6a'][kind]}/><stop offset="1" stopColor={['#2b6450','#78669a','#ac7741'][kind]}/></linearGradient>
      <filter id={`${id}-shadow`} x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    </defs>
    <rect width="360" height="220" rx="24" fill={`url(#${id}-bg)`}/>
    <circle cx="284" cy="52" r="63" fill="white" fillOpacity=".28"/>
    <circle cx="48" cy="210" r="95" fill="white" fillOpacity=".2"/>
    <ellipse cx="183" cy="187" rx="64" ry="8" fill={['#2e5f46','#6e5794','#9f6c35'][kind]} opacity=".14" filter={`url(#${id}-shadow)`}/>
    {kind === 0 && <>
      <path d="M150 140h66l-7 42q-24 12-51 0l-8-42Z" fill="#f8faf3"/><ellipse cx="183" cy="140" rx="33" ry="9" fill="#d2dccc"/><ellipse cx="183" cy="140" rx="24" ry="5" fill="#788671"/>
      <path d="M183 142V67m0 49c-36 0-51-18-49-44 31 0 49 17 49 44Z" fill={`url(#${id}-object)`}/><path d="M183 95c0-29 19-46 47-45 3 26-13 47-47 45Z" fill="#7aa68a"/><path d="M183 142V72m0 42-34-26m34 5 31-28" stroke="#365f4b" strokeWidth="2" strokeLinecap="round"/>
      <path d="M112 157h25v23h-25q-6-10 0-23Z" fill="#d5af85"/><path d="M137 161h5a6 6 0 0 1 0 12h-5" stroke="#c19970" strokeWidth="3"/><path d="M120 145q-4-6 0-12" stroke="#b59d83" strokeWidth="2" strokeLinecap="round"/>
    </>}
    {kind === 1 && <>
      <path d="M131 129V102a52 52 0 0 1 104 0v27" stroke="#c9bada" strokeWidth="14"/><path d="M135 125v-23a48 48 0 0 1 96 0v23" stroke="#f7f2fb" strokeWidth="5"/>
      <rect x="123" y="115" width="29" height="62" rx="14.5" fill={`url(#${id}-object)`}/><rect x="214" y="115" width="29" height="62" rx="14.5" fill={`url(#${id}-object)`}/><rect x="144" y="123" width="13" height="47" rx="6.5" fill="#e2d7ec"/><rect x="209" y="123" width="13" height="47" rx="6.5" fill="#e2d7ec"/>
      <path d="M174 117v27m9-37v47m9-37v27" stroke="#ac98bf" strokeWidth="4" strokeLinecap="round"/><path d="M88 82v13m-6-6h12m169 60v10m-5-5h10" stroke="#b7a8c8" strokeWidth="2" strokeLinecap="round"/>
    </>}
    {kind === 2 && <>
      <rect x="108" y="52" width="145" height="135" rx="8" transform="rotate(-7 108 52)" fill="#e9d5b8"/><rect x="115" y="43" width="145" height="135" rx="8" transform="rotate(3 115 43)" fill="#fffdf7"/>
      <path d="M137 141c13-31 30 9 38-13s15-41 28-28c16 17 29 9 30-8M140 92q15-29 37-18" stroke="#b08964" strokeWidth="2.5" strokeLinecap="round"/><circle cx="214" cy="74" r="9" stroke="#d6b27b" strokeWidth="2"/>
      <path d="m254 91-35 71-9 7 1-12 35-71 8 5Z" fill={`url(#${id}-object)`}/><path d="m211 157 8 5-9 7 1-12Z" fill="#4c5550"/>
    </>}
    <path d="M278 142v10m-5-5h10M81 55v6m-3-3h6" stroke={['#86a18b','#b3a0c3','#c4a67c'][kind]} strokeWidth="1.5" strokeLinecap="round"/>
  </svg>;
}
