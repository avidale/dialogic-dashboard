import argparse
import os

from dash_app import create_app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run LogViewer')
    parser.add_argument('--debug', help='Run the app in the debug mode', default=False, action='store_true')
    args = parser.parse_args()
    app = create_app()
    app.run('0.0.0.0', port=os.getenv('PORT', 5000), debug=args.debug)
