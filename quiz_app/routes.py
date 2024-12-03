from flask import (
    Blueprint,
    render_template as render,
    flash,
    redirect,
    url_for,
    render_template,
    request,
    jsonify,
    send_file
)
from . import models
from .extentions import db, socketio
from flask_login import (
    logout_user,
    login_required,
    login_user,
    current_user
)
from .models import Notification
from random import shuffle
from werkzeug.utils import secure_filename
from os.path import join, dirname
from add_questions import (
    load_questions,
    add_to_db
)
from flask import current_app
from .constants import ADD_QUESTIONS
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import csv
from io import StringIO, BytesIO
from sqlalchemy import or_
from datetime import timedelta
from sqlalchemy import func, and_, distinct
import json
from functools import wraps
import time
from sqlalchemy import text
from flask_socketio import emit, join_room, leave_room
from .utils import (
    notify_quiz_completion, 
    notify_leaderboard_position, 
    get_user_leaderboard_position,
    send_notification,
    generate_verification_token,
    verify_token
)
from io import BytesIO
import io
from datetime import datetime, timedelta
import pytz
from base64 import b64encode
from .static.images.medals import GOLD_MEDAL, SILVER_MEDAL, BRONZE_MEDAL
import base64

main = Blueprint("main", __name__)

@main.app_template_filter('timeago')
def timeago(date):
    """Convert a datetime to "time ago" text."""
    now = datetime.utcnow()
    diff = now - date
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years}y ago"
    if diff.days > 30:
        months = diff.days // 30
        return f"{months}mo ago"
    if diff.days > 0:
        return f"{diff.days}d ago"
    if diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    if diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    return "just now"

@main.app_template_filter('b64encode')
def b64encode_filter(data):
    """Template filter to base64 encode data"""
    if isinstance(data, str):
        data = data.encode()
    return base64.b64encode(data).decode()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access required", "warning")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated_function

@main.route("/")
def index():
    return render("index.html")

