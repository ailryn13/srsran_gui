# srsRAN GUI - Visual Mockup

This document provides ASCII art mockups of the srsRAN GUI interface.

## Main Window

```
┌────────────────────────────────────────────────────────────────────────────┐
│ srsRAN GUI - 4G/5G Software Radio Suite                          [_][□][X] │
├────────────────────────────────────────────────────────────────────────────┤
│ [Control Panel] [Configuration] [Logs] [About]                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─ Component Status ──────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  EPC (Core Network):          ● Stopped                              │  │
│  │  eNB (Base Station):          ● Stopped                              │  │
│  │  UE (User Equipment):         ● Stopped                              │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ Controls ──────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  EPC:      [ Start EPC ]  [ Stop EPC ]                               │  │
│  │  eNB:      [ Start eNB ]  [ Stop eNB ]                               │  │
│  │  UE:       [ Start UE  ]  [ Stop UE  ]                               │  │
│  │                                                                       │  │
│  │            [ Start All ]  [ Stop All ]                               │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ System Information ────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  Welcome to srsRAN GUI                                               │  │
│  │                                                                       │  │
│  │  This application provides a graphical interface for managing        │  │
│  │  srsRAN components:                                                  │  │
│  │  - EPC (Evolved Packet Core): The 4G core network                   │  │
│  │  - eNB (Evolved Node B): The base station                           │  │
│  │  - UE (User Equipment): The mobile device simulator                 │  │
│  │                                                                       │  │
│  │  Please configure the binary paths and config files in the          │  │
│  │  Configuration tab before starting.                                  │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Running State

```
┌────────────────────────────────────────────────────────────────────────────┐
│ srsRAN GUI - 4G/5G Software Radio Suite                          [_][□][X] │
├────────────────────────────────────────────────────────────────────────────┤
│ [Control Panel] [Configuration] [Logs] [About]                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─ Component Status ──────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  EPC (Core Network):          ● Running (PID: 12345)                 │  │
│  │  eNB (Base Station):          ● Running (PID: 12346)                 │  │
│  │  UE (User Equipment):         ● Running (PID: 12347)                 │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ Controls ──────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  EPC:      [ Start EPC ]  [ Stop EPC ]                               │  │
│  │             (disabled)     (active)                                  │  │
│  │  eNB:      [ Start eNB ]  [ Stop eNB ]                               │  │
│  │             (disabled)     (active)                                  │  │
│  │  UE:       [ Start UE  ]  [ Stop UE  ]                               │  │
│  │             (disabled)     (active)                                  │  │
│  │                                                                       │  │
│  │            [ Start All ]  [ Stop All ]                               │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Configuration Tab

```
┌────────────────────────────────────────────────────────────────────────────┐
│ srsRAN GUI - 4G/5G Software Radio Suite                          [_][□][X] │
├────────────────────────────────────────────────────────────────────────────┤
│ [Control Panel] [Configuration] [Logs] [About]                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Working Directory:                                                        │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /home/user                                              │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  EPC Configuration:                                                        │
│                                                                             │
│  Binary Path:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /usr/local/bin/srsepc                                   │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  Config File:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /etc/srsran/epc.conf                                    │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  eNB Configuration:                                                        │
│                                                                             │
│  Binary Path:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /usr/local/bin/srsenb                                   │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  Config File:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /etc/srsran/enb.conf                                    │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  UE Configuration:                                                         │
│                                                                             │
│  Binary Path:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /usr/local/bin/srsue                                    │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  Config File:                                                              │
│  ┌─────────────────────────────────────────────────────────┐ [Browse]     │
│  │ /etc/srsran/ue.conf                                     │              │
│  └─────────────────────────────────────────────────────────┘              │
│                                                                             │
│  [ Save Configuration ]                                                    │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Logs Tab

```
┌────────────────────────────────────────────────────────────────────────────┐
│ srsRAN GUI - 4G/5G Software Radio Suite                          [_][□][X] │
├────────────────────────────────────────────────────────────────────────────┤
│ [Control Panel] [Configuration] [Logs] [About]                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ Clear Logs ]  [ Export Logs ]                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │████████████████████████████████████████████████████████████████████│  │
│  │█ [11:23:45] srsRAN GUI started at 2025-12-08 11:23:45          █  │
│  │█ [11:23:50] Configuration saved                                █  │
│  │█ [11:24:00] Starting EPC: /usr/local/bin/srsepc                █  │
│  │█ [11:24:01] EPC started with PID 12345                         █  │
│  │█ [11:24:01] [EPC] Opening 1 RF devices with 1 RF channels...  █  │
│  │█ [11:24:02] [EPC] Attaching service at MME                     █  │
│  │█ [11:24:05] Starting eNB: /usr/local/bin/srsenb                █  │
│  │█ [11:24:06] eNB started with PID 12346                         █  │
│  │█ [11:24:06] [eNB] Setting frequency: DL=2680.0 MHz, UL=...    █  │
│  │█ [11:24:07] [eNB] Cell id=0x01 configured                      █  │
│  │█ [11:24:10] Starting UE: /usr/local/bin/srsue                  █  │
│  │█ [11:24:11] UE started with PID 12347                          █  │
│  │█ [11:24:12] [UE] Searching for cell...                         █  │
│  │█ [11:24:13] [UE] Found cell with PCI=1                         █  │
│  │█ [11:24:15] [UE] RRC connected                                 █  │
│  │█ [11:24:16] [UE] Network attach successful                     █  │
│  │█                                                                █  │
│  │████████████████████████████████████████████████████████████████│  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Color Legend

- ● Red Circle: Component is stopped
- ● Green Circle: Component is running
- Disabled buttons: Grayed out when action is not available
- Active buttons: Normal appearance when action is available
- Black background (in Logs tab): Terminal-style display
- White text (in Logs tab): Easy to read on dark background

## Key Interactions

1. **Starting Components**:
   - Click "Start EPC" → Status turns green, Stop button enables, Start button disables
   - Logs show startup messages in real-time

2. **Stopping Components**:
   - Click "Stop EPC" → Status turns red, Start button enables, Stop button disables
   - Logs show shutdown messages

3. **Configuration**:
   - Click "Browse" → File/directory selection dialog opens
   - Click "Save Configuration" → Settings persist to ~/.srsran_gui/config.json

4. **Logs**:
   - "Clear Logs" → Empties the log display
   - "Export Logs" → Opens save file dialog to export logs

## Window Close Behavior

When clicking the [X] button:
```
┌─────────────────────────────────────┐
│ Quit                        [?]     │
├─────────────────────────────────────┤
│                                     │
│ Do you want to quit?                │
│ All running components will be      │
│ stopped.                            │
│                                     │
│          [ OK ]    [ Cancel ]       │
│                                     │
└─────────────────────────────────────┘
```

If OK is clicked, all components are gracefully stopped before the application exits.
