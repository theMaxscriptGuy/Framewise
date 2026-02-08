import sys
from framewise.app import FramewiseApp

def main() -> int:
    app = FramewiseApp(sys.argv)
    return app.run()

if __name__ == "__main__":
    raise SystemExit(main())
