from .extentions import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
import json
from flask import url_for

# Add new association table
user_quiz_sets = db.Table('user_quiz_sets',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('quiz_set_id', db.Integer, db.ForeignKey('questionset.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    questions = db.relationship("Question", backref="creator")
    is_admin = db.Column(db.Boolean, default=False)
    results = db.relationship("Result", back_populates="user")
    quiz_sets = db.relationship('QuestionSet', 
                              secondary=user_quiz_sets,
                              backref=db.backref('users', lazy='dynamic'))
    avatar_url = db.Column(db.String(200))
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    email_verified = db.Column(db.Boolean, default=False)
    bio = db.Column(db.Text)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=None, nullable=True)
    social_links = db.Column(db.JSON)  # Store social media links
    unread_notifications = db.Column(db.Integer, default=0)
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    DEFAULT_AVATAR = """
    data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23E9ECEF'/%3E%3Ccircle cx='100' cy='70' r='50' fill='%23ADB5BD'/%3E%3Ccircle cx='100' cy='230' r='100' fill='%23ADB5BD'/%3E%3C/svg%3E
    """.strip()

    def set_password(self, pwd):
        self.password = generate_password_hash(pwd)

    def verify_password(self, pwd):
        return check_password_hash(self.password, pwd)

    def __repr__(self):
        return f"User({self.id}, '{self.name}')"

    @property
    def is_online(self):
        """Check if user was active in last 5 minutes"""
        if not self.last_seen:
            return False
        return (datetime.utcnow() - self.last_seen).total_seconds() < 300

    @property
    def get_avatar_url(self):
        if not self.avatar_url:
            return self.DEFAULT_AVATAR
        return url_for('static', filename=f'uploads/avatars/{self.avatar_url}')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default='multiple_choice')  # multiple_choice, true_false, image
    image_url = db.Column(db.String(200), nullable=True)  # For image-based questions
    option1 = db.Column(db.String, nullable=True)  # Made nullable for true/false
    option2 = db.Column(db.String, nullable=True)
    option3 = db.Column(db.String, nullable=True)
    option4 = db.Column(db.String, nullable=True)
    correct_option = db.Column(db.CHAR, nullable=False)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question_set_id = db.Column(db.Integer, db.ForeignKey("questionset.id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    difficulty = db.Column(db.String(20), default="medium")
    content = db.Column(db.Text)  # Rich text content
    explanation = db.Column(db.Text)  # Explanation for the answer
    tags = db.Column(db.JSON)  # Tags for better organization
    media_urls = db.Column(db.JSON)  # Store multiple media files
    difficulty_level = db.Column(db.Integer, default=1)  # 1-5 difficulty scale
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = db.Column(db.Integer, default=1)  # Track question versions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def difficulty_value(self):
        return {
            "easy": 1,
            "medium": 2,
            "hard": 3
        }.get(self.difficulty, 2)

    def __repr__(self):
        return f"Question({self.id}, '{self.question}', {self.creator})"

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_number = db.Column(db.Integer, nullable=False)
    correct = db.Column(db.Integer, default=0, nullable=False)
    not_attempt = db.Column(db.Integer, default=0, nullable=False)
    incorrect = db.Column(db.Integer, default=0, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    time_taken = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    question_set_id = db.Column(db.Integer, db.ForeignKey('questionset.id'))
    answers = db.Column(db.JSON)  # Store answers as JSON
    
    # Define relationships
    user = db.relationship('User', back_populates="results")
    question_set = db.relationship('QuestionSet', backref='results')

    @property
    def answers_dict(self):
        """Convert JSON string to dictionary"""
        if self.answers:
            try:
                if isinstance(self.answers, str):
                    return json.loads(self.answers)
                return self.answers
            except:
                return {}
        return {}

    @property
    def formatted_time(self):
        """Format time taken in MM:SS format"""
        if self.time_taken is not None:
            minutes = self.time_taken // 60
            seconds = self.time_taken % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"

    @property
    def score(self):
        """Calculate percentage score"""
        if self.total_number == 0:
            return 0.0
        return (self.correct / self.total_number) * 100

    def __repr__(self):
        return f"Result({self.id}, {self.correct}/{self.total_number})"

class QuestionSet(db.Model):
    __tablename__ = 'questionset'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=True)
    time_limit = db.Column(db.Integer, nullable=False, default=0)
    questions = db.relationship("Question", backref="qset")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"QuestionSet({self.id}, {[i.id for i in self.questions]})"

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200))
    questions = db.relationship("Question", backref="category")

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # info, success, warning, quiz, admin, etc.
    link = db.Column(db.String(200))  # Optional link to related content
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    action_taken = db.Column(db.Boolean, default=False)  # Track if user acted on notification
    priority = db.Column(db.String(10), default='normal')  # low, normal, high
    expiry_date = db.Column(db.DateTime)  # Optional expiry date
    extra_data = db.Column(db.JSON)  # Changed from metadata to extra_data

class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # general, quiz_discussion, question_discussion, private
    is_private = db.Column(db.Boolean, default=False)
    passcode = db.Column(db.String(6))  # For private rooms
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Optional relationships for specific room types
    quiz_set_id = db.Column(db.Integer, db.ForeignKey('questionset.id'))
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='room', lazy=True)
    participants = db.relationship('User', 
                                 secondary='chat_participants',
                                 backref=db.backref('chat_rooms', lazy=True))
    creator = db.relationship('User', backref='created_rooms')
    
    @classmethod
    def get_user_private_room_count(cls, user_id):
        return cls.query.filter_by(creator_id=user_id, type='private').count()

    def check_passcode(self, passcode):
        """Check if provided passcode matches room passcode"""
        return str(self.passcode).strip() == str(passcode).strip()

    def can_delete(self, user):
        """Check if user can delete this room"""
        return user.is_admin or (user.id == self.creator_id)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    file_url = db.Column(db.String(200))
    
    # Relationships
    user = db.relationship('User', backref='chat_messages')
    reactions = db.relationship('MessageReaction', backref='message', lazy=True)

    def can_delete(self, user):
        """Check if user can delete this message"""
        return user.is_admin or user.id == self.user_id

class MessageReaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reaction = db.Column(db.String(20), nullable=False)  # emoji code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Association table for chat room participants
chat_participants = db.Table('chat_participants',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('room_id', db.Integer, db.ForeignKey('chat_room.id'), primary_key=True)
)

# Update the MessageReport model
class MessageReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=False)  # Changed from 'message' to 'chat_message'
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, resolved, dismissed
    
    # Add relationships
    message = db.relationship('ChatMessage', backref='reports')
    reporter = db.relationship('User', backref='message_reports')

