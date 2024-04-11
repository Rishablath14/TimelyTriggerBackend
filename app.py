import os
from flask import Flask, render_template, request, jsonify,send_from_directory
from firebase_admin import credentials, db, initialize_app
from flask_cors import CORS
import pandas as pd
import random 
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()
app = Flask(__name__)
CORS(app)
firebase_config = {
    "apiKey": os.environ.get("FIREBASE_API_KEY"),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
    "databaseURL": os.environ.get("FIREBASE_DATABASE_URL"),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.environ.get("FIREBASE_APP_ID"),
    "measurementId": os.environ.get("FIREBASE_MEASUREMENT_ID")
}
cred = credentials.Certificate({
    "type": os.environ.get("FIREBASE_TYPE"),
    "project_id": firebase_config["projectId"],
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_X509_CERT_URL")
})
initialize_app(cred, {
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL"),
    "authDomain": os.getenv("UNIVERSE_DOMAIN")
})

@app.route('/')
def index():
    return render_template('admin.html')

@app.route('/generate_time_table')
def generate_time_table():
    # Fetch department names from the database
    departments = fetch_departments()
    return render_template('generate_time_table.html', departments=departments)

@app.route('/fetch_shifts', methods=['POST'])
def fetch_shifts():
    univerId = request.form['univerId']
    ref = db.reference(f'/universities/{univerId}/College Data')
    shifts = ref.get().keys()
    return jsonify({'shifts': list(shifts)})

@app.route('/fetch_generated_timetable', methods=['POST'])
def fetch_gen_timetable():
    univerId = request.form['univerId']
    ref = db.reference(f'/universities/{univerId}/generated_timetable')
    gen_timetable = ref.get()
    print(generate_time_table)
    return jsonify({'gentimetable': gen_timetable})

@app.route('/fetch_branches', methods=['POST'])
def fetch_branches():
    # Get the selected department name from the request
    department_name = request.form['department']
    univerId = request.form['univerId']
    # Fetch branch names based on the selected department
    branches = fetch_branches_by_department(department_name,univerId)
    return jsonify({'branches': list(branches)})  # Convert branches to list and jsonify

@app.route('/fetch_departments', methods=['POST'])
def fetch_departments():    
    univerId = request.form['univerId']
    ref = db.reference(f'/universities/{univerId}/academic_data')
    # Get all department names
    departments = ref.get().keys()
    return jsonify({'departments': list(departments)})

def fetch_branches_by_department(department_name,univerId):
    # Reference to the 'academic_data' node for the selected department
    
    ref = db.reference(f'/universities/{univerId}/academic_data/{department_name}')
    # Get all branch names for the selected department
    branches = ref.get()
    if branches:
        # Filter out the 'classrooms_labs_data' node if it exists
        branches = [branch for branch in branches.keys() if branch not in('classrooms_labs_data','Teachers Data')]
    return branches if branches else []

# Flask route to fetch programs
@app.route('/fetch_programs', methods=['POST'])
def fetch_programs():
    # Get the selected department and branch names from the request
    department_name = request.form['department']
    branch_name = request.form['branch']
    univerId = request.form['univerId']
    # Fetch program names based on the selected department and branch
    programs = fetch_programs_by_department_and_branch(department_name, branch_name,univerId)
    return jsonify({'programs': programs})

def fetch_programs_by_department_and_branch(department_name, branch_name,univerId):
    # Reference to the 'academic_data' node for the selected department and branch
    ref = db.reference(f'/universities/{univerId}/academic_data/{department_name}/{branch_name}')
    # Get all program names for the selected department and branch
    programs = ref.get()
    
    if programs:
        # Filter out non-program data nodes
        programs = [program for program in programs.keys() if program not in('classrooms_labs_data','Teachers Data')]
    return programs if programs else []

# Flask route to fetch semesters
@app.route('/fetch_semesters', methods=['POST'])
def fetch_semesters():
    # Get the selected department, branch, and program names from the request
    department_name = request.form['department']
    branch_name = request.form['branch']
    program_name = request.form['program']
    univerId = request.form['univerId']
    # Fetch semester names based on the selected department, branch, and program
    semests = fetch_semesters_by_department_branch_and_program(department_name, branch_name, program_name,univerId)
    semesters = list(semests.keys()) if semests else []
    return jsonify({'semesters': semesters})

