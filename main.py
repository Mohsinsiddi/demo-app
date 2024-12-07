import os
import shutil

def log_folder_contents(source_paths, output_file):
    with open(output_file, 'w', encoding='utf-8') as log_file:
        for path in source_paths:
            log_file.write(f"Contents of {path}:\n")
            log_file.write("=" * 50 + "\n\n")
            
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, path)
                    
                    log_file.write(f"File: {relative_path}\n")
                    log_file.write("-" * 30 + "\n")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            log_file.write(content)
                    except UnicodeDecodeError:
                        log_file.write("(Binary or non-text file)\n")
                    except Exception as read_error:
                        log_file.write(f"Error reading file: {read_error}\n")
                    
                    log_file.write("\n\n")

# Specify source paths
source_paths = [
    'packages/valory/contracts/erc20',
    'packages/valory/contracts/token_reader',
    'packages/valory/skills/learning_abci'
]

# Output file
output_file = 'folder_contents_log.txt'

# Execute the function
log_folder_contents(source_paths, output_file)
print(f"File contents logged in {output_file}")