"use client";

import { useEffect, useState, type ReactNode } from "react";

import { Provider } from "react-redux";
import { setupListeners } from "@reduxjs/toolkit/query";

import { makeStore } from "@/lib/store/store";
import AuthBootstrap from "@/components/auth/AuthBootstrap";

export default function StoreProvider({ children, allowUnavailable }: {
  children: ReactNode;
  allowUnavailable?: boolean;
}) {
  const [store] = useState(makeStore);

  useEffect(() => {
    return setupListeners(store.dispatch);
  }, [store]);

  return (
    <Provider store={store}>
      <AuthBootstrap allowUnavailable={allowUnavailable}>{children}</AuthBootstrap>
    </Provider>
  );
}
