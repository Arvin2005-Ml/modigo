import { useSyncExternalStore } from "react";

const key = "moodigo:guest-suggestion";

function subscribe(onChange: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === key || event.key === null) onChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("pageshow", onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("pageshow", onChange);
  };
}

function readSuggestion() {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return false;
  }
}

export function useStoredGuestSuggestion() {
  return useSyncExternalStore(subscribe, readSuggestion, () => undefined);
}

export async function storeGuestSuggestion(activityKey: string) {
  const claim = () => {
    const storage = window.localStorage;
    if (storage.getItem(key) !== null) return false;
    storage.setItem(key, activityKey);
    return true;
  };

  // Serialize the read and write across tabs when the browser supports Web Locks.
  return navigator.locks ? navigator.locks.request(key, claim) : claim();
}
