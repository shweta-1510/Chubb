"""
Quick setup script for the Health Monitor application.
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a shell command and display results."""
    print(f"\n{'='*60}")
    print(f"📌 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            text=True,
            capture_output=True
        )
        print(f"✅ {description} - SUCCESS")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Main setup function."""
    print("\n" + "="*60)
    print("🏥 Environment Health Check Monitor - Setup Script")
    print("="*60)
    
    # Check Python version
    print(f"\n🐍 Python Version: {sys.version}")
    if sys.version_info < (3, 11):
        print("⚠️  WARNING: Python 3.11+ is recommended")
    
    # Check if .env exists
    env_file = Path(".env")
    if not env_file.exists():
        print("\n📝 Creating .env file from template...")
        env_example = Path(".env.example")
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            print("✅ .env file created. Please update it with your configuration.")
        else:
            print("⚠️  .env.example not found")
    
    # Create necessary directories
    print("\n📁 Creating directories...")
    directories = ["logs", "reports"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"  ✅ {directory}/")
    
    # Install dependencies
    install = input("\n❓ Install Python dependencies? (yes/no): ")
    if install.lower() in ['yes', 'y']:
        run_command(
            f"{sys.executable} -m pip install --upgrade pip",
            "Upgrading pip"
        )
        run_command(
            f"{sys.executable} -m pip install -r requirements.txt",
            "Installing dependencies"
        )
    
    # Initialize database
    init_db = input("\n❓ Initialize database? (yes/no): ")
    if init_db.lower() in ['yes', 'y']:
        run_command(
            f"{sys.executable} init_db.py",
            "Initializing database"
        )
    
    # Display next steps
    print("\n" + "="*60)
    print("🎉 Setup Complete!")
    print("="*60)
    print("\n📋 Next Steps:")
    print("  1. Update .env file with your configuration")
    print("  2. Ensure PostgreSQL is running")
    print("  3. Run the application:")
    print(f"     {sys.executable} -m streamlit run app/main.py")
    print("\n  Or use Docker:")
    print("     docker-compose up -d")
    print("\n  Access the app at: http://localhost:8501")
    print("="*60)


if __name__ == "__main__":
    main()
