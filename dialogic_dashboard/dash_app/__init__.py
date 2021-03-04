import flask_login
import os
import pymongo

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import current_user

from .app_config import AppConfig

login_manager = flask_login.LoginManager()


def load_logs(mongo_uri=None, logs_collection=None):
    db = pymongo.MongoClient(mongo_uri or os.getenv('MONGODB_URI')).get_default_database()
    coll_name = logs_collection or os.getenv('LOGS_COLLECTION', 'message_logs')
    logs_coll = db.get_collection(coll_name)
    logs_coll.create_index([('text', 'text')], default_language='russian')
    return logs_coll


def create_app(configs=None, mongodb_uri=None, collection_name=None):
    app = Flask(__name__)
    app.secret_key = os.getenv('APP_SECRET', 'doMino')
    Bootstrap(app)

    login_manager.init_app(app)

    from .auth import bp
    app.register_blueprint(bp)

    from .views import bp as bp2, get_current_coll
    app.register_blueprint(bp2)

    if not configs:
        configs = {'default': {
            'name': 'default',
            'database_uri': mongodb_uri or os.getenv('MONGODB_URI'),
            'logs_collection_name': collection_name or os.getenv('LOGS_COLLECTION', 'message_logs'),
        }}

    app.configs = {k: AppConfig(id=k, **v) for k, v in (configs or {}).items()}
    app.default_coll = list(configs.keys())[0] if configs else None

    app.logs_map = {
        k: load_logs(mongo_uri=v.database_uri, logs_collection=v.logs_collection_name)
        for k, v in app.configs.items()
    }

    @app.context_processor
    def inject_configs():
        cc = get_current_coll(app=app, user=current_user)
        return dict(configs=configs, current_coll=cc)

    return app
