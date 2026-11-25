// The kill switch for the stream maps' service worker (README, "Offline, as an app"), kept here and not published.
// Copied over scripts/web/sw.js and published, it answers nothing: with no fetch handler every page, library and tile
// comes from the network as if there were no worker. Each phone takes it at its next page load with a connection
// (sw.js is checked past the HTTP cache: offline.js registers it with updateViaCache "none") and it takes over at once
// (skipWaiting, clients.claim), open pages included. The maps saved on phones stay there unused (WIPE = true deletes
// them too); the layer panel can still save, to no effect, so put the real sw.js back soon: phones take it the same
// way and their saved maps work again.
const WIPE = false;
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil((async () => {
  if (WIPE) for (const k of await caches.keys()) if (k.startsWith("streams-")) await caches.delete(k);
  await self.clients.claim();
})()));