@main.route("/login", methods=["GET", "POST"])
def login():
    if not current_user.is_anonymous:
        flash("You are already logged in, logout to login with another account", "info")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        data = request.form.to_dict()
        user = models.User.query.filter_by(
            name=data["name"],
            is_admin=True if "is_admin" in data.keys() else False
        ).first()
        if user is not None and user.verify_password(data["password"]):
            login_user(user)
            flash("logged in successfully", "success")
            return redirect(url_for("main.index"))
        else:
            flash("user's name or password is wrong", "warning")
    return render("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("logged out", "info")
    return redirect(url_for("main.index"))
    

@main.route("/register", methods=["GET", "POST"])
def register():
    if not current_user.is_anonymous:
        flash("You are already logged in, logout to login with another account", "info")
        return redirect(url_for('main.index'))
    if request.method == "POST":
        data = request.form.to_dict()
        name = data["name"]
        password = data["password"]
        if models.User.query.filter_by(name=name).first() is not None:
            flash("user with this username already exists", "info")
            return redirect(url_for("main.register"))
        user = models.User(
            name=name,
            is_admin=False,
            created_at=datetime.utcnow()
        )
        user.set_password(data["password"])
        db.session.add(user)
        db.session.commit()
        
        # Send welcome notification with correct metadata
        send_notification(
            user=user,
            title="Welcome to Quiz App!", 
            message="Complete your profile to get started with quizzes!",
            type="success",
            link=url_for("main.edit_profile"),
            priority="high",
            expiry_days=7,
            metadata={
                "registration_date": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "next_steps": [
                    "Add a profile picture",
                    "Fill in your bio",
                    "Complete your profile information"
                ]
            }
        )
        
        flash("Registration successful!", "success")
        return redirect(url_for("main.login"))
    return render("register.html")


@main.route("/add", methods=["GET", "POST"])
@login_required
def add_questions():
    if request.method == "POST":
        try:
            data = request.form.to_dict()
            files = request.files
            category_id = data.get('category')
            difficulty = data.get('difficulty', 'medium')
            
            submitted_questions = []  # Store all submitted questions
            
            for i in range(1, ADD_QUESTIONS+1):
                question_type = data.get(f'qt{i}', 'multiple_choice')
                
                # Handle image upload if it's an image-based question
                image_url = None
                if question_type == 'image' and f'qi{i}' in files:
                    image = files[f'qi{i}']
                    if image and allowed_file(image.filename):
                        filename = secure_filename(image.filename)
                        image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                        image_url = filename

                # Create question based on type
                question = models.Question(
                    question=data[f"q{i}"],
                    question_type=question_type,
                    image_url=image_url,
                    creator_id=current_user.id,
                    category_id=category_id,
                    difficulty=difficulty,
                    verified=False
                )

                # Handle options based on question type
                if question_type == 'true_false':
                    question.option1 = "True"
                    question.option2 = "False"
                    question.correct_option = data.get(f"q{i}tf")
                else:
                    question.option1 = data.get(f"q{i}o1")
                    question.option2 = data.get(f"q{i}o2")
                    question.option3 = data.get(f"q{i}o3")
                    question.option4 = data.get(f"q{i}o4")
                    question.correct_option = data.get(f"q{i}c")[0].upper()

                db.session.add(question)
                submitted_questions.append(question)  # Add to our list
                
            db.session.commit()  # Commit once after all questions are added

            # Notify all admins about all submitted questions
            admins = models.User.query.filter_by(is_admin=True).all()
            for admin in admins:
                send_notification(
                    user=admin,
                    title=f"New Questions Submitted ({len(submitted_questions)})",
                    message=f"User {current_user.name} has submitted {len(submitted_questions)} new questions for review",
                    type="admin",
                    priority="normal",
                    link=url_for('main.review_questions'),
                    metadata={
                        "submitter": current_user.name,
                        "question_count": len(submitted_questions),
                        "questions": [
                            {
                                "id": q.id,
                                "type": q.question_type,
                                "category": q.category.name,
                                "difficulty": q.difficulty
                            } for q in submitted_questions
                        ]
                    }
                )

            flash("Your questions have been submitted for verification", "success")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error submitting questions: {str(e)}", "error")
            
    return render(
        "add_questions.html",
        questions=ADD_QUESTIONS,
        categories=models.Category.query.all(),
        show=True
    )

def allowed_file(filename, allowed_extensions=None):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return extension in allowed_extensions

@main.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    # Check if user has any quiz sets
    if not current_user.quiz_sets:  # Changed from question_sets to quiz_sets
        flash("You don't have any quiz sets assigned to you yet", "info")
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        try:
            data = request.form.to_dict()
            set_id = data.get("set")
            quiz_set = models.QuestionSet.query.get_or_404(set_id)
            
            # Verify user has access to this set
            if quiz_set not in current_user.quiz_sets:  # Changed from question_sets to quiz_sets
                flash("You don't have access to this quiz set", "warning")
                return redirect(url_for("main.quiz"))
            
            # Get questions for this set
            questions = models.Question.query.filter_by(
                question_set_id=set_id,
                verified=True
            ).all()

            if not questions:
                flash("This quiz has no questions yet.", "warning")
                return redirect(url_for("main.quiz"))

            # Show quiz
            shuffle(questions)
            return render(
                "quiz.html",
                questions=questions,
                question_set=quiz_set,
                show=True
            )

        except Exception as e:
            db.session.rollback()
            print(f"Error saving result: {str(e)}")
            flash(f"Error saving quiz result: {str(e)}", "error")
            return redirect(url_for("main.quiz"))

    # GET method - show quiz form
    return render_template(
        "quiz/index.html",
        quiz_sets=current_user.quiz_sets  # Changed from question_sets to quiz_sets
    )

@main.route("/result")
@login_required
def result():
    try:
        results = models.Result.query.filter_by(
            user_id=current_user.id
        ).order_by(models.Result.created_at.desc()).all()
        
        if not results:
            flash("No quiz results found.", "info")
            return redirect(url_for("main.quiz"))
        
        formatted_results = []
        for res in results:
            quiz_set = models.QuestionSet.query.get(res.question_set_id)
            formatted_results.append({
                'id': res.id,
                'set_name': quiz_set.name if quiz_set else "Unknown Quiz",
                'total_questions': res.total_number,
                'correct': res.correct,
                'incorrect': res.incorrect,
                'not_attempt': res.not_attempt,
                'score': (res.correct / res.total_number * 100) if res.total_number > 0 else 0,
                'time_taken': res.formatted_time,
                'date': utc_to_gmt7(res.created_at)  # Convert to GMT+7
            })
        
        return render_template("result.html", results=formatted_results)
        
    except Exception as e:
        print(f"Error loading results: {e}")
        flash("Error loading quiz results.", "error")
        return redirect(url_for("main.quiz"))


@main.route("/leaderboard")
@login_required
def leaderboard():
    quiz_sets = models.QuestionSet.query.all()
    selected_set = request.args.get('set_id', type=int)
    
    if selected_set:
        # Get all results for the selected quiz set
        results = models.Result.query.filter_by(question_set_id=selected_set)\
            .join(models.User)\
            .add_columns(
                models.User.name.label('user_name'),
                models.User
            ).all()
        
        # Create a dictionary to store best attempts per user
        best_attempts = {}
        for result, user_name, user in results:
            user_id = result.user_id
            score = (result.correct / result.total_number * 100)
            current_best = best_attempts.get(user_id)
            
            if not current_best or score > current_best['score'] or \
               (score == current_best['score'] and result.time_taken < current_best['time_taken']):
                best_attempts[user_id] = {
                    'user_name': user_name,
                    'user': user,
                    'score': score,
                    'formatted_time': result.formatted_time,
                    'date': result.created_at,
                    'time_taken': result.time_taken
                }
        
        # Convert to list and sort
        formatted_results = [
            {**data, 'user_id': user_id} 
            for user_id, data in best_attempts.items()
        ]
        formatted_results.sort(key=lambda x: (-x['score'], x['time_taken']))
            
        current_set = models.QuestionSet.query.get(selected_set)
    else:
        formatted_results = []
        current_set = None

    return render_template('leaderboard.html',
                         results=formatted_results,
                         sets=quiz_sets,
                         current_set=current_set,
                         utc_to_gmt7=utc_to_gmt7,
                         gold_medal=GOLD_MEDAL.encode(),
                         silver_medal=SILVER_MEDAL.encode(),
                         bronze_medal=BRONZE_MEDAL.encode())  # Removed b64encode

@main.route("/admin")
@login_required
@admin_required
def admin():
    try:
        # Gather statistics
        stats = {
            'total_users': models.User.query.filter_by(is_admin=False).count(),
            'active_users': models.User.query.filter_by(is_admin=False).join(models.Result).distinct().count(),
            'total_sets': models.QuestionSet.query.count(),
            'active_sets': models.QuestionSet.query.join(models.Question).distinct().count(),
            'total_questions': models.Question.query.count(),
            'verified_questions': models.Question.query.filter_by(verified=True).count(),
            'pending_reviews': models.Question.query.filter_by(verified=False).count(),
            'total_categories': models.Category.query.count()
        }
        
        # Get recent activities
        recent_activities = []
        results = models.Result.query.order_by(models.Result.created_at.desc()).limit(5).all()
        for result in results:
            quiz_set = models.QuestionSet.query.get(result.question_set_id)
            if quiz_set:  # Only add if quiz set exists
                recent_activities.append({
                    'action': 'Quiz Completed',
                    'description': f"{quiz_set.name} - Score: {result.correct}/{result.total_number}",
                    'user': result.user.name,
                    'time': result.created_at.strftime('%Y-%m-%d %H:%M')
                })
        
        # Get latest quiz results
        latest_results = []
        for result in results:
            quiz_set = models.QuestionSet.query.get(result.question_set_id)
            if quiz_set:  # Only add if quiz set exists
                latest_results.append({
                    'user_name': result.user.name,
                    'set_name': quiz_set.name,
                    'score': (result.correct / result.total_number * 100),
                    'time_taken': f"{result.time_taken // 60}:{result.time_taken % 60:02d}"
                })
        
        return render_template(
            "admin/admin.html",
            stats=stats,
            recent_activities=recent_activities,
            latest_results=latest_results
        )
        
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")  # For debugging
        flash("Error loading admin dashboard", "error")
        return redirect(url_for("main.index"))

@main.route("/admin/results")
@login_required
def admin_results():
    if current_user.is_admin:
        res = models.Result.query.all()
        return render("admin/result.html", results=res)
    else:
        flash("You are not an admin, so you can't access this portal", "warning")
        return redirect(url_for('main.index'))

@main.route("/admin/add_questions", methods=["GET", "POST"])
@login_required
def admin_add_questions():
    if current_user.is_admin:
        if request.method == "POST":
            data = request.form.to_dict()
            verified_count = 0
            rejected_count = 0
            
            # Handle bulk actions
            if 'bulk_action' in data:
                action = data['bulk_action']
                if action == 'verify_all':
                    # Verify all pending questions
                    questions = models.Question.query.filter_by(verified=False).all()
                    for question in questions:
                        question.verified = True
                        verified_count += 1
                
                elif action == 'reject_all':
                    # Reject all pending questions
                    questions = models.Question.query.filter_by(verified=False).all()
                    for question in questions:
                        db.session.delete(question)
                        rejected_count += 1
                
                elif action in ['verify_selected', 'reject_selected']:
                    # Handle selected questions
                    selected_ids = request.form.getlist('selected_questions')
                    for q_id in selected_ids:
                        question = models.Question.query.get(int(q_id))
                        if question:
                            if action == 'verify_selected':
                                question.verified = True
                                verified_count += 1
                            else:
                                db.session.delete(question)
                                rejected_count += 1
            
            # Handle individual question actions
            elif 'action' in data:
                action = data['action']
                if action.startswith(('verify_', 'reject_')):
                    action_type, q_id = action.split('_')
                    question = models.Question.query.get(int(q_id))
                    if question:
                        if action_type == 'verify':
                            question.verified = True
                            verified_count += 1
                        else:
                            db.session.delete(question)
                            rejected_count += 1
            
            db.session.commit()
            flash(f"Verified {verified_count} questions and rejected {rejected_count} questions", "success")
            
        # Get all unverified questions
        questions = models.Question.query.filter_by(verified=False).all()
        return render("admin/add_questions.html", questions=questions)
    else:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/upload", methods=["GET", "POST"])
@login_required
def admin_upload_questions():
    if current_user.is_admin:
        if request.method == "POST":
            if 'qFile' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['qFile']
            if (fname:=file.filename) == '':
                flash('No selected file')
                return redirect(request.url)
            if file and ('.' in fname and fname.rsplit('.', 1)[1].lower() in ["csv"]):
                flocation = join(dirname(__file__), "..", "upload_files", "questions.csv")
                file.save(flocation)
                qbank = load_questions(flocation)
                q_added = add_to_db(
                    qbank=qbank,
                    app=current_app,
                    db=db,
                    verbose=False
                )
                flash(f"{q_added} questions added successfully", "success")

        return render("admin/upload_questions.html")
    else:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/create-set", methods=["GET", "POST"])
@login_required
@admin_required
def create_set():
    if request.method == "POST":
        try:
            data = request.form
            # Create new quiz set
            quiz_set = models.QuestionSet(
                name=data.get('name'),
                time_limit=int(data.get('time_limit', 30)) * 60  # Convert minutes to seconds
            )
            db.session.add(quiz_set)
            db.session.commit()  # Commit to get quiz_set.id

            # Handle manual selection
            if data.get('selection_method') == 'manual':
                question_ids = request.form.getlist('questions[]')
                questions = models.Question.query.filter(models.Question.id.in_(question_ids)).all()
                for question in questions:
                    question.question_set_id = quiz_set.id
            else:
                # Handle automatic selection
                total_questions = int(data.get('total_questions', 10))
                category_id = data.get('category')
                
                # Calculate question counts
                easy_percent = int(data.get('easy_percent', 30))
                medium_percent = int(data.get('medium_percent', 40))
                hard_percent = int(data.get('hard_percent', 30))
                
                if easy_percent + medium_percent + hard_percent != 100:
                    raise ValueError("Difficulty percentages must sum to 100")
                
                easy_count = int(total_questions * easy_percent / 100)
                medium_count = int(total_questions * medium_percent / 100)
                hard_count = total_questions - easy_count - medium_count
                
                # Build query base
                base_query = models.Question.query.filter_by(verified=True)
                if category_id:
                    base_query = base_query.filter_by(category_id=category_id)
                
                # Get questions for each difficulty
                easy_questions = base_query.filter_by(difficulty='easy').order_by(func.random()).limit(easy_count).all()
                medium_questions = base_query.filter_by(difficulty='medium').order_by(func.random()).limit(medium_count).all()
                hard_questions = base_query.filter_by(difficulty='hard').order_by(func.random()).limit(hard_count).all()
                
                # Update all selected questions
                all_questions = easy_questions + medium_questions + hard_questions
                if len(all_questions) < total_questions:
                    raise ValueError(f"Not enough questions available. Found {len(all_questions)} of {total_questions} requested")
                
                for question in all_questions:
                    question.question_set_id = quiz_set.id
            
            db.session.commit()
            flash("Quiz set created successfully!", "success")
            return redirect(url_for("main.admin_show_sets"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating quiz set: {str(e)}", "error")
            return redirect(url_for("main.create_set"))

    return render_template(
        "admin/create_set.html",
        categories=models.Category.query.all(),
        questions=models.Question.query.filter_by(verified=True).all()
    )

def notify_users_about_quiz(users, quiz_set):
    """
    Placeholder for user notification system.
    This could be implemented with email, in-app notifications, etc.
    """
    # TODO: Implement actual notification system
    pass

@main.route("/admin/sets/<int:set_id>/distribute", methods=["GET", "POST"])
@login_required
@admin_required
def distribute_set(set_id):
    quiz_set = models.QuestionSet.query.get_or_404(set_id)
    
    if request.method == "POST":
        try:
            # Get selected users
            user_ids = request.form.getlist('users')
            users = models.User.query.filter(models.User.id.in_(user_ids)).all()
            
            # Add users to quiz set
            for user in users:
                if user not in quiz_set.users:  # Using the quiz_set relationship
                    quiz_set.users.append(user)
            
            # Send notifications if checkbox is checked
            if request.form.get('notify_users') == 'on':
                for user in users:
                    send_notification(
                        user=user,
                        title="New Quiz Set Available! 📚",
                        message=f"A new quiz set '{quiz_set.name}' has been assigned to you",
                        type="quiz",
                        priority="high",
                        link=url_for('main.quiz', set_id=quiz_set.id),
                        metadata={
                            "quiz_set_name": quiz_set.name,
                            "question_count": len(quiz_set.questions),
                            "time_limit": f"{quiz_set.time_limit // 60} minutes",
                            "categories": [q.category.name for q in quiz_set.questions if q.category],
                            "assigned_by": current_user.name,
                            "assigned_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    )
            
            db.session.commit()
            flash(f"Quiz set distributed to {len(users)} users successfully!", "success")
            return redirect(url_for('main.admin_show_sets'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error distributing quiz set: {str(e)}", "error")
    
    # Get users not already assigned to this set
    available_users = models.User.query.filter(
        ~models.User.quiz_sets.contains(quiz_set),  # Using quiz_sets instead of question_sets
        models.User.is_admin == False
    ).all()
    
    return render_template(
        "admin/distribute_set.html",
        quiz_set=quiz_set,
        available_users=available_users
    )

@main.route("/dashboard")
@login_required
def dashboard():
    # Get user statistics
    results = models.Result.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        "total_quizzes": len(results),
        "average_score": calculate_average_score(current_user.id),
        "total_questions": calculate_total_questions(current_user.id)
    }
    
    # Get category performance data
    categories = models.Category.query.all()
    category_data = {
        'labels': [],
        'scores': [],
        'attempts': [],
        'colors': [
            'rgba(255, 99, 132, 0.7)',   # Red
            'rgba(54, 162, 235, 0.7)',   # Blue
            'rgba(255, 206, 86, 0.7)',   # Yellow
            'rgba(75, 192, 192, 0.7)',   # Green
            'rgba(153, 102, 255, 0.7)',  # Purple
            'rgba(255, 159, 64, 0.7)'    # Orange
        ]
    }
    
    for category in categories:
        # Get questions from this category that were answered by the user
        category_questions = models.Question.query.filter_by(category_id=category.id).all()
        if not category_questions:
            continue
            
        question_ids = [q.id for q in category_questions]
        category_results = []
        
        # Process each result
        for result in results:
            try:
                answers = json.loads(result.answers) if result.answers else {}
                if isinstance(answers, dict):  # Make sure answers is a dictionary
                    category_correct = 0
                    category_total = 0
                    
                    # Process each answer
                    for answer_data in answers.values():
                        if isinstance(answer_data, dict):  # Make sure each answer is a dictionary
                            q_id = answer_data.get('question_id')
                            if q_id in question_ids:
                                category_total += 1
                                if answer_data.get('is_correct'):
                                    category_correct += 1
                    
                    if category_total > 0:
                        category_results.append({
                            'correct': category_correct,
                            'total': category_total,
                            'score': (category_correct / category_total * 100)
                        })
            except (json.JSONDecodeError, AttributeError):
                continue
        
        # Calculate average score for category
        if category_results:
            avg_score = sum(r['score'] for r in category_results) / len(category_results)
            category_data['labels'].append(category.name)
            category_data['scores'].append(round(avg_score, 1))
            category_data['attempts'].append(len(category_results))
    
    # Get recent activities
    recent_activities = []
    for result in results[-5:]:  # Get last 5 results
        quiz_set = models.QuestionSet.query.get(result.question_set_id)
        if quiz_set:
            recent_activities.append({
                'date': utc_to_gmt7(result.created_at),
                'quiz_name': quiz_set.name,
                'score': (result.correct / result.total_number * 100) if result.total_number > 0 else 0,
                'time_taken': result.formatted_time
            })
    
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_activities=recent_activities,
        category_data=json.dumps(category_data)
    )

def calculate_average_score(user_id):
    results = models.Result.query.filter_by(user_id=user_id).all()
    if not results:
        return 0
    total_score = sum(r.correct / r.total_number * 100 for r in results)
    return total_score / len(results)

def calculate_total_questions(user_id):
    results = models.Result.query.filter_by(user_id=user_id).all()
    return sum(r.total_number for r in results)

def get_category_performance(user_id):
    # Get all categories
    categories = models.Category.query.all()
    labels = []
    scores = []
    
    for category in categories:
        # Get questions from this category that were answered by the user
        results = models.Result.query.filter_by(user_id=user_id).all()
        if not results:
            continue
            
        questions = models.Question.query.filter_by(
            category_id=category.id,
            question_set_id=results[-1].question_set_id  # Get questions from latest quiz
        ).all()
        
        if questions:
            # Get the latest result for this category
            total_questions = len(questions)
            latest_result = results[-1]  # Get most recent result
            
            if total_questions > 0:
                score = (latest_result.correct / total_questions) * 100
                labels.append(category.name)
                scores.append(score)
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Score %',
            'data': scores,
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }

@main.route("/admin/categories", methods=["GET", "POST"])
@login_required
def manage_categories():
    if not current_user.is_admin:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))
        
    if request.method == "POST":
        category_id = request.form.get("category_id")
        name = request.form.get("name")
        description = request.form.get("description")
        
        if category_id:  # Edit existing category
            category = models.Category.query.get(int(category_id))
            if category:
                if models.Category.query.filter(
                    models.Category.name == name,
                    models.Category.id != category.id
                ).first():
                    flash("Category name already exists", "warning")
                else:
                    category.name = name
                    category.description = description
                    db.session.commit()
                    flash("Category updated successfully", "success")
        else:  # Add new category
            if models.Category.query.filter_by(name=name).first():
                flash("Category already exists", "warning")
            else:
                category = models.Category(name=name, description=description)
                db.session.add(category)
                db.session.commit()
                flash("Category added successfully", "success")
            
    categories = models.Category.query.all()
    return render("admin/categories.html", categories=categories)

@main.route("/admin/categories/<int:category_id>", methods=["DELETE"])
@login_required
def delete_category(category_id):
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
        
    category = models.Category.query.get_or_404(category_id)
    
    # Check if category has questions
    if category.questions:
        return jsonify({"error": "Cannot delete category with existing questions"}), 400
        
    try:
        db.session.delete(category)
        db.session.commit()
        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/admin/users", methods=["GET", "POST"])
@login_required
def manage_users():
    if not current_user.is_admin:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))
        
    if request.method == "POST":
        user_id = request.form.get("user_id")
        name = request.form.get("name")
        password = request.form.get("password")
        is_admin = request.form.get("is_admin") == "on"
        
        if user_id:  # Edit existing user
            user = models.User.query.get(int(user_id))
            if user:
                if models.User.query.filter(
                    models.User.name == name,
                    models.User.id != user.id
                ).first():
                    flash("Username already exists", "warning")
                else:
                    user.name = name
                    user.is_admin = is_admin
                    if password:  # Update password only if provided
                        user.password = generate_password_hash(password)
                    db.session.commit()
                    flash("User updated successfully", "success")
        else:  # Add new user
            if not password:
                flash("Password is required for new users", "warning")
            elif models.User.query.filter_by(name=name).first():
                flash("Username already exists", "warning")
            else:
                user = models.User(
                    name=name,
                    is_admin=is_admin,
                    created_at=datetime.utcnow()
                )
                user.password = generate_password_hash(password)
                db.session.add(user)
                db.session.commit()
                flash("User added successfully", "success")
            
    users = models.User.query.all()
    return render("admin/users.html", users=users)

