import sys
import os
import zlib
import time
import struct
import hashlib
import urllib.request
from typing import List, Tuple, Dict
from urllib.parse import urlparse


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
    commit_data = ("\n".join(content) + "\n").encode()

    # Hash and store the commit object
    return hash_object(commit_data, "commit")


def convert_github_url(url: str) -> str:
    """Convert a GitHub URL to a Git URL."""
    parsed = urlparse(url)
    path = parsed.path

    if not path.endswith(".git"):
        path += ".git"

    return f"{parsed.scheme}://{parsed.netloc}{path}"


def get_refs(url: str) -> Tuple[Dict[str, bool | str], List[Tuple[str, str]]]:
    """Fetch refs using Smart HTTP protocol."""
    url = f"{url}/info/refs?service=git-upload-pack"

    req = urllib.request.Request(url)
    refs, caps = [], {}
    with urllib.request.urlopen(req) as response:
        lines = response.read().split(b"\n")

    # parse capabilities
    cap_bytes = lines[1].split(b'\x00')[1]
    for cap in cap_bytes.split(b' '):
        if cap.startswith(b"symref=HEAD:"):
            caps["default_branch"] = cap.split(b":")[1].decode()
        else:
            caps[cap.decode()] = True

    # parse refs
    for line in lines[2:]:
        if line.startswith(b"0000"):
            break

        sha, ref_name = line.decode().split(" ")  # each ref line is formatted as: "<sha>\x00ref_name"
        refs.append((sha[4:], ref_name))  # remove the length prefix that git uses

    return caps, refs


def download_packfile(url: str, want_ref: str) -> bytes:
    """Download a packfile using Git protocol v2."""
    url = f"{url}/git-upload-pack"

    # Create the request body with proper packet format
    body = (
            b"0011command=fetch0001000fno-progress"
            + f"0032want {want_ref}\n".encode()
            + b"0009done\n0000"
    )

    headers = {
        "Content-Type": "application/x-git-upload-pack-request",
        "Git-Protocol": "version=2"
    }

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = response.read()

    # Parse the response into lines
    pack_lines = []

    while data:
        # Read packet length (4 hex digits)
        line_len = int(data[:4], 16)
        if line_len == 0:
            break
        pack_lines.append(data[4:line_len])
        data = data[line_len:]

    # Combine all lines after the first one (skipping header)
    # and remove the packet type byte from each line
    return b"".join(l[1:] for l in pack_lines[1:])


def write_packfile(data: bytes, target_dir: str) -> None:
    """Parse and write a packfile to the target directory."""
    git_dir = os.path.join(target_dir, ".git")

    def next_size_type(bs: bytes) -> Tuple[str, int, bytes]:
        """Parse the type and size of the next object."""
        ty = (bs[0] & 0b01110000) >> 4
        type_map = {
            1: "commit",
            2: "tree",
            3: "blob",
            4: "tag",
            6: "ofs_delta",
            7: "ref_delta"
        }
        ty = type_map.get(ty, "unknown")

        size = bs[0] & 0b00001111
        i = 1
        shift = 4
        while bs[i - 1] & 0b10000000:
            size |= (bs[i] & 0b01111111) << shift
            shift += 7
            i += 1
        return ty, size, bs[i:]

    def next_size(bs: bytes) -> Tuple[int, bytes]:
        """Parse just the size field."""
        size = bs[0] & 0b01111111
        i = 1
        shift = 7
        while bs[i - 1] & 0b10000000:
            size |= (bs[i] & 0b01111111) << shift
            shift += 7
            i += 1
        return size, bs[i:]

    # Skip pack header and version (8 bytes)
    data = data[8:]

    # Read number of objects
    n_objects = struct.unpack("!I", data[:4])[0]
    data = data[4:]

    print(f"Processing {n_objects} objects")

    # First pass: collect all objects and their data
    objects = []  # List to store (type, content, base_sha) tuples
    remaining_data = data

    for _ in range(n_objects):
        obj_type, _, remaining_data = next_size_type(remaining_data)

        if obj_type in ["commit", "tree", "blob", "tag"]:
            # Direct object - just decompress
            decomp = zlib.decompressobj()
            content = decomp.decompress(remaining_data)
            remaining_data = decomp.unused_data
            objects.append((obj_type, content, None))

        elif obj_type == "ref_delta":
            # Reference delta object - store for second pass
            base_sha = remaining_data[:20].hex()
            remaining_data = remaining_data[20:]

            # Decompress delta data
            decomp = zlib.decompressobj()
            delta = decomp.decompress(remaining_data)
            remaining_data = decomp.unused_data

            objects.append(("ref_delta", delta, base_sha))

    # Second pass: process objects in order
    processed_objects = set()  # Keep track of processed objects

    def process_object(obj_data: Tuple[str, bytes, str | None]) -> None:
        obj_type, content, base_sha = obj_data

        if obj_type != "ref_delta":
            # Direct object
            store = f"{obj_type} {len(content)}\x00".encode() + content
            sha = hashlib.sha1(store).hexdigest()

            # Write to objects directory
            path = os.path.join(git_dir, "objects", sha[:2])
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, sha[2:]), "wb") as f:
                f.write(zlib.compress(store))

            processed_objects.add(sha)
            return sha

        else:
            # Delta object
            if base_sha not in processed_objects:
                # Find and process base object first
                for obj in objects:
                    if obj[0] != "ref_delta" and hashlib.sha1(
                            f"{obj[0]} {len(obj[1])}\x00".encode() + obj[1]).hexdigest() == base_sha:
                        process_object(obj)
                        break

            # Read base object
            with open(f"{git_dir}/objects/{base_sha[:2]}/{base_sha[2:]}", "rb") as f:
                base_content = zlib.decompress(f.read())
            base_type = base_content.split(b' ')[0].decode()
            base_content = base_content.split(b'\x00', 1)[1]

            # Skip size headers in delta
            delta = content
            _, delta = next_size(delta)  # base size
            _, delta = next_size(delta)  # target size

            # Apply delta instructions
            result = b""
            while delta:
                cmd = delta[0]
                if cmd & 0b10000000:  # Copy command
                    pos = 1
                    offset = 0
                    size = 0

                    # Read offset
                    for i in range(4):
                        if cmd & (1 << i):
                            offset |= delta[pos] << (i * 8)
                            pos += 1

                    # Read size
                    for i in range(3):
                        if cmd & (1 << (4 + i)):
                            size |= delta[pos] << (i * 8)
                            pos += 1

                    result += base_content[offset:offset + size]
                    delta = delta[pos:]
                else:  # Insert command
                    size = cmd
                    result += delta[1:size + 1]
                    delta = delta[size + 1:]

            # Store the resulting object
            store = f"{base_type} {len(result)}\x00".encode() + result
            sha = hashlib.sha1(store).hexdigest()

            path = os.path.join(git_dir, "objects", sha[:2])
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, sha[2:]), "wb") as f:
                f.write(zlib.compress(store))

            processed_objects.add(sha)
            return sha

    for obj in objects:
        process_object(obj)


