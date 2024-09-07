from flask import Flask, render_template, request, redirect, flash
import os
from werkzeug.utils import secure_filename
from database import get_db, query_db, insert_db, update_db, init_db, close_db
import fitz

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATABASE'] = 'team_info.db'  

ALLOWED_EXTENSIONS = {'pdf'}

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Check if the uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to break the PDF into images using PyMuPDF
def pdf_to_images(pdf_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        output_path = os.path.join(output_folder, f"slide_{page_num + 1}.png")
        pix.save(output_path)
        print(f"Saved slide {page_num + 1} as {output_path}")

@app.route('/')
def landing_page():
    return render_template('index.html')

@app.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if request.method == 'POST':
        team_name = request.form['team_name']
        team_number = request.form['team_number']
        problem_statement_id = request.form['problem_statement_id']
        problem_description = request.form['problem_description']
        file = request.files['file']

        if team_name and team_number and problem_statement_id and problem_description and file and allowed_file(file.filename):
            folder_name = f"{team_name}_{team_number}"
            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(folder_path, filename)
            file.save(file_path)

            # Check for existing record
            existing_record = query_db(
                'SELECT * FROM team_info WHERE team_name = ? AND problem_statement_id = ?',
                (team_name, problem_statement_id),
                one=True
            )

            if existing_record:
                # Update existing record
                update_db(
                    'UPDATE team_info SET file_path = ?, problem_description = ? WHERE team_name = ? AND problem_statement_id = ?',
                    (file_path, problem_description, team_name, problem_statement_id)
                )
            else:
                # Insert new record
                insert_db(
                    'INSERT INTO team_info (team_name, team_number, problem_statement_id, file_path, problem_description) VALUES (?, ?, ?, ?, ?)',
                    (team_name, team_number, problem_statement_id, file_path, problem_description)
                )

            pdf_to_images(file_path, folder_path)

            flash('PDF uploaded and team info saved successfully!')

            return redirect('/')
        else:
            flash('Invalid file or missing team information. Please try again.')

    return render_template('upload_ppt.html')

@app.teardown_appcontext
def close_connection(exception):
    close_db()

if __name__ == '__main__':
    app.run(debug=True)
