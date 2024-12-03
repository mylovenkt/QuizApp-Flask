from flask import url_for
from quiz_app.extentions import db, socketio
from quiz_app.models import Notification, Result
from datetime import datetime, timedelta
from flask_socketio import emit
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def get_user_leaderboard_position(user_id, quiz_set_id):
    """Get user's position on the leaderboard for a specific quiz set"""
    results = Result.query.filter_by(question_set_id=quiz_set_id)\
        .order_by(
            Result.correct.desc(),
            Result.time_taken.asc()
        ).all()
    
    # Create a unique list of users sorted by their best performance
    user_scores = {}
    for result in results:
        score = (result.correct / result.total_number * 100)
        if result.user_id not in user_scores or score > user_scores[result.user_id]['score'] or \
           (score == user_scores[result.user_id]['score'] and result.time_taken < user_scores[result.user_id]['time']):
            user_scores[result.user_id] = {
                'score': score,
                'time': result.time_taken
            }
    
    # Convert to sorted list
    sorted_users = sorted(
        user_scores.items(),
        key=lambda x: (-x[1]['score'], x[1]['time'])  # Sort by score desc, then time asc
    )
    
    # Find user's position
    for position, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return position
    
    return None

def send_notification(user, title, message, type='info', link=None, priority='normal', expiry_days=None, metadata=None):
    """
    Enhanced notification sender with more options
    
    Args:
        user: User object
        title: Notification title
        message: Notification message
        type: Type of notification (info, success, warning, quiz, admin)
        link: Optional URL for action
        priority: Priority level (low, normal, high)
        expiry_days: Days until notification expires
        metadata: Additional JSON data
    """
    expiry_date = None
    if expiry_days:
        expiry_date = datetime.utcnow() + timedelta(days=expiry_days)

    notification = Notification(
        user_id=user.id,
        title=title,
        message=message,
        type=type,
        link=link,
        priority=priority,
        expiry_date=expiry_date,
        extra_data=metadata
    )
    
    db.session.add(notification)
    user.unread_notifications += 1
    db.session.commit()

    try:
        emit('new_notification', {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.type,
            'link': notification.link,
            'priority': notification.priority,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=f'user_{user.id}', namespace='/')
    except Exception as e:
        print(f"Error sending real-time notification: {str(e)}")

    return notification

# Specific notification functions
def notify_quiz_assigned(user, quiz_set):
    send_notification(
        user=user,
        title="New Quiz Assigned",
        message=f"You have been assigned a new quiz: {quiz_set.name}",
        type="quiz",
        link=url_for('main.quiz', set_id=quiz_set.id)
    )

def notify_quiz_result(user, result):
    score_percentage = (result.correct / result.total_number) * 100
    send_notification(
        user=user,
        title="Quiz Results Available",
        message=f"You scored {score_percentage:.1f}% on {result.question_set.name}",
        type="success",
        link=url_for('main.view_result', result_id=result.id)
    )

def notify_question_verified(user, question):
    send_notification(
        user=user,
        title="Question Verified",
        message=f"Your question has been verified and added to the question bank",
        type="success"
    )

# Add these test notification functions
def notify_test_all_types(user):
    """Create test notifications of all types"""
    # Regular info notification
    send_notification(
        user=user,
        title="Welcome!",
        message="Welcome to the enhanced notification system",
        type="info"
    )
    
    # High priority warning
    send_notification(
        user=user,
        title="Action Required",
        message="Please complete your profile",
        type="warning",
        priority="high",
        link=url_for('main.edit_profile'),
        metadata={
            "completion": "60%",
            "missing": "Profile picture, Bio"
        }
    )
    
    # Quiz notification with expiry
    send_notification(
        user=user,
        title="New Quiz Available",
        message="Advanced Mathematics Quiz is now available",
        type="quiz",
        priority="normal",
        expiry_days=7,
        metadata={
            "Quiz Name": "Advanced Mathematics",
            "Questions": "20",
            "Time Limit": "45 minutes"
        }
    )
    
    # Success notification
    send_notification(
        user=user,
        title="Achievement Unlocked",
        message="You've completed 10 quizzes!",
        type="success",
        metadata={
            "Achievement": "Quiz Master",
            "Reward": "New badge unlocked"
        }
    )
    
    # Admin notification
    send_notification(
        user=user,
        title="System Update",
        message="The system will be under maintenance",
        type="admin",
        priority="high",
        metadata={
            "Start Time": "22:00 UTC",
            "Duration": "2 hours",
            "Impact": "System will be read-only"
        }
    )

# Add these notification functions
def notify_welcome_new_user(user):
    """Send welcome notification to new user with profile completion reminder"""
    send_notification(
        user=user,
        title="Welcome to Quiz App! 👋",
        message="Complete your profile to get started",
        type="info",
        priority="high",
        link=url_for('main.edit_profile'),
        metadata={
            "steps": [
                "Add profile picture",
                "Fill in your bio",
                "Add your full name",
                "Add your email"
            ]
        }
    )

def notify_quiz_completion(user, result):
    """Notify user about quiz completion and achievements"""
    score_percentage = (result.correct / result.total_number) * 100
    message = f"You scored {score_percentage:.1f}% on {result.question_set.name}"
    
    # Add achievement messages based on score
    if score_percentage == 100:
        message += "\n🏆 Perfect Score! Outstanding!"
    elif score_percentage >= 80:
        message += "\n🌟 Excellent performance!"
    
    send_notification(
        user=user,
        title="Quiz Completed!",
        message=message,
        type="success",
        link=url_for('main.view_result', result_id=result.id),
        metadata={
            "Score": f"{score_percentage:.1f}%",
            "Correct": f"{result.correct}/{result.total_number}",
            "Time Taken": f"{result.time_taken} minutes"
        }
    )

def notify_question_approval(user, question):
    """Notify user when their question is approved"""
    send_notification(
        user=user,
        title="Question Approved! ✅",
        message=f"Your question has been approved and added to {question.question_set.name}",
        type="success",
        priority="normal",
        metadata={
            "Question Type": question.type,
            "Category": question.question_set.name,
            "Points": "10"
        }
    )

def notify_leaderboard_position(user, position, quiz_set):
    """Notify user about their leaderboard position"""
    messages = {
        1: "🥇 Congratulations! You're #1 on the leaderboard!",
        2: "🥈 Amazing! You've reached #2 on the leaderboard!",
        3: "🥉 Great job! You're #3 on the leaderboard!",
        None: f"You've made it to the top 10 in {quiz_set.name}!"
    }
    
    message = messages.get(position, messages[None])
    
    send_notification(
        user=user,
        title="Leaderboard Achievement",
        message=message,
        type="success",
        priority="high" if position <= 3 else "normal",
        link=url_for('main.leaderboard', set_id=quiz_set.id),
        metadata={
            "Position": f"#{position}",
            "Quiz Set": quiz_set.name
        }
    )

def notify_streak_achievement(user, days):
    """Notify user about their quiz streak"""
    send_notification(
        user=user,
        title="Streak Achievement! 🔥",
        message=f"You've maintained a {days}-day quiz streak!",
        type="success",
        priority="normal",
        metadata={
            "Streak": f"{days} days",
            "Achievement": "Consistent Learner"
        }
    )

def generate_verification_token(email):
    """Generate a secure token for email verification"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')

def verify_token(token, expiration=3600):
    """Verify the email verification token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt='email-verification',
            max_age=expiration
        )
        return email
    except:
        return None 