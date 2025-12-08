#!/usr/bin/env python3
"""
srsRAN GUI - A graphical user interface for managing srsRAN components
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import os
import signal
import json
from datetime import datetime
from pathlib import Path


class SrsRANGUI:
    """Main GUI application for srsRAN management"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("srsRAN GUI - 4G/5G Software Radio Suite")
        self.root.geometry("1200x800")
        
        # Process tracking
        self.processes = {
            'epc': None,
            'enb': None,
            'ue': None
        }
        
        # Configuration
        self.config_dir = Path.home() / '.srsran_gui'
        self.config_file = self.config_dir / 'config.json'
        self.load_config()
        
        # Setup UI
        self.setup_ui()
        
        # Start status update loop
        self.update_status()
        
    def load_config(self):
        """Load configuration from file"""
        self.config_dir.mkdir(exist_ok=True)
        
        # Default configuration
        self.config = {
            'epc_binary': 'srsepc',
            'enb_binary': 'srsenb',
            'ue_binary': 'srsue',
            'epc_config': '',
            'enb_config': '',
            'ue_config': '',
            'working_dir': str(Path.home())
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create tabs
        self.create_control_tab()
        self.create_config_tab()
        self.create_logs_tab()
        self.create_about_tab()
        
    def create_control_tab(self):
        """Create the main control tab"""
        control_frame = ttk.Frame(self.notebook)
        self.notebook.add(control_frame, text='Control Panel')
        
        # Status Frame
        status_frame = ttk.LabelFrame(control_frame, text="Component Status", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        # EPC Status
        ttk.Label(status_frame, text="EPC (Core Network):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.epc_status = ttk.Label(status_frame, text="●", foreground="red", font=("Arial", 16))
        self.epc_status.grid(row=0, column=1, padx=5)
        self.epc_status_text = ttk.Label(status_frame, text="Stopped")
        self.epc_status_text.grid(row=0, column=2, sticky='w', padx=5)
        
        # eNB Status
        ttk.Label(status_frame, text="eNB (Base Station):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.enb_status = ttk.Label(status_frame, text="●", foreground="red", font=("Arial", 16))
        self.enb_status.grid(row=1, column=1, padx=5)
        self.enb_status_text = ttk.Label(status_frame, text="Stopped")
        self.enb_status_text.grid(row=1, column=2, sticky='w', padx=5)
        
        # UE Status
        ttk.Label(status_frame, text="UE (User Equipment):").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.ue_status = ttk.Label(status_frame, text="●", foreground="red", font=("Arial", 16))
        self.ue_status.grid(row=2, column=1, padx=5)
        self.ue_status_text = ttk.Label(status_frame, text="Stopped")
        self.ue_status_text.grid(row=2, column=2, sticky='w', padx=5)
        
        # Control Buttons Frame
        button_frame = ttk.LabelFrame(control_frame, text="Controls", padding=10)
        button_frame.pack(fill='x', padx=10, pady=5)
        
        # EPC Controls
        epc_frame = ttk.Frame(button_frame)
        epc_frame.pack(fill='x', pady=5)
        ttk.Label(epc_frame, text="EPC:", width=15).pack(side='left', padx=5)
        self.epc_start_btn = ttk.Button(epc_frame, text="Start EPC", command=lambda: self.start_component('epc'))
        self.epc_start_btn.pack(side='left', padx=5)
        self.epc_stop_btn = ttk.Button(epc_frame, text="Stop EPC", command=lambda: self.stop_component('epc'), state='disabled')
        self.epc_stop_btn.pack(side='left', padx=5)
        
        # eNB Controls
        enb_frame = ttk.Frame(button_frame)
        enb_frame.pack(fill='x', pady=5)
        ttk.Label(enb_frame, text="eNB:", width=15).pack(side='left', padx=5)
        self.enb_start_btn = ttk.Button(enb_frame, text="Start eNB", command=lambda: self.start_component('enb'))
        self.enb_start_btn.pack(side='left', padx=5)
        self.enb_stop_btn = ttk.Button(enb_frame, text="Stop eNB", command=lambda: self.stop_component('enb'), state='disabled')
        self.enb_stop_btn.pack(side='left', padx=5)
        
        # UE Controls
        ue_frame = ttk.Frame(button_frame)
        ue_frame.pack(fill='x', pady=5)
        ttk.Label(ue_frame, text="UE:", width=15).pack(side='left', padx=5)
        self.ue_start_btn = ttk.Button(ue_frame, text="Start UE", command=lambda: self.start_component('ue'))
        self.ue_start_btn.pack(side='left', padx=5)
        self.ue_stop_btn = ttk.Button(ue_frame, text="Stop UE", command=lambda: self.stop_component('ue'), state='disabled')
        self.ue_stop_btn.pack(side='left', padx=5)
        
        # Quick Actions
        quick_frame = ttk.Frame(button_frame)
        quick_frame.pack(fill='x', pady=10)
        ttk.Button(quick_frame, text="Start All", command=self.start_all).pack(side='left', padx=5)
        ttk.Button(quick_frame, text="Stop All", command=self.stop_all).pack(side='left', padx=5)
        
        # Information Frame
        info_frame = ttk.LabelFrame(control_frame, text="System Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.info_text = scrolledtext.ScrolledText(info_frame, height=15, wrap=tk.WORD)
        self.info_text.pack(fill='both', expand=True)
        self.info_text.insert('1.0', "Welcome to srsRAN GUI\n\n")
        self.info_text.insert('end', "This application provides a graphical interface for managing srsRAN components:\n")
        self.info_text.insert('end', "- EPC (Evolved Packet Core): The 4G core network\n")
        self.info_text.insert('end', "- eNB (Evolved Node B): The base station\n")
        self.info_text.insert('end', "- UE (User Equipment): The mobile device simulator\n\n")
        self.info_text.insert('end', "Please configure the binary paths and config files in the Configuration tab before starting.\n")
        self.info_text.config(state='disabled')
        
    def create_config_tab(self):
        """Create the configuration tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text='Configuration')
        
        # Create scrollable frame
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Working Directory
        ttk.Label(scrollable_frame, text="Working Directory:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=10, pady=(10,5))
        self.working_dir_var = tk.StringVar(value=self.config['working_dir'])
        ttk.Entry(scrollable_frame, textvariable=self.working_dir_var, width=60).grid(row=1, column=0, padx=10, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_directory(self.working_dir_var)).grid(row=1, column=1, padx=5)
        
        # EPC Configuration
        ttk.Label(scrollable_frame, text="EPC Configuration:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=10, pady=(20,5))
        
        ttk.Label(scrollable_frame, text="Binary Path:").grid(row=3, column=0, sticky='w', padx=20, pady=5)
        self.epc_binary_var = tk.StringVar(value=self.config['epc_binary'])
        ttk.Entry(scrollable_frame, textvariable=self.epc_binary_var, width=60).grid(row=4, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.epc_binary_var)).grid(row=4, column=1, padx=5)
        
        ttk.Label(scrollable_frame, text="Config File:").grid(row=5, column=0, sticky='w', padx=20, pady=5)
        self.epc_config_var = tk.StringVar(value=self.config['epc_config'])
        ttk.Entry(scrollable_frame, textvariable=self.epc_config_var, width=60).grid(row=6, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.epc_config_var)).grid(row=6, column=1, padx=5)
        
        # eNB Configuration
        ttk.Label(scrollable_frame, text="eNB Configuration:", font=('Arial', 10, 'bold')).grid(row=7, column=0, sticky='w', padx=10, pady=(20,5))
        
        ttk.Label(scrollable_frame, text="Binary Path:").grid(row=8, column=0, sticky='w', padx=20, pady=5)
        self.enb_binary_var = tk.StringVar(value=self.config['enb_binary'])
        ttk.Entry(scrollable_frame, textvariable=self.enb_binary_var, width=60).grid(row=9, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.enb_binary_var)).grid(row=9, column=1, padx=5)
        
        ttk.Label(scrollable_frame, text="Config File:").grid(row=10, column=0, sticky='w', padx=20, pady=5)
        self.enb_config_var = tk.StringVar(value=self.config['enb_config'])
        ttk.Entry(scrollable_frame, textvariable=self.enb_config_var, width=60).grid(row=11, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.enb_config_var)).grid(row=11, column=1, padx=5)
        
        # UE Configuration
        ttk.Label(scrollable_frame, text="UE Configuration:", font=('Arial', 10, 'bold')).grid(row=12, column=0, sticky='w', padx=10, pady=(20,5))
        
        ttk.Label(scrollable_frame, text="Binary Path:").grid(row=13, column=0, sticky='w', padx=20, pady=5)
        self.ue_binary_var = tk.StringVar(value=self.config['ue_binary'])
        ttk.Entry(scrollable_frame, textvariable=self.ue_binary_var, width=60).grid(row=14, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.ue_binary_var)).grid(row=14, column=1, padx=5)
        
        ttk.Label(scrollable_frame, text="Config File:").grid(row=15, column=0, sticky='w', padx=20, pady=5)
        self.ue_config_var = tk.StringVar(value=self.config['ue_config'])
        ttk.Entry(scrollable_frame, textvariable=self.ue_config_var, width=60).grid(row=16, column=0, padx=20, pady=5)
        ttk.Button(scrollable_frame, text="Browse", command=lambda: self.browse_file(self.ue_config_var)).grid(row=16, column=1, padx=5)
        
        # Save button
        ttk.Button(scrollable_frame, text="Save Configuration", command=self.save_configuration).grid(row=17, column=0, pady=20, padx=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def create_logs_tab(self):
        """Create the logs tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text='Logs')
        
        # Control buttons
        control_frame = ttk.Frame(logs_frame)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(control_frame, text="Clear Logs", command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Export Logs", command=self.export_logs).pack(side='left', padx=5)
        
        # Log display
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=30, wrap=tk.WORD, bg='black', fg='white', font=('Courier', 9))
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log(f"srsRAN GUI started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    def create_about_tab(self):
        """Create the about tab"""
        about_frame = ttk.Frame(self.notebook)
        self.notebook.add(about_frame, text='About')
        
        about_text = scrolledtext.ScrolledText(about_frame, height=30, wrap=tk.WORD)
        about_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        about_content = """
srsRAN GUI - Graphical User Interface for srsRAN

Version: 1.0.0

About srsRAN:
srsRAN is a free and open-source 4G and 5G software radio suite.
It includes:
- srsEPC: A light-weight 4G core network implementation
- srsENB: A 4G base station implementation
- srsUE: A 4G UE implementation

About this GUI:
This graphical user interface provides an easy way to manage and monitor
srsRAN components. Features include:
- Start/Stop srsRAN components
- Configure binary paths and configuration files
- Monitor component status
- View logs in real-time
- Export logs for analysis

Requirements:
- Python 3.6 or higher
- srsRAN installed on your system
- Appropriate permissions to run srsRAN components

Getting Started:
1. Install srsRAN on your system
2. Configure binary paths in the Configuration tab
3. Optionally specify configuration files for each component
4. Use the Control Panel to start/stop components

License:
This GUI is provided as-is for use with srsRAN.

For more information about srsRAN, visit:
https://www.srslte.com/

For issues and contributions to this GUI, please visit the project repository.
        """
        
        about_text.insert('1.0', about_content)
        about_text.config(state='disabled')
    
    def browse_file(self, var):
        """Browse for a file"""
        filename = filedialog.askopenfilename()
        if filename:
            var.set(filename)
    
    def browse_directory(self, var):
        """Browse for a directory"""
        dirname = filedialog.askdirectory()
        if dirname:
            var.set(dirname)
    
    def save_configuration(self):
        """Save the current configuration"""
        self.config['working_dir'] = self.working_dir_var.get()
        self.config['epc_binary'] = self.epc_binary_var.get()
        self.config['epc_config'] = self.epc_config_var.get()
        self.config['enb_binary'] = self.enb_binary_var.get()
        self.config['enb_config'] = self.enb_config_var.get()
        self.config['ue_binary'] = self.ue_binary_var.get()
        self.config['ue_config'] = self.ue_config_var.get()
        
        self.save_config()
        messagebox.showinfo("Success", "Configuration saved successfully!")
        self.log("Configuration saved")
    
    def start_component(self, component):
        """Start a srsRAN component"""
        binary_key = f'{component}_binary'
        config_key = f'{component}_config'
        
        binary = self.config[binary_key]
        config_file = self.config[config_key]
        
        # Build command
        cmd = [binary]
        if config_file and os.path.exists(config_file):
            cmd.append(config_file)
        
        try:
            self.log(f"Starting {component.upper()}: {' '.join(cmd)}")
            
            # Start process in working directory
            working_dir = self.config['working_dir']
            if not os.path.exists(working_dir):
                working_dir = os.getcwd()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
                text=True,
                bufsize=1
            )
            
            self.processes[component] = process
            
            # Start thread to read output
            threading.Thread(target=self.read_output, args=(component, process), daemon=True).start()
            
            self.log(f"{component.upper()} started with PID {process.pid}")
            
        except FileNotFoundError:
            self.log(f"ERROR: Binary not found: {binary}")
            messagebox.showerror("Error", f"Binary not found: {binary}\n\nPlease check the configuration.")
        except Exception as e:
            self.log(f"ERROR starting {component.upper()}: {str(e)}")
            messagebox.showerror("Error", f"Failed to start {component.upper()}: {str(e)}")
    
    def stop_component(self, component):
        """Stop a srsRAN component"""
        process = self.processes.get(component)
        if process and process.poll() is None:
            self.log(f"Stopping {component.upper()}")
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.log(f"Force killing {component.upper()}")
                    process.kill()
                self.log(f"{component.upper()} stopped")
            except Exception as e:
                self.log(f"ERROR stopping {component.upper()}: {str(e)}")
            finally:
                self.processes[component] = None
    
    def start_all(self):
        """Start all components in order"""
        self.log("Starting all components...")
        self.start_component('epc')
        self.root.after(2000, lambda: self.start_component('enb'))
        self.root.after(4000, lambda: self.start_component('ue'))
    
    def stop_all(self):
        """Stop all components"""
        self.log("Stopping all components...")
        for component in ['ue', 'enb', 'epc']:
            self.stop_component(component)
    
    def read_output(self, component, process):
        """Read output from a component process"""
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.log(f"[{component.upper()}] {line.rstrip()}")
        except Exception as e:
            self.log(f"Error reading output from {component.upper()}: {str(e)}")
    
    def update_status(self):
        """Update the status indicators"""
        for component in ['epc', 'enb', 'ue']:
            process = self.processes.get(component)
            is_running = process and process.poll() is None
            
            # Update status indicators
            status_label = getattr(self, f'{component}_status')
            status_text = getattr(self, f'{component}_status_text')
            start_btn = getattr(self, f'{component}_start_btn')
            stop_btn = getattr(self, f'{component}_stop_btn')
            
            if is_running:
                status_label.config(foreground='green')
                status_text.config(text=f"Running (PID: {process.pid})")
                start_btn.config(state='disabled')
                stop_btn.config(state='normal')
            else:
                status_label.config(foreground='red')
                status_text.config(text='Stopped')
                start_btn.config(state='normal')
                stop_btn.config(state='disabled')
                
                # Clean up finished process
                if process:
                    self.processes[component] = None
        
        # Schedule next update
        self.root.after(1000, self.update_status)
    
    def log(self, message):
        """Add a log message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state='normal')
        self.log_text.insert('end', log_message)
        self.log_text.see('end')
        self.log_text.config(state='disabled')
    
    def clear_logs(self):
        """Clear the log display"""
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        self.log("Logs cleared")
    
    def export_logs(self):
        """Export logs to a file"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.log',
            filetypes=[('Log files', '*.log'), ('Text files', '*.txt'), ('All files', '*.*')]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.get('1.0', 'end'))
                messagebox.showinfo("Success", f"Logs exported to {filename}")
                self.log(f"Logs exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export logs: {str(e)}")
    
    def cleanup(self):
        """Cleanup when closing the application"""
        self.log("Shutting down...")
        self.stop_all()
        self.root.after(1000, self.root.destroy)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = SrsRANGUI(root)
    
    # Handle window close
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit? All running components will be stopped."):
            app.cleanup()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
