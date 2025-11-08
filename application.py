# application.py  (RAÍZ DEL PROYECTO)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from app import create_app
application = create_app()

if __name__ == "__main__":
    application.run()
