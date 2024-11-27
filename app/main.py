import sys
import os
import zlib
import hashlib
import time


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
    author = "Code Challenger <challenger@example.com>"
    committer = "Code Challenger <challenger@example.com>"

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

    elif command == "commit-tree":
        tree_sha = sys.argv[2]
        # Parse command line arguments
        i = 3
        parent_sha = None
        message = None
        while i < len(sys.argv):
            if sys.argv[i] == "-p":
                parent_sha = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "-m":
                message = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        if tree_sha and parent_sha and message:
            commit_sha = create_commit(tree_sha, parent_sha, message)
            print(commit_sha)
        else:
            raise RuntimeError("Missing required arguments for commit-tree")

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()