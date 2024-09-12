import os
import subprocess
import yaml
import re
import sys
import sqlite3
import string

def create_filter():
    # Create a set of all ASCII characters
    ascii_chars = set(chr(i) for i in range(128))

    # Create a set of control characters (as per POSIX [:cntrl:])
    control_chars = set(chr(i) for i in range(32)) | {chr(127)}

    # Create a set of characters to keep
    chars_to_keep = ascii_chars - control_chars - {'\t'} | {'\n'}

    # Create a regex pattern that matches any character not in chars_to_keep
    pattern = f'[^{"".join(re.escape(c) for c in chars_to_keep)}]'

    return re.compile(pattern)

# Create the filter
char_filter = create_filter()

def filter_string(s):
    return char_filter.sub('', s)

def run_git_log(repo_directory):
    os.chdir(repo_directory)
    git_command = [
        'git', '--no-pager', 'log',
        '--pretty=format:---\ncommit: "%H"\nmessage: |\n  %s'
    ]

    result = subprocess.run(git_command, capture_output=True, text=True)
    output = result.stdout

    # Apply the filter
    output = filter_string(output)

    return output

def parse_yaml(yaml_str):
    try:
        documents = yaml.safe_load_all(yaml_str)
        return list(documents)
    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}")
        print("Failing YAML part:")
        print(yaml_str)
        sys.exit(1)

def extract_package_info(message):
    pattern = r'(\w+(?:-\w+)*): ([\w.]+) -> ([\w.]+)'
    matches = re.findall(pattern, message)
    return matches

def process_commits(commits):
    package_info = []
    for commit in commits:
        commit_hash = commit['commit']
        message = commit['message']

        packages = extract_package_info(message)
        for package, previous_version, new_version in packages:
            package_info.append({
                'package': package,
                'previous_version': previous_version,
                'new_version': new_version,
                'commit': commit_hash
            })

    return package_info

def create_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS package_versions (
        id INTEGER PRIMARY KEY,
        package TEXT,
        previous_version TEXT,
        version TEXT,
        commit_hash TEXT,
        UNIQUE(package, previous_version, version, commit_hash)
    )
    ''')

    conn.commit()
    return conn

def insert_package_info(conn, package_info):
    cursor = conn.cursor()
    for info in package_info:
        cursor.execute('''
        INSERT OR IGNORE INTO package_versions (package, previous_version, version, commit_hash)
        VALUES (?, ?, ?, ?)
        ''', (info['package'], info['previous_version'], info['new_version'], info['commit']))

    conn.commit()

def main():
    repo_directory = './nixpkgs'  # Configure this
    script_directory = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_directory, 'package_versions.db')

    git_output = run_git_log(repo_directory)
    commits = parse_yaml(git_output)
    package_info = process_commits(commits)

    conn = create_database(db_path)
    insert_package_info(conn, package_info)
    conn.close()

    print(f"Data has been written to {db_path}")

if __name__ == "__main__":
    main()