@main.route("/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
        
    if user_id == current_user.id:
        return jsonify({"error": "Cannot delete your own account"}), 400
        
    user = models.User.query.get_or_404(user_id)
    
    # Check if user has created questions or has results
    if user.questions or user.results:
        return jsonify({"error": "Cannot delete user with existing questions or results"}), 400
        
    try:
        # Remove user from all question sets
        user.question_sets = []
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/quiz/review/<int:result_id>")
@login_required
def quiz_review(result_id):
    # Get the result
    result = models.Result.query.get_or_404(result_id)
    
    # Check if the result belongs to the current user
    if result.user_id != current_user.id:
        flash("You can only review your own quiz results.", "error")
        return redirect(url_for("main.result"))
        
    # Get the quiz set
    quiz_set = models.QuestionSet.query.get(result.question_set_id)
    if not quiz_set:
        flash("Quiz set not found.", "error")
        return redirect(url_for("main.result"))
        
    # Get questions and answers
    questions = models.Question.query.filter_by(
        question_set_id=quiz_set.id,
        verified=True
    ).all()
    
    # Get user's answers for this result
    answers = {}  # Dictionary to store question_id: answer
    for i, question in enumerate(questions, 1):
        answer_key = f"q{i}o"
        answers_dict = result.answers_dict  # Use the new property
        if answer_key in answers_dict:
            answers[question.id] = answers_dict[answer_key]
        else:
            answers[question.id] = None
    
    return render_template(
        "quiz_review.html",
        result=result,
        quiz_set=quiz_set,
        questions=questions,
        answers=answers,
        score=(result.correct / result.total_number * 100) if result.total_number > 0 else 0,
        time_taken=f"{result.time_taken // 60}:{result.time_taken % 60:02d}"
    )

@main.route("/admin/question-bank")
@login_required
def question_bank():
    if not current_user.is_admin:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))
        
    # Get filter parameters
    category_id = request.args.get('category', type=int)
    difficulty = request.args.get('difficulty')
    question_type = request.args.get('type')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = models.Question.query
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if question_type:
        query = query.filter_by(question_type=question_type)
    if search:
        query = query.filter(models.Question.question.ilike(f'%{search}%'))
    
    # Paginate results
    pagination = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    return render(
        "admin/question_bank.html",
        questions=pagination.items,
        pagination=pagination,
        categories=models.Category.query.all()
    )

