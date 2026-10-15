"""Bounded official API collection, exact raw responses and explicit coverage."""

from __future__ import annotations

import json
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx

from src.quality.contracts import Product, iso
from src.quality.store import Store

STEAM_API = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
SAFE_HEADERS = (
    "content-type",
    "etag",
    "last-modified",
    "link",
    "date",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "retry-after",
)


class SourceError(RuntimeError):
    pass


class Collector:
    def __init__(self, store: Store, run_id: str, progress=None, client=None, delay=0.65):
        self.store = store
        self.run_id = run_id
        self.progress = progress or (lambda **_: None)
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(40, connect=15),
            follow_redirects=True,
            headers={
                "User-Agent": "GamePulse/0.1 local product-quality research",
                "Accept": "application/json",
            },
        )
        self.owns_client = client is None
        self.delay = delay
        self.last_request = 0.0
        self.last_search = 0.0

    def close(self):
        if self.owns_client:
            self.client.close()

    def fetch(
        self,
        product: str,
        source: str,
        sequence: int,
        url: str,
        params: dict | None = None,
        metadata: dict | None = None,
    ) -> tuple[dict, object, dict]:
        request = self.client.build_request("GET", url, params=params)
        request_url = str(request.url)
        headers = {}
        cached = self.store.cached(request_url) if source.startswith("github") else None
        if cached and cached["etag"]:
            headers["If-None-Match"] = cached["etag"]
        if source.startswith("github"):
            headers.update(
                {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
            )
        for attempt in range(4):
            if request_url.startswith("https://api.github.com/search/"):
                # Anonymous search is more restrictive than repository REST calls.
                # 7.1 seconds remains below both the documented 9/10-per-minute variants.
                time.sleep(max(0, self.last_search + (7.1 if self.delay else 0) - time.monotonic()))
                self.last_search = time.monotonic()
            time.sleep(max(0, self.last_request + self.delay - time.monotonic()))
            self.last_request = time.monotonic()
            try:
                response = self.client.get(request_url, headers=headers)
            except httpx.TransportError as exc:
                if attempt == 3:
                    raise SourceError(f"{source} network failure: {type(exc).__name__}") from exc
                time.sleep(2**attempt)
                continue
            public_headers = {
                key: response.headers[key] for key in SAFE_HEADERS if key in response.headers
            }
            if response.status_code == 304:
                if not cached:
                    raise SourceError("304 received without a verified cached response")
                content = self.store.read_raw(cached["path"], cached["sha256"])
                previous = self.store.query(
                    "SELECT headers_json FROM pages WHERE path=? ORDER BY fetched_at DESC LIMIT 1",
                    (cached["path"],),
                )
                public_headers = {
                    **(json.loads(previous[0]["headers_json"]) if previous else {}),
                    **public_headers,
                }
            else:
                content = response.content
            if len(content) > 30 * 1024 * 1024:
                raise SourceError("source response exceeds 30 MiB limit")
            if response.status_code == 429 or (
                response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0"
            ):
                page = self.store.save_page(
                    self.run_id,
                    product,
                    source,
                    sequence,
                    request_url,
                    content,
                    response.status_code,
                    public_headers,
                    {**(metadata or {}), "attempt": attempt},
                )
                retry = response.headers.get("retry-after", "")
                wait = float(retry) if retry.isdigit() else 60.0
                if attempt == 3 or wait > 60 or response.status_code == 403:
                    raise SourceError(
                        f"{source} rate limited; reset={response.headers.get('x-ratelimit-reset', 'unknown')}; raw={page['id']}"
                    )
                time.sleep(wait)
                continue
            if response.status_code >= 500 and attempt < 3:
                self.store.save_page(
                    self.run_id,
                    product,
                    source,
                    sequence,
                    request_url,
                    content,
                    response.status_code,
                    public_headers,
                    {**(metadata or {}), "attempt": attempt},
                )
                time.sleep(2**attempt)
                continue
            page = self.store.save_page(
                self.run_id,
                product,
                source,
                sequence,
                request_url,
                content,
                response.status_code,
                public_headers,
                metadata,
            )
            if response.status_code not in (200, 304):
                raise SourceError(f"{source} HTTP {response.status_code}; raw={page['id']}")
            try:
                data = json.loads(content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourceError(f"{source} returned non-JSON; raw={page['id']}") from exc
            return page, data, public_headers
        raise SourceError(f"{source} retries exhausted")

    def identity(self, product: Product):
        page, body, _ = self.fetch(
            product.key,
            "steam_identity",
            1,
            "https://store.steampowered.com/api/appdetails",
            {"appids": product.app_id, "cc": "US", "l": "english"},
        )
        app = body.get(str(product.app_id), {}) if isinstance(body, dict) else {}
        # The App ID was checked when the game was added; a later rename on Steam is not an error.
        if app.get("success") is not True or not app.get("data", {}).get("name"):
            raise SourceError(f"Steam 上找不到 App {product.app_id}；raw={page['id']}")
        return {
            "steam_name": app["data"]["name"],
            "developers": app["data"].get("developers", []),
            "store_url": f"https://store.steampowered.com/app/{product.app_id}/",
            "repository": product.repo,
            "raw_page": page["id"],
        }

    def steam(self, product: Product, start: datetime, end: datetime, max_reviews: int):
        rows = []
        seen = set()
        cursor = "*"
        seen_cursors = {cursor}
        page_number = 0
        duplicates = 0
        matching = None
        stop_reason = "record_cap"
        complete = False
        stagnant_pages = 0
        request_cap = ((max_reviews + 99) // 100) * 3 + 10
        while len(seen) < max_reviews:
            if page_number >= request_cap:
                stop_reason = "request_cap"
                break
            page_number += 1
            inputs = {
                "appid": product.app_id,
                "filter": 1,
                "languages": ["all"],
                "review_type": 0,
                "purchase_type": 1,
                "num_per_page": 100,
                "filter_offtopic_activity": False,
                "cursor": cursor,
                "date_range_start": int(start.timestamp()),
                "date_range_end": int(end.timestamp()),
            }
            page, payload, _ = self.fetch(
                product.key,
                "steam",
                page_number,
                STEAM_API,
                {"input_json": json.dumps(inputs, separators=(",", ":"))},
                {"cursor": cursor, "window_start": iso(start), "window_end": iso(end)},
            )
            body = payload.get("response") if isinstance(payload, dict) else None
            # The real zero-row terminal response omits `reviews` and explicitly
            # reports query_summary.num_reviews=0. Do not accept arbitrary missing arrays.
            if (
                isinstance(body, dict)
                and "reviews" not in body
                and body.get("query_summary", {}).get("num_reviews") == 0
            ):
                body = {**body, "reviews": []}
            if not isinstance(body, dict) or not isinstance(body.get("reviews"), list):
                raise SourceError(f"Steam schema changed; raw={page['id']}")
            batch = body["reviews"]
            previous_count = len(seen)
            if page_number == 1:
                matching = body.get("total_matching")
                if not isinstance(matching, int) or isinstance(matching, bool) or matching < 0:
                    raise SourceError("Steam did not provide valid total_matching")
            for index, item in enumerate(batch):
                if not isinstance(item, dict):
                    raise SourceError("Steam review row is not an object")
                rid = str(item.get("recommendationid", ""))
                if rid in seen:
                    duplicates += 1
                seen.add(rid)
                rows.append((item, page, f"/response/reviews/{index}"))
            stagnant_pages = stagnant_pages + 1 if batch and len(seen) == previous_count else 0
            self.progress(
                product=product.key,
                source="steam",
                pages=page_number,
                records=len(seen),
                message=f"{product.name}：评论第 {page_number} 页",
            )
            if not batch:
                stop_reason = "empty_page"
                complete = True
                break
            if stagnant_pages >= 2:
                stop_reason = "repeated_records_without_progress"
                break
            next_cursor = body.get("cursor")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                stop_reason = "repeated_or_missing_cursor"
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        if len(seen) > max_reviews:
            kept_ids = set()
            limited = []
            for item, page, pointer in rows:
                rid = str(item.get("recommendationid", ""))
                if rid in kept_ids or len(kept_ids) < max_reviews:
                    kept_ids.add(rid)
                    limited.append((item, page, pointer))
            rows = limited
        unique = len({str(r[0].get("recommendationid", "")) for r in rows})
        count_matches = matching == unique if complete else None
        if complete and not count_matches:
            complete = False
            stop_reason = "count_mismatch"
        coverage = {
            "source": "steam",
            "pages": page_number,
            "raw_rows": len(rows),
            "unique_ids": unique,
            "duplicates": duplicates,
            "reported_matching": matching,
            "complete": complete,
            "stop_reason": stop_reason,
            "count_matches": count_matches,
            "cap": max_reviews,
            "request_cap": request_cap,
            "window_start": iso(start),
            "window_end": iso(end),
            "scope": "公开评论；按创建时间；所有语言/购买来源；包含off-topic；不是全体玩家样本",
        }
        return rows, coverage

    def github(self, product: Product, source: str, start: datetime, max_pages: int):
        if source == "github_issues":
            return self.github_issues(product, start, max_pages)
        suffix = "issues" if source == "github_issues" else "releases"
        url = f"https://api.github.com/repos/{product.repo}/{suffix}"
        params = {"per_page": 100}
        if suffix == "issues":
            params.update(
                {"state": "all", "since": iso(start), "sort": "created", "direction": "desc"}
            )
        rows = []
        visited = set()
        complete = False
        page_number = 0
        stop_reason = "page_cap"
        while page_number < max_pages:
            page_number += 1
            page, body, headers = self.fetch(
                product.key,
                source,
                page_number,
                url,
                params,
                {"updated_since": iso(start) if suffix == "issues" else None},
            )
            if not isinstance(body, list) or any(not isinstance(x, dict) for x in body):
                raise SourceError(f"GitHub schema changed for {source}; raw={page['id']}")
            rows.extend((item, page, f"/{index}") for index, item in enumerate(body))
            self.progress(
                product=product.key,
                source=source,
                pages=page_number,
                records=len(rows),
                message=f"{product.name}：{suffix} 第 {page_number} 页",
            )
            next_url = (
                httpx.Response(200, headers={"Link": headers.get("link", "")})
                .links.get("next", {})
                .get("url")
            )
            if not next_url:
                complete = True
                stop_reason = "no_next_link"
                break
            parsed = urlparse(next_url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "api.github.com"
                or not parsed.path.endswith("/" + suffix)
            ):
                raise SourceError("untrusted GitHub pagination URL")
            if next_url in visited:
                stop_reason = "repeated_next_link"
                break
            visited.add(next_url)
            url, params = next_url, None
        return rows, {
            "source": source,
            "pages": page_number,
            "raw_rows": len(rows),
            "complete": complete,
            "stop_reason": stop_reason,
            "page_cap": max_pages,
            "scope": "updated_since 窗口内的公开 issues（排除PR），非完整历史缺陷库"
            if suffix == "issues"
            else "官方仓库公开 releases；发布时间未核验为Steam部署时间",
        }

    def github_issues(self, product: Product, start: datetime, max_pages: int):
        # Repository /issues includes PRs; use explicit is:issue to spend the row
        # budget on the business population. Keep search index/1,000-result limits visible.
        query = f"repo:{product.repo} is:issue updated:>={start.date().isoformat()}"
        rows, visited = [], set()
        reported = None
        incomplete = False
        complete = False
        boundary_verified = False
        stop_reason = "page_cap"
        page_number = 0
        for number in range(1, min(max_pages, 10) + 1):
            page_number = number
            page, payload, headers = self.fetch(
                product.key,
                "github_issues",
                number,
                "https://api.github.com/search/issues",
                {"q": query, "sort": "created", "order": "desc", "per_page": 100, "page": number},
                {"query": query, "updated_since_date_utc": start.date().isoformat()},
            )
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("items"), list)
                or not isinstance(payload.get("total_count"), int)
            ):
                raise SourceError(f"GitHub issue search schema changed; raw={page['id']}")
            reported = payload["total_count"] if reported is None else reported
            incomplete = incomplete or payload.get("incomplete_results") is not False
            items = payload["items"]
            rows.extend((item, page, f"/items/{index}") for index, item in enumerate(items))
            self.progress(
                product=product.key,
                source="github_issues",
                pages=number,
                records=len(rows),
                message=f"{product.name}：公开 issue 第 {number} 页",
            )
            next_url = (
                httpx.Response(200, headers={"Link": headers.get("link", "")})
                .links.get("next", {})
                .get("url")
            )
            if not next_url:
                if reported >= 1000:
                    stop_reason = "search_1000_result_limit"
                    break
                # Verify one page beyond the advertised end, including zero-result repositories.
                _, tail, _ = self.fetch(
                    product.key,
                    "github_issues",
                    number + 1,
                    "https://api.github.com/search/issues",
                    {
                        "q": query,
                        "sort": "created",
                        "order": "desc",
                        "per_page": 100,
                        "page": number + 1,
                    },
                    {"query": query, "boundary_probe": True},
                )
                page_number += 1
                boundary_verified = (
                    isinstance(tail, dict)
                    and tail.get("items") == []
                    and tail.get("incomplete_results") is False
                )
                unique = len({r[0].get("id") for r in rows})
                complete = boundary_verified and not incomplete and unique == reported
                stop_reason = (
                    "empty_boundary_page" if complete else "search_count_or_boundary_mismatch"
                )
                break
            parsed = urlparse(next_url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "api.github.com"
                or parsed.path != "/search/issues"
            ):
                raise SourceError("untrusted issue search pagination URL")
            if next_url in visited:
                stop_reason = "repeated_next_link"
                break
            visited.add(next_url)
        return rows, {
            "source": "github_issues",
            "pages": page_number,
            "raw_rows": len(rows),
            "complete": complete,
            "stop_reason": stop_reason,
            "page_cap": max_pages,
            "reported_matching": reported,
            "search_incomplete": incomplete,
            "boundary_verified": boundary_verified,
            "search_result_limit": 1000,
            "scope": f"官方仓库公开issue；更新日期UTC≥{start.date().isoformat()}；搜索索引结果，排除PR；不是全部历史缺陷",
        }
