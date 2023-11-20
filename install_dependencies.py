import subprocess

def install_dependencies():
    try:
        subprocess.check_call(["pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print("Error: Failed to install dependencies.", e)

if __name__ == "__main__":
    install_dependencies()
