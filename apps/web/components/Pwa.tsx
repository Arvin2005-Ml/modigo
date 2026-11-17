"use client";

import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { Button } from "./ui";

interface InstallPrompt extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function Pwa() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(false);
  const [offline, setOffline] = useState(false);
  const [ios, setIos] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const display = window.matchMedia("(display-mode: standalone)");
    const syncDisplay = () =>
      setInstalled(
        display.matches ||
          Boolean(
            (navigator as Navigator & { standalone?: boolean }).standalone,
          ),
      );
    const syncNetwork = () => setOffline(!navigator.onLine);
    const beforeInstall = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    };
    const afterInstall = () => {
      setInstalled(true);
      setPrompt(null);
      dialog.current?.close();
    };
    syncDisplay();
    syncNetwork();
    display.addEventListener("change", syncDisplay);
    window.addEventListener("online", syncNetwork);
    window.addEventListener("offline", syncNetwork);
    window.addEventListener("beforeinstallprompt", beforeInstall);
    window.addEventListener("appinstalled", afterInstall);
    if (
      process.env.NODE_ENV === "production" &&
      "serviceWorker" in navigator &&
      window.isSecureContext
    ) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .catch(() => {
          // Installation help still works when a browser disallows service workers.
          setMessage(
            "مرورگرت فعلاً دسترسی آفلاین رو فعال نکرده؛ مودیگو با اینترنت در دسترسه.",
          );
        });
    }
    return () => {
      display.removeEventListener("change", syncDisplay);
      window.removeEventListener("online", syncNetwork);
      window.removeEventListener("offline", syncNetwork);
      window.removeEventListener("beforeinstallprompt", beforeInstall);
      window.removeEventListener("appinstalled", afterInstall);
    };
  }, []);

  const install = async () => {
    if (!prompt || installing) return;
    setInstalling(true);
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      setPrompt(null);
      if (choice.outcome === "accepted") dialog.current?.close();
    } catch {
      setMessage("نصب انجام نشد؛ از منوی مرورگرت دوباره امتحان کن.");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <>
      {!installed && (
        <button
          className="install-button"
          onClick={() => {
            setIos(
              /iPhone|iPad|iPod/.test(navigator.userAgent) ||
                (navigator.platform === "MacIntel" &&
                  navigator.maxTouchPoints > 1),
            );
            dialog.current?.showModal();
          }}
          aria-label="نصب مودیگو روی دستگاه"
        >
          <Icon name="download" size={18} />
          <span>نصب برنامه</span>
        </button>
      )}
      {offline && (
        <div className="offline-notice" role="status">
          <Icon name="wifi" size={18} />
          <span>
            اینترنت قطع شده؛ برای دریافت پیشنهاد و ثبت تجربه دوباره وصل شو.
          </span>
        </div>
      )}
      <dialog
        ref={dialog}
        className="install-dialog"
        aria-labelledby="install-title"
        aria-describedby="install-description"
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        <button
          autoFocus
          className="icon-button dialog-close"
          onClick={() => dialog.current?.close()}
          aria-label="بستن راهنمای نصب"
        >
          <Icon name="close" />
        </button>
        <span className="install-logo">
          <Icon name="spark" size={38} />
        </span>
        <span className="eyebrow">همیشه دمِ دستت</span>
        <h2 id="install-title">یه جا برای مودیگو، روی صفحه‌ات.</h2>
        <p id="install-description">
          مودیگو رو به صفحهٔ اصلی اضافه کن تا با یه لمس برگردی به وقتِ خودت.
        </p>
        {prompt ? (
          <Button className="w-full" disabled={installing} onClick={install}>
            <Icon name="download" size={19} />
            {installing ? "در حال نصب…" : "نصب مودیگو"}
          </Button>
        ) : (
          <ol className="install-instructions">
            {(ios
              ? [
                  "مودیگو رو در مرورگر Safari باز کن.",
                  "دکمهٔ اشتراک‌گذاری (Share) رو بزن.",
                  "افزودن به صفحهٔ اصلی (Add to Home Screen) رو انتخاب کن.",
                ]
              : [
                  "منوی مرورگرت رو باز کن.",
                  "نصب برنامه (Install app) یا افزودن به صفحهٔ اصلی رو انتخاب کن.",
                  "اگه این گزینه رو ندیدی، مودیگو رو در Chrome یا Edge باز کن.",
                ]
            ).map((text, i) => (
              <li key={text}>
                <span>{new Intl.NumberFormat("fa-IR").format(i + 1)}</span>
                {text}
              </li>
            ))}
          </ol>
        )}
        {message && (
          <p className="hint" role="status">
            {message}
          </p>
        )}
        <p className="install-footnote">
          دریافت پیشنهاد و نگه‌داشتن تجربه‌ها به اتصال اینترنت نیاز داره.
        </p>
      </dialog>
    </>
  );
}
