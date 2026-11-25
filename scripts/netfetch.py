"""Downloads that fail fast, and the last good copy when one fails (2026-11-22).

Two network drops on 2026-11-22 (the Mac moved between Wi-Fi and a phone hotspot and back) stalled and failed a
12-map rebuild: 11_context.py waited 90 minutes in one ArcGIS query on connections whose address had gone (its page
size shrank to one feature and never grew back), 47 minutes on another connection, and stopped an area on
"iNaturalist failed". Every download in the pipeline goes through here:

  get(url, ...), post(url, ...), request(method, url, ...)
      requests.get / .post / .request, one attempt (the caller's loop retries; fetch() below is a loop), with
      - CONNECT s to connect (TLS handshake included) and the caller's read timeout between bytes;
      - a hard limit on the whole attempt, CONNECT + LIMIT_X x the read timeout (or limit=): a DNS lookup that never
        returns, a stuck handshake or a server trickling bytes is cut as well. With stream=True it covers the answer's
        head; the body is read by the caller, with the read timeout between bytes;
      - a breaker: a host that failed HOST_FAILS requests in a row without answering (no connection, reset, timed
        out, cut at the hard limit), or NET_FAILS such requests in a row to any hosts, counts as unreachable for
        COOL_OFF s. (A server that times out three times in a row isn't answering, whatever the reason; a page too
        big for a server comes back as an error answer, which doesn't count.) A request to it
        raises NetworkDown at once, and so does wait(), the pause between a caller's tries. NetworkDown is a
        RuntimeError, not a requests error: the callers' retry loops (which catch requests' errors) end there and the
        step goes on to its last good copy. After COOL_OFF s one request may try again. Any answer (any HTTP status)
        clears the host.
  fetch(method, url, tries=3, pause=..., ok=...)  a few tries of request() until ok(response); FetchError (a
      RuntimeError) when none gives a usable answer
  last_good(name, fetch, what, also=())    fetch()'s result (anything JSON can hold), kept as the last good copy in
      data/raw/<area>/_shared/netcache/<name>.json.gz. When fetch() fails (no network, a server that answers
      nonsense): that copy, a dated NOTE in the log, and asof(what) gives its date. The error again when there is none.
      `also`: names the copy was kept under before (tried in turn when `name` has none).
  keep_old(path, fetch, what)     the same for a download kept as a file of its own (a week or a month): fetch()
      rewrites `path`; when it fails the earlier file stays, with the NOTE.
An empty answer (a box with no closed roads, no named stream) is an answer: it is kept like any other, since without
a copy the step can't run offline. A partial answer, or an error page, is not.
  asof(*what)                     ' (as of Nov 21)' when any of those sources came from a last good copy in this step,
      else '': for the source wording the map shows (closures' source, fire perimeters' source, trout records' label).
  usgs_key(url)                   {"X-Api-Key": key} for a request to the USGS Water Data APIs, else {}: the key from
      USGS_API_KEY or, when that's unset, the private file ~/.config/usgs/api_key (2026-11-24)

A copy is used whatever its age: a rebuild on day-old closures with a dated note is better than no map. With the
network up nothing here changes what a step makes (the same requests, the same answers); only the copies are written.

Switches (environment), for tests:
  NET_FAIL=1         every request fails at once, as with no network; NET_FAIL=<regex>: only the URLs it matches
  NET_LOG=1          one line per request: method, host and path, the answer or the error, seconds
GDAL's own downloads (/vsicurl/ in lakelidar.py) get the same connect timeout, a stall limit and three tries through
its GDAL_HTTP_* settings, set here unless already set. NET_FAIL doesn't reach them: a test that should cut them too
sets GDAL_HTTP_PROXY=http://127.0.0.1:9 (a closed port).
"""
import os, re, sys, json, gzip, time, hashlib, threading, datetime as dt
from urllib.parse import urlsplit
import requests

CONNECT = 15         # s to connect, TLS handshake included: a dead address or route doesn't answer in 15 s
LIMIT_X = 2          # an attempt's hard limit: CONNECT + LIMIT_X x its read timeout
HOST_FAILS = 3       # unanswered requests in a row that take a host out for COOL_OFF s
NET_FAILS = 5        # ... and to any hosts, that take the whole network out
COOL_OFF = 120

