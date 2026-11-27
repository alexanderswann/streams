// gunzip in plain JavaScript (RFC 1951 deflate in an RFC 1952 gzip wrapper), for browsers without DecompressionStream
// (Safari before 16.4): load.js loads it only there. Written for these maps (2026-11-25), checked byte for byte on every
// compressed file of the 12 maps against the files they were made from (JavaScriptCore, the iPhone's engine).
//   StreamsInflate.gunzip(Uint8Array) -> Uint8Array   throws on anything that isn't one whole, intact gzip member
(function () {
  const LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195,
                 227, 258];
  const LEXT = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
  const DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
                 4097, 6145, 8193, 12289, 16385, 24577];
  const DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
  const ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

  // a canonical Huffman code (code lengths of symbols 0..n-1) as one lookup table indexed by the next mb input bits
  // (least significant first): each entry is symbol << 4 | code length, 0 where no code starts so
  function table(lens, n) {
    let mb = 0;
    const count = new Uint16Array(16), next = new Uint16Array(16);
    for (let i = 0; i < n; i++) { count[lens[i]]++; if (lens[i] > mb) mb = lens[i]; }
    count[0] = 0;
    for (let b = 1, code = 0; b < 16; b++) { code = (code + count[b - 1]) << 1; next[b] = code; }
    const size = 1 << mb, t = new Int32Array(size);
    for (let s = 0; s < n; s++) {
      const l = lens[s];
      if (!l) continue;
      let c = next[l]++, r = 0;
      for (let i = 0; i < l; i++) { r = (r << 1) | (c & 1); c >>= 1; }
      for (let j = r, v = (s << 4) | l; j < size; j += 1 << l) t[j] = v;
    }
    return {t, mb};
  }
  const FIXED_L = table(Uint8Array.from({length: 288}, (_, i) => i < 144 ? 8 : i < 256 ? 9 : i < 280 ? 7 : 8), 288);
  const FIXED_D = table(new Uint8Array(30).fill(5), 30);

  // raw deflate data from byte at of d into out (sized exactly); returns the bytes written
  function inflate(d, at, out) {
    let p = at * 8, o = 0, last = 0;
    const n = d.length * 8;
    const bits = k => { const i = p >> 3, v = ((d[i] | (d[i + 1] << 8) | (d[i + 2] << 16)) >>> (p & 7)) & ((1 << k) - 1);
                        p += k; return v; };
    const sym = h => {
      const i = p >> 3, e = h.t[((d[i] | (d[i + 1] << 8) | (d[i + 2] << 16)) >>> (p & 7)) & ((1 << h.mb) - 1)];
      if (!e) throw new Error("inflate: bad code");
      p += e & 15;
      return e >> 4;
    };
    while (!last) {
      if (p > n) throw new Error("inflate: data ends early");
      last = bits(1);
      const type = bits(2);
      if (type === 0) {                                   // stored
        let i = (p + 7) >> 3;
        const len = d[i] | (d[i + 1] << 8), nlen = d[i + 2] | (d[i + 3] << 8);
        if ((len ^ 0xffff) !== nlen || i + 4 + len > d.length) throw new Error("inflate: bad stored block");
        out.set(d.subarray(i + 4, i + 4 + len), o);
        o += len; p = (i + 4 + len) * 8;
        continue;
      }
      let L, D;
      if (type === 1) { L = FIXED_L; D = FIXED_D; }
      else if (type === 2) {                              // dynamic Huffman codes
        const nl = bits(5) + 257, nd = bits(5) + 1, nc = bits(4) + 4;
        const cl = new Uint8Array(19);
        for (let i = 0; i < nc; i++) cl[ORDER[i]] = bits(3);
        const C = table(cl, 19), lens = new Uint8Array(nl + nd);
        for (let i = 0; i < nl + nd;) {
          const s = sym(C);
          if (s < 16) lens[i++] = s;
          else {
            let rep, v = 0;
            if (s === 16) { if (!i) throw new Error("inflate: bad lengths"); v = lens[i - 1]; rep = 3 + bits(2); }
            else rep = s === 17 ? 3 + bits(3) : 11 + bits(7);
            if (i + rep > nl + nd) throw new Error("inflate: bad lengths");
            lens.fill(v, i, i + rep); i += rep;
          }
        }
        L = table(lens.subarray(0, nl), nl); D = table(lens.subarray(nl), nd);
      } else throw new Error("inflate: bad block type");
      for (;;) {
        const s = sym(L);
        if (s < 256) { if (o >= out.length) throw new Error("inflate: too long"); out[o++] = s; continue; }
        if (s === 256) break;
        const li = s - 257;
        if (li >= 29) throw new Error("inflate: bad length");
        const len = LBASE[li] + bits(LEXT[li]), di = sym(D);
        if (di >= 30) throw new Error("inflate: bad distance");
        const dist = DBASE[di] + bits(DEXT[di]);
        if (dist > o || o + len > out.length) throw new Error("inflate: bad match");
        if (dist >= len) { out.copyWithin(o, o - dist, o - dist + len); o += len; }
        else for (let k = 0; k < len; k++, o++) out[o] = out[o - dist];
      }
    }
    return o;
  }

  let CRC = null;
  function crc32(b) {
    if (!CRC) {
      CRC = new Int32Array(256);
      for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; CRC[i] = c; }
    }
    let c = -1;
    for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8);
    return (c ^ -1) >>> 0;
  }

  function gunzip(d) {
    if (d.length < 18 || d[0] !== 0x1f || d[1] !== 0x8b || d[2] !== 8) throw new Error("gunzip: not gzip");
    const flg = d[3];
    let i = 10;
    if (flg & 4) i += 2 + (d[i] | (d[i + 1] << 8));      // extra field
    if (flg & 8) while (d[i++]);                          // file name
    if (flg & 16) while (d[i++]);                         // comment
    if (flg & 2) i += 2;                                  // header crc
    const u32 = j => (d[j] | (d[j + 1] << 8) | (d[j + 2] << 16) | (d[j + 3] << 24)) >>> 0;
    const out = new Uint8Array(u32(d.length - 4));
    if (inflate(d, i, out) !== out.length || crc32(out) !== u32(d.length - 8)) throw new Error("gunzip: damaged data");
    return out;
  }

  (typeof window !== "undefined" ? window : this).StreamsInflate = {gunzip, inflate};
})();
