"""Local source and user-state backup; excludes bulky HCAD downloads and virtualenv."""
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent


def main():
    destination = ROOT / "output" / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    destination.mkdir(parents=True)
    files = subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=ROOT).decode().split("\0")
    target = destination / "TexasInvestors-source-and-state.zip"
    with ZipFile(target,"w",ZIP_DEFLATED) as archive:
        for name in sorted(set(files)):
            if not name:
                continue
            path = (ROOT/name).resolve()
            path.relative_to(ROOT)
            if path.is_file():
                archive.write(path,"source/"+name)
        for db in sorted((ROOT/"audit_logs").glob("*.db")):
            copy_path=destination/db.name
            source=sqlite3.connect(str(db));backup=sqlite3.connect(str(copy_path))
            try:
                source.backup(backup)
            finally:
                source.close();backup.close()
            archive.write(copy_path,"state/audit_logs/"+db.name)
        state_files = list((ROOT/"output").glob("*.csv"))+list((ROOT/"data/imports").glob("*.csv"))
        state_files += [ROOT/"output/lead_status.json"]
        for path in state_files:
            if path.is_file():
                archive.write(path,"state/"+path.relative_to(ROOT).as_posix())
        archive.writestr("backup-info.json",json.dumps({"created":datetime.now().isoformat(),"excludes":["raw HCAD downloads","virtual environment","phone credentials (regenerate)"]}))
    with ZipFile(target) as archive:
        assert archive.testzip() is None
    print(json.dumps({"backup":str(target),"bytes":target.stat().st_size}))


if __name__ == "__main__":
    main()
