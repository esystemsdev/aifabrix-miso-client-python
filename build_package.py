#!/usr/bin/env python
"""
Helper script to build and verify the package.
"""
import subprocess
import sys
import os

def main():
    """Build and verify the package."""
    print("Building package...")
    
    # Clean previous builds
    for dir_name in ['build', 'dist', '*.egg-info']:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            import shutil
            if os.path.isdir(dir_name):
                shutil.rmtree(dir_name)
    
    # Build the package
    try:
        subprocess.check_call([sys.executable, "-m", "build", "--wheel", "--sdist"], 
                            cwd=os.getcwd())
        print("\n✓ Package built successfully!")
        print("\nTo install locally:")
        print("  pip install dist/miso_client-*.whl")
        print("\nOr in development mode:")
        print("  pip install -e .")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        sys.exit(1)
    except ImportError:
        print("\n⚠ build module not found. Install it with:")
        print("  pip install build")
        print("\nPackage structure is ready for building.")
        print("You can build it later with:")
        print("  python -m build")

if __name__ == "__main__":
    main()