for _k, _v in (("GDAL_HTTP_CONNECTTIMEOUT", str(CONNECT)), ("GDAL_HTTP_LOW_SPEED_TIME", "120"),
               ("GDAL_HTTP_LOW_SPEED_LIMIT", "1"), ("GDAL_HTTP_MAX_RETRY", "3"), ("GDAL_HTTP_RETRY_DELAY", "10")):
    os.environ.setdefault(_k, _v)


class NetworkDown(RuntimeError):
    """The host, or the network, didn't answer the last few requests: not tried again now."""


class FetchError(RuntimeError):
    """No usable answer after a fetch()'s tries."""


class HardTimeout(requests.exceptions.Timeout):
    """An attempt that ran past its hard limit."""


_lock = threading.Lock()
_fails, _down = {}, {}             # host -> unanswered requests in a row; host -> out until (time.time())
_net = {"fails": 0, "until": 0.0}
_stale = {}                        # what -> the date of the last good copy used in this step


def _host(url):
    return urlsplit(url).netloc or url[:40]


def _out(host):
    """Why `host` isn't tried now (it, or the whole network, is in its cool-off), or None."""
    now = time.time()
    with _lock:
        if now < _down.get(host, 0):
            return f"{host} didn't answer {_fails.get(host, 0)} requests in a row; not tried again before " \
                   f"{dt.datetime.fromtimestamp(_down[host]):%H:%M:%S}"
        if now < _net["until"]:
            return f"the network didn't answer {_net['fails']} requests in a row; {host} not tried again before " \
                   f"{dt.datetime.fromtimestamp(_net['until']):%H:%M:%S}"
    return None


def _failed(host):
    with _lock:
        _fails[host] = _fails.get(host, 0) + 1
        _net["fails"] += 1
        if _fails[host] >= HOST_FAILS:
            _down[host] = time.time() + COOL_OFF
        if _net["fails"] >= NET_FAILS:
            _net["until"] = time.time() + COOL_OFF


def _answered(host):
    with _lock:
        _fails[host] = 0
        _down.pop(host, None)
        _net["fails"], _net["until"] = 0, 0.0


def _forced(url):
    f = os.environ.get("NET_FAIL", "")
    return bool(f) and (f == "1" or re.search(f, url) is not None)


def _timeouts(timeout):
    """(connect, read) from a caller's timeout: one number was both, now the connect part is CONNECT at most."""
    if timeout is None:
        return CONNECT, 120.0
    c, r = timeout if isinstance(timeout, tuple) else (timeout, timeout)
    return min(c or CONNECT, CONNECT), r


def _log(method, url, what, t0):
    if os.environ.get("NET_LOG"):
        u = urlsplit(url)
        print(f"net {method} {u.netloc}{u.path[-60:]} -> {what} {time.time() - t0:.1f}s", flush=True)


def request(method, url, limit=None, **kw):
    """One attempt of requests.request(method, url, **kw) within its time limits (see the module's docstring).
    Raises requests' errors as requests does (HardTimeout is a requests Timeout), or NetworkDown."""
    host = _host(url)
    why = _out(host)
    if why:
        raise NetworkDown(why)
    c, r = _timeouts(kw.pop("timeout", None))
    kw["timeout"] = (c, r)
    limit = limit or c + LIMIT_X * r
    t0 = time.time()
    if _forced(url):
        _failed(host)
        _log(method, url, "NET_FAIL", t0)
        raise requests.ConnectionError(f"NET_FAIL: {host} not tried")
    box = {}

    def run():
        try:
            box["r"] = requests.request(method, url, **kw)
        except BaseException as e:     # noqa: BLE001 (handed back to the caller's thread)
            box["e"] = e
    t = threading.Thread(target=run, name=f"netfetch {host}", daemon=True)
    t.start()
    t.join(limit)
    try:
        if t.is_alive():               # left to finish or time out on its own; nothing reads its answer
            raise HardTimeout(f"{host}: no complete answer within {limit:.0f} s")
        if "e" in box:
            raise box["e"]
    except requests.RequestException as e:
        if isinstance(e, (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError)):
            _failed(host)              # no answer: no connection, reset, timed out, cut short
        _log(method, url, type(e).__name__, t0)
        raise
    _answered(host)
    _log(method, url, box["r"].status_code, t0)
    return box["r"]


