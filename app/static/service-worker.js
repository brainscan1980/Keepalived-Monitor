const CACHE='keepalived-monitor-v3';
const ASSETS=['/','/static/app.css','/static/branding.css','/static/app.js','/static/manifest.json','/static/logo.svg','/static/app-icon.svg','/static/app-icon-maskable.svg','/static/icon-192.png','/static/icon-512.png','/static/icon-maskable-512.png','/static/apple-touch-icon.png','/static/favicon-32.png','/static/favicon.ico'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  if(event.request.url.includes('/api/')){event.respondWith(fetch(event.request));return;}
  event.respondWith(fetch(event.request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));return response}).catch(()=>caches.match(event.request).then(cached=>cached||caches.match('/'))));
});
