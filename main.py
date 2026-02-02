import threading
import requests
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.core.audio import SoundLoader
from kivy.utils import platform
from kivy.metrics import dp, sp
from kivy.storage.jsonstore import JsonStore
from plyer import vibrator
import os

# ================= CONFIGURARE =================
FIREBASE_URL = "https://mesaje-bce12-default-rtdb.europe-west1.firebasedatabase.app/alerta.json"
FIREBASE_ISTORIC_URL = "https://mesaje-bce12-default-rtdb.europe-west1.firebasedatabase.app/istoric.json"
# ===============================================

# Variabile pentru Android
if platform == 'android':
    from android import mActivity
    from android.permissions import request_permissions, Permission
    from jnius import autoclass

    Context = autoclass('android.content.Context')
    Intent = autoclass('android.content.Intent')
    PythonService = autoclass('org.kivy.android.PythonService')
    PowerManager = autoclass('android.os.PowerManager')
    Settings = autoclass('android.provider.Settings')
    Uri = autoclass('android.net.Uri')
    Build = autoclass('android.os.Build')


class ModernButton(Button):
    def __init__(self, **kwargs):
        btn_color = kwargs.pop('btn_color', (1, 0, 0, 1))
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)

        with self.canvas.before:
            self.bg_color = Color(rgba=btn_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])

        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def set_color(self, color):
        self.bg_color.rgba = color


class StatusIndicator(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(20), dp(20))

        with self.canvas:
            self.indicator_color = Color(rgba=(0.5, 0.5, 0.5, 1))
            self.indicator = Ellipse(pos=self.pos, size=self.size)

        self.bind(pos=self.update_indicator, size=self.update_indicator)

    def update_indicator(self, *args):
        self.indicator.pos = self.pos
        self.indicator.size = self.size

    def set_status(self, status):
        if status == 'alert':
            self.indicator_color.rgba = (1, 0.2, 0.2, 1)
        elif status == 'connected':
            self.indicator_color.rgba = (0.2, 0.8, 0.2, 1)
        else:
            self.indicator_color.rgba = (0.5, 0.5, 0.5, 1)


