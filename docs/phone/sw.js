// Built by build.mjs. Keeps the phone edition's own files so it opens with no internet.
// The patient model is not here: WebLLM keeps it in the browser's storage by itself.
// Online, every file comes fresh from the network, and the copy here is updated.
// Offline, or after 6 seconds with no answer, the copy here is used.
const CACHE = "vsp-phone-78ae9c6003ce";
const KEEP = ["./","index.html","phone.js","lib/web-llm.js","manifest.webmanifest","icon-180.png","icon-192.png","icon-512.png","cases/index.json","cases/bellevue.txt","cases/davis.txt","cases/graham.txt","cases/lewis.txt","cases/morris.txt","cases/samuels.txt","cases/springfield.txt","cases/travis.txt"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(KEEP.map(f => new Request(f, { cache: "reload" })))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("vsp-phone-") && k !== CACHE)
    .map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    // WebLLM and the icons change only with a new version, and WebLLM is 6.6 MB: keep the copy.
    if (req.url.includes("/lib/") || req.url.includes("/icon-")) { const hit = await cache.match(req); if (hit) return hit; }
    try {
      const res = await Promise.race([fetch(req, { cache: "no-store" }),
        new Promise((_, no) => setTimeout(() => no(new Error("slow")), 6000))]);
      if (res.ok) cache.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await cache.match(req, { ignoreSearch: true });
      if (hit) return hit;
      throw err;
    }
  })());
});
