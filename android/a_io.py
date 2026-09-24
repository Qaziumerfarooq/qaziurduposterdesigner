"""File / intent bridges that work on Android (SAF) and gracefully on desktop.

Android API 29+ (scoped storage) blocks random reads/writes to other apps'
folders. The reliable mobile pattern is:
  - IMPORT  : SAF "Open Document" picker -> bytes via ContentResolver fd
  - EXPORT  : SAF "Create Document" picker -> write fd
  - QUICK   : save to our private dir + Android share sheet (FileProvider)

On desktop these helpers fall back so the Kivy UI can also run for testing.
"""
import os

from kivy.utils import platform

IS_ANDROID = platform == "android"

try:
    from android import activity as _actmod
except Exception:
    _actmod = None

_CODE = 9001


def _activity():
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    return PythonActivity.mActivity


def _read_bytes_from_fd(fd):
    with os.fdopen(fd, "rb") as f:
        return f.read()


def _read_uri_bytes(uri):
    from jnius import autoclass
    Uri = autoclass("android.net.Uri")
    act = _activity()
    cr = act.getContentResolver()
    pfd = cr.openFileDescriptor(Uri.parse(str(uri)), "r")
    fd = pfd.detachFd()
    try:
        return _read_bytes_from_fd(fd)
    finally:
        try:
            os.close(fd)
        except Exception:
            pass


def _read_uri_name(uri, fallback="file"):
    try:
        act = _activity()
        cr = act.getContentResolver()
        name = cr.loadName(__import__("jnius", fromlist=["autoclass"]).autoclass(
            "android.net.Uri").parse(str(uri)))
        if name:
            return name
    except Exception:
        pass
    try:
        seg = str(uri).strip().rstrip("/").split("/")[-1]
        return seg or fallback
    except Exception:
        return fallback


def _unbind(handler):
    try:
        if _actmod is not None:
            _actmod.unbind(on_activity_result=handler)
    except Exception:
        pass


def _launch(intent, handler):
    if _actmod is not None:
        _actmod.bind(on_activity_result=handler)
    act = _activity()
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    act.startActivityForResult(Intent.createChooser(intent, "Select"), _CODE)


def pick_file(on_result, mime="*/*"):
    """Open Android SAF picker. on_result(None) on cancel/error, else
    on_result((name, bytes)). Returns True when the picker was launched."""
    if not IS_ANDROID or _actmod is None:
        return False
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")

        def handler(request_code, result_code, data):
            _unbind(handler)
            try:
                if request_code == _CODE and result_code == -1 and data is not None:
                    uri = data.getData()
                    if uri is not None:
                        name = _read_uri_name(uri)
                        b = _read_uri_bytes(uri)
                        on_result((name, b))
                        return
            except Exception:
                pass
            on_result(None)

        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.setType(mime)
        _launch(intent, handler)
        return True
    except Exception:
        return False


def create_document(suggested_name, mime, on_writer):
    """Android SAF "Create Document" -> on_writer(fd) called with a write fd.
    on_writer(None) when cancelled. Returns True if the dialog was launched."""
    if not IS_ANDROID or _actmod is None:
        return False
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")

        def handler(request_code, result_code, data):
            _unbind(handler)
            try:
                if request_code == _CODE and result_code == -1 and data is not None:
                    uri = data.getData()
                    if uri is not None:
                        act = _activity()
                        cr = act.getContentResolver()
                        pfd = cr.openFileDescriptor(Uri.parse(str(uri)), "w")
                        fd = pfd.detachFd()
                        on_writer(fd)
                        return
            except Exception:
                pass
            on_writer(None)

        intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(mime)
        intent.putExtra(Intent.EXTRA_TITLE, suggested_name)
        _launch(intent, handler)
        return True
    except Exception:
        return False


def share_file(path, mime):
    """Share a file via the system share sheet (best-effort)."""
    try:
        from plyer import share
        import threading
        def _do():
            try:
                share.share(file_path=path, mime_type=mime)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()
        return True
    except Exception:
        return False