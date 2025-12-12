#!/usr/bin/env python3
import os, signal, subprocess, threading, re, time, sys
os.environ['GDK_BACKEND'] = 'x11'                  # Force X11 (fixes Wayland crashes)
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'          # Force software rendering
os.environ['WEBKIT_DISABLE_DMABUF_RENDERER'] = '1' # Disable DMABuf (common crash source)
os.environ['WEBKIT_DISABLE_COMPOSITING_MODE'] = '1' # Optional: Reduce GPU load

# --- FIX: Handling WebKit Version Compatibility ---
import gi
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
        self.closing_terminals = []
        self.is_closing = False

        # Runtime control state
        self.gnb_running = False
        self.gnb_terminal_ref = None
        self.gnb_button_ref = None

        self.grafana_terminal_ref = None
        self.grafana_scheduler_id = None
        
        self.ue_running = False
        self.ue_terminal_ref = None
        self.ue_button_ref = None

        self.core_iperf_running = False
        self.core_iperf_button_ref = None
        self.core_iperf_start_time = 0

        self.ue_iperf_running = False
        self.ue_iperf_button_ref = None
        self.ue_iperf_start_time = 0
        
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
        self.core_ip = "<N/A>"
        
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
        
        # Performance Fix: Run watchdog in a separate thread, not the main UI loop
        self.watchdog_running = True
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

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
        
        protected_keys = ["gnb", "ue", "tshark", "core","grafana","core_iperf","ue_iperf"]
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
                if self.is_closing: return False
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
        
        # --- RETURN THE HBOX SO WE CAN ADD EXTRA BUTTONS ---
        return hbox_buttons

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
        parent_box.pack_start(self.create_title("UE"), False, False, 0)
        
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
        
        # IP Display Frame
        ip_frame = Gtk.Frame()
        # CHANGED: Label is now "gNB IP"
        self.gnb_ip_label = Gtk.Label(label=f"gNB IP: {self.gnb_link_ip}")
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

        # Web UI Button
        gnb_webui_btn = Gtk.Button(label="Web UI")
        gnb_webui_btn.get_style_context().add_class("start-button")
        gnb_webui_btn.connect("clicked", self.on_gnb_webview)
        parent_box.pack_start(gnb_webui_btn, False, False, 5)

    def create_core_control_ui(self, parent_box):
        parent_box.pack_start(self.create_title("5G Core"), False, False, 0)
        
        # IP Display Frame
        ip_frame = Gtk.Frame()
        # CHANGED: Label is now "AMF IP"
        self.core_ip_label = Gtk.Label(label=f"AMF IP: {self.core_ip}")
        
        self.core_ip_label.set_margin_top(10)
        self.core_ip_label.set_margin_bottom(10)
        self.core_ip_label.set_margin_start(10)
        self.core_ip_label.set_margin_end(10)
        
        ip_frame.add(self.core_ip_label)
        parent_box.pack_start(ip_frame, False, False, 5)

        # Start Button
        self.core_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start 5G Core")
        self.core_button_ref.get_style_context().add_class("start-button")
        if self.core_running:
            self.core_button_ref.set_label(f"{STOP_SYMBOL} Stop 5G Core")
            self.core_button_ref.get_style_context().add_class("stop-button")
        self.core_button_ref.connect("clicked", self.toggle_core_process)
        parent_box.pack_start(self.core_button_ref, False, False, 5)

        # Web UI Button
        webui_btn = Gtk.Button(label="Web UI")
        webui_btn.get_style_context().add_class("start-button")
        webui_btn.connect("clicked", self.on_core_webui)
        parent_box.pack_start(webui_btn, False, False, 5)

    def toggle_core_process(self, widget, force=False):
        self.content_paned.set_position(self.default_terminal_pane_position)
        if not self.core_running:
            # --- STARTUP LOGIC (Unchanged) ---
            self.core_button_ref.set_sensitive(False)
            terminal = self.create_terminal_tab("core", "5G Core Console")
            terminal.connect("child-exited", self.on_process_exited, "core")
            self.core_terminal_ref = terminal
            
            ctx = self.core_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.core_button_ref.set_label(f"{STOP_SYMBOL} Stop 5G Core")

            def startup_complete():
                self.core_running = True
                self.core_button_ref.set_sensitive(True)
                self.fetch_and_display_core_ip()

            commands = [
                "sudo su",
                "cd",
                "cd srsRAN_Project/docker",
                "sudo docker compose up 5gc"
            ]
            
            self._send_commands_sequentially(
                terminal,
                commands,
                "core_scheduler_id",
                delay=1000,
                on_complete=startup_complete
            )
        else:
            # --- STOPPING LOGIC ---
            
            # 1. SAFETY CHECK (Only if not forced)
            # If the user clicks the button, we warn them.
            if not force and (self.gnb_running or self.ue_running):
                self._show_alert("Cannot stop 5G Core while gNB or UE are active.\nPlease stop User Equipment and gNB first.")
                return

            # 2. Proceed with Stop
            if "core" in self.terminals:
                # Switch to tab to show logs
                frame = self.terminals["core"]['frame']
                page = self.terminal_notebook.page_num(frame)
                if page != -1:
                    self.terminal_notebook.set_current_page(page)
                    current_pos = self.content_paned.get_position()
                    max_pos = self.content_paned.get_allocation().height
                    if current_pos > max_pos - 100: 
                        self.content_paned.set_position(self.default_terminal_pane_position)

            if self.core_scheduler_id:
                GLib.source_remove(self.core_scheduler_id)
                self.core_scheduler_id = None
            
            if self.core_terminal_ref:
                self.core_terminal_ref.feed_child(b'\x03') # Ctrl+C
            
            self.reset_core_button()

    def reset_core_button(self):
        self.core_running = False
        self.reset_core_ip_display()
        def update_ui():
            if self.is_closing: return
            if self.core_button_ref and self.core_button_ref.get_realized():
                self.core_button_ref.set_sensitive(True)
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

    def toggle_gnb_process(self, widget, force=False):
        if not self.gnb_running:
            # --- STARTUP SEQUENCE ---
            
            # 1. Prerequisite Check
            if not self.core_running:
                self._show_alert("Please start the 5G Core Network first.")
                return

            self.gnb_button_ref.set_sensitive(False)

            # 2. Start Grafana (Foreground Mode)
            grafana_terminal = self.create_terminal_tab("grafana", "Grafana Service")
            self.grafana_terminal_ref = grafana_terminal
            
            # Use absolute path for safety
            grafana_cmd = [
                "sudo su",
                "cd",
                "cd srsRAN_Project/", 
                "sudo docker compose -f docker/docker-compose.yml up grafana" 
            ]
            self._send_commands_sequentially(grafana_terminal, grafana_cmd, "grafana_scheduler_id")
            
            # 3. Resize Terminal (Optional, if you added this helper previously)
            if hasattr(self, 'maximize_terminal_view'):
                self.maximize_terminal_view()

            # --- KEY FIX: NON-BLOCKING DELAY ---
            # Instead of time.sleep(2), we define the gNB startup as a separate function
            # and schedule it to run in 2000ms (2 seconds).
            
            def start_gnb_delayed():
                if self.is_closing: return False

                # 4. Start gNB (Foreground Tab)
                gnb_terminal = self.create_terminal_tab("gnb", "gNB Console")
                self.gnb_terminal_ref = gnb_terminal
                
                # Update Button Style
                ctx = self.gnb_button_ref.get_style_context()
                ctx.remove_class("start-button")
                ctx.add_class("stop-button")
                self.gnb_button_ref.set_label(f"{STOP_SYMBOL} Stop gNB")

                def startup_complete():
                    self.gnb_running = True
                    self.gnb_button_ref.set_sensitive(True)
                    self.fetch_and_display_gnb_ips()

                commands = [
                    "sudo su",
                    "cd",
                    "cd srsRAN_Project/build/apps/gnb", # Absolute path
                    "sudo gnb -c /home/student/Downloads/gnb_zmq.yaml" # Absolute path
                ]
                
                self._send_commands_sequentially(
                    gnb_terminal,
                    commands,
                    "gnb_command_scheduler_id",
                    delay=1000,
                    on_complete=startup_complete
                )
                
                # If you want the view to switch to the new gNB tab:
                if hasattr(self, 'maximize_terminal_view'):
                    self.maximize_terminal_view()
                    
                return False # Run once

            # Schedule the gNB start for 2 seconds later (allows Grafana to init)
            GLib.timeout_add(2000, start_gnb_delayed)
            
        else:
            # --- STOPPING SEQUENCE (Unchanged) ---
            
            # 1. Safety Check
            if not force and self.ue_running:
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
            
            # 2. Stop gNB
            if self.gnb_command_scheduler_id:
                GLib.source_remove(self.gnb_command_scheduler_id)
                self.gnb_command_scheduler_id = None
            if self.gnb_terminal_ref:
                self.gnb_terminal_ref.feed_child(b'\x03') 
            
            # 3. Stop Grafana
            if self.grafana_terminal_ref:
                try:
                    self.grafana_terminal_ref.feed_child(b'\x03') 
                except:
                    pass
                self.grafana_terminal_ref = None

            self.reset_gnb_button()

    def toggle_ue_process(self, _):
        self.content_paned.set_position(self.default_terminal_pane_position)
        if not self.ue_running:
            # Check Core First
            if not self.core_running:
                self._show_alert("Please start the 5G Core Network first.")
                return
            
            # Check gNB Second
            if not self.gnb_running:
                self._show_alert("Please start the gNB first.")
                return

            self.ue_button_ref.set_sensitive(False)
            terminal = self.create_terminal_tab("ue", "UE Console")
            terminal.connect("child-exited", self.on_process_exited, "ue")
            self.ue_terminal_ref = terminal

            ctx = self.ue_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.ue_button_ref.set_label(f"{STOP_SYMBOL} Stop UE")

            def startup_complete():
                self.ue_running = True
                self.ue_button_ref.set_sensitive(True)
                self.fetch_and_display_ue_ips()

            # --- MODIFIED SECTION: SILENT CHECK ---
            # "grep -q" checks silently. 
            # "||" means "OR": if the first part fails (UE not found), run the second part (add it).
            silent_check_cmd = "ip netns list | grep -q 'ue1' || ip netns add ue1"

            commands = [
                "sudo su",
                "cd",
                silent_check_cmd,               # <--- Runs silently
                "cd srsRAN_4G/build/srsue/src",
                "sudo srsue /home/student/Downloads/ue_zmq.conf"
            ]
            # --------------------------------------

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
        self.content_paned.set_position(self.default_terminal_pane_position)
        # 1. Ensure capture folder exists (We will move the file here later)
        if not os.path.exists(self.capture_folder_path):
            try:
                os.makedirs(self.capture_folder_path)
                # Ensure the folder is owned by the user
                sudo_user = os.environ.get('SUDO_USER')
                if sudo_user:
                    import pwd
                    pw = pwd.getpwnam(sudo_user)
                    os.chown(self.capture_folder_path, pw.pw_uid, pw.pw_gid)
            except Exception:
                pass

        if not self.tshark_running:
            # --- STARTUP ---
            self.tshark_button_ref.set_sensitive(False)
            
            terminal = self.create_terminal_tab("tshark", "Tshark NGAP Capture")
            terminal.connect("child-exited", self.on_process_exited, "tshark")
            self.tshark_terminal_ref = terminal
            
            # Update Button
            ctx = self.tshark_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.tshark_button_ref.set_label(f"{STOP_SYMBOL} Stop Tshark")
            
            def startup_complete():
                self.tshark_running = True
                self.tshark_button_ref.set_sensitive(True)

            # --- KEY FIX 1: CAPTURE TO /tmp FIRST ---
            # AppArmor allows tshark to write to /tmp without issues.
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"srs_ngap_{timestamp}.pcap"
            
            self.temp_pcap_path = f"/tmp/{filename}"
            self.final_pcap_path = os.path.join(self.capture_folder_path, filename)
            
            # Run tshark pointing to the TEMP path
            commands = [f'sudo tshark -i any -f "sctp port 38412" -w "{self.temp_pcap_path}" -P']
            
            self._send_commands_sequentially(
                terminal, 
                commands, 
                "tshark_scheduler_id",
                on_complete=startup_complete
            )
        else:
            # --- STOPPING ---
            
            # --- KEY FIX 2: Tell Watchdog to ignore Tshark IMMEDIATELY ---
            # This prevents the "Watchdog: tshark stopped unexpectedly" error.
            self.tshark_running = False 
            
            # Disable button and show status while we save
            self.tshark_button_ref.set_sensitive(False)
            self.tshark_button_ref.set_label("Saving...")

            if self.tshark_scheduler_id:
                GLib.source_remove(self.tshark_scheduler_id)
                self.tshark_scheduler_id = None

            # Kill the process
            if self.tshark_terminal_ref:
                try:
                    self.tshark_terminal_ref.feed_child(b'\x03') 
                except:
                    pass
            
            # Wait and Move (Bypasses AppArmor)
            def move_capture_file():
                try:
                    if hasattr(self, 'temp_pcap_path') and os.path.exists(self.temp_pcap_path):
                        # FIX: Use 'sudo mv' via subprocess instead of shutil.move
                        # This works even if the script is running as a normal user.
                        subprocess.run(["sudo", "mv", self.temp_pcap_path, self.final_pcap_path], check=True)
                        
                        # FIX: Change ownership to the real user
                        # (Because 'sudo mv' keeps the file owned by root)
                        real_user = os.environ.get('SUDO_USER') or os.environ.get('USER')
                        if real_user:
                            subprocess.run(["sudo", "chown", f"{real_user}:{real_user}", self.final_pcap_path], check=True)
                            
                    else:
                        print("Warning: No capture file found in /tmp")
                except Exception as e:
                    print(f"Error moving capture file: {e}")
                
                # Restore button state
                self.reset_tshark_button()
                return False # Run once

            # Schedule the move operation (1.5s delay allows tshark to close file)
            GLib.timeout_add(1500, move_capture_file)

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
    def fetch_and_display_core_ip(self):
        def worker_thread():
            core_ip = "<N/A>" 
            config_path = "/home/student/Downloads/gnb_zmq.yaml"
            
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        lines = f.readlines()
                        in_amf_section = False
                        for line in lines:
                            clean_line = line.strip()
                            if clean_line.startswith("amf:"):
                                in_amf_section = True
                                continue
                            if in_amf_section and clean_line.startswith("addr:"):
                                parts = clean_line.split("addr:")
                                if len(parts) > 1:
                                    core_ip = parts[1].split("#")[0].strip()
                                break
                                
                elif self.core_running:
                    cmd = ["sudo", "docker", "inspect", "-f", 
                           "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", 
                           "open5gs_5gc"]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    output = result.stdout.strip()
                    if output: core_ip = output

            except Exception:
                pass

            def update_gui():
                if self.is_closing: return
                self.core_ip = core_ip
                if hasattr(self, 'core_ip_label'):
                    # CHANGED: Update text to "AMF IP"
                    self.core_ip_label.set_text(f"AMF IP: {self.core_ip}")
            
            GLib.idle_add(update_gui)
        threading.Thread(target=worker_thread, daemon=True).start()

    def fetch_and_display_gnb_ips(self):
        def worker_thread():
            link_ip = "<N/A>"
            config_path = "/home/student/Downloads/gnb_zmq.yaml"
            
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        lines = f.readlines()
                        in_amf_section = False
                        for line in lines:
                            clean_line = line.strip()
                            if clean_line.startswith("amf:"):
                                in_amf_section = True
                                continue
                            if in_amf_section and clean_line.startswith("bind_addr:"):
                                parts = clean_line.split("bind_addr:")
                                if len(parts) > 1:
                                    link_ip = parts[1].split("#")[0].strip()
                                break
            except Exception:
                pass

            def update_gui():
                if self.is_closing: return
                self.gnb_link_ip = link_ip
                if hasattr(self, 'gnb_ip_label'):
                    # CHANGED: Update text to "gNB IP"
                    self.gnb_ip_label.set_text(f"gNB IP: {self.gnb_link_ip}")
            
            GLib.idle_add(update_gui)
        threading.Thread(target=worker_thread, daemon=True).start()
        
    def reset_core_ip_display(self):
        self.core_ip = "<N/A>"
        def update_gui():
            if self.is_closing: return
            if hasattr(self, 'core_ip_label'):
                # CHANGED: Reset to "AMF IP"
                self.core_ip_label.set_text(f"AMF IP: {self.core_ip}")
        GLib.idle_add(update_gui)

    def reset_gnb_ip_display(self):
        self.gnb_link_ip = "<N/A>"
        def update_gui():
            if self.is_closing: return
            if hasattr(self, 'gnb_ip_label'):
                # CHANGED: Reset to "gNB IP"
                self.gnb_ip_label.set_text("gNB IP: <N/A>")
        GLib.idle_add(update_gui)
        
    def fetch_and_display_ue_ips(self):
        def worker_thread():
            ue_ip = "<N/A>"
            # FIX: Retry loop (Try for 15 seconds)
            max_retries = 15
            
            for _ in range(max_retries):
                if self.is_closing: break
                
                # Attempt 1: Check inside 'ue1' namespace
                try:
                    cmd_ns = "sudo ip netns exec ue1 ip -4 addr show tun_srsue | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"
                    proc = subprocess.run(cmd_ns, shell=True, capture_output=True, text=True)
                    if proc.stdout.strip():
                        ue_ip = proc.stdout.strip()
                        break 
                except Exception:
                    pass

                # Attempt 2: Check on Host (Fallback)
                if ue_ip == "<N/A>":
                    try:
                        cmd_host = "ip -4 addr show tun_srsue | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"
                        proc = subprocess.run(cmd_host, shell=True, capture_output=True, text=True)
                        if proc.stdout.strip():
                            ue_ip = proc.stdout.strip()
                            break 
                    except Exception:
                        pass
                
                time.sleep(1) # Wait 1s before retrying

            # Update GUI
            def update_gui():
                if self.is_closing: return
                self.ue_ip = ue_ip
                # Check if label exists and is valid
                if hasattr(self, 'ue_ip_label') and self.ue_ip_label:
                    self.ue_ip_label.set_text(f"UE IP: {self.ue_ip}")
            
            GLib.idle_add(update_gui)
        
        threading.Thread(target=worker_thread, daemon=True).start()

    def reset_ue_ip_display(self):
        # FIX: Reset the persistent variable too
        self.ue_ip = "<N/A>"
        
        def update_gui():
            if self.is_closing: return
            if hasattr(self, 'ue_ip_label'):
                self.ue_ip_label.set_text("UE IP: <N/A>")
        GLib.idle_add(update_gui)

    def reset_gnb_button(self):
        self.gnb_running = False
        self.reset_gnb_ip_display()
        def update_ui():
            if self.is_closing: return
            if self.gnb_button_ref and self.gnb_button_ref.get_realized():
                self.gnb_button_ref.set_sensitive(True)
                ctx = self.gnb_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.gnb_button_ref.set_label(f"{PLAY_SYMBOL} Start gNB")
        GLib.idle_add(update_ui)

    def reset_ue_button(self):
        self.ue_running = False
        self.reset_ue_ip_display()
        def update_ui():
            if self.is_closing: return
            if self.ue_button_ref and self.ue_button_ref.get_realized():
                self.ue_button_ref.set_sensitive(True)
                ctx = self.ue_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.ue_button_ref.set_label(f"{PLAY_SYMBOL} Start UE")
        GLib.idle_add(update_ui)

    def reset_tshark_button(self):
        self.tshark_running = False
        def update_ui():
            if self.is_closing: return
            if self.tshark_button_ref and self.tshark_button_ref.get_realized():
                self.tshark_button_ref.set_sensitive(True)
                ctx = self.tshark_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.tshark_button_ref.set_label(f"{PLAY_SYMBOL} Start Tshark")
        GLib.idle_add(update_ui)

    def on_process_exited(self, _terminal, _exit_status, key):
        if key not in self.terminals:
            return

        if key == "gnb" and self.gnb_running:
            self.reset_gnb_button()
            if self.grafana_terminal_ref:
                try:
                    self.grafana_terminal_ref.feed_child(b'\x03')
                except Exception:
                    pass
                self.grafana_terminal_ref = None
        elif key == "grafana":
            if self.ue_running:
                self.toggle_ue_process(None) # Auto stop UE if gNB dies
            if self.gnb_running:
                self.toggle_gnb_process(None, force=True) # Auto stop gNB if gNB dies
        elif key == "ue" and self.ue_running:
            self.reset_ue_button()
        elif key == "core" and self.core_running:
            # Core died (shell exited). 
            # Use the shared handler to ensure UE/gNB are stopped too.
            self.handle_core_stopped_unexpectedly()
        elif key == "tshark" and self.tshark_running:
            self.reset_tshark_button()
        elif key == "core_iperf":
            self.reset_core_iperf_button()
        elif key == "ue_iperf":
            self.reset_ue_iperf_button()

    def _check_process_running_native(self, pattern):
        """
        Optimization: Checks if a process is running by reading /proc directly.
        This avoids the overhead of spawning a 'pgrep' subprocess 4 times per loop.
        """
        try:
            # Iterate over all PIDs in /proc
            for pid in os.listdir('/proc'):
                if pid.isdigit():
                    try:
                        # Read the command line arguments for the process
                        with open(f'/proc/{pid}/cmdline', 'rb') as f:
                            # Arguments are separated by null bytes (\x00)
                            content = f.read()
                            if not content: continue
                            
                            # Decode and format as a single string
                            cmd_str = content.replace(b'\x00', b' ').decode('utf-8', errors='ignore')
                            
                            if pattern in cmd_str:
                                return True
                    except (FileNotFoundError, PermissionError, OSError):
                        # Process might have died while we were checking, just skip
                        continue
        except Exception:
            pass
        return False
    
    def _watchdog_loop(self):
        while self.watchdog_running:
            time.sleep(2) # Keep the 2-second interval
            
            if self.is_closing:
                break

            # key: (is_running_flag, cleanup_function, pattern)
            checks = [
                ('gnb', self.gnb_running, self.handle_gnb_stopped_unexpectedly, "gnb -c",None),
                ('ue', self.ue_running, self.reset_ue_button, "srsue",None),
                ('tshark', self.tshark_running, self.reset_tshark_button, "tshark",None),
                # Note: "docker compose" often appears as "docker-compose" or just "docker" depending on version
                ('core', self.core_running, self.handle_core_stopped_unexpectedly, "docker compose",None),
                ('core_iperf', self.core_iperf_running, self.reset_core_iperf_button, "iperf3 -s",'core_iperf_start_time'),
                ('ue_iperf', self.ue_iperf_running, self.reset_ue_iperf_button, "iperf3 -c",'ue_iperf_start_time')
            ]
            try:
                for key, running, func, ptrn, grace_attr in checks:
                    if running:
                        if grace_attr:
                            start_ts = getattr(self, grace_attr, 0)
                            if time.time() - start_ts < 15:
                                continue
                        # USE THE NEW OPTIMIZED CHECK
                        if not self._check_process_running_native(ptrn):
                            GLib.idle_add(func)
            except Exception as e:
                print(f"Watchdog Error: {e}")       

    def handle_core_stopped_unexpectedly(self):
        # This function is called by the Watchdog when it sees 
        # "docker compose" is no longer running (e.g., after Ctrl+C)
        
        # 1. Stop UE if running
        if self.ue_running:
            self.toggle_ue_process(None)
            
        # 2. Stop gNB if running (Force=True to skip checks)
        if self.gnb_running:
            self.toggle_gnb_process(None, force=True)
            
        # 3. Finally reset the Core button
        self.reset_core_button()

    def handle_gnb_stopped_unexpectedly(self):
        self.reset_gnb_button()
        if self.grafana_terminal_ref:
            try:
                self.grafana_terminal_ref.feed_child(b'\x03')
            except Exception:
                pass
            self.grafana_terminal_ref = None

        if self.ue_running:
            self.toggle_ue_process(None) # Auto stop UE if gNB dies

    # -------------------------------------------------------------------------
    # SUBMENU LOGIC
    # -------------------------------------------------------------------------
    def show_core_menu(self):
        # Removed "Speedtest" from this list
        items = [
            ("Docker", self.on_core_docker_menu),
            ("Config", self.on_core_config),
            ("Logs", self.on_core_logs),
            ("Web UI", self.on_core_webui),
        ]
        
        # Capture the button container
        hbox = self.add_toolbar_with_content(items, "core_area", "core_buttons")

        # --- ADD DIRECT SPEEDTEST TOGGLE BUTTON ---
        self.core_iperf_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start Speedtest")
        self.core_iperf_button_ref.set_size_request(180, 40) # Slightly wider
        
        # Set Initial State
        if self.core_iperf_running:
            self.core_iperf_button_ref.set_label(f"{STOP_SYMBOL} Stop Speedtest")
            self.core_iperf_button_ref.get_style_context().add_class("stop-button")
        else:
            self.core_iperf_button_ref.get_style_context().add_class("start-button")

        self.core_iperf_button_ref.connect("clicked", self.toggle_core_iperf)
        
        # Pack it at the end of the toolbar
        hbox.pack_start(self.core_iperf_button_ref, False, False, 0)
        hbox.show_all()

    def on_core_docker_menu(self, _):
        # 1. Clear the 'core_area' (the content box below the main buttons)
        # This acts as our "Submenu" view
        box = self.core_area
        for c in box.get_children(): box.remove(c)

        # 2. Create the Layout for the Submenu
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        vbox.set_margin_top(20)
        vbox.set_margin_start(20)
        
        # Title
        title = Gtk.Label(label="Docker Management Tools")
        title.get_style_context().add_class("header-title")
        vbox.pack_start(title, False, False, 0)

        # 3. Create a Grid for the Buttons (2x2 Layout)
        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(20)
        grid.set_halign(Gtk.Align.CENTER)

        # Define the menu options
        options = [
            ("Docker Containers", self.on_docker_containers, "View running and stopped containers"),
            ("Docker Images", self.on_docker_images, "List all locally available images"),
            ("Docker Networks", self.on_docker_networks, "Inspect network bridges and IP ranges"),
            ("Docker Stats", self.on_docker_stats, "Live CPU/Memory usage of containers")
        ]

        # 4. Generate Buttons
        for i, (label_text, handler, tooltip) in enumerate(options):
            btn = Gtk.Button(label=label_text)
            btn.set_size_request(200, 60)
            btn.set_tooltip_text(tooltip)
            btn.get_style_context().add_class("big-menu-label") # Reuse existing style
            btn.connect("clicked", handler)
            
            # Calculate grid position (2 columns)
            col = i % 2
            row = i // 2
            grid.attach(btn, col, row, 1, 1)

        vbox.pack_start(grid, False, False, 0)
        
        # Add a help tip at the bottom
        tip = Gtk.Label(label="Click a button above to open the corresponding terminal view.")
        tip.set_opacity(0.7)
        vbox.pack_start(tip, False, False, 10)

        box.pack_start(vbox, True, True, 0)
        box.show_all()

    # --- Docker Submenu Handlers ---

    def on_docker_containers(self, _):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab("docker_ps", "Docker Containers")
        # We use 'watch' so it updates live every 2 seconds
        command = "sudo docker ps\n"
        self._run_simple_command(terminal, command)

    def on_docker_images(self, _):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab("docker_img", "Docker Images")
        command = "sudo docker images\n"
        self._run_simple_command(terminal, command)

    def on_docker_networks(self, _):
        # 1. Clear the content area immediately so the user sees something happening
        box = self.core_area
        for child in box.get_children():
            box.remove(child)
        
        # Show a "Loading..." spinner or label
        loading_lbl = Gtk.Label(label="Loading Docker Networks...")
        box.pack_start(loading_lbl, True, True, 20)
        box.show_all()

        # 2. Define the heavy work
        def fetch_networks_background():
            networks = []
            error_message = None
            try:
                # This is the line that used to freeze the GUI
                cmd = ["sudo", "docker", "network", "ls", "--format", "{{.Name}}"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output = result.stdout.strip()
                if output:
                    networks = sorted(output.split('\n'))
            except subprocess.CalledProcessError:
                error_message = "Error: Could not list Docker networks.\nIs the Docker daemon running?"
            except Exception as e:
                error_message = f"Error: {str(e)}"

            # 3. Schedule the UI update back on the main thread
            GLib.idle_add(update_ui, networks, error_message)

        # 4. Define the UI Update logic
        def update_ui(networks, error_message):
            if self.is_closing: return
            
            # Remove "Loading..." label
            for child in box.get_children():
                box.remove(child)

            # --- HEADER ---
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            hbox_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            btn_back = Gtk.Button(label="Back")
            btn_back.connect("clicked", self.on_core_docker_menu)
            hbox_header.pack_start(btn_back, False, False, 0)
            lbl = Gtk.Label(label="Docker Networks")
            lbl.get_style_context().add_class("header-title")
            hbox_header.pack_start(lbl, False, False, 0)
            vbox.pack_start(hbox_header, False, False, 0)

            # --- CONTENT ---
            if error_message:
                lbl_err = Gtk.Label(label=error_message)
                vbox.pack_start(lbl_err, False, False, 0)
            elif not networks:
                lbl_empty = Gtk.Label(label="No networks found.")
                vbox.pack_start(lbl_empty, False, False, 0)
            else:
                listbox = Gtk.ListBox()
                listbox.set_selection_mode(Gtk.SelectionMode.NONE)
                for net_name in networks:
                    row = Gtk.ListBoxRow()
                    btn = Gtk.Button(label=net_name)
                    if isinstance(btn.get_child(), Gtk.Label):
                        btn.get_child().set_xalign(0.0)
                    btn.set_relief(Gtk.ReliefStyle.NONE)
                    btn.connect("clicked", self.on_network_inspect_clicked, net_name)
                    row.add(btn)
                    listbox.add(row)
                
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scrolled.add(listbox)
                vbox.pack_start(scrolled, True, True, 0)

            box.pack_start(vbox, True, True, 0)
            box.show_all()
            
            allocation = self.content_paned.get_allocation()
            self.content_paned.set_position(allocation.height)

        # 5. Start the thread
        threading.Thread(target=fetch_networks_background, daemon=True).start()

    def on_network_inspect_clicked(self, button, network_name):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Create a new tab for this inspection
        terminal = self.create_terminal_tab(f"net_{network_name}", f"Net: {network_name}")
        
        # 3. commands to run
        commands = [
            f"echo '--- Inspecting Network: {network_name} ---'",
            f"sudo docker network inspect {network_name}"
        ]
        
        # 4. Execute
        # reusing core_logs_scheduler_id is fine here as it's a one-off command sequence
        self._send_commands_sequentially(terminal, commands, "core_logs_scheduler_id")

    def on_docker_stats(self, _):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab("docker_stats", "Docker Stats")
        # standard docker stats is interactive and perfect for this
        command = "sudo docker stats\n"
        self._run_simple_command(terminal, command)

    def _run_simple_command(self, terminal, command):
        # Helper to send a single command safely
        def send():
            if not self.is_closing and terminal:
                try:
                    terminal.feed_child(command.encode())
                except:
                    pass
            return False
        GLib.timeout_add(500, send)

    def show_gnb_menu(self):
        items = [
            ("Config", self.on_gnb_config),
            ("Logs", self.on_gnb_logs),
            ("Web UI", self.on_gnb_webui),
            ("Pcap", self.on_gnb_pcap),
        ]
        self.add_toolbar_with_content(items, "gnb_area", "gnb_buttons")

    def show_ue_menu(self):
        # Removed "Speedtest" from this list
        items = [
            ("Config", self.on_ue_config),
            ("Logs", self.on_ue_logs),
            ("Pcap", self.on_ue_pcap),
        ]
        
        # Capture the button container
        hbox = self.add_toolbar_with_content(items, "ue_area", "ue_buttons")

        # --- ADD DIRECT SPEEDTEST TOGGLE BUTTON ---
        self.ue_iperf_button_ref = Gtk.Button(label=f"{PLAY_SYMBOL} Start Speedtest")
        self.ue_iperf_button_ref.set_size_request(180, 40)
        
        # Set Initial State
        if self.ue_iperf_running:
            self.ue_iperf_button_ref.set_label(f"{STOP_SYMBOL} Stop Speedtest")
            self.ue_iperf_button_ref.get_style_context().add_class("stop-button")
        else:
            self.ue_iperf_button_ref.get_style_context().add_class("start-button")

        self.ue_iperf_button_ref.connect("clicked", self.toggle_ue_iperf)
        
        # Pack it at the end of the toolbar
        hbox.pack_start(self.ue_iperf_button_ref, False, False, 0)
        hbox.show_all()

    def on_gnb_logs(self, _):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Clear previous buttons
        box = self.gnb_area
        for child in box.get_children():
            box.remove(child)
            
        # 3. Create the tab
        terminal = self.create_terminal_tab("gnb_logs", "gNB Logs")
        
        # 4. Define the command sequence
        # We assume the log is in the build directory. 
        # If your log is elsewhere (e.g. /var/log), change the path here.
        commands = [
            "sudo su",
            "cd",    # 1. Go to build folder
            "cd /tmp",                # 2. Verify file exists
            "cat gnb.log"                   # 3. Display content
        ]
        
        # 5. Execute
        self._send_commands_sequentially(terminal, commands, "gnb_logs_scheduler_id")

    def on_gnb_webui(self, _):
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
        webview.load_uri("http://127.0.0.1:3300/")
        self.webview_container.pack_start(header, False, False, 0)
        self.webview_container.pack_start(webview, True, True, 0)
        self.content_paned.remove(self.original_content_pane)
        self.content_paned.pack1(self.webview_container, resize=True, shrink=False)
        self.webview_container.show_all()

    def on_ue_logs(self, _):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Clear previous buttons
        box = self.ue_area
        for child in box.get_children():
            box.remove(child)
            
        # 3. Create the tab
        terminal = self.create_terminal_tab("ue_logs", "UE Logs")
        
        # 4. Define the command sequence
        # We assume the log is in the build directory. 
        # If your log is elsewhere (e.g. /var/log), change the path here.
        commands = [
            "sudo su",
            "cd",    
            "cd /tmp",                
            "cat ue.log"                    
        ]
        
        # 5. Execute
        self._send_commands_sequentially(terminal, commands, "ue_logs_scheduler_id")

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

    def toggle_ue_iperf(self, widget):
        # Ensure we switch to terminal view so user sees the result
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        if not self.ue_iperf_running:
            # --- START ---
            terminal = self.create_terminal_tab("ue_iperf", "UE iPerf Client")
            self.ue_iperf_running = True
            self.ue_iperf_start_time = time.time()
            
            # Update Button to Red/Stop
            widget.set_label(f"{STOP_SYMBOL} Stop Speedtest")
            ctx = widget.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")

            commands = [
                "sudo su",
                "ip route show | grep -q '10.45.0.0/16' && sudo ip route del 10.45.0.0/16 || true",
                "sudo ip route add 10.45.0.0/16 via 10.53.1.2",
                "route -n",
                "sudo ip netns exec ue1 ip route add default via 10.45.1.1 dev tun_srsue",
                "sudo ip netns exec ue1 route -n",
                "sudo ip netns exec ue1 iperf3 -c 10.53.1.1 -i 1 -t 60 -b 60M -R"
            ]
            self._send_commands_sequentially(terminal, commands, "ue_speedtest_scheduler_id", delay=400)
        else:
            # --- STOP ---
            if "ue_iperf" in self.terminals:
                # Send Ctrl+C
                term = self.terminals["ue_iperf"]['terminal']
                try:
                    term.feed_child(b'\x03')
                except:
                    pass
                
                # Optional: Destroy tab immediately or let it linger so user can see results
                # To close immediately:
                # self.terminals["ue_iperf"]['frame'].destroy()
                # self.terminals.pop("ue_iperf", None)

            self.reset_ue_iperf_button()

    def reset_ue_iperf_button(self):
        self.ue_iperf_running = False
        def update_ui():
            if self.is_closing: return
            # Check if the button exists (user might have switched menus)
            if self.ue_iperf_button_ref and self.ue_iperf_button_ref.get_realized():
                self.ue_iperf_button_ref.set_sensitive(True)
                ctx = self.ue_iperf_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.ue_iperf_button_ref.set_label(f"{PLAY_SYMBOL} Start Speedtest")
        GLib.idle_add(update_ui)

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
        GLib.timeout_add(300, lambda: (terminal.feed_child(command.encode()) or False) if not self.is_closing else False)

    def on_gnb_config(self, _):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Clear previous content
        box = self.gnb_area
        for child in box.get_children():
            box.remove(child)

        # 3. Create the tab
        terminal = self.create_terminal_tab("gnb_config", "gNB Config")

        # 4. Define the 3 commands to run one by one
        commands = [
            "sudo su",      # Command 1: Go to the folder
            "cd",              # Command 2: Show file details/size
            "cat gnb_zmq.yaml"                 # Command 3: Display content
        ]
        
        # 5. Execute them sequentially
        # We use a unique scheduler ID for this task
        self._send_commands_sequentially(terminal, commands, "gnb_config_scheduler_id")
        
    def on_ue_config(self, _):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Clear previous content
        box = self.ue_area
        for child in box.get_children():
            box.remove(child)

        # 3. Create the tab
        terminal = self.create_terminal_tab("ue_config", "UE Config")

        # 4. Define the 3 commands to run one by one
        # Based on your toggle_ue_process, the file is ue_zmq.conf
        commands = [
            "sudo su",      # Command 1: Go to the folder
            "cd",               # Command 2: Verify file exists
            "cat ue_zmq.conf"                  # Command 3: Display content
        ]
        
        # 5. Execute them sequentially
        self._send_commands_sequentially(terminal, commands, "ue_config_scheduler_id")
        

    def on_core_config(self, _):
        # Start browsing at /open5gs/src inside the container
        # The third argument ensures the "Back" button stops here.
        self._browse_docker_container(
            container_name="open5gs_5gc", 
            current_path="/open5gs/src", 
            root_path="/open5gs/src"
        )

    def on_core_config_file_clicked(self, button, filename):
        self.content_paned.set_position(self.default_terminal_pane_position)
        terminal = self.create_terminal_tab(f"conf-{filename}", "Conf: " + filename)
        command = f'cat /etc/open5gs/{filename}\n'
        GLib.timeout_add(300, lambda: (terminal.feed_child(command.encode()) or False) if not self.is_closing else False)

    def _show_config_view(self, area_box, key_prefix, config_path, config_file, scheduler_id_attr):
        self.content_paned.set_position(self.default_terminal_pane_position)
        for c in area_box.get_children(): area_box.remove(c)
        area_box.show_all()
        terminal = self.create_terminal_tab(f"{key_prefix}_config", f"{key_prefix.upper()} Configuration")
        commands = [f"cd ~/{config_path}", "ls", f"cat {config_file}"]
        self._send_commands_sequentially(terminal, commands, scheduler_id_attr)

    def on_core_logs(self, _):
        # 1. Switch to terminal view
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Clear previous content (like the file buttons)
        box = self.core_area
        for child in box.get_children():
            box.remove(child)
            
        # 3. Create the log tab
        terminal = self.create_terminal_tab("core_logs", "5G Core Logs")
        
        # 4. Commands with 'less' pager
        # - 2>&1: Captures both standard output and error messages
        # - less -R: Opens the reader in "Raw" mode to preserve colors
        # - +G: (Optional) Auto-scroll to the very bottom (most recent logs)
        commands = [
            "sudo su",
            "cd",
            "cd srsRAN_Project/docker",
            "sudo docker logs open5gs_5gc 2>&1 | less -R +G" 
        ]
        
        # 5. Execute
        self._send_commands_sequentially(terminal, commands, "core_logs_scheduler_id")

    def toggle_core_iperf(self, widget):
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        if not self.core_iperf_running:
            # --- START ---
            terminal = self.create_terminal_tab("core_iperf", "Core iPerf Server")
            self.core_iperf_running = True
            self.core_iperf_start_time = time.time()
            
            # Update Button to Red/Stop
            widget.set_label(f"{STOP_SYMBOL} Stop Speedtest")
            ctx = widget.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")

            cmd = "iperf3 -s -i 1"
            self._send_commands_sequentially(terminal, [cmd], "core_speedtest_scheduler_id")
        else:
            # --- STOP ---
            if "core_iperf" in self.terminals:
                term=self.terminals["core_iperf"]['terminal']
                try:
                    term.feed_child(b'\x03')
                except:
                    pass
            
            self.reset_core_iperf_button()

    def reset_core_iperf_button(self):
        self.core_iperf_running = False
        def update_ui():
            if self.is_closing: return
            if self.core_iperf_button_ref and self.core_iperf_button_ref.get_realized():
                self.core_iperf_button_ref.set_sensitive(True)
                ctx = self.core_iperf_button_ref.get_style_context()
                ctx.remove_class("stop-button")
                ctx.add_class("start-button")
                self.core_iperf_button_ref.set_label(f"{PLAY_SYMBOL} Start Speedtest")
        GLib.idle_add(update_ui)
    # -------------------------------------------------------------------------
    # UTILS & HELPERS
    # -------------------------------------------------------------------------
    def create_terminal_tab(self, key, title):
        # 1. Check if terminal exists
        if key in self.terminals:
            terminal_info = self.terminals[key]
            frame = terminal_info['frame']
            terminal = terminal_info['terminal']
            
            page_num = self.terminal_notebook.page_num(frame)
            if page_num != -1:
                self.terminal_notebook.set_current_page(page_num)
                return terminal
            else:
                self.terminals.pop(key, None)

        # 2. Create UI Elements
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
        
        # --- RESTORED LISTENER: This makes Ctrl+C work ---
        terminal.connect("child-exited", self.on_process_exited, key)
        # -------------------------------------------------

        # 3. Graceful Close Logic (The previous fix)
        def close_tab(_):
            # A. Unregister from dictionary immediately
            self.terminals.pop(key, None)

            # B. CASCADE SHUTDOWN
            # If "Core" tab is closed manually, kill dependencies
            if key == "core":
                if self.ue_running:
                    self.toggle_ue_process(None)
                if self.gnb_running:
                    self.toggle_gnb_process(None, force=True) # Force used here
                if self.core_running:
                    self.toggle_core_process(None, force=True)
                    self.core_terminal_ref = None
            else:
                # Normal stop for other tabs
                if key == "ue" and self.ue_running: 
                    self.toggle_ue_process(None)
                    self.ue_terminal_ref = None
                elif key == "gnb" and self.gnb_running: 
                    self.toggle_gnb_process(None)
                    self.gnb_terminal_ref = None
                elif key == "tshark" and self.tshark_running: 
                    self.toggle_tshark_process(None)
                    self.tshark_terminal_ref = None
                elif key == "core_iperf":
                    self.core_iperf_running = False

            # C. Define Destruction Logic
            def do_destroy(*args):
                if self.terminal_notebook:
                    page = self.terminal_notebook.page_num(frame)
                    if page != -1: 
                        self.terminal_notebook.remove_page(page)
                GLib.idle_add(frame.destroy)
                return False

            # D. Wait for process death before hiding UI
            if terminal.get_pty() is not None:
                btn_close.set_sensitive(False)
                lbl.set_text(f"{title} (Stopping...)")
                # We use a local handler for the CLOSE BUTTON destroy logic
                terminal.connect("child-exited", do_destroy)
                GLib.timeout_add_seconds(2, do_destroy)
            else:
                do_destroy()

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
        
        # Store valid reference
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
        webview.load_uri("http://127.0.0.1:3300/") 
        
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
            if self.is_closing:
                setattr(self, scheduler_id_attr, None)
                return False
            if terminal is None: 
                setattr(self, scheduler_id_attr, None)
                return False

            if not command_queue:
                if on_complete: on_complete()
                setattr(self, scheduler_id_attr, None)
                return False
            
            cmd = command_queue.pop(0)
            try:
                terminal.feed_child((cmd + "\n").encode())
            except Exception:
                # Terminal likely destroyed
                setattr(self, scheduler_id_attr, None)
                return False
                
            return True
        source_id = GLib.timeout_add(delay, send_next)
        setattr(self, scheduler_id_attr, source_id)

    def _browse_docker_container(self, container_name, current_path, root_path):
        """
        A recursive file browser for Docker containers.
        - container_name: Name of the docker container (e.g., open5gs_5gc)
        - current_path: The directory we are currently looking at
        - root_path: The top-level directory (to know when to stop going 'Back')
        """
        # 1. Clear the core_area
        box = self.core_area
        for child in box.get_children():
            box.remove(child)

        # 2. List files using 'ls -p' (puts a / at the end of directories)
        items = []
        error_message = None
        
        try:
            # sudo docker exec open5gs_5gc ls -p /open5gs/src/
            cmd = ["sudo", "docker", "exec", container_name, "ls", "-p", current_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            if output:
                items = sorted(output.split('\n'))
        except subprocess.CalledProcessError:
            error_message = f"Error accessing path: {current_path}"

        # 3. Build UI Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # --- HEADER (Path + Back Button) ---
        hbox_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Only show Back button if we are deeper than the root path
        if current_path.rstrip('/') != root_path.rstrip('/'):
            btn_back = Gtk.Button(label=".. (Up)")
            # Calculate parent directory
            parent_dir = os.path.dirname(current_path.rstrip('/'))
            btn_back.connect("clicked", lambda w: self._browse_docker_container(container_name, parent_dir, root_path))
            hbox_header.pack_start(btn_back, False, False, 0)
            
        lbl_path = Gtk.Label(label=f"Path: {current_path}")
        lbl_path.get_style_context().add_class("header-title")
        hbox_header.pack_start(lbl_path, False, False, 0)
        vbox.pack_start(hbox_header, False, False, 0)
        # -----------------------------------

        if error_message:
            vbox.pack_start(Gtk.Label(label=error_message), False, False, 0)
        else:
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)

            # Separate folders and files for cleaner sorting
            folders = [x for x in items if x.endswith('/')]
            files = [x for x in items if not x.endswith('/')]
            
            # --- RENDER FOLDERS ---
            for folder in folders:
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f"📂 {folder}") # Add folder icon
                if isinstance(btn.get_child(), Gtk.Label):
                    btn.get_child().set_xalign(0.0)
                btn.set_relief(Gtk.ReliefStyle.NONE)
                
                # Click handler: Go deeper into this directory
                new_path = os.path.join(current_path, folder)
                btn.connect("clicked", lambda w, p=new_path: self._browse_docker_container(container_name, p, root_path))
                
                row.add(btn)
                listbox.add(row)

            # --- RENDER FILES ---
            for f in files:
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f"📄 {f}") # Add file icon
                if isinstance(btn.get_child(), Gtk.Label):
                    btn.get_child().set_xalign(0.0)
                btn.set_relief(Gtk.ReliefStyle.NONE)
                
                # Click handler: View file content
                full_file_path = os.path.join(current_path, f)
                btn.connect("clicked", self.on_docker_file_clicked, container_name, full_file_path, "core")
                
                row.add(btn)
                listbox.add(row)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.add(listbox)
            vbox.pack_start(scrolled, True, True, 0)

        box.pack_start(vbox, True, True, 0)
        box.show_all()
        
        # Ensure view is visible
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)

    def _display_docker_file_list_menu(self, area_box, container_name, directory, extension, key_prefix):
        """
        Lists files residing INSIDE a Docker container as buttons.
        """
        # 1. Clear the content area
        for child in area_box.get_children():
            area_box.remove(child)
            
        files = []
        error_message = None

        # 2. Run 'docker exec' to list files
        try:
            # We use 'ls -p' to identify directories (they end with /) so we can skip them
            cmd = ["sudo", "docker", "exec", container_name, "ls", "-p", directory]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            
            if output:
                # Filter files based on extension (if provided) and ignore directories (ending in /)
                raw_list = output.split('\n')
                for f in raw_list:
                    f = f.strip()
                    if f.endswith('/'): continue # Skip directories
                    if extension and not f.endswith(extension): continue
                    files.append(f)
                files.sort()
                
        except subprocess.CalledProcessError:
            error_message = f"Error: Could not list files.\nIs container '{container_name}' running?"

        # 3. Create the ListBox
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        if error_message:
            row = Gtk.ListBoxRow()
            row.add(Gtk.Label(label=error_message))
            listbox.add(row)
        elif not files:
            row = Gtk.ListBoxRow()
            row.add(Gtk.Label(label=f"No files found in {directory} inside {container_name}"))
            listbox.add(row)
        else:
            for f in files:
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f)
                if isinstance(btn.get_child(), Gtk.Label):
                    btn.get_child().set_xalign(0.0)
                btn.set_relief(Gtk.ReliefStyle.NONE)
                
                # Connect click to the Docker file opener
                # We pass the full path inside the container
                full_path_in_container = f"{directory}/{f}"
                # Remove double slashes just in case
                full_path_in_container = full_path_in_container.replace('//', '/')
                
                btn.connect("clicked", self.on_docker_file_clicked, container_name, full_path_in_container, key_prefix)
                row.add(btn)
                listbox.add(row)

        # 4. Wrap in ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(listbox)
        
        # 5. Add title and list
        vbox_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        lbl_title = Gtk.Label(label=f"Container: {container_name}")
        lbl_title.get_style_context().add_class("header-title")
        lbl_path = Gtk.Label(label=f"Path: {directory}")
        
        vbox_header.pack_start(lbl_title, False, False, 0)
        vbox_header.pack_start(lbl_path, False, False, 0)
        
        area_box.pack_start(vbox_header, False, False, 10)
        area_box.pack_start(scrolled, True, True, 0)
        area_box.show_all()
        
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)

    def on_docker_file_clicked(self, button, container_name, full_path, key_prefix):
        """
        Opens a terminal tab and cats the file from INSIDE the Docker container.
        """
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        filename = os.path.basename(full_path)
        terminal = self.create_terminal_tab(f"{key_prefix}_dock_{filename}", f"View: {filename}")
        
        # The command to run inside the terminal tab
        command = f"sudo docker exec {container_name} cat {full_path}\n"
        
        GLib.timeout_add(300, lambda: (terminal.feed_child(command.encode()) or False) if not self.is_closing else False)
    def _display_file_list_menu(self, area_box, directory, extension, key_prefix):
        """
        Generic function to list files in a directory as buttons.
        """
        # 1. Clear the content area (gnb_area, ue_area, etc.)
        for child in area_box.get_children():
            area_box.remove(child)
            
        # 2. Expand the user path (e.g., turn '~' into '/home/student')
        full_dir_path = os.path.expanduser(directory)
        
        # 3. List files
        if os.path.exists(full_dir_path):
            files = sorted([f for f in os.listdir(full_dir_path) if f.endswith(extension)])
        else:
            files = []
            
        # 4. Create the ListBox for buttons
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        if not files:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=f"No {extension} files found in {full_dir_path}")
            lbl.set_margin_top(10)
            lbl.set_margin_bottom(10)
            row.add(lbl)
            listbox.add(row)
        else:
            for f in files:
                row = Gtk.ListBoxRow()
                # Create a button for the file
                btn = Gtk.Button(label=f)
                if isinstance(btn.get_child(), Gtk.Label):
                    btn.get_child().set_xalign(0.0)
                btn.set_relief(Gtk.ReliefStyle.NONE) 
                
                # Connect the click event
                full_file_path = os.path.join(full_dir_path, f)
                btn.connect("clicked", self.on_generic_file_clicked, full_file_path, key_prefix)
                
                row.add(btn)
                listbox.add(row)

        # 5. Wrap in ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(listbox)
        
        # 6. Add title and list to the area
        lbl_dir = Gtk.Label(label=f"Directory: {full_dir_path}")
        lbl_dir.get_style_context().add_class("header-title")
        lbl_dir.set_margin_bottom(10)
        
        area_box.pack_start(lbl_dir, False, False, 0)
        area_box.pack_start(scrolled, True, True, 0)
        area_box.show_all()
        
        # Ensure the view panel is set to show this content (hiding terminal temporarily)
        allocation = self.content_paned.get_allocation()
        self.content_paned.set_position(allocation.height)

    def on_generic_file_clicked(self, button, full_file_path, key_prefix):
        """
        Opens a terminal tab and 'cats' the file when a button is clicked.
        """
        # 1. Switch view to terminal pane
        self.content_paned.set_position(self.default_terminal_pane_position)
        
        # 2. Extract filename for the tab title
        filename = os.path.basename(full_file_path)
        
        # 3. Create the tab
        terminal = self.create_terminal_tab(f"{key_prefix}_conf_{filename}", f"Conf: {filename}")
        
        # 4. Command to display the file
        command = f"cat {full_file_path}\n"
        
        # 5. Execute
        GLib.timeout_add(300, lambda: (terminal.feed_child(command.encode()) or False) if not self.is_closing else False)
        
    def on_delete_event(self, widget, event):
        self.is_closing = True
        return self.on_app_quit()

    def on_app_quit(self, *args):
        if self.is_closing and hasattr(self, '_quit_done'):
             # Avoid re-running logic if already done
             return False
        
        self.is_closing = True
        self._quit_done = True
        
        # 1. Stop all schedulers/timers
        schedulers = [
            'process_watchdog_id', 'gnb_command_scheduler_id', 'ue_command_scheduler_id',
            'core_monitor_scheduler_id', 'gnb_config_scheduler_id', 'ue_config_scheduler_id',
            'core_scheduler_id', 'tshark_scheduler_id','core_logs_scheduler_id', 'core_speedtest_scheduler_id',
            'ue_speedtest_scheduler_id', 'ue_logs_scheduler_id','gnb_logs_scheduler_id', 'grafana_scheduler_id'
        ]
        
        for sched_attr in schedulers:
            try:
                if hasattr(self, sched_attr):
                    sid = getattr(self, sched_attr)
                    if sid:
                        GLib.source_remove(sid)
                        setattr(self, sched_attr, None)
            except Exception:
                pass

        # 2. Stop UE (Check if running AND reference exists)
        if self.ue_running and self.ue_terminal_ref:
            try:
                self.ue_terminal_ref.feed_child(b'\x03') # Send Ctrl+C
            except Exception:
                pass
            time.sleep(0.5) 

        # 3. Stop gNB
        if self.gnb_running and self.gnb_terminal_ref:
            try:
                self.gnb_terminal_ref.feed_child(b'\x03')
            except Exception:
                pass
            time.sleep(0.5)
        
        # 3. Stop Grafana
        if self.grafana_terminal_ref:
            try:
                self.grafana_terminal_ref.feed_child(b'\x03')
            except Exception:
                pass
            time.sleep(0.5)

        # 4. Stop Core
        if self.core_running and self.core_terminal_ref:
            try:
                self.core_terminal_ref.feed_child(b'\x03')
            except Exception:
                pass
        
        # 5. Stop Tshark (This was the cause of your crash)
        # We added the check 'if self.tshark_terminal_ref:' to prevent the AttributeError
        if self.tshark_running and self.tshark_terminal_ref:
            try:
                self.tshark_terminal_ref.feed_child(b'\x03')
            except Exception:
                pass
        
        # 6. Quit GTK
        try:
            Gtk.main_quit()
        except Exception:
            pass
            
        # Force exit
        sys.exit(0)

if __name__ == "__main__":
    app = SrsRanGuiApp()
    app.connect("delete-event", app.on_delete_event)
    app.connect("destroy", app.on_app_quit)
    
    # GLib Signal Handlers (run in main loop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, app.on_app_quit, None)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, app.on_app_quit, None)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, app.on_app_quit, None)

    # Standard Signal Handlers (Fallback)
    def signal_handler(sig, frame):
        app.on_app_quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)

    try:
        Gtk.main()
    except KeyboardInterrupt:
        app.on_app_quit()
