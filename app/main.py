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

                header_end = data.index(b'\x00')
                header = data[:header_end]
                content = data[header_end + 1:]

                pos = 0
                entries = []
                while pos < len(content):
                    null_pos = content.index(b'\x00', pos)

                    mode_name = content[pos:null_pos]
                    mode, name = mode_name.split(b' ', 1)

                    pos = null_pos + 1 + 20
                    entries.append(name.decode())

                for entry in entries:
                    print(entry)
        else:
            sha = sys.argv[2]
            with open(f".git/objects/{sha[:2]}/{sha[2:]}", "rb") as f:
                data = zlib.decompress(f.read())

                header_end = data.index(b'\x00')
                content = data[header_end + 1:]

                pos = 0
                while pos < len(content):
                    null_pos = content.index(b'\x00', pos)
                    mode_name = content[pos:null_pos]
                    mode, name = mode_name.split(b' ', 1)

                    sha_bytes = content[null_pos + 1:null_pos + 21]
                    sha_hex = sha_bytes.hex()

                    entry_type = "tree" if mode == b"40000" else "blob"

                    print(f"{mode.decode().zfill(6)} {entry_type} {sha_hex}    {name.decode()}")
                    pos = null_pos + 1 + 20

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
