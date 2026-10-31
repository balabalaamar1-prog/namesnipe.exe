import traceback


def _crash(exc: BaseException) -> None:
    """A windowed exe has no console, so write errors to a log and tell the user."""
    from app.settings import data_dir
    log = data_dir() / "error.log"
    log.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    try:
        from tkinter import Tk, messagebox
        r = Tk(); r.withdraw()
        messagebox.showerror("Name Checker crashed", f"Details were saved to:\n{log}")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from app.gui import run
        run()
    except Exception as e:
        _crash(e)
