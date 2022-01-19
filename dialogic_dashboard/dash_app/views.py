from collections import OrderedDict

import flask_login

from flask import Blueprint, render_template, request, redirect, url_for, current_app, make_response, g
from flask_login import current_user
from pymongo.collection import Collection

bp = Blueprint('main', __name__)


def get_current_coll(app, user=None, coll_name=None):
    if coll_name:
        return coll_name
    with app.app_context():
        if hasattr(g, 'current_coll') and g.current_coll:
            return g.current_coll
    cookied = request.cookies.get('current_coll')
    if cookied and cookied in app.logs_map:
        coll_name = cookied
    elif hasattr(app, 'default_coll') and app.default_coll is not None:
        coll_name = app.default_coll
    return coll_name


def get_logs_coll(app, user=None, coll_name=None):
    coll_name = get_current_coll(app=app, user=user, coll_name=coll_name)
    if not coll_name or coll_name not in app.logs_map:
        return
    return app.logs_map[coll_name]


@bp.route('/')
@bp.route('/app/<coll_name>')
@flask_login.login_required
def index(coll_name=None):
    if coll_name:
        g.current_coll = coll_name
    resp = make_response(render_template('index.html', cc=coll_name))
    if coll_name:
        resp.set_cookie('current_coll', coll_name)
    return resp


def find_sessions(logs_coll: Collection, page=0, page_size=15, filters=None):
    match = {'$or': [{'data.session.session_id': {"$exists": True}}, {'session_id': {"$exists": True}}]}
    if filters:
        match.update(filters)
    complex_id = {  # https://stackoverflow.com/questions/36795528/
        "$cond": [
            {"$gt": ["$session_id", None]},
            "$session_id",
            "$data.session.session_id",
        ]
    }
    agg = logs_coll.aggregate([
        {'$match': match},
        {"$group": {
            "_id": complex_id,
            "latest": {"$max": '$timestamp'},
            'len': {'$sum': 1}
        }},
        {"$sort": {'latest': -1}},
        {'$skip': page * page_size},
        {'$limit': page_size},
    ])
    sessions = list(agg)
    return sessions


def find_messages(logs_coll: Collection, page=0, page_size=1000, filters=None, time_sort=1, extra_pipe=None, get_pairs=True):
    match = {}
    if filters:
        match.update(filters)
    pipeline = [
        {'$match': match},
        {'$lookup': {
            'from': logs_coll.name,
            'let': {'req_id': '$request_id', 'fu': '$from_user'},
            'pipeline': [{'$match': {
                '$expr':
                    {'$and':
                        [
                            {'$eq': ["$request_id", "$$req_id"]},
                            {'$ne': ["$from_user", '$$fu']}
                        ]
                    }
            }
            }],
            'as': 'paired'
        }},
        {'$unwind': '$paired'},
    ]
    if extra_pipe:
        pipeline.extend(extra_pipe)
    pipeline.extend([
        {"$sort": {'timestamp': -1}},
        {'$skip': page * page_size},
        {'$limit': page_size},
        {"$sort": {'timestamp': time_sort}},
    ])
    agg = logs_coll.aggregate(pipeline)
    messages = list(agg)
    if get_pairs:
        for m in messages:
            m['response_text'] = m['paired']['text'] if m.get('paired') and m['paired'].get('text') else None
            if not m.get('from_user'):
                m['response_text'], m['text'] = m['text'], m['response_text']
                m['data_req'] = m['paired'].get('data')
                m['data_resp'] = m.get('data')
            else:
                m['data_req'] = m.get('data')
                m['data_resp'] = m['paired'].get('data')
            if not m.get('handler') and m['paired'].get('handler'):
                m['handler'] = m['paired']['handler']

    # add request types in Alice messages
    for m in messages:
        if not m.get('request_type'):
            req_data = m.get('data_req')
            if isinstance(req_data, dict):
                r = req_data.get('request')
                if isinstance(r, dict):
                    m['request_type'] = r.get('type')
        if not m.get('directives'):
            resp_data = m.get('data_resp')
            if isinstance(resp_data, dict):
                r = resp_data.get('response')
                if isinstance(r, dict):
                    m['directives'] = r.get('directives')

        if 'session_id' not in m:
            m['session_id'] = None
            if isinstance(m['data'], dict):
                m['session_id'] = m['data'].get('session', {}).get('session_id')
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


def find_handlers(logs_coll: Collection, filters=None):
    match = {'handler': {"$exists": True}, 'from_user': False}
    if filters:
        match.update(filters)
    agg = logs_coll.aggregate([
        {'$match': match},
        {"$group": {
            "_id": "$handler",
            "first_time": {"$min": '$timestamp'},
            "last_time": {"$max": '$timestamp'},
            "response_example": {"$last": '$text'},
            'messages': {'$sum': 1}
        }},
        {"$sort": {'messages': -1}},
    ])
    return list(agg)


@bp.route('/sessions')
@bp.route('/<coll_name>/sessions')
@flask_login.login_required
def list_sessions(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 15))
    sessions = find_sessions(logs_coll=logs_coll, page=page, page_size=page_size)
    prev_url = url_for('main.list_sessions', page=page - 1) if page else None
    next_url = url_for('main.list_sessions', page=page + 1)
    return render_template('sessions.html', sessions=sessions, page=page, prev_url=prev_url, next_url=next_url)


@bp.route('/users')
@bp.route('/<coll_name>/users')
@flask_login.login_required
def list_users(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 15))
    users = find_users(logs_coll=logs_coll, page=page, page_size=page_size)
    prev_url = url_for('main.list_users', page=page - 1) if page else None
    next_url = url_for('main.list_users', page=page + 1)
    return render_template('users.html', users=users, page=page, prev_url=prev_url, next_url=next_url)


