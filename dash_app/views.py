import flask_login

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from pymongo.collection import Collection

bp = Blueprint('main', __name__)


@bp.route('/')
@flask_login.login_required
def index():
    return render_template('index.html')


def find_sessions(logs_coll: Collection, page=0, page_size=15, filters=None):
    match = {'data.session.session_id': {"$exists": True}}
    if filters:
        match.update(filters)
    agg = logs_coll.aggregate([
        {'$match': match},
        {"$group": {
            "_id": "$data.session.session_id",
            "latest": {"$max": '$timestamp'},
            'len': {'$sum': 1}
        }},
        {"$sort": {'latest': -1}},
        {'$skip': page * page_size},
        {'$limit': page_size},
    ])
    sessions = list(agg)
    return sessions


def find_users(logs_coll: Collection, page=0, page_size=15, filters=None):
    match = {'user_id': {"$exists": True}, 'from_user': True}
    if filters:
        match.update(filters)
    agg = logs_coll.aggregate([
        {'$match': match},
        {"$group": {
            "_id": "$user_id",
            "first_time": {"$min": '$timestamp'},
            "last_time": {"$max": '$timestamp'},
            'messages': {'$sum': 1}
        }},
        {"$sort": {'last_time': -1}},
        {'$skip': page * page_size},
        {'$limit': page_size},
    ])
    sessions = list(agg)
    return sessions


@bp.route('/sessions')
@flask_login.login_required
def list_sessions():
    logs_coll: Collection = current_app.logs_coll
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 15))
    sessions = find_sessions(logs_coll=logs_coll, page=page, page_size=page_size)
    prev_url = url_for('main.list_sessions', page=page - 1) if page else None
    next_url = url_for('main.list_sessions', page=page + 1)
    return render_template('sessions.html', sessions=sessions, page=page, prev_url=prev_url, next_url=next_url)


@bp.route('/users')
@flask_login.login_required
def list_users():
    logs_coll: Collection = current_app.logs_coll
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 15))
    users = find_users(logs_coll=logs_coll, page=page, page_size=page_size)
    prev_url = url_for('main.list_users', page=page - 1) if page else None
    next_url = url_for('main.list_users', page=page + 1)
    return render_template('users.html', users=users, page=page, prev_url=prev_url, next_url=next_url)


@bp.route('/session/<session_id>')
@flask_login.login_required
def show_session(session_id):
    logs_coll: Collection = current_app.logs_coll
    agg = logs_coll.aggregate([
        {'$match': {'data.session.session_id': session_id, 'from_user': True}},
        {'$lookup': {
            'from': 'message_logs',
            'let': {'reqid': '$request_id'},
            'pipeline': [{'$match':
                 { '$expr':
                    { '$and':
                       [
                         { '$eq': [ "$request_id",  "$$reqid" ] },
                         { '$eq': [ "$from_user", False ] }
                       ]
                    }
                 }
            }],
            #'localField': 'request_id',
            #'foreignField': 'request_id',
            'as': 'response'
        }},
        {"$sort": {'timestamp': 1}},
    ])
    messages = list(agg)
    if not messages:
        return f'Session "{session_id}" not found', 404
    return render_template('session.html', messages=messages, session=messages[0])


@bp.route('/user/<user_id>')
@flask_login.login_required
def show_user(user_id):
    logs_coll: Collection = current_app.logs_coll
    sessions = find_sessions(logs_coll=logs_coll, page=0, page_size=100500, filters={'user_id': user_id})
    return render_template('user.html', sessions=sessions, user_id=user_id)


@bp.route('/api/foo')
@flask_login.login_required
def api_foo():
    return {'foo': 'bar-protected'}


@bp.route('/api/all-sessions')
@flask_login.login_required
def api_list_sessions():
    logs_coll: Collection = current_app.logs_coll
    return {'foo': 'bar-protected'}
