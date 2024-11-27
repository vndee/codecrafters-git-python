import sys
import os
import zlib


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
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
