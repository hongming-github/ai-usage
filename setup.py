"""py2app build script.

    pip install py2app
    python setup.py py2app

Produces dist/AI Usage.app — a standalone menu bar app (LSUIElement, no Dock icon).
"""

from setuptools import setup

APP = ["run.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "AI Usage",
        "CFBundleDisplayName": "AI Usage",
        "CFBundleIdentifier": "com.github.aiusage",
        "CFBundleVersion": "0.1.0",
        "LSUIElement": True,  # menu bar only, no Dock icon
        "NSHighResolutionCapable": True,
    },
    "packages": ["rumps", "requests", "cryptography", "ai_usage"],
}

setup(
    app=APP,
    name="AI Usage",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
