from flask import (
    Blueprint,
    render_template as render,
    flash,
    redirect,
    url_for,
    request
)
from .models import User, Question, QuestionSet, Result
from .extentions import db
from flask_login import (
    logout_user,
    login_required,
    login_user,
    current_user
)
from random import shuffle
from werkzeug.utils import secure_filename
from os.path import join, dirname
from add_questions import (
    load_questions,
    add_to_db
)
from flask import current_app
from .constants import ADD_QUESTIONS

main = Blueprint("main", __name__)

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
        user = User.query.filter_by(
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
        if User.query.filter_by(name=name).first() is not None:
            flash("user with this username already exists", "info")
            return redirect(url_for("main.register"))
        user = User(
            name=name,
            is_admin=False
        )
        user.set_password(data["password"])
        db.session.add(user)
        db.session.commit()
        flash("register complete", "success")
        return redirect(url_for("main.login"))
    return render("register.html")


@main.route("/add", methods=["GET", "POST"])
@login_required
def add_questions():
    if request.method == "POST":
        data = request.form.to_dict()
        for i in range(1, ADD_QUESTIONS+1):
            question = Question(
                question=data[f"q{i}"],
                option1=data[f"q{i}o1"],
                option2=data[f"q{i}o2"],
                option3=data[f"q{i}o3"],
                option4=data[f"q{i}o4"],
                correct_option=data[f"q{i}c"][0].upper(),
                creator_id=current_user.id
            )
            db.session.add(question)
            db.session.commit()
        else:
            flash("your questions added successfully", "success")
    return render(
        "add_questions.html",
        questions=ADD_QUESTIONS,
        show=True if Question.query.filter_by(creator_id=current_user.id).first() is None else False
    )


@main.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    if request.method == "POST":
        data = request.form.to_dict()
        qset = current_user.question_set
        total_questions = len(
            Question.query.filter_by(
                question_set_id = qset
            ).all()
        )
        result = Result(
            total_number=total_questions,
            correct=0,
            not_attempt=0,
            incorrect=0,
            user_id=current_user.id
        )
        for i in range(1, total_questions+1):
            q, o = data.get(f"q{i}", None), data.get(f"q{i}o", None)
            question = Question.query.filter_by(
                id=q,
                correct_option=o,
                verified=True
            ).first()
            if question is not None:
                result.correct += 1
            else:
                result.incorrect += 1
        result.not_attempt = result.total_number-(result.correct+result.incorrect)
        db.session.add(result)
        db.session.commit()
        flash("quiz complete", "success")
        return redirect(url_for("main.result"))
    print("abcdefg", current_user, current_user.question_set)
    questions = Question.query.filter_by(
        question_set_id = current_user.question_set
    ).all()
    shuffle(questions)
    return render(
        "quiz.html",
        questions=questions,
        show=True if Result.query.filter_by(user_id=current_user.id).first() is None else False
    )


@main.route("/result")
@login_required
def result():
    res = Result.query.filter_by(
        user_id=current_user.id
    ).all()
    if res is not None:
        return render(
            "result.html", 
            results=res, 
            user=current_user
        )
    else:
        return render(
            "result.html",
            results=Result(
                user_id=current_user.id,
                total_number=0,
                correct=0,
                incorrect=0,
                not_attempt=0
            ), user=current_user
        )


@main.route("/leaderboard")
@login_required
def leaderboard():
    res = Result.query.order_by(
        Result.correct.desc()
    ).all()
    return render("leaderboard.html", results=res)


@main.route("/admin")
@login_required
def admin():
    if current_user.is_admin:
        # {title: {link: link_of_btn(to_be_redirected), btn_text: text}}
        panel_options = {
            "Upload Questions": {
                "link": url_for("main.admin_upload_questions"),
                "btn-text": "Upload"
            },
            "Verify & Add Questions": {
                "link": url_for("main.admin_add_questions"),
                "btn-text": "Add"
            },
            "Create SETs": {
                "link": url_for("main.admin_create_set"),
                "btn-text": "Create"
            },
            "Show SETs": {
                "link": url_for("main.admin_show_sets"),
                "btn-text": "Show"
            },
            "Distribute SETs": {
                "link": url_for("main.admin_distribute_sets"),
                "btn-text": "Distribute"
            },
            "Get Results": {
                "link": url_for("main.admin_results"),
                "btn-text": "Get"
            }
        }
        return render(
            "admin/admin.html",
            panel_options = panel_options
        )
    else:
        flash("You are not an admin, so you can't access this", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/results")
@login_required
def admin_results():
    if current_user.is_admin:
        res = Result.query.all()
        return render("admin/result.html", results=res)
    else:
        flash("You are not an admin, so you can't access this portal", "warning")
        return redirect(url_for('main.index'))

@main.route("/admin/add-questions", methods=["GET", "POST"])
@login_required
def admin_add_questions():
    if current_user.is_admin:
        if request.method == "POST":
            data, changed = request.form, 0
            for i in data:
                if data[i] == "on":
                    qno = int(i[1:])
                    q = Question.query.filter_by(id=qno).first()
                    q.verified = True
                    db.session.commit()
                    changed += 1
            flash(f"{changed} questions added.", "success")
        qs = Question.query.filter_by(verified=False).all()
        return render("admin/add_questions.html", questions=qs)
    else:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/upload", methods=["GET", "POST"])
@login_required
def admin_upload_questions():
    if not current_user.is_admin:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        file = request.files.get('qFile')
        if not file:
            flash('No file part', 'error')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        if not filename:
            flash('No selected file', 'error')
            return redirect(request.url)

        if filename.endswith('.csv'):
            # Save the file to a secure location
            file_location = join(dirname(__file__), "..", "upload_files", "questions.csv")
            file.save(file_location)
            
            # Process the uploaded file
            try:
                qbank = load_questions(file_location)
                q_added = add_to_db(
                    qbank=qbank,
                    app=current_app,
                    db=db,
                    verbose=False
                )
                flash(f"{q_added} questions added successfully", "success")
            except Exception as e:
                flash(f"An error occurred while processing the file: {str(e)}", "error")
        else:
            flash('Invalid file type, please upload a CSV file.', 'error')

    return render("admin/upload_questions.html")

@main.route("/admin/create_set", methods=["GET", "POST"])
@login_required
def admin_create_set():
    if current_user.is_admin:
        if request.method == "POST":
            data, added = request.form, 0
            set_name = data.get("set_name", "abcd")
            q_set = QuestionSet(
                name=set_name
            )
            db.session.add(q_set)
            db.session.commit()
            for i in data:
                if data[i] == "on":
                    qno = int(i[1:])
                    q = Question.query.filter_by(id=qno).first()
                    q.question_set_id = q_set.id
                    db.session.commit()
                    added += 1
            flash(f"{added} questions added successfully to set {q_set.name}", "success")
        return render(
            "admin/create_set.html", 
            questions = Question.query.filter_by(
                question_set_id = None,
                verified=True
            ).all()
        )
    else:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/show_sets")
@login_required
def admin_show_sets():
    if current_user.is_admin:
        return render(
            "admin/show_sets.html",
            sets = QuestionSet.query.all()
        )
    else:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))

@main.route("/admin/distribute_sets", methods=["GET", "POST"])
@login_required
def admin_distribute_sets():
    if current_user.is_admin:
        if request.method == "POST":
            data, changed = request.form.to_dict(), 0
            qset = QuestionSet.query.filter_by(
                id = int(data.get("set", 0))
            ).first()
            del data["set"]
            for i, j in data.items():
                if j == "on":
                    u = User.query.filter_by(
                        id=int(i[1:])
                    ).first()
                    u.question_set = qset.id
                    db.session.commit()
                    changed += 1
            flash(f"question papers set distributed to {changed} students", "success")
            
        return render(
            "admin/distribute_sets.html",
            sets = QuestionSet.query.all(),
            users = User.query.filter_by(
                question_set = None,
                is_admin=False
            ).all()
        )
    else:
        flash("You are not an admin, so you can't access this page", "warning")
        return redirect(url_for("main.index"))