def fetch_semesters_by_department_branch_and_program(department_name, branch_name, program_name,univerId):
    # Reference to the 'Subjects' node for the selected department, branch, and program
    ref = db.reference(f'/universities/{univerId}/academic_data/{department_name}/{branch_name}/{program_name}/Subjects')
    # Get all subject keys
    semesters = ref.get()  # Update the reference path to include 'Subjects'
    
    
    return semesters

@app.route('/upload_academic_data', methods=['POST'])
def upload_academic_data():
    # Get the uploaded file
    file = request.files['file']
    univerId = request.form['univerId']


    # Read data from the Excel file
    data_df = pd.read_excel(file)

    # Fill NaN values with empty strings
    data_df.fillna("", inplace=True)

    # Process the academic data and store it in Firebase
    for _, program_row in data_df.iterrows():
        department_name = sanitize_string(program_row["Department Name"])
        branch_name = sanitize_string(program_row["Branch Name"])
        program_name = sanitize_string(program_row["Program Name"])
        
        # Create a dictionary to store subjects hierarchy
        subjects = {}   

        # Assuming the subjects are in columns "1 Semester Subject" to "8 Semester Subject"
        for i in range(1, 9):
            semester_subjects = program_row.get(f"{i} Semester Subject", "")  # Check if the column exists
            semester_subject_list = [subj.strip() for subj in semester_subjects.split(",")]  # Split subjects by comma
            semester_name = f"Semester {i}"

            # Add semester to subjects dictionary
            subjects[semester_name] = {}

            # Add subjects to the semester
            for idx, subject in enumerate(semester_subject_list, start=1):
                subjects[semester_name][f"Subject {idx}"] = subject

        # Print the path for debugging
        

        # Reference to the department
        ref = db.reference(f"/universities/{univerId}/academic_data/{department_name}/{branch_name}/{program_name}")
        ref.set({"Subjects": subjects})

    return jsonify({'success': True}), 200

@app.route('/upload_teachers_data', methods=['POST'])
def upload_teachers_data():
    # Get the uploaded file
    file = request.files['file']
    univerId = request.form['univerId']

    # Read data from the Excel file
    data_df = pd.read_excel(file)

    # Fill NaN values with empty strings
    data_df.fillna("", inplace=True)

    # Process the teachers data and store it in Firebase
    for _, row in data_df.iterrows():
        department_name = sanitize_string(row["Department Name"])
        teacher_name = sanitize_string(row["Teacher Name"])  # Sanitize teacher's name
        contact_number = row["Contact No."]
        email_id = row["Email ID"]
        subject_1 = row.get("Subject 1", "")  # Check if the column exists
        subject_2 = row.get("Subject 2", "")  # Check if the column exists
        available_from = row.get("From")  # Check if the column exists
        available_to = row.get("To")  # Check if the column exists

        # Build Firebase reference path
        ref_path = f"/universities/{univerId}/academic_data/{department_name}/Teachers Data"

        # Generate a unique key for the teacher using a sanitized version of their name
        teacher_key = sanitize_string(teacher_name)

        ref = db.reference(f"{ref_path}/{teacher_key}")

        # Store data
        ref.set({
            "Teacher Name": teacher_name,  # Include the original unsanitized name for display purposes
            "Contact_No": contact_number,  # Change key name to "Contact_No"
            "Email ID": email_id,
            "Subject": {
                "Subject 1": subject_1,
                "Subject 2": subject_2
            },
            "Available Time":f"{available_from}-{available_to}",
        })

    return jsonify({'success': True}), 200

@app.route('/upload_classroom_data', methods=['POST'])
def upload_classroom_data():
    # Get the uploaded file
    file = request.files['file']
    univerId = request.form['univerId']

    # Read data from the Excel file
    data_df = pd.read_excel(file)

    # Fill NaN values with empty strings
    data_df.fillna("", inplace=True)

    # Process the college data and store it in Firebase
    for _, row in data_df.iterrows():
            department_name = sanitize_string(row["Department Name"])
            # branch_name = sanitize_string(row["Branch Name"])
            # program_name = sanitize_string(row["Program Name"])
            room_no = row["Room No."]
            room_type = row["Room Type"]
            capacity = row["Capacity"]

            # Build the reference path
            ref_path = f"/universities/{univerId}/academic_data/{department_name}/classrooms_labs_data/Classrooms/{room_no}"

            # Reference to the room
            ref = db.reference(ref_path)

            # Store data
            ref.set({
                "Room Type": room_type,
                "Capacity": capacity,
                "assigned":False,
            })

    return jsonify({'success': True}), 200

