import flask_login
import os
import pymongo

from flask import Flask
from flask_bootstrap import Bootstrap


login_manager = flask_login.LoginManager()


def load_logs():
    db = pymongo.MongoClient(os.getenv('MONGODB_URI')).get_default_database()
    coll_name = os.getenv('LOGS_COLLECTION', 'message_logs')
    logs_coll = db.get_collection(coll_name)
    logs_coll.create_index([('text', 'text')], default_language='russian')
    return logs_coll


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('APP_SECRET', 'doMino')
    Bootstrap(app)

    login_manager.init_app(app)

    from .auth import bp
    app.register_blueprint(bp)

    from .views import bp as bp2
    app.register_blueprint(bp2)

    app.logs_coll = load_logs()

    return app
