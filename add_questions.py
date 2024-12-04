from quiz_app.models import Question, Category
from quiz_app.extentions import db
import csv
from datetime import datetime

def load_questions(file_path):
    """Load questions from CSV file
    
    Parameters:
        file_path (str): Path to CSV file
        
    Returns:
        list: List of dictionaries containing question data
    """
    questions = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)
    return questions

def add_to_db(qbank, app, db, verbose=True):
    """Add questions to database
    
    Parameters:
        qbank (list): List of question dictionaries
        app: Flask application instance
        db: SQLAlchemy database instance
        verbose (bool): Print progress messages
        
    Returns:
        int: Number of questions added
    """
    questions_added = 0
    
    with app.app_context():
        for q in qbank:
            try:
                # Get or create category
                category = Category.query.filter_by(name=q['Category']).first()
                if not category:
                    category = Category(name=q['Category'])
                    db.session.add(category)
                    db.session.flush()

                # Create question
                question = Question(
                    question=q['Question'],
                    question_type=q['Type'].lower(),
                    option1=q['Option1'],
                    option2=q['Option2'],
                    option3=q['Option3'] if q['Option3'] else None,
                    option4=q['Option4'] if q['Option4'] else None,
                    correct_option=q['Correct Answer'],
                    category_id=category.id,
                    difficulty=q['Difficulty'].lower(),
                    explanation=q.get('Explanation', ''),
                    verified=True,
                    created_at=datetime.utcnow()
                )
                
                db.session.add(question)
                questions_added += 1
                
                if verbose:
                    print(f"Added question: {q['Question'][:50]}...")
                    
            except Exception as e:
                print(f"Error adding question: {str(e)}")
                continue
                
        db.session.commit()
        
    return questions_added 