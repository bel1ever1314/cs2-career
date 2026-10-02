"""Frozen entry point: keep business imports after the service selects its save root."""
from tools.career3d_service import main


if __name__ == '__main__':
    raise SystemExit(main())