def read_object(path: str, sha: str) -> Tuple[str, bytes]:
    """Read a Git object and return its type and content."""
    with open(f"{path}/.git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
        data = zlib.decompress(f.read())

    # Split into header and content
    null_pos = data.index(b'\x00')
    header = data[:null_pos]
    content = data[null_pos + 1:]

    # Parse type and size from header
    obj_type = header.split(b' ')[0].decode()
    return obj_type, content


def render_tree(repo_path: str, dir_path: str, sha: str):
    """
    Recursively render a Git tree object to the filesystem.
    """
    print(f"Rendering tree {sha} to {dir_path}")
    os.makedirs(dir_path, exist_ok=True)
    _, tree_content = read_object(repo_path, sha)

    # Process each entry in the tree
    while tree_content:
        # Split mode and remaining content
        mode, tree_content = tree_content.split(b' ', 1)
        # Split name and remaining content
        name, tree_content = tree_content.split(b'\x00', 1)
        # Get object SHA (next 20 bytes)
        entry_sha = tree_content[:20].hex()
        tree_content = tree_content[20:]

        # Create full path for this entry
        entry_path = os.path.join(dir_path, name.decode())

        # Handle based on mode
        if mode == b'40000':  # Directory
            # Recursively render subtree
            render_tree(repo_path, entry_path, entry_sha)
        elif mode == b'100644':  # Regular file
            # Read and write file content
            _, content = read_object(repo_path, entry_sha)
            with open(entry_path, 'wb') as f:
                f.write(content)
        else:
            raise RuntimeError(f"Unsupported mode: {mode}")


def main():
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

                header_end = data.index(b'\x00')
                content = data[header_end + 1:]

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

    elif command == "clone":
        # Get repository URL and directory
        remote = sys.argv[2]
        if len(sys.argv) == 4:
            local = sys.argv[3]
        else:
            parsed = urlparse(remote)
            local = parsed.path.split("/")[-1].replace(".git", "")

        # Initialize repository
        os.makedirs(local)
        os.makedirs(os.path.join(local, ".git", "objects"))
        os.makedirs(os.path.join(local, ".git", "refs"))

        print(f"Cloning {remote} to {local}")

        # Fetch refs
        caps, refs = get_refs(remote)
        default_branch = caps.get("default_branch", "refs/heads/main")

        default_ref_sha = None
        for sha, ref in refs:
            if ref == default_branch:
                default_ref_sha = sha
                break

        if default_ref_sha is None:
            raise RuntimeError(f"Default branch not found: {default_branch}")

        # Download and process packfile
        print(f"Downloading {default_branch} ({default_ref_sha})")
        packfile = download_packfile(remote, default_ref_sha)
        write_packfile(packfile, local)

        # Write HEAD ref
        with open(os.path.join(local, ".git", "HEAD"), "w") as f:
            f.write(f"ref: {default_branch}\n")

        # Write branch ref
        ref_dir = os.path.join(local, ".git", os.path.dirname(default_branch))
        os.makedirs(ref_dir, exist_ok=True)
        with open(os.path.join(local, ".git", default_branch), "w") as f:
            f.write(f"{default_ref_sha}\n")

        # Read the commit and tree
        _, commit_content = read_object(local, default_ref_sha)
        tree_sha = commit_content[5:45].decode()  # Extract tree SHA from commit

        # Render the tree to the working directory
        render_tree(local, local, tree_sha)

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
