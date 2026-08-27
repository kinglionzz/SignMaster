from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import os
import uuid

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ====================== MODELS ======================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_path = db.Column(db.String(300), nullable=False)
    subtitle_path = db.Column(db.String(300))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_uploaded = db.Column(db.DateTime, default=db.func.current_timestamp())


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ====================== ROUTES ======================
@app.route('/')
def index():
    return redirect(url_for('home'))    # Show home first


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('register'))

        user = User(fullname=fullname, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'lecturer':
        return redirect(url_for('dashboard_lecturer'))
    else:
        return redirect(url_for('dashboard_student'))


@app.route('/dashboard_student')
@login_required
def dashboard_student():
    videos = Video.query.order_by(Video.date_uploaded.desc()).limit(6).all()
    return render_template('dashboard.html', user=current_user, videos=videos)


@app.route('/dashboard_lecturer')
@login_required
def dashboard_lecturer():
    videos = Video.query.order_by(Video.date_uploaded.desc()).limit(6).all()
    return render_template('dashboard_lecturer.html', user=current_user, videos=videos)


@app.route('/video_library')
@login_required
def video_library():
    videos = Video.query.order_by(Video.date_uploaded.desc()).all()
    return render_template('video_library.html', videos=videos)


@app.route('/upload_video', methods=['GET', 'POST'])
@login_required
def upload_video():
    if current_user.role != 'lecturer':
        flash('Only lecturers can upload videos', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        video = request.files['video']
        subtitle = request.files.get('subtitle')

        if video:
            # Save video
            video_filename = str(uuid.uuid4()) + "_" + video.filename
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
            video.save(video_path)

            # Save subtitle if uploaded
            subtitle_filename = None
            if subtitle and subtitle.filename:
                subtitle_filename = str(uuid.uuid4()) + "_" + subtitle.filename
                subtitle_path = os.path.join(app.config['UPLOAD_FOLDER'], subtitle_filename)
                subtitle.save(subtitle_path)

            new_video = Video(
                title=title,
                description=description,
                video_path=video_filename,
                subtitle_path=subtitle_filename,
                uploaded_by=current_user.id
            )
            db.session.add(new_video)
            db.session.commit()

            flash('Video uploaded successfully!', 'success')
            return redirect(url_for('video_library'))

    return render_template('upload_video.html')


# ====================== ASSIGNMENT MODEL ======================
class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_path = db.Column(db.String(300))  # Student uploaded file
    comment = db.Column(db.Text)  # Lecturer's comment
    status = db.Column(db.String(50), default='Submitted')  # Submitted, Reviewed
    date_submitted = db.Column(db.DateTime, default=db.func.current_timestamp())


# ====================== ASSIGNMENT ROUTES ======================

@app.route('/submit_assignment', methods=['GET', 'POST'])
@login_required
def submit_assignment():
    if current_user.role != 'student':
        flash('Only students can submit assignments', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        file = request.files['file']

        if file:
            filename = str(uuid.uuid4()) + "_" + file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            new_assignment = Assignment(
                title=title,
                description=description,
                student_id=current_user.id,
                file_path=filename
                # lecturer_id left blank for now (lecturer can review all)
            )
            db.session.add(new_assignment)
            db.session.commit()

            flash('Assignment submitted successfully!', 'success')
            return redirect(url_for('my_assignments'))

    return render_template('submit_assignment.html')


@app.route('/my_assignments')
@login_required
def my_assignments():
    if current_user.role == 'student':
        assignments = Assignment.query.filter_by(student_id=current_user.id).all()
        return render_template('student_assignments.html', assignments=assignments)
    else:
        # Lecturer sees ALL submissions
        assignments = Assignment.query.all()
        return render_template('lecturer_assignments.html', assignments=assignments)

@app.route('/review_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def review_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)

    if current_user.role != 'lecturer':
        flash('Only lecturers can review assignments', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        assignment.comment = request.form['comment']
        assignment.status = 'Reviewed'
        db.session.commit()
        flash('Comment added successfully!', 'success')
        return redirect(url_for('my_assignments'))

    return render_template('review_assignment.html', assignment=assignment)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/signmaster_quiz')
def signmaster_quiz():
    return render_template('signmaster_quiz.html')

@app.route('/fingerspell_quiz')
def fingerspell_quiz():
    return render_template('fingerspell_quiz.html')


@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/start_lesson')
def start_lesson():
    return render_template('start_lesson.html')

@app.route('/family_lesson')
def family_lesson():
    return render_template('family_lesson.html')

@app.route('/pronouns_question_words_endings')
def pronouns_question_words_endings():
    return render_template('pronouns_question_words_endings.html')

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory('videos', filename)

@app.route('/exercises')
def exercises():
    return render_template('exercises.html')

@app.route('/quiz_result')
def quiz_result():
    score = int(request.args.get('score', 0))
    total = int(request.args.get('total', 0))
    return render_template('quiz_result.html', score=score, total=total)


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Password reset instructions have been sent to your email (demo).', 'success')
        else:
            flash('No account found with that email.', 'danger')
        return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')


@app.route('/dictionary')
def dictionary():
    query = request.args.get('q', '').lower().strip()

    # Dictionary of signs (you can add more later)
    signs = {
        "water": {
            "word": "water",
            "video": "water.mp4",
            # "description": "The sign for water in Nigerian Sign Language."
        },
        "father": {
            "word": "father",
            "video": "father.mp4",
        },
        "mother": {
            "word": "mother",
            "video": "mother.mp4",
        },
        "hello": {
            "word": "hello",
            "video": "hello.mp4",
        },
        "male": {
            "word": "male",
            "video": "male.mp4",
        },
        "female": {
            "word": "female",
            "video": "female.mp4",
        },
        "adult": {
            "word": "adult",
            "video": "adult.mp4",
        },
        "am": {
            "word": "am",
            "video": "am.mp4",
        },
        "another": {
            "word": "another",
            "video": "another.mp4",
        },
        "any": {
            "word": "any",
            "video": "any.mp4",
        },
        "anybody": {
            "word": "anybody",
            "video": "anybody.mp4",
        },
        "anyone": {
            "word": "anyone",
            "video": "anyone.mp4",
        },
        "anything": {
            "word": "anything",
            "video": "anything.mp4",
        },
        "april": {
            "word": "april",
            "video": "april.mp4",
        },
        "august": {
            "word": "august",
            "video": "august.mp4",
        },
        "aunty": {
            "word": "aunty",
            "video": "aunty.mp4",
        },
        "baby": {
            "word": "baby",
            "video": "baby.mp4",
        },
        "brother": {
            "word": "brother",
            "video": "brother.mp4",
        },
        "child": {
            "word": "child",
            "video": "child.mp4",
        },
        "cousin": {
            "word": "cousin",
            "video": "cousin.mp4",
        },
        "daughter": {
            "word": "daughter",
            "video": "daughter.mp4",
        },
        "december": {
            "word": "december",
            "video": "december.mp4",
        },
        "divorce": {
            "word": "divorce",
            "video": "divorce.mp4",
        },
        "engagement": {
            "word": "engagement",
            "video": "engagement.mp4",
        },
        "every": {
            "word": "every",
            "video": "every.mp4",
        },
        "everybody": {
            "word": "everybody",
            "video": "everybody.mp4",
        },
        "everyone": {
            "word": "everyone",
            "video": "everyone.mp4",
        },
        "everything": {
            "word": "everything",
            "video": "everything.mp4",
        },
        "family": {
            "word": "family",
            "video": "family.mp4",
        },
        "february": {
            "word": "february",
            "video": "february.mp4",
        },
        "fellowship": {
            "word": "fellowship",
            "video": "fellowship.mp4",
        },
        "generation": {
            "word": "generation",
            "video": "generation.mp4",
        },
        "grandfather": {
            "word": "grandfather",
            "video": "grandfather.mp4",
        },
        "gentleman": {
            "word": "gentleman",
            "video": "gentleman.mp4",
        },
        "grandmother": {
            "word": "grandmother",
            "video": "grandmother.mp4",
        },
        "her": {
            "word": "her",
            "video": "her.mp4",
        },
        "herself": {
            "word": "herself",
            "video": "herself.mp4",
        },
        "himself": {
            "word": "himself",
            "video": "himself.mp4",
        },
        "his": {
            "word": "his",
            "video": "his.mp4",
        },
        "how": {
            "word": "how",
            "video": "how.mp4",
        },
        "husband": {
            "word": "husband",
            "video": "husband.mp4",
        },
        "i": {
            "word": "i",
            "video": "i.mp4",
        },
        "ing": {
            "word": "ing",
            "video": "ing.mp4",
        },
        "itself": {
            "word": "itself",
            "video": "itself.mp4",
        },
        "january": {
            "word": "january",
            "video": "january.mp4",
        },
        "june": {
            "word": "june",
            "video": "june.mp4",
        },
        "july": {
            "word": "july",
            "video": "july.mp4",
        },
        "kid": {
            "word": "kid",
            "video": "kid.mp4",
        },
        "march": {
            "word": "march",
            "video": "march.mp4",
        },
        "may": {
            "word": "may",
            "video": "may.mp4",
        },
        "me": {
            "word": "me",
            "video": "me.mp4",
        },
        "ment": {
            "word": "ment",
            "video": "ment.mp4",
        },
        "my": {
            "word": "my",
            "video": "my.mp4",
        },
        "myself": {
            "word": "myself",
            "video": "myself.mp4",
        },
        "negative": {
            "word": "negative",
            "video": "negative.mp4",
        },
        "nephew": {
            "word": "nephew",
            "video": "nephew.mp4",
        },
        "niece": {
            "word": "father",
            "video": "father.mp4",
        },
        "november": {
            "word": "november",
            "video": "november.mp4",
        },
        "october": {
            "word": "october",
            "video": "october.mp4",
        },
        "other": {
            "word": "other",
            "video": "other.mp4",
        },
        "our": {
            "word": "our",
            "video": "our.mp4",
        },
        "parents": {
            "word": "parents",
            "video": "parents.mp4",
        },
        "person": {
            "word": "person",
            "video": "person.mp4",
        },
        "post": {
            "word": "post",
            "video": "post.mp4",
        },
        "pre": {
            "word": "pre",
            "video": "pre.mp4",
        },
        "september": {
            "word": "september",
            "video": "september.mp4",
        },
        "sign language": {
            "word": "sign language",
            "video": "sign_lang.mp4",
        },
        "sister": {
            "word": "sister",
            "video": "sister.mp4",
        },
        "somebody": {
            "word": "somebody",
            "video": "somebody.mp4",
        },
        "someone": {
            "word": "someone",
            "video": "someone.mp4",
        },
        "something": {
            "word": "something",
            "video": "something.mp4",
        },
        "son": {
            "word": "son",
            "video": "son.mp4",
        },
        "stepfather": {
            "word": "stepfather",
            "video": "stepfather.mp4",
        },
        "stepmother": {
            "word": "stepmother",
            "video": "stepmother.mp4",
        },
        "that": {
            "word": "that",
            "video": "that.mp4",
        },
        "the": {
            "word": "the",
            "video": "the.mp4",
        },
        "their": {
            "word": "their",
            "video": "their.mp4",
        },
        "them": {
            "word": "them",
            "video": "them.mp4",
        },
        "themselve": {
            "word": "themselve",
            "video": "themselve.mp4",
        },
        "they": {
            "word": "they",
            "video": "they.mp4",
        },
        "this": {
            "word": "this",
            "video": "this.mp4",
        },
        "those": {
            "word": "those",
            "video": "those.mp4",
        },
        "twins": {
            "word": "twins",
            "video": "twins.mp4",
        },
        "uncle": {
            "word": "uncle",
            "video": "uncle.mp4",
        },
        "us": {
            "word": "us",
            "video": "us.mp4",
        },
        "we": {
            "word": "we",
            "video": "we.mp4",
        },
        "wedding": {
            "word": "wedding",
            "video": "wedding.mp4",
        },
        "what": {
            "word": "what",
            "video": "what.mp4",
        },
        "when": {
            "word": "when",
            "video": "when.mp4",
        },
        "where": {
            "word": "where",
            "video": "where.mp4",
        },
        "whether": {
            "word": "whether",
            "video": "whether.mp4",
        },
        "which": {
            "word": "which",
            "video": "which.mp4",
        },
        "who": {
            "word": "who",
            "video": "who.mp4",
        },
        "why": {
            "word": "why",
            "video": "why.mp4",
        },
        "wife": {
            "word": "wife",
            "video": "wife.mp4",
        },
        "you": {
            "word": "you",
            "video": "you.mp4",
        },
        "your": {
            "word": "your",
            "video": "your.mp4",
        },
        "yourself": {
            "word": "yourself",
            "video": "yourself.mp4",
        }
    }

    result = signs.get(query)
    return render_template('dictionary.html', query=query, result=result)





# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

@app.route('/signmaster_quiz')
@login_required


@app.route('/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    # For now, just show result page (we will improve later)
    return render_template('quiz_result.html', score=8, total=10)


