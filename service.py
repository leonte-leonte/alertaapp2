"""
Serviciu Android pentru verificarea alertelor in background.
Acest serviciu ruleaza continuu si verifica Firebase pentru alerte noi.
"""
import time
import json
import os
import requests
from jnius import autoclass

# Configurare Firebase - trebuie sa fie aceeasi ca in main.py
FIREBASE_URL = "https://mesaje-bce12-default-rtdb.europe-west1.firebasedatabase.app/alerta.json"

# Clase Android necesare
PythonService = autoclass('org.kivy.android.PythonService')
Intent = autoclass('android.content.Intent')
Context = autoclass('android.content.Context')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')
NotificationChannel = autoclass('android.app.NotificationChannel')
PendingIntent = autoclass('android.app.PendingIntent')
Build = autoclass('android.os.Build')
PowerManager = autoclass('android.os.PowerManager')
AudioManager = autoclass('android.media.AudioManager')
RingtoneManager = autoclass('android.media.RingtoneManager')
Uri = autoclass('android.net.Uri')

CHANNEL_ID = "alerta_channel"
NOTIFICATION_ID = 1001

class AlertService:
    def __init__(self):
        self.service = PythonService.mService
        self.context = self.service.getApplicationContext()
        self.ultima_stare_alerta = False
        self.running = True

        # Calea catre fisierul de setari
        self.settings_path = os.path.join(
            self.context.getFilesDir().getAbsolutePath(),
            'app', 'settings.json'
        )

        # Obtine wake lock pentru a mentine CPU activ
        power_manager = self.context.getSystemService(Context.POWER_SERVICE)
        self.wake_lock = power_manager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "AlertaApp::BackgroundService"
        )

        self.create_notification_channel()
        self.start_foreground()

    def is_silent_mode(self):
        """Verifica daca modul silentios este activ"""
        try:
            # Incearca mai multe locatii posibile pentru settings.json
            possible_paths = [
                self.settings_path,
                '/data/data/org.test.alertasala/files/app/settings.json',
                '/data/data/org.test.alertasala/files/settings.json',
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        data = json.load(f)
                        if 'silent_mode' in data:
                            return data['silent_mode'].get('enabled', False)
            return False
        except Exception as e:
            print(f"Eroare citire setari silent mode: {e}")
            return False

    def create_notification_channel(self):
        """Creeaza canal de notificari pentru Android 8+"""
        if Build.VERSION.SDK_INT >= 26:
            channel = NotificationChannel(
                CHANNEL_ID,
                "Alerte",
                NotificationManager.IMPORTANCE_HIGH
            )
            channel.setDescription("Notificari pentru alerte de urgenta")
            channel.enableVibration(True)
            channel.setLockscreenVisibility(1)  # VISIBILITY_PUBLIC

            notification_manager = self.context.getSystemService(Context.NOTIFICATION_SERVICE)
            notification_manager.createNotificationChannel(channel)

    def start_foreground(self):
        """Porneste serviciul ca foreground service cu notificare persistenta"""
        # Intent pentru a deschide aplicatia la click pe notificare
        package_name = self.context.getPackageName()
        launch_intent = self.context.getPackageManager().getLaunchIntentForPackage(package_name)

        if Build.VERSION.SDK_INT >= 31:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_IMMUTABLE
            )
        else:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_UPDATE_CURRENT
            )

        # Construieste notificarea
        if Build.VERSION.SDK_INT >= 26:
            builder = NotificationBuilder(self.context, CHANNEL_ID)
        else:
            builder = NotificationBuilder(self.context)

        notification = (builder
            .setContentTitle("Alerta Sala")
            .setContentText("Monitorizare activa")
            .setSmallIcon(self.context.getApplicationInfo().icon)
            .setContentIntent(pending_intent)
            .setOngoing(True)
            .build())

        self.service.startForeground(NOTIFICATION_ID, notification)

    def show_alert_notification(self, expeditor):
        """Afiseaza notificare de alerta cu sunet si vibratie"""
        package_name = self.context.getPackageName()
        launch_intent = self.context.getPackageManager().getLaunchIntentForPackage(package_name)
        launch_intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)

        if Build.VERSION.SDK_INT >= 31:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
            )
        else:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_UPDATE_CURRENT
            )

        # Sunet de alarma
        alarm_uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)

        if Build.VERSION.SDK_INT >= 26:
            builder = NotificationBuilder(self.context, CHANNEL_ID)
        else:
            builder = NotificationBuilder(self.context)

        notification = (builder
            .setContentTitle("!!! ALERTA !!!")
            .setContentText(f"Alerta de la: {expeditor}")
            .setSmallIcon(self.context.getApplicationInfo().icon)
            .setContentIntent(pending_intent)
            .setSound(alarm_uri)
            .setVibrate([0, 1000, 500, 1000, 500, 1000])
            .setPriority(2)  # PRIORITY_MAX
            .setCategory("alarm")
            .setAutoCancel(True)
            .setFullScreenIntent(pending_intent, True)
            .build())

        notification_manager = self.context.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.notify(NOTIFICATION_ID + 1, notification)

    def show_silent_notification(self, expeditor):
        """Afiseaza notificare discreta fara sunet (mod silentios)"""
        package_name = self.context.getPackageName()
        launch_intent = self.context.getPackageManager().getLaunchIntentForPackage(package_name)
        launch_intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)

        if Build.VERSION.SDK_INT >= 31:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
            )
        else:
            pending_intent = PendingIntent.getActivity(
                self.context, 0, launch_intent,
                PendingIntent.FLAG_UPDATE_CURRENT
            )

        if Build.VERSION.SDK_INT >= 26:
            builder = NotificationBuilder(self.context, CHANNEL_ID)
        else:
            builder = NotificationBuilder(self.context)

        # Notificare fara sunet si vibratie
        notification = (builder
            .setContentTitle("Alerta (Silentios)")
            .setContentText(f"Alerta de la: {expeditor}")
            .setSmallIcon(self.context.getApplicationInfo().icon)
            .setContentIntent(pending_intent)
            .setPriority(0)  # PRIORITY_DEFAULT
            .setAutoCancel(True)
            .build())

        notification_manager = self.context.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.notify(NOTIFICATION_ID + 1, notification)

    def clear_alert_notification(self):
        """Sterge notificarea de alerta"""
        try:
            notification_manager = self.context.getSystemService(Context.NOTIFICATION_SERVICE)
            notification_manager.cancel(NOTIFICATION_ID + 1)
        except Exception as e:
            print(f"Eroare stergere notificare: {e}")

    def verifica_alerta(self):
        """Verifica starea alertei pe Firebase"""
        try:
            response = requests.get(FIREBASE_URL, timeout=10)
            data = response.json()

            if data:
                status = data.get('status', False)
                cine = data.get('cine', 'Necunoscut')

                # Daca s-a activat o alerta noua
                if status == True and not self.ultima_stare_alerta:
                    self.ultima_stare_alerta = True

                    # Verifica daca modul silentios este activ
                    if not self.is_silent_mode():
                        self.show_alert_notification(cine)
                        # Trezeste ecranul
                        self.wake_screen()
                    else:
                        # Mod silentios - doar notificare discreta fara sunet
                        self.show_silent_notification(cine)

                # Daca alerta s-a oprit
                elif status == False and self.ultima_stare_alerta:
                    self.ultima_stare_alerta = False
                    # Sterge notificarea de alerta
                    self.clear_alert_notification()

        except Exception as e:
            print(f"Eroare verificare alerta: {e}")

    def wake_screen(self):
        """Trezeste ecranul telefonului"""
        try:
            power_manager = self.context.getSystemService(Context.POWER_SERVICE)
            wake_lock = power_manager.newWakeLock(
                PowerManager.FULL_WAKE_LOCK |
                PowerManager.ACQUIRE_CAUSES_WAKEUP |
                PowerManager.ON_AFTER_RELEASE,
                "AlertaApp::WakeScreen"
            )
            wake_lock.acquire(5000)  # 5 secunde
        except Exception as e:
            print(f"Eroare wake screen: {e}")

    def run(self):
        """Bucla principala a serviciului"""
        self.wake_lock.acquire()

        try:
            while self.running:
                self.verifica_alerta()
                time.sleep(3)  # Verifica la fiecare 3 secunde
        finally:
            if self.wake_lock.isHeld():
                self.wake_lock.release()


if __name__ == '__main__':
    service = AlertService()
    service.run()
