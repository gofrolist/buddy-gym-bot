#!/usr/bin/env python3
"""
Simple script to upload ExerciseDB data to OpenAI for file_search tool usage.
This eliminates the need for complex vector store management.
"""

import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def upload_exercisedb_to_openai():
    """Upload ExerciseDB data to OpenAI and return file_id."""
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not found in environment")
            return None

        # Check if ExerciseDB data exists
        data_file = Path("src/buddy_gym_bot/data/exercises.json")
        if not data_file.exists():
            print("❌ ExerciseDB data not found. Run 'make update-exercises' first.")
            return None

        print("✅ ExerciseDB data found, uploading to OpenAI...")

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Upload file to OpenAI
        print("📤 Uploading file to OpenAI...")
        with open(data_file, 'rb') as f:
            file_response = client.files.create(
                file=f,
                purpose="assistants"  # This allows file_search tool usage
            )

        file_id = file_response.id
        print(f"✅ File uploaded successfully: {file_id}")

        # Save file_id to local .env file for development
        env_file = Path(".env")
        env_content = f"\n# OpenAI ExerciseDB file ID (auto-updated)\nOPENAI_FILE_ID={file_id}\n"

        # Append to .env file
        with open(env_file, 'a') as f:
            f.write(env_content)

        print("💾 File ID added to .env file")
        print(f"📊 File size: {data_file.stat().st_size / 1024:.1f} KB")

        print("\n🌍 For production deployment, set this secret in Fly.io:")
        print(f"   flyctl secrets set OPENAI_FILE_ID={file_id}")
        print("   # Or update your .env file manually:")
        print(f"   # OPENAI_FILE_ID={file_id}")

        return file_id

    except Exception as e:
        print(f"❌ Error uploading to OpenAI: {e}")
        return None

def main():
    """Main function."""
    print("OpenAI File Upload for ExerciseDB")
    print("=" * 40)

    file_id = upload_exercisedb_to_openai()

    if file_id:
        print("\n🎉 Success! ExerciseDB data uploaded to OpenAI.")
        print(f"   File ID: {file_id}")
        print("   Ready to use with file_search tool in OpenAI scheduling!")
        print("\n💡 To use this file_id in your code:")
        print("   - Load from: src/buddy_gym_bot/data/openai_file_id.json")
        print(f"   - Use in file_search tool with file_ids: ['{file_id}']")
        return 0
    else:
        print("\n💥 Upload failed!")
        return 1

if __name__ == "__main__":
    exit(main())
