import sys
import os
import zlib
import time
import hashlib
from typing import List, Tuple


def hash_object(data: bytes, obj_type: str) -> str:
    """
    Hash an object and store it in the objects directory.
    Returns the SHA1 hash of the object.
    """
    # Prepare the object store data with header
    store = f"{obj_type} {len(data)}\x00".encode() + data

    # Calculate SHA1 hash
    sha = hashlib.sha1(store).hexdigest()

    # Store the object
    path = f".git/objects/{sha[:2]}"
    os.makedirs(path, exist_ok=True)
    with open(f"{path}/{sha[2:]}", "wb") as f:
        f.write(zlib.compress(store))

    return sha


def create_tree_entry(mode: str, name: str, sha: str) -> bytes:
    """Create a single tree entry in the correct format."""
    # Convert the hex SHA to bytes
    sha_bytes = bytes.fromhex(sha)
    return f"{mode} {name}\x00".encode() + sha_bytes


def write_tree_recursive(directory: str) -> str:
    """
    Recursively create tree objects for a directory and its subdirectories.
    Returns the SHA1 hash of the tree object.
    """
    entries: List[Tuple[str, str, str]] = []  # List of (mode, name, sha)

    # Iterate through directory entries in sorted order
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)

        # Skip .git directory
        if name == '.git':
            continue

        # Get file stats
        stats = os.lstat(path)

        if os.path.isfile(path):
            # Regular file
            mode = "100644"
            if stats.st_mode & 0o111:  # Check if executable
                mode = "100755"

            # Hash the file content
            with open(path, 'rb') as f:
                file_sha = hash_object(f.read(), "blob")
            entries.append((mode, name, file_sha))

        elif os.path.isdir(path):
            # Directory - recursively create tree
            tree_sha = write_tree_recursive(path)
            entries.append(("40000", name, tree_sha))

    # Create tree content
    tree_content = b""
    for mode, name, sha in entries:
        tree_content += create_tree_entry(mode, name, sha)

    # Hash and store the tree object
    return hash_object(tree_content, "tree")


def create_commit(tree_sha: str, parent_sha: str, message: str) -> str:
    """
    Create a commit object with the given tree, parent, and message.
    Returns the SHA1 hash of the commit.
    """
    # Get current timestamp
    timestamp = int(time.time())
    # Use Pacific timezone (-0700) as an example
    timezone = "-0700"

    # Hardcode author/committer information
    author = "Duy Huynh <vndee.huynh@gmail.com>"
    committer = "Duy Huynh <vndee.huynh@gmail.com>"

    # Build commit content
    content = [
        f"tree {tree_sha}",
        f"parent {parent_sha}",
        f"author {author} {timestamp} {timezone}",
        f"committer {committer} {timestamp} {timezone}",
        "",  # Empty line before message
        message
    ]

    # Join with Unix-style newlines
    commit_data = "\n".join(content).encode()

    # Hash and store the commit object
    return hash_object(commit_data, "commit")


def main():
    print("Logs from your program will appear here!", file=sys.stderr)

    command = sys.argv[1]
    if command == "init":
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")

    elif command == "cat-file":
        sub_command = sys.argv[2]
        sha = sys.argv[3]
        with open(f".git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
            data = zlib.decompress(f.read())

            parts = data.split(b"\x00", 2)
            _type, _size = parts[0].decode().split(" ")
            _content = parts[-1].decode()

            if sub_command == "-p":
                print(_content, end="")

    elif command == "hash-object":
        if sys.argv[2] == "-w":
            if sys.argv[3] == "--stdin":
                data = sys.stdin.buffer.read()
            else:
                with open(sys.argv[3], "rb") as f:
                    data = f.read()

            print(hash_object(data, "blob"))

    elif command == "ls-tree":
        if sys.argv[2] == "--name-only":
            sha = sys.argv[3]
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
                data = zlib.decompress(f.read())

                # Split header from content
                header_end = data.index(b'\x00')
                content = data[header_end + 1:]

                # Process each entry
                pos = 0
                entries = []
                while pos < len(content):
                    # Find the end of the mode+name portion (marked by null byte)
                    null_pos = content.index(b'\x00', pos)

                    # Extract mode and name
                    mode_name = content[pos:null_pos]
                    mode, name = mode_name.split(b' ', 1)

                    # Skip past the SHA (20 bytes) and prepare for next entry
                    pos = null_pos + 1 + 20

                    entries.append(name.decode())

                # Print entries (they're already sorted in the tree object)
                for entry in entries:
                    print(entry)

    elif command == "write-tree":
        # Write tree starting from current directory
        tree_sha = write_tree_recursive(".")
        print(tree_sha)

    elif command == "commit-tree":
        tree_sha = sys.argv[2]

        i, parent_sha, message = 3, None, ""
        while i < len(sys.argv):
            if sys.argv[i] == "-p":
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "-m":
                message = sys.argv[i + 1]
                i += 2
            else:
                raise RuntimeError(f"Unknown argument {sys.argv[i]}")

        commit_sha = create_commit(tree_sha, parent_sha, message)
        print(commit_sha)

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