@main.route("/admin/questions/<int:question_id>")
@login_required
def view_question(question_id):
    if not current_user.is_admin:
        return "Unauthorized", 403
        
    question = models.Question.query.get_or_404(question_id)
    return render(
        "admin/question_detail.html",
        question=question,
        layout=False
    )

@main.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    if not current_user.is_admin:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))
        
    question = models.Question.query.get_or_404(question_id)
    
    if request.method == "POST":
        data = request.form.to_dict()
        files = request.files
        
        # Update basic info
        question.question = data['question']
        question.difficulty = data['difficulty']
        question.category_id = int(data['category'])
        question.question_type = data['question_type']
        
        # Handle image if provided
        if 'image' in files and files['image'].filename:
            image = files['image']
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                question.image_url = filename
        
        # Update options based on type
        if question.question_type == 'true_false':
            question.option1 = "True"
            question.option2 = "False"
            question.correct_option = data['correct_tf']
        else:
            question.option1 = data['option1']
            question.option2 = data['option2']
            question.option3 = data.get('option3')
            question.option4 = data.get('option4')
            question.correct_option = data['correct_option']
        
        db.session.commit()
        flash("Question updated successfully", "success")
        return redirect(url_for("main.question_bank"))
    
    return render(
        "admin/edit_question.html",
        question=question,
        categories=models.Category.query.all()
    )

@main.route("/admin/questions/<int:question_id>", methods=["DELETE"])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
        
    question = models.Question.query.get_or_404(question_id)
    
    try:
        # Delete associated image if exists
        if question.image_url:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_url)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(question)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/admin/questions/bulk-verify", methods=["POST"])
@login_required
def bulk_verify_questions():
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
        
    data = request.get_json()
    question_ids = data.get('question_ids', [])
    
    try:
        models.Question.query.filter(
            models.Question.id.in_(question_ids)
        ).update(
            {models.Question.verified: True},
            synchronize_session=False
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/admin/questions/export", methods=["GET"])
@login_required
@admin_required
def export_questions():
    try:
        # Create a StringIO object to write CSV data
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Question', 'Type', 'Option1', 'Option2', 'Option3', 'Option4',
            'Correct Answer', 'Category', 'Difficulty', 'Explanation'
        ])
        
        # Write questions
        questions = models.Question.query.all()
        for q in questions:
            writer.writerow([
                q.question,
                q.question_type,
                q.option1,
                q.option2,
                q.option3,
                q.option4,
                q.correct_option,
                q.category.name if q.category else '',
                q.difficulty,
                q.explanation
            ])
        
        # Prepare the response
        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='questions.csv'
        )
        
    except Exception as e:
        print(f"Error exporting questions: {str(e)}")
        flash("Error exporting questions", "error")
        return redirect(url_for("main.admin"))

