#!/usr/bin/env python3
"""
Script to ultra-minify and upload ExerciseDB data to OpenAI for file_search tool usage.
Creates minimal data with only exerciseId and name to maximize token cost savings.
Automatically minifies data and uploads to OpenAI.
"""

import json
import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def minify_exercisedb():
    """Create an ultra-minimal version of ExerciseDB data for OpenAI with only exerciseId and name."""
    try:
        # Load original ExerciseDB data
        data_file = Path("src/buddy_gym_bot/data/exercises.json")
        if not data_file.exists():
            print("❌ ExerciseDB data not found. Run 'make update-exercises' first.")
            return None

        print("📖 Loading original ExerciseDB data...")
        with open(data_file, encoding="utf-8") as f:
            original_data = json.load(f)

        print(f"📊 Original data: {len(original_data)} exercises")
        original_size = data_file.stat().st_size
        print(f"📏 Original file size: {original_size / 1024:.1f} KB")

        # Ultra-minify the data - keep only exerciseId and name
        minified_data = []
        for exercise in original_data:
            minified_exercise = {
                "exerciseId": exercise.get("exerciseId"),
                "name": exercise.get("name"),
            }
            minified_data.append(minified_exercise)

        # Save minified data
        minified_file = Path("src/buddy_gym_bot/data/exercises_minified.json")
        with open(minified_file, "w", encoding="utf-8") as f:
            json.dump(minified_data, f, ensure_ascii=False, separators=(",", ":"))

        minified_size = minified_file.stat().st_size
        size_reduction = ((original_size - minified_size) / original_size) * 100

        print(f"✅ Ultra-minified data saved: {minified_file}")
        print(f"📊 Minified data: {len(minified_data)} exercises")
        print(f"📏 Minified file size: {minified_size / 1024:.1f} KB")
        print(f"💾 Size reduction: {size_reduction:.1f}%")
        print(f"💰 Estimated cost reduction: {size_reduction:.1f}%")
        print("🎯 Kept only: exerciseId, name")
        print(
            "🗑️  Removed: targetMuscles, bodyParts, equipments, secondaryMuscles, instructions, gifUrl"
        )

        return minified_file

    except Exception as e:
        print(f"❌ Error minifying ExerciseDB: {e}")
        return None


def upload_exercisedb_to_openai():
    """Upload ExerciseDB data to OpenAI and return vector_store_id for use with file_search tool."""
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not found in environment")
            return None

        # Check if minified data exists, create if not
        data_file = Path("src/buddy_gym_bot/data/exercises_minified.json")
        if not data_file.exists():
            print("📝 Minified data not found, creating it now...")
            data_file = minify_exercisedb()
            if not data_file:
                return None
        else:
            print("✅ Minified ExerciseDB data found")

        print("📤 Uploading to OpenAI...")

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Upload file to OpenAI
        with open(data_file, "rb") as f:
            file_response = client.files.create(
                file=f,
                purpose="assistants",  # This allows file_search tool usage
            )

        file_id = file_response.id
        print(f"✅ File uploaded successfully: {file_id}")

        # Create a vector store from the uploaded file
        print("🔍 Creating vector store...")
        vector_store_response = client.vector_stores.create(
            name="ExerciseDB Data", file_ids=[file_id]
        )

        vector_store_id = vector_store_response.id
        print(f"✅ Vector store created successfully: {vector_store_id}")

        # Save vector_store_id to local .env file for development
        env_file = Path(".env")
        env_content = f"\n# OpenAI ExerciseDB vector store ID (auto-updated)\nOPENAI_VECTOR_STORE_ID={vector_store_id}\n"

        # Append to .env file
        with open(env_file, "a") as f:
            f.write(env_content)

        print("💾 Vector store ID added to .env file")
        print(f"📊 File size: {data_file.stat().st_size / 1024:.1f} KB")

        print("\n🌍 For production deployment, set this secret in Fly.io:")
        print(f"   flyctl secrets set OPENAI_VECTOR_STORE_ID={vector_store_id}")
        print("   # Or update your .env file manually:")
        print(f"   # OPENAI_VECTOR_STORE_ID={vector_store_id}")

        return vector_store_id

    except Exception as e:
        print(f"❌ Error uploading to OpenAI: {e}")
        return None


def main():
    """Main function."""
    print("ExerciseDB Minifier & OpenAI Upload")
    print("=" * 40)

    vector_store_id = upload_exercisedb_to_openai()

    if vector_store_id:
        print("\n🎉 Success! ExerciseDB data minified and uploaded to OpenAI.")
        print(f"   Vector Store ID: {vector_store_id}")
        print("   Ready to use with file_search tool in OpenAI scheduling!")
        print("\n💡 To use this vector_store_id in your code:")
        print(f"   - Use in file_search tool with vector_store_ids: ['{vector_store_id}']")
        return 0
    else:
        print("\n💥 Process failed!")
        return 1


if __name__ == "__main__":
    exit(main())
