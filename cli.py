"""CLI для ndVpi."""
import sys

def main():
    from .menu import run
    try:
        return run()
    except KeyboardInterrupt:
        print()
        return 130

if __name__ == "__main__":
    sys.exit(main())