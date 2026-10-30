from faker import Faker
import random
from weasyprint import HTML
from uuid import uuid4


fake = Faker()


def generate_university_name():
    universities = [
        'Massachusetts Institute of Technology',
        'Stanford University',
        'Harvard University',
        'California Institute of Technology',
        'University of Oxford',
        'ETH Zurich',
        'University of Cambridge',
        'Imperial College London',
        'University of Chicago',
        'UCL (University College London)'
    ]
    return random.choice(universities)

def generate_personal_info():
    return {
        "Name": fake.name(),
        "Email": fake.email(),
        "Phone": fake.phone_number(),
    }

def generate_education():
    degrees = ['B.Sc. in Computer Science', 'B.Sc. in Statistics', 'M.Sc. in Data Science', 'M.Sc. in Computer Science']
    return {
        "Degree": random.choice(degrees),
        "University": generate_university_name(),
        "Year": f"{random.randint(2010, 2015)} - {random.randint(2016, 2021)}"
    }

def generate_experience():
    titles = ['Data Scientist', 'Junior Data Scientist', 'Senior Data Scientist', 'Data Analyst']
    experience = []
    for _ in range(random.randint(2, 5)):
        experience.append({
            "Job Title": random.choice(titles),
            "Company": fake.company(),
            "Years": f"{random.randint(2016, 2019)} - {random.randint(2020, 2023)}"
        })
    return experience

def generate_skills():
    skills = ['Python', 'R', 'SQL', 'Machine Learning', 'Deep Learning', 'Data Visualization', 'Data Wrangling', 'Big Data', 'Statistics', 'TensorFlow', 'PyTorch']
    return random.sample(skills, 5)

def generate_projects():
    projects = []
    for _ in range(random.randint(2, 4)):
        projects.append({
            "Title": fake.sentence(nb_words=6),
            "Description": fake.text(max_nb_chars=200)
        })
    return projects

def generate_resume():
    resume = {
        "Personal Information": generate_personal_info(),
        "Education": generate_education(),
        "Work Experience": generate_experience(),
        "Skills": generate_skills(),
        "Projects": generate_projects(),
    }
    
    return resume

def save_pdf(html_content, file_name='resume.pdf'):
    HTML(string=html_content).write_pdf(file_name)



if __name__ == "__main__":
    num_resumes = input("How many resumes would you like to generate? ")
    for _ in range(int(num_resumes)):
        fake_resume = generate_resume()
        html_content = '<!DOCTYPE html><html><head><title>Resume</title></head><body>'
        html_content += '<h1>Resume</h1>'

        for section, content in fake_resume.items():
            html_content += f'<h2>{section}</h2>'
            if isinstance(content, list):
                if section == "Skills":
                    html_content += "<ul>"
                    for item in content:
                        html_content += f"<li>{item}</li>"
                    html_content += "</ul>"
                else:
                    for item in content:
                        for key, value in item.items():
                            html_content += f'<p><strong>{key}:</strong> {value}</p>'
                        html_content += '<hr>'
            else:
                for key, value in content.items():
                    html_content += f'<p><strong>{key}:</strong> {value}</p>'
            
        html_content += '</body></html>'
        save_pdf(html_content, file_name=f"resumes/{uuid4()}.pdf")