def get(url, **kw):
    return request("GET", url, **kw)


def post(url, **kw):
    return request("POST", url, **kw)


def wait(seconds, url=None):
    """The pause between a caller's tries; NetworkDown at once instead when the host (or the network) is out. With
    NET_FAIL=1 (a test with no network: every request fails at once, nothing is tried) there is nothing to wait for:
    the same tries, failures and NetworkDown as ever, in the same order, without the pauses (20-40 s a step offline)."""
    why = _out(_host(url)) if url else None
    if why is None and time.time() < _net["until"]:
        why = f"the network didn't answer {_net['fails']} requests in a row"
    if why:
        raise NetworkDown(why)
    if os.environ.get("NET_FAIL", "") == "1":
        return
    time.sleep(seconds)


def fetch(method, url, tries=3, pause=(5, 15, 30), ok=None, **kw):
    """request() until ok(response) (default: an HTTP success) or `tries` attempts, with the pauses between them.
    A server over its request limit (HTTP 429) is waited out as long as it asks (Retry-After, 10 min at most), twice
    at most, outside the tries. FetchError when no attempt gives a usable answer; NetworkDown when the host is out."""
    ok = ok or (lambda r: r.ok)
    last, waits, n = None, 0, 0
    while n < tries:
        try:
            r = request(method, url, **kw)
            if r.status_code == 429 and waits < 2:
                s = r.headers.get("Retry-After", "")
                s = min(int(s) if s.isdigit() else 600, 600)
                rate_wait(s + 5, url)
                waits += 1
                continue
            try:
                if ok(r):
                    return r
            except ValueError:                 # an answer that isn't what was asked for (JSON that doesn't parse)
                pass
            last = f"HTTP {r.status_code}: {r.text[:120]!r}"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:160]}"
        n += 1
        if n < tries:
            wait(pause[min(n - 1, len(pause) - 1)] if isinstance(pause, (tuple, list)) else pause, url)
    raise FetchError(f"no usable answer from {_host(url)} after {tries} tries ({last})")


OVERPASS = ("https://overpass.openstreetmap.fr/api/interpreter", "https://overpass-api.de/api/interpreter")
UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}


def overpass(q, tries=14, read=None):
    """The elements of an Overpass query, from the two public mirrors in turn (the kumi mirror stopped answering in
    Nov 2026). A busy mirror (502 / 429 / 504 under load; each allows about two queries at once per address, so ranges
    running side by side queue up) is waited for, longer each time (30 s, up to 2 min: ~25 min over 14 tries); one that
    doesn't answer at all is passed over after 5 s. An answer whose "remark" carries a runtime error (the query timed
    out or ran out of memory: its elements are only part of the result, audit finding 10, 2026-11-22) is no answer.
    The read timeout is the query's own [timeout:] plus a minute. RuntimeError("Overpass failed") after `tries`;
    NetworkDown when the network is out."""
    if read is None:
        m = re.search(r"\[timeout:(\d+)\]", q)
        read = int(m.group(1)) + 60 if m else 900
    for attempt in range(tries):
        url, answered = OVERPASS[attempt % 2], False
        try:
            r = request("POST", url, data={"data": q}, timeout=(20, read), headers=UA)
            answered = True
            if r.ok:
                js = r.json()
                if "elements" in js and "error" not in str(js.get("remark", "")).lower():
                    return js["elements"]
                print(f"Overpass ({_host(url)}): {' '.join(str(js.get('remark', 'no elements')).split())[:160]}",
                      flush=True)
        except NetworkDown:            # this mirror is out; the other one may not be
            pass
        except (requests.RequestException, ValueError):
            pass
        if attempt < tries - 1:
            wait(min(30 * (attempt + 1), 120) if answered else 5)
    raise RuntimeError("Overpass failed")


