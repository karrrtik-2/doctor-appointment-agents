from setuptools import find_packages, setup
from typing import List


def get_requirements() -> List[str]:
    try:
        with open('requirements.txt', 'r') as file:
            requirement_list = [
                line.strip() for line in file.readlines()
                if line.strip()
                and not line.strip().startswith('#')
                and line.strip() != '-e .'
            ]
        return requirement_list
    except FileNotFoundError:
        print("requirements.txt file not found. Make sure it exists!")
        return []

with open("README.md", "r", encoding="utf-8") as readme_file:
    long_description = readme_file.read()


setup(
    name="doctor-appointment-ai-platform",
    version="1.0.0",
    description="Enterprise AI orchestration platform for doctor appointment management with LangSmith observability",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Project Contributors",
    packages=find_packages(),
    install_requires=get_requirements(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "platform-server=run_server:main",
            "platform-eval=run_evaluation:main",
        ],
    },
)
