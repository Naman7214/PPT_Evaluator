from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify
import os
from werkzeug.utils import secure_filename
from database import get_db, query_db, insert_db, update_db, init_db, close_db
import google.generativeai as genai
from threading import Thread
import time
import hashlib
from nashx import hasher
from dotenv import load_dotenv
import json


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATABASE'] = os.getenv('DATABASE_URL')

ALLOWED_EXTENSIONS = {'pdf'}

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Check if the uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_prompt(team_name, problem_statement, problem_description):
    return f"""
    The team name is: {team_name}

    Problem Statement: {problem_statement}

    Problem Statement Description: {problem_description}


    Evaluation Criteria:
    1. *Novelty of Idea*: 
    - Originality (5 marks)
    - Creativity (5 marks)

    2. *Feasibility*: 
    - Technical feasibility (5 marks)
    - Resource availability (5 marks)

    3. *Sustainability*:
    - Environmental impact (3 marks)
    - Long-term viability (2 marks)

    4. *Scale of Impact*: 
    - Target audience reach (5 marks)
    - Social/Economic impact (5 marks)

    5. *Potential for Future Work*: 
    - Scalability (2 marks)
    - Roadmap for growth (2 marks)
    - Integration potential (2 marks)

    6. *Clarity and Presentation*:
    - Structure of the presentation (3 marks)
    - Detailing (3 marks)
    - Compliance with guidelines (3 marks)

    Total Marks: 50

    #INSTRUCTIONS:
    - Validate whether the file is a presentation.
    - Check alignment with the problem statement and description.
    - If the content does not align, allocate 0/50.
    - If it's not a PPT, allocate 0/50.
    - After evaluation, return marks according to the criteria distribution.
    - Set difficulty to HARD.
    - Also provide Suggestions to improve ppt

    #OUTPUT:
    {{
    "Novelty_of_Idea_Originality": int,
    "Novelty_of_Idea_Creativity": int,
    "Feasibility_Technical_feasibility": int,   
    "Feasibility_Resource_availability": int,
    "Sustainability_Environmental_impact": int,
    "Sustainability_Long_term_viability": int,
    "Scale_of_Impact_Target_audience_reach": int,
    "Scale_of_Impact_Social_Economic_impact": int,
    "Potential_for_Future_Work_Scalability": int,
    "Potential_for_Future_Work_Roadmap_for_growth": int,
    "Potential_for_Future_Work_Integration_potential": int,
    "Clarity_and_Presentation_Structure_of_presentation": int,
    "Clarity_and_Presentation_Detailing": int,
    "Clarity_and_Presentation_Compliance_with_guidelines": int
    "Justification" : str
    "Suggestions" : str
        }}
    """