class AlertaApp(App):
    def build(self):
        self.culoare_originala = (0.05, 0.05, 0.1, 1)
        Window.clearcolor = self.culoare_originala

        # Incarca setarile salvate
        self.store = JsonStore('settings.json')

        # Variabile profil
        self.profil = None  # 'sala' sau 'persoana'
        self.nume_utilizator = ""
        self.poate_trimite = False

        # Verifica daca exista profil salvat
        if self.store.exists('profil'):
            self.profil = self.store.get('profil')['tip']
            self.nume_utilizator = self.store.get('profil')['nume']
            self.poate_trimite = (self.profil == 'sala')
            return self.build_main_screen()
        else:
            return self.build_profile_screen()

    def build_profile_screen(self):
        """Ecran de selectare profil"""
        self.profile_layout = FloatLayout()

        content = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(15),
            size_hint=(0.92, 0.88),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # Titlu
        title = Label(
            text="ALERTA SALA",
            font_size='32sp',
            color=(0.9, 0.9, 0.95, 1),
            bold=True,
            size_hint_y=0.15
        )

        subtitle = Label(
            text="Selecteaza profilul:",
            font_size='20sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=0.1
        )

        # Buton SALA MINIMIS
        btn_sala = ModernButton(
            text="SALA MINIMIS\n(Poate trimite alerte)",
            btn_color=(0.85, 0.15, 0.15, 1),
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=0.25,
            halign='center'
        )
        btn_sala.bind(on_press=lambda x: self.selecteaza_profil_sala())

        spacer = Label(size_hint_y=0.05)

        # Buton PERSOANA
        btn_persoana = ModernButton(
            text="PERSOANA\n(Doar primeste alerte)",
            btn_color=(0.2, 0.5, 0.8, 1),
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=0.25
        )
        btn_persoana.bind(on_press=lambda x: self.arata_input_nume())

        # Input pentru nume (ascuns initial)
        self.nume_container = BoxLayout(
            orientation='vertical',
            spacing=dp(8),
            size_hint_y=0.25,
            opacity=0
        )

        self.nume_input = TextInput(
            hint_text="Introdu numele tau...",
            font_size='18sp',
            multiline=False,
            size_hint_y=0.5,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.6, 1),
            cursor_color=(1, 1, 1, 1),
            padding=(dp(12), dp(12))
        )

        self.btn_confirma_nume = ModernButton(
            text="CONFIRMA",
            btn_color=(0.2, 0.75, 0.3, 1),
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=0.5
        )
        self.btn_confirma_nume.bind(on_press=lambda x: self.selecteaza_profil_persoana())

        self.nume_container.add_widget(self.nume_input)
        self.nume_container.add_widget(self.btn_confirma_nume)

        content.add_widget(title)
        content.add_widget(subtitle)
        content.add_widget(btn_sala)
        content.add_widget(spacer)
        content.add_widget(btn_persoana)
        content.add_widget(self.nume_container)

        self.profile_layout.add_widget(content)
        return self.profile_layout

    def arata_input_nume(self):
        """Arata input-ul pentru nume"""
        self.nume_container.opacity = 1
        self.nume_input.focus = True

    def selecteaza_profil_sala(self):
        """Selecteaza profilul SALA MINIMIS"""
        self.profil = 'sala'
        self.nume_utilizator = "SALA MINIMIS"
        self.poate_trimite = True
        self.salveaza_profil()
        self.trece_la_ecran_principal()

    def selecteaza_profil_persoana(self):
        """Selecteaza profilul PERSOANA"""
        nume = self.nume_input.text.strip()
        if not nume:
            self.nume_input.hint_text = "Te rog introdu un nume!"
            return

        self.profil = 'persoana'
        self.nume_utilizator = nume.upper()
        self.poate_trimite = False
        self.salveaza_profil()
        self.trece_la_ecran_principal()

    def salveaza_profil(self):
        """Salveaza profilul selectat"""
        self.store.put('profil', tip=self.profil, nume=self.nume_utilizator)

    def trece_la_ecran_principal(self):
        """Trece de la ecranul de profil la ecranul principal"""
        Window.clearcolor = self.culoare_originala
        self.root.clear_widgets()
        main_screen = self.build_main_screen()
        self.root.add_widget(main_screen)

        # Initializare Android
        if platform == 'android':
            Clock.schedule_once(self.init_android, 1)

        # Porneste verificarea serverului
        Clock.schedule_interval(self.verifica_server, 3)

    def build_main_screen(self):
        """Construieste ecranul principal de alerta"""
        self.alerta_activa = False
        self.sunt_expeditor = False
        self.se_proceseaza_oprire = False  # Flag pentru a preveni race condition
        self.ultima_alerta_expeditor = ""  # Memorează cine a trimis ultima alertă
        self.is_muted = False
        self.silent_mode = False
        self.conectat = False
        self.erori_consecutive = 0

        # Incarca setari
        self.incarca_setari()

        self.alarm_sound = None
        self.incarca_sunet_alarma()

        self.main_layout = FloatLayout()

        self.layout = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(15),
            size_hint=(0.92, 0.92),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        header_layout = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=dp(10))

        self.status_indicator = StatusIndicator(pos_hint={'center_y': 0.5})
        header_layout.add_widget(self.status_indicator)

        self.status_lbl = Label(
            text=f"{self.nume_utilizator}",
            font_size='24sp',
            color=(0.9, 0.9, 0.95, 1),
            bold=True,
            halign='left',
            valign='middle'
        )
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        header_layout.add_widget(self.status_lbl)

        # Buton Silent Mode
        self.btn_silent = ModernButton(
            text="SILENT OFF",
            btn_color=(0.3, 0.3, 0.4, 1),
            font_size='11sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.3, 0.8)
        )
        self.btn_silent.bind(on_press=self.toggle_silent_mode)
        header_layout.add_widget(self.btn_silent)

        spacer1 = Label(size_hint_y=0.05)

        # Label conexiune
        self.conexiune_lbl = Label(
            text="Se conecteaza...",
            font_size='14sp',
            color=(0.5, 0.5, 0.6, 1),
            size_hint_y=0.05,
            halign='center'
        )

        # Label info
        self.info_lbl = Label(
            text="Se initializeaza...",
            font_size='20sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=0.12,
            halign='center'
        )

        # Buton trimite alerta - vizibil doar pentru SALA
        self.btn_panica = ModernButton(
            text="TRIMITE ALERTA",
            btn_color=(0.85, 0.15, 0.15, 1),
            font_size='26sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=0.35,
            disabled=not self.poate_trimite,
            opacity=1 if self.poate_trimite else 0
        )
        self.btn_panica.bind(on_press=self.trimite_alerta)

        # Buton confirma/opreste
        self.btn_stop = ModernButton(
            text="CONFIRMA / OPRESTE",
            btn_color=(0.2, 0.75, 0.3, 1),
            font_size='24sp',
            bold=True,
            color=(1, 1, 1, 1),
            disabled=True,
            opacity=0,
            size_hint_y=0.35
        )
        self.btn_stop.bind(on_press=self.opreste_alarma_global)

        # Buton anulare (pentru expeditor)
        self.btn_anulare = ModernButton(
            text="ANULEAZA ALERTA",
            btn_color=(0.9, 0.5, 0.1, 1),
            font_size='24sp',
            bold=True,
            color=(1, 1, 1, 1),
            disabled=True,
            opacity=0,
            size_hint_y=0.35
        )
        self.btn_anulare.bind(on_press=self.opreste_alarma_global)

        # Buton mute
        self.btn_mute = ModernButton(
            text="MUTE (SUNT IN SEDINTA)",
            btn_color=(0.4, 0.4, 0.5, 1),
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            disabled=True,
            opacity=0,
            size_hint_y=0.18
        )
        self.btn_mute.bind(on_press=self.mute_alarma)

        # Container pentru butoanele din josul ecranului
        bottom_buttons = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=0.08
        )

        # Buton schimba profil
        self.btn_schimba_profil = ModernButton(
            text="Schimba profil",
            btn_color=(0.2, 0.2, 0.25, 1),
            font_size='12sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_x=0.5
        )
        self.btn_schimba_profil.bind(on_press=self.schimba_profil)

        # Buton istoric
        self.btn_istoric = ModernButton(
            text="Istoric",
            btn_color=(0.25, 0.25, 0.35, 1),
            font_size='12sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_x=0.5
        )
        self.btn_istoric.bind(on_press=self.arata_istoric)

        bottom_buttons.add_widget(self.btn_schimba_profil)
        bottom_buttons.add_widget(self.btn_istoric)

        spacer2 = Label(size_hint_y=0.02)

        self.layout.add_widget(header_layout)
        self.layout.add_widget(spacer1)
        self.layout.add_widget(self.conexiune_lbl)
        self.layout.add_widget(self.info_lbl)
        self.layout.add_widget(self.btn_panica)
        self.layout.add_widget(self.btn_stop)
        self.layout.add_widget(self.btn_anulare)
        self.layout.add_widget(self.btn_mute)
        self.layout.add_widget(spacer2)
        self.layout.add_widget(bottom_buttons)

        self.main_layout.add_widget(self.layout)

        # Initializare Android daca profilul era deja salvat
        if platform == 'android' and self.store.exists('profil'):
            Clock.schedule_once(self.init_android, 1)
            Clock.schedule_interval(self.verifica_server, 3)

        return self.main_layout

    def schimba_profil(self, instance):
        """Sterge profilul si revine la ecranul de selectie"""
        if self.store.exists('profil'):
            self.store.delete('profil')

        # Opreste verificarea serverului
        Clock.unschedule(self.verifica_server)

        # Revine la ecranul de profil
        self.root.clear_widgets()
        profile_screen = self.build_profile_screen()
        self.root.add_widget(profile_screen)

    def arata_istoric(self, instance):
        """Afiseaza ecranul cu istoricul alertelor"""
        # Opreste temporar verificarea serverului
        Clock.unschedule(self.verifica_server)

        self.root.clear_widgets()
        istoric_screen = self.build_istoric_screen()
        self.root.add_widget(istoric_screen)

        # Incarca datele din Firebase
        self.incarca_istoric()

    def build_istoric_screen(self):
        """Construieste ecranul de istoric"""
        self.istoric_layout = FloatLayout()

        content = BoxLayout(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(10),
            size_hint=(0.96, 0.96),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=dp(10))

        btn_inapoi = ModernButton(
            text="< Inapoi",
            btn_color=(0.3, 0.3, 0.4, 1),
            font_size='14sp',
            color=(1, 1, 1, 1),
            size_hint_x=0.3
        )
        btn_inapoi.bind(on_press=self.inchide_istoric)

        title = Label(
            text="ISTORIC ALERTE",
            font_size='22sp',
            color=(0.9, 0.9, 0.95, 1),
            bold=True,
            size_hint_x=0.7
        )

        header.add_widget(btn_inapoi)
        header.add_widget(title)

        # Label pentru loading
        self.istoric_loading = Label(
            text="Se incarca istoricul...",
            font_size='16sp',
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=0.1
        )

        # ScrollView pentru lista de istoric
        scroll = ScrollView(size_hint_y=0.8)
        self.istoric_list = BoxLayout(
            orientation='vertical',
            spacing=dp(8),
            size_hint_y=None,
            padding=(0, dp(8))
        )
        self.istoric_list.bind(minimum_height=self.istoric_list.setter('height'))
        scroll.add_widget(self.istoric_list)

        content.add_widget(header)
        content.add_widget(self.istoric_loading)
        content.add_widget(scroll)

        self.istoric_layout.add_widget(content)
        return self.istoric_layout

    def incarca_istoric(self):
        """Incarca istoricul din Firebase"""
        def _load():
            try:
                response = requests.get(FIREBASE_ISTORIC_URL, timeout=10)
                data = response.json()
                Clock.schedule_once(lambda dt: self.afiseaza_istoric(data), 0)
            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.eroare_istoric(str(e)), 0
                )

        threading.Thread(target=_load, daemon=True).start()

    def afiseaza_istoric(self, data):
        """Afiseaza datele din istoric"""
        self.istoric_list.clear_widgets()
        self.istoric_loading.text = ""

        if not data:
            self.istoric_loading.text = "Nu exista istoric"
            return

        # Converteste dict in lista si sorteaza dupa timestamp (descrescator)
        entries = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    value['_key'] = key
                    entries.append(value)

        # Sorteaza descrescator dupa timestamp
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        # Limiteaza la ultimele 50 de intrari
        entries = entries[:50]

        for entry in entries:
            item = self.creeaza_item_istoric(entry)
            self.istoric_list.add_widget(item)

        if not entries:
            self.istoric_loading.text = "Nu exista istoric"

    def creeaza_item_istoric(self, entry):
        """Creeaza un widget pentru o intrare din istoric"""
        item = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(75),
            padding=dp(8)
        )

        # Background
        with item.canvas.before:
            Color(rgba=(0.15, 0.15, 0.2, 1))
            item.bg_rect = RoundedRectangle(pos=item.pos, size=item.size, radius=[dp(8)])
        item.bind(pos=lambda i, p: setattr(i.bg_rect, 'pos', p),
                  size=lambda i, s: setattr(i.bg_rect, 'size', s))

        timestamp = entry.get('timestamp', 'Necunoscut')
        expeditor = entry.get('expeditor', 'Necunoscut')
        confirmat_de = entry.get('confirmat_de', 'Necunoscut')
        tip = entry.get('tip', 'confirmat')

        # Linia 1: Data si ora
        lbl_timp = Label(
            text=f"📅 {timestamp}",
            font_size='14sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            valign='middle',
            size_hint_y=0.4
        )
        lbl_timp.bind(size=lbl_timp.setter('text_size'))

        # Linia 2: Detalii
        if tip == 'anulat':
            detalii = f"🔴 Alerta de la {expeditor} - ANULATA de {confirmat_de}"
            culoare = (1, 0.5, 0.3, 1)
        else:
            detalii = f"🟢 Alerta de la {expeditor} - CONFIRMATA de {confirmat_de}"
            culoare = (0.3, 0.9, 0.4, 1)

        lbl_detalii = Label(
            text=detalii,
            font_size='13sp',
            color=culoare,
            halign='left',
            valign='middle',
            size_hint_y=0.6
        )
        lbl_detalii.bind(size=lbl_detalii.setter('text_size'))

        item.add_widget(lbl_timp)
        item.add_widget(lbl_detalii)

        return item

    def eroare_istoric(self, mesaj):
        """Afiseaza eroare la incarcarea istoricului"""
        self.istoric_loading.text = f"Eroare: {mesaj}"
        self.istoric_loading.color = (1, 0.3, 0.3, 1)

    def inchide_istoric(self, instance):
        """Revine la ecranul principal"""
        self.root.clear_widgets()
        main_screen = self.build_main_screen()
        self.root.add_widget(main_screen)

    def init_android(self, dt):
        """Initializeaza componentele specifice Android"""
        request_permissions([
            Permission.INTERNET,
            Permission.VIBRATE,
            Permission.WAKE_LOCK,
            Permission.FOREGROUND_SERVICE,
            Permission.POST_NOTIFICATIONS,
            Permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
        ])

        Clock.schedule_once(lambda dt: self.start_service(), 2)
        Clock.schedule_once(lambda dt: self.cere_excludere_baterie(), 3)

    def start_service(self):
        if platform == 'android':
            try:
                service = autoclass('org.test.alertasala.ServiceAlertaservice')
                service.start(mActivity, '')
                print("Serviciu background pornit")
            except Exception as e:
                print(f"Eroare pornire serviciu: {e}")

    def stop_service(self):
        if platform == 'android':
            try:
                service = autoclass('org.test.alertasala.ServiceAlertaservice')
                service.stop(mActivity)
                print("Serviciu background oprit")
            except Exception as e:
                print(f"Eroare oprire serviciu: {e}")

    def cere_excludere_baterie(self):
        if platform == 'android':
            try:
                context = mActivity.getApplicationContext()
                package_name = context.getPackageName()
                pm = context.getSystemService(Context.POWER_SERVICE)

                if not pm.isIgnoringBatteryOptimizations(package_name):
                    intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                    intent.setData(Uri.parse(f"package:{package_name}"))
                    mActivity.startActivity(intent)
            except Exception as e:
                print(f"Eroare cerere excludere baterie: {e}")

    def on_pause(self):
        print("Aplicatia in background - serviciul continua")
        return True

    def on_resume(self):
        print("Aplicatia a revenit din background")
        Clock.schedule_once(lambda dt: self.verifica_server(0), 0.5)

    def on_stop(self):
        print("Aplicatia se opreste - serviciul ramane activ")

    def incarca_setari(self):
        try:
            if self.store.exists('silent_mode'):
                self.silent_mode = self.store.get('silent_mode')['enabled']
        except Exception as e:
            print(f"Eroare incarcare setari: {e}")
            self.silent_mode = False

    def salveaza_setari(self):
        try:
            self.store.put('silent_mode', enabled=self.silent_mode)
        except Exception as e:
            print(f"Eroare salvare setari: {e}")

    def toggle_silent_mode(self, instance):
        self.silent_mode = not self.silent_mode
        self.actualizeaza_buton_silent()
        self.salveaza_setari()

    def actualizeaza_buton_silent(self):
        if self.silent_mode:
            self.btn_silent.text = "SILENT ON"
            self.btn_silent.set_color((0.6, 0.3, 0.6, 1))
            self.conexiune_lbl.text = "Mod silentios ACTIV"
            self.conexiune_lbl.color = (0.6, 0.3, 0.6, 1)
        else:
            self.btn_silent.text = "SILENT OFF"
            self.btn_silent.set_color((0.3, 0.3, 0.4, 1))
            if self.conectat:
                self.conexiune_lbl.text = "Conectat"
                self.conexiune_lbl.color = (0.2, 0.8, 0.2, 1)

    def incarca_sunet_alarma(self):
        try:
            base_path = os.path.dirname(os.path.abspath(__file__))
            alarm_wav = os.path.join(base_path, 'alarm.wav')
            alarm_mp3 = os.path.join(base_path, 'alarm.mp3')

            if os.path.exists(alarm_wav):
                self.alarm_sound = SoundLoader.load(alarm_wav)
            elif os.path.exists(alarm_mp3):
                self.alarm_sound = SoundLoader.load(alarm_mp3)
            elif os.path.exists('alarm.wav'):
                self.alarm_sound = SoundLoader.load('alarm.wav')
            elif os.path.exists('alarm.mp3'):
                self.alarm_sound = SoundLoader.load('alarm.mp3')
            else:
                print("Nu s-a gasit fisier alarm.wav/mp3")

            if self.alarm_sound:
                self.alarm_sound.loop = True
                self.alarm_sound.volume = 1.0
        except Exception as e:
            print(f"Eroare incarcare sunet: {e}")

    def trimite_alerta(self, instance):
        self.sunt_expeditor = True
        self.info_lbl.text = "Alerta trimisa, se asteapta confirmare..."
        self.info_lbl.color = (1, 0.7, 0.2, 1)
        self.btn_panica.disabled = True

        def _request():
            try:
                payload = {'status': True, 'cine': self.nume_utilizator}
                response = requests.patch(FIREBASE_URL, json=payload, timeout=10)
                if response.status_code == 200:
                    Clock.schedule_once(lambda dt: self.alerta_trimisa_ok(), 0)
                else:
                    Clock.schedule_once(lambda dt: self.eroare_trimitere("Eroare server"), 0)
            except requests.exceptions.Timeout:
                Clock.schedule_once(lambda dt: self.eroare_trimitere("Timeout"), 0)
            except requests.exceptions.ConnectionError:
                Clock.schedule_once(lambda dt: self.eroare_trimitere("Fara conexiune"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.eroare_trimitere(str(e)), 0)

        threading.Thread(target=_request, daemon=True).start()

    def alerta_trimisa_ok(self):
        self.info_lbl.text = "Alerta trimisa! Se asteapta confirmare..."
        self.info_lbl.color = (1, 0.7, 0.2, 1)

    def eroare_trimitere(self, mesaj):
        self.info_lbl.text = f"Eroare: {mesaj}"
        self.info_lbl.color = (1, 0.3, 0.3, 1)
        if self.poate_trimite:
            self.btn_panica.disabled = False
        self.sunt_expeditor = False

    def verifica_server(self, dt):
        def _check():
            # Nu verifica dacă se procesează oprirea (previne race condition)
            if self.se_proceseaza_oprire:
                return

            try:
                response = requests.get(FIREBASE_URL, timeout=10)
                data = response.json()

                self.erori_consecutive = 0
                Clock.schedule_once(lambda dt: self.actualizeaza_stare_conexiune(True), 0)

                if data:
                    status = data.get('status', False)
                    cine = data.get('cine', 'Necunoscut')

                    # Verificare suplimentară pentru a preveni re-trigger
                    if status == True and not self.se_proceseaza_oprire:
                        self.activeaza_alarma_pe_ui(cine)
                    elif status == False and self.alerta_activa:
                        self.dezactiveaza_alarma_pe_ui()
                    elif status == False and not self.alerta_activa and not self.conectat:
                        Clock.schedule_once(lambda dt: self.prima_conectare(), 0)

            except requests.exceptions.Timeout:
                self.erori_consecutive += 1
                Clock.schedule_once(lambda dt: self.actualizeaza_stare_conexiune(False, "Timeout"), 0)
            except requests.exceptions.ConnectionError:
                self.erori_consecutive += 1
                Clock.schedule_once(lambda dt: self.actualizeaza_stare_conexiune(False, "Fara conexiune"), 0)
            except Exception as e:
                self.erori_consecutive += 1
                Clock.schedule_once(lambda dt: self.actualizeaza_stare_conexiune(False, str(e)[:30]), 0)

        threading.Thread(target=_check, daemon=True).start()

    def actualizeaza_stare_conexiune(self, conectat, eroare=None):
        self.conectat = conectat
        if conectat:
            if not self.alerta_activa:
                self.status_indicator.set_status('connected')
            if self.silent_mode:
                self.conexiune_lbl.text = "Mod silentios ACTIV"
                self.conexiune_lbl.color = (0.6, 0.3, 0.6, 1)
            else:
                self.conexiune_lbl.text = "Conectat"
                self.conexiune_lbl.color = (0.2, 0.8, 0.2, 1)
        else:
            self.status_indicator.set_status('disconnected')
            self.conexiune_lbl.text = f"Deconectat: {eroare}" if eroare else "Deconectat"
            self.conexiune_lbl.color = (1, 0.3, 0.3, 1)

    def prima_conectare(self):
        if self.poate_trimite:
            self.info_lbl.text = "Totul e in siguranta"
            self.btn_panica.disabled = False
            self.btn_panica.opacity = 1
        else:
            self.info_lbl.text = "Astept alerte..."
        self.info_lbl.color = (0.6, 0.6, 0.7, 1)
        self.actualizeaza_buton_silent()

    def mute_alarma(self, instance):
        self.is_muted = True

        if self.alarm_sound:
            self.alarm_sound.stop()

        if hasattr(self, 'vibratie_event'):
            self.vibratie_event.cancel()

        self.btn_mute.text = "MUTED"
        self.btn_mute.set_color((0.3, 0.3, 0.35, 1))
        self.btn_mute.disabled = True

        self.info_lbl.text = f"{self.info_lbl.text}\n(Sunet oprit)"

    def opreste_alarma_global(self, instance):
        # Previne double-click și race condition
        if self.se_proceseaza_oprire:
            return
        self.se_proceseaza_oprire = True

        # Salveaza in istoric cine a confirmat
        expeditor_alerta = getattr(self, 'expeditor_curent', 'Necunoscut')
        era_expeditor = self.sunt_expeditor  # Salvăm înainte de reset

        # Oprește sunetul și vibrația imediat
        if self.alarm_sound:
            self.alarm_sound.stop()
        if hasattr(self, 'vibratie_event'):
            try:
                self.vibratie_event.cancel()
            except:
                pass

        def _reset():
            try:
                # IMPORTANT: Resetează Firebase PRIMUL
                requests.patch(FIREBASE_URL, json={'status': False, 'cine': ''}, timeout=10)

                # Apoi salvează în istoric
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                istoric_entry = {
                    'timestamp': timestamp,
                    'expeditor': expeditor_alerta,
                    'confirmat_de': self.nume_utilizator,
                    'tip': 'anulat' if era_expeditor else 'confirmat'
                }
                requests.post(FIREBASE_ISTORIC_URL, json=istoric_entry, timeout=10)

                # Actualizează UI-ul DUPĂ ce Firebase e resetat
                Clock.schedule_once(lambda dt: self._finalizeaza_oprire(), 0)
            except Exception as e:
                print(f"Eroare salvare istoric: {e}")
                # Chiar dacă e eroare, resetăm UI-ul
                Clock.schedule_once(lambda dt: self._finalizeaza_oprire(), 0)

        threading.Thread(target=_reset, daemon=True).start()

    def _finalizeaza_oprire(self):
        """Finalizează oprirea alertei după ce Firebase a fost resetat"""
        self.dezactiveaza_alarma_pe_ui()
        # Resetăm flag-ul după un scurt delay pentru siguranță
        Clock.schedule_once(lambda dt: setattr(self, 'se_proceseaza_oprire', False), 1)

    def activeaza_alarma_pe_ui(self, nume_expeditor):
        Clock.schedule_once(lambda dt: self._interfata_alerta(nume_expeditor), 0)

    def dezactiveaza_alarma_pe_ui(self):
        Clock.schedule_once(lambda dt: self._interfata_normala(), 0)

    def _interfata_alerta(self, nume):
        # Previne re-trigger în timpul procesării opririi
        if self.se_proceseaza_oprire:
            return

        if self.alerta_activa:
            return

        self.alerta_activa = True
        self.expeditor_curent = nume  # Salvam pentru istoric
        self.ultima_alerta_expeditor = nume  # Memorăm expeditorul
        self.status_indicator.set_status('alert')

        # Verificam daca suntem expeditorul (verificare îmbunătățită)
        # Verificăm atât flag-ul cât și numele pentru siguranță
        este_propria_alerta = (nume == self.nume_utilizator)
        if este_propria_alerta and (self.sunt_expeditor or self.poate_trimite):
            self.info_lbl.text = "Alerta trimisa, se asteapta confirmare..."
            self.info_lbl.color = (1, 0.7, 0.2, 1)
            self.info_lbl.font_size = '22sp'

            self.btn_anulare.disabled = False
            self.btn_anulare.opacity = 1
            self.btn_panica.disabled = True
            self.btn_panica.opacity = 0
            return

        # Verificam daca e modul silentios
        if self.silent_mode:
            self.info_lbl.text = f"Alerta de la: {nume}\n(Mod silentios activ)"
            self.info_lbl.color = (1, 0.5, 0.5, 1)
            self.info_lbl.font_size = '18sp'
            self.info_lbl.bold = False

            self.btn_stop.disabled = False
            self.btn_stop.opacity = 1
            self.btn_panica.disabled = True
            self.btn_panica.opacity = 0
            return

        # Alarma completa pentru receptori
        Window.clearcolor = (0.15, 0.02, 0.02, 1)

        self.status_lbl.text = f"{self.nume_utilizator}"
        self.status_lbl.color = (1, 0.3, 0.3, 1)
        self.info_lbl.text = f"ALERTA DE LA: {nume}"
        self.info_lbl.color = (1, 0.9, 0.2, 1)
        self.info_lbl.font_size = '24sp'
        self.info_lbl.bold = True

        self.btn_stop.disabled = False
        self.btn_stop.opacity = 1
        self.btn_mute.disabled = False
        self.btn_mute.opacity = 1
        self.btn_mute.text = "MUTE (SUNT IN SEDINTA)"
        self.btn_mute.set_color((0.4, 0.4, 0.5, 1))
        self.btn_panica.disabled = True
        self.btn_panica.opacity = 0

        if not self.is_muted:
            if self.alarm_sound:
                self.alarm_sound.play()
            self.vibratie_event = Clock.schedule_interval(self.vibreaza_hardware, 2)

        self.pulse_event = Clock.schedule_interval(self.pulse_stop_button, 0.8)

        if platform == 'android':
            self.wake_screen()

    def wake_screen(self):
        if platform == 'android':
            try:
                pm = mActivity.getSystemService(Context.POWER_SERVICE)
                wake_lock = pm.newWakeLock(
                    PowerManager.FULL_WAKE_LOCK |
                    PowerManager.ACQUIRE_CAUSES_WAKEUP |
                    PowerManager.ON_AFTER_RELEASE,
                    "AlertaApp::WakeScreen"
                )
                wake_lock.acquire(10000)
            except Exception as e:
                print(f"Eroare wake screen: {e}")

    def _interfata_normala(self):
        if not self.alerta_activa:
            return

        self.alerta_activa = False
        self.sunt_expeditor = False
        self.is_muted = False
        self.ultima_alerta_expeditor = ""  # Resetăm expeditorul
        Window.clearcolor = self.culoare_originala

        self.status_lbl.text = f"{self.nume_utilizator}"
        self.status_lbl.color = (0.9, 0.9, 0.95, 1)
        if self.poate_trimite:
            self.info_lbl.text = "Totul e in siguranta"
        else:
            self.info_lbl.text = "Astept alerte..."
        self.info_lbl.color = (0.6, 0.6, 0.7, 1)
        self.info_lbl.font_size = '20sp'
        self.info_lbl.bold = False

        self.status_indicator.set_status('connected')

        if self.alarm_sound:
            self.alarm_sound.stop()

        self.btn_stop.disabled = True
        self.btn_stop.opacity = 0
        self.btn_anulare.disabled = True
        self.btn_anulare.opacity = 0
        self.btn_mute.disabled = True
        self.btn_mute.opacity = 0

        if self.poate_trimite:
            self.btn_panica.disabled = False
            self.btn_panica.opacity = 1

        self.actualizeaza_buton_silent()

        if hasattr(self, 'pulse_event'):
            self.pulse_event.cancel()
        if hasattr(self, 'vibratie_event'):
            self.vibratie_event.cancel()

    def pulse_stop_button(self, dt):
        if self.btn_stop.opacity == 1:
            self.btn_stop.opacity = 0.7
        else:
            self.btn_stop.opacity = 1

    def vibreaza_hardware(self, dt):
        if self.is_muted:
            return
        try:
            vibrator.vibrate(1)
        except NotImplementedError:
            print("Bzzzt! (Vibratie simulata pe PC)")
        except Exception as e:
            print(f"Eroare vibratie: {e}")


if __name__ == '__main__':
    AlertaApp().run()
