export function updateDiscoverFilter(key: "q" | "tag" | "limit", value: string) {
  const url = new URL(window.location.href);

  if (value) url.searchParams.set(key, value);
  else url.searchParams.delete(key);

  if (key !== "limit") url.searchParams.delete("limit");

  window.history.replaceState(null, "", url);
}
