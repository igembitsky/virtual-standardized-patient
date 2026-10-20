// The phone test version was removed. This service worker replaces the old one, deletes what
// the old one and WebLLM kept, and removes itself. See index.html.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys())
    if (k.startsWith("vsp-phone-") || k.startsWith("webllm")) await caches.delete(k);
  await self.registration.unregister();
  for (const c of await self.clients.matchAll({ type: "window" })) c.navigate(c.url);
})()));
