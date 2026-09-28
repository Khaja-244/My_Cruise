/* FCM/browser push worker. Firebase supplies the notification payload; no credentials are embedded here. */
self.addEventListener('push',event=>{let data={};try{data=event.data?event.data.json():{}}catch{}const n=data.notification||data.data||{};event.waitUntil(self.registration.showNotification(n.title||'my_cruise',{body:n.body||'You have a new notification.',data:data.data||{}}));});
