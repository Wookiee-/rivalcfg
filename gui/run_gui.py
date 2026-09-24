"""Run the rivalcfg GUI:  python gui/run_gui.py [--gg] [--classic] [--dark] [--tray] [--apply-last]"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ensure parent rivalcfg library (repo root) is importable when run from checkout
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

if "--apply-last" in sys.argv:
    from rivalcfg_gui.apply_last import main as apply_main
    raise SystemExit(apply_main())

# Default to GG-style layout (generic, like the screenshot); --classic for old form.
# Theme is native/system by default for all desktop environments;
# pass --dark (or RIVALCFG_GUI_THEME=dark) for the forced GG dark look.
# Pass --tray to start minimized to the system tray (all DEs with a tray/SNI host).
if "--classic" in sys.argv:
    from rivalcfg_gui.app import main
else:
    from rivalcfg_gui.gg_window import main

if __name__ == "__main__":
    raise SystemExit(main())
