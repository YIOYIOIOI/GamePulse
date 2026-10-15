import { useEffect, useState } from "react";

export const PAGES = [
  "overview",
  "issues",
  "releases",
  "feedback",
  "follow-ups",
  "settings",
] as const;
export type Page = (typeof PAGES)[number];

export interface Route {
  page: Page;
  /** Second path segment: a category key, release id, follow-up id or settings tab. */
  id?: string;
  params: URLSearchParams;
}

function parse(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const [page, id] = path.split("/").map(decodeURIComponent);
  return {
    page: (PAGES as readonly string[]).includes(page)
      ? (page as Page)
      : "overview",
    id: id || undefined,
    params: new URLSearchParams(query),
  };
}

/** Builds a hash link, e.g. href("feedback", undefined, { category: "stability" }). */
export function href(
  page: Page,
  id?: string,
  params?: Record<string, string | undefined>,
) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {}))
    if (value) query.set(key, value);
  const search = query.toString();
  return `#/${page}${id ? "/" + encodeURIComponent(id) : ""}${search ? "?" + search : ""}`;
}

export function navigate(target: string, replace = false) {
  if (replace) history.replaceState(null, "", target);
  else history.pushState(null, "", target);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(location.hash));
  useEffect(() => {
    const update = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
