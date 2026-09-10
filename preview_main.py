"""Packaged first-stage design checkpoint. Never opens a production save."""
import sys
from main import main

if __name__ == '__main__':
    sys.argv.append('--design-preview')
    main()
