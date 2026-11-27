"""A map file read from a folder of maps that may keep it gzip-compressed. Since 2026-11-25 the site keeps an area's
big files as <name>.gz (scripts/weblib.py pack, run by publish_site.sh): the very bytes of <name>, compressed. output/,
the baselines and the scratch builds keep them plain. Every read here gives the plain file's bytes and sha1() its hash,
whichever of the two is there, so a check reads the published site and a build the same way.
    exists(path)          path or path.gz is there
    read_bytes(path), read_text(path)
    sha1(path)            of the plain bytes (run_all.sh's status, which the publish gate matches with output/)
    plain(path, folder)   a plain file to hand to another program (jsc): path itself, or path.gz unpacked into folder
"""
import gzip, hashlib, os, shutil


def where(path):
    """path, or path + ".gz" where only that is there; None where neither is."""
    if os.path.exists(path):
        return path
    return path + ".gz" if os.path.exists(path + ".gz") else None


def exists(path):
    return where(path) is not None


def _open(path):
    p = where(path)
    if p is None:
        raise FileNotFoundError(path)
    return gzip.open(p, "rb") if p.endswith(".gz") and not path.endswith(".gz") else open(p, "rb")


def read_bytes(path):
    with _open(path) as f:
        return f.read()


def read_text(path):
    return read_bytes(path).decode("utf-8")


def sha1(path):
    h = hashlib.sha1()
    with _open(path) as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def plain(path, folder):
    p = where(path)
    if p is None or p == path:
        return path
    out = os.path.join(folder, os.path.basename(path))
    with _open(path) as f, open(out, "wb") as g:
        shutil.copyfileobj(f, g)
    return out
