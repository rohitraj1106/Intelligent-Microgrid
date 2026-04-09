import os
import glob

def clean_state():
    print("🧹 Sweeping stale microgrid databases...")
    project_root = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(project_root, "data", "edge", "*.db"),
        os.path.join(project_root, "data", "edge", "*.db-shm"),
        os.path.join(project_root, "data", "edge", "*.db-wal"),
        os.path.join(project_root, "marketplace.db"),
        os.path.join(project_root, "marketplace.db-shm"),
        os.path.join(project_root, "marketplace.db-wal"),
    ]
    count = 0
    for pattern in patterns:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                count += 1
            except OSError:
                pass
    print(f"✅ Removed {count} old sqlite files! Environment is fresh.")

if __name__ == "__main__":
    clean_state()
