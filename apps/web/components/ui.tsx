import type {ButtonHTMLAttributes, ReactNode} from 'react';
import Icon from './Icon';

export function Button({children, secondary, className = '', ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {secondary?: boolean}) {
  return <button className={`${secondary ? 'button-secondary' : 'button-primary'} ${className}`} {...props}>{children}</button>;
}
export function Choices<T extends string | number>({legend, value, options, onChange, hint, disabledValues}: {
  legend: string; value: T | null; options: readonly (readonly [T, string])[]; onChange: (v: T) => void; hint?: string;
  disabledValues?: readonly T[];
}) {
  return <fieldset className="field"><legend>{legend}</legend>{hint && <p className="hint">{hint}</p>}
    <div className="choices">{options.map(([key, label]) => <label className="choice" key={key}>
      <input type="radio" name={legend} value={key} checked={value === key} disabled={disabledValues?.includes(key)} onChange={() => onChange(key)} /><span>{label}</span>
    </label>)}</div></fieldset>;
}
export function Empty({title, children}: {title: string; children: ReactNode}) {
  return <div className="empty-state"><span className="empty-mark"><Icon name="leaf" size={32}/></span><h2>{title}</h2>{children}</div>;
}
export function Note({children}: {children: ReactNode}) {return <p className="soft-note">{children}</p>;}
