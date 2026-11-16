"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Provider } from "react-redux";
import { setupListeners } from "@reduxjs/toolkit/query";

import { makeStore } from "@/lib/store/store";

export default function StoreProvider({ children }: { children: ReactNode }) {
  const [store] = useState(makeStore);

  useEffect(() => {
    return setupListeners(store.dispatch);
  }, [store]);

  return <Provider store={store}>{children}</Provider>;
}
