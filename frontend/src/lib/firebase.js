import { initializeApp, getApps } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';
import { api } from '../api/client';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export async function enablePushAfterBooking() {
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !import.meta.env.VITE_FIREBASE_VAPID_KEY || !config.apiKey) return false;
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return false;
  const app = getApps()[0] || initializeApp(config);
  const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  const messaging = getMessaging(app);
  const token = await getToken(messaging, { vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY, serviceWorkerRegistration: registration });
  if (token) await api.post('/devices/token', { fcm_token: token, platform: 'web' });
  onMessage(messaging, (payload) => window.dispatchEvent(new CustomEvent('mycruise-notification', { detail: payload })));
  return true;
}
