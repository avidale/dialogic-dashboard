import flask_login
import os

from dash_app import login_manager

from flask import Blueprint, render_template, request, redirect, url_for, current_app

bp = Blueprint('auth', __name__)


class User(flask_login.UserMixin):
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def user_loader(string_uid):
    user = User(id=string_uid)
    return user


@bp.route('/login', methods=['GET', 'POST'])
def login():
    app_username = os.getenv('APP_LOGIN_USERNAME')
    app_password = os.getenv('APP_LOGIN_PASSWORD')

    if not app_username or not app_password:
        user = User(id='default_user')
        flask_login.login_user(user)
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    pwd = request.form['password']

    if username == app_username and pwd == app_password:
        user = User(id=username)
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


