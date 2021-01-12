from collections import OrderedDict

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


def find_messages(logs_coll: Collection, page=0, page_size=1000, filters=None):
    match = {}
    if filters:
        match.update(filters)
    agg = logs_coll.aggregate([
        {'$match': match},
        {'$lookup': {
            'from': logs_coll.name,
            'let': {'req_id': '$request_id'},
            'pipeline': [{'$match': {
                '$expr':
                    {'$and':
                        [
                            {'$eq': ["$request_id", "$$req_id"]},
                            {'$eq': ["$from_user", False]}
                        ]
                    }
                }
            }],
            'as': 'response'
        }},
        {"$sort": {'timestamp': -1}},
        {'$skip': page * page_size},
        {'$limit': page_size},
        {"$sort": {'timestamp': 1}},
    ])
    messages = list(agg)
    for m in messages:
        m['response_text'] = m['response'][0]['text'] if m['response'] and m['response'][0].get('text') else None
    return messages


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
    return list(agg)


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
    messages = find_messages(logs_coll=logs_coll, filters={'data.session.session_id': session_id, 'from_user': True})
    if not messages:
        return f'Session "{session_id}" not found', 404
    return render_template('session.html', messages=messages, session=messages[0])


@bp.route('/session/random')
@flask_login.login_required
def random_session():
    logs_coll: Collection = current_app.logs_coll
    sampled = list(logs_coll.aggregate(
       [
           {'$match': {'from_user': True}},
           {'$sample': {'size': 1}},
       ]
    ))
    if sampled:
        session_id = sampled[0]['data']['session']['session_id']
        return show_session(session_id=session_id)
    return list_sessions()


@bp.route('/user/<user_id>')
@flask_login.login_required
def show_user(user_id):
    logs_coll: Collection = current_app.logs_coll
    sessions = find_sessions(logs_coll=logs_coll, page=0, page_size=100500, filters={'user_id': user_id})
    return render_template('user.html', sessions=sessions, user_id=user_id)


@bp.route('/search', methods=['GET', 'POST'])
@flask_login.login_required
def search_text():
    logs_coll: Collection = current_app.logs_coll
    query = ''
    if request.args and request.args.get('query'):
        query = request.args['query']
    if query:
        messages = find_messages(logs_coll=logs_coll, filters={'$text': {'$search': query}, 'from_user': True})
    else:
        messages = []
    return render_template('search.html', messages=messages, query=query)


@bp.route('/api/messages-by-day')
@flask_login.login_required
def api_list_sessions():
    logs_coll: Collection = current_app.logs_coll
    r = logs_coll.aggregate([
        {'$match': {
            'from_user': True,
        }},
        {"$group": {
            "_id": {
                "year": {
                    "$substr": ["$timestamp", 0, 4]
                },
                "month": {
                    "$substr": ["$timestamp", 5, 2]
                },
                "day": {
                    "$substr": ["$timestamp", 8, 2]
                }
            },
            'count': {'$sum': 1}
        }},
        {"$sort": OrderedDict([('_id.year', 1), ('_id.month', 1), ('_id.day', 1)])},
    ])
    indexes = []
    values = []
    for item in r:
        indexes.append('-'.join([item['_id']['year'], item['_id']['month'], item['_id']['day']]))
        values.append(item['count'])
    return {
        'indexes': indexes,
        'values': values,
    }

@bp.route('/api/users-by-day')
@flask_login.login_required
def api_list_users():
    logs_coll: Collection = current_app.logs_coll
    r = logs_coll.aggregate([
        {'$match': {
            'from_user': True,
        }},
        {"$group": {
            "_id": {
                "year": {
                    "$substr": ["$timestamp", 0, 4]
                },
                "month": {
                    "$substr": ["$timestamp", 5, 2]
                },
                "day": {
                    "$substr": ["$timestamp", 8, 2]
                },
                'user_id': '$user_id',
            },
            'count': {'$sum': 1}
        }},
        {"$group": {
            "_id": {
                "year": '$_id.year',
                "month": '$_id.month',
                "day": '$_id.day',
            },
            'count': {'$sum': 1}
        }},
        {"$sort": OrderedDict([('_id.year', 1), ('_id.month', 1), ('_id.day', 1)])},
    ])
    indexes = []
    values = []
    for item in r:
        indexes.append('-'.join([item['_id']['year'], item['_id']['month'], item['_id']['day']]))
        values.append(item['count'])
    return {
        'indexes': indexes,
        'values': values,
    }