def urlretrieve(url, path, read=120, limit=3600):
    """urllib.request.urlretrieve (PRISM's FTP server) within a read timeout and a hard limit, for one attempt."""
    import urllib.request
    host = _host(url)
    why = _out(host)
    if why:
        raise NetworkDown(why)
    if _forced(url):
        _failed(host)
        raise OSError(f"NET_FAIL: {host} not tried")
    box = {}

    def run():
        try:
            with urllib.request.urlopen(url, timeout=read) as src, open(path, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            box["ok"] = True
        except BaseException as e:     # noqa: BLE001
            box["e"] = e
    t = threading.Thread(target=run, name=f"netfetch {host}", daemon=True)
    t.start()
    t.join(limit)
    if t.is_alive() or "e" in box:
        _failed(host)
        raise box.get("e") or OSError(f"{host}: download not complete within {limit} s")
    _answered(host)


# ---- the USGS Water Data API key ----
USGS_HOST = "api.waterdata.usgs.gov"
_usgs = {}


def usgs_key(url):
    """{"X-Api-Key": key} for a request to the USGS Water Data APIs (https, that host only: a "next" link that led
    anywhere else gets {}), else {}. Without a key those APIs count requests by connection, shared with anything else
    on it (a rebuild waited an hour on that limit on 2026-11-24); a free key from https://api.waterdata.usgs.gov/signup/
    gets 1,000 an hour of its own (its X-RateLimit-Limit on 2026-11-24). The key is USGS_API_KEY, or when that's unset
    or empty the private file ~/.config/usgs/api_key (USGS_API_KEY_FILE names another), read once per process: a shell
    started before the key was stored sends it as well. No key, no header (the requests go as before). The key is never
    printed: one that isn't a single word of letters, digits, - and _ (two lines, a stray quote) is left out, with a
    NOTE that doesn't show it."""
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname != USGS_HOST:
        return {}
    if "key" not in _usgs:
        k, src = os.environ.get("USGS_API_KEY", "").strip(), "USGS_API_KEY"
        if not k:
            src = os.path.expanduser(os.environ.get("USGS_API_KEY_FILE") or "~/.config/usgs/api_key")
            try:
                with open(src, encoding="utf-8", errors="replace") as f:
                    k = f.read().strip()
            except OSError:                    # no file: no key
                k = ""
        if k and not re.fullmatch(r"[A-Za-z0-9_-]+", k):
            note(f"the USGS API key in {src} isn't a single word of letters and digits: requests go without a key")
            k = ""
        _usgs["key"] = k
    return {"X-Api-Key": _usgs["key"]} if _usgs["key"] else {}


# ---- the last good copies ----
def _area():
    return os.environ.get("AREA", "la")


def _dir():
    from config import SHARED
    d = f"{SHARED}/netcache"
    os.makedirs(d, exist_ok=True)
    return d


def key(*parts):
    """A short stable name for a request's identity (url, query, box ...)."""
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def note(msg):
    """A dated NOTE line in the step's log (the drivers append every step's output to data/<stage>_<area>.log)."""
    print(f"NOTE {_area()} {dt.datetime.now():%Y-%m-%d %H:%M}: {msg}", flush=True)


def _short(e):
    return f"{type(e).__name__}: {' '.join(str(e).split())[:160]}"


def _mark(what, when):
    _stale[what] = min(when, _stale.get(what, when))


class Partial:
    """What a fetch returns when a part of its answer is missing (a request in it was refused): last_good() hands it
    on, as the step always used it, but never keeps it as the last good copy."""
    def __init__(self, data, why):
        self.data, self.why = data, why


class RateLimited(RuntimeError):
    """A server asked to wait longer than RATE_WAIT_MAX s, and a last good copy is at hand: that copy, now."""


RATE_WAIT_MAX = 120      # s: a longer wait a server asks for (HTTP 429, Retry-After) isn't waited out when there is a copy
_copy_at_hand = []       # for each last_good() / keep_old() under way: whether its copy exists


def rate_wait(seconds, url):
    """The wait a server over its request limit asks for (HTTP 429). On 2026-11-22 the USGS Water Data API asked for 35
    minutes, then 8 more: a rebuild would stall there. A wait over RATE_WAIT_MAX s is not waited out when the fetch has
    a last good copy (RateLimited, which last_good() / keep_old() turn into that copy); without one it is."""
    if seconds > RATE_WAIT_MAX and _copy_at_hand and _copy_at_hand[-1]:
        raise RateLimited(f"{_host(url)} asks to wait {seconds / 60:.0f} min (over its request limit)")
    print(f"{_host(url)} is rate limiting: waiting {seconds // 60 + 1:.0f} min", flush=True)
    time.sleep(seconds)


def last_good(name, fetch, what, also=()):
    """fetch()'s result, saved as `name`'s last good copy; when fetch() fails, that copy (see the module's docstring),
    or else the first there of the copies under the older names `also`. A Partial answer is used and not saved."""
    path = f"{_dir()}/{name}.json.gz"
    olds = [path] + [f"{_dir()}/{a}.json.gz" for a in also]
    _copy_at_hand.append(any(os.path.exists(p) for p in olds))
    try:
        data = fetch()
        if isinstance(data, Partial):
            note(f"{what}: part of the answer is missing ({data.why}); used, but not kept as the last good copy")
            return data.data
    except Exception as e:             # noqa: BLE001 (any network or server failure)
        old = None
        for p in olds:
            if not os.path.exists(p):
                continue
            try:
                with gzip.open(p, "rt") as f:
                    old = json.load(f)
                break
            except (OSError, ValueError) as e2:
                note(f"the last good copy of {what} can't be read ({_short(e2)})")
        if old is None:
            note(f"{what} not fetched ({_short(e)}) and there is no earlier copy")
            raise
        when = dt.datetime.fromisoformat(old["fetched"])
        _mark(what, when)
        note(f"{what} not fetched ({_short(e)}); using the last good copy, of {when:%Y-%m-%d %H:%M}")
        return old["data"]
    finally:
        _copy_at_hand.pop()
    tmp = f"{path}.{os.getpid()}.tmp"
    try:                               # (a copy that can't be written never stops the step that fetched it)
        with gzip.open(tmp, "wt", compresslevel=3) as f:
            json.dump({"fetched": dt.datetime.now().isoformat(timespec="seconds"), "what": what, "data": data}, f)
        os.replace(tmp, path)
    except (TypeError, ValueError, OSError) as e:
        note(f"the last good copy of {what} was not written ({_short(e)})")
        try:
            os.remove(tmp)
        except OSError:
            pass
    return data


def keep_old(path, fetch, what):
    """fetch() (which rewrites the file `path`, or each of a list of paths); when it fails and the earlier files are
    all there, they stay."""
    paths = [path] if isinstance(path, str) else list(path)
    _copy_at_hand.append(all(os.path.exists(p) for p in paths))
    try:
        return fetch()
    except Exception as e:             # noqa: BLE001
        if not all(os.path.exists(p) for p in paths):
            note(f"{what} not fetched ({_short(e)}) and there is no earlier copy")
            raise
        when = dt.datetime.fromtimestamp(min(os.path.getmtime(p) for p in paths))
        _mark(what, when)
        note(f"{what} not refreshed ({_short(e)}); using the copy of {when:%Y-%m-%d %H:%M}")
        return None
    finally:
        _copy_at_hand.pop()


def stale(*what):
    """The date of the oldest last good copy used in this step among `what` (all sources when none given), or None."""
    days = [d for w, d in _stale.items() if not what or w in what]
    return min(days) if days else None


def stale_names():
    """The sources read from a last good copy so far in this step."""
    return set(_stale)


def when(*what):
    """'Nov 21' (with the year when it isn't this year's) when any of `what` came from a last good copy in this step,
    the oldest such copy's day; else ''."""
    d = stale(*what) if what else None
    if d is None:
        return ""
    return f"{d:%b} {d.day}" + (f", {d.year}" if d.year != dt.date.today().year else "")


def asof(*what):
    """' (as of Nov 21)' when any of `what` came from a last good copy in this step, else ''."""
    w = when(*what)
    return f" (as of {w})" if w else ""


def tag(df, col, *what):
    """df with asof(*what) added to its text column `col`, when any of `what` came from a last good copy in this
    step; otherwise (or with no rows) df itself, untouched."""
    a = asof(*what)
    if not a or not len(df):
        return df
    return df.assign(**{col: (df[col].fillna("").astype(str) + a).str.strip()})
