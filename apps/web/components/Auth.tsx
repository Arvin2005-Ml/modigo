import { useState } from "react";
import type { FormEvent } from "react";

import type { AuthMode } from "@/lib/navigation";
import { Button, Note } from "./ui";
import Icon from "./Icon";

type Props = {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  busy: boolean;
  login: (email: string, password: string) => void;
  signup: (email: string, password: string, name: string) => Promise<void>;
  forgot: (email: string) => Promise<boolean>;
  reset: (password: string) => void;
  resetToken: boolean;
};

export default function Auth({
  mode,
  onModeChange,
  busy,
  login,
  signup,
  forgot,
  reset,
  resetToken,
}: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [sent, setSent] = useState(false);

  const setMode = (next: AuthMode) => {
    setSent(false);
    onModeChange(next);
  };

  const title = sent
    ? "یه سر به صندوق محلی بزن"
    : resetToken
      ? "یه رمز تازه انتخاب کن."
      : mode === "login"
        ? "خوش اومدی."
        : mode === "forgot"
          ? "رمزت یادت نیست؟"
          : "اینجا، به خودت وقت بده.";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (resetToken) {
      reset(password);
      return;
    }

    if (mode === "login") {
      login(email, password);
      return;
    }

    if (mode === "forgot") {
      if (await forgot(email)) {
        setSent(true);
      }
      return;
    }

    await signup(email, password, name);
  };

  return (
    <div className="auth-layout">
      <div className="auth-welcome" aria-hidden="true">
        <span className="welcome-symbol">
          <Icon name="spark" size={74} />
        </span>

        <h2>
          خوش اومدی
          <br />
          به وقتِ خودت.
        </h2>

        <p>
          یه گوشهٔ آروم برای پیدا کردن
          <br />
          چیزهایی که بهت می‌چسبن.
        </p>

        <span className="welcome-footnote">کمتر باید. بیشتر دلت می‌خواد.</span>
      </div>

      <section className="auth-column">
        <span className="eyebrow">یه جای کوچیک برای وقت‌های خودت</span>

        <h1>{title}</h1>

        {sent ? (
          <>
            <p className="intro">
              اگه این نشانی قابل استفاده باشه، لینک راهنما می‌رسه.
            </p>

            <Note>
              در اجرای محلی، ایمیل‌ها در صندوق توسعه‌اند. اپراتور پروژه می‌تونه
              لینک رو از کنسول محلی بگیره.
            </Note>

            <Button onClick={() => setMode("login")}>برم صفحهٔ ورود</Button>
          </>
        ) : (
          <>
            <p className="intro">
              {resetToken
                ? "با نگه‌داشتن رمز تازه، نشست‌های قبلی بسته می‌شن."
                : mode === "login"
                  ? "وارد شو تا تجربه‌ها و انتخاب‌هات یه جا بمونن."
                  : mode === "forgot"
                    ? "نشانی حسابت رو بنویس تا لینک راهنما برسه."
                    : "فقط یه ایمیل و رمز؛ بعدش می‌ریم سراغ وقت آزادت."}
            </p>

            {!resetToken && mode !== "forgot" && (
              <div
                className="auth-segments"
                role="group"
                aria-label="ورود یا ساخت حساب"
              >
                <button
                  type="button"
                  aria-pressed={mode === "login"}
                  disabled={busy}
                  onClick={() => setMode("login")}
                >
                  ورود به حساب
                </button>

                <button
                  type="button"
                  aria-pressed={mode === "signup"}
                  disabled={busy}
                  onClick={() => setMode("signup")}
                >
                  ساخت حساب
                </button>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {mode === "signup" && !resetToken && (
                <label className="label">
                  چی صدات کنیم؟
                  <span className="muted">اختیاری</span>
                  <input
                    className="input"
                    value={name}
                    maxLength={60}
                    autoComplete="nickname"
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
              )}

              {!resetToken && (
                <label className="label">
                  ایمیل
                  <input
                    className="input ltr"
                    type="email"
                    required
                    value={email}
                    maxLength={254}
                    autoComplete="email"
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
              )}

              {(mode !== "forgot" || resetToken) && (
                <label className="label">
                  {resetToken ? "رمز تازه" : "رمز عبور"}

                  <input
                    className="input ltr"
                    type="password"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete={
                      mode === "login" && !resetToken
                        ? "current-password"
                        : "new-password"
                    }
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />

                  <span className="hint">
                    ۱۲ تا ۱۲۸ نویسه؛ فاصله و عبارت بلند هم مجازه.
                  </span>
                </label>
              )}

              {mode === "signup" && !resetToken && (
                <label className="check-label">
                  <input type="checkbox" required />
                  ۱۸ سالم شده و می‌خوام حساب بسازم.
                </label>
              )}

              <Button className="w-full" disabled={busy} type="submit">
                {busy
                  ? "یه لحظه…"
                  : resetToken
                    ? "رمز تازه رو نگه دار"
                    : mode === "login"
                      ? "وارد بشم"
                      : mode === "forgot"
                        ? "لینک راهنما رو بفرست"
                        : "حساب بسازم"}
              </Button>
            </form>

            {!resetToken && mode !== "forgot" && (
              <p className="auth-switch">
                {mode === "login" ? "بار اوله میای؟" : "از قبل حساب داری؟"}{" "}
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => setMode(mode === "login" ? "signup" : "login")}
                >
                  {mode === "login" ? "یه حساب بساز" : "وارد شو"}
                </button>
              </p>
            )}

            {!resetToken && mode === "login" && (
              <div className="text-center">
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => setMode("forgot")}
                >
                  رمزم یادم نیست
                </button>
              </div>
            )}

            {!resetToken && mode === "forgot" && (
              <button
                className="text-button"
                disabled={busy}
                onClick={() => setMode("login")}
              >
                بازگشت به ورود
              </button>
            )}
          </>
        )}
      </section>
    </div>
  );
}
