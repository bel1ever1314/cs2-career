"""Packaged player-flow checkpoint; never opens a normal player save."""
import sys
from main import main

if __name__ == '__main__':
    sys.argv.append('--playtest')
    main()
