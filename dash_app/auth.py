import flask_login
import os

from dash_app import login_manager

from flask import Blueprint, render_template, request, redirect, url_for

bp = Blueprint('auth', __name__)


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(string_uid):
    user = User()
    user.id = string_uid
    return user


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    pwd = request.form['password']

    # todo: don't hardcode credentials
    if username == os.getenv('APP_LOGIN_USERNAME') and pwd == os.getenv('APP_LOGIN_PASSWORD'):
        user = User()
        user.id = username
        flask_login.login_user(user)
        return redirect(url_for('main.index'))

    return 'Invalid credentials'


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    flask_login.logout_user()
    return redirect(url_for('auth.login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('auth.login'))


