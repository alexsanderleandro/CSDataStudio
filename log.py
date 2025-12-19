import os
import json
import datetime
import shutil
from typing import Optional
import subprocess

try:
    import pyminizip
except Exception:
    pyminizip = None


def _safe_filename(s: str) -> str:
    return ''.join(c for c in s if c.isalnum() or c in ('-', '_')).rstrip()


class SessionLogger:
    """Registra ações do usuário durante a sessão e gera um ZIP protegido por senha.

    Uso:
        logger = SessionLogger(user_name, login_time)
        logger.log('action', 'mensagem', {'extra': 1})
        logger.close_session()
    """

    ZIP_PASSWORD = "PWDCEOSOFTWARE"

    def __init__(self, user_name: str, login_time: Optional[str] = None, logs_dir: Optional[str] = None):
        self.user_name = user_name or 'unknown'
        self.login_dt = None
        if isinstance(login_time, str):
            try:
                # aceita formatos com espaço ou T
                self.login_dt = datetime.datetime.fromisoformat(login_time.replace(' ', 'T'))
            except Exception:
                try:
                    self.login_dt = datetime.datetime.strptime(login_time, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    self.login_dt = datetime.datetime.now()
        elif isinstance(login_time, datetime.datetime):
            self.login_dt = login_time
        else:
            self.login_dt = datetime.datetime.now()

        self.logs_dir = logs_dir or os.path.join(os.path.dirname(__file__), 'Logs')
        os.makedirs(self.logs_dir, exist_ok=True)

        safe_user = _safe_filename(self.user_name)
        date_part = self.login_dt.strftime('%Y%m%d')
        time_part = self.login_dt.strftime('%H%M%S')
        base = f"log_{safe_user}_{date_part}_{time_part}"

        self.plain_path = os.path.join(self.logs_dir, base + '.log')
        self.zip_path = os.path.join(self.logs_dir, base + '.zip')

        # open plain log for append
        self._fh = open(self.plain_path, 'a', encoding='utf-8')
        self._write_header()

    def _write_header(self):
        self._fh.write(f"Session start: {self.login_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._fh.write(f"User: {self.user_name}\n")
        self._fh.write("---\n")
        self._fh.flush()

    def log(self, action: str, message: str = '', data: Optional[dict] = None):
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = {
            'timestamp': ts,
            'action': action,
            'message': message,
            'data': data or {}
        }
        line = json.dumps(entry, ensure_ascii=False)
        self._fh.write(line + '\n')
        self._fh.flush()

    def close_session(self):
        try:
            end_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._fh.write('---\n')
            self._fh.write(f"Session end: {end_ts}\n")

            # Inform about zip protection status before closing the plain file
            if pyminizip:
                self._fh.write('# ZIP_PROTECTION: requested (pyminizip present)\n')
            else:
                self._fh.write("# ZIP_PROTECTION: NOT_AVAILABLE - will create ZIP without password. To enable passworded ZIPs, install 'pyminizip' (requires Microsoft C++ Build Tools on Windows).\n")
                print("[WARN] pyminizip not available: session log will be zipped without password.")

            self._fh.flush()
            self._fh.close()

            # Try to create a password-protected zip using pyminizip when available
            created = False
            if pyminizip:
                try:
                    pyminizip.compress(self.plain_path, None, self.zip_path, self.ZIP_PASSWORD, 5)
                    os.remove(self.plain_path)
                    created = True
                except Exception:
                    print("[WARN] pyminizip failed to create passworded zip; will try 7-Zip or fallback to non-password zip.")

            # If not created yet, try 7-Zip (if available on the system) to create a passworded archive
            if not created:
                seven = None
                # common executable names
                for name in ("7z", "7za", "7zr", "7z.exe"):
                    seven = shutil.which(name)
                    if seven:
                        break
                # common Windows install locations
                if not seven and os.name == 'nt':
                    candidates = [
                        os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), '7-Zip', '7z.exe'),
                        os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), '7-Zip', '7z.exe')
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            seven = c
                            break

                if seven:
                    try:
                        # 7z a -pPASSWORD -mem=AES256 archive.zip file
                        cmd = [seven, 'a', f'-p{self.ZIP_PASSWORD}', '-mem=AES256', self.zip_path, self.plain_path]
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode == 0:
                            try:
                                os.remove(self.plain_path)
                            except Exception:
                                pass
                            created = True
                        else:
                            print(f"[WARN] 7-Zip failed: {res.returncode} {res.stderr}")
                    except Exception as e:
                        print(f"[WARN] Exception while invoking 7-Zip: {e}")

            # If still not created, create a regular zip as fallback (no password)
            if not created:
                try:
                    shutil.make_archive(self.zip_path[:-4], 'zip', root_dir=self.logs_dir, base_dir=os.path.basename(self.plain_path))
                    os.remove(self.plain_path)
                    print("[WARN] Created non-password zip as fallback for session log.")
                except Exception:
                    print("[ERROR] Failed to create any zip for session log.")
        except Exception:
            try:
                self._fh.close()
            except Exception:
                pass
