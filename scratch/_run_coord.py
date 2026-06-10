import traceback

try:
    from workers.platform_coordinator import run_once

    run_once()
    print("OK")
except Exception:
    traceback.print_exc()
    raise
