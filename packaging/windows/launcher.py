"""Frozen entry point: protect the multiprocessing bootloader on Windows."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--release-smoke":
        from browser.release_smoke import run
        raise SystemExit(run(sys.argv[2]))
    from browser.main import main
    raise SystemExit(main())
