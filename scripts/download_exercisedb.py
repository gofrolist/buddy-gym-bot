#!/usr/bin/env python3
"""
Script to clone ExerciseDB repository and copy exercises data.
This eliminates the need for external API calls during plan generation.
"""

import shutil
import subprocess
from pathlib import Path

EXERCISEDB_REPO = "https://github.com/ExerciseDB/exercisedb-api.git"
REPO_DIR = Path("temp_exercisedb_repo")
DATA_DIR = REPO_DIR / "src" / "data"
MEDIA_DIR = REPO_DIR / "media"
OUTPUT_DIR = Path("src/buddy_gym_bot/data")

def download_exercisedb_data() -> dict[str, list[Path] | Path] | None:
    """Clone ExerciseDB repository and extract all data."""
    print("Cloning ExerciseDB repository...")

    try:
        # Clean up any existing repo directory
        if REPO_DIR.exists():
            shutil.rmtree(REPO_DIR)
            print("Cleaned up existing repository directory")

        # Clone the repository
        print(f"Cloning {EXERCISEDB_REPO}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", EXERCISEDB_REPO, str(REPO_DIR)],
            capture_output=True,
            text=True,
            check=True
        )
        print("Repository cloned successfully")

        # Check what data files are available
        data_files: list[Path] = list(DATA_DIR.glob("*.json"))
        print(f"Found {len(data_files)} data files: {[f.name for f in data_files]}")

        # Check media files
        discovered_media_files: list[Path] = []
        if MEDIA_DIR.exists():
            discovered_media_files = list(MEDIA_DIR.glob("*.gif"))
            print(f"Found {len(discovered_media_files)} GIF files")
        else:
            print("No media directory found")

        return {
            "data_files": data_files,
            "media_files": discovered_media_files,
            "data_dir": DATA_DIR,
            "media_dir": MEDIA_DIR
        }

    except subprocess.CalledProcessError as e:
        print(f"Git clone failed: {e}")
        print(f"Git stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"Failed to extract data: {e}")
        return None

def copy_exercisedb_data(repo_data: dict[str, list[Path] | Path]) -> list[Path]:
    """Copy all ExerciseDB data files and media."""
    print("Copying ExerciseDB data...")

    # Create the output directory if it doesn't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []

    # Copy all JSON data files
    repo_data_files: list[Path] = repo_data["data_files"]  # type: ignore
    for data_file in repo_data_files:
        output_file = OUTPUT_DIR / data_file.name
        shutil.copy2(data_file, output_file)
        copied_files.append(output_file)
        print(f"Copied {data_file.name}")

    # Copy media files (GIFs)
    repo_media_dir: Path = repo_data["media_dir"]  # type: ignore
    if repo_media_dir.exists():
        media_output_dir = OUTPUT_DIR / "media"
        media_output_dir.mkdir(exist_ok=True)

        repo_media_files: list[Path] = repo_data["media_files"]  # type: ignore
        for media_file in repo_media_files:
            output_file = media_output_dir / media_file.name
            shutil.copy2(media_file, output_file)
            copied_files.append(output_file)
            print(f"Copied {media_file.name}")

    print(f"Copied {len(copied_files)} files total")
    return copied_files

def main() -> int:
    """Main function to clone repository and copy all ExerciseDB data."""
    print("ExerciseDB Complete Data Cloner")
    print("=" * 40)

    # Clone repository and extract all data
    repo_data = download_exercisedb_data()
    if not repo_data:
        print("Failed to extract data from repository. Exiting.")
        return 1

    # Copy all data files and media
    copied_files = copy_exercisedb_data(repo_data)

    print("\nSuccess! Complete ExerciseDB data has been embedded locally.")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Files copied: {len(copied_files)}")

    # Clean up the temporary repository
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
        print("Cleaned up temporary repository")

    return 0

if __name__ == "__main__":
    exit(main())
