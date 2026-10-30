from flask import render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from .models import db, User
from jose import jwt, JWTError
from datetime import datetime, timedelta
from functools import wraps
from .query_rag import query_rag_secure, query_rag_insecure

def set_jwt_cookie(response, user):
    token = jwt.encode(
        {
            'user_id': user.id,
            'email': user.email,
            'department': user.department,
            'exp': datetime.utcnow() + timedelta(days=1)
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )

    response.set_cookie(
        'jwt_token',
        token,
        httponly=True,
        secure=False,
        samesite='Lax'
    )
    return response

def get_jwt_data():
    token = request.cookies.get('jwt_token')
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
    except jwt.ExpiredSignatureError:
        return None
    except JWTError:
        return None

def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app.debug:
            return f(*args, **kwargs)
        jwt_data = get_jwt_data()
        if jwt_data is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@current_app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        department = request.form.get('department')

        if not all([email, password, confirm_password, department]):
            flash('All fields are required', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))

        if department not in ['engineering', 'sales', 'legal']:
            flash('Invalid department', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        user = User(email=email, department=department)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@current_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            response = make_response(redirect(url_for('home')))
            return set_jwt_cookie(response, user)

        flash('Invalid email or password', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')

@current_app.route('/logout')
@login_required
def logout():
    logout_user()
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('jwt_token')
    return response

@current_app.route('/', methods=['GET', 'POST'])
@login_required
@jwt_required
def home():
    question = ''
    answer = ''
    if request.method == 'POST':
        question = request.form.get('question', '')
        if question:
            try:
                jwt_data = get_jwt_data()
                if not jwt_data:
                    flash('Authentication error. Please login again.', 'error')
                    return redirect(url_for('login'))
                
                department = jwt_data.get('department')
                if not department:
                    flash('Department information missing. Please login again.', 'error')
                    return redirect(url_for('login'))
                
                answer = query_rag_secure(question, department)
                # answer = query_rag_insecure(question, department)
                print("Answer......", type(answer))
                if not answer or not isinstance(answer, str) or not answer.strip():
                    flash('No answer could be generated for your question. Please try rephrasing or ask a different question.', 'error')
                    return render_template('home.html', question=question, answer='')
                
            except Exception as e:
                flash(f'An error occurred while processing your question: {str(e)}', 'error')
                return render_template('home.html', question=question, answer='')
        else:
            flash('Please enter a question before submitting.', 'error')
            return render_template('home.html', question=question, answer='')
    
    return render_template('home.html', question=question, answer=answer)

@current_app.route('/insecure', methods=['GET', 'POST'])
@login_required
@jwt_required
def insecure():
    question = ''
    answer = ''
    if request.method == 'POST':
        question = request.form.get('question', '')
        if question:
            try:
                jwt_data = get_jwt_data()
                if not jwt_data:
                    flash('Authentication error. Please login again.', 'error')
                    return redirect(url_for('login'))

                department = jwt_data.get('department')
                if not department:
                    flash('Department information missing. Please login again.', 'error')
                    return redirect(url_for('login'))

                answer = query_rag_insecure(question, department)
                print("Answer......", type(answer))
                if not answer or not isinstance(answer, str) or not answer.strip():
                    flash('No answer could be generated for your question. Please try rephrasing or ask a different question.', 'error')
                    return render_template('home.html', question=question, answer='')

            except Exception as e:
                flash(f'An error occurred while processing your question: {str(e)}', 'error')
                return render_template('home.html', question=question, answer='')
        else:
            flash('Please enter a question before submitting.', 'error')
            return render_template('home.html', question=question, answer='')

    return render_template('home.html', question=question, answer=answer)
