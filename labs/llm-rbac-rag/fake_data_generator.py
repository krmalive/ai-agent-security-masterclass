import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API
API_KEY = os.getenv("OPENAI_API_KEY")  
BASE_URL = os.getenv("OPENAI_API_BASE") 


def create_directory_structure():
    """Create necessary directories for documentation"""
    base_path = Path("docs")
    engineering_path = base_path / "engineering"
    sales_path = base_path / "sales"

    # Create directories if they don't exist
    for path in [base_path, engineering_path, sales_path]:
        path.mkdir(exist_ok=True)

    return engineering_path, sales_path

def generate_content(prompt):
    """Generate content"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    
    url = f"{BASE_URL}/chat/completions"

    payload = {
        "model": "openai/gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": "You are a technical writer creating internal documentation for AcmeCorp."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code}, {response.text}")

    data = response.json()
    
    return data["choices"][0]["message"]["content"]


def generate_docs(path, docs):
    """Generate documentation files"""
    for filename, prompt in docs.items():
        content = generate_content(prompt)
        with open(path / filename, 'w') as f:
            f.write(content)

def main():
    if not API_KEY or not BASE_URL:
        print("Error: API key or Base URL not set")
        return

    print("Creating directory structure...")
    engineering_path, sales_path = create_directory_structure()

    print("Generating engineering documentation...")
    generate_docs(engineering_path, {
        "coding_standards.md": "Write detailed coding standards and best practices for AcmeCorp's engineering team.",
        "architecture.md": "Write a technical architecture document for AcmeCorp's main product.",
        "deployment_process.md": "Write deployment guidelines and processes for AcmeCorp's engineering team.",
        "security_guidelines.md": "Write security guidelines and protocols for AcmeCorp's engineering team."
    })

    print("Generating sales documentation...")
    generate_docs(sales_path, {
        "sales_playbook.md": "Write a comprehensive sales playbook for AcmeCorp's sales team.",
        "pricing_strategy.md": "Write pricing strategies and guidelines for AcmeCorp's products.",
        "customer_personas.md": "Write detailed customer personas for AcmeCorp's target market.",
        "sales_process.md": "Write the step-by-step sales process for AcmeCorp's sales team."
    })

    print("Documentation generation complete!")

if __name__ == "__main__":
    main()
