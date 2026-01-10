#!/usr/bin/env python3
"""
verify_setup.py - Pre-deployment verification script for thermal-report

Checks that your local environment is ready to deploy to Google Cloud.
Run this before starting Phase 5 of the GCS_Setup_Guide.md.

Usage:
    python verify_setup.py
"""

import subprocess
import sys
import os
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def check(name, condition, error_msg=""):
    """Print a check result."""
    status = f"{Colors.GREEN}✓{Colors.RESET}" if condition else f"{Colors.RED}✗{Colors.RESET}"
    print(f"  {status} {name}")
    if not condition and error_msg:
        print(f"    {Colors.YELLOW}→ {error_msg}{Colors.RESET}")
    return condition

def run_command(cmd):
    """Run a command and return (success, output, error)."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def section(title):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}▶ {title}{Colors.RESET}")

def main():
    print(f"{Colors.BOLD}Thermal Report - GCS Deployment Verification{Colors.RESET}\n")

    all_ok = True

    # ===== System Tools =====
    section("System Tools")
    
    success, _, _ = run_command("gcloud --version")
    all_ok &= check("gcloud CLI installed", success, "Install from https://cloud.google.com/sdk/docs/install")
    
    success, _, _ = run_command("docker --version")
    all_ok &= check("Docker installed", success, "Install from https://www.docker.com/get-started")
    
    success, _, _ = run_command("git --version")
    all_ok &= check("Git installed", success, "Install from https://git-scm.com")
    
    success, _, _ = run_command("python --version")
    all_ok &= check("Python 3 installed", success, "Install Python 3.9 or later")

    # ===== Project Structure =====
    section("Project Structure")
    
    repo_root = Path.cwd()
    
    files_to_check = {
        "app.py": "Flask application entry point",
        "requirements.txt": "Python dependencies",
        "Dockerfile": "Docker build configuration",
        ".gitignore": "Git ignore rules",
        "README.md": "Project documentation",
    }
    
    for filename, description in files_to_check.items():
        filepath = repo_root / filename
        all_ok &= check(f"{filename}", filepath.exists(), f"Missing: {description}")

    # ===== Flask Configuration =====
    section("Flask Configuration")
    
    try:
        with open("app.py", "r") as f:
            app_content = f.read()
    except FileNotFoundError:
        print(f"  {Colors.RED}✗ Cannot read app.py{Colors.RESET}")
        app_content = ""
    
    # Check for port 8080
    has_port_8080 = "8080" in app_content or "PORT" in app_content
    all_ok &= check(
        "Configured to use port 8080 or PORT env var",
        has_port_8080,
        "Update app.py: use port = int(os.environ.get('PORT', 8080))"
    )
    
    # Check for 0.0.0.0 binding
    has_0_0_0_0 = "0.0.0.0" in app_content
    all_ok &= check(
        "Configured to bind to 0.0.0.0",
        has_0_0_0_0,
        "Update app.py: use host='0.0.0.0' (not 127.0.0.1)"
    )

    # ===== Dependencies =====
    section("Python Dependencies")
    
    try:
        with open("requirements.txt", "r") as f:
            req_content = f.read().lower()
    except FileNotFoundError:
        print(f"  {Colors.RED}✗ Cannot read requirements.txt{Colors.RESET}")
        req_content = ""
    
    required_packages = {
        "flask": "Flask web framework",
        "gunicorn": "Production WSGI server",
        "pillow": "Image processing (PIL)",
        "numpy": "Numerical computing",
    }
    
    for pkg, desc in required_packages.items():
        has_pkg = pkg.lower() in req_content
        all_ok &= check(
            f"{pkg}",
            has_pkg,
            f"Add to requirements.txt: {desc}"
        )
    
    # Check for Drive API packages
    optional_packages = {
        "google-auth-oauthlib": "Google OAuth (for Drive API)",
        "google-api-python-client": "Google API client",
    }
    
    for pkg, desc in optional_packages.items():
        has_pkg = pkg.lower() in req_content
        status = "✓" if has_pkg else "⚠"
        if has_pkg:
            print(f"  {Colors.GREEN}{status}{Colors.RESET} {pkg} (Google Drive support)")
        else:
            print(f"  {Colors.YELLOW}{status}{Colors.RESET} {pkg} (optional, for Drive API)")

    # ===== Docker Configuration =====
    section("Docker Configuration")
    
    try:
        with open("Dockerfile", "r") as f:
            docker_content = f.read()
    except FileNotFoundError:
        print(f"  {Colors.RED}✗ Cannot read Dockerfile{Colors.RESET}")
        docker_content = ""
    
    has_exiftool = "exiftool" in docker_content.lower()
    all_ok &= check(
        "Dockerfile installs exiftool",
        has_exiftool,
        "Add to Dockerfile: RUN apt-get install -y exiftool"
    )
    
    has_gunicorn = "gunicorn" in docker_content.lower()
    all_ok &= check(
        "Dockerfile uses gunicorn",
        has_gunicorn,
        "Add CMD: exec gunicorn --bind :$PORT --workers 1 app:app"
    )
    
    has_port_env = "PORT" in docker_content
    all_ok &= check(
        "Dockerfile references PORT env var",
        has_port_env,
        "Ensure: --bind :$PORT and ENV PORT=8080"
    )
    
    # ===== GCP Authentication =====
    section("GCP Authentication")
    
    success, output, error = run_command("gcloud config get-value project")
    has_project = success and output and output != "None"
    
    if has_project:
        print(f"  {Colors.GREEN}✓ GCP project configured: {output}{Colors.RESET}")
    else:
        print(f"  {Colors.RED}✗ GCP project not configured{Colors.RESET}")
        print(f"    {Colors.YELLOW}→ Run: gcloud auth login{Colors.RESET}")
        print(f"    {Colors.YELLOW}→ Then: gcloud config set project YOUR_PROJECT_ID{Colors.RESET}")
        all_ok = False
    
    success, account, _ = run_command("gcloud config get-value account")
    if success and account and account != "None":
        print(f"  {Colors.GREEN}✓ GCP account: {account}{Colors.RESET}")
    else:
        print(f"  {Colors.RED}✗ No GCP account logged in{Colors.RESET}")
        all_ok = False

    # ===== Summary =====
    section("Summary")
    
    if all_ok:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All checks passed! You're ready to deploy.{Colors.RESET}")
        print(f"\nNext steps:")
        print(f"  1. Review GCS_Setup_Guide.md")
        print(f"  2. Follow Phase 2: Share Drive folder with service account")
        print(f"  3. Follow Phase 7: Build and deploy to Cloud Run")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Some checks failed. Please fix the items above and try again.{Colors.RESET}")
        print(f"\nRefer to GCS_Setup_Guide.md Phase 4 for detailed instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
