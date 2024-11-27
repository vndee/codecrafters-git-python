import sys
import os


def find_solutions():
    # Target sum before multiplying by 5
    target = 25950000 // 5  # = 5190000

    # Calculate reasonable ranges for each variable
    max_x = target // 582 + 1
    max_y = target // 776 + 1
    max_z = target // 388 + 1

    # Iterate through ranges starting from 1
    for x in range(1000, max_x + 1):
        remain_x = target - (582 * x)
        if remain_x < 0:
            break

        for y in range(1000, max_y + 1):
            remain_y = remain_x - (776 * y)
            if remain_y < 0:
                break

            for z in range(1000, max_z + 1):
                remain_z = remain_y - (388 * z)
                if remain_z < 0:
                    break

                # Check if remaining amount is perfectly divisible by 620
                if remain_z % 620 == 0:
                    t = remain_z // 620
                    if t >= 1:  # Ensure t is at least 1
                        # Verify solution
                        if 5 * (582 * x + 776 * y + 388 * z + 620 * t) == 25950000:
                            print(f"Solution found: x={x}, y={y}, z={z}, t={t}")


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
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    find_solutions()