import os

# Create a new directory for our project
def create_project_dir(project_name):
    # Use os.mkdir to create a new directory
    os.mkdir(project_name)

# Navigate into the project directory
def navigate_to_project(project_name):
    # Use os.chdir to change the current working directory
    os.chdir(project_name)

# Create the 'hello_world' file and print 'Hello, World!'
def main():
    # Create the project directory
    project_name = 'hello_world_project'
    create_project_dir(project_name)
    
    # Navigate into the project directory
    navigate_to_project(project_name)
    
    # Create the 'hello_world.py' file
    with open('hello_world.py', 'w') as f:
        # Write 'Hello, World!' to the file
        f.write('print("Hello, World!")\n')

# Run the main function
if __name__ == '__main__':
    main()