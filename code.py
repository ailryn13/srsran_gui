#!/usr/bin/env python3
import gi, os, signal, subprocess, threading, re, time
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'

# --- FIX: Handling WebKit Version Compatibility ---
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    try:
        gi.require_version("WebKit2", "4.0")
    except ValueError:
        print("Error: WebKit2 not found. Please install: sudo apt install gir1.2-webkit2-4.0")
        exit(1)

from gi.repository import WebKit2
from gi.repository import Gtk, Gdk, Vte, GLib, Pango
from datetime import datetime

PLAY_SYMBOL = "\u25B6"  # ▶
STOP_SYMBOL = "\u25A0"   # ■

class SrsRanGuiApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="srsRAN 5G Test Bed")
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)
        self.set_default_size(1100, 750)
        self.setup_css()
        self.terminals = {}

        # Runtime control state
        self.gnb_running = False
        self.gnb_terminal_ref = None
        self.gnb_button_ref = None
        
        self.ue_running = False
        self.ue_terminal_ref = None
        self.ue_button_ref = None
        
        self.tshark_running = False
        self.tshark_terminal_ref = None
        self.tshark_button_ref = None
        self.tshark_scheduler_id = None

        self.core_running = False
        self.core_button_ref = None
        self.core_terminal_ref = None

        # Determine desktop path for captures
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            home_dir = os.path.expanduser(f'~{sudo_user}')
            desktop_path = os.path.join(home_dir, 'Desktop')
        else:
            desktop_path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)

        self.capture_folder_path = os.path.join(desktop_path, "srsRAN_Captures")
        
        self.is_terminal_position_set = False

        # Scheduler IDs
        self.gnb_command_scheduler_id = None
        self.ue_command_scheduler_id = None
        self.core_monitor_scheduler_id = None 
        self.gnb_config_scheduler_id = None
        self.ue_config_scheduler_id = None
        self.core_scheduler_id = None
        
        self.webview_container = None
        self.original_content_pane = None
        self.current_menu_index = None
        
        # IP State (Removed extra IPs)
        self.gnb_link_ip = "<N/A>"
        self.ue_ip = "<N/A>"
        self.core_ip = "127.0.0.1"
        
        # Main layout
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.paned)

        # Sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_menu_items = ["Network Overview", "5G Core Network", "gNB", "User Equipment"]
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        for title in self.main_menu_items:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=title, xalign=0)
            label.get_style_context().add_class("big-menu-label")
            row.add(label)
            self.listbox.add(row)
        self.listbox.connect("row-selected", self.on_menu_selected)
        sidebar.pack_start(self.listbox, True, True, 0)

        sidebar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, True, 8)
        
        # License button removed
        # self.license_btn = Gtk.Button(label="License")
        # self.license_btn.get_style_context().add_class("big-menu-label")
        # self.license_btn.connect("clicked", self.on_license_selected)
        # sidebar.pack_end(self.license_btn, False, False, 10)
        self.paned.pack1(sidebar, resize=False, shrink=False)

        # Content Area
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.content_paned.connect("size-allocate", self.on_content_paned_allocated)
        self.paned.pack2(self.content_paned, resize=True, shrink=False)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_paned.pack1(self.content_box, resize=True, shrink=False)

        # Terminal Notebook
        self.terminal_notebook = Gtk.Notebook()
        self.terminal_notebook.set_scrollable(True)
        self.terminal_notebook.hide()
        self.default_terminal_pane_position=260
        self.content_paned.pack2(self.terminal_notebook, resize=True, shrink=False)

        self.paned.set_position(280)
        self.listbox.select_row(self.listbox.get_row_at_index(0))
        
        GLib.timeout_add_seconds(2, self._check_process_status)
        self.show_all()
        
    def on_content_paned_allocated(self, widget, allocation):
        if not self.is_terminal_position_set and self.terminal_notebook.is_visible() and allocation.height > 0:
            widget.set_position(self.default_terminal_pane_position)
            self.is_terminal_position_set = True

    def setup_css(self):
        css = b"""
        .big-menu-label { font-size: 16px; padding: 8px; }
        .header-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; }
        .content-box { border-radius: 6px; padding: 10px; background-color: #2E3440; }
        .start-button { background: #2ecc71; color: white; font-weight: bold; }
        .stop-button { background: #e74c3c; color: white; font-weight: bold; }
        .active-submenu { background: orange; color: white; font-weight: bold; }
        .terminal-style { font-family: monospace; }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_menu_selected(self, listbox, row):
        if not row or row.get_index() == self.current_menu_index:
            return
        
        protected_keys = ["gnb", "ue", "tshark", "core"]
        for key in list(self.terminals.keys()):
            if key not in protected_keys:
                if key == "tshark" and self.tshark_running:
                    self.toggle_tshark_process(None)
                
                terminal_info = self.terminals.pop(key, None)
                if terminal_info:
                    frame = terminal_info['frame']
                    page_num = self.terminal_notebook.page_num(frame)
                    if page_num != -1:
                        self.terminal_notebook.remove_page(page_num)

        new_index = row.get_index()
        self._restore_main_view()
        self.current_menu_index = new_index

        section = self.main_menu_items[new_index]
        if section == "Network Overview":
            self.content_paned.set_position(self.default_terminal_pane_position)
        else:
            def hide_terminal_pane():
                allocation = self.content_paned.get_allocation()
                if allocation.height > 0:
                    self.content_paned.set_position(allocation.height)
                return False
            GLib.idle_add(hide_terminal_pane)

        if row:
            for child in self.content_box.get_children():
                if child != self.terminal_notebook:
                    self.content_box.remove(child)

            if section == "Network Overview":
                self.show_network_overview()
            elif section == "5G Core Network":
                self.show_core_menu()
            elif section == "gNB":
                self.show_gnb_menu()
            elif section == "User Equipment":
                self.show_ue_menu()
            self.content_box.show_all()
        
    # License logic removed

    def make_submenu_click_handler(self, button_list, clicked_button, callback):
        def handler(_):
            for b in button_list:
                b.get_style_context().remove_class("active-submenu")
            clicked_button.get_style_context().add_class("active-submenu")
            callback(None)
        return handler

    def add_toolbar_with_content(self, items, content_attr, button_list_attr):
        vbox_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hbox_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox_buttons.set_margin_top(15)
        hbox_buttons.set_margin_start(15)

        btn_list = []
        for title, handler in items:
            btn = Gtk.Button(label=title)
            btn.set_size_request(150, 40)
            btn.get_style_context().add_class("big-menu-label")
            btn.connect("clicked", self.make_submenu_click_handler(btn_list, btn, handler))
            btn_list.append(btn)
            hbox_buttons.pack_start(btn, False, False, 0)

        setattr(self, button_list_attr, btn_list)
        vbox_main.pack_start(hbox_buttons, False, False, 0)

        setattr(self, content_attr, Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10))
        getattr(self, content_attr).set_margin_start(15)
        getattr(self, content_attr).set_margin_top(10)
        vbox_main.pack_start(getattr(self, content_attr), True, True, 0)
        self.content_box.pack_start(vbox_main, True, True, 0)

    # -------------------------------------------------------------------------
    # NETWORK OVERVIEW - MODIFIED LAYOUT
    # -------------------------------------------------------------------------
    def show_network_overview(self):
        for child in self.content_box.get_children():
            self.content_box.remove(child)

        # Create a single row with 4 distinct columns
        hbox_columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        hbox_columns.set_homogeneous(True)
        hbox_columns.set_margin_start(15)
        hbox_columns.set_margin_end(15)
        hbox_columns.set_margin_top(20)

        # --- Column 1: UE ---
        vbox_ue = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.create_ue_control_ui(vbox_ue)
        hbox_columns.pack_start(vbox_ue, True, True, 0)

        # --- Column 2: gNB ---
        vbox_gnb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.create_gnb_control_ui(vbox_gnb)
        hbox_columns.pack_start(vbox_gnb, True, True, 0)

        # --- Column 3: 5G Core ---
        vbox_core = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.create_core_control_ui(vbox_core)
        hbox_columns.pack_start(vbox_core, True, True, 0)

        # --- Column 4: Tshark ---
        vbox_tshark = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.create_tshark_control_ui(vbox_tshark)
        hbox_columns.pack_start(vbox_tshark, True, True, 0)

        self.content_box.pack_start(hbox_columns, False, False, 0)
        self.content_box.show_all()

    def create_title(self, text):
        lbl = Gtk.Label(label=text)
        lbl.get_style_context().add_class("header-title")
        lbl.set_halign(Gtk.Align.CENTER)
        return lbl

    def create_ue_control_ui(self, parent_box):
        parent_box.pack_start(self.create_title("User Equipment (UE)"), False, False, 0)
        
        # IP Display Frame (REMOVED: gNB Search IP)
        ip_frame = Gtk.Frame()
        self.ue_ip_label = Gtk.Label(label=f"UE IP: {self.ue_ip}")
        # --- FIX: Replaced set_padding with set_margin_* ---
        self.ue_ip_label.set_margin_top(10)
        self.ue_ip_label.set_margin_bottom(10)
        self.ue_ip_label.set_margin_start(10)
        self.ue_ip_label.set_margin_end(10)
        
        ip_frame.add(self.ue_ip_label)
        parent_box.pack_start(ip_frame, False, False, 5)

        # Start Button
        self.ue_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start UE")
        self.ue_button_ref.get_style_context().add_class("start-button")
        if self.ue_running:
            self.ue_button_ref.set_label(f"{STOP_SYMBOL} Stop UE")
            self.ue_button_ref.get_style_context().add_class("stop-button")
        self.ue_button_ref.connect("clicked", self.toggle_ue_process)
        parent_box.pack_start(self.ue_button_ref, False, False, 5)

    def create_tshark_control_ui(self, parent_box):
        parent_box.pack_start(self.create_title("Tshark Capture"), False, False, 0)

        # Open Folder Button (Below Start)
        open_folder_btn = Gtk.Button(label="Open Capture Folder")
        open_folder_btn.connect("clicked", self.on_open_capture_folder_clicked)
        parent_box.pack_start(open_folder_btn, False, False, 8)

        # Start Button
        self.tshark_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start Tshark")
        self.tshark_button_ref.get_style_context().add_class("start-button")
        if self.tshark_running:
            self.tshark_button_ref.set_label(f"{STOP_SYMBOL} Stop Tshark")
            self.tshark_button_ref.get_style_context().add_class("stop-button")
        self.tshark_button_ref.connect("clicked", self.toggle_tshark_process)
        parent_box.pack_start(self.tshark_button_ref, False, False, 5)

    def create_gnb_control_ui(self, parent_box):
        parent_box.pack_start(self.create_title("gNB"), False, False, 0)
        
        # IP Display Frame (REMOVED: NGAP IP)
        ip_frame = Gtk.Frame()
        self.gnb_ip_label = Gtk.Label(label=f"Link IP: {self.gnb_link_ip}")
        # --- FIX: Replaced set_padding with set_margin_* ---
        self.gnb_ip_label.set_margin_top(10)
        self.gnb_ip_label.set_margin_bottom(10)
        self.gnb_ip_label.set_margin_start(10)
        self.gnb_ip_label.set_margin_end(10)
        
        ip_frame.add(self.gnb_ip_label)
        parent_box.pack_start(ip_frame, False, False, 5)

        # Start Button
        self.gnb_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start gNB")
        self.gnb_button_ref.get_style_context().add_class("start-button")
        if self.gnb_running:
            self.gnb_button_ref.set_label(f"{STOP_SYMBOL} Stop gNB")
            self.gnb_button_ref.get_style_context().add_class("stop-button")
        self.gnb_button_ref.connect("clicked", self.toggle_gnb_process)
        parent_box.pack_start(self.gnb_button_ref, False, False, 5)

        # Web UI Button (Added below Start)
        gnb_webui_btn = Gtk.Button(label="Web UI")
        gnb_webui_btn.get_style_context().add_class("start-button")
        gnb_webui_btn.connect("clicked", self.on_gnb_webview)
        parent_box.pack_start(gnb_webui_btn, False, False, 5)

    def create_core_control_ui(self, parent_box):
        parent_box.pack_start(self.create_title("5G Core"), False, False, 0)
        
        # IP Display Frame
        ip_frame = Gtk.Frame()
        self.core_ip_label = Gtk.Label(label=f"Core IP: {self.core_ip}")
        
        # Apply margins
        self.core_ip_label.set_margin_top(10)
        self.core_ip_label.set_margin_bottom(10)
        self.core_ip_label.set_margin_start(10)
        self.core_ip_label.set_margin_end(10)
        
        ip_frame.add(self.core_ip_label)
        parent_box.pack_start(ip_frame, False, False, 5)

        # "Start" Button (Core Toggle)
        self.core_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start 5G Core")
        self.core_button_ref.get_style_context().add_class("start-button")
        if self.core_running:
            self.core_button_ref.set_label(f"{STOP_SYMBOL} Stop 5G Core")
            self.core_button_ref.get_style_context().add_class("stop-button")
        self.core_button_ref.connect("clicked", self.toggle_core_process)
        parent_box.pack_start(self.core_button_ref, False, False, 5)

        # Web UI Button (Added below Start)
        webui_btn = Gtk.Button(label="Web UI")
        webui_btn.get_style_context().add_class("start-button")
        webui_btn.connect("clicked", self.on_core_webui)
        parent_box.pack_start(webui_btn, False, False, 5)

    def toggle_core_process(self, _):
        if not self.core_running:
            terminal = self.create_terminal_tab("core", "5G Core Console")
            terminal.connect("child-exited", self.on_process_exited, "core")
            self.core_terminal_ref = terminal
            
            ctx = self.core_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.core_button_ref.set_label(f"{STOP_SYMBOL} Stop 5G Core")

            def startup_complete():
                self.core_running = True

            # Placeholder sequential commands
            # User can update this list with actual commands like:
            # "cd ~/open5gs", "docker-compose up -d", etc.
            commands = [
                "echo 'Starting 5G Core Sequence...'",
                "sleep 1",
                "echo 'Running Step 1 (Placeholder)...'",
                "sleep 1", 
                "echo '5G Core Started (Placeholder)'"
            ]
            
            self._send_commands_sequentially(
                terminal,
                commands,
                "core_scheduler_id",
                delay=1000,
                on_complete=startup_complete
            )
        else:
            if self.core_scheduler_id:
                GLib.source_remove(self.core_scheduler_id)
                self.core_scheduler_id = None
            
            if self.core_terminal_ref:
                self.core_terminal_ref.feed_child(b'\x03') # Ctrl+C
                # Optional: Send specific stop command if Ctrl+C isn't enough
                # self.core_terminal_ref.feed_child(b'docker-compose down\n')
            
            self.reset_core_button()

    def reset_core_button(self):
        self.core_running = False
        def update_ui():
            if self.core_button_ref:
                ctx = self.core_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.core_button_ref.set_label(f"{PLAY_SYMBOL} Start 5G Core")
        GLib.idle_add(update_ui)

    # -------------------------------------------------------------------------
    # PROCESS LOGIC
    # -------------------------------------------------------------------------

    def _show_alert(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Startup Order Error",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def toggle_gnb_process(self, _):
        if not self.gnb_running:
            if not self.core_running:
                self._show_alert("Please start the 5G Core Network first.")
                return

            terminal = self.create_terminal_tab("gnb", "gNB Console")
            terminal.connect("child-exited", self.on_process_exited, "gnb")
            self.gnb_terminal_ref = terminal
            
            ctx = self.gnb_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.gnb_button_ref.set_label(f"{STOP_SYMBOL} Stop gNB")

            def startup_complete():
                self.gnb_running = True
                self.fetch_and_display_gnb_ips()

            # srsRAN 5G typically uses a config file (gnb.yaml or gnb.conf)
            # Adjust path as needed: ~/srsRAN_Project/build/gnb
            commands = [
                "echo 'Starting gNB...'",
                "cd ~/srsRAN_Project/build",
                "sudo ./gnb -c gnb.yaml"
            ]
            self._send_commands_sequentially(
                terminal,
                commands,
                "gnb_command_scheduler_id",
                delay=1000,
                on_complete=startup_complete
            )
        else:
            if self.ue_running:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text="UE is Still Active",
                )
                dialog.format_secondary_text(
                    "Please stop the User Equipment (UE) before stopping the gNB."
                )
                dialog.run()
                dialog.destroy()
                return 
            
            if self.gnb_command_scheduler_id:
                GLib.source_remove(self.gnb_command_scheduler_id)
                self.gnb_command_scheduler_id = None
            if self.gnb_terminal_ref:
                self.gnb_terminal_ref.feed_child(b'\x03') # Ctrl+C
            self.reset_gnb_button()

    def toggle_ue_process(self, _):
        if not self.ue_running:
            if not self.gnb_running:
                self._show_alert("Please start the gNB first.")
                return



            terminal = self.create_terminal_tab("ue", "UE Console")
            terminal.connect("child-exited", self.on_process_exited, "ue")
            self.ue_terminal_ref = terminal

            ctx = self.ue_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.ue_button_ref.set_label(f"{STOP_SYMBOL} Stop UE")

            def startup_complete():
                self.ue_running = True
                self.fetch_and_display_ue_ips()

            # srsRAN 5G UE command
            commands = [
                "echo 'Starting UE...'",
                "cd ~/srsRAN_Project/build",
                "sudo ./ue -c ue.yaml"
            ]
            self._send_commands_sequentially(
                terminal,
                commands,
                "ue_command_scheduler_id",
                delay=1000,
                on_complete=startup_complete
            )
        else:
            if self.ue_command_scheduler_id:
                GLib.source_remove(self.ue_command_scheduler_id)
                self.ue_command_scheduler_id = None
            if self.ue_terminal_ref:
                self.ue_terminal_ref.feed_child(b'\x03')
            self.reset_ue_button()

    def toggle_tshark_process(self, _):
        # Create folder if missing
        if not os.path.exists(self.capture_folder_path):
            os.makedirs(self.capture_folder_path)

        if not self.tshark_running:
            terminal = self.create_terminal_tab("tshark", "Tshark Capture")
            terminal.connect("child-exited", self.on_process_exited, "tshark")
            self.tshark_terminal_ref = terminal
            
            ctx = self.tshark_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.tshark_button_ref.set_label(f"{STOP_SYMBOL} Stop Tshark")
            
            def startup_complete():
                self.tshark_running = True

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"srs_capture_{timestamp}.pcap"
            full_path = os.path.join(self.capture_folder_path, filename)
            
            # Capture filter tailored for srsRAN/Open5GS common protocols
            commands = [f'exec sudo tshark -i any -w {full_path}']
            
            self._send_commands_sequentially(
                terminal, 
                commands, 
                "tshark_scheduler_id",
                on_complete=startup_complete
            )
        else:
            if self.tshark_scheduler_id:
                GLib.source_remove(self.tshark_scheduler_id)
                self.tshark_scheduler_id = None

            if self.tshark_terminal_ref:
                self.tshark_terminal_ref.feed_child(b'\x03')
            self.reset_tshark_button()

    def on_open_capture_folder_clicked(self, button):
        try:
            os.makedirs(self.capture_folder_path, exist_ok=True)
            sudo_user = os.environ.get('SUDO_USER')
            command_to_run = ['/usr/bin/xdg-open', self.capture_folder_path]
            if sudo_user:
                command_to_run = ['sudo', '-u', sudo_user] + command_to_run
            subprocess.Popen(command_to_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Error opening folder: {e}")

    # -------------------------------------------------------------------------
    # IP & STATUS HELPERS
    # -------------------------------------------------------------------------
    def fetch_and_display_gnb_ips(self):
        def worker_thread():
            link_ip = "<N/A>"
            try:
                # srsRAN config parsing (Adjust grep pattern based on your .yaml or .conf)
                # Assuming srsRAN Project YAML structure
                cmd_link = "grep 'addr:' ~/srsRAN_Project/build/gnb.yaml | head -1 | awk '{print $2}'"
                proc_link = subprocess.run(cmd_link, shell=True, capture_output=True, text=True)
                if proc_link.stdout: link_ip = proc_link.stdout.strip()
                
                # Removed NGAP IP fetching as requested

            except Exception:
                pass

            def update_gui():
                self.gnb_link_ip = link_ip
                if hasattr(self, 'gnb_ip_label'):
                    self.gnb_ip_label.set_text(f"Link IP: {self.gnb_link_ip}")
            
            GLib.idle_add(update_gui)
        threading.Thread(target=worker_thread, daemon=True).start()
        
    def reset_gnb_ip_display(self):
        self.gnb_link_ip = "<N/A>"
        def update_gui():
            if hasattr(self, 'gnb_ip_label'):
                self.gnb_ip_label.set_text("Link IP: <N/A>")
        GLib.idle_add(update_gui)
        
    def fetch_and_display_ue_ips(self):
        def worker_thread():
            ue_ip = "<N/A>"
            try:
                # Get IP assigned to tun_srsue interface
                for _ in range(5):
                    cmd_ue = "ip -4 addr show tun_srsue | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"
                    proc_ue = subprocess.run(cmd_ue, shell=True, capture_output=True, text=True)
                    if proc_ue.stdout:
                        ue_ip = proc_ue.stdout.strip()
                        break
                    time.sleep(2)
            except Exception:
                pass

            def update_gui():
                self.ue_ip = ue_ip
                # Removed gNB Search IP fetching as requested
                if hasattr(self, 'ue_ip_label'):
                    self.ue_ip_label.set_text(f"UE IP: {self.ue_ip}")
            
            GLib.idle_add(update_gui)
        threading.Thread(target=worker_thread, daemon=True).start()

    def reset_ue_ip_display(self):
        def update_gui():
            if hasattr(self, 'ue_ip_label'):
                self.ue_ip_label.set_text("UE IP: <N/A>")
        GLib.idle_add(update_gui)

    def reset_gnb_button(self):
        self.gnb_running = False
        self.reset_gnb_ip_display()
        def update_ui():
            if self.gnb_button_ref:
                ctx = self.gnb_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.gnb_button_ref.set_label(f"{PLAY_SYMBOL} Start gNB")
        GLib.idle_add(update_ui)

    def reset_ue_button(self):
        self.ue_running = False
        self.reset_ue_ip_display()
        def update_ui():
            if self.ue_button_ref:
                ctx = self.ue_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.ue_button_ref.set_label(f"{PLAY_SYMBOL} Start UE")
        GLib.idle_add(update_ui)

    def reset_tshark_button(self):
        self.tshark_running = False
        def update_ui():
            if self.tshark_button_ref:
                ctx = self.tshark_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.tshark_button_ref.set_label(f"{PLAY_SYMBOL} Start Tshark")
        GLib.idle_add(update_ui)

    def on_process_exited(self, _terminal, _exit_status, key):
        if key == "gnb" and self.gnb_running:
            self.reset_gnb_button()
        elif key == "ue" and self.ue_running:
            self.reset_ue_button()
        elif key == "tshark" and self.tshark_running:
            self.reset_tshark_button()
        elif key == "core" and self.core_running:
            self.reset_core_button()

    def _check_process_status(self):
        # Watchdog to reset buttons if process crashes
        processes = {
            'gnb': (self.gnb_running, self.handle_gnb_stopped_unexpectedly, "./gnb"),
            'ue': (self.ue_running, self.reset_ue_button, "./ue"),
            'tshark': (self.tshark_running, self.reset_tshark_button, "tshark")
        }
        for key, (running, func, ptrn) in processes.items():
            if running:
                try:
                    subprocess.run(['pgrep', '-f', ptrn], check=True, stdout=subprocess.DEVNULL)
                except:
                    GLib.idle_add(func)
        return True

    def handle_gnb_stopped_unexpectedly(self):
        self.reset_gnb_button()
        if self.ue_running:
            self.toggle_ue_process(None) # Auto stop UE if gNB dies

    # -------------------------------------------------------------------------
    # SUBMENU LOGIC
    # -------------------------------------------------------------------------
    def show_core_menu(self):
        items = [
            ("Docker", self.on_core_docker_menu),
            ("Config", self.on_core_config),
            ("Logs", self.on_core_logs),
            ("Web UI", self.on_core_webui)
        ]
        self.add_toolbar_with_content(items, "core_area", "core_buttons")

    def on_core_docker_menu(self, _):
        """
        Fetches 'docker ps' output and displays it in a read-only tab.
        """
        # Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # Clear previous content in the core area
        box = self.core_area
        for child in box.get_children():
            box.remove(child)

        # Create the tab using the existing helper
        text_buffer = self.create_textview_tab("docker_view", "Docker Status")
        text_buffer.set_text("Fetching Docker status...")

        def worker():
            # Run docker ps with a clean table format
            cmd = 'docker ps -a --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"'
            try:
                # Try running as current user
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                # If that fails (permission denied), try sudo
                if res.returncode != 0 or "permission denied" in res.stderr.lower():
                    cmd = 'sudo ' + cmd
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                output = res.stdout if res.stdout else "No Docker containers found or Docker is not running."
            except Exception as e:
                output = f"Error fetching Docker stats: {str(e)}"
            
            GLib.idle_add(text_buffer.set_text, output)

        threading.Thread(target=worker, daemon=True).start()

    def show_gnb_menu(self):
        items = [
            ("Config", self.on_gnb_config),
            ("Logs", self.on_gnb_logs),
            ("Web UI", self.on_gnb_webui),
            ("Pcap", self.on_gnb_pcap),
        ]
        self.add_toolbar_with_content(items, "gnb_area", "gnb_buttons")

    def show_ue_menu(self):
        items = [
            ("Config", self.on_ue_config),
            ("Logs", self.on_ue_logs),
            ("Web UI", self.on_ue_webui),
            ("Pcap", self.on_ue_pcap),
        ]
        self.add_toolbar_with_content(items, "ue_area", "ue_buttons")

    def on_gnb_logs(self, _):
        # List .log files in build directory
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        
        log_dir = os.path.expanduser("~/srsRAN_Project/build")
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
        else: files = []
        
        box = self.gnb_area
        for c in box.get_children(): box.remove(c)
        
        listbox = Gtk.ListBox()
        if not files:
            row = Gtk.ListBoxRow()
            row.add(Gtk.Label(label="No logs found in ~/srsRAN_Project/build"))
            listbox.add(row)
        else:
            for f in files:
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f, xalign=0)
                # Use a specific handler for gNB logs if needed, reusing core log viewer for now
                # assuming we want to view them. on_log_file_clicked uses /var/log/open5gs...
                # Need a new handler or make on_log_file_clicked generic.
                # Let's make a generic viewer.
                btn.connect("clicked", self.on_gnb_log_file_clicked, log_dir, f)
                row.add(btn)
                listbox.add(row)
                
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(listbox)
        box.pack_start(scrolled, True, True, 15)
        box.show_all()

    def on_gnb_log_file_clicked(self, button, log_dir, filename):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab(f"gnblog-{filename}", "Log: " + filename)
        command = f'cat {os.path.join(log_dir, filename)}\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def on_gnb_webui(self, _):
        self.on_gnb_webview(_)

    def on_ue_logs(self, _):
        # Placeholder for UE Logs
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        box = self.ue_area
        for c in box.get_children(): box.remove(c)
        lbl = Gtk.Label(label="UE Logs functionality coming soon")
        box.pack_start(lbl, True, True, 0)
        box.show_all()

    def on_ue_webui(self, _):
        # Placeholder for UE Web UI
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        if self.webview_container: return
        
        self.original_content_pane = self.content_box
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", lambda w: self._restore_main_view())
        header.pack_start(back_btn, False, False, 10)
        
        webview = WebKit2.WebView()
        webview.load_uri("about:blank") # Placeholder URL
        
        self.webview_container.pack_start(header, False, False, 0)
        self.webview_container.pack_start(webview, True, True, 0)
        
        self.content_paned.remove(self.original_content_pane)
        self.content_paned.pack1(self.webview_container, resize=True, shrink=False)
        self.webview_container.show_all()

    def on_ue_pcap(self, _):
        # Placeholder for Pcap
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        box = self.ue_area
        for c in box.get_children(): box.remove(c)
        lbl = Gtk.Label(label="Pcap functionality coming soon")
        box.pack_start(lbl, True, True, 0)
        box.show_all()

    def on_gnb_pcap(self, _):
        # Placeholder for Pcap
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        box = self.gnb_area
        for c in box.get_children(): box.remove(c)
        lbl = Gtk.Label(label="Pcap functionality coming soon")
        box.pack_start(lbl, True, True, 0)
        box.show_all()


    def on_ue_binaries(self, _):
        self.content_paned.set_position(self.default_terminal_pane_position)
        box=self.ue_area
        for c in box.get_children(): box.remove(c)
        terminal = self.create_terminal_tab("ue_bin", "UE Binaries")
        command = "ls -l ~/srsRAN_Project/build/ue\n"
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def on_gnb_config(self, _):
        self._show_config_view(self.gnb_area, "gnb", "srsRAN_Project/build", "gnb.yaml", "gnb_config_scheduler_id")
        
    def on_ue_config(self, _):
        self._show_config_view(self.ue_area, "ue", "srsRAN_Project/build", "ue.yaml", "ue_config_scheduler_id")

    def on_core_config(self, _):
        # Open5GS config logic
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        config_dir = "/etc/open5gs"
        if os.path.exists(config_dir):
            files = sorted([f for f in os.listdir(config_dir) if f.endswith('.yaml')])
        else: files = []
        
        box = self.core_area
        for c in box.get_children(): box.remove(c)
        
        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_core_config_file_clicked, f)
            row.add(btn)
            listbox.add(row)
            
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(listbox)
        box.pack_start(scrolled, True, True, 15)
        box.show_all()

    def on_core_config_file_clicked(self, button, filename):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab(f"conf-{filename}", "Conf: " + filename)
        command = f'cat /etc/open5gs/{filename}\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def _show_config_view(self, area_box, key_prefix, config_path, config_file, scheduler_id_attr):
        self.content_paned.set_position(self.default_terminal_pane_position)
        for c in area_box.get_children(): area_box.remove(c)
        area_box.show_all()
        terminal = self.create_terminal_tab(f"{key_prefix}_config", f"{key_prefix.upper()} Configuration")
        commands = [f"cd ~/{config_path}", "ls", f"cat {config_file}"]
        self._send_commands_sequentially(terminal, commands, scheduler_id_attr)

    def on_core_logs(self, _):
        # Open5GS logs logic
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        log_dir = "/var/log/open5gs"
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
        else: files = []
        box = self.core_area
        for c in box.get_children(): box.remove(c)
        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_log_file_clicked, f)
            row.add(btn)
            listbox.add(row)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(listbox)
        box.pack_start(scrolled, True, True, 15)
        box.show_all()

    def on_log_file_clicked(self, button, filename):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab(f"log-{filename}", "Log: " + filename)
        command = f'cat /var/log/open5gs/{filename}\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    # -------------------------------------------------------------------------
    # UTILS & HELPERS
    # -------------------------------------------------------------------------
    def create_terminal_tab(self, key, title):
        if key in self.terminals:
            terminal_info = self.terminals[key]
            terminal = terminal_info['terminal']
            terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash"], [], GLib.SpawnFlags.DEFAULT, None, None, -1, None, None)
            page_num = self.terminal_notebook.page_num(terminal_info['frame'])
            if page_num != -1: self.terminal_notebook.set_current_page(page_num)
        else:
            frame = Gtk.Frame()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            lbl = Gtk.Label(label=title)
            btn_close = Gtk.Button(label="✖")
            header.pack_start(lbl, True, True, 5)
            header.pack_start(btn_close, False, False, 0)
            terminal = Vte.Terminal()
            terminal.set_scrollback_lines(1000)
            terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash"], [], GLib.SpawnFlags.DEFAULT, None, None, -1, None, None)
            
            def close_tab(_):
                if key == "gnb" and self.gnb_running: self.toggle_gnb_process(None)
                elif key == "ue" and self.ue_running: self.toggle_ue_process(None)
                elif key == "tshark" and self.tshark_running: self.toggle_tshark_process(None)
                page = self.terminal_notebook.page_num(frame)
                if page != -1: self.terminal_notebook.remove_page(page)
                if key not in ("gnb", "ue", "tshark", "core"): self.terminals.pop(key, None)

            btn_close.connect("clicked", close_tab)
            vbox.pack_start(header, False, False, 0)
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.add(terminal)
            vbox.pack_start(scrolled, True, True, 0)
            frame.add(vbox)

            # Tab Label Click Event
            tab_label = Gtk.Label(label=title)
            event_box = Gtk.EventBox()
            event_box.add(tab_label)
            event_box.connect("button-press-event", self.on_terminal_tab_clicked)
            event_box.show_all()
            
            self.terminal_notebook.append_page(frame, event_box)
            new_page_num = self.terminal_notebook.page_num(frame)
            GLib.idle_add(self.terminal_notebook.set_current_page, new_page_num)
            self.terminals[key] = {'frame': frame, 'terminal': terminal}
        
        self.terminal_notebook.show_all()
        return terminal

    def create_textview_tab(self, key, title):
        # Read-only text tab (used for daemon status)
        if key in self.terminals:
            terminal_info = self.terminals[key]
            text_buffer = terminal_info['buffer']
            page_num = self.terminal_notebook.page_num(terminal_info['frame'])
            if page_num != -1: self.terminal_notebook.set_current_page(page_num)
        else:
            frame = Gtk.Frame()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            lbl = Gtk.Label(label=title)
            btn_close = Gtk.Button(label="✖")
            header.pack_start(lbl, True, True, 5)
            header.pack_start(btn_close, False, False, 0)
            
            text_view = Gtk.TextView()
            text_view.set_editable(False)
            text_view.set_cursor_visible(False)
            text_view.get_style_context().add_class("terminal-style")
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.add(text_view)
            text_buffer = text_view.get_buffer()

            def close_tab(_):
                page = self.terminal_notebook.page_num(frame)
                if page != -1: self.terminal_notebook.remove_page(page)
                self.terminals.pop(key, None)

            btn_close.connect("clicked", close_tab)
            vbox.pack_start(header, False, False, 0)
            vbox.pack_start(scrolled, True, True, 0)
            frame.add(vbox)
            
            tab_label = Gtk.Label(label=title)
            event_box = Gtk.EventBox()
            event_box.add(tab_label)
            event_box.connect("button-press-event", self.on_terminal_tab_clicked)
            event_box.show_all()
            
            self.terminal_notebook.append_page(frame, event_box)
            new_page_num = self.terminal_notebook.page_num(frame)
            GLib.idle_add(self.terminal_notebook.set_current_page, new_page_num)
            self.terminals[key] = {'frame': frame, 'buffer': text_buffer}
        
        self.terminal_notebook.show_all()
        return text_buffer

    def start_5g_terminal(self, _):
        self.on_core_docker_menu(_)

    def on_gnb_webview(self, _):
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        if self.webview_container: return
        
        self.original_content_pane = self.content_box
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        # Header with Back button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", lambda w: self._restore_main_view())
        header.pack_start(back_btn, False, False, 10)
        
        # Webview
        webview = WebKit2.WebView()
        webview.load_uri("http://127.0.0.1:3000/") 
        
        self.webview_container.pack_start(header, False, False, 0)
        self.webview_container.pack_start(webview, True, True, 0)
        
        self.content_paned.remove(self.original_content_pane)
        self.content_paned.pack1(self.webview_container, resize=True, shrink=False)
        self.webview_container.show_all()

    def on_core_webui(self, _):
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)
        if self.webview_container: return
        self.original_content_pane = self.content_box
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", lambda w: self._restore_main_view())
        header.pack_start(back_btn, False, False, 10)
        webview = WebKit2.WebView()
        webview.load_uri("http://127.0.0.1:9999/")
        self.webview_container.pack_start(header, False, False, 0)
        self.webview_container.pack_start(webview, True, True, 0)
        self.content_paned.remove(self.original_content_pane)
        self.content_paned.pack1(self.webview_container, resize=True, shrink=False)
        self.webview_container.show_all()

    def _restore_main_view(self):
        if self.webview_container and self.webview_container.get_parent():
            old = self.webview_container
            self.content_paned.remove(old)
            self.content_paned.pack1(self.original_content_pane, resize=True, shrink=False)
            self.original_content_pane.show_all()
            GLib.idle_add(old.destroy)
            self.webview_container = None
            self.original_content_pane = None

    def on_terminal_tab_clicked(self, event_box, event):
        GLib.idle_add(self.content_paned.set_position, self.default_terminal_pane_position)
        return False

    def _send_commands_sequentially(self, terminal, commands, scheduler_id_attr, delay=1000, on_complete=None):
        command_queue = list(commands)
        def send_next():
            if not command_queue:
                if on_complete: on_complete()
                setattr(self, scheduler_id_attr, None)
                return False
            cmd = command_queue.pop(0)
            terminal.feed_child((cmd + "\n").encode())
            return True
        source_id = GLib.timeout_add(delay, send_next)
        setattr(self, scheduler_id_attr, source_id)

    def on_app_quit(self, *args):
        if self.ue_running and self.ue_terminal_ref: self.ue_terminal_ref.feed_child(b'\x03')
        if self.gnb_running and self.gnb_terminal_ref: self.gnb_terminal_ref.feed_child(b'\x03')
        if self.tshark_running and self.tshark_terminal_ref: self.tshark_terminal_ref.feed_child(b'\x03')
        Gtk.main_quit()

if __name__ == "__main__":
    app = SrsRanGuiApp()
    app.connect("destroy", app.on_app_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, app.on_app_quit, None)
    Gtk.main()