def evaluate_ppt_in_background(file_path, file_name, team_name, team_number, problem_statement_id, problem_description):
    prompt = get_prompt(team_name, problem_statement_id, problem_description)
    generation_config = {
        "temperature": 0,
        "top_p": 0.95,
        "top_k": 24,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }
    sample_file = genai.upload_file(path=file_path, display_name=file_name)

    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction="You are an expert PPT evaluator.", generation_config=generation_config)
    response = model.generate_content([sample_file, prompt])
    genai.delete_file(sample_file.name)
    print(f'Deleted file {sample_file.uri}')

    parsed_output = json.loads(response.text)

    # Calculate total marks
    total_marks = sum([
        parsed_output["Novelty_of_Idea_Originality"],
        parsed_output["Novelty_of_Idea_Creativity"],
        parsed_output["Feasibility_Technical_feasibility"],
        parsed_output["Feasibility_Resource_availability"],
        parsed_output["Sustainability_Environmental_impact"],
        parsed_output["Sustainability_Long_term_viability"],
        parsed_output["Scale_of_Impact_Target_audience_reach"],
        parsed_output["Scale_of_Impact_Social_Economic_impact"],
        parsed_output["Potential_for_Future_Work_Scalability"],
        parsed_output["Potential_for_Future_Work_Roadmap_for_growth"],
        parsed_output["Potential_for_Future_Work_Integration_potential"],
        parsed_output["Clarity_and_Presentation_Structure_of_presentation"],
        parsed_output["Clarity_and_Presentation_Detailing"],
        parsed_output["Clarity_and_Presentation_Compliance_with_guidelines"]
    ])

    # Store the total marks in the team_info table
    with app.app_context():
        update_db(
            'UPDATE team_info SET total_marks = ? WHERE team_name = ? AND problem_statement_id = ?',
            (total_marks, team_name, problem_statement_id)
        )

        # Check if record exists in evaluation_details
        existing_record = query_db(
            'SELECT * FROM evaluation_details WHERE team_name = ? AND team_number = ? AND problem_statement_id = ?',
            (team_name, team_number, problem_statement_id),
            one=True
        )

        if existing_record:
            # Update the existing record
            update_db(
                '''UPDATE evaluation_details SET 
                    originality = ?, creativity = ?, technical_feasibility = ?, resource_availability = ?, 
                    environmental_impact = ?, long_term_viability = ?, target_audience_reach = ?, 
                    social_economic_impact = ?, scalability = ?, roadmap_for_growth = ?, integration_potential = ?, 
                    structure_of_presentation = ?, detailing = ?, compliance_with_guidelines = ?, justification = ?, suggestions = ?
                    WHERE team_name = ? AND team_number = ? AND problem_statement_id = ?''',
                (
                    parsed_output["Novelty_of_Idea_Originality"],
                    parsed_output["Novelty_of_Idea_Creativity"],
                    parsed_output["Feasibility_Technical_feasibility"],
                    parsed_output["Feasibility_Resource_availability"],
                    parsed_output["Sustainability_Environmental_impact"],
                    parsed_output["Sustainability_Long_term_viability"],
                    parsed_output["Scale_of_Impact_Target_audience_reach"],
                    parsed_output["Scale_of_Impact_Social_Economic_impact"],
                    parsed_output["Potential_for_Future_Work_Scalability"],
                    parsed_output["Potential_for_Future_Work_Roadmap_for_growth"],
                    parsed_output["Potential_for_Future_Work_Integration_potential"],
                    parsed_output["Clarity_and_Presentation_Structure_of_presentation"],
                    parsed_output["Clarity_and_Presentation_Detailing"],
                    parsed_output["Clarity_and_Presentation_Compliance_with_guidelines"],
                    parsed_output["Justification"],
                    parsed_output["Suggestions"],
                    team_name, team_number, problem_statement_id
                )
            )
        else:
            # Insert a new record
            insert_db(
                '''INSERT INTO evaluation_details (
                    team_name, team_number, problem_statement_id,
                    originality, creativity, technical_feasibility, resource_availability, 
                    environmental_impact, long_term_viability, target_audience_reach,
                    social_economic_impact, scalability, roadmap_for_growth, integration_potential, 
                    structure_of_presentation, detailing, compliance_with_guidelines, justification, suggestions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    team_name, team_number, problem_statement_id,
                    parsed_output["Novelty_of_Idea_Originality"],
                    parsed_output["Novelty_of_Idea_Creativity"],
                    parsed_output["Feasibility_Technical_feasibility"],
                    parsed_output["Feasibility_Resource_availability"],
                    parsed_output["Sustainability_Environmental_impact"],
                    parsed_output["Sustainability_Long_term_viability"],
                    parsed_output["Scale_of_Impact_Target_audience_reach"],
                    parsed_output["Scale_of_Impact_Social_Economic_impact"],
                    parsed_output["Potential_for_Future_Work_Scalability"],
                    parsed_output["Potential_for_Future_Work_Roadmap_for_growth"],
                    parsed_output["Potential_for_Future_Work_Integration_potential"],
                    parsed_output["Clarity_and_Presentation_Structure_of_presentation"],
                    parsed_output["Clarity_and_Presentation_Detailing"],
                    parsed_output["Clarity_and_Presentation_Compliance_with_guidelines"],
                    parsed_output["Justification"],
                    parsed_output["Suggestions"]
                )
            )

    

@app.route('/')
def landing_page():
    if 'username' in session:
        return render_template('index.html')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        match = False
        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user is None:
            flash('Invalid username or password')
        else:
            user_hash = hasher(user['password'],16)
            actual_hash = hasher(password,16)
            if user_hash == actual_hash:
                match = True
            if user and match:
                session['username'] = username
                return redirect(url_for('landing_page'))
            else:
                flash('Invalid username or password.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        team_name = request.form['team_name']
        team_number = request.form['team_number']
        problem_statement_id = request.form['problem_statement_id']
        problem_description = request.form['problem_description']
        file = request.files['file']

        if team_name and team_number and problem_statement_id and problem_description and file and allowed_file(file.filename):
            filename = secure_filename(f"{team_name}_{team_number}.pdf")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            existing_record = query_db(
                'SELECT * FROM team_info WHERE team_name = ? AND problem_statement_id = ?',
                (team_name, problem_statement_id),
                one=True
            )

            if existing_record:
                update_db(
                    'UPDATE team_info SET file_path = ?, problem_description = ? WHERE team_name = ? AND problem_statement_id = ?',
                    (file_path, problem_description, team_name, problem_statement_id)
                )
            else:
                insert_db(
                    'INSERT INTO team_info (team_name, team_number, problem_statement_id, file_path, problem_description) VALUES (?, ?, ?, ?, ?)',
                    (team_name, team_number, problem_statement_id, file_path, problem_description)
                )

            # Start evaluation in the background and show loading screen
            Thread(target=evaluate_ppt_in_background, args=(file_path, filename, team_name, team_number,  problem_statement_id, problem_description)).start()
            return redirect(url_for('loading'))

        else:
            flash('Invalid file or missing team information. Please try again.')

    return render_template('upload_ppt.html')   

@app.route('/loading')
def loading():
    return render_template('loading.html')


@app.route('/view_results')
def view_results():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Fetch all team results
    teams = query_db('SELECT team_number, team_name, problem_statement_id, total_marks FROM team_info')

    return render_template('view_results.html', teams=teams)


@app.route('/get_detailed_results', methods=['POST'])
def get_detailed_results():
    print("get_detailed_results route called")
    data = request.get_json()
    team_name = data.get('team_name')
    team_number = data.get('team_number')
    print(team_name)
    print(team_number)
    if not team_name or not team_number:
        return jsonify({'error': 'Missing team_name or team_number'}), 400

    # Fetch detailed results for the team
    results = query_db(
        'SELECT * FROM evaluation_details WHERE team_name = ? AND team_number = ?',
        (team_name, team_number),
        one=True
    )
    print(results)

    if results is None:
        return jsonify({'error': 'No detailed results found'}), 404

    return jsonify(results)




@app.teardown_appcontext
def close_connection(exception):
    close_db()

if __name__ == '__main__':
    app.run(debug=True)