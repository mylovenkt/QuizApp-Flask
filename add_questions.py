from csv import reader
from quiz_app.models import User

def load_questions(file_path, verbose: bool = True) -> dict:
    '''
    Load questions from a CSV file and serialize them into a dictionary mapped by roll_no.
    
    Arguments:
    - file_path (str): Path to the CSV file.
    - verbose (bool): Toggle for detailed logging.
    
    Returns:
    - dict: A dictionary where each key is a roll_no and the value is a list of question dictionaries.
    '''
    questions = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            csv_reader = reader(f)
            headers = next(csv_reader, None)
            if not headers:
                if verbose:
                    print("The CSV file is empty or missing headers.")
                return questions

            for index, row in enumerate(csv_reader):
                if verbose:
                    print(f"Processing row {index + 1}: {row}")
                if len(row) < 4:  # Ensure there are at least 4 columns: roll_no, question, options, correct option
                    if verbose:
                        print("Skipping a row due to insufficient data.")
                    continue

                roll_no = row[0]  # The roll_no is now expected to be in the first column
                question_text = row[1]
                options = row[2].strip().split("\n")
                correct_option = row[3]

                if len(options) != 4:
                    if verbose:
                        print(f"RollNo: {roll_no} has incorrect number of options ({len(options)}).")
                    continue

                question_dict = {
                    "q": question_text,
                    "o": tuple(options),
                    "co": correct_option
                }

                if roll_no in questions:
                    questions[roll_no].append(question_dict)
                else:
                    questions[roll_no] = [question_dict]

    except FileNotFoundError:
        if verbose:
            print(f"File {file_path} not found.")
    except Exception as e:
        if verbose:
            print(f"An error occurred while reading the file: {e}")

    return questions

def add_to_db(qbank: dict, app, db, verbose: bool = True) -> int:
    '''
    Add questions to the database.
    
    Arguments:
    - qbank (dict): A dictionary mapping roll numbers to lists of question data.
    - app: Flask app instance for context.
    - db: Database session object.
    - verbose (bool): Toggle for detailed logging.
    
    Returns:
    - int: Count of questions successfully added to the database.
    '''
    questions_added = 0

    with app.app_context():
        for roll_no, questions in qbank.items():
            user = User.query.filter_by(id=roll_no).first()
            if not user:
                if verbose:
                    print(f"User does not exist with ID {roll_no}.")
                continue

            for question in questions:
                try:
                    new_question = Question(
                        question=question["q"],
                        option1=question["o"][0],
                        option2=question["o"][1],
                        option3=question["o"][2],
                        option4=question["o"][3],
                        correct_option=question["co"],
                        creator_id=user.id
                    )
                    db.session.add(new_question)
                    questions_added += 1
                except Exception as e:
                    if verbose:
                        print(f"Failed to add question for user {roll_no}: {e}")

            db.session.commit()
            if verbose:
                print(f"Questions added for user {roll_no}: {questions_added}")

    return questions_added

if __name__ == "__main__":
    from app import app
    from quiz_app.extentions import db  # Assuming 'extensions' is where the db instance is initialized.
    from quiz_app.models import User, Question  # Ensure these are correctly imported based on your application's structure.

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
