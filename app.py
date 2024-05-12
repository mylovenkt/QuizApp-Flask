from create_app import create_app, login_manager
from quiz_app.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
    from app import app
    from quiz_app.extentions import db  # Assuming 'extensions' is where the db instance is initialized.
    from quiz_app.models import User, Question  # Ensure these are correctly imported based on your application's structure.
    from .add_questions import (
        load_questions,
        add_to_db
    )

    # File path to the CSV with questions
    csv_file_path = "upload_files/questions.csv"

    # Load questions from CSV
    print("Loading questions from file...")
    question_bank = load_questions(csv_file_path)

    # Add loaded questions to the database
    if question_bank:
        print(f"Adding questions to the database...")
        added_count = add_to_db(question_bank, app, db)
        print(f"Total questions added: {added_count}")
    else:
        print("No questions were loaded from the file.")