@bp.route('/session/<session_id>')
@bp.route('/<coll_name>/session/<session_id>')
@flask_login.login_required
def show_session(session_id, coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    messages = find_messages(logs_coll=logs_coll, filters={
        '$or': [{'data.session.session_id': session_id}, {'session_id': session_id}],
        'from_user': True
    })
    if not messages:
        return f'Session "{session_id}" not found', 404
    sess = messages[0]
    sess_data = sess.get('data')
    if isinstance(sess_data, dict):
        device = sess_data.get('meta', {}).get('client_id')
    else:
        device = None
    return render_template(
        'session.html', messages=messages, session_id=session_id, device=device, user_id=sess['user_id']
    )


@bp.route('/handlers')
@bp.route('/<coll_name>/handlers')
@flask_login.login_required
def list_handlers(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    handlers = find_handlers(logs_coll=logs_coll)
    return render_template('handlers.html', handlers=handlers)


@bp.route('/handler/<handler_name>')
@bp.route('/<coll_name>/handler/<handler_name>')
@flask_login.login_required
def show_handler(handler_name, coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 100))
    messages = find_messages(
        logs_coll=logs_coll, filters={'handler': handler_name, 'from_user': False}, time_sort=-1,
        page=page, page_size=page_size
    )
    if not messages:
        if not page:
            return f'Handler "{handler_name}" not found', 404
        return f'Handler "{handler_name}" does not have page {page}', 404
    prev_url = url_for(
        'main.show_handler', page=page - 1, handler_name=handler_name, coll_name=coll_name
    ) if page else None
    next_url = url_for('main.show_handler', page=page + 1, handler_name=handler_name, coll_name=coll_name)
    return render_template(
        'by_handler.html', messages=messages, handler_name=handler_name,
        prev_url=prev_url, next_url=next_url,
    )


@bp.route('/handler-unique/<handler_name>')
@bp.route('/<coll_name>/handler-unique/<handler_name>')
@flask_login.login_required
def show_handler_unique(handler_name, coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    page = int(request.args.get('page', 0))
    page_size = int(request.args.get('page_size', 100))
    extra = [
        {"$group": {
            "_id": '$paired.text',
            "first_time": {"$min": '$timestamp'},
            "last_time": {"$max": '$timestamp'},
            'count': {'$sum': 1}
        }},
    ]
    messages = find_messages(
        logs_coll=logs_coll, filters={'handler': handler_name, 'from_user': False}, time_sort=-1, extra_pipe=extra,
        page=page, page_size=page_size, get_pairs=False,
    )
    if not messages:
        if not page:
            return f'Handler "{handler_name}" not found', 404
        return f'Handler "{handler_name}" does not have page {page}', 404
    prev_url = url_for(
        'main.show_handler', page=page - 1, handler_name=handler_name, coll_name=coll_name
    ) if page else None
    next_url = url_for('main.show_handler_unique', page=page + 1, handler_name=handler_name, coll_name=coll_name)
    return render_template(
        'by_handler_unique.html', messages=messages, handler_name=handler_name,
        prev_url=prev_url, next_url=next_url,
    )


@bp.route('/session/random')
@bp.route('/<coll_name>/session/random')
@flask_login.login_required
def random_session(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    sampled = list(logs_coll.aggregate(
       [
           {'$match': {'from_user': True}},
           {'$sample': {'size': 1}},
       ]
    ))
    if sampled:
        # todo: fix the case when session is not marked in an alice-like way
        session_id = sampled[0].get('data', {}).get('session', {}).get('session_id') or sampled[0].get('session_id')
        if session_id is not None:
            return show_session(session_id=session_id)
        uid = sampled[0].get('user_id')
        return show_user(user_id=uid)
    return list_sessions()


@bp.route('/user/<user_id>')
@bp.route('/<coll_name>/user/<user_id>')
@flask_login.login_required
def show_user(user_id, coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    sessions = find_sessions(logs_coll=logs_coll, page=0, page_size=100500, filters={'user_id': user_id})
    return render_template('user.html', sessions=sessions, user_id=user_id)


@bp.route('/user_messages/<user_id>')
@bp.route('/<coll_name>/user_messages/<user_id>')
@flask_login.login_required
def show_user_messages(user_id, coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    messages = find_messages(logs_coll=logs_coll, filters={'user_id': user_id, 'from_user': True})
    if not messages:
        return f'User "{user_id}" not found', 404
    return render_template('user_messages.html', messages=messages, user_id=user_id)


@bp.route('/search', methods=['GET', 'POST'])
@bp.route('/<coll_name>/search', methods=['GET', 'POST'])
@flask_login.login_required
def search_text(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
    query = ''
    from_user = bool(request.args.get('query_type') != 'res')
    if request.args and request.args.get('query'):
        query = request.args['query']
    if query:
        messages = find_messages(logs_coll=logs_coll, filters={'$text': {'$search': query}, 'from_user': from_user})
    else:
        messages = []
    return render_template('search.html', messages=messages, query=query)


@bp.route('/api/messages-by-day')
@bp.route('/api/<coll_name>/messages-by-day')
@flask_login.login_required
def api_list_sessions(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
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
@bp.route('/api/<coll_name>/users-by-day')
@flask_login.login_required
def api_list_users(coll_name=None):
    logs_coll: Collection = get_logs_coll(current_app, current_user, coll_name=coll_name)
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
