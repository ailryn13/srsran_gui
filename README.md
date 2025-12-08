# srsRAN GUI

A graphical user interface for managing and monitoring srsRAN (4G/5G Software Radio Suite) components.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.6+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Overview

srsRAN GUI provides an intuitive graphical interface for managing srsRAN components, making it easier to:
- Start and stop srsRAN components (EPC, eNB, UE)
- Configure binary paths and configuration files
- Monitor component status in real-time
- View and export logs
- Manage multiple components simultaneously

## Features

### Control Panel
- **Real-time Status Monitoring**: Visual indicators show the running state of each component
- **Quick Controls**: Start/stop individual components or all at once
- **Process Information**: View PID and status of running processes

### Configuration Management
- **Binary Path Configuration**: Set paths to srsEPC, srsENB, and srsUE binaries
- **Config File Selection**: Specify custom configuration files for each component
- **Working Directory**: Set the working directory for srsRAN processes
- **Persistent Settings**: Configuration is saved and loaded automatically

### Log Viewer
- **Real-time Logs**: View output from all components in a unified log window
- **Timestamped Entries**: All log entries include timestamps for easy tracking
- **Export Functionality**: Export logs to file for analysis
- **Clear Logs**: Clear the log display when needed

## Prerequisites

1. **Python 3.6 or higher**
   ```bash
   python3 --version
   ```

2. **srsRAN installed on your system**
   - Visit [srsRAN website](https://www.srslte.com/) for installation instructions
   - Ensure `srsepc`, `srsenb`, and `srsue` binaries are accessible

3. **Required Python packages**
   ```bash
   pip install -r requirements.txt
   ```

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/ailryn13/srsran_gui.git
   cd srsran_gui
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Make the GUI executable (optional):
   ```bash
   chmod +x srsran_gui.py
   ```

## Usage

### Starting the GUI

Run the application:
```bash
python3 srsran_gui.py
```

Or if you made it executable:
```bash
./srsran_gui.py
```

### First Time Setup

1. Navigate to the **Configuration** tab
2. Set the binary paths:
   - EPC Binary: Path to `srsepc` (e.g., `/usr/local/bin/srsepc`)
   - eNB Binary: Path to `srsenb` (e.g., `/usr/local/bin/srsenb`)
   - UE Binary: Path to `srsue` (e.g., `/usr/local/bin/srsue`)

3. (Optional) Set configuration files:
   - EPC Config: Path to `epc.conf`
   - eNB Config: Path to `enb.conf`
   - UE Config: Path to `ue.conf`

4. Set the working directory where srsRAN should run

5. Click **Save Configuration**

### Running srsRAN Components

#### Individual Components

1. Go to the **Control Panel** tab
2. Click the **Start** button for the desired component
3. Monitor the status indicator (turns green when running)
4. View logs in the **Logs** tab

#### All Components

Click **Start All** to start components in the recommended order:
1. EPC (Core Network)
2. eNB (Base Station) - starts 2 seconds after EPC
3. UE (User Equipment) - starts 4 seconds after EPC

### Stopping Components

- Click **Stop** button for individual components
- Click **Stop All** to stop all running components
- Close the application (all components will be stopped automatically)

## Configuration File

The GUI stores configuration in `~/.srsran_gui/config.json`:

```json
{
  "epc_binary": "srsepc",
  "enb_binary": "srsenb",
  "ue_binary": "srsue",
  "epc_config": "",
  "enb_config": "",
  "ue_config": "",
  "working_dir": "/home/user"
}
```

## Architecture

### Components

1. **Main GUI Window** (`SrsRANGUI` class)
   - Built using Python Tkinter
   - Tabbed interface with 4 main sections

2. **Process Management**
   - Subprocess management for srsRAN components
   - Process monitoring and status tracking
   - Graceful shutdown handling

3. **Configuration System**
   - JSON-based configuration storage
   - Automatic save/load functionality
   - File browser integration

4. **Logging System**
   - Real-time log capture from subprocesses
   - Timestamped log entries
   - Export functionality

### Technology Stack

- **Python 3**: Core language
- **Tkinter**: GUI framework (included with Python)
- **subprocess**: Process management
- **threading**: Asynchronous log reading
- **json**: Configuration persistence

## Troubleshooting

### Binary Not Found Error

**Problem**: "Binary not found" error when starting a component

**Solution**:
- Verify srsRAN is installed: `which srsepc`
- Check the binary path in the Configuration tab
- Ensure you have execute permissions

### Component Won't Start

**Problem**: Component starts but immediately stops

**Solution**:
- Check the logs tab for error messages
- Verify configuration files are valid
- Ensure you have required permissions
- Check if ports are already in use

### Permission Denied

**Problem**: Permission denied when starting components

**Solution**:
- srsRAN may require root/sudo privileges for certain operations
- Run the GUI with appropriate permissions
- Consider using capabilities instead of root (Linux)

### GUI Doesn't Launch

**Problem**: Python/Tkinter errors when starting

**Solution**:
- Verify Python 3.6+ is installed
- Ensure Tkinter is installed: `python3 -m tkinter`
- On Ubuntu/Debian: `sudo apt-get install python3-tk`

## Development

### Project Structure

```
srsran_gui/
├── srsran_gui.py      # Main application
├── requirements.txt   # Python dependencies
├── README.md         # Documentation
└── .gitignore        # Git ignore rules
```

### Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Security Considerations

- The GUI runs srsRAN components as subprocesses with the same privileges
- Configuration files may contain sensitive information (stored in user's home directory)
- Be cautious when running components with elevated privileges

## License

This project is open source and available for use with srsRAN.

## Acknowledgments

- [srsRAN](https://www.srslte.com/) - The underlying 4G/5G software radio suite
- Python Tkinter - GUI framework

## Support

For issues related to:
- **This GUI**: Open an issue on the GitHub repository
- **srsRAN itself**: Visit [srsRAN documentation](https://docs.srsran.com/)

## Roadmap

Future enhancements may include:
- [ ] Real-time metrics visualization
- [ ] Network performance graphs
- [ ] Configuration file editor
- [ ] Multiple profile support
- [ ] Remote component management
- [ ] Advanced filtering for logs
- [ ] Component auto-restart on failure

## Version History

### v1.0.0 (Initial Release)
- Basic component management (start/stop)
- Configuration management
- Real-time status monitoring
- Log viewing and export
- Multi-component support