def sanitize_string(string):
    # Replace spaces with underscores and remove other illegal characters
    return string.replace('.', '').replace(' ', '_')

# --------------------------- Fetch data from Firebase based on the selected options ---------------------------------

def fetch_subjects(department, branch, program, semester,univerId):
    # Reference the location of subjects in the Firebase database based on the selected options
    ref_path = f'/universities/{univerId}/academic_data/{department}/{branch}/{program}/Subjects/{semester}'

    # Fetch subjects data from Firebase
    subjects_ref = db.reference(ref_path)
    subjects_data = subjects_ref.get()

    # Extract subjects from the fetched data
    subjects = []
    if subjects_data:
        subjects = list(subjects_data.values())  # Extracting subject names from the dictionary keys

    return subjects

# ------------------------------------------------------------------------------------------
# -------------- Function to fetch lectures and lunch timings based on the selected shift
def fetch_shift_schedule(shift,univerId):
    ref = db.reference(f'/universities/{univerId}/College Data/{shift}')
    shift_info = ref.get()  # This will return a dictionary containing shift information

    lectures = shift_info.get('lectures', None)
    lunch = shift_info.get('Lunch', None)

    return lectures, lunch

# ------------------------------------------------------------------------------------------
# ----------------------------------Function to fetch available classroom numbers
def fetch_available_classrooms(department,univerId):
    ref = db.reference(f'/universities/{univerId}/academic_data/{department}')
    classrooms_ref = ref.child('classrooms_labs_data').child('Classrooms')
    classrooms_data = classrooms_ref.get()
    
    available_classrooms = []
    
    if classrooms_data:
        for classroom_number, classroom_info in classrooms_data.items():
            if not classroom_info.get('assigned', False):  # Check if classroom is not assigned
                available_classrooms.append(classroom_number)           
    return available_classrooms

def fetch_univername(univerId):
    ref = db.reference(f'/universities/{univerId}')
    univer_data = ref.get()  
    return univer_data["UniversityName"]

# ----------------------------------Function to fetch Teachers with Timing
def fetch_teachers_with_timing(department,fetched_subjects,univerId):
    # Reference to the Teachers Data for the selected department
    ref = db.reference(f'/universities/{univerId}/academic_data/{department}/Teachers Data')
    teachers_data = ref.get()
    teachers_with_timing = []
    if teachers_data:
        for teacher_key, teacher_info in teachers_data.items():
            teacher_name = teacher_info.get('Teacher Name', '')
            available_time = teacher_info.get('Available Time', '')
            subjects = teacher_info.get('Subject', {})
            # Check if the teacher has subjects matching the fetched subjects
            matched_subjects = set(subjects.values()) & set(fetched_subjects)
            if matched_subjects:
                teachers_with_timing.append({'Teacher Name': teacher_name, 'Available Time': available_time})
            

    return teachers_with_timing

# ----------------------------------Function to generate_timetable_structure
def generate_timetable_structure(shift, department, branch, program, semester, session_from, session_to, session_year):
    # Fetch actual data from the database to replace placeholders
    university_name = "Sage University Indore"  # Fetch from the database
    classroom_no = "104"  # Fetch from the database
    room_no = "Room No. - 104"  # Fetch from the database
    shift_name = shift  # Use the provided shift
    branch_name = branch  # Use the provided branch
    program_name = program  # Use the provided program
    semester_name = semester  # Use the provided semester
    session_info = f"Session: {session_from} - {session_to} {session_year}"  # Use the provided session

    # Construct the timetable structure with the fetched data
    timetable_structure = f"""
    Timetable for {university_name}
    Classroom No. - {classroom_no}
    Shift: {shift_name}
    Department: {department}
    Branch: {branch_name}
    Program: {program_name}
    Semester: {semester_name}
    {session_info}
    """
    return timetable_structure

def initialize_timetable_structure(time_slots):
    timetable = {
        'Monday': {},
        'Tuesday': {},
        'Wednesday': {},
        'Thursday': {},
        'Friday': {},
        'Saturday': {},
    }
    # Initialize time slots from 8:00 AM to 5:00 PM with 1-hour intervals
    # Assign empty slots for each day and time slot
    for day in timetable:
        for time_slot in time_slots:
            timetable[day][time_slot] = {'subject': '', 'teacher': ''}
    return timetable

def assign_subject(fetched_subjects):
    if fetched_subjects:
        return random.choice(fetched_subjects)
    else:
        return ''