@main.route("/admin/performance-report")
@login_required
@admin_required
def performance_report():
    # Calculate overall statistics
    stats = {
        'total_quizzes': models.Result.query.count(),
        'avg_score': db.session.query(func.avg(models.Result.correct * 100.0 / models.Result.total_number)).scalar() or 0,
        'active_users': models.User.query.filter(models.User.results.any()).count(),
        'total_questions': models.Question.query.filter_by(verified=True).count()
    }
    
    # Calculate score distribution
    score_ranges = ['0-20%', '21-40%', '41-60%', '61-80%', '81-100%']
    score_distribution = [0] * 5
    
    results = models.Result.query.all()
    for result in results:
        score = (result.correct / result.total_number) * 100
        index = min(int(score // 20), 4)
        score_distribution[index] += 1
    
    # Calculate category performance
    categories = models.Category.query.all()
    category_names = [cat.name for cat in categories]
    category_scores = []
    
    for category in categories:
        # Get all questions in this category
        questions = models.Question.query.filter_by(category_id=category.id).all()
        question_ids = [q.id for q in questions]
        
        # Calculate average score for questions in this category
        if question_ids:
            avg_score = db.session.query(
                func.avg(models.Result.correct * 100.0 / models.Result.total_number)
            ).filter(
                models.Result.answers.like(f'%"question_id": {question_ids[0]}%')
            ).scalar() or 0
            category_scores.append(float(avg_score))
        else:
            category_scores.append(0)
    
    # Get top performers with user details
    top_performers = db.session.query(
        models.User,
        func.count(models.Result.id).label('quiz_count'),
        func.avg(models.Result.correct * 100.0 / models.Result.total_number).label('avg_score'),
        func.max(models.Result.correct * 100.0 / models.Result.total_number).label('best_score')
    ).join(models.Result)\
     .group_by(models.User)\
     .order_by(text('avg_score DESC'))\
     .limit(10)\
     .all()

    return render_template(
        'admin/performance_report.html',
        stats=stats,
        score_ranges=score_ranges,
        score_distribution=score_distribution,
        category_names=category_names,
        category_scores=category_scores,
        top_performers=top_performers  # This now contains user objects
    )

@main.route("/admin/show_sets")
@login_required
def admin_show_sets():
    if not current_user.is_admin:
        flash("Admin access required", "warning")
        return redirect(url_for("main.index"))
        
    return render_template(
        "admin/show_sets.html",
        sets=models.QuestionSet.query.all(),
        categories=models.Category.query.all()
    )



@main.route("/admin/sets/<int:set_id>/view")
@login_required
@admin_required
def view_set(set_id):
    quiz_set = models.QuestionSet.query.get_or_404(set_id)
    return render_template(
        "admin/set_details.html", 
        quiz_set=quiz_set,
        layout=False
    )

@main.route("/admin/sets/<int:set_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_set(set_id):
    quiz_set = models.QuestionSet.query.get_or_404(set_id)
    
    if request.method == "POST":
        try:
            # Update basic info
            quiz_set.name = request.form.get("set_name", "Untitled Set")
            quiz_set.time_limit = int(request.form.get("time_limit", 5)) * 60
            
            # Handle questions
            selected_questions = request.form.getlist('questions[]')
            # Clear existing questions
            for question in quiz_set.questions:
                question.question_set_id = None
            
            # Add selected questions
            for q_id in selected_questions:
                question = models.Question.query.get(int(q_id))
                if question:
                    question.question_set_id = quiz_set.id
            
            db.session.commit()
            flash(f"Quiz set '{quiz_set.name}' updated successfully", "success")
            return redirect(url_for("main.admin_show_sets"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating quiz set: {str(e)}", "error")
    
    # Get all available questions plus current set's questions
    available_questions = models.Question.query.filter(
        (models.Question.question_set_id == None) | 
        (models.Question.question_set_id == set_id)
    ).filter_by(verified=True).all()
    
    return render_template(
        "admin/edit_set.html",
        quiz_set=quiz_set,
        available_questions=available_questions,
        categories=models.Category.query.all()
    )

@main.route("/admin/sets/<int:set_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_set(set_id):
    quiz_set = models.QuestionSet.query.get_or_404(set_id)
    try:
        # Remove set from all users
        quiz_set.users = []
        # Clear question associations
        for question in quiz_set.questions:
            question.question_set_id = None
        # Delete the set
        db.session.delete(quiz_set)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/profile")
@login_required
def profile():
    return render_template("profile/view_profile.html", user=current_user)

@main.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        try:
            # Handle avatar upload
            if 'avatar' in request.files:
                file = request.files['avatar']
                if file and file.filename and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
                    # Create avatars directory if it doesn't exist
                    avatar_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
                    if not os.path.exists(avatar_dir):
                        os.makedirs(avatar_dir)
                        
                    # Generate unique filename
                    filename = secure_filename(f"avatar_{current_user.id}_{int(time.time())}{os.path.splitext(file.filename)[1]}")
                    
                    # Delete old avatar if it exists and isn't the default
                    if current_user.avatar_url:
                        old_avatar_path = os.path.join(avatar_dir, current_user.avatar_url)
                        if os.path.exists(old_avatar_path) and current_user.avatar_url != 'default_avatar.png':
                            try:
                                os.remove(old_avatar_path)
                            except OSError:
                                pass  # Ignore deletion errors
                            
                    # Save new avatar
                    file_path = os.path.join(avatar_dir, filename)
                    file.save(file_path)
                    current_user.avatar_url = filename

            # Update other profile fields
            new_email = request.form.get('email')
            if new_email:
                existing_user = models.User.query.filter(
                    models.User.email == new_email,
                    models.User.id != current_user.id
                ).first()
                if existing_user:
                    flash("This email is already in use", "danger")
                    return redirect(url_for('main.edit_profile'))

            current_user.email = new_email
            current_user.full_name = request.form.get('full_name')
            current_user.bio = request.form.get('bio')
            current_user.social_links = {
                'github': request.form.get('github'),
                'linkedin': request.form.get('linkedin'),
                'twitter': request.form.get('twitter')
            }
            
            db.session.commit()
            
            # Send notification about email verification if needed
            if new_email and not current_user.email_verified:
                send_notification(
                    user=current_user,
                    title="Verify Your Email",
                    message="Please verify your email address to secure your account",
                    type="warning",
                    priority="high",
                    link=url_for('main.verify_email'),
                    metadata={
                        "email": new_email,
                        "importance": "Required for account security"
                    }
                )
            
            flash("Profile updated successfully!", "success")
            return redirect(url_for('main.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {str(e)}", "error")
            
    return render_template("profile/edit_profile.html", user=current_user)

@main.route("/notifications")
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'high':
        query = query.filter_by(priority='high')
    elif filter_type in ['info', 'success', 'warning', 'quiz', 'admin']:
        query = query.filter_by(type=filter_type)
    
    # Don't show expired notifications by default
    query = query.filter(or_(
        Notification.expiry_date.is_(None),
        Notification.expiry_date > datetime.utcnow()
    ))
    
    notifications = query.order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render("notifications.html",
        notifications=notifications.items,  # Add .items here
        now=datetime.utcnow()
    )

@main.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    if not notification.is_read:
        notification.is_read = True
        current_user.unread_notifications -= 1
        db.session.commit()
    
    return jsonify({
        "success": True,
        "unread_count": current_user.unread_notifications
    })

@main.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    unread = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).all()
    
    for notification in unread:
        notification.is_read = True
    
    current_user.unread_notifications = 0
    db.session.commit()
    
    return jsonify({"success": True})

@main.route("/notifications/<int:notification_id>/delete", methods=["DELETE"])
@login_required
def delete_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    if not notification.is_read:
        current_user.unread_notifications -= 1
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "unread_count": current_user.unread_notifications
    })

@main.route("/notifications/clear-all", methods=["DELETE"])
@login_required
def clear_all_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    current_user.unread_notifications = 0
    db.session.commit()
    
    return jsonify({"success": True})

# Chat routes
@main.route("/chat")
@login_required
def chat_rooms():
    # Get rooms by type
    general_rooms = models.ChatRoom.query.filter_by(type='general').all()
    quiz_rooms = models.ChatRoom.query.filter_by(type='quiz_discussion').all()
    question_rooms = models.ChatRoom.query.filter_by(type='question_discussion').all()
    private_rooms = models.ChatRoom.query.filter_by(type='private', is_private=True).all()
    
    # Get quiz sets and questions for room creation
    quiz_sets = models.QuestionSet.query.all()
    questions = models.Question.query.filter_by(verified=True).all()
    
    return render_template(
        "chat/rooms.html",
        general_rooms=general_rooms,
        quiz_rooms=quiz_rooms,
        question_rooms=question_rooms,
        private_rooms=private_rooms,
        quiz_sets=quiz_sets,
        questions=questions
    )

@main.route("/chat/room/<int:room_id>")
@login_required
def chat_room(room_id):
    room = models.ChatRoom.query.get_or_404(room_id)
    
    # Add current user to room participants if not already there
    if current_user not in room.participants:
        room.participants.append(current_user)
        db.session.commit()
    
    # Convert messages timestamps to GMT+7
    messages = models.ChatMessage.query.filter_by(room_id=room_id).order_by(models.ChatMessage.created_at).all()
    
    return render_template('chat/room.html',
                         room=room,
                         room_id=room_id,
                         messages=messages,
                         participants=room.participants,
                         utc_to_gmt7=utc_to_gmt7)  # Pass the conversion function to template

@main.route("/chat/create", methods=["POST"])
@login_required
def create_chat_room():
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Invalid request format"}), 400
            
        data = request.json
        print("Creating room with data:", data)  # Debug log
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({"success": False, "error": "Room name is required"}), 400
            
        # Check private room limits (skip for admins)
        if data['type'] == 'private' and not current_user.is_admin:
            passcode = str(data.get('passcode', '')).strip()
            if not passcode.isdigit() or len(passcode) < 4 or len(passcode) > 6:
                return jsonify({"success": False, "error": "Invalid passcode format"}), 400
                
            private_room_count = models.ChatRoom.get_user_private_room_count(current_user.id)
            if private_room_count >= 3:
                return jsonify({
                    "success": False, 
                    "error": "You have reached the maximum limit of 3 private rooms"
                }), 400

        room = models.ChatRoom(
            name=data['name'],
            type=data['type'],
            is_private=data.get('is_private', False),
            passcode=str(data.get('passcode', '')).strip(),  # Ensure passcode is stored as string
            creator_id=current_user.id
        )
        print(f"Created room with passcode: {room.passcode}")  # Debug log
        
        room.participants.append(current_user)
        db.session.add(room)
        db.session.commit()
        
        return jsonify({'success': True, 'room_id': room.id})
    except Exception as e:
        db.session.rollback()
        print(f"Error creating chat room: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        print(f"Client connected: {current_user.name}")

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        print(f"Client disconnected: {current_user.name}")

@socketio.on('join')
def on_join(data):
    try:
        room = str(data.get('room', ''))  # Use get() with default value
        if not room:
            print("No room ID provided")
            return
            
        join_room(room)
        print(f"User {current_user.name} joined room {room}")
        
        # Update participant status
        participants = get_room_participants(room)
        emit('participant_update', {'participants': participants}, room=room, broadcast=True)
        
    except Exception as e:
        print(f"Error in join: {str(e)}")

def utc_to_gmt7(utc_dt):
    if utc_dt is None:
        return None
    gmt7 = pytz.timezone('Asia/Bangkok')
    return utc_dt.replace(tzinfo=pytz.UTC).astimezone(gmt7)

@socketio.on('message')
def handle_message(data):
    try:
        room = str(data.get('room', ''))
        message_text = data.get('message', '').strip()
        file_url = data.get('file_url')
        
        if not room or not message_text:
            return
            
        # Save message to database in UTC
        chat_message = models.ChatMessage(
            content=message_text,
            user_id=current_user.id,
            room_id=int(room),
            file_url=file_url
        )
        db.session.add(chat_message)
        db.session.commit()
        
        # Convert to GMT+7 for display
        gmt7_time = utc_to_gmt7(chat_message.created_at)
        
        # Broadcast message with GMT+7 timestamp
        emit('message', {
            'id': chat_message.id,
            'message': message_text,
            'author': current_user.name,
            'author_id': current_user.id,  # Make sure this is included
            'avatar_url': current_user.get_avatar_url,
            'created_at': gmt7_time.strftime('%Y-%m-%d %H:%M:%S'),
            'room_id': room,
            'file_url': file_url
        }, room=room, broadcast=True)
        
    except Exception as e:
        print(f"Error handling message: {str(e)}")
        db.session.rollback()

def get_room_participants(room_id):
    try:
        room = models.ChatRoom.query.get(int(room_id))
        if not room:
            return []
        return [{
            'id': p.id,
            'name': p.name,
            'avatar_url': p.get_avatar_url or '',  # Add default value
            'is_online': p.is_online
        } for p in room.participants]
    except Exception as e:
        print(f"Error getting participants: {str(e)}")
        return []

@socketio.on('reaction')
def handle_reaction(data):
    try:
        # Check if reaction already exists
        existing = models.MessageReaction.query.filter_by(
            message_id=data['message_id'],
            user_id=current_user.id,
            reaction=data['reaction']
        ).first()
        
        if existing:
            # Remove reaction if it exists
            db.session.delete(existing)
            emit('reaction_removed', {
                'message_id': data['message_id'],
                'reaction': data['reaction'],
                'user': current_user.name
            }, room=data['room'])
        else:
            # Add new reaction
            reaction = models.MessageReaction(
                message_id=data['message_id'],
                user_id=current_user.id,
                reaction=data['reaction']
            )
            db.session.add(reaction)
            emit('reaction_added', {
                'message_id': data['message_id'],
                'reaction': data['reaction'],
                'user': current_user.name
            }, room=data['room'])
            
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error handling reaction: {str(e)}")

@main.route("/analytics")
@login_required
def analytics_dashboard():
    # Get user's quiz history
    user_results = models.Result.query.filter_by(user_id=current_user.id).order_by(models.Result.created_at.desc()).all()
    
    # Calculate performance metrics
    total_quizzes = len(user_results)
    if total_quizzes > 0:
        avg_score = sum(r.correct * 100.0 / r.total_number for r in user_results) / total_quizzes
        best_score = max(r.correct * 100.0 / r.total_number for r in user_results)
        total_time = sum(r.time_taken for r in user_results)
        avg_time = total_time / total_quizzes
    else:
        avg_score = best_score = avg_time = 0
    
    # Format recent activity with proper time formatting
    recent_activity = []
    for result in user_results[:5]:  # Last 5 quizzes
        quiz_set = models.QuestionSet.query.get(result.question_set_id)
        activity = {
            'type': 'quiz_completion',
            'date': utc_to_gmt7(result.created_at),  # Convert to GMT+7
            'details': {
                'quiz_name': quiz_set.name if quiz_set else 'Practice Quiz',
                'score': result.correct * 100.0 / result.total_number,
                'time_taken': result.formatted_time
            }
        }
        recent_activity.append(activity)
    
    return render_template(
        'analytics/dashboard.html',
        stats={
            'total_quizzes': total_quizzes,
            'avg_score': avg_score,
            'best_score': best_score,
            'avg_time': f"{int(avg_time // 60):02d}:{int(avg_time % 60):02d}" if total_quizzes > 0 else "00:00"
        },
        recent_activity=recent_activity
    )

@main.route("/admin/questions/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_rich_text_question():
    if request.method == "POST":
        try:
            # Handle file uploads first
            media_files = request.files.getlist('mediaFiles')
            media_urls = []
            
            for file in media_files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{int(time.time())}_{file.filename}")
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', filename))
                    media_urls.append(filename)
            
            # Get tags and ensure it's a valid JSON string
            tags_str = request.form.get('tags', '[]')
            if not tags_str:
                tags_str = '[]'
            
            # Create question
            question = models.Question(
                question=request.form.get('content'),
                question_type='rich_text',
                option1=request.form.get('option1'),
                option2=request.form.get('option2'),
                option3=request.form.get('option3'),
                option4=request.form.get('option4'),
                correct_option=request.form.get('correct_option'),
                category_id=request.form.get('category_id'),
                difficulty=request.form.get('difficulty', 'medium'),
                explanation=request.form.get('explanation'),
                creator_id=current_user.id,
                verified=True,
                media_urls=media_urls,
                tags=json.loads(tags_str)  # Closed parenthesis here
            )
            
            db.session.add(question)
            db.session.commit()
            
            flash("Question created successfully!", "success")
            return jsonify({
                "success": True,
                "redirect": url_for('main.question_bank')
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating question: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            })
    
    return render_template(
        "admin/rich_text_editor.html",
        categories=models.Category.query.all()
    )

@main.route("/quiz/set/<int:set_id>/discuss")
@login_required
def quiz_discussion(set_id):
    quiz_set = models.QuestionSet.query.get_or_404(set_id)
    
    # Find or create discussion room for this quiz set
    room = models.ChatRoom.query.filter_by(
        type='quiz_discussion',
        quiz_set_id=set_id
    ).first()
    
    if not room:
        room = models.ChatRoom(
            name=f"Discussion: {quiz_set.name}",
            type='quiz_discussion',
            quiz_set_id=set_id
        )
        db.session.add(room)
        db.session.commit()
    
    return redirect(url_for('main.chat_room', room_id=room.id))

@main.route("/question/<int:question_id>/discuss")
@login_required
def question_discussion(question_id):
    question = models.Question.query.get_or_404(question_id)
    
    # Find or create discussion room for this question
    room = models.ChatRoom.query.filter_by(
        type='question_discussion',
        question_id=question_id
    ).first()
    
    if not room:
        room = models.ChatRoom(
            name=f"Question Discussion: {question.question[:50]}...",
            type='question_discussion',
            question_id=question_id
        )
        db.session.add(room)
        db.session.commit()
    
    return redirect(url_for('main.chat_room', room_id=room.id))

@socketio.on('typing')
def on_typing(data):
    emit('typing', {
        'user_id': current_user.id,
        'user_name': current_user.name
    }, room=data['room'])

@socketio.on('stop_typing')
def on_stop_typing(data):
    emit('stop_typing', {
        'user_id': current_user.id,
        'user_name': current_user.name
    }, room=data['room'])

@main.route("/chat/upload", methods=["POST"])
@login_required
def upload_chat_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
        
    file = request.files['file']
    if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}):
        try:
            filename = secure_filename(f"{int(time.time())}_{file.filename}")
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat')
            
            # Create chat uploads directory if it doesn't exist
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
                
            file.save(os.path.join(upload_path, filename))
            
            return jsonify({
                "success": True,
                "filename": filename,
                "url": url_for('static', filename=f'uploads/chat/{filename}')
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Invalid file type"}), 400

@socketio.on('reaction')
def handle_reaction(data):
    try:
        # Check if reaction already exists
        existing = models.MessageReaction.query.filter_by(
            message_id=data['message_id'],
            user_id=current_user.id,
            reaction=data['reaction']
        ).first()
        
        if existing:
            # Remove reaction if it exists
            db.session.delete(existing)
            emit('reaction_removed', {
                'message_id': data['message_id'],
                'reaction': data['reaction'],
                'user': current_user.name
            }, room=data['room'])
        else:
            # Add new reaction
            reaction = models.MessageReaction(
                message_id=data['message_id'],
                user_id=current_user.id,
                reaction=data['reaction']
            )
            db.session.add(reaction)
            emit('reaction_added', {
                'message_id': data['message_id'],
                'reaction': data['reaction'],
                'user': current_user.name
            }, room=data['room'])
            
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error handling reaction: {str(e)}")

@socketio.on('message_read')
def handle_message_read(data):
    try:
        # Mark message as read
        read_receipt = models.MessageRead(
            message_id=data['message_id'],
            user_id=current_user.id
        )
        db.session.add(read_receipt)
        db.session.commit()
        
        # Notify others in room
        emit('message_read_status', {
            'message_id': data['message_id'],
            'user': current_user.name,
            'read_at': read_receipt.read_at.strftime('%H:%M')
        }, room=data['room'])
        
    except Exception as e:
        db.session.rollback()
        print(f"Error handling read receipt: {str(e)}")

@main.route("/chat/message/<int:message_id>/report", methods=["POST"])
@login_required
def report_message(message_id):
    message = models.Message.query.get_or_404(message_id)
    reason = request.json.get('reason')
    
    report = models.MessageReport(
        message_id=message_id,
        reporter_id=current_user.id,
        reason=reason
    )
    db.session.add(report)
    db.session.commit()
    
    # Notify admins
    admins = models.User.query.filter_by(is_admin=True).all()
    for admin in admins:
        notification = models.Notification(
            user_id=admin.id,
            title="New Message Report",
            message=f"Message reported in {message.room.name}",
            type="warning",
            link=url_for('main.chat_room', room_id=message.room_id)
        )
        db.session.add(notification)
    db.session.commit()
    
    return jsonify({"success": True})

@main.route("/admin/chat/reports")
@login_required
@admin_required
def chat_reports():
    reports = models.MessageReport.query.filter_by(status='pending')\
        .order_by(models.MessageReport.created_at.desc()).all()
    return render_template('admin/chat_reports.html', reports=reports)

@main.route("/chat/message/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(message_id):
    try:
        message = models.ChatMessage.query.get_or_404(message_id)
        
        # Check if user can delete this message
        if not message.can_delete(current_user):
            return jsonify({"success": False, "error": "Unauthorized"}), 403
        
        room_id = message.room_id  # Store room_id before deleting
        
        # Delete associated file if exists
        if message.file_url:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat', message.file_url)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete message
        db.session.delete(message)
        db.session.commit()
        
        # Notify room about deletion
        socketio.emit('message_deleted', {
            'message_id': message_id,
            'deleted_by': current_user.name
        }, room=str(room_id))
        
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting message: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@main.route("/admin/user/warn", methods=["POST"])
@login_required
@admin_required
def warn_user():
    data = request.json
    user = models.User.query.get_or_404(data['user_id'])
    room = models.ChatRoom.query.get_or_404(data['room_id'])
    
    try:
        # Create warning notification
        notification = models.Notification(
            user_id=user.id,
            title="Warning from Admin",
            message=data['reason'],
            type="warning",
            link=url_for('main.chat_room', room_id=room.id)
        )
        db.session.add(notification)
        user.unread_notifications += 1
        
        # Send system message to chat
        system_message = models.Message(
            content=f"⚠️ User {user.name} received a warning: {data['reason']}",
            user_id=current_user.id,
            room_id=room.id
        )
        db.session.add(system_message)
        db.session.commit()
        
        # Notify room about the system message
        socketio.emit('message', {
            'id': system_message.id,
            'user': 'System',
            'content': system_message.content,
            'timestamp': system_message.created_at.strftime('%H:%M'),
            'is_system': True
        }, room=room.id)
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/admin/chat")
@login_required
@admin_required
def admin_chat():
    # Get all chat rooms
    rooms = models.ChatRoom.query.all()
    
    return render_template(
        "admin/chat_management.html",
        rooms=rooms
    )

@main.route("/chat/room/<int:room_id>/delete", methods=["POST"])
@login_required
def delete_chat_room(room_id):
    try:
        room = models.ChatRoom.query.get_or_404(room_id)
        
        # Check if user has permission to delete the room
        if not room.can_delete(current_user):
            return jsonify({"error": "You don't have permission to delete this room"}), 403
            
        # Delete all messages in the room
        models.ChatMessage.query.filter_by(room_id=room_id).delete()
        
        # Remove all participants
        room.participants = []
        
        # Delete the room
        db.session.delete(room)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting room: {str(e)}")
        return jsonify({"error": str(e)}), 500

@main.route("/chat/join", methods=["POST"])
@login_required
def join_chat_room():
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.json
        print("Received join request:", data)  # Debug log

        if not data or 'room_id' not in data:
            return jsonify({'success': False, 'error': 'Room ID is required'}), 400

        room = models.ChatRoom.query.get_or_404(int(data['room_id']))  # Ensure room_id is int
        
        # Check if user is already a participant
        if current_user in room.participants:
            return jsonify({'success': True, 'room_id': room.id})
        
        # Check if room is private and requires passcode
        if room.is_private and not current_user.is_admin:  # Only check passcode if not admin
            provided_passcode = data.get('passcode', '').strip()
            if not provided_passcode:
                return jsonify({'success': False, 'error': 'Passcode required'}), 403
            
            # Compare passcodes directly
            if provided_passcode != room.passcode:
                return jsonify({'success': False, 'error': 'Invalid passcode'}), 403
        
        # Add user to room participants
        room.participants.append(current_user)
        db.session.commit()
        
        return jsonify({'success': True, 'room_id': room.id})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error joining room: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route("/profile/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        # Verify current password
        if not check_password_hash(current_user.password, current_password):
            flash("Current password is incorrect", "danger")
            return redirect(url_for("main.change_password"))
        
        # Verify new password matches confirmation
        if new_password != confirm_password:
            flash("New passwords do not match", "danger")
            return redirect(url_for("main.change_password"))
        
        # Update password
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        
        flash("Password updated successfully", "success")
        return redirect(url_for("main.profile"))
    
    return render("profile/change_password.html")

@main.route("/test/notifications")
@login_required
def test_notifications():
    """Generate test notifications for the current user"""
    from .utils import notify_test_all_types
    
    notify_test_all_types(current_user)
    flash("Test notifications created successfully", "success")
    return redirect(url_for('main.notifications'))

@main.route("/profile/verify-email")
@login_required
def verify_email():
    # Generate verification token
    token = generate_verification_token(current_user.email)
    
    # Send verification notification
    send_notification(
        user=current_user,
        title="Email Verification",
        message="Click the button below to verify your email address",
        type="info",
        priority="high",
        link=url_for('main.verify_email_token', token=token, _external=True),
        metadata={
            "email": current_user.email,
            "expires_in": "24 hours"
        }
    )
    
    flash("Verification email has been sent. Please check your notifications.", "info")
    return redirect(url_for('main.edit_profile'))

@main.route("/profile/verify-email/<token>")
@login_required
def verify_email_token(token):
    try:
        email = verify_token(token)
        if email == current_user.email:
            current_user.email_verified = True
            db.session.commit()
            flash("Your email has been verified!", "success")
        else:
            flash("Invalid verification link", "danger")
    except Exception as e:
        flash("The verification link is invalid or has expired", "danger")
    
    return redirect(url_for('main.profile'))

@main.route("/admin/questions/review", methods=["GET", "POST"])
@login_required
@admin_required
def review_questions():
    if request.method == "POST":
        try:
            data = request.json
            question = models.Question.query.get_or_404(data['question_id'])
            action = data['action']  # 'approve' or 'reject'
            
            if action == 'approve':
                question.verified = True
                # Notify user about approval
                send_notification(
                    user=question.creator,
                    title="Question Approved! ✅",
                    message=f"Your question has been approved and added to the question bank",
                    type="success",
                    priority="normal",
                    link=url_for('main.add_questions'),
                    metadata={
                        "question": question.question[:100] + "...",
                        "category": question.category.name,
                        "approved_by": current_user.name,
                        "approved_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }
                )
                db.session.commit()
            else:  # reject
                reason = data.get('reason', 'No reason provided')
                # Store creator and question info before deletion
                creator = question.creator
                question_text = question.question
                category_name = question.category.name

                # Send notification BEFORE deleting the question
                send_notification(
                    user=creator,
                    title="Question Needs Revision ⚠️",
                    message=f"Your question was not approved. Reason: {reason}",
                    type="warning",
                    priority="high",
                    link=url_for('main.add_questions'),
                    metadata={
                        "question": question_text[:100] + "...",
                        "reason": reason,
                        "category": category_name,
                        "reviewed_by": current_user.name,
                        "reviewed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }
                )

                # Now delete the question
                db.session.delete(question)
                db.session.commit()
            
            return jsonify({"success": True})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
    
    # GET method - show unverified questions
    questions = models.Question.query.filter_by(verified=False).all()
    return render_template("admin/review_questions.html", questions=questions)

@main.route("/admin/review-question/<int:question_id>")
@login_required
@admin_required
def admin_review_question(question_id):
    question = models.Question.query.get_or_404(question_id)
    return render_template(
        "admin/review_question.html",
        question=question,
        categories=models.Category.query.all()
    )

@main.route("/admin/questions/bulk-review", methods=["POST"])
@login_required
@admin_required
def bulk_review_questions():
    try:
        data = request.json
        action = data['action']
        question_ids = data['question_ids']
        reason = data.get('reason')
        
        questions = models.Question.query.filter(models.Question.id.in_(question_ids)).all()
        
        for question in questions:
            if action == 'approve':
                question.verified = True
                # Notify user about approval
                send_notification(
                    user=question.creator,
                    title="Question Approved! ✅",
                    message=f"Your question has been approved and added to the question bank",
                    type="success",
                    priority="normal",
                    link=url_for('main.add_questions'),
                    metadata={
                        "question": question.question[:100] + "...",
                        "category": question.category.name,
                        "approved_by": current_user.name,
                        "approved_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }
                )
            else:  # reject
                creator = question.creator
                question_text = question.question
                category_name = question.category.name
                
                # Send notification before deletion
                send_notification(
                    user=creator,
                    title="Question Needs Revision ⚠️",
                    message=f"Your question was not approved. Reason: {reason}",
                    type="warning",
                    priority="high",
                    link=url_for('main.add_questions'),
                    metadata={
                        "question": question_text[:100] + "...",
                        "reason": reason,
                        "category": category_name,
                        "reviewed_by": current_user.name,
                        "reviewed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }
                )
                db.session.delete(question)
        
        db.session.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@main.route("/quiz/submit", methods=["POST"])
@login_required
def submit_quiz():
    try:
        data = request.form.to_dict()
        set_id = data.get('set_id')
        quiz_set = models.QuestionSet.query.get_or_404(set_id)
        
        # Create a mapping of question IDs to their correct answers
        question_map = {}
        for i in range(1, 6):  # Assuming 5 questions
            q_id = data.get(f'question_{i}_id')
            if q_id:
                question_map[q_id] = {
                    'index': i,
                    'correct_answer': data.get(f'correct_{i}')
                }
        
        # Get questions and ensure they're in the right order
        questions = models.Question.query.filter_by(
            question_set_id=int(set_id),
            verified=True
        ).order_by(models.Question.id).all()
        
        total_questions = len(questions)
        time_taken = int(data.get('time_taken', 0))

        correct = 0
        incorrect = 0
        not_attempt = 0
        answers = {}

        # Process each question using the mapping
        for question in questions:
            q_info = question_map.get(str(question.id))
            if not q_info:
                continue
                
            i = q_info['index']
            answer_key = f"q{i}o"
            user_answer = data.get(answer_key)

            # Store answer details
            answer_data = {
                'question_id': question.id,
                'question_text': question.question,
                'correct_answer': question.correct_option,
                'user_answer': user_answer,
                'is_correct': False
            }

            if not user_answer:
                not_attempt += 1
            else:
                # Clean and compare answers
                user_answer = user_answer.strip().upper()
                correct_answer = question.correct_option.strip().upper()
                
                answer_data['user_answer'] = user_answer
                answer_data['is_correct'] = user_answer == correct_answer
                
                if user_answer == correct_answer:
                    correct += 1
                else:
                    incorrect += 1

            answers[str(question.id)] = answer_data

        # Calculate score before notifications
        score = (correct / total_questions * 100) if total_questions > 0 else 0

        # Get user's previous best position (if any)
        old_position = get_user_leaderboard_position(current_user.id, int(set_id))

        result = models.Result(
            total_number=total_questions,
            correct=correct,
            incorrect=incorrect,
            not_attempt=not_attempt,
            user_id=current_user.id,
            time_taken=time_taken,
            question_set_id=int(set_id),
            created_at=datetime.utcnow(),
            answers=json.dumps(answers)
        )

        db.session.add(result)
        db.session.commit()

        # Get new leaderboard position
        new_position = get_user_leaderboard_position(current_user.id, int(set_id))
        
        # Notify about quiz completion
        send_notification(
            user=current_user,
            title="Quiz Completed! 🎯",
            message=f"You scored {score:.1f}% on {quiz_set.name} in {result.formatted_time}",
            type="success",
            priority="normal",
            link=url_for('main.view_result', result_id=result.id),
            metadata={
                'quiz_set': quiz_set.name,
                'score': score,
                'time_taken': result.formatted_time,
                'correct': correct,
                'total': total_questions
            }
        )

        # Notify if user reached a new high position
        if new_position:  # If user is in top positions
            if not old_position or new_position < old_position:  # If new position is better
                position_text = {
                    1: "🥇 First",
                    2: "🥈 Second", 
                    3: "🥉 Third",
                    4: "4th",
                    5: "5th"
                }.get(new_position, f"{new_position}th")

                achievement_text = "Congratulations! "
                if not old_position:
                    achievement_text += f"You've made it to the leaderboard in {position_text} place!"
                else:
                    achievement_text += f"You've moved up to {position_text} place!"

                send_notification(
                    user=current_user,
                    title="New Leaderboard Achievement! 🏆",
                    message=f"{achievement_text} on {quiz_set.name}",
                    type="achievement",
                    priority="high",
                    link=url_for('main.leaderboard', set_id=set_id),
                    metadata={
                        'quiz_set': quiz_set.name,
                        'old_position': old_position,
                        'new_position': new_position,
                        'score': score,
                        'time_taken': result.formatted_time,
                        'achievement_type': 'leaderboard_position'
                    }
                )

        return redirect(url_for("main.view_result", result_id=result.id))

    except Exception as e:
        db.session.rollback()
        print(f"Error in submit_quiz: {str(e)}")
        flash(f"Error submitting quiz: {str(e)}", "error")
        return redirect(url_for("main.quiz"))

def get_user_leaderboard_position(user_id, set_id):
    """Get user's position in leaderboard for a quiz set"""
    try:
        # Get all results for the quiz set
        results = models.Result.query.filter_by(question_set_id=set_id).all()
        
        # Create a dictionary to store best attempts per user
        best_attempts = {}
        for result in results:
            score = (result.correct / result.total_number * 100)
            current_best = best_attempts.get(result.user_id)
            
            if not current_best or score > current_best['score'] or \
               (score == current_best['score'] and result.time_taken < current_best['time_taken']):
                best_attempts[result.user_id] = {
                    'score': score,
                    'time_taken': result.time_taken
                }
        
        # Sort users by score and time
        sorted_users = sorted(
            best_attempts.items(),
            key=lambda x: (-x[1]['score'], x[1]['time_taken'])
        )
        
        # Find user's position
        for position, (uid, _) in enumerate(sorted_users, 1):
            if uid == user_id:
                return position if position <= 5 else None  # Only return position if in top 5
                
        return None  # User not in leaderboard
        
    except Exception as e:
        print(f"Error getting leaderboard position: {str(e)}")
        return None

@main.route("/result/<int:result_id>")
@login_required
def view_result(result_id):
    result = models.Result.query.get_or_404(result_id)
    
    if result.user_id != current_user.id:
        flash("You can only review your own quiz results.", "error")
        return redirect(url_for("main.result"))
        
    quiz_set = models.QuestionSet.query.get(result.question_set_id)
    if not quiz_set:
        flash("Quiz set not found.", "error")
        return redirect(url_for("main.result"))
    
    questions = models.Question.query.filter_by(
        question_set_id=quiz_set.id,
        verified=True
    ).order_by(models.Question.id).all()
    
    try:
        answers = json.loads(result.answers) if result.answers else {}
    except Exception as e:
        answers = {}
    
    score = (result.correct / result.total_number * 100) if result.total_number > 0 else 0
    
    return render_template(
        "quiz/view_result.html",
        result={
            'id': result.id,
            'set_name': quiz_set.name,
            'total_questions': result.total_number,
            'correct': result.correct,
            'incorrect': result.incorrect,
            'not_attempt': result.not_attempt,
            'score': score,
            'time_taken': result.formatted_time,  # Make sure this is formatted as MM:SS
            'date': result.created_at
        },
        quiz_set=quiz_set,
        questions=questions,
        answers=answers
    )

@main.route("/admin/sets/<int:set_id>/remove-user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def remove_user_from_set(set_id, user_id):
    try:
        quiz_set = models.QuestionSet.query.get_or_404(set_id)
        user = models.User.query.get_or_404(user_id)
        
        if user in quiz_set.users:
            quiz_set.users.remove(user)
            db.session.commit()
            
            # Notify user about removal
            send_notification(
                user=user,
                title="Quiz Set Access Removed",
                message=f"Your access to quiz set '{quiz_set.name}' has been removed",
                type="info",
                priority="normal"
            )
            
            flash(f"User {user.name} removed from quiz set", "success")
        else:
            flash("User not found in quiz set", "error")
            
        return redirect(url_for('main.distribute_set', set_id=set_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing user: {str(e)}", "error")
        return redirect(url_for('main.distribute_set', set_id=set_id))

@main.route("/api/results/<int:set_id>")
@login_required
def get_results(set_id):
    results = models.Result.query.filter_by(question_set_id=set_id).all()
    return jsonify([{
        'id': r.id,
        'score': r.score,
        'time_taken': r.formatted_time,
        'user': r.user.name,
        'date': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for r in results])

@main.route("/admin/questions/upload", methods=["GET", "POST"])
@login_required
@admin_required
def upload_questions():
    if request.method == "POST":
        try:
            if 'qFile' not in request.files:  # Changed from 'file' to 'qFile'
                flash('No file selected', 'error')
                return redirect(request.url)
                
            file = request.files['qFile']  # Changed from 'file' to 'qFile'
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
                
            if not file.filename.endswith('.csv'):
                flash('Please upload a CSV file', 'error')
                return redirect(request.url)

            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            questions_added = 0
            for row in csv_reader:
                try:
                    # Get or create category
                    category = models.Category.query.filter_by(name=row['Category']).first()
                    if not category:
                        category = models.Category(name=row['Category'])
                        db.session.add(category)
                        db.session.flush()

                    # Create question
                    question = models.Question(
                        question=row['Question'],
                        question_type=row['Type'].lower(),
                        option1=row['Option1'],
                        option2=row['Option2'],
                        option3=row['Option3'] if row['Option3'] else None,
                        option4=row['Option4'] if row['Option4'] else None,
                        correct_option=row['Correct Answer'],
                        category_id=category.id,
                        difficulty=row['Difficulty'].lower(),
                        explanation=row['Explanation'],
                        creator_id=current_user.id,
                        verified=True
                    )
                    
                    db.session.add(question)
                    questions_added += 1
                    
                except Exception as e:
                    print(f"Error adding question: {str(e)}")
                    continue

            db.session.commit()
            flash(f'{questions_added} Questions Added Successfully', 'success')
            return redirect(url_for('main.admin'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error uploading questions: {str(e)}")
            flash(f'Error uploading questions: {str(e)}', 'error')
            return redirect(request.url)
            
    return render_template('admin/upload_questions.html')
