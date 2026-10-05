"""Attach notices, dependency inventory and application source to a onedir build."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import zipfile


def assemble(destination: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    if not destination.is_dir():
        raise ValueError(f"Missing onedir build: {destination}")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / name, destination / name)
    licenses = destination / "licenses"
    shutil.copytree(root / "packaging/licenses", licenses, dirs_exist_ok=True)
    packages = ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6",
                "requests", "urllib3", "certifi", "charset-normalizer", "idna",
                "Pillow", "numpy", "python-docx", "lxml", "typing_extensions")
    inventory = []
    from PySide6.QtCore import qVersion
    for name in packages:
        dist = metadata.distribution(name)
        inventory.append({"name": dist.metadata["Name"], "version": dist.version,
                          "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                          "project_urls": dist.metadata.get_all("Project-URL", []),
                          "homepage": dist.metadata.get("Home-page")})
        for item in dist.files or ():
            if any(word in item.name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    target = licenses / name / str(item).replace("..", "_parent")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    # Include Python's own license, even when it lives outside wheel metadata.
    import sysconfig
    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    manifest = {"python": sys.version, "qt": qVersion(), "packages": inventory}
    (destination / "dependency-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    directories = ("ai", "capture", "export", "platform_api", "sentinel", "storage", "ui", "tests", "packaging", "assets")
    files = [root / name for name in ("main.py", "config.py", "packaging_smoke.py", "requirements.txt", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "run.sh")]
    files.append(root / ".github/workflows/build-portable.yml")
    files.append(root / "branding.py")
    files += [p for name in directories for p in (root / name).rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".cpp", ".xml", ".sh", ".ps1", ".txt", ".svg")]
    with zipfile.ZipFile(destination / "cupi-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root))


if __name__ == "__main__":
    assemble(Path(sys.argv[1]))