def assign_teacher(teachers_with_timing, time_slot):
    if teachers_with_timing:
        # Convert the time slot string to datetime object for comparison
        time_slot_start, time_slot_end = time_slot.split(' - ')
        time_slot_start = datetime.strptime(time_slot_start, '%H:%M')
        time_slot_end = datetime.strptime(time_slot_end, '%H:%M')

        # Filter available teachers based on time availability
        available_teachers = [teacher for teacher in teachers_with_timing if is_teacher_available(teacher['Available Time'], time_slot_start, time_slot_end)]

        # Return a random teacher's name from the filtered available teachers
        if available_teachers:
            return random.choice(available_teachers)['Teacher Name']

    return ''

def is_teacher_available(available_time, time_slot_start, time_slot_end):
    available_from, available_to = available_time.split('-')
    available_from = datetime.strptime(available_from, '%H:%M:%S')
    available_to = datetime.strptime(available_to, '%H:%M:%S')

    # Check if the time slot falls within the teacher's available time range
    return available_from <= time_slot_start <= available_to and available_from <= time_slot_end <= available_to

def assign_classroom(available_classrooms):
    if available_classrooms:
        return random.choice(available_classrooms)
    else:
        return ''

@app.route('/generate_time_table_result', methods=['POST'])
def generate_time_table_result():
    print("AAGYA//")
    # Get selected options from the request
    shift = request.form['shift']
    department = request.form['department']
    branch = request.form['branch']
    program = request.form['program']
    semester = request.form['semester']
    session_from_month = request.form['sessionFromMonth']
    session_to_month = request.form['sessionToMonth']
    session_year = request.form['sessionYear']
    univerId = request.form['univerId']
    session_from = f"{session_from_month} {session_year}"
    session_to = f"{session_to_month} {session_year}"

    # Fetch data from Firebase based on the selected options
    fetched_subjects = fetch_subjects(department, branch, program, semester,univerId)
    shift_lectures, lunch_timing = fetch_shift_schedule(shift,univerId)
    available_classrooms = fetch_available_classrooms(department,univerId)
    univerName = fetch_univername(univerId)
    teachers_with_timing = fetch_teachers_with_timing(department, fetched_subjects,univerId)  # Pass fetched_subjects here
    
    if(shift=="shift_1"):
     time_slots = ['08:30 - 09:20', '09:20 - 10:10', '10:10 - 11:00', '11:00 - 11:50', '11:50 - 12:20', '12:20 - 13:10', '13:10 - 14:00', '14:00 - 14:50']
     timetable = initialize_timetable_structure(time_slots=time_slots)
    else:
     time_slots = ['10:10 - 11:00', '11:00 - 11:50', '11:50 - 12:40', '12:40 - 13:10', '13:10 - 14:00', '14:00 - 14:50','14:50 - 15:40','15:40 - 16:30']
     timetable = initialize_timetable_structure(time_slots=time_slots)
    
    # timetable = generate_timetable_structure(shift, department, branch, program, semester, session_from, session_to, session_year)     
    modified_timetable = {}

    # Iterate over the days and time slots in the original timetable
    for day in timetable:
        modified_timetable[day] = {}
        for time_slot in timetable[day]:
            subject = assign_subject(fetched_subjects)
            teacher = assign_teacher(teachers_with_timing, time_slot)
            classroom = assign_classroom(available_classrooms)
            modified_timetable[day][time_slot] = {'subject': subject, 'teacher': teacher}

    # Assign a classroom to the timetable
    classroom = assign_classroom(available_classrooms)

    modified_timetable['classroom'] = classroom
    session_info = f"Session: {session_from} - {session_to}"  # Use the provided session
    timetable_structure = f"""Timetable for {univerName} --> Classroom No. - {classroom} Shift: {shift} Department: {department} Branch: {branch} Program: {program} Semester: {semester} {session_info}"""
    timetable_data = {
        'shift':shift,
        'department':department,
        'branch':branch,
        'program':program,
        'semester': semester,
        'Structure': timetable_structure,
        'timetable': modified_timetable,
    }
    semkey = semester.replace(' ', '_').lower()
    semkey = ''.join(char for char in semkey if char.isalnum() or char in ['_', '-'])
    time_key = f"{program}_{semkey}_{shift}"
    ref_path = f"/universities/{univerId}/generated_timetable/{time_key}"
    ref = db.reference(ref_path)
    ref.set(timetable_data)
    # Return the modified timetable
    return jsonify({'timetable': timetable_data})  