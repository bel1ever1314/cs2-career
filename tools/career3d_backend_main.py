"""Frozen entry point: a CS2 exit watcher never initializes a Career save."""
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == '--cs2-environment-watchdog':
        from tools.career3d_cs2_watchdog import main as watchdog_main
        return watchdog_main(args[1:])
    from tools.career3d_service import main as service_main
    return service_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
