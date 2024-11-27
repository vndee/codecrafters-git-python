import sys
import os
import zlib
import hashlib


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

            header = f"blob {len(data)}\x00"
            store = header.encode() + data
            sha = hashlib.sha1(store).hexdigest()
            os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
                f.write(zlib.compress(store))

            print(sha)

    elif command == "ls-tree":
        if sys.argv[2] == "--name-only":
            sha = sys.argv[3]
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
                data = zlib.decompress(f.read())

                parts = data.split(b"\x00", 2)
                _type, _size = parts[0].decode().split(" ")
                _content = parts[1].decode()
                print(_content)

                for line in _content.split("\n"):
                    if not line:
                        continue
                    mode, type, sha, name = line.split("\t")
                    print(name)
        else:
            sha = sys.argv[2]
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
                data = zlib.decompress(f.read())

                parts = data.split(b"\x00", 2)
                _type, _size = parts[0].decode().split(" ")
                _content = parts[-1].decode()

                for line in _content.split("\n"):
                    if not line:
                        continue
                    mode, type, sha, name = line.split("\t")
                    print(f"{mode} {type} {sha} {name}")

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
