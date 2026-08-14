/*
 * Enough of a service worker to make this installable, and no more.
 *
 * Nothing is cached. The whole app is one page served by a machine on the same
 * network, and a cached copy of a question is a stale question -- worse than
 * no page at all. The worker exists so a phone will offer "Add to Home Screen"
 * and treat this as an app once it is there.
 */
self.addEventListener("install", (event) => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

/*
 * A nudge from a push service, carrying nothing.
 *
 * This is the one part that cannot be local: waking a locked phone is done by
 * Apple and Google and by nobody else. So the push says only that there is
 * something to answer -- no question, no options, no employer. The app opens,
 * asks the machine at home what was being asked, and shows it.
 */
self.addEventListener("push", (event) => {
  event.waitUntil(
    self.registration.showNotification("A question about your application", {
      body: "Open to answer it.",
      tag: "applypilot",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("/phone/"));
});
