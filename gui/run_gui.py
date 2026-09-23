"""Run the rivalcfg GUI:  python gui/run_gui.py [--gg] [--apply-last]"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ensure parent rivalcfg library (repo root) is importable when run from checkout
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

if "--apply-last" in sys.argv:
    from rivalcfg_gui.apply_last import main as apply_main
    raise SystemExit(apply_main())

# Default to GG-style layout (generic, like the screenshot); --classic for old form.
if "--classic" in sys.argv:
    from rivalcfg_gui.app import main
else:
    from rivalcfg_gui.gg_window import main

if __name__ == "__main__":
    raise SystemExit(main())
