import type {CSSProperties} from 'react';

export type IconName = 'spark' | 'arrow' | 'bookmark' | 'journey' | 'user' | 'download' | 'close' | 'check' | 'clock' | 'leaf' | 'sun' | 'shuffle' | 'shield' | 'wifi' | 'heart' | 'coffee' | 'headphones' | 'plus';
const paths: Record<IconName, React.ReactNode> = {
  spark: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6L20 2Z"/></>,
  arrow: <path d="M20 12H4m6-6-6 6 6 6"/>,
  bookmark: <path d="M7 3.5h10a1 1 0 0 1 1 1v16l-6-4-6 4v-16a1 1 0 0 1 1-1Z"/>,
  journey: <><path d="M6 19c0-5 12-2 12-8 0-4-7-2-7-6"/><circle cx="6" cy="20" r="2"/><circle cx="11" cy="4" r="2"/></>,
  user: <><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  check: <path d="m5 12 4.5 4.5L19 7"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  leaf: <><path d="M5 19C-1 9 10 3 21 3c0 12-6 21-16 16ZM5 19l10-10"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
  shuffle: <><path d="M20 8a8 8 0 0 0-14-2L3 9m0-6v6h6M4 16a8 8 0 0 0 14 2l3-3m0 6v-6h-6"/></>,
  shield: <><path d="m12 3 8 3v5c0 5-5 8.5-8 10-3-1.5-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/></>,
  wifi: <><path d="M3 8a15 15 0 0 1 18 0M6 12a10 10 0 0 1 12 0M9 16a5 5 0 0 1 6 0M3 3l18 18"/><circle cx="12" cy="20" r=".7"/></>,
  heart: <path d="M12 21 3.5 12.5a5.5 5.5 0 0 1 8-7.5l.5.5.5-.5a5.5 5.5 0 0 1 8 7.5L12 21Z"/>,
  coffee: <><path d="M4 8h13v8a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8Zm13 1h2a3 3 0 0 1 0 6h-2M7 2v2m5-2v2"/></>,
  headphones: <><path d="M4 14V11a8 8 0 0 1 16 0v3M4 12H3v7h4v-7H4Zm16 0h1v7h-4v-7h3Z"/></>,
  plus: <path d="M12 5v14M5 12h14"/>
};

// Original project icons. Kept local, with a consistent 24px grid.
export default function Icon({name, size = 22, className = '', style}: {name: IconName; size?: number; className?: string; style?: CSSProperties}) {
  return <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name]}</svg>;
}
