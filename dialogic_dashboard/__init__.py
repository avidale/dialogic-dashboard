import argparse
import os

from .dash_app import create_app


def main():
    parser = argparse.ArgumentParser(description='Run LogViewer')
    parser.add_argument('--debug', help='Run the app in the debug mode', default=False, action='store_true')
    parser.add_argument('--url', help='The connection string to MongoDB', default=None, type=str)
    parser.add_argument('--collection', help='The collection name in MongoDB', default=None, type=str)
    args = parser.parse_args()
    app = create_app(mongodb_uri=args.url, collection_name=args.collection)
    app.run('0.0.0.0', port=os.getenv('PORT', 5000), debug=args.debug)


if __name__ == '__main__':
    main